#!/usr/bin/env bash
# validation/fixtures.sh — V-01…V-04: each corruption REACHED from a valid unit (D-09).
#
# Every fixture here builds a real unit with the real verbs — `unit new`, `signoff`,
# `draft`, `steer` — in a hermetic temp git repo, and only then breaks it in exactly one
# named way. That is the whole point of the file: a corruption assembled by hand from a
# checked-in ledger tree proves nothing about a state the tool can actually reach, and a
# `prev` digest typed by a human is a digest the writer never produced (LEDG-06, D-09).
#
# It sources `tests/lib.sh` rather than re-implementing a harness (17 D-10: one definition
# site). From there it gets `setup_repo`, `setup_drafted_unit`, `ledger_line`, `assert_eq`,
# `assert_contains`, `cleanup`, the per-test subshell, the WR-09 vacuous-test guard, the
# assertion counting and the TAP emit. None of that is redefined below.
#
# The `test_` prefix is load-bearing and constrained in BOTH directions. `main`'s discovery
# is `declare -F | awk '{print $3}' | grep '^test_'`, so any helper carrying the prefix
# would silently be run as a test — every helper below therefore does NOT carry it. And
# D-12's widened `tests/check_traces.py` keys the four V-0N trace ids off the underscore-
# bounded `v01`…`v04` tokens in these names, so only the four V-0N fixtures may carry a
# `vNN` token. The `test_score_*` fixtures pin properties of the scorer itself and carry no
# `X-NN` id for the trace checker to key on, deliberately.
#
# Exit codes are `tests/lib.sh`'s, which are the project's 0/1/2 lint contract:
#   0  every assertion passed
#   1  at least one assertion failed
#   2  is unreachable here — the harness reports a suite that discovered nothing as a
#      FAILED test (`not ok 1 - the suite discovered no test functions`), not as a 2
#
# `shellcheck -S warning validation/fixtures.sh` must be clean from this file's first
# commit: plan 19-04 widens CI's glob to `tests/*.sh validation/*.sh`, and a glob with no
# match expands literally, so the file and the widening have to be able to land together
# (Pitfall 12).

# shellcheck source=../tests/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../tests/lib.sh"

SCORE="$REPO_ROOT/validation/score.py"

# `dogen` is not checked into a documentation repository, so `score.py` resolves the tool
# from `DOGEN` first. `tests/lib.sh` assigns it but does not export it; exporting it here is
# what lets the scorer's `[verify]` arm reach the same in-tree executable the fixtures drive.
export DOGEN

# --- helpers (NEVER `test_`-prefixed — `main` would discover them as tests) -------------

# Run the scorer's `audit` over the hermetic repo and capture BOTH streams plus the exit
# code. stdout+stderr are merged on purpose: a fixture that asserts the exit code alone
# passes on the wrong finding (T-19-07), and a traceback is stderr text a fixture must be
# able to see.
audit_output() {
    local unit="$1"
    AUDIT_OUT=$(python3 "$SCORE" audit "$unit" --root "$TEST_DIR" 2>&1)
    AUDIT_RC=$?
    return 0
}

# The same `audit`, with `DOGEN` REMOVED from the environment. `fixtures.sh` exports `DOGEN`
# at the top and it always wins, which is exactly why no fixture could reach
# `_dogen_executable`'s fallback chain — the one CR-01 was filed against.
audit_output_without_dogen_env() {
    local unit="$1"
    AUDIT_OUT=$(env -u DOGEN python3 "$SCORE" audit "$unit" --root "$TEST_DIR" 2>&1)
    AUDIT_RC=$?
    return 0
}

# A `dogen` shipped BY THE TREE UNDER AUDIT: it records that it ran and prints a report saying
# everything is fine. This is ordinary contributor input — a documentation repository may hold
# any file it likes — and the oracle must not execute it.
plant_hostile_dogen_in_the_audited_tree() {
    cat >"$TEST_DIR/dogen" <<'HOSTILE'
#!/usr/bin/env bash
printf 'ran with args: %s\n' "$*" >"$(dirname "$0")/hostile-dogen-ran"
printf '{"verdict": "ok", "checks": [{"id": "V1", "status": "ok", "detail": "forged-by-the-target"}]}\n'
exit 0
HOSTILE
    chmod +x "$TEST_DIR/dogen"
}

# Rewrite ONE ledger line in place through python3, so no digest is ever typed by hand
# (LEDG-06). `$1` is the unit, `$2` the 1-based line number, `$3` a python expression body
# operating on the name `event`; the line is re-serialised with the writer's own separators.
rewrite_ledger_event() {
    local unit="$1" number="$2" mutation="$3"
    python3 -c '
import json, sys
path, number, mutation = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(path, "rb") as handle:
    lines = handle.read().split(b"\n")
event = json.loads(lines[number - 1].decode("utf-8"))
exec(mutation, {"event": event})
lines[number - 1] = json.dumps(
    event, sort_keys=True, separators=(",", ":"), ensure_ascii=False
).encode("utf-8")
with open(path, "wb") as handle:
    handle.write(b"\n".join(lines))
' ".dogen/units/${unit}/ledger.jsonl" "$number" "$mutation"
}

# The ledger's line count, so no fixture hardcodes a seq or a line number the harness
# already knows. `wc -l` counts LFs, and the writer always ends with exactly one.
ledger_lines() {
    wc -l <".dogen/units/$1/ledger.jsonl" | tr -d ' '
}

# Keep only the first `$2` lines of the ledger, trailing LF included — the truncation the
# boundary fixture needs, applied through the same byte-level path the reader uses.
truncate_ledger_to() {
    local unit="$1" keep="$2" path
    path=".dogen/units/${unit}/ledger.jsonl"
    head -n "$keep" "$path" >"${path}.cut"
    mv "${path}.cut" "$path"
}

# Hand-append an ACCEPTING `review` event that disposes of nothing, following
# `tests/lib.sh::forge_escaping_target`'s pattern exactly: the event is built and chained
# through the writer's own primitives INSIDE THE FIXTURE, so the appended line's `prev` is
# computed from the previous line's bytes and no digest is typed by hand (LEDG-06). Loading
# `dogen` here is not a breach of D-02 — the independence rule binds the ORACLE, which must
# never import the tool; a fixture that forges contributor input is entitled to use the same
# writer a contributor's branch would have used.
#
# The tool refuses this accept outright (`unapplied_steering`), which is exactly why the
# state can only be reached by writing the line — and why the oracle has to be able to see
# it once someone has.
# `$2` is the `resolves[]` the forged accept carries, as a JSON list, defaulting to none. A
# caller that names a seq NOT YET ON RECORD is spelling the WR-09 tamper: contract §5.4
# subtracts only what a LATER accept disposed of, and a hand-written accept is the only way an
# earlier one can claim to have judged a request recorded after it.
forge_accepting_review() {
    python3 -c '
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("dogen", sys.argv[1])
spec = importlib.util.spec_from_loader("dogen", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
path = module.ledger_path(os.getcwd(), sys.argv[2])
records = module.read_events(path)
basis = [event for event, _ in records if event["kind"] == "generation"][-1]
actor = {"name": "Test Author", "email": "test@example.com"}
forged = module.build_event(
    "review", len(records), module.chain_prev(records[-1][1]), actor, None,
    {"verdict": "accept", "generation_seq": basis["seq"], "note": "ok",
     "basis_seq": basis["seq"], "files": basis["files"],
     "resolves": json.loads(sys.argv[3]), "withdraws": []})
module.append_batch(path, module.chain_lines([forged]))
' "$DOGEN" "$1" "${2:-[]}"
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: forged accepting review $1" >/dev/null 2>&1
}

# A SEALED unit: the drafted one, accepted. `setup_drafted_unit` stops at the generation, and
# three of the four oracle checks are about what a seal records — so the sealed state is the
# one a valid-unit fixture has to start from.
setup_sealed_unit() {
    setup_drafted_unit "$1" "$2"
    "$DOGEN" review "$1" --verdict accept --note ok >/dev/null 2>&1
}

# A sorted `<sha256>  <path>` listing of every file under `.dogen` and `docs`. Comparing
# two of these either side of an `audit` run is the RUNNABLE form of "`audit` is read-only",
# and it is what makes the concurrency claim checkable: two runs that write nothing cannot
# interfere with each other.
ledger_tree_digest() {
    find "$TEST_DIR/.dogen" "$TEST_DIR/docs" -type f -exec sha256sum {} + | sort
}

# --- V-01 ------------------------------------------------------------------------------

# V-01 gate-bypass: a generation on record whose signoff no longer covers the plan it gated.
# `signoff` freezes `sha256(unit.md)` as `plan_hash` and `draft` refuses while that hash is
# stale, so the state is reached by drafting FIRST and amending `unit.md` afterwards — one
# hand edit, no re-sign, and `unit.md` is a plain file an author may edit at any time.
#
# The tool's own refusal on the un-forged path is asserted first, so the fixture records both
# halves of the claim: `draft` will not step over the gate, and the oracle sees the unit that
# did. `verify` reports this at level `warn` (V19's `plan_stale` clause) and exits 0 — which
# is the severity split D-03's matrix is about, and why the oracle's own reading is needed.
test_v01_gate_bypass_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    hand_edit_source demo-unit "Demo" "Demo, amended after the draft"

    stage_draft demo-unit reference/demo.rst "Demo\n====\n\nA second body.\n"
    local refusal
    refusal=$("$DOGEN" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" --json 2>&1)
    assert_contains "v01: dogen itself refuses to draft over a stale plan hash" \
        "$refusal" '"error": "plan_stale"'

    audit_output demo-unit
    assert_eq "v01: audit exits 1 when the signed plan is no longer the plan on disk" \
        "1" "$AUDIT_RC"
    assert_contains "v01: the signoff-freshness check is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [oracle-2]"
    cleanup
}

# The independent audit must not read a ledger outside --root before dogen's own
# unit-id check runs. A valid id can also lead through a symlinked ledger path.
test_score_audit_rejects_traversing_unit_id_before_reading() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    mkdir -p "$TEST_DIR/docs/.dogen/units"

    local output rc
    output=$(python3 "$SCORE" audit '../../../.dogen/units/demo-unit' \
        --root "$TEST_DIR/docs" 2>&1)
    rc=$?
    assert_eq "audit: traversal is rejected" "1" "$rc"
    assert_contains "audit: invalid id is named" "$output" "FLAG [io] invalid unit id"
    assert_not_contains "audit: outside ledger was not read" \
        "$output" "chain recomputes clean"
    cleanup
}

test_score_audit_rejects_ledger_symlink_leaving_root() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    mkdir -p "$TEST_DIR/audit-root/.dogen/units"
    ln -s "$TEST_DIR/.dogen/units/demo-unit" \
        "$TEST_DIR/audit-root/.dogen/units/demo-unit"

    local output rc
    output=$(python3 "$SCORE" audit demo-unit --root "$TEST_DIR/audit-root" 2>&1)
    rc=$?
    assert_eq "audit: outside symlink is rejected" "1" "$rc"
    assert_contains "audit: escape is named" "$output" "leaves audit root"
    assert_not_contains "audit: linked ledger was not read" \
        "$output" "chain recomputes clean"
    cleanup
}

test_score_audit_unit_alphabet_matches_the_tool() {
    local tool_pattern audit_pattern
    tool_pattern=$(sed -n 's/^_UNIT_ID_RE = re.compile(r"\(.*\)")$/\1/p' "$DOGEN")
    audit_pattern=$(sed -n 's/^UNIT_ID_RE = re.compile(r"\(.*\)")$/\1/p' "$SCORE")
    assert_not_eq "audit: the tool declares an id alphabet" "" "$tool_pattern"
    assert_not_eq "audit: the scorer declares an id alphabet" "" "$audit_pattern"
    assert_eq "audit: the scorer mirrors the tool's id alphabet" \
        "$tool_pattern" "^${audit_pattern}\$"
}

# --- V-02 ------------------------------------------------------------------------------

# V-02 tamper-ledger: the canonical head-to-head. One character of one recorded digest is
# flipped inside the `generation` event's `files[]`, which leaves the FOLLOWING line's
# `prev` stale — so the oracle's own chain recompute and `verify`'s V3 are reading the same
# fact from two independent implementations.
#
# The `steer` call is part of reaching the valid state, not part of the corruption:
# `setup_drafted_unit` stops at seq 3 and the generation IS the final line there, so a
# tamper of it would leave no following `prev` to go stale and the corruption would be
# unreachable. One real verb later, the generation has a successor and the break is real.
test_v02_tamper_ledger_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    "$DOGEN" steer demo-unit --note "please add a table" >/dev/null 2>&1

    local before
    before=$(ledger_line demo-unit 4)
    assert_contains "v02: line 4 is the generation event the fixture tampers with" \
        "$before" '"kind":"generation"'

    rewrite_ledger_event demo-unit 4 '
digest = event["files"][0]["sha256"]
event["files"][0]["sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
'

    audit_output demo-unit
    assert_eq "v02: audit exits 1 on a tampered ledger" "1" "$AUDIT_RC"
    assert_contains "v02: the chain-recompute check is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [oracle-1]"
    cleanup
}

# --- V-03 ------------------------------------------------------------------------------

# V-03 unsteered: a second generation with nothing recorded between it and the first, and no
# override to justify it. The corruption is applied to the FINAL line, so the chain still
# recomputes and `oracle-1` stays out of it — this fixture is about the `[unsteered]` report
# line and nothing else.
#
# The route around the refusal is the tool's own escape hatch, used honestly and then broken:
# `draft --unsteered-reason` is the only way to record a second generation with no intervening
# H event, and removing the reason afterwards is the one named corruption. Asserting the bare
# refusal first records that the un-overridden state is not reachable by a verb at all.
test_v03_unsteered_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    stage_draft demo-unit reference/demo.rst "Demo\n====\n\nA second body.\n"

    local refusal
    refusal=$("$DOGEN" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" --json 2>&1)
    assert_contains "v03: dogen itself refuses a second generation with nothing recorded between" \
        "$refusal" '"error": "unsteered"'

    "$DOGEN" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --unsteered-reason "rerun after a tooling fix" >/dev/null 2>&1
    rewrite_ledger_event demo-unit "$(ledger_lines demo-unit)" \
        'event.pop("unsteered_reason", None)'

    audit_output demo-unit
    assert_eq "v03: audit exits 1 on an unsteered generation with no recorded reason" \
        "1" "$AUDIT_RC"
    assert_contains "v03: the [unsteered] report line is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [unsteered]"
    cleanup
}

