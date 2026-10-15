#!/usr/bin/env bash
# tests/lib.sh — the single shared bash harness for crayon's two bash suites (D-10).
#
# `tests/test_crayon_acceptance.sh` (the ported A-series) and
# `tests/test_crayon_lifecycle.sh` (the N-series lifecycle / negative / recovery
# suite) both source this file, and neither redefines any of it. Everything
# below moved out of tests/test_crayon_acceptance.sh verbatim, comments included:
# the WR-07 / WR-08 / WR-09 rationales are load-bearing and travel with the code
# they justify.
#
# NO function in this file may be named with the `test_` prefix. Both suites
# discover their tests with `declare -F | awk '{print $3}' | grep '^test_'`, so a
# helper carrying that prefix would be auto-discovered as a test in BOTH suites
# at once (RESEARCH Pitfall 13), and the only thing between that and a silent
# green is the WR-09 vacuous-test guard in `run_test`. A grep gate in this
# plan's verification asserts the count stays zero.
#
# Every test drives the real `crayon` executable in a hermetic temp git repo:
# argparse, the lock, containment, derivation, routing, the six-step write
# protocol, the trailered pathspec-scoped commit and the post-commit check.
# Nothing is stubbed. Each test function runs in a SUBSHELL so `cd` cannot leak,
# and assertions are recorded through a results file because a subshell cannot
# write the parent's counters.
#
# The harness shape (run_test / assert_* / auto-discovery / the
# "Results: N passed, N failed" line) is copied from the v1.x bash suite,
# `git show 357c513:tests/test_dogen_scripts.sh`, which plan 17-10 deleted from
# the tree once its 32 tests had been ported to A-01…A-35.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CRAYON="$REPO_ROOT/crayon.py"

PASS=0
FAIL=0
FAILED_TESTS=()

RESULTS="$(mktemp)"
trap 'rm -f "$RESULTS"' EXIT

_record_pass() {
    printf 'PASS\n' >>"$RESULTS"
}

_record_fail() {
    printf 'FAIL\t%s\n' "$1" >>"$RESULTS"
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        _record_pass
    else
        _record_fail "$desc (expected: '$expected', got: '$actual')"
    fi
    return 0
}

# Phase-17 IN-05: two digests are compared for INEQUALITY, never for
# non-containment. `assert_not_contains "$before" "$fresh"` on two equal-length
# hex strings happens to be equivalent, and reads as a containment claim that
# will mislead the next editor -- the same "an assertion that says something
# other than what it checks" class as WR-18.
assert_not_eq() {
    local desc="$1" unexpected="$2" actual="$3"
    if [ "$unexpected" != "$actual" ]; then
        _record_pass
    else
        _record_fail "$desc (expected anything but: '$unexpected')"
    fi
    return 0
}

# WR-12: the three substring assertions were `grep -qF -- "$needle"`, which has
# two failure modes the suite could not see.
#
#   1. `grep -F ''` matches EVERY line, so an assertion whose needle expanded to
#      the empty string recorded a PASS. `set -u` catches an UNSET variable,
#      never an empty one, and call sites pass variables (`"$ADOPT_SUFFIX"`,
#      `"$verb"`) — a helper that returned nothing would have turned its
#      assertions green rather than red.
#   2. `grep -F` treats a MULTI-LINE needle as a set of ALTERNATIVES, so a
#      multi-line expectation passed when any ONE of its lines matched.
#
# The `case` form below is a true substring test, which answers (2) outright;
# an empty needle is recorded as a failure by name, because the honest report
# for "this assertion asserts nothing" is a failure and not a pass.
_needle_guard() {
    if [ -z "$2" ]; then
        _record_fail "$1 (the expected substring is empty — a vacuous assertion)"
        return 1
    fi
    return 0
}

assert_contains() {
    local desc="$1" haystack="$2" needle="$3"
    _needle_guard "$desc" "$needle" || return 0
    case "$haystack" in
        *"$needle"*) _record_pass ;;
        *) _record_fail "$desc (expected to contain: '$needle', got: '$haystack')" ;;
    esac
    return 0
}

assert_not_contains() {
    local desc="$1" haystack="$2" needle="$3"
    # Same true-substring test as its positive twin, deliberately: a pair whose
    # two halves disagree about what "contains" means is a trap of its own.
    _needle_guard "$desc" "$needle" || return 0
    case "$haystack" in
        *"$needle"*) _record_fail "$desc (expected NOT to contain: '$needle')" ;;
        *) _record_pass ;;
    esac
    return 0
}