# --- V-04 ------------------------------------------------------------------------------

# V-04 pending-unresolved: an accept that seals a page while a steering request is still
# undisposed. The tool refuses it outright, so the fixture asserts that refusal FIRST and only
# then hand-appends the forged accepting `review` — recording two facts rather than one: the
# state is unreachable through a verb, and the oracle catches it when it is reached by hand.
test_v04_pending_unresolved_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    "$DOGEN" steer demo-unit --note "please add a table" >/dev/null 2>&1

    local refusal
    refusal=$("$DOGEN" review demo-unit --verdict accept --note ok --json 2>&1)
    assert_contains "v04: dogen itself refuses an accept that disposes of nothing" \
        "$refusal" '"error": "unapplied_steering"'

    forge_accepting_review demo-unit

    audit_output demo-unit
    assert_eq "v04: audit exits 1 on a forged accept past a pending request" "1" "$AUDIT_RC"
    assert_contains "v04: the [requests] report line is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [requests]"
    cleanup
}

# WR-09: contract §5.4 subtracts "seqs in any LATER accept.resolves ∪ withdraws". The
# implementation collected dispositions from EVERY accept in any position, so an accept could
# name a seq that did not exist when it was written and silence a request recorded after it.
#
# The forgery is the only way to reach the state, and it is built in ledger order: an accept at
# seq 4 claiming to resolve seq 5, then the steering that BECOMES seq 5, then a second accept
# at the tip so the unit is sealed and `[requests]` — a gating line — has something to gate on.
# On a well-formed ledger the two readings agree, which is exactly why agreeing on honest input
# was never evidence the rule was implemented.
test_score_requests_an_earlier_accept_cannot_dispose_of_a_later_request() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    forge_accepting_review demo-unit '[5]'
    "$DOGEN" steer demo-unit --note "please add a table" >/dev/null 2>&1
    assert_contains "requests: the steering the forged accept pre-resolved is seq 5" \
        "$(ledger_line demo-unit 6)" '"seq":5'
    forge_accepting_review demo-unit

    audit_output demo-unit
    assert_eq "requests: a request pre-resolved by an earlier accept still exits 1" \
        "1" "$AUDIT_RC"
    assert_contains "requests: the gating line is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [requests]"
    assert_contains "requests: and names the seq that is still pending" \
        "$AUDIT_OUT" "request(s) [5] are still pending"
    assert_contains "requests: the out-of-order disposition is reported as a tamper signal" \
        "$AUDIT_OUT" "which is not a seq recorded BEFORE it"
    cleanup
}

# The other direction: an accept that disposes of a request recorded BEFORE it is the ordinary
# loop and must still clear the request. A fix that disregarded every disposition would pass
# the case above and fail every honest unit.
test_score_requests_a_later_accept_still_disposes_of_an_earlier_request() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    "$DOGEN" steer demo-unit --note "please add a table" >/dev/null 2>&1
    forge_accepting_review demo-unit '[4]'

    audit_output demo-unit
    assert_contains "requests: the disposed request is not pending" \
        "$AUDIT_OUT" "0 request(s) pending since the last generation"
    assert_contains "requests: and the line PASSes" "$AUDIT_OUT" "PASS [requests]"
    assert_not_contains "requests: nothing is reported out of order" \
        "$AUDIT_OUT" "which is not a seq recorded BEFORE it"
    cleanup
}

# --- the four oracle checks, and the cap ---------------------------------------------------

# The whole oracle over a unit with nothing wrong with it. Four checks, four PASSes, no fifth
# tag and exit 0 — the negative half of VAL-05's cap, which a fixture that only ever looks at
# corrupted trees cannot state.
test_score_oracle_all_four_checks_pass_on_a_sealed_unit() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst

    audit_output demo-unit
    assert_eq "oracle: a valid sealed unit exits 0" "0" "$AUDIT_RC"
    assert_contains "oracle: check 1 of 4 PASSes" "$AUDIT_OUT" "PASS [oracle-1]"
    assert_contains "oracle: check 2 of 4 PASSes" "$AUDIT_OUT" "PASS [oracle-2]"
    assert_contains "oracle: check 3 of 4 PASSes" "$AUDIT_OUT" "PASS [oracle-3]"
    assert_contains "oracle: check 4 of 4 PASSes" "$AUDIT_OUT" "PASS [oracle-4]"
    assert_not_contains "oracle: there is no fifth check — VAL-05 caps it at four" \
        "$AUDIT_OUT" "oracle-5"
    cleanup
}

# Oracle check 2 names BOTH sides of the comparison it made. A checker that reports "the plan
# hash is stale" without printing the two digests leaves its reader unable to tell a genuine
# amendment from a rewritten ledger line, which is the whole question the check exists to put
# in front of them. Neither digest is a literal here: both are read back out of the tree.
test_score_oracle_signoff_freshness_names_both_digests() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    local recorded computed
    recorded=$(ledger_line demo-unit 3 | json_field plan_hash)
    hand_edit_source demo-unit "Demo" "Demo, amended"
    computed=$(sha256_of_file .dogen/units/demo-unit/unit.md)

    audit_output demo-unit
    assert_contains "oracle-2: the FLAG names the plan_hash the signoff recorded" \
        "$AUDIT_OUT" "$recorded"
    assert_contains "oracle-2: the FLAG names the freshly computed sha256(unit.md)" \
        "$AUDIT_OUT" "$computed"
    cleanup
}

# Oracle check 3 reaches the FILESYSTEM, and the `docs/` join is its own job: the basis event
# records `reference/demo.rst` without the prefix (RESEARCH Pitfall 4). Removing exactly that
# one file is what proves the join happened — a check that stat'd the recorded path directly
# would find nothing either way and report the same FLAG for the wrong reason.
test_score_oracle_missing_page_flags_the_joined_path() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rm -f docs/reference/demo.rst

    audit_output demo-unit
    assert_eq "oracle-3: a page missing from disk exits 1" "1" "$AUDIT_RC"
    assert_contains "oracle-3: the seal-vs-disk check is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [oracle-3]"
    assert_contains "oracle-3: the FLAG names the path the oracle joined docs/ onto" \
        "$AUDIT_OUT" "docs/reference/demo.rst"
    cleanup
}

# The other half of check 3: the page is there and its bytes are not the ones sealed. Both
# digests are read back out of the tree rather than written down here.
test_score_oracle_drifted_page_flags_both_digests() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    local recorded computed
    recorded=$(ledger_line demo-unit 4 | event_files | awk '{print $2}')
    printf 'Demo\n====\n\nThe drafted body, edited on disk.\n' >docs/reference/demo.rst
    computed=$(sha256_of_file docs/reference/demo.rst)

    audit_output demo-unit
    assert_eq "oracle-3: a page whose bytes changed on disk exits 1" "1" "$AUDIT_RC"
    assert_contains "oracle-3: the FLAG names the digest the basis sealed" \
        "$AUDIT_OUT" "$recorded"
    assert_contains "oracle-3: the FLAG names the digest computed from disk" \
        "$AUDIT_OUT" "$computed"
    cleanup
}

# Oracle check 4's tamper signal. `dogen signoff` refuses a `docs/`-prefixed target outright
# (`bad_write_path`, with a hint telling the author to drop the prefix), so a ledger carrying
# one cannot have been produced by the tool. The corruption is applied to the FINAL line, so
# the chain still recomputes and check 4 is the finding rather than a side effect of check 1.
test_score_oracle_docs_prefixed_path_flags_the_double_segment() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rewrite_ledger_event demo-unit "$(ledger_lines demo-unit)" \
        'event["files"][0]["path"] = "docs/" + event["files"][0]["path"]'

    audit_output demo-unit
    assert_eq "oracle-4: a docs/-prefixed recorded path exits 1" "1" "$AUDIT_RC"
    assert_contains "oracle-4: the sealed-path-shape check is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [oracle-4]"
    assert_contains "oracle-4: the FLAG names the docs/docs/ segment the join would produce" \
        "$AUDIT_OUT" "docs/docs/"
    cleanup
}

# Check 4's other half: the sealed path is a path the signoff never named. Contract V13 makes
# a generation's `files[]` exactly the signed targets, so a recorded path outside them is a
# rewritten record, and the FLAG has to name both sides for a reader to act on it.
test_score_oracle_recorded_path_outside_the_targets_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rewrite_ledger_event demo-unit "$(ledger_lines demo-unit)" \
        'event["files"][0]["path"] = "reference/not-a-target.rst"'

    audit_output demo-unit
    assert_eq "oracle-4: a recorded path outside the signoff's targets exits 1" "1" "$AUDIT_RC"
    assert_contains "oracle-4: the FLAG names the path the record carries" \
        "$AUDIT_OUT" "reference/not-a-target.rst"
    assert_contains "oracle-4: the FLAG names the target the signoff froze" \
        "$AUDIT_OUT" "reference/demo.rst"
    cleanup
}

# --- `draft`: the include resolver, confined on both branches -------------------------------

# A minimal Sphinx-shaped tree: a `conf.py` marking the source root, a page under it, and a
# file OUTSIDE it holding a token the scorer would report if it ever read it. `$1` is the
# include target written into the page, verbatim.
setup_draft_tree_with_include() {
    local target="$1"
    mkdir -p "$TEST_DIR/site/docs/guides" "$TEST_DIR/site/docs/_shared" "$TEST_DIR/private"
    printf 'project = "fixture"\n' >"$TEST_DIR/site/docs/conf.py"
    printf 'A note that mentions the corpus.\n' >"$TEST_DIR/private/notes.txt"
    printf 'A shared fragment that mentions the corpus.\n' >"$TEST_DIR/site/docs/_shared/frag.txt"
    printf 'Page\n====\n\n.. include:: %s\n' "$target" \
        >"$TEST_DIR/site/docs/guides/page.rst"
}

# WR-06: `_resolve` applied `resolve()` + `relative_to(root)` to a leading-`/` target and
# returned `draft_path.parent / rel` UNCHECKED for a dir-relative one. A draft is
# model-produced content, so `.. include:: ../../../private/notes.txt` was read and folded into
# the text all four scans then run over — and the matched tokens are ECHOED, so content left
# the file. `draft` is report-only, so this is a scorecard rather than a gate, which is why the
# assertion is that the token did not travel.
test_score_draft_a_dir_relative_include_leaving_the_source_root_is_refused() {
    setup_repo
    setup_draft_tree_with_include "../../../private/notes.txt"

    local scored
    scored=$(python3 "$SCORE" draft "$TEST_DIR/site/docs/guides/page.rst" 2>&1)
    assert_contains "draft: the include is reported as unresolved" \
        "$scored" "unresolved include: ../../../private/notes.txt"
    assert_not_contains "draft: and the file outside the source root was never read" \
        "$scored" "researcher register: ['the corpus']"
    assert_contains "draft: the register scan ran over the page alone, and is clean" \
        "$scored" "researcher register: clean"
    cleanup
}

# The other direction, and the reason the boundary is the SOURCE ROOT rather than the draft's
# own directory: `.. include:: ../_shared/frag.txt` is an ordinary rST pattern in a real docs
# tree — the phase-19 target repository uses exactly this shape for its `_interfaces/`
# fragments — and confining a dir-relative target to the page's own directory would refuse it.
# A confinement that breaks the legitimate case is not a fix.
test_score_draft_a_dir_relative_include_inside_the_source_root_still_resolves() {
    setup_repo
    setup_draft_tree_with_include "../_shared/frag.txt"

    local scored
    scored=$(python3 "$SCORE" draft "$TEST_DIR/site/docs/guides/page.rst" 2>&1)
    assert_not_contains "draft: a sibling fragment under the source root is not refused" \
        "$scored" "unresolved include"
    assert_contains "draft: it was read, and its text was scanned with the page" \
        "$scored" "researcher register: ['the corpus']"
    cleanup
}

# --- independence (D-02): the tree under audit never chooses the tool ----------------------

# CR-01. `_dogen_executable` fell back to `<root>/dogen`, where `root` is the attacker-
# influenced `--root`, and `audit` then ran it with `cwd=str(root)`. The `[verify]` arm is the
# oracle's single point of contact with the tool and its whole value is that the reading is
# INDEPENDENT; a repository under audit that ships its own `dogen` got to write that reading,
# and got arbitrary code execution in the auditor's process besides.
#
# This is the argument the file already makes about `DOCS_ROOT` — the artefact under audit must
# not choose what it is compared against — applied to the PROGRAM rather than to the directory.
# The success criterion this phase states is that the oracle is independent, so the word has to
# survive a target that tries to supply the tool.
test_score_independence_the_audited_tree_never_supplies_the_verify_arms_tool() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    plant_hostile_dogen_in_the_audited_tree

    audit_output_without_dogen_env demo-unit
    assert_file_not_exists "independence: the dogen shipped by the audited tree was never run" \
        "$TEST_DIR/hostile-dogen-ran"
    assert_not_contains "independence: so its forged detail never reached the report" \
        "$AUDIT_OUT" "forged-by-the-target"
    assert_not_contains "independence: nor its one-check verdict" \
        "$AUDIT_OUT" "over 1 check(s)"
    assert_contains "independence: the kit's own tool gave the reading instead" \
        "$AUDIT_OUT" "PASS [verify]"
    assert_eq "independence: and a healthy sealed unit still exits 0 without DOGEN set" \
        "0" "$AUDIT_RC"
    cleanup
}

# --- the D-03 DISAGREE matrix, over CLAUSES and not over substrings ------------------------

# CR-02, the noisy direction. `V14`'s detail is `"<path>: <status>"` joined over every row, so
# a bare `"missing" in detail` test reads the PAGE PATHS as findings. A healthy sealed unit
# whose signed target is named `reference/missing-fields.rst` — an ordinary reference page —
# made `audit` print `PASS [oracle-3]` and a DISAGREE about it in the same run, and exit 1.
#
# The target name is the whole fixture: swap it for `reference/demo.rst` and nothing here is
# exercised, which is why it is spelled out rather than parameterised.
test_score_disagree_a_page_path_containing_missing_is_not_a_v14_finding() {
    setup_repo
    setup_sealed_unit demo-unit reference/missing-fields.rst

    audit_output demo-unit
    assert_eq "disagree: a healthy unit whose page is named 'missing-fields' exits 0" \
        "0" "$AUDIT_RC"
    assert_contains "disagree: the seal-vs-disk check PASSes, as it should" \
        "$AUDIT_OUT" "PASS [oracle-3]"
    assert_contains "disagree: and the verify arm agrees" "$AUDIT_OUT" "PASS [verify]"
    assert_not_contains "disagree: so no split is reported on a filename" \
        "$AUDIT_OUT" "DISAGREE"
    cleanup
}

# CR-02, the SUPPRESSED direction — the one a noisy false positive hides. The oracle FLAGs
# (contract V6: the accepting tip's `files[]` differs from the basis's) while `V14` reads the
# basis and correctly reports `current`. That is a real split. With the old substring test the
# path's own `missing` made the verify side read as a finding too, the two sides "agreed", and
# the DISAGREE line was never printed — a silent comparison of the wrong things on the one line
# whose docstring says neither reading is authoritative.
#
# The corruption is applied to the FINAL line, so the chain still recomputes and `oracle-1`
# stays out of it.
test_score_disagree_a_true_split_is_not_suppressed_by_a_page_path() {
    setup_repo
    setup_sealed_unit demo-unit reference/missing-fields.rst
    rewrite_ledger_event demo-unit "$(ledger_lines demo-unit)" '
digest = event["files"][0]["sha256"]
event["files"][0]["sha256"] = ("0" if digest[0] != "0" else "1") + digest[1:]
'

    audit_output demo-unit
    assert_eq "disagree: a tip whose files[] differs from the basis exits 1" "1" "$AUDIT_RC"
    assert_contains "disagree: the seal-vs-disk check is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [oracle-3]"
    assert_contains "disagree: and the split against V14 is reported, not swallowed" \
        "$AUDIT_OUT" "DISAGREE [oracle-3 vs V14]"
    assert_contains "disagree: naming which side read which way" \
        "$AUDIT_OUT" "oracle flag, verify ok"
    cleanup
}

# A unit that is a seq-0 `ledger` header and NOTHING else. It is reached by copying the header
# of a real unit and retargeting it, so the line is one the writer produced rather than one a
# fixture typed, and it carries no `unit.md` — which is what makes `verify` report `warn`
# rather than fail and leaves `audit` with nothing but its chain recompute to do.
setup_header_only_unit() {
    local source="$1" ghost="$2"
    mkdir -p ".dogen/units/${ghost}"
    head -n 1 ".dogen/units/${source}/ledger.jsonl" | python3 -c '
import json, sys
event = json.loads(sys.stdin.read())
event["unit"] = sys.argv[1]
sys.stdout.write(json.dumps(
    event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
' "$ghost" >".dogen/units/${ghost}/ledger.jsonl"
}

# WR-01: `checks_run` was incremented for every one of the eight report lines INCLUDING the
# ones that printed SKIP, so its minimum was 10 and `if checks_run == 0` could never fire.
# Exit 2 was reachable only from the `root.is_dir()` arm. The code did the one thing the
# comment twelve lines above it says it must not:
#
#   A check that could not be read … reports SKIP and is NOT counted in `checks_run`: counting
#   it would let a unit with nothing on record but a header report three checks it never
#   performed.
#
# A ledger holding only its seq-0 header exited 0 with three of the four oracle checks SKIPped.
# That is the shape a retargeted root or a reshaped tree produces, and reporting it as clean is
# the one outcome the 0/1/2 contract exists to make impossible.
test_score_a_header_only_ledger_reports_nothing_checked_rather_than_clean() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    setup_header_only_unit demo-unit ghost

    audit_output ghost
    assert_eq "vacuous: a ledger with nothing but its header exits 2, never 0" "2" "$AUDIT_RC"
    assert_contains "vacuous: the chain recompute did run, and says so" \
        "$AUDIT_OUT" "PASS [oracle-1]"
    assert_contains "vacuous: check 2 of 4 had no evidence" "$AUDIT_OUT" "SKIP [oracle-2]"
    assert_contains "vacuous: check 3 of 4 had no evidence" "$AUDIT_OUT" "SKIP [oracle-3]"
    assert_contains "vacuous: check 4 of 4 had no evidence" "$AUDIT_OUT" "SKIP [oracle-4]"
    assert_contains "vacuous: and [requests] no longer counts a zero over nothing" \
        "$AUDIT_OUT" "SKIP [requests]"
    assert_contains "vacuous: the count is named rather than returned silently" \
        "$AUDIT_OUT" "NOTHING with unit evidence was checked"
    cleanup
}

# The other side of the same threshold, and the one that keeps it honest: a unit with real
# evidence on record is scored, not refused. A SKIPping line must cost the run nothing.
test_score_a_sealed_unit_is_scored_and_never_reported_as_unchecked() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst

    audit_output demo-unit
    assert_eq "vacuous: a sealed unit with evidence on record still exits 0" "0" "$AUDIT_RC"
    assert_not_contains "vacuous: and is never reported as having checked nothing" \
        "$AUDIT_OUT" "NOTHING with unit evidence was checked"
    assert_contains "vacuous: even though five of its report lines SKIPped" \
        "$AUDIT_OUT" "SKIP [sphinx]"
    cleanup
}

# --- the eight report lines, and the three that gate ---------------------------------------

# All eight lines render over a unit with nothing wrong with it, and the run still exits 0.
# The `[sphinx]` assertion is deliberately a pair: SKIP present AND PASS absent. Absence of a
# RUN file is not a pass of the §10 Sphinx rule, and a reader who cannot tell those apart is
# being told a leg was scored when nothing looked at it.
test_score_report_all_eight_lines_render_on_a_sealed_unit() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst

    audit_output demo-unit
    assert_eq "report: a valid sealed unit with no RUN file exits 0" "0" "$AUDIT_RC"
    local tag
    for tag in unsteered edits requests model report context steps sphinx; do
        assert_contains "report: the [${tag}] line is rendered" "$AUDIT_OUT" "[${tag}]"
    done
    assert_contains "report: [sphinx] SKIPs with no RUN file under the root" \
        "$AUDIT_OUT" "SKIP [sphinx]"
    assert_not_contains "report: [sphinx] never claims a pass it did not make" \
        "$AUDIT_OUT" "PASS [sphinx]"
    assert_contains "report: [steps] renders 'no step plan' for a reference unit" \
        "$AUDIT_OUT" "no step plan"
    assert_contains "report: [context] reports the empty signoff map without FLAGging" \
        "$AUDIT_OUT" "no recorded source digests"
    assert_contains "report: [context] says which 'context' it means" \
        "$AUDIT_OUT" "not the RUN file"
    cleanup
}

# The D-04 property that the exit contract exists to state: an INFORMATIONAL line can report a
# finding without moving the exit code. The finding here is real and reachable — the drafting
# skill's own `--report` declared a gap — and the reviewer-edit beside it pins the other hazard
# the eight-row table names: a `reviewer-edit`'s `files[]` carries `path` and `sha256` and no
# `bytes`, so a reader that requires `bytes` breaks on every hand-edit adoption.
test_score_report_informational_findings_never_change_the_exit_code() {
    setup_repo
    dogen_unit_new demo-unit reference/demo.rst >/dev/null 2>&1
    "$DOGEN" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit reference/demo.rst "Demo\n====\n\nThe drafted body.\n"
    printf '%s' '{"origins":["notes/source-a.md"],"gaps":["the SDK list is incomplete"],
"gaps_note":"needs a second pass"}' >claims.json
    "$DOGEN" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --report claims.json >/dev/null 2>&1
    printf 'Demo\n====\n\nThe reviewer edited body.\n' >docs/reference/demo.rst
    "$DOGEN" edits demo-unit --note "fixed a typo" >/dev/null 2>&1

    audit_output demo-unit
    assert_contains "report: [report] reports the gap the drafting skill declared" \
        "$AUDIT_OUT" "FLAG [report]"
    assert_contains "report: [edits] reads a reviewer-edit that records no bytes key" \
        "$AUDIT_OUT" "PASS [edits]"
    assert_eq "report: an informational FLAG leaves the exit code at 0" "0" "$AUDIT_RC"
    cleanup
}

# The CONTEXT open item, pinned rather than asserted in prose. The module docstring is the ONE
# place the gating enumeration is written as a list; in the code each report line carries its
# own `gating` flag. This reads both and compares them, so the two cannot drift apart silently
# — which is the failure a comment saying "keep these in sync" does not prevent.
#
# It builds no repo: both readings are static reads of `score.py`, and `$SCORE` is absolute.
test_score_report_gating_enumeration_matches_the_docstring() {
    local from_docstring from_code
    from_docstring=$(python3 -c '
import ast, re, sys
text = ast.get_docstring(ast.parse(open(sys.argv[1], encoding="utf-8").read()))
paragraph = text.split("GATING report lines FLAGs")[1].split("\n\n")[0]
print(" ".join(sorted(set(re.findall(r"``\[([a-z]+)\]``", paragraph)))))
' "$SCORE")
    from_code=$(python3 -c '
import ast, sys
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
gating = []
for node in tree.body:
    if not isinstance(node, ast.FunctionDef) or not node.name.startswith("_line_"):
        continue
    for statement in node.body:
        if (isinstance(statement, ast.Assign)
                and getattr(statement.targets[0], "id", "") == "gating"
                and getattr(statement.value, "value", None) is True):
            gating.append(node.name[len("_line_"):])
print(" ".join(sorted(set(gating))))
' "$SCORE")
    assert_eq "report: the docstring enumerates exactly three gating lines" \
        "requests sphinx unsteered" "$from_docstring"
    assert_eq "report: the code's gating set is the docstring's, with no second list" \
        "$from_docstring" "$from_code"
    return 0
}

# --- the §5.2 restatement, pinned ---------------------------------------------------------
#
# D-02 puts contract §5.2's serialization rule in a SECOND home, deliberately: an oracle that
# shares the tool's chain primitives goes green on the very bug it exists to catch. A second
# home for a rule is drift unless something pins the two together, and these are that pin.
# They are not V-0N fixtures and carry no `vNN` token, so `check_traces.py` has no trace id to
# key on — but they do carry the `test_` prefix, because they are real tests and must run.

# The lower boundary: one event, seq 0, `prev` null. A chain of length one is still a chain,
# and a reader that only recomputes from index 1 onwards would report this as clean for the
# wrong reason — so the assertion is the named PASS, not the exit code, which other checks
# over a deliberately truncated ledger are entitled to move.
test_score_reader_single_event_ledger_recomputes_clean() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    truncate_ledger_to demo-unit 1

    audit_output demo-unit
    assert_contains "reader: a single-event ledger recomputes clean" \
        "$AUDIT_OUT" "PASS [oracle-1]"
    assert_not_contains "reader: nothing about the chain FLAGged at the lower boundary" \
        "$AUDIT_OUT" "FLAG [oracle-1]"
    cleanup
}

# WR-02: the truncation that lands exactly ON a line boundary. Contract §5.2 fixes the writer
# as `json.dumps(...) + "\n"`, so a final line with NO trailing LF is the signature of an
# interrupted `write()` — the case §5.8's manifest recovery boundary exists for. Every event
# still parses and every `prev` still checks out, so the reader used to report the file clean
# and `audit` printed `chain recomputes clean` over a ledger that is missing its tail.
#
# Only the last byte is removed, so the assertion is about the boundary and nothing else.
test_score_reader_a_final_line_with_no_trailing_lf_flags_as_a_truncated_write() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    local expected_line
    expected_line=$(ledger_lines demo-unit)
    python3 -c '
import sys
path = sys.argv[1]
with open(path, "rb") as handle:
    raw = handle.read()
assert raw.endswith(b"\n"), "the writer should have ended this ledger with one LF"
with open(path, "wb") as handle:
    handle.write(raw[:-1])
' .dogen/units/demo-unit/ledger.jsonl

    audit_output demo-unit
    assert_eq "reader: a ledger truncated at a line boundary exits 1, never 0" "1" "$AUDIT_RC"
    assert_contains "reader: the chain-recompute check is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [oracle-1]"
    assert_contains "reader: the problem names the line and says it is a truncated write" \
        "$AUDIT_OUT" "line ${expected_line}: the final line has no trailing LF"
    assert_not_contains "reader: and never reports the chain as clean" \
        "$AUDIT_OUT" "chain recomputes clean"
    cleanup
}

# One step past the boundary: a byte appended AFTER the final LF. The writer ends every
# ledger with exactly one LF, so those bytes are a line the reader must account for rather
# than an artefact it may discard.
test_score_reader_one_byte_after_the_final_lf_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    local expected_line
    expected_line=$(( $(ledger_lines demo-unit) + 1 ))
    printf 'x' >>".dogen/units/demo-unit/ledger.jsonl"

    audit_output demo-unit
    assert_eq "reader: one byte after the final LF exits 1" "1" "$AUDIT_RC"
    assert_contains "reader: the problem names the appended line by number" \
        "$AUDIT_OUT" "line ${expected_line}: not valid JSON"
    cleanup
}

# The rule that cannot be restated as "hash the event": the digest is over the previous
# line's BYTES. Re-serialising an event with a different key order changes nothing that
# survives `json.loads`, and everything about the bytes the next line's `prev` committed to.
test_score_reader_reserialised_key_order_still_flags() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    python3 -c '
import json, sys
path = sys.argv[1]
with open(path, "rb") as handle:
    lines = handle.read().split(b"\n")