# D-16: the ledger vocabulary no human success line may carry, in Python `re`
# syntax. This is its ONE definition site; `assert_plain` reads it, and the
# lifecycle suite's self-test drives it against the forbidden samples. `seq`
# followed by a number, `sealed`, `basis` and `plan_hash` as whole words, and
# any run of 12 or more lowercase hex characters (a digest or a long sha). A
# seven-character short sha stays allowed: a human line may give the short
# commit sha where it helps the reader find it (P-06).
LEDGER_WORDS_RE='\bseq\s*[0-9]|\bsealed\b|\bbasis\b|\bplan_hash\b|[0-9a-f]{12,}'

# D-16: TEXT carries none of LEDGER_WORDS_RE. A match is recorded as a failure
# naming the matched words; so is a matcher that could not run, because a
# check that silently checked nothing is the vacuous pass WR-12 forbids.
assert_plain() {
    local desc="$1" text="$2" hit rc
    hit=$(python3 -c '
import re, sys
match = re.search(sys.argv[1], sys.argv[2])
if match:
    print(match.group(0))
    sys.exit(3)
' "$LEDGER_WORDS_RE" "$text" 2>&1)
    rc=$?
    if [ "$rc" -eq 0 ]; then
        _record_pass
    elif [ "$rc" -eq 3 ]; then
        _record_fail "$desc (ledger vocabulary '$hit' in: '$text')"
    else
        _record_fail "$desc (the ledger-vocabulary matcher failed: $hit)"
    fi
    return 0
}

assert_file_exists() {
    local desc="$1" file="$2"
    if [ -e "$file" ]; then
        _record_pass
    else
        _record_fail "$desc (file $file should exist)"
    fi
    return 0
}

assert_file_not_exists() {
    local desc="$1" file="$2"
    if [ ! -e "$file" ]; then
        _record_pass
    else
        _record_fail "$desc (file $file should not exist)"
    fi
    return 0
}

assert_file_contains() {
    local desc="$1" file="$2" needle="$3"
    _needle_guard "$desc" "$needle" || return 0
    if [ ! -f "$file" ]; then
        _record_fail "$desc (file $file does not exist)"
        return 0
    fi
    local haystack
    haystack=$(cat -- "$file")
    case "$haystack" in
        *"$needle"*) _record_pass ;;
        *) _record_fail "$desc (file $file expected to contain: '$needle')" ;;
    esac
    return 0
}