event = json.loads(lines[1].decode("utf-8"))
reordered = dict(reversed(list(event.items())))
lines[1] = json.dumps(
    reordered, sort_keys=False, separators=(",", ":"), ensure_ascii=False
).encode("utf-8")
with open(path, "wb") as handle:
    handle.write(b"\n".join(lines))
' .dogen/units/demo-unit/ledger.jsonl

    audit_output demo-unit
    assert_eq "reader: a key-order-only rewrite exits 1" "1" "$AUDIT_RC"
    assert_contains "reader: the stale prev on the FOLLOWING line is the finding" \
        "$AUDIT_OUT" "line 3: prev is"
    cleanup
}

# `seq` contiguous from 0 is half of §5.2, and the problem string has to name BOTH sides —
# a checker that reports "bad seq" without saying what it found and what it expected is the
# failure mode this tree lints against by convention.
test_score_reader_renumbered_seq_names_both_sides() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rewrite_ledger_event demo-unit 2 'event["seq"] = 7'

    audit_output demo-unit
    assert_eq "reader: a renumbered seq exits 1" "1" "$AUDIT_RC"
    assert_contains "reader: the problem names the found and the expected seq" \
        "$AUDIT_OUT" "line 2: seq is 7, expected 1"
    cleanup
}

# --- the no-crash and read-only posture, pinned -------------------------------------------

# WR-03: a unit that is not there is a FLAG naming the path it looked for, never a
# FileNotFoundError traceback — the scorer is pointed at other people's repositories.
test_score_posture_missing_ledger_flags_without_a_traceback() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rm -f .dogen/units/demo-unit/ledger.jsonl

    audit_output demo-unit
    assert_eq "posture: a missing ledger exits 1" "1" "$AUDIT_RC"
    assert_contains "posture: the FLAG names the path it looked for" \
        "$AUDIT_OUT" "FLAG [io]"
    assert_not_contains "posture: no Python traceback reaches the caller" \
        "$AUDIT_OUT" "Traceback (most recent call last)"
    cleanup
}

# An empty ledger is not a clean ledger. It is the vacuous case the reader has to name,
# because "no lines, no problems" is exactly what a silently green oracle looks like.
test_score_posture_empty_ledger_flags_without_a_traceback() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    : >".dogen/units/demo-unit/ledger.jsonl"

    audit_output demo-unit
    assert_eq "posture: an empty ledger exits 1" "1" "$AUDIT_RC"
    assert_contains "posture: the problem names line 1 and what was expected there" \
        "$AUDIT_OUT" "line 1: the ledger is empty"
    assert_not_contains "posture: no Python traceback reaches the caller" \
        "$AUDIT_OUT" "Traceback (most recent call last)"
    cleanup
}

# WR-05: a `path` of `null` inside a generation's `files[]` is a finding, not a
# `root / None` TypeError. The corruption is applied to the FINAL line, so the chain still
# recomputes and the two readings are genuinely independent here: `oracle-1` PASSes and the
# tool refuses. `audit` must report what the tool actually said — an arm that reports only
# "no payload" hides the tool's own account of the damage from the person reading the audit.
test_score_posture_null_page_path_flags_cleanly() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rewrite_ledger_event demo-unit "$(ledger_lines demo-unit)" 'event["files"][0]["path"] = None'

    audit_output demo-unit
    assert_eq "posture: a null page path exits 1" "1" "$AUDIT_RC"
    assert_contains "posture: the [verify] arm is the one that FLAGged" \
        "$AUDIT_OUT" "FLAG [verify]"
    assert_contains "posture: the FLAG names the refusal the tool actually printed" \
        "$AUDIT_OUT" "ledger_corrupt"
    assert_not_contains "posture: no Python traceback reaches the caller" \
        "$AUDIT_OUT" "Traceback (most recent call last)"
    cleanup
}

# `audit` is read-only. Two runs that write nothing cannot interfere with each other, which
# is what makes the concurrency claim checkable without running two of them: the property
# under test is "no byte under `.dogen` or `docs` changed, and no lock appeared".
#
# The stale `.dogen/staging/lock` is removed BEFORE the baseline is taken, deliberately. The
# writing verbs in `setup_drafted_unit` leave it behind (contract §5.8's repo-wide flock is a
# real file and the tool does not unlink it), so a bare "the lock does not exist" assertion
# over the built state would fail on the previous commands' leftovers and say nothing at all
# about `audit`. Removed first, its absence afterwards is a statement about this run only.
test_score_posture_audit_writes_nothing() {
    setup_repo
    setup_drafted_unit demo-unit reference/demo.rst
    rm -f .dogen/staging/lock
    local before after
    before=$(ledger_tree_digest)

    audit_output demo-unit
    after=$(ledger_tree_digest)

    assert_eq "posture: audit changed no byte under .dogen or docs" "$before" "$after"
    assert_file_not_exists "posture: audit acquired no lock" "$TEST_DIR/.dogen/staging/lock"
    cleanup
}

# =========================================================================================
# Plan 19-03 — `validation/runmeta.sh` and the RUN file (VAL-06, D-05, D-06, D-08)
# =========================================================================================

# --- helpers (NEVER `test_`-prefixed — `main` would discover them as tests) ---------------

RUNMETA="$REPO_ROOT/validation/runmeta.sh"

# Run `runmeta.sh` and capture BOTH streams plus the exit code — the same merge
# `audit_output` makes, for the same reason: a fixture that asserts the exit code alone
# passes on the wrong refusal (T-19-07), and a refusal has to be readable to be asserted on.
runmeta_output() {
    RUNMETA_OUT=$(bash "$RUNMETA" "$@" 2>&1)
    RUNMETA_RC=$?
    return 0
}

# A stub `sphinx-build` written into the temp tree, with its exit code and its stderr text in
# SIBLING FILES so neither is quoted into a generated script. `SPHINX_BUILD` is the
# indirection `runmeta.sh` reads, and it is what lets CI — which has no Sphinx and no
# `docs/.venv` — run these fixtures at all.
stub_sphinx() {
    local exit_code="$1" diagnostics="$2"
    printf '%s' "$diagnostics" >"$TEST_DIR/stub-sphinx-diagnostics"
    printf '%s' "$exit_code" >"$TEST_DIR/stub-sphinx-exit"
    cat >"$TEST_DIR/stub-sphinx-build" <<'STUB'
#!/usr/bin/env bash
here="$(cd "$(dirname "$0")" && pwd)"
cat "$here/stub-sphinx-diagnostics" >&2
exit "$(cat "$here/stub-sphinx-exit")"
STUB
    chmod +x "$TEST_DIR/stub-sphinx-build"
    export SPHINX_BUILD="$TEST_DIR/stub-sphinx-build"
}

# Two of the 17 REAL baseline diagnostics quoted verbatim in 19-RESEARCH, with the absolute
# repo prefix left ON — that prefix is normalisation rule 1's whole subject, and a fixture
# that pre-stripped it would exercise the rule against a shape the build never emits.
sphinx_before_diagnostics() {
    printf "%s/docs/reference/definition-files/index.rst:28: WARNING: toctree contains reference to nonexisting document 'reference/definition-files/workshop-definition'\n" "$TEST_DIR"
    printf "%s/docs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'\n" "$TEST_DIR"
}

# A target repo as a leg meets it: a committed source under `notes/` for the origins digest to
# reach, a baseline tag for `begin` to resolve, and the stub build on `SPHINX_BUILD`.
setup_target_repo() {
    setup_repo
    mkdir -p notes
    printf 'A source.\n' >notes/source-a.md
    git add -A
    git commit -q -m "fixture: a source for the D-08 origins digest"
    git tag -a validation-base-v6 -m "fixture baseline"
    stub_sphinx 0 "$(sphinx_before_diagnostics)"
}

# One field out of the RUN file, through python3 and never `jq` — the `tests/lib.sh:281-287`
# idiom with an expression rather than a key, because the shapes asserted below are nested and
# a fixture that only reached top-level keys could not state them.
run_field() {
    local leg="$1" expression="$2"
    python3 -c '
import json, sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
value = eval(sys.argv[2], {"data": data})  # noqa: S307 — a fixture-side accessor
print("null" if value is None else value)
' "$TEST_DIR/validation/RUN-${leg}.json" "$expression" 2>/dev/null
}

# The six rev8 3.2 metric flags `end` requires, as an array. A fixture that needs ONE of them
# missing names it here rather than retyping the other five — which is what keeps "the six" a
# single list in the fixtures as well as in the script.
METRIC_FLAGS=()
set_metric_flags() {
    local skip="${1:-}" key
    METRIC_FLAGS=()
    for key in install time_to_usable_draft avoidable_questions \
               manual_dogen_commands help_requests resume_invocations; do
        if [ "$key" = "$skip" ]; then
            continue
        fi
        METRIC_FLAGS+=(--metric "${key}=measured")
    done
}

# A unit whose generation records an `origins[]` — the list D-08 digests. `setup_drafted_unit`
# drafts without a `--report`, so its generation carries no origins at all and the digest would
# be taken over an empty list, which is not the case worth pinning.
setup_unit_with_origins() {
    local unit="$1" target="$2"
    dogen_unit_new "$unit" "$target" >/dev/null 2>&1
    "$DOGEN" signoff "$unit" >/dev/null 2>&1
    stage_draft "$unit" "$target" "Demo\n====\n\nThe drafted body.\n"
    printf '%s' '{"origins":["notes/source-a.md"]}' >claims.json
    "$DOGEN" draft "$unit" "$(draft_path "$unit" "$target")" --report claims.json \
        >/dev/null 2>&1
}

# --- `begin`: the D-05 shape, written into the TARGET repo --------------------------------

# The shape, asserted key by key rather than by eye. `sphinx` must be a non-empty `str`
# because `dogen:7209-7243` accepts nothing else; `sphinx_before` must carry an integer `exit`
# and a string `diagnostics` because that is the pair `[sphinx]` diffs. The diagnostics
# assertion is on the build's OWN text, unfiltered — filtering it is what VAL-06 exists against.
test_runmeta_begin_writes_the_d05_shape() {
    setup_target_repo

    runmeta_output begin --leg reference --repo "$TEST_DIR"
    assert_eq "runmeta: begin exits 0 over a git work tree with a baseline tag" \
        "0" "$RUNMETA_RC"
    assert_file_exists "runmeta: begin writes <repo>/validation/RUN-<leg>.json" \
        "$TEST_DIR/validation/RUN-reference.json"
    assert_eq "runmeta: the sphinx key is a str, which is all dogen will render" \
        "str" "$(run_field reference 'type(data["sphinx"]).__name__')"
    assert_not_eq "runmeta: the sphinx key is not empty" \
        "" "$(run_field reference 'data["sphinx"]')"
    assert_eq "runmeta: sphinx_before.exit is an integer" \
        "int" "$(run_field reference 'type(data["sphinx_before"]["exit"]).__name__')"
    assert_eq "runmeta: sphinx_before.diagnostics is a string" \
        "str" "$(run_field reference 'type(data["sphinx_before"]["diagnostics"]).__name__')"
    assert_contains "runmeta: the diagnostics are the build's own text, never filtered" \
        "$(run_field reference 'data["sphinx_before"]["diagnostics"]')" \
        "undefined label: 'ref_workshop_definition'"
    assert_eq "runmeta: baseline.commit is the sha the baseline tag resolves to" \
        "$(git rev-parse 'refs/tags/validation-base-v6^{commit}')" \
        "$(run_field reference 'data["baseline"]["commit"]')"
    assert_eq "runmeta: tool.contract is read from dogen version --json" \
        "1" "$(run_field reference 'data["tool"]["contract"]')"
    assert_eq "runmeta: tool.min_tool is the tool's own version, as check_docs pins it" \
        "$("$DOGEN" version --json | json_field tool)" \
        "$(run_field reference 'data["tool"]["min_tool"]')"
    cleanup
}

# The skills digest (a CONTEXT discretion this plan settles): sha256 over the sorted
# `(path, sha256)` list under `.agents/skills/`, with the ROOT recorded beside it so a later
# reader knows what was covered. An absent root is `null` and NOT a digest of nothing —
# `protocol` refuses that RUN as incomplete, because the leg's premise is installed skills.
test_runmeta_begin_records_the_skills_root_beside_its_digest() {
    setup_target_repo

    runmeta_output begin --leg reference --repo "$TEST_DIR"
    assert_eq "runmeta: skills.root is recorded even when the directory is absent" \
        ".agents/skills" "$(run_field reference 'data["skills"]["root"]')"
    assert_eq "runmeta: an absent skills root digests to null, never to a digest of nothing" \
        "null" "$(run_field reference 'data["skills"]["sha256"]')"

    mkdir -p .agents/skills/dogen-write
    printf 'name: dogen-write\n' >.agents/skills/dogen-write/SKILL.md
    runmeta_output begin --leg reference --repo "$TEST_DIR"
    assert_eq "runmeta: an installed skills root digests to 64 hex characters" \
        "64" "$(run_field reference 'len(data["skills"]["sha256"])')"
    cleanup
}

# One RUN file per working tree is `dogen:7209-7243`'s constraint, not a convention: the tool
# scans `RUN-*.json` in sorted NAME order and returns the first usable one. Re-running `begin`
# for the same leg therefore overwrites, and never accumulates a second file.
test_runmeta_begin_twice_overwrites_rather_than_accumulating() {
    setup_target_repo

    runmeta_output begin --leg reference --repo "$TEST_DIR"
    runmeta_output begin --leg reference --repo "$TEST_DIR"
    assert_eq "runmeta: the second begin for the same leg still exits 0" "0" "$RUNMETA_RC"
    assert_eq "runmeta: there is exactly one RUN file in the target's validation/" \
        "1" "$(find "$TEST_DIR/validation" -maxdepth 1 -name 'RUN-*.json' | wc -l | tr -d ' ')"
    cleanup
}