# One JSON refusal line on stderr — never zero, never two, never a stack trace,
# and always the full five-key object (contract 5.7).
assert_json_error() {
    local desc="$1" errfile="$2" expected="$3"
    local lines
    lines=$(wc -l <"$errfile" | tr -d ' ')
    assert_eq "$desc: exactly one stderr line" "1" "$lines"
    local got
    got=$(python3 -c '
import json, sys
payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
missing = [k for k in ("error", "unit", "detail", "hint", "next") if k not in payload]
print("MISSING:" + ",".join(missing) if missing else payload["error"])
' "$errfile" 2>/dev/null)
    assert_eq "$desc: error code" "$expected" "$got"
    return 0
}

assert_json_detail() {
    local desc="$1" errfile="$2" expected="$3"
    local got
    got=$(python3 -c '
import json, sys
print(json.loads(open(sys.argv[1], encoding="utf-8").read()).get("detail"))
' "$errfile" 2>/dev/null)
    assert_eq "$desc: detail" "$expected" "$got"
    return 0
}

# --- the shared hermetic temp-repo helper (D-11) -----------------------------

# GIT_CONFIG_GLOBAL/SYSTEM are pinned to /dev/null so the developer's global
# config — commit.gpgsign above all (RESEARCH P-9) — cannot leak into a test
# repo, and CRAYON_NOW is pinned so every ledger byte, and therefore every chain
# digest, is reproducible.
setup_repo() {
    export GIT_CONFIG_GLOBAL=/dev/null
    export GIT_CONFIG_SYSTEM=/dev/null
    export GIT_AUTHOR_DATE="2026-01-01T00:00:00+00:00"
    export GIT_COMMITTER_DATE="2026-01-01T00:00:00+00:00"
    export CRAYON_NOW="2026-01-01T00:00:00+00:00"
    # WR-07: CRAYON_NOW and CRAYON_CRASH_AT are armed only by this explicit
    # switch, so neither is live in the shipped executable.
    export CRAYON_TEST_HOOKS=1
    unset CRAYON_CRASH_AT || true
    # WR-08: `cd ""` SUCCEEDS in bash and leaves the shell where it is, so
    # `cd "$TEST_DIR" || exit 1` is not a guard. With an unchecked `mktemp -d`
    # — a full or read-only /tmp, a restrictive TMPDIR — every test below would
    # then `git init`, overwrite `docs/index.md` and commit in the CURRENT
    # directory, which is the crayon repository, and `cleanup`'s `[ -n ... ]`
    # guard would keep it. The three checks make the failure loud instead.
    TEST_DIR=$(mktemp -d) || exit 1
    [ -n "$TEST_DIR" ] && [ -d "$TEST_DIR" ] || exit 1
    cd "$TEST_DIR" || exit 1
    git init -q -b main .
    git config user.name "Test Author"
    git config user.email "test@example.com"
    mkdir -p docs/reference
    printf '# Docs\n' >docs/index.md
    git add -A
    git commit -q -m "initial"
}

cleanup() {
    cd / || return 0
    [ -n "${TEST_DIR:-}" ] && rm -rf "$TEST_DIR"
    TEST_DIR=""
    return 0
}

# `crayon unit new` with the §6 signature filled in; extra flags pass through.
crayon_unit_new() {
    local unit="$1" target="$2"
    shift 2
    printf '# Plan\n\nAn outline.\n' |
        "$CRAYON" unit new "$unit" \
            --intent reference \
            --audience "TAs onboarding to the docs repo" \
            --title "Demo" \
            --target "$target" \
            --body-file - "$@"
}

# Phase-16 IN-03: git's own first line for a pathspec `crayon` would refuse,
# read from git under the SAME locale `crayon` pins for the probe (IPC_LOCALE).
# The assertions that used to hardcode git's English sentence ask git for it
# instead, so they state the property -- "the detail is git's own words" --
# rather than one release's translation of them.
git_add_first_line() {
    # DEF-18-01: `LANGUAGE=` and `LANGUAGE=''` assign the same empty string for
    # the duration of the command, but shellcheck 0.11.0 reads the bare form as
    # a stray assignment and reports SC1007 at warning level. Whether the
    # runner's pinned 0.9.0 reports it could not be established here -- the
    # policy is to reproduce a finding against the pinned version before
    # changing code for it, and installing a second shellcheck is not something
    # the gate may do. The explicit empty string is the form SC1007's own
    # message suggests and is clean under every version, so it settles the
    # question instead of answering it.
    LC_ALL=C LANGUAGE='' git add --dry-run --ignore-missing -- "$@" 2>&1 | sed -n '1p'
}

# WR-17 (phase 18): the declaring verbs now apply the same filesystem rules
# `sign_sources` applies, so a source `signoff` cannot read is no longer
# REACHABLE by a command. It is still reachable by hand -- `unit.md` is a plain
# file an author may edit and `signoff` re-reads it fresh -- which is exactly
# why the signoff-side guard stays. This is how the tests for it get there.
hand_edit_source() {
    local unit="$1" from="$2" to="$3"
    python3 -c '
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()
quoted = chr(34)
assert quoted + old + quoted in text, "hand_edit_source: %r is not in %s" % (old, path)
open(path, "w", encoding="utf-8").write(
    text.replace(quoted + old + quoted, quoted + new + quoted)
)
' ".crayon/units/${unit}/unit.md" "$from" "$to"
}

ledger_line() {
    local unit="$1" number="$2"
    sed -n "${number}p" ".crayon/units/${unit}/ledger.jsonl"
}

json_field() {
    python3 -c '
import json, sys
value = json.loads(sys.stdin.read()).get(sys.argv[1])
print("null" if value is None else value)
' "$1"
}

sha256_of_text() {
    printf '%s' "$1" | python3 -c '
import hashlib, sys
print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())
'
}

# --- pre-commit hook fixtures (contract 5.8 step 5) --------------------------

# A pre-commit hook runs inside the tool's own transaction, against a TEMPORARY
# index git points GIT_INDEX_FILE at for a partial commit — which is exactly how
# a hook gets bytes and paths into a commit the tool believed it had scoped
# (RESEARCH P-1, P-2). Both real shapes are fixtures here.
install_hook() {
    printf '#!/bin/sh\n' >.git/hooks/pre-commit
    cat >>.git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
}

# The formatter shape a real pre-commit framework installs: rewrite the file AND
# stage it, so the rewritten bytes reach the temporary index and therefore HEAD.
install_rewrite_and_succeed_hook() {
    local path="$1"
    install_hook <<HOOK
printf 'HOOKFORMATTED\n' > '${path}'
git add -- '${path}'
exit 0
HOOK
}

# The other real shape: rewrite the worktree but stage nothing. git builds the
# partial commit's temporary index from the worktree BEFORE hooks run, so these
# bytes never reach HEAD — only the disk side of the two-sided digest check sees
# them. This is why `git show HEAD:<path>` alone is not sufficient evidence.
install_rewrite_without_staging_hook() {
    local path="$1"
    install_hook <<HOOK
printf 'HOOKFORMATTED\n' > '${path}'
exit 0
HOOK
}

install_rewrite_and_stage_unrelated_hook() {
    local path="$1" unrelated="$2"
    install_hook <<HOOK
printf 'HOOKFORMATTED\n' > '${path}'
printf 'hook wrote this\n' > '${unrelated}'
git add -- '${unrelated}'
exit 0
HOOK
}

install_rewrite_and_reject_hook() {
    local path="$1"
    install_hook <<HOOK
printf 'HOOKFORMATTED\n' > '${path}'
exit 1
HOOK
}

# The realistic "reformat and reject" shape, and the one CR-01 was filed for:
# the hook CANONICALISES the target and rejects only when it actually had to
# change a byte. A target that is already canonical commits untouched — which
# is what makes `--adopt` the escape contract 5.8's hook paragraph promises,
# and what the unconditional rewriter above cannot model. Its output is the
# same `HOOKFORMATTED` line, so a fixture can make a page's PRE-transition
# bytes equal the hook's output and reproduce the livelock shape.
install_canonicalising_reject_hook() {
    local path="$1"
    install_hook <<HOOK
if [ "\$(cat '${path}' 2>/dev/null)" = "HOOKFORMATTED" ]; then
    exit 0
fi
printf 'HOOKFORMATTED\n' > '${path}'
exit 1
HOOK
}

# The ordinary "lint failed" shape, and the majority one: the hook REJECTS and
# rewrites NOTHING. CR-01 (iteration 3) is why it is a fixture — every other
# reject hook here also rewrites its target, which is the one shape where
# `resume --adopt` has an `unexpected` file to adopt. With the placed bytes
# untouched `--adopt` has nothing to adopt, degrades to a plain resume by
# contract 5.8, re-places the same bytes and meets the same hook, so the escape
# reproduces the refusal it was offered against. That is the shape no fixture
# covered.
install_reject_only_hook() {
    install_hook <<'HOOK'
echo "policy: nope" >&2
exit 1
HOOK
}

# The other ordinary reject shape, and the one CR-01 (iteration 4) was filed
# for: "generated files must not be committed" — the hook DELETES its target
# and rejects. `classify_file` returns `unexpected` whenever a placed file's
# disk bytes are not `after_sha`, and an absent file is one of those, so the
# batch reaches `resume_adopt`'s SECOND `adopt_unsupported` arm — the "no
# current bytes to adopt" one, which no fixture had ever driven. Every other
# reject hook here either rewrites its target or leaves it alone.
install_delete_and_reject_hook() {
    local path="$1"
    install_hook <<HOOK
rm -f '${path}'
exit 1
HOOK
}

# The "append a distinct marker on every run" shape, and the one WR-03 was
# filed for: each pass leaves DIFFERENT bytes, so a batch that has already been
# adopted once still classifies its target `unexpected` and still satisfies all
# three published `--adopt` conditions. The fourth condition — that the last
# event is not itself an adoption — is the one the tool applies and no surface
# stated, and this hook is what drives a batch into it.
install_appending_reject_hook() {
    local path="$1"
    install_hook <<HOOK
pass=\$(cat .git/hookpass 2>/dev/null || echo 0)
pass=\$((pass + 1))
printf '%s\n' "\$pass" >.git/hookpass
printf 'HOOKPASS%s\n' "\$pass" >>'${path}'
exit 1
HOOK
}

install_whitespace_hook() {
    local path="$1"
    install_hook <<HOOK
sed -i 's/\$/ /' '${path}'
exit 0
HOOK
}


# --- the shared fixtures both suites read state through (17-11) --------------
#
# These were defined in tests/test_crayon_acceptance.sh until plan 17-11 moved
# the T-labelled bodies out of it. the ported A-series and the migrated N-series
# BOTH call them, so neither file can own them: a copy in each is precisely how
# the two suites drift apart (D-10). They live here, once, like the rest of the
# harness.

ledger_digest() {
    sha256_of_text "$(cat ".crayon/units/$1/ledger.jsonl" 2>/dev/null || true)"
}

sha256_of_file() {
    python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$1"
}

# One derived field, read through the tool's own `unit_state`/`route`. `show`
# (plan 16-06) will print this for the author; until then the acceptance suite
# reads it directly rather than asserting state through a surface that does not
# exist yet.
derived() {
    local unit="$1" field="$2"
    python3 -c '
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
state = module.unit_state(os.getcwd(), sys.argv[2])
value = module.route(state) if sys.argv[3] == "next" else state[sys.argv[3]]
print(value if isinstance(value, str) else json.dumps(value))
' "$CRAYON" "$unit" "$field"
}

# CR-05: re-sign the unit onto a target that traverses OUT of the docs root and
# record a basis for it, all through the tool's own writer so the chain still
# verifies. This is exactly the artefact an untrusted branch or PR carries:
# `.crayon/` is committed, so a forged `ledger.jsonl` is ordinary contributor
# input, and the escaping path is read by the REVIEWER's own `crayon show`.
forge_escaping_target() {
    local unit="$1" victim="$2"
    python3 -c '
import importlib.machinery, importlib.util, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
repo, unit, victim = os.getcwd(), sys.argv[2], sys.argv[3]
relative = os.path.relpath(victim, os.path.join(repo, "docs"))
path = module.ledger_path(repo, unit)
records = module.read_events(path)
signoff = module.derive([event for event, _ in records],
                        {"unit_md_sha": None, "paths": {}})["so"]
payload = {key: value for key, value in signoff.items()
           if key not in ("kind", "seq", "prev", "at", "actor", "tool_version",
                          "contract", "commit")}
payload["targets"] = [relative]
actor = {"name": "Test Author", "email": "test@example.com"}
seq = len(records)
events = [
    module.build_event("signoff", seq, module.chain_prev(records[-1][1]), actor,
                       None, payload),
    module.build_event("generation", seq + 1, None, actor, None, {
        "files": [{"path": relative, "sha256": "0" * 64, "bytes": 1}],
        "signoff_seq": seq,
        "plan_hash": payload.get("plan_hash"),
        "model": "m",
        "model_origin": "configured",
        "basis_seq": None,
        "unsteered": False,
    }),
]
module.append_batch(path, module.chain_lines(events))
sys.stdout.write(relative)
' "$CRAYON" "$unit" "$victim"
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: forged escaping target ${unit}" >/dev/null 2>&1
}

# Stage draft bytes under `.crayon/staging/<id>/draft/` — contract 5.6's only
# sanctioned source for a page. The staging tree is gitignored input, never a
# recorded artifact.
stage_draft() {
    local unit="$1" target="$2" content="$3"
    local path=".crayon/staging/${unit}/draft/${target}"
    mkdir -p "$(dirname "$path")"
    # %b so a fixture can spell a real newline as \n inside one argument.
    printf '%b' "$content" >"$path"
}

draft_path() {
    printf '.crayon/staging/%s/draft/%s' "$1" "$2"
}

# "<path> <sha256> <bytes>" per entry of an event's files[], in recorded order.
event_files() {
    python3 -c '
import json, sys
for entry in json.loads(sys.stdin.read()).get("files") or []:
    print("%s %s %s" % (entry.get("path"), entry.get("sha256"), entry.get("bytes")))
'
}

# "<path> <sha256>" per entry of a reviewer-edit's files[], in recorded order.
edit_files() {
    python3 -c '
import json, sys
for entry in json.loads(sys.stdin.read()).get("files") or []:
    print("%s %s" % (entry.get("path"), entry.get("sha256")))
'
}

# A drafted unit: seq 0 ledger, 1 unit-declared, 2 signoff, 3 generation.
setup_drafted_unit() {
    local unit="$1" target="$2"
    crayon_unit_new "$unit" "$target" >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
    stage_draft "$unit" "$target" "Demo\n====\n\nThe drafted body.\n"
    "$CRAYON" draft "$unit" "$(draft_path "$unit" "$target")" >/dev/null 2>&1
}

# The `next` token of a refusal line — the token the skill routes on.
refusal_next() {
    python3 -c '
import json, sys
print(json.loads(open(sys.argv[1], encoding="utf-8").read()).get("next"))
' "$1"
}

# verify_chain over the WHOLE ledger, through the tool's own verifier.
chain_problems() {
    python3 -c '
import importlib.machinery, importlib.util, json, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
text = open(sys.argv[2], encoding="utf-8").read()
print(json.dumps(module.verify_chain([line for line in text.split("\n") if line])))
' "$CRAYON" ".crayon/units/$1/ledger.jsonl"
}

# --- Runner ------------------------------------------------------------------

# Each test runs in a SUBSHELL so `cd` cannot leak, and reports one TAP line.
# TAP granularity is per test function; the `Results:` line below counts
# assertions. Both are emitted from the same real run.
TAP_INDEX=0
TAP_PASS=0
TAP_FAIL=0

run_test() {
    local name="$1"
    local before rc failed_here ran_here
    before=$(wc -l <"$RESULTS")
    (
        set +e
        "$name"
        exit 0
    )
    rc=$?
    # Counted BEFORE the two synthetic failures below, so they cannot mask a
    # test that recorded nothing of its own.
    ran_here=$(awk -v start="$before" 'NR > start' "$RESULTS" | wc -l)
    failed_here=$(awk -v start="$before" 'NR > start && /^FAIL/ {n++} END {print n + 0}' "$RESULTS")
    if [ "$rc" -ne 0 ]; then
        _record_fail "$name (subshell exited $rc)"
        failed_here=$((failed_here + 1))
    fi
    # WR-09: the verdict used to be "no FAIL lines", so a test that returned
    # early — a renamed helper, an `if` that never fires, a `cleanup` reached
    # before the assertions — recorded zero assertions and printed `ok`. With
    # one aggregate count over 150+ tests, a silently vacuous test is invisible.
    if [ "$ran_here" -eq 0 ]; then
        _record_fail "$name (recorded no assertions)"
        failed_here=$((failed_here + 1))
    fi
    TAP_INDEX=$((TAP_INDEX + 1))
    if [ "$failed_here" -eq 0 ]; then
        TAP_PASS=$((TAP_PASS + 1))
        echo "ok ${TAP_INDEX} - ${name}"
    else
        TAP_FAIL=$((TAP_FAIL + 1))
        echo "not ok ${TAP_INDEX} - ${name}"
    fi
    return 0
}

main() {
    echo "TAP version 13"

    local test_fn
    for test_fn in $(declare -F | awk '{print $3}' | grep '^test_'); do
        run_test "$test_fn"
    done

    # WR-09's FILE-level counterpart (T-17-49). `run_test` above catches a test
    # that recorded nothing; until plan 17-11 nothing caught a SUITE that
    # defined nothing. A file whose function definitions are lost to a bad edit
    # — a stray `}`, a botched merge, a migration that moves 181 bodies between
    # two files — printed `1..0`, `# fail 0` and `Results: 0 passed, 0 failed`
    # and exited 0, which is byte-for-byte what a healthy run over a working
    # system looks like. Discovery finding nothing is a failure, always, and it
    # is recorded through the same results file so the `Failed assertions:`
    # block below names it.
    if [ "$TAP_INDEX" -eq 0 ]; then
        TAP_INDEX=1
        TAP_FAIL=1
        echo "not ok 1 - the suite discovered no test functions"
        _record_fail "$0 discovered no test functions (nothing matched '^test_')"
    fi

    PASS=$(awk '/^PASS/ {n++} END {print n + 0}' "$RESULTS")
    FAIL=$(awk '/^FAIL/ {n++} END {print n + 0}' "$RESULTS")
    while IFS= read -r line; do
        FAILED_TESTS+=("$line")
    done < <(awk -F'\t' '/^FAIL/ {print $2}' "$RESULTS")

    echo "1..${TAP_INDEX}"
    echo "# tests ${TAP_INDEX}"
    echo "# pass ${TAP_PASS}"
    echo "# fail ${TAP_FAIL}"
    echo ""
    echo "Results: ${PASS} passed, ${FAIL} failed"

    if [ "$FAIL" -gt 0 ]; then
        echo ""
        echo "Failed assertions:"
        local t
        for t in "${FAILED_TESTS[@]}"; do
            echo "  - $t"
        done
        exit 1
    fi
    exit 0
}