# The other half of the same constraint: a RUN file for a DIFFERENT leg is refused rather than
# silently joined, because `dogen` would pick one of the two by name order and say nothing.
# The refusal names the file it found — a checker that refuses without naming what it compared
# is the failure mode this tree lints against by convention.
test_runmeta_begin_refuses_a_run_file_for_a_different_leg() {
    setup_target_repo

    runmeta_output begin --leg reference --repo "$TEST_DIR"
    runmeta_output begin --leg actionable --repo "$TEST_DIR"
    assert_not_eq "runmeta: a second leg's begin does not exit 0" "0" "$RUNMETA_RC"
    assert_contains "runmeta: the refusal names the RUN file already present" \
        "$RUNMETA_OUT" "RUN-reference.json"
    assert_file_not_exists "runmeta: and no second RUN file was written" \
        "$TEST_DIR/validation/RUN-actionable.json"
    cleanup
}

# --- `end`: the six metrics, the two-step transcript and the D-08 digests ------------------

# The six rev8 3.2 metrics have ONE authoring site and the author supplies all six at `end` —
# three of them are judgements about the session, not counters a script can read. A missing
# key is refused by NAME, so the author is told which measurement is absent.
test_runmeta_end_refuses_a_missing_metric_naming_it() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR"

    set_metric_flags help_requests
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    assert_not_eq "runmeta: end with five of the six metrics does not exit 0" \
        "0" "$RUNMETA_RC"
    assert_contains "runmeta: the refusal names the metric that is missing" \
        "$RUNMETA_OUT" "help_requests"
    cleanup
}

# RESEARCH Pitfall 6, pinned: `end` writes the transcript's resolved PATH and a null sha, and
# the author fills the sha from outside the session. A sha taken by a tool call inside the
# session is stale the moment that tool call is itself appended to the transcript, so a
# computed value here would be a fabricated measurement.
test_runmeta_end_writes_the_two_step_transcript_record() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR"

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    assert_eq "runmeta: end exits 0 with all six metrics supplied" "0" "$RUNMETA_RC"
    assert_eq "runmeta: transcript.sha256 is JSON null, never a self-computed digest" \
        "NoneType" "$(run_field reference 'type(data["transcript"]["sha256"]).__name__')"
    assert_eq "runmeta: transcript.path is a string or null, and nothing else" \
        "True" \
        "$(run_field reference 'type(data["transcript"]["path"]).__name__ in ("str", "NoneType")')"
    assert_eq "runmeta: all six 3.2 metrics are recorded at their one authoring site" \
        "6" "$(run_field reference 'len(data["metrics"])')"
    cleanup
}

# D-08: `baseline` is the digest of the generation's `origins[]` at the baseline tag and
# `context` is the same list recomputed from the working tree. Nothing touched the source
# between the tag and the draft, so the two are EQUAL here — which is the state `protocol`'s
# fourth check asserts. A HEAD comparison could never state this: every verb commits, so the
# target's HEAD at `end` necessarily differs from its HEAD at `begin`.
test_runmeta_end_digests_the_origins_at_the_tag_and_in_the_working_tree() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR"

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    assert_eq "runmeta: baseline.origins_sha256 is 64 hex characters" \
        "64" "$(run_field reference 'len(data["baseline"]["origins_sha256"])')"
    assert_eq "runmeta: context.origins_sha256 is 64 hex characters" \
        "64" "$(run_field reference 'len(data["context"]["origins_sha256"])')"
    assert_eq "runmeta: an untouched source digests identically at the tag and on disk" \
        "$(run_field reference 'data["baseline"]["origins_sha256"]')" \
        "$(run_field reference 'data["context"]["origins_sha256"]')"
    assert_contains "runmeta: the origins list itself is recorded beside the digest" \
        "$(run_field reference 'data["baseline"]["origins"]')" "notes/source-a.md"
    cleanup
}

# The `sphinx` string after `end` names BOTH halves of the build pair and survives dogen's
# 120-character collapse still saying so. It is a human one-liner for `dogen summary` and
# deliberately does not restate the normalised diff: `score.py`'s `[sphinx]` line is the one
# place the new/resolved bookkeeping is computed, and a second computation here would be drift.
test_runmeta_end_names_both_halves_of_the_build_pair() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR"

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    local summary
    summary=$(run_field reference 'data["sphinx"]')
    assert_contains "runmeta: the summary names the before half" "$summary" "before exit 0"
    assert_contains "runmeta: the summary names the after half" "$summary" "after exit 0"
    assert_eq "runmeta: the summary still says both after a 120-character collapse" \
        "True" "$(run_field reference 'len(data["sphinx"]) <= 120')"
    assert_eq "runmeta: sphinx_after.exit is an integer" \
        "int" "$(run_field reference 'type(data["sphinx_after"]["exit"]).__name__')"
    cleanup
}

# `.planning/WINDOWS.md` entry 10, closed end to end: `dogen`'s `sphinx_result` branch has
# never been exercised against a real RUN file. It renders the STRING key and never sees the
# structured siblings — which is why the shape costs `dogen` zero lines (D-05).
test_runmeta_summary_round_trip_renders_only_the_string_key() {
    setup_target_repo
    setup_sealed_unit demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR"

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    local rendered
    rendered=$("$DOGEN" summary demo-unit 2>&1)
    assert_contains "round trip: dogen summary renders the sphinx line" "$rendered" "sphinx:"
    assert_contains "round trip: and names the RUN file it read it from" "$rendered" "RUN-"
    assert_contains "round trip: the rendered text is the RUN file's own sphinx string" \
        "$rendered" "$(run_field reference 'data["sphinx"]')"
    assert_not_contains "round trip: the structured before sibling is invisible to dogen" \
        "$rendered" "sphinx_before"
    assert_not_contains "round trip: so is the after sibling" "$rendered" "sphinx_after"
    cleanup
}

# A `dogen` stand-in whose `version --json` prints something that is NOT JSON. It is the
# shortest reachable route into `do_begin`'s writer raising: the writer is the only place the
# string is parsed, and `begin` checks that it is non-empty and nothing else.
stub_dogen_with_unparseable_version() {
    cat >"$TEST_DIR/stub-dogen" <<'STUB'
#!/usr/bin/env bash
printf 'not json at all\n'
exit 0
STUB
    chmod +x "$TEST_DIR/stub-dogen"
    export DOGEN="$TEST_DIR/stub-dogen"
}

# CR-05: the script runs under `set -u` alone and neither JSON writer was followed by
# `|| refuse`, so both subcommands printed their success line and exited 0 whatever the
# writer did. The header's own exit contract says `0  the RUN file was written`.
#
# `begin`'s half: a `version --json` that is non-empty but not JSON makes `json.loads` raise,
# no RUN file is written, and `runmeta: wrote <path>` used to print anyway.
test_runmeta_begin_refuses_when_its_writer_could_not_run() {
    setup_target_repo
    stub_dogen_with_unparseable_version

    runmeta_output begin --leg reference --repo "$TEST_DIR"
    assert_not_eq "runmeta: a begin whose writer died does not exit 0" "0" "$RUNMETA_RC"
    assert_contains "runmeta: the refusal says the RUN file was not written" \
        "$RUNMETA_OUT" "the RUN file was NOT written"
    assert_not_contains "runmeta: and it never claims it wrote one" "$RUNMETA_OUT" "runmeta: wrote"
    assert_file_not_exists "runmeta: no RUN file is on disk" \
        "$TEST_DIR/validation/RUN-reference.json"
    cleanup
}

# `end`'s half, and the one the review reproduced: with a key dropped from the RUN file
# between `begin` and `end` — an editor, a partial merge, a hand fix — the writer raised, the
# metrics, `sphinx_after`, the transcript record and both D-08 digests were silently lost, and
# the operator was told the leg completed. The measurement is a once-per-session artefact, so
# a silent loss is not recoverable by re-running.
test_runmeta_end_refuses_rather_than_reporting_a_completion_it_did_not_make() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR"
    patch_run_file 'data.pop("baseline", None)'

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    assert_not_eq "runmeta: an end whose writer could not read the RUN file does not exit 0" \
        "0" "$RUNMETA_RC"
    assert_not_contains "runmeta: and it never prints the completion line" \
        "$RUNMETA_OUT" "runmeta: completed"
    assert_contains "runmeta: the refusal names the RUN file it could not complete" \
        "$RUNMETA_OUT" "RUN-reference.json"
    assert_eq "runmeta: the after build was not recorded over a failed completion" \
        "null" "$(run_field reference 'data.get("sphinx_after")')"
    assert_eq "runmeta: and neither were the six metrics" \
        "null" "$(run_field reference 'data.get("metrics")')"
    cleanup
}

# WR-08: the `case "$harness"` had exactly one named arm and a catch-all `*)` that searched
# Claude Code's tree. A RUN file recording `copilot-cli`, `cursor`, a typo or the empty string
# was searched in the wrong tree, found nothing, and recorded
# `{"path": null, "searched": "~/.claude/projects/<slug>"}` — "searched, found nothing", which
# is the exact vacuous reading commit c572e64 was written to eliminate for the opposite
# harness. The RUN file now records WHY nothing was found.
test_runmeta_an_unsupported_harness_records_why_and_not_a_tree_nobody_searched() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR" --harness copilot-cli

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    assert_eq "runmeta: an unsupported harness does not stop the leg being recorded" \
        "0" "$RUNMETA_RC"
    assert_eq "runmeta: and its transcript path is null, as it was before" \
        "null" "$(run_field reference 'data["transcript"]["path"]')"
    assert_contains "runmeta: but the searched field now says why, not where it did not look" \
        "$(run_field reference 'data["transcript"]["searched"]')" \
        "no transcript resolver for harness: copilot-cli"
    assert_not_contains "runmeta: and never names another harness's tree" \
        "$(run_field reference 'data["transcript"]["searched"]')" ".claude/projects"
    cleanup
}

# The named arm still resolves the way it always did — the fix must not be "refuse everything".
# The directory is recorded whether or not it exists, which is the c572e64 courtesy itself.
test_runmeta_the_claude_code_arm_still_names_the_tree_it_searched() {
    setup_target_repo
    setup_unit_with_origins demo-unit reference/demo.rst
    runmeta_output begin --leg reference --repo "$TEST_DIR" --harness claude-code

    set_metric_flags
    stub_sphinx 0 ""
    runmeta_output end --leg reference --repo "$TEST_DIR" --unit demo-unit "${METRIC_FLAGS[@]}"
    assert_eq "runmeta: the default harness still exits 0" "0" "$RUNMETA_RC"
    assert_contains "runmeta: and records the Claude Code tree it searched" \
        "$(run_field reference 'data["transcript"]["searched"]')" ".claude/projects"
    cleanup
}

# --- the script's own posture -------------------------------------------------------------

# WR-10: `LEG_RE='^[A-Za-z0-9][A-Za-z0-9._-]*$'` was declared and never used. The enforcement
# was a `case` that does not anchor the FIRST character, so `--leg ..`, `--leg -x` and
# `--leg .hidden` all passed a refusal message naming a regex the check did not implement. No
# traversal followed — `/` is excluded and the value is only ever a filename component — but
# this guard is cited on `score.py`'s side as the reason a leg name is trustworthy, and CR-04
# is what happens when it is not.
#
# Every rejected shape is a value the OLD check let through, so the case is about the anchor
# and nothing else.
test_runmeta_enforces_the_leg_alphabet_it_declares() {
    setup_target_repo
    local leg
    for leg in ".." "-x" ".hidden" "_leading"; do
        runmeta_output begin --leg "$leg" --repo "$TEST_DIR"
        assert_not_eq "runmeta: --leg $leg does not exit 0" "0" "$RUNMETA_RC"
        assert_contains "runmeta: --leg $leg is refused against the declared regex" \
            "$RUNMETA_OUT" "does not match"
    done
    assert_eq "runmeta: and nothing was written for any of them" \
        "0" "$(find "$TEST_DIR/validation" -maxdepth 1 -name 'RUN-*.json' 2>/dev/null | wc -l | tr -d ' ')"
    cleanup
}

# The alphabet's legitimate shapes still pass — the two real legs are named like this, and a
# guard that refused them would be a different defect.
test_runmeta_accepts_the_leg_names_the_real_legs_use() {
    setup_target_repo
    local leg
    for leg in "reference" "validate-workshop-definition" "leg.2"; do
        rm -f "$TEST_DIR/validation"/RUN-*.json
        runmeta_output begin --leg "$leg" --repo "$TEST_DIR"
        assert_eq "runmeta: --leg $leg is a legitimate leg name" "0" "$RUNMETA_RC"
        assert_file_exists "runmeta: and its RUN file was written" \
            "$TEST_DIR/validation/RUN-${leg}.json"
    done
    cleanup
}

# The leg alphabet now has TWO homes — `runmeta.sh` validates it before the name becomes a
# filename it writes, `score.py` before the name becomes a path it reads (CR-04) — and a second
# home for a rule is drift unless something pins the two together. This reads both and compares
# them, which is what a comment saying "keep these in sync" does not do.
#
# It builds no repo: both readings are static reads of files this suite already knows the paths
# of.
test_runmeta_and_score_agree_on_the_leg_alphabet() {
    local from_bash from_python
    from_bash=$(grep -E "^LEG_RE=" "$RUNMETA" | sed "s/^LEG_RE='//; s/'$//")
    from_python=$(python3 -c '
import ast, sys
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
for node in tree.body:
    if (isinstance(node, ast.Assign)
            and getattr(node.targets[0], "id", "") == "LEG_RE"):
        print(node.value.args[0].value)
        break
' "$SCORE")
    assert_not_eq "leg alphabet: runmeta.sh declares one" "" "$from_bash"
    assert_eq "leg alphabet: and score.py restates exactly it, with no second rule" \
        "$from_bash" "$from_python"
    return 0
}

# A bare invocation is not a run. It names its two subcommands rather than defaulting to one,
# because a script that silently picks `begin` would overwrite a RUN file someone meant to end.
test_runmeta_bare_invocation_names_its_two_subcommands() {
    runmeta_output
    assert_not_eq "runmeta: a bare invocation does not exit 0" "0" "$RUNMETA_RC"
    assert_contains "runmeta: the usage names the begin subcommand" "$RUNMETA_OUT" "begin"
    assert_contains "runmeta: the usage names the end subcommand" "$RUNMETA_OUT" "end"
    return 0
}

# RESEARCH Assumption A1: every JSON read and write goes through `python3`, never `jq`. `jq`
# is not a documented prerequisite of this repository and is not guaranteed on the runner, so
# a single `jq` call would make the RUN file unwritable exactly where it matters most.
test_runmeta_reaches_json_through_python3_and_never_jq() {
    local uses
    uses=$(grep -v '^ *#' "$RUNMETA" | grep -c 'jq' || true)
    assert_eq "runmeta: no jq outside the comments" "0" "$uses"
    assert_file_contains "runmeta: JSON is read and written through python3" \
        "$RUNMETA" "python3 -c"
    return 0
}

# =========================================================================================
# `[sphinx]` — normalise, multiset-diff, and gate on unaccounted items (VAL-06, D-07)
# =========================================================================================

# --- helpers (NEVER `test_`-prefixed — `main` would discover them as tests) ---------------

# Two of the 17 REAL baseline diagnostics, quoted verbatim from 19-RESEARCH's measured output.
# `$1` is the path prefix, separator included, so one call spells the absolute form the build
# emits and another spells the bare relative form — which is the only difference normalisation
# rule 1 is allowed to erase.
diag_toctree() {
    printf "%sdocs/reference/definition-files/index.rst:28: WARNING: toctree contains reference to nonexisting document 'reference/definition-files/workshop-definition'" "$1"
}

diag_label() {
    printf "%sdocs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'" "$1"
}

# A D-05-shaped RUN file with the given before/after build EXIT CODES and diagnostics blocks
# and, optionally, `item=account` attribution entries. The blocks are fixture STRINGS on
# purpose: these fixtures pin `[sphinx]`'s READING of a RUN file rather than `runmeta.sh`'s
# writing of one, and a hand-built pair is what lets one build differ from the other by
# exactly one line.
#
# The two exit codes are parameters rather than the hard-coded zeros this helper carried
# until CR-03. Hard-coding them is exactly why no fixture could see a GATING `[sphinx]` line
# PASSing over two builds that never ran: every RUN file the suite could write said both
# builds had completed.
write_run_file_with_exits() {
    local before_exit="$1" after_exit="$2" before="$3" after="$4"
    shift 4
    mkdir -p "$TEST_DIR/validation"
    python3 -c '
import json, sys
path, before_exit, after_exit, before, after = sys.argv[1:6]
attribution = []
for entry in sys.argv[6:]:
    item, _, account = entry.partition("=")
    attribution.append({"item": item, "account": account})
data = {
    "leg": "reference",
    "sphinx": "before exit %s - after exit %s" % (before_exit, after_exit),
    "sphinx_before": {"exit": int(before_exit), "diagnostics": before},
    "sphinx_after": {"exit": int(after_exit), "diagnostics": after},
    "sphinx_attribution": attribution,
}
with open(path, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
' "$TEST_DIR/validation/RUN-reference.json" "$before_exit" "$after_exit" "$before" "$after" "$@"
}

# The ordinary case — two builds that COMPLETED — so every diff fixture below states one
# thing and the exit codes are somebody else's subject.
write_run_file() {
    local before="$1" after="$2"
    shift 2
    write_run_file_with_exits 0 0 "$before" "$after" "$@"
}

# Just the `[sphinx]` lines of the last `audit` run — the INFO item lines included, because
# the determinism claim is about the whole block and not only about its verdict line.
sphinx_block() {
    printf '%s\n' "$AUDIT_OUT" | grep '\[sphinx\]' || true
}

# --- the diff, over normalised lines ------------------------------------------------------

# The zero case, stated as a PASS with its counts rather than as silence. A build pair with
# nothing between them is the ordinary shape of a leg that changed no page, and the reader
# still has to see the bookkeeping that produced the verdict.
test_sphinx_identical_before_and_after_reports_zero_new_zero_resolved() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    local block
    block="$(diag_toctree "$TEST_DIR/")"$'\n'"$(diag_label "$TEST_DIR/")"
    write_run_file "$block" "$block"

    audit_output demo-unit
    assert_eq "sphinx: an unchanged build pair leaves the audit at 0" "0" "$AUDIT_RC"
    assert_contains "sphinx: the line PASSes" "$AUDIT_OUT" "PASS [sphinx]"
    assert_contains "sphinx: and reports both counts" "$AUDIT_OUT" "0 new, 0 resolved"
    cleanup
}

# The success shape the reference leg pre-registered: every before item gone, none arrived.
# The resolved count is the evidence the leg's own page did the resolving.
test_sphinx_a_resolved_subset_reports_the_resolved_count() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    local before
    before="$(diag_toctree "$TEST_DIR/")"$'\n'"$(diag_label "$TEST_DIR/")"
    write_run_file "$before" ""

    audit_output demo-unit
    assert_eq "sphinx: a strictly smaller after-build leaves the audit at 0" "0" "$AUDIT_RC"
    assert_contains "sphinx: nothing new and both items resolved" \
        "$AUDIT_OUT" "0 new, 2 resolved"
    assert_contains "sphinx: the resolved set is emitted, not only counted" \
        "$AUDIT_OUT" "docs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'"
    cleanup
}

# D-07's machine half: a new diagnostic nobody accounted for FLAGs, and `[sphinx]` is one of
# the three GATING lines, so the audit exits non-zero. The FLAG names the exact NORMALISED
# line, because that is the string the author has to copy into the attribution list.
test_sphinx_an_unaccounted_new_item_flags_and_gates() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file "" "$(diag_label "$TEST_DIR/")"

    audit_output demo-unit
    assert_eq "sphinx: one unaccounted new item exits 1" "1" "$AUDIT_RC"
    assert_contains "sphinx: the gating line is the one that FLAGged" "$AUDIT_OUT" "FLAG [sphinx]"
    assert_contains "sphinx: the FLAG names the exact normalised line" \
        "$AUDIT_OUT" "docs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'"
    assert_contains "sphinx: and reports the count beside it" "$AUDIT_OUT" "1 new, 0 resolved"
    cleanup
}

# The human half: the judgement stays with the author, the bookkeeping does not. The same
# item with a matching attribution entry passes, and the account is printed beside the item so
# a reader of the audit sees WHY the new diagnostic was accepted.
test_sphinx_an_accounted_new_item_passes_and_prints_the_account() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    local item="docs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'"
    write_run_file "" "$(diag_label "$TEST_DIR/")" \
        "${item}=unit 1 has not written the label yet; resolved by the second target"

    audit_output demo-unit
    assert_eq "sphinx: an accounted new item leaves the audit at 0" "0" "$AUDIT_RC"
    assert_contains "sphinx: the line PASSes" "$AUDIT_OUT" "PASS [sphinx]"
    assert_contains "sphinx: the account is printed beside the item" \
        "$AUDIT_OUT" "unit 1 has not written the label yet"
    cleanup
}

# WR-07: MEMBERSHIP was the whole test, so `--attribute "<item>="` silenced a new Sphinx
# warning with no account at all while the INFO line printed `accounted: ` followed by nothing.
# The bookkeeping half of D-07 IS this list, and an empty entry is a bookkeeping no-op that
# reads as done — the author is not being asked for a judgement, only for one that was recorded.
test_sphinx_an_empty_account_does_not_account_for_anything() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    local item="docs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'"
    write_run_file "" "$(diag_label "$TEST_DIR/")" "${item}="

    audit_output demo-unit
    assert_eq "sphinx: an empty account leaves the item unaccounted, so the audit exits 1" \
        "1" "$AUDIT_RC"
    assert_contains "sphinx: the gating line FLAGs" "$AUDIT_OUT" "FLAG [sphinx]"
    assert_contains "sphinx: and says what kind of nothing it found" \
        "$AUDIT_OUT" "an EMPTY account, which is not an account"
    assert_not_contains "sphinx: the INFO line never prints 'accounted:' with nothing after it" \
        "$AUDIT_OUT" "— accounted: "
    cleanup
}

# Whitespace is not an account either. A checker that accepted `" "` would be asking the author
# to press the space bar rather than to record a judgement.
test_sphinx_a_whitespace_account_does_not_account_for_anything() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    local item="docs/index.rst:74: WARNING: undefined label: 'ref_workshop_definition'"
    write_run_file "" "$(diag_label "$TEST_DIR/")" "${item}=   "

    audit_output demo-unit
    assert_eq "sphinx: a whitespace-only account exits 1 too" "1" "$AUDIT_RC"
    assert_contains "sphinx: the gating line FLAGs" "$AUDIT_OUT" "FLAG [sphinx]"
    cleanup
}

# --- the four normalisation rules ---------------------------------------------------------

# Rule 1: the absolute repo prefix differs between the primary checkout and any worktree and
# says nothing about the diagnostic, so two lines differing only in it are ONE item.
test_sphinx_the_absolute_repo_prefix_is_not_a_difference() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file "$(diag_label "$TEST_DIR/")" "$(diag_label "")"

    audit_output demo-unit
    assert_eq "sphinx: the prefix alone is not a change, so the audit stays at 0" \
        "0" "$AUDIT_RC"
    assert_contains "sphinx: nothing new and nothing resolved" "$AUDIT_OUT" "0 new, 0 resolved"
    cleanup
}

# Rule 3: line numbers are NOT normalised. A diagnostic that moved lines is a different item
# and the author should account for it — a checker that erased the number would silently
# accept a warning that migrated to a page nobody looked at.
test_sphinx_a_moved_line_number_is_a_different_item() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file \
        "$(diag_label "$TEST_DIR/")" \
        "${TEST_DIR}/docs/index.rst:75: WARNING: undefined label: 'ref_workshop_definition'"

    audit_output demo-unit
    assert_eq "sphinx: a moved line number is a new item, so the audit exits 1" \
        "1" "$AUDIT_RC"
    assert_contains "sphinx: one item arrived and one left" "$AUDIT_OUT" "1 new, 1 resolved"
    cleanup
}

# Rule 4: one DIAGNOSTIC is one item, not one line. Sphinx prints the offending source line and
# its underline beneath a warning, so a line-per-item normaliser turned a single `Title underline
# too short.` into three new items — the warning, a section title and a run of dashes — and asked
# the author to account for the dashes as though they were a finding. Found walking the phase-19
# reference leg, where 3 real new warnings were reported as 9.
test_sphinx_a_multi_line_diagnostic_is_one_item_not_three() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file \
        "$(diag_label "$TEST_DIR/")" \
        "$(printf '%s\n\n%s\n%s' \
            "$(diag_label "$TEST_DIR/")" \
            "${TEST_DIR}/docs/demo.rst:105: WARNING: Title underline too short." \
            "Connections
----------")"

    audit_output demo-unit
    assert_eq "sphinx: the warning and its two continuation lines are ONE new item" \
        "1" "$AUDIT_RC"
    assert_contains "sphinx: one new item, not three" "$AUDIT_OUT" "1 new, 0 resolved"
    assert_contains "sphinx: the continuation rides with its header, it is not dropped" \
        "$AUDIT_OUT" "Connections"
    cleanup
}

# The multiset property. Two byte-identical diagnostics after where there was one before is
# exactly ONE new item; a set difference would report zero and wave the second one through.
test_sphinx_a_repeated_diagnostic_counts_once_per_occurrence() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    local one two
    one="$(diag_label "$TEST_DIR/")"
    two="${one}"$'\n'"${one}"
    write_run_file "$one" "$two"

    audit_output demo-unit
    assert_eq "sphinx: the second occurrence is a new item, so the audit exits 1" \
        "1" "$AUDIT_RC"
    assert_contains "sphinx: counted once per occurrence, not once per distinct line" \
        "$AUDIT_OUT" "1 new, 0 resolved"
    cleanup
}

# Rule 4, and the prohibition this plan carries: nothing is excluded by filename. A diagnostic
# naming a file nobody in the leg touched is still compared, because filtering the evidence to
# make a claim come out clean is the exact failure VAL-06 and D-07 exist against.
test_sphinx_a_diagnostic_naming_an_untouched_file_is_still_compared() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file "" \
        "${TEST_DIR}/docs/how-to/nobody-touched-this.rst:12: WARNING: image file not readable: x.png"

    audit_output demo-unit
    assert_eq "sphinx: an untouched file's diagnostic still gates" "1" "$AUDIT_RC"
    assert_contains "sphinx: and is named in the FLAG, never filtered out" \
        "$AUDIT_OUT" "docs/how-to/nobody-touched-this.rst:12: WARNING: image file not readable"
    cleanup
}

# --- determinism and posture ---------------------------------------------------------------

# Two runs over the same pair of builds print byte-identical `[sphinx]` output. Sorting the
# two item sets is what buys this: without it the block would reorder with dict iteration and
# two honest runs would diff against each other.
test_sphinx_two_runs_over_one_run_file_print_byte_identical_output() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file \
        "$(diag_toctree "$TEST_DIR/")" \
        "$(diag_label "$TEST_DIR/")"$'\n'"${TEST_DIR}/docs/a.rst:1: WARNING: another"

    audit_output demo-unit
    local first second
    first=$(sphinx_block)
    audit_output demo-unit
    second=$(sphinx_block)
    assert_not_eq "sphinx: the block is not empty" "" "$first"
    assert_eq "sphinx: two runs over one RUN file print byte-identical output" \
        "$first" "$second"
    cleanup
}

# WR-11: the RUN file is UNTRACKED, unvalidated working-tree input that both the kit and the
# tool read. A malformed one FLAGs naming what was wrong with it and never raises — a
# traceback at the reader is the outcome T-19-16 is filed against.
test_sphinx_a_malformed_run_file_flags_without_a_traceback() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    mkdir -p "$TEST_DIR/validation"
    printf 'not json at all\n' >"$TEST_DIR/validation/RUN-reference.json"

    audit_output demo-unit
    assert_eq "sphinx: an unparseable RUN file exits 1" "1" "$AUDIT_RC"
    assert_contains "sphinx: it FLAGs rather than raising" "$AUDIT_OUT" "FLAG [sphinx]"
    assert_not_contains "sphinx: no Python traceback reaches the caller" \
        "$AUDIT_OUT" "Traceback (most recent call last)"

    printf '[]\n' >"$TEST_DIR/validation/RUN-reference.json"
    audit_output demo-unit
    assert_contains "sphinx: a RUN file that is not an object FLAGs by shape" \
        "$AUDIT_OUT" "FLAG [sphinx]"

    printf '{"sphinx_before": {"exit": 0}}\n' >"$TEST_DIR/validation/RUN-reference.json"
    audit_output demo-unit
    assert_contains "sphinx: a missing sphinx_after is named rather than guessed at" \
        "$AUDIT_OUT" "sphinx_after"
    cleanup
}

# The 19-02 SKIP, preserved. Absence of the RUN file is not a pass of the section 10 rule and
# not a FLAG either — `protocol` is the gate over a leg that never wrote one.
test_sphinx_no_run_file_still_skips_and_never_passes() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst

    audit_output demo-unit
    assert_eq "sphinx: a leg with no RUN file leaves the audit at 0" "0" "$AUDIT_RC"
    assert_contains "sphinx: and SKIPs rather than passing" "$AUDIT_OUT" "SKIP [sphinx]"
    assert_not_contains "sphinx: it never claims a pass it did not make" \
        "$AUDIT_OUT" "PASS [sphinx]"
    cleanup
}

# The bookkeeping is printed on a PASS as well as on a FLAG. A gate that shows its working
# only when it fails leaves a green run unreadable, and the exit codes of the two builds are
# half of what section 10 asks for — a build that CRASHED with no diagnostics at all is not
# the same fact as a build that emitted none.
test_sphinx_prints_both_exit_codes_and_the_counts_on_a_pass() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file_with_exits 0 0 \
        "docs/a.rst:1: WARNING: one" "docs/a.rst:1: WARNING: one"

    audit_output demo-unit
    assert_eq "sphinx: two completed builds with an empty diff leave the audit at 0" \
        "0" "$AUDIT_RC"
    assert_contains "sphinx: the line PASSes" "$AUDIT_OUT" "PASS [sphinx]"
    assert_contains "sphinx: the before build's exit status is reported" \
        "$AUDIT_OUT" "before exit 0"
    assert_contains "sphinx: so is the after build's" "$AUDIT_OUT" "after exit 0"
    assert_contains "sphinx: and both counts, on a pass" "$AUDIT_OUT" "0 new, 0 resolved"
    assert_contains "sphinx: the RUN file it read is named" "$AUDIT_OUT" "RUN-reference.json"
    cleanup
}

# CR-03, the direct repro: `[sphinx]` is GATING and its verdict used to be the diagnostics
# diff alone, so two builds that CRASHED identically produced an empty diff and a PASS. The
# exit codes were printed and compared to nothing. A build that did not complete is not a
# build that emitted no diagnostics, and an empty diff over two builds that never ran is the
# vacuous green this whole kit exists against.
test_sphinx_two_builds_that_crashed_identically_flag_rather_than_pass() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file_with_exits 2 2 \
        "docs/a.rst:1: WARNING: one" "docs/a.rst:1: WARNING: one"

    audit_output demo-unit
    assert_eq "sphinx: an empty diff over two crashed builds exits 1" "1" "$AUDIT_RC"
    assert_contains "sphinx: the gating line FLAGs" "$AUDIT_OUT" "FLAG [sphinx]"
    assert_not_contains "sphinx: and never claims the pass the diff alone would have given" \
        "$AUDIT_OUT" "PASS [sphinx]"
    assert_contains "sphinx: the FLAG names both halves that did not complete" \
        "$AUDIT_OUT" "sphinx_before, sphinx_after"
    assert_contains "sphinx: and says why an empty diff is not evidence here" \
        "$AUDIT_OUT" "not a build that emitted no diagnostics"
    cleanup
}

# One half only, and the other finding beside it: a crashed AFTER build plus a new item
# nobody accounted for is TWO things to fix, and both are reported in one run. A gate that
# stops at the first violation makes an author fix one thing and come back.
test_sphinx_a_crashed_half_and_an_unaccounted_item_are_both_reported() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    write_run_file_with_exits 0 127 "" "$(diag_label "$TEST_DIR/")"

    audit_output demo-unit
    assert_eq "sphinx: a crashed after-build exits 1" "1" "$AUDIT_RC"
    assert_contains "sphinx: the crashed half is named, and only that half" \
        "$AUDIT_OUT" "sphinx_after=127"
    assert_not_contains "sphinx: the completed half is not named as crashed" \
        "$AUDIT_OUT" "sphinx_before=0"
    assert_contains "sphinx: the unaccounted item is reported in the same run" \
        "$AUDIT_OUT" "accounted for by nobody"
    cleanup
}

# A RUN file that records no `exit` at all for a half is not evidence that the half ran. The
# absent key is reported by value rather than assumed to be zero.
test_sphinx_a_missing_exit_key_is_not_a_completed_build() {
    setup_repo
    setup_sealed_unit demo-unit reference/demo.rst
    mkdir -p "$TEST_DIR/validation"
    python3 -c '
import json, sys
data = {"leg": "reference", "sphinx": "fixture",
        "sphinx_before": {"diagnostics": ""},
        "sphinx_after": {"diagnostics": ""},
        "sphinx_attribution": []}
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
' "$TEST_DIR/validation/RUN-reference.json"

    audit_output demo-unit
    assert_eq "sphinx: a RUN file recording no exit codes exits 1" "1" "$AUDIT_RC"
    assert_contains "sphinx: the gating line FLAGs" "$AUDIT_OUT" "FLAG [sphinx]"
    assert_contains "sphinx: and names the absent value rather than assuming zero" \
        "$AUDIT_OUT" "sphinx_before=None"
    cleanup
}

# The `runmeta.sh` half of CR-03: a `sphinx-build` that could not be EXECUTED is refused
# outright rather than recorded as a build that emitted nothing. 127 with an empty
# diagnostics file is exactly what a missing `docs/.venv` or a typo'd `SPHINX_BUILD`
# produces, and it used to be written into the RUN file as `exit 127, 0 warn`.
test_runmeta_refuses_a_sphinx_build_it_could_not_execute() {
    setup_target_repo
    stub_sphinx 127 ""

    runmeta_output begin --leg reference --repo "$TEST_DIR"
    assert_not_eq "runmeta: a build that could not be executed does not exit 0" \
        "0" "$RUNMETA_RC"
    assert_contains "runmeta: the refusal names the 127 it saw" \
        "$RUNMETA_OUT" "could not be executed (exit 127)"
    assert_contains "runmeta: and names the indirection the author has to set" \
        "$RUNMETA_OUT" "SPHINX_BUILD"
    assert_file_not_exists "runmeta: and no RUN file was written for a build that never ran" \
        "$TEST_DIR/validation/RUN-reference.json"
    cleanup
}

# =========================================================================================
# `protocol` — rev8 §10's six checks, and the refusal of an incomplete RUN (VAL-07)
# =========================================================================================

# --- helpers (NEVER `test_`-prefixed — `main` would discover them as tests) ---------------

# Run the scorer's `protocol` over a directory and capture BOTH streams plus the exit code.
protocol_output() {
    PROTOCOL_OUT=$(python3 "$SCORE" protocol "${1:-$TEST_DIR/validation}" 2>&1)
    PROTOCOL_RC=$?
    return 0
}

# Mutate the RUN file in place through python3, so no case below hand-writes a whole file it
# only wanted to break in one named way — the same rule `rewrite_ledger_event` follows for the
# ledger, and for the same reason.
patch_run_file() {
    python3 -c '
import json, sys
path, mutation = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
exec(mutation, {"data": data})  # noqa: S102 — a fixture-side mutation
with open(path, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
' "$TEST_DIR/validation/RUN-reference.json" "$1"
}

# A pre-registered leg file with every heading `protocol`'s fifth check requires and one
# rubric table for its sixth. `$1` is the score written into the rows: `UNSCORED` is the
# placeholder the sixth check refuses, `n/a` is the legitimate value for a dimension that
# cannot apply, and a number is a filled score.
write_leg_file() {
    local score="${1:-2}"
    mkdir -p "$TEST_DIR/validation/legs"
    cat >"$TEST_DIR/validation/legs/reference.md" <<LEG
# Reference leg — fixture

## Pre-registration

Written before the session could run.

## Prerequisites

The baseline tag, as placed.

## The walk

Two units.

## Rubric instantiation

| dimension | unit | score |
| --- | --- | --- |
| 1. Coverage parity | \`demo-unit\` | \`${score}\` |
| 3b. Cross-page consistency | \`demo-unit\` | \`n/a\` |

## Baseline row

The row a usable draft must reach.

## Sphinx expectation

0 new items and 17 resolved.

## Green audit

\`score.py audit\` exited 0.

## Metrics

Authored once, in the RUN file.

## Friction

no friction recorded

## Findings

None.
LEG
}

# The RUN file `protocol` accepts: written by `runmeta.sh`, then COMPLETED the way the author
# completes it — the transcript sha filled from OUTSIDE the session. That second step is not a
# fixture convenience, it is Pitfall 6's two-step performed, and it is the only way a RUN file
# can ever satisfy the second check.
# `$1` selects whether the unit records an `origins[]` at all. `with-origins` (the default) is
# the shape every check below wants; `no-origins` is the one WR-03 is about — a unit drafted
# without `--report`, whose D-08 digests are both taken over an empty list.
complete_run_file() {
    setup_target_repo
    if [ "${1:-with-origins}" = "no-origins" ]; then
        setup_drafted_unit demo-unit reference/demo.rst
    else
        setup_unit_with_origins demo-unit reference/demo.rst
    fi
    bash "$RUNMETA" begin --leg reference --repo "$TEST_DIR" --model fixture-model \
        >/dev/null 2>&1
    set_metric_flags
    stub_sphinx 0 ""
    bash "$RUNMETA" end --leg reference --repo "$TEST_DIR" --unit demo-unit \
        "${METRIC_FLAGS[@]}" >/dev/null 2>&1
    patch_run_file 'data["transcript"]["sha256"] = "a" * 64'
    write_leg_file 2
}

# The count of check lines in the last `protocol` run — six, always, because none of them
# short-circuits the others.
protocol_check_lines() {
    printf '%s\n' "$PROTOCOL_OUT" |
        grep -cE '^(PASS|FLAG) \[(run|transcript|compat|context|results|rubric)\]'
}

# --- the clean run, and the shape of the report -------------------------------------------

# Six checks, six lines, exit 0. The positive half of VAL-07: a gate only ever exercised
# against broken inputs cannot state what a conformant leg looks like.
test_protocol_a_complete_run_and_a_filled_leg_file_exits_0() {
    complete_run_file

    protocol_output
    assert_eq "protocol: a complete RUN file and a filled leg file exit 0" "0" "$PROTOCOL_RC"
    assert_eq "protocol: six checks, one line each" "6" "$(protocol_check_lines)"
    assert_contains "protocol: the RUN-file completeness check PASSes" \
        "$PROTOCOL_OUT" "PASS [run]"
    assert_contains "protocol: the transcript-sha check PASSes on a 64-hex value" \
        "$PROTOCOL_OUT" "PASS [transcript]"
    assert_contains "protocol: the compatibility numbers PASS" "$PROTOCOL_OUT" "PASS [compat]"
    assert_contains "protocol: context == baseline PASSes" "$PROTOCOL_OUT" "PASS [context]"
    assert_contains "protocol: the leg file's headings PASS" "$PROTOCOL_OUT" "PASS [results]"
    assert_contains "protocol: the rubric score rows PASS" "$PROTOCOL_OUT" "PASS [rubric]"
    cleanup
}

# EVERY failing check is reported, not the first. A gate that stops at the first violation
# makes an author fix one thing, re-run, and find the next — and the whole point of a
# conformance report is to hand back the full list once.
test_protocol_reports_every_failing_check_not_only_the_first() {
    complete_run_file
    patch_run_file '
data["transcript"]["sha256"] = None
data["context"]["origins_sha256"] = "b" * 64
'

    protocol_output
    assert_eq "protocol: two failing checks still exit 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the transcript check FLAGged" "$PROTOCOL_OUT" "FLAG [transcript]"
    assert_contains "protocol: and so did the context check, in the same run" \
        "$PROTOCOL_OUT" "FLAG [context]"
    assert_eq "protocol: all six lines are still printed" "6" "$(protocol_check_lines)"
    cleanup
}

# --- check 2: the transcript sha ------------------------------------------------------------

# A null sha is exactly what `end` writes, and it is exactly what `protocol` refuses: the
# author fills it from OUTSIDE the session, and the message says so rather than leaving a
# reader to guess why the field they have never touched is a violation.
test_protocol_a_null_transcript_sha_flags_and_says_who_fills_it() {
    complete_run_file
    patch_run_file 'data["transcript"]["sha256"] = None'

    protocol_output
    assert_eq "protocol: a null transcript sha exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the transcript check is the one that FLAGged" \
        "$PROTOCOL_OUT" "FLAG [transcript]"
    assert_contains "protocol: the message says the author fills it from outside the session" \
        "$PROTOCOL_OUT" "outside the session"
    cleanup
}

# --- check 1: RUN file completeness ---------------------------------------------------------

# A missing top-level key is named. A checker that reports "the RUN file is incomplete" without
# saying which key is absent is the failure mode this tree lints against by convention.
test_protocol_a_missing_run_key_flags_naming_it() {
    complete_run_file
    patch_run_file 'data.pop("harness", None)'

    protocol_output
    assert_eq "protocol: a RUN file missing a required key exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the completeness check FLAGged" "$PROTOCOL_OUT" "FLAG [run]"
    assert_contains "protocol: and named the key that is absent" "$PROTOCOL_OUT" "harness"
    cleanup
}

# The six rev8 §3.2 metrics are part of completeness, and a missing one is named as a METRIC
# rather than folded into the key list — the author is being told which measurement was never
# taken, which is a different instruction from "add a key".
test_protocol_a_missing_metric_key_flags_naming_it() {
    complete_run_file
    patch_run_file 'data["metrics"].pop("avoidable_questions", None)'

    protocol_output
    assert_eq "protocol: a metrics object missing one of the six exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the completeness check FLAGged" "$PROTOCOL_OUT" "FLAG [run]"
    assert_contains "protocol: and named the missing §3.2 metric" \
        "$PROTOCOL_OUT" "avoidable_questions"
    cleanup
}

# Two RUN files in one directory is the state `dogen` cannot see: `sphinx_result` takes the
# first by sorted NAME and says nothing about the second. `protocol` is where that is said.
test_protocol_a_second_run_file_flags_naming_both() {
    complete_run_file
    cp "$TEST_DIR/validation/RUN-reference.json" "$TEST_DIR/validation/RUN-actionable.json"

    protocol_output
    assert_eq "protocol: two RUN files in one directory exit 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the completeness check FLAGged" "$PROTOCOL_OUT" "FLAG [run]"
    assert_contains "protocol: the FLAG names the file dogen would pick" \
        "$PROTOCOL_OUT" "RUN-actionable.json"
    assert_contains "protocol: and the one it would silently ignore" \
        "$PROTOCOL_OUT" "RUN-reference.json"
    cleanup
}

# --- check 3: the compatibility numbers ------------------------------------------------------

# `tool.contract` and `tool.min_tool` are compared against `dogen version --json` — the same
# two numbers `tests/check_docs.py` already pins docs/compatibility.md's COMPAT region against, so this is a
# second reading of one source rather than a third opinion. A mismatch names BOTH sides.
test_protocol_compatibility_numbers_name_both_sides_on_a_mismatch() {
    complete_run_file
    patch_run_file 'data["tool"]["contract"] = 99'

    protocol_output
    assert_eq "protocol: a contract mismatch exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the compatibility check FLAGged" "$PROTOCOL_OUT" "FLAG [compat]"
    assert_contains "protocol: the FLAG names the number the RUN file recorded" \
        "$PROTOCOL_OUT" "99"
    assert_contains "protocol: and the number the tool reports now" \
        "$PROTOCOL_OUT" "$("$DOGEN" version --json | json_field contract)"
    cleanup
}

# --- check 4: context == baseline -------------------------------------------------------------

# Exact string equality of two sha256 hex digests, with both named on a difference. A leg whose
# sources moved under it between the tag and the seal has not measured what it pre-registered,
# and a reader cannot act on "they differ" without seeing which two values did.
test_protocol_context_differing_from_baseline_names_both_digests() {
    complete_run_file
    patch_run_file 'data["context"]["origins_sha256"] = "c" * 64'

    protocol_output
    assert_eq "protocol: a context digest that is not the baseline's exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the context check FLAGged" "$PROTOCOL_OUT" "FLAG [context]"
    assert_contains "protocol: the FLAG names the context digest" "$PROTOCOL_OUT" "cccccccc"
    assert_contains "protocol: and the baseline digest it was compared against" \
        "$PROTOCOL_OUT" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["baseline"]["origins_sha256"])' "$TEST_DIR/validation/RUN-reference.json")"
    cleanup
}

# WR-03: `origins[]` reaches a generation only when `draft --report` was used. With none
# recorded, `runmeta.sh` digests an empty list on BOTH sides and this check compared
# `e3b0c442…` to `e3b0c442…` and PASSed — text indistinguishable from a real pass, asserting
# the whole of D-08's claim over no sources at all. `setup_unit_with_origins` covers only the
# non-empty case, which is why nothing saw this.
test_protocol_an_empty_origins_list_skips_rather_than_passing_on_two_digests_of_nothing() {
    complete_run_file no-origins

    protocol_output
    assert_eq "context: no origins on either side is the empty digest, twice" \
        "0" "$(run_field reference 'len(data["baseline"]["origins"])')"
    assert_contains "context: it SKIPs — the evidence the rule needs is not there" \
        "$PROTOCOL_OUT" "SKIP [context]"
    assert_not_contains "context: and never claims the pass two digests of nothing would give" \
        "$PROTOCOL_OUT" "PASS [context]"
    assert_contains "context: the reader is told what was not digested" \
        "$PROTOCOL_OUT" "no source set to digest on either side"
    assert_eq "context: a SKIP does not gate, so the leg is not failed for it" \
        "0" "$PROTOCOL_RC"
    cleanup
}

# The non-empty case says how big the claim is. A digest line that names no count leaves a
# reader unable to tell one path from twenty-nine.
test_protocol_a_real_origins_digest_names_how_many_paths_it_covers() {
    complete_run_file

    protocol_output
    assert_contains "context: the check PASSes over a real source set" \
        "$PROTOCOL_OUT" "PASS [context]"
    assert_contains "context: and names how many paths the digest covers" \
        "$PROTOCOL_OUT" "the origins digest over 1 path(s)"
    cleanup
}

# A path with a stamp is still a string, but no file has that name. `runmeta.sh` digests
# `absent` on both sides and the equal hashes used to make this check PASS without reading
# the source. The report must contain plain repository-relative paths.
test_protocol_stamped_or_missing_origins_never_pass_on_two_absent_digests() {
    complete_run_file
    patch_run_file '
data["baseline"]["origins"] = ["notes/source-a.md @ baseline"]
data["context"]["origins"] = data["baseline"]["origins"]
data["baseline"]["origins_sha256"] = "a" * 64
data["context"]["origins_sha256"] = "a" * 64
'

    protocol_output
    assert_eq "context: matching absent-source digests cannot pass" "1" "$PROTOCOL_RC"
    assert_contains "context: rejects the revision-stamped origin" \
        "$PROTOCOL_OUT" "FLAG [context]"
    assert_contains "context: identifies the missing source" \
        "$PROTOCOL_OUT" "notes/source-a.md @ baseline"
    assert_not_contains "context: no vacuous pass" "$PROTOCOL_OUT" "PASS [context]"
    cleanup
}

test_protocol_absolute_origin_even_inside_repo_cannot_pass() {
    complete_run_file
    patch_run_file '
data["baseline"]["origins"] = [__import__("os").getcwd() + "/notes/source-a.md"]
data["context"]["origins"] = data["baseline"]["origins"]
'

    protocol_output
    assert_eq "context: requires repo-relative origin paths" "1" "$PROTOCOL_RC"
    assert_contains "context: absolute paths FLAG" "$PROTOCOL_OUT" "FLAG [context]"
    cleanup
}

# --- checks 5 and 6: the leg file ---------------------------------------------------------------

# The v1 `RESULTS.md` heading check, retargeted: `validation/legs/<leg>.md` is the v2.0 home of
# what v1 put in `RESULTS.md`. A missing heading is named, so the author is told which section
# of a PRE-REGISTERED file was never written.
test_protocol_a_leg_file_missing_a_heading_flags_naming_it() {
    complete_run_file
    python3 -c '
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(text.replace("## Sphinx expectation", "## Something else"))
' "$TEST_DIR/validation/legs/reference.md"

    protocol_output
    assert_eq "protocol: a leg file missing a required heading exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the leg-file check FLAGged" "$PROTOCOL_OUT" "FLAG [results]"
    assert_contains "protocol: and named the heading that is absent" \
        "$PROTOCOL_OUT" "Sphinx expectation"
    cleanup
}

# An absent leg file names the path it looked for — the same WR-03 courtesy `audit` extends for
# a missing ledger, and for the same reason: the scorer is pointed at other people's trees.
test_protocol_a_missing_leg_file_flags_naming_the_path() {
    complete_run_file
    rm -f "$TEST_DIR/validation/legs/reference.md"

    protocol_output
    assert_eq "protocol: a missing leg file exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the leg-file check FLAGged" "$PROTOCOL_OUT" "FLAG [results]"
    assert_contains "protocol: and named the path it looked for" \
        "$PROTOCOL_OUT" "legs/reference.md"
    cleanup
}

# Check 6, both directions. `UNSCORED` is the ONE placeholder token a leg file writes for a row
# nobody has scored yet, and it FLAGs naming the row. `n/a` is a different thing — a dimension
# that cannot apply to this leg, recorded up front so it can never be mistaken for an unfilled
# score — and it passes.
test_protocol_an_unfilled_rubric_score_row_flags_naming_the_row() {
    complete_run_file
    write_leg_file UNSCORED

    protocol_output
    assert_eq "protocol: an unfilled rubric score row exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the rubric check FLAGged" "$PROTOCOL_OUT" "FLAG [rubric]"
    assert_contains "protocol: and named the row that is unfilled" \
        "$PROTOCOL_OUT" "1. Coverage parity"

    write_leg_file 2
    protocol_output
    assert_contains "protocol: an n/a row is a legitimate score, not a placeholder" \
        "$PROTOCOL_OUT" "PASS [rubric]"
    cleanup
}

# --- CR-04: the RUN file's `leg` is a record-supplied path, and is guarded like one ----------

# `leg` is UNTRACKED, unvalidated working-tree input (WR-11) and was interpolated straight into
# `<directory>/legs/<leg>.md` with no containment. `"leg": "../../secret/loot"` read a file
# outside the tree AND check 6 echoed its table cells into the report, so this was a read
# primitive with an output channel rather than a stat. `_resolved_under` already existed for
# exactly this class of read and was not used here.
#
# The secret's rubric row carries a token nothing else in the run can produce, so the assertion
# is that the CONTENT did not travel — not merely that a check FLAGged.
test_protocol_a_traversing_leg_name_is_refused_unread() {
    complete_run_file
    mkdir -p "$TEST_DIR/secret"
    cat >"$TEST_DIR/secret/loot.md" <<'LOOT'
# Not a leg file

## Pre-registration

## Rubric instantiation

| dimension | unit | score |
| --- | --- | --- |
| exfiltrated-cell-nobody-should-see | `x` | `UNSCORED` |
LOOT
    patch_run_file 'data["leg"] = "../../secret/loot"'

    protocol_output
    assert_eq "leg: a traversing leg name still exits 1" "1" "$PROTOCOL_RC"
    assert_contains "leg: the leg-file check FLAGged" "$PROTOCOL_OUT" "FLAG [results]"
    assert_contains "leg: and said the value is not a leg name" \
        "$PROTOCOL_OUT" "is not a leg name"
    assert_not_contains "leg: the file outside the tree was never read" \
        "$PROTOCOL_OUT" "exfiltrated-cell-nobody-should-see"
    assert_file_exists "leg: and it is still sitting there, untouched" \
        "$TEST_DIR/secret/loot.md"
    cleanup
}

# The symlink the NAME check cannot see: `legs/<leg>.md` is a well-formed leg name pointing at
# a file outside the directory. `_resolved_under` follows the link when it resolves, which is
# why the containment check is the second control and not a duplicate of the first.
test_protocol_a_symlinked_leg_file_leaving_the_directory_is_refused() {
    complete_run_file
    mkdir -p "$TEST_DIR/secret"
    cat >"$TEST_DIR/secret/elsewhere.md" <<'LOOT'
# Not a leg file

## Rubric instantiation

| dimension | unit | score |
| --- | --- | --- |
| exfiltrated-cell-nobody-should-see | `x` | `UNSCORED` |
LOOT
    rm -f "$TEST_DIR/validation/legs/reference.md"
    ln -s "$TEST_DIR/secret/elsewhere.md" "$TEST_DIR/validation/legs/reference.md"

    protocol_output
    assert_eq "leg: a leg file symlinked out of the directory exits 1" "1" "$PROTOCOL_RC"
    assert_contains "leg: the leg-file check FLAGged" "$PROTOCOL_OUT" "FLAG [results]"
    assert_not_contains "leg: and the link's target was never read" \
        "$PROTOCOL_OUT" "exfiltrated-cell-nobody-should-see"
    cleanup
}

# --- the vacuous-pass guard and the no-crash posture -----------------------------------------

# Exit 2, never 0. A directory with no RUN file has had NOTHING checked, and reporting that as
# clean is the one outcome this exit contract exists to make impossible — a retargeted root or
# a reshaped tree must not be able to masquerade as a conformant leg.
test_protocol_a_directory_with_no_run_file_exits_2() {
    setup_repo
    mkdir -p "$TEST_DIR/nothing-here"

    protocol_output "$TEST_DIR/nothing-here"
    assert_eq "protocol: zero RUN files is the vacuous-pass guard, not a clean run" \
        "2" "$PROTOCOL_RC"
    assert_contains "protocol: and it says nothing was checked" \
        "$PROTOCOL_OUT" "NOTHING was checked"
    assert_not_contains "protocol: nothing is reported as having passed" \
        "$PROTOCOL_OUT" "PASS ["
    cleanup
}

# WR-11 again, on `protocol`'s side of the same untrusted file: invalid JSON FLAGs and exits 1
# with no traceback. The other checks that have evidence still run — the leg file is reached
# through the RUN file's NAME when its contents cannot be read.
test_protocol_a_malformed_run_file_flags_without_a_traceback() {
    complete_run_file
    printf 'not json at all\n' >"$TEST_DIR/validation/RUN-reference.json"

    protocol_output
    assert_eq "protocol: an unparseable RUN file exits 1" "1" "$PROTOCOL_RC"
    assert_contains "protocol: the completeness check FLAGged" "$PROTOCOL_OUT" "FLAG [run]"
    assert_not_contains "protocol: no Python traceback reaches the caller" \
        "$PROTOCOL_OUT" "Traceback (most recent call last)"

    printf '[]\n' >"$TEST_DIR/validation/RUN-reference.json"
    protocol_output
    assert_eq "protocol: a RUN file that is not an object also exits 1" "1" "$PROTOCOL_RC"
    assert_not_contains "protocol: still no traceback" \
        "$PROTOCOL_OUT" "Traceback (most recent call last)"
    cleanup
}

main
