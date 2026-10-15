#!/usr/bin/env bash
# test_crayon_lifecycle.sh — the N-series lifecycle, negative and recovery suite.
#
# Usage: bash tests/test_crayon_lifecycle.sh   (run from the repository root)
#
# D-10 splits the bash coverage in two. `tests/test_crayon_acceptance.sh` is
# the reviewer's A-01…A-35 — the suite they wrote, ported by intent, and must be able to
# open and recognise. THIS file is the N-series: the lifecycle walks, the
# negative paths, the recovery situations and the contract's trace table T1–T34b.
#
# Both suites source `tests/lib.sh` and neither carries a harness of its own:
# the hermetic temp repo, the assertion set, the WR-09 vacuous-test guard, the
# TAP runner and the auto-discovery all live there, once.
#
# D-09: every function's name carries its own test id and the trace(s) it
# discharges — `test_n40_t31_t32_…` — so `tests/check_traces.py` can find the
# test a trace-table row names by grepping for the id.
#
# Two ids that are NOT N-series live here anyway, decided in plan 17-01:
#
#   A-36 — an A-id in the N file. D-10 makes tests/test_crayon_acceptance.sh
#          the reviewer's A-01…A-35, the suite they wrote, so that they can open it and
#          recognise it. A-36 is new and has no counterpart there; putting it in
#          their file would break that recognition for no gain. Plan 17-10 closed
#          this the way RESEARCH Pitfall 11 proposed: with A-01…A-35 ported and
#          the whole A range enumerated, the contract's Mechanisms cell for
#          `retire` now names N-40 below rather than reserving A-36, so no A-36
#          function is ever written. The id is retired, not relocated.
#   V-05 — the T25 unknown-kinds trace. It is a `verify` BEHAVIOUR test, not a
#          phase-19 fixture, so it belongs to the lifecycle suite and carries
#          `v05` in its name. It lands with `verify` in plan 17-09.

set -u

# shellcheck source=tests/lib.sh
. "$(dirname "$0")/lib.sh"

# --- N-40: `unit retire` (VERB-07) — T31 claim policy, T32 the retire no-op ---

test_n40_t31_t32_retire_releases_the_target_claim() {
    setup_repo
    mkdir -p docs/how-to

    crayon_unit_new alpha "how-to/x.rst" >/dev/null 2>&1
    "$CRAYON" signoff alpha >/dev/null 2>&1

    # T31, claim-policy half (contract 5.1): a sibling cannot take a target that
    # a live unit's CURRENT signoff still lists, and the refusal has to be
    # actionable — it names the holder and the literal command that releases it,
    # because that hint is the row the plan skill acts on.
    local rc
    crayon_unit_new beta "how-to/x.rst" >/dev/null 2>claimed.txt
    rc=$?
    assert_eq "a claimed target refuses exit 1" "1" "$rc"
    assert_json_error "the refusal is target_claimed" "claimed.txt" "target_claimed"
    assert_file_contains "the detail names the claiming unit" "claimed.txt" "alpha"
    assert_file_contains "the hint is the literal retire command" "claimed.txt" \
        "crayon unit retire alpha --note"

    # The retire itself: exactly one event, one commit, one pathspec.
    local lines_before
    lines_before=$(wc -l <".crayon/units/alpha/ledger.jsonl")
    local out
    out=$("$CRAYON" unit retire alpha --note "superseded" 2>retire.txt)
    rc=$?
    assert_eq "unit retire exits 0" "0" "$rc"
    assert_eq "the response is exactly one line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "the response routes to the retired row" "$out" "Next: retired"
    assert_contains "the response names the released target" "$out" "how-to/x.rst"

    local lines_after
    lines_after=$(wc -l <".crayon/units/alpha/ledger.jsonl")
    assert_eq "exactly one event is appended" "$((lines_before + 1))" "$lines_after"
    local last
    last=$(ledger_line alpha "$lines_after")
    assert_eq "the appended event is a retired event" "retired" \
        "$(printf '%s' "$last" | json_field kind)"
    assert_eq "its note is what the author wrote" "superseded" \
        "$(printf '%s' "$last" | json_field note)"
    assert_eq "the envelope carries contract 1" "1" \
        "$(printf '%s' "$last" | json_field contract)"
    # The payload is `{note}` and nothing else (contract 5.3): a second key here
    # would be an unannounced widening of the event catalogue.
    assert_eq "the payload is exactly {note}" "note" \
        "$(printf '%s' "$last" | python3 -c '
import json, sys
envelope = {"kind", "seq", "prev", "at", "actor", "tool_version", "contract", "commit"}
print(",".join(sorted(k for k in json.load(sys.stdin) if k not in envelope)))
')"

    local subject body
    subject=$(git log -1 --format=%s)
    body=$(git log -1 --format=%B)
    assert_eq "the commit subject" "crayon: retired alpha" "$subject"
    assert_contains "the Crayon-Unit trailer" "$body" "Crayon-Unit: alpha"
    assert_contains "the Crayon-Phase trailer" "$body" "Crayon-Phase: retired"
    assert_contains "the Crayon-Seq trailer" "$body" "Crayon-Seq: $((lines_after - 1))"
    assert_eq "the Crayon-Head trailer is 16 hex" "1" \
        "$(printf '%s\n' "$body" | grep -cE '^Crayon-Head: [0-9a-f]{16}$')"
    # T-17-01: the pathspec is the ledger and nothing else — never a directory,
    # never `-A`. `git show --stat` is the instrument because it reports what
    # actually reached the commit, hooks included.
    assert_eq "the commit names the ledger alone" ".crayon/units/alpha/ledger.jsonl" \
        "$(git show --stat --format= --name-only HEAD | sed '/^$/d')"

    # T31, the other half: the claim is released by the committed event, read
    # back through derive() — no claim flag is stored anywhere.
    crayon_unit_new beta "how-to/x.rst" >/dev/null 2>released.txt
    rc=$?
    assert_eq "a sibling can claim the released target" "0" "$rc"

    # T32: retiring again is the verb's no-op (contract 5.7 d), not a refusal —
    # exit 3 carrying the existing event's seq and commit, appending nothing.
    "$CRAYON" unit retire alpha --note "again" >/dev/null 2>again.txt
    rc=$?
    assert_eq "a second retire exits 3" "3" "$rc"
    assert_json_error "the no-op is already_retired" "again.txt" "already_retired"
    assert_file_contains "the no-op names the existing event's seq" "again.txt" '"seq"'
    assert_file_contains "the no-op names the existing event's commit" "again.txt" '"commit"'
    assert_eq "the no-op appends nothing" "$lines_after" \
        "$(wc -l <".crayon/units/alpha/ledger.jsonl")"

    "$CRAYON" unit retire ghost --note "x" >/dev/null 2>ghost.txt
    rc=$?
    assert_eq "an unknown unit exits 2" "2" "$rc"
    assert_json_error "the refusal is unit_not_found" "ghost.txt" "unit_not_found"

    # Contract 5.6's note rule, in stage b — before the no-op, because a note
    # that could never be recorded is bad input whichever state the unit is in.
    "$CRAYON" unit retire alpha --note "$(printf 'a\rb')" >/dev/null 2>cr.txt
    rc=$?
    assert_eq "a carriage return in the note exits 2" "2" "$rc"
    assert_json_error "the refusal is note_required" "cr.txt" "note_required"

    "$CRAYON" unit retire alpha --note "" >/dev/null 2>blank.txt
    rc=$?
    assert_eq "an empty note exits 2" "2" "$rc"
    assert_json_error "the refusal is note_required" "blank.txt" "note_required"

    cleanup
}

# --- N-27: `plan-steps`, contract 5.4 step status and the reuse prefix -------
#
# T12 (an unresolved step refuses the draft), T13 (evidence carries forward only
# along consecutive reusing plans with an identical prefix) and T14 (the step
# no-op and stale evidence). The reuse ALGORITHM is driven exhaustively at unit
# level in `tests/test_crayon_unit.py` (TestReusePrefixCarryForward) because it is
# pure; this test proves the wiring end to end through the real executable.

# Local to this suite: the three draft helpers the acceptance suite keeps for
# itself. lib.sh is the shared harness (D-10) and is not widened for two
# callers in one file.



# An actionable (how-to) unit, declared and signed off.
walk_unit_new() {
    local unit="$1"
    printf '# Plan\n\nAn outline.\n' |
        "$CRAYON" unit new "$unit" \
            --intent how-to \
            --audience "TAs onboarding to the docs repo" \
            --title "Walk" \
            --target "how-to/guide.rst" \
            --body-file - >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
}

# One field of a unit's derived state, read through the real module.
derived_field() {
    python3 -c '
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
state = module.unit_state(os.getcwd(), sys.argv[2])
value = module.route(state) if sys.argv[3] == "next" else state[sys.argv[3]]
print(value if isinstance(value, str) else json.dumps(value))
' "$CRAYON" "$1" "$2"
}

# The human `Next:` segment for a routed token, read from the tool's own
# `next_line` (CLOSE-04), so the expected wording has one definition site.
human_next_line() {
    python3 -c '
import importlib.machinery, importlib.util, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
print(module.next_line(sys.argv[2]))
' "$CRAYON" "$1"
}

# The last event of a kind, as one JSON line.
last_event() {
    python3 -c '
import json, sys
found = ""
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if line and json.loads(line).get("kind") == sys.argv[2]:
        found = line
print(found)
' ".crayon/units/$1/ledger.jsonl" "$2"
}

# The unresolved step ids of a unit's CURRENT plan, read through the real
# derivation rather than re-implemented in the fixture.
unresolved_now() {
    python3 -c '
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
records = module.read_events(module.ledger_path(os.getcwd(), sys.argv[2]), sys.argv[2])
events = [event for event, _ in records]
plan = module._last_of(events, "steps-planned")
print(json.dumps(module.unresolved_steps(events, plan)))
' "$CRAYON" "$1"
}

THREE_STEPS='[{"id":"one","text":"install the tool","mode":"agent","stateful":false},
{"id":"two","text":"run the check","mode":"agent","stateful":false},
{"id":"three","text":"publish the result","mode":"ta","stateful":true}]'

# WR-12: the harness's own substring assertions, driven against a PRIVATE
# results file so their deliberate failures are this test's evidence rather than
# the suite's. `grep -F ''` matches every line, so an assertion whose needle
# expanded to the empty string recorded a PASS — and `set -u` catches an unset
# variable, never an empty one, while call sites pass variables. `grep -F` also
# reads a multi-line needle as a set of alternatives, so a multi-line
# expectation passed when any ONE of its lines matched.
test_wr12_the_substring_assertions_are_not_vacuous_on_an_empty_needle() {
    setup_repo
    printf 'one\ntwo\n' >probe.txt

    local outer="$RESULTS" probe
    probe=$(mktemp)
    RESULTS="$probe"

    assert_contains "empty needle" "anything at all" ""
    assert_not_contains "empty needle" "anything at all" ""
    assert_file_contains "empty needle" "probe.txt" ""
    local empty_fails empty_passes
    empty_fails=$(grep -c '^FAIL' "$probe" || true)
    empty_passes=$(grep -c '^PASS' "$probe" || true)

    : >"$probe"
    # Neither line of this needle is a substring of the haystack as a BLOCK,
    # but the first line is a substring of it line by line — which is exactly
    # what `grep -F` used to accept.
    assert_contains "a multi-line needle is one substring" \
        "$(printf 'alpha\nzulu\n')" "$(printf 'alpha\nbravo\n')"
    local multiline_fails
    multiline_fails=$(grep -c '^FAIL' "$probe" || true)

    : >"$probe"
    assert_contains "an ordinary substring still passes" "alpha bravo" "pha bra"
    assert_file_contains "and so does one in a file" "probe.txt" "two"
    assert_not_contains "and an absent one still passes" "alpha bravo" "charlie"
    local ordinary_passes ordinary_fails
    ordinary_passes=$(grep -c '^PASS' "$probe" || true)
    ordinary_fails=$(grep -c '^FAIL' "$probe" || true)

    : >"$probe"
    assert_file_contains "a missing file is reported, not swallowed" \
        "no-such-file.txt" "anything"
    local missing_fails
    missing_fails=$(grep -c '^FAIL' "$probe" || true)

    RESULTS="$outer"
    rm -f "$probe"

    assert_eq "all three refuse an empty needle" "3" "$empty_fails"
    assert_eq "and none of them calls it a pass" "0" "$empty_passes"
    assert_eq "a multi-line needle is a substring, never an alternation" "1" \
        "$multiline_fails"
    assert_eq "an ordinary substring is still a pass" "3" "$ordinary_passes"
    assert_eq "and records no failure" "0" "$ordinary_fails"
    assert_eq "a missing file is still a failure" "1" "$missing_fails"
    cleanup
}

# WR-04: with the `evidence_incomplete` raise moved into stage e, a capture-less
# non-`skipped` verdict now REACHES stage d carrying the digest of zero bytes.
# A step genuinely recorded from an empty capture would match that tuple, and d
# would answer `already_recorded` (exit 3, "nothing to do") for evidence the
# caller never supplied. An incomplete submission is not a no-op.
test_wr04_a_captureless_verdict_is_never_recognised_as_a_no_op() {
    setup_repo
    mkdir -p docs/how-to
    walk_unit_new wr04-unit

    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps wr04-unit --steps-file - >/dev/null 2>&1
    assert_eq "the plan records" "0" "$?"
    local seq
    seq=$(last_plan_seq wr04-unit)

    # A real step whose command produced NO output. Legitimate, and it makes
    # `output_sha256` the digest of zero bytes on the record.
    local ws=".crayon/staging/wr04-unit/scratch/evidence"
    mkdir -p "$ws"
    : >"$ws/one.out"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "x"}\n' \
        >"$ws/one.json"
    "$CRAYON" step wr04-unit one --steps-seq "$seq" \
        --evidence-file "$ws/one.json" --output-file "$ws/one.out" >/dev/null 2>&1
    assert_eq "a pass with an empty capture records" "0" "$?"

    local lines_before
    lines_before=$(wc -l <".crayon/units/wr04-unit/ledger.jsonl")

    # The same evidence with the capture WITHHELD. Every field of 5.7's no-op
    # tuple matches the event above, digest included.
    "$CRAYON" step wr04-unit one --steps-seq "$seq" \
        --evidence-file "$ws/one.json" >/dev/null 2>noop.txt
    local rc=$?
    assert_eq "withholding the capture exits 4, not 3" "4" "$rc"
    assert_json_error "and is refused as incomplete, never as a no-op" \
        "noop.txt" "evidence_incomplete"
    assert_eq "nothing is appended either way" "$lines_before" \
        "$(wc -l <".crayon/units/wr04-unit/ledger.jsonl")"
    cleanup
}

# WR-02 (iteration 3): the THIRD e-gate stage d was shadowing, and the same
# defect as the two above one field along. 5.7's no-op tuple is `(steps_seq,
# step_id, verdict, exit_code, output_sha256, reason)` — `mode` is not in it and
# is not compared — so resubmitting an identical capture under the WRONG mode
# matched field for field and was refused `already_recorded`, whose own detail
# says "already on the record, field for field". It is not: `mode` differs, and
# `evidence_mismatch` — the refusal CR-02 documented a remedy for on six
# surfaces — never fired.
test_wr02_an_identical_capture_in_a_divergent_mode_is_never_a_no_op() {
    setup_repo
    mkdir -p docs/how-to
    walk_unit_new wr02-unit

    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps wr02-unit --steps-file - >/dev/null 2>&1
    assert_eq "the plan records" "0" "$?"
    local seq
    seq=$(last_plan_seq wr02-unit)

    local ws=".crayon/staging/wr02-unit/scratch/evidence"
    mkdir -p "$ws"
    printf 'installed ok\n' >"$ws/one.out"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "x"}\n' \
        >"$ws/agent.json"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "ta", "command": "x"}\n' \
        >"$ws/ta.json"

    # Step `one` is declared `agent`. Record it in the declared mode first, so
    # there IS a record for stage d to match against.
    "$CRAYON" step wr02-unit one --steps-seq "$seq" \
        --evidence-file "$ws/agent.json" --output-file "$ws/one.out" \
        >/dev/null 2>&1
    assert_eq "the declared mode records" "0" "$?"

    local lines_before
    lines_before=$(wc -l <".crayon/units/wr02-unit/ledger.jsonl")

    # The SAME capture, verdict, exit code and reason — every field of the
    # no-op tuple — under a mode the plan does not declare.
    "$CRAYON" step wr02-unit one --steps-seq "$seq" \
        --evidence-file "$ws/ta.json" --output-file "$ws/one.out" \
        >/dev/null 2>mode.txt
    local rc=$?
    assert_eq "a divergent mode exits 4, not 3" "4" "$rc"
    assert_json_error "and names the real problem" "mode.txt" "evidence_mismatch"
    assert_file_contains "the detail names the declared mode" "mode.txt" "'agent'"
    assert_file_contains "and the claimed one" "mode.txt" "'ta'"
    assert_eq "nothing is appended" "$lines_before" \
        "$(wc -l <".crayon/units/wr02-unit/ledger.jsonl")"

    # Vacuous-pass guard: with the mode RESTORED the identical resubmission is
    # still the no-op stage d exists for, so the exclusion is scoped to the
    # divergence rather than having disabled d.
    "$CRAYON" step wr02-unit one --steps-seq "$seq" \
        --evidence-file "$ws/agent.json" --output-file "$ws/one.out" \
        >/dev/null 2>noop.txt
    assert_eq "the identical submission is still a no-op" "3" "$?"
    assert_json_error "recognised as already_recorded" "noop.txt" \
        "already_recorded"
    cleanup
}

test_n27_t12_t13_t14_step_status_and_reuse_prefix() {
    setup_repo
    mkdir -p docs/how-to
    walk_unit_new walk-unit

    local rc out

    # --- stage b: the D-01 shape, refused as `bad_target` per 16-03's rule ---
    # 16-03 routes every argparse, id and shape fault to ONE reason; a new key
    # here would be a REASONS entry the contract does not have.
    local ledger_before
    ledger_before=$(ledger_digest walk-unit)

    # STATE-03 probe 3: an empty plan is a plan that can never resolve.
    printf '[]' | "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>empty.txt
    rc=$?
    assert_eq "an empty steps array exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "empty.txt" "bad_target"

    printf '{"id":"one"}' | "$CRAYON" plan-steps walk-unit --steps-file - \
        >/dev/null 2>object.txt
    rc=$?
    assert_eq "a JSON object rather than an array exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "object.txt" "bad_target"

    printf 'not json' | "$CRAYON" plan-steps walk-unit --steps-file - \
        >/dev/null 2>notjson.txt
    rc=$?
    assert_eq "a non-JSON steps file exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "notjson.txt" "bad_target"

    printf '[{"id":"one","text":"a","mode":"agent","stateful":false},
{"id":"one","text":"b","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>dup.txt
    rc=$?
    assert_eq "a duplicate step id exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "dup.txt" "bad_target"
    assert_file_contains "the detail names the repeated id" "dup.txt" "one"

    printf '[{"id":"Step1","text":"a","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>badid.txt
    rc=$?
    assert_eq "a step id failing the 5.6 regex exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "badid.txt" "bad_target"

    # Pitfall 18: an unvalidated mode silently breaks the (text_hash, mode,
    # stateful) prefix comparison and reads as a reuse bug three plans later.
    printf '[{"id":"one","text":"a","mode":"run","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>badmode.txt
    rc=$?
    assert_eq "a mode outside the two wire values exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "badmode.txt" "bad_target"
    assert_file_contains "the hint names both wire values" "badmode.txt" "agent"
    assert_file_contains "the hint names both wire values" "badmode.txt" "ta"

    printf '[{"id":"one","text":"a","mode":"agent","stateful":"yes"}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>badflag.txt
    rc=$?
    assert_eq "a non-boolean stateful exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "badflag.txt" "bad_target"

    printf '[{"id":"one","text":"a","mode":"agent","stateful":false,"text_hash":"x"}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>typed.txt
    rc=$?
    assert_eq "a typed text_hash exits 2 — the TOOL computes it" "2" "$rc"
    assert_json_error "the refusal is bad_target" "typed.txt" "bad_target"
    assert_file_contains "the detail names the offending key" "typed.txt" "text_hash"

    printf '[{"id":"one","text":"   ","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>blank.txt
    rc=$?
    assert_eq "whitespace-only step text exits 2" "2" "$rc"
    assert_json_error "the refusal is note_required" "blank.txt" "note_required"

    # Pitfall 19: the contract makes reuse_note required whenever reuse is set,
    # and argparse registers the two flags independently.
    printf '%s' "$THREE_STEPS" | "$CRAYON" plan-steps walk-unit --steps-file - \
        --keep-evidence >/dev/null 2>noreason.txt
    rc=$?
    assert_eq "--keep-evidence without --note exits 2" "2" "$rc"
    assert_json_error "the refusal is note_required" "noreason.txt" "note_required"

    assert_eq "every stage-b refusal appended nothing" "$ledger_before" \
        "$(ledger_digest walk-unit)"

    # --- the first plan: `replaces` is null, `reuse` is false ----------------
    out=$(printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps walk-unit --steps-file - 2>plan1.txt)
    rc=$?
    assert_eq "a well-shaped step plan exits 0" "0" "$rc"
    assert_eq "the response is exactly one line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "the response routes to the walk" "$out" "Next: walk"
    assert_contains "the response counts the planned steps" "$out" "3 step"
    # Contract 5.4: `resolved` is a derivation result, never an observation.
    assert_not_contains "the response never claims execution" "$out" "executed"
    assert_not_contains "the response never claims verification" "$out" "verified"

    local plan1 seq1
    plan1=$(last_event walk-unit steps-planned)
    seq1=$(last_plan_seq walk-unit)
    assert_eq "the first plan's replaces is null" "null" \
        "$(printf '%s' "$plan1" | json_field replaces)"
    assert_eq "the first plan does not reuse" "False" \
        "$(printf '%s' "$plan1" | json_field reuse)"
    assert_eq "the payload is exactly {steps, replaces, reuse}" \
        "replaces,reuse,steps" \
        "$(printf '%s' "$plan1" | python3 -c '
import json, sys
envelope = {"kind", "seq", "prev", "at", "actor", "tool_version", "contract", "commit"}
print(",".join(sorted(k for k in json.load(sys.stdin) if k not in envelope)))
')"
    # D-01: the TOOL computes text_hash, and it is sha256 over the UTF-8 bytes.
    assert_eq "every entry carries a tool-computed text_hash" \
        "$(sha256_of_text 'install the tool') $(sha256_of_text 'run the check') $(sha256_of_text 'publish the result')" \
        "$(printf '%s' "$plan1" | python3 -c '
import json, sys
print(" ".join(s["text_hash"] for s in json.load(sys.stdin)["steps"]))
')"
    assert_eq "every entry carries exactly the five recorded keys" \
        "id,mode,stateful,text,text_hash" \
        "$(printf '%s' "$plan1" | python3 -c '
import json, sys
print(",".join(sorted(json.load(sys.stdin)["steps"][0])))
')"
    # D-01 forbids mirroring the plan into unit.md by name: that re-opens the
    # 13-08 plan_stale friction the tool spent a milestone closing.
    assert_eq "the plan is NOT mirrored into unit.md" "0" \
        "$(grep -c 'install the tool' ".crayon/units/walk-unit/unit.md" || true)"
    assert_eq "the unit is not plan_stale after planning steps" "false" \
        "$(derived_field walk-unit plan_stale)"
    # The read surface lists the recorded plan, so a session that did not
    # propose it walks it from `show` rather than from the ledger.
    assert_contains "show lists each recorded step with its text" \
        "$("$CRAYON" show walk-unit 2>&1)" \
        "1. one [agent] — unresolved: install the tool"
    assert_eq "show --json carries the plan's texts" \
        "install the tool|run the check|publish the result" \
        "$("$CRAYON" show walk-unit --json | python3 -c '
import json, sys
print("|".join(row["text"] for row in json.load(sys.stdin)["steps"]["plan"]))
')"
    assert_eq "the commit names the ledger alone" \
        ".crayon/units/walk-unit/ledger.jsonl" \
        "$(git show --stat --format= --name-only HEAD | sed '/^$/d')"
    assert_eq "the commit subject" "crayon: steps-planned walk-unit" \
        "$(git log -1 --format=%s)"

    # --- T12: an unresolved step refuses the draft --------------------------
    stage_draft walk-unit "how-to/guide.rst" "the guide\n"
    "$CRAYON" draft walk-unit "$(draft_path walk-unit how-to/guide.rst)" \
        >/dev/null 2>t12.txt
    rc=$?
    assert_eq "drafting with an unresolved step exits 4" "4" "$rc"
    assert_json_error "the refusal is steps_unresolved" "t12.txt" "steps_unresolved"
    assert_file_contains "the detail names the unresolved step" "t12.txt" "one"
    assert_file_contains "the hint is the crayon step command" "t12.txt" "crayon step"
    assert_file_contains "the hint carries the right --steps-seq" "t12.txt" \
        "--steps-seq $seq1"

    # --- the walk: evidence recorded against the first plan ------------------
    record_step walk-unit one "$seq1" pass "installed ok\n" >/dev/null 2>one.txt
    rc=$?
    assert_eq "a pass step with captured output exits 0" "0" "$rc"
    record_step walk-unit two "$seq1" pass "check ok\n" >/dev/null 2>&1
    out=$(skip_step walk-unit three "$seq1" "the publish step needs a credential \
this environment does not hold" 2>three.txt)
    rc=$?
    assert_eq "a skipped step with a reason exits 0" "0" "$rc"
    assert_contains "the step response reports the tally" "$out" "passed 2"
    assert_contains "the step response reports the skip" "$out" "skipped 1"
    assert_not_contains "the step response never claims execution" "$out" "executed"
    assert_not_contains "the step response never claims verification" "$out" "verified"

    assert_eq "every step now resolves" "true" \
        "$(derived_field walk-unit steps_resolved)"

    # --- T12, second half: with --keep-evidence and an identical prefix, 0 ---
    out=$(printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps walk-unit --steps-file - --keep-evidence \
            --note "the prefix is unchanged; the plan was re-recorded verbatim" \
            2>plan2.txt)
    rc=$?
    assert_eq "a reusing re-plan exits 0" "0" "$rc"
    local plan2
    plan2=$(last_event walk-unit steps-planned)
    assert_eq "replaces names the plan this one supersedes" "$seq1" \
        "$(printf '%s' "$plan2" | json_field replaces)"
    assert_eq "reuse is recorded true" "True" \
        "$(printf '%s' "$plan2" | json_field reuse)"
    assert_eq "the reuse note is recorded" \
        "the prefix is unchanged; the plan was re-recorded verbatim" \
        "$(printf '%s' "$plan2" | json_field reuse_note)"
    assert_eq "a reusing plan's payload adds exactly reuse_note" \
        "replaces,reuse,reuse_note,steps" \
        "$(printf '%s' "$plan2" | python3 -c '
import json, sys
envelope = {"kind", "seq", "prev", "at", "actor", "tool_version", "contract", "commit"}
print(",".join(sorted(k for k in json.load(sys.stdin) if k not in envelope)))
')"
    assert_eq "the identical prefix carries the evidence forward" "true" \
        "$(derived_field walk-unit steps_resolved)"

    out=$("$CRAYON" draft walk-unit "$(draft_path walk-unit how-to/guide.rst)" \
        2>draft.txt)
    rc=$?
    assert_eq "the draft now succeeds" "0" "$rc"
    assert_contains "the draft line carries the derived tally" "$out" \
        "steps: passed 2 · skipped 1"
    assert_contains "the tally names the skip reason" "$out" "needs a credential"
    assert_contains "the tally reports nothing unresolved" "$out" "unresolved 0"
    # Pitfall 20 / contract 5.4: `resolved` is a derivation result, and the
    # response line is the record speaking in its own voice.
    assert_not_contains "the draft line never claims execution" "$out" "executed"
    assert_not_contains "the draft line never claims verification" "$out" "verified"

    # --- T13: a step changed one hop back stops carrying, and only from there
    local changed_steps
    changed_steps='[{"id":"one","text":"install the tool","mode":"agent","stateful":false},
{"id":"two","text":"run the check","mode":"agent","stateful":false},
{"id":"three","text":"publish the result TWICE","mode":"ta","stateful":true}]'
    printf '%s' "$changed_steps" |
        "$CRAYON" plan-steps walk-unit --steps-file - --keep-evidence \
            --note "the publish step now runs twice" >/dev/null 2>plan3.txt
    rc=$?
    assert_eq "a third reusing plan exits 0" "0" "$rc"
    assert_eq "the changed step no longer resolves" '["three"]' \
        "$(unresolved_now walk-unit)"

    # A fourth reusing plan, identical to the third: the change is two hops
    # back now and must STILL be seen — the prefix can only shrink.
    printf '%s' "$changed_steps" |
        "$CRAYON" plan-steps walk-unit --steps-file - --keep-evidence \
            --note "re-recorded verbatim to prove the hop walk" >/dev/null 2>&1
    assert_eq "the change is still seen two hops later" '["three"]' \
        "$(unresolved_now walk-unit)"

    # --- T14: stale evidence, and the exact duplicate ------------------------
    record_step walk-unit one "$seq1" pass "installed ok\n" >/dev/null 2>stale.txt
    rc=$?
    assert_eq "evidence against a superseded plan seq exits 4" "4" "$rc"
    assert_json_error "the refusal is evidence_stale" "stale.txt" "evidence_stale"

    # WR-04: contract 5.7 fixes stage e's order as `evidence_stale`,
    # `evidence_incomplete`, `evidence_mismatch`. The capture-less refusal used
    # to be raised in the copy/digest block ABOVE stage d, so a superseded
    # `--steps-seq` with a non-`skipped` verdict and no `--output-file` reported
    # `evidence_incomplete` — the wrong problem, pointing the caller at
    # re-capturing output when the plan itself had moved. Both are exit 4, so
    # only the `error` field can tell them apart.
    local ews=".crayon/staging/walk-unit/scratch/evidence"
    mkdir -p "$ews"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "x"}\n' \
        >"$ews/order.json"
    "$CRAYON" step walk-unit one --steps-seq "$seq1" \
        --evidence-file "$ews/order.json" >/dev/null 2>order.txt
    rc=$?
    assert_eq "a superseded seq with no capture still exits 4" "4" "$rc"
    assert_json_error "and reports the plan that moved, not the missing bytes" \
        "order.txt" "evidence_stale"

    # The same submission against the CURRENT plan is the one the incomplete
    # refusal belongs to — the vacuous-pass guard for the assertion above.
    local seq_now
    seq_now=$(last_plan_seq walk-unit)
    "$CRAYON" step walk-unit one --steps-seq "$seq_now" \
        --evidence-file "$ews/order.json" >/dev/null 2>order2.txt
    rc=$?
    assert_eq "a current seq with no capture exits 4" "4" "$rc"
    assert_json_error "and reports the missing bytes" "order2.txt" \
        "evidence_incomplete"

    local seq4 lines_before
    seq4=$(last_plan_seq walk-unit)
    # Step `three` is declared `ta` in THREE_STEPS, so its evidence says `ta`.
    record_step walk-unit three "$seq4" pass "published twice\n" ta \
        >/dev/null 2>&1
    assert_eq "the ta step records against its declared mode" "0" "$?"
    lines_before=$(wc -l <".crayon/units/walk-unit/ledger.jsonl")
    record_step walk-unit three "$seq4" pass "published twice\n" ta \
        >/dev/null 2>dup2.txt
    rc=$?
    assert_eq "an identical re-record exits 3" "3" "$rc"
    assert_json_error "the no-op is already_recorded" "dup2.txt" "already_recorded"
    assert_file_contains "the no-op names the existing event's seq" "dup2.txt" '"seq"'
    assert_file_contains "the no-op names the existing event's commit" "dup2.txt" \
        '"commit"'
    assert_eq "the no-op appends nothing" "$lines_before" \
        "$(wc -l <".crayon/units/walk-unit/ledger.jsonl")"

    # WR-01: T14's no-op is defined on the tuple, with no recency qualifier.
    # The adjacent case above is the easy one; the case that matters in a real
    # multi-step walk is a re-run of an EARLIER step, where the most recent
    # `step-recorded` names a DIFFERENT step. Scanning only that one event
    # failed the comparison and appended a second event and a second commit for
    # one fact.
    record_step walk-unit one "$seq4" pass "installed ok\n" >/dev/null 2>&1
    assert_eq "an earlier step recorded against the current plan appends" "0" "$?"
    record_step walk-unit two "$seq4" pass "check ok\n" >/dev/null 2>&1
    assert_eq "and so does the one after it" "0" "$?"

    lines_before=$(wc -l <".crayon/units/walk-unit/ledger.jsonl")
    record_step walk-unit one "$seq4" pass "installed ok\n" >/dev/null 2>dup3.txt
    rc=$?
    assert_eq "re-recording the EARLIER step identically exits 3" "3" "$rc"
    assert_json_error "the no-op is already_recorded" "dup3.txt" "already_recorded"
    assert_eq "and nothing is appended for a fact already on the record" \
        "$lines_before" "$(wc -l <".crayon/units/walk-unit/ledger.jsonl")"
    assert_eq "exactly one step-recorded event names (seq4, one)" "1" \
        "$(python3 - "$seq4" <<'PY'
import json, sys

seq = int(sys.argv[1])
count = 0
with open(".crayon/units/walk-unit/ledger.jsonl", encoding="utf-8") as handle:
    for line in handle:
        event = json.loads(line)
        if (
            event.get("kind") == "step-recorded"
            and event.get("steps_seq") == seq
            and event.get("step_id") == "one"
        ):
            count += 1
print(count)
PY
)"

    # --- a unit with no step plan reports no tally at all, not a zero one ----
    crayon_unit_new ref-unit "reference/api.rst" >/dev/null 2>&1
    "$CRAYON" signoff ref-unit >/dev/null 2>&1
    stage_draft ref-unit "reference/api.rst" "the reference\n"
    out=$("$CRAYON" draft ref-unit "$(draft_path ref-unit reference/api.rst)" 2>/dev/null)
    rc=$?
    assert_eq "a reference unit drafts" "0" "$rc"
    assert_not_contains "no step tally is reported" "$out" "passed"
    assert_not_contains "no step tally is reported" "$out" "unresolved"

    cleanup
}

# --- N-18: `step` evidence is computed by the tool, from bytes it copied -----
#
# LEDG-06's whole claim: the digest is over bytes the tool owns, a typed digest
# is refused by name, and an output path outside the repository is never read.

test_n18_step_evidence_is_tool_computed() {
    setup_repo
    mkdir -p docs/how-to
    walk_unit_new evidence-unit

    local rc out seq
    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps evidence-unit --steps-file - >/dev/null 2>&1
    seq=$(last_plan_seq evidence-unit)

    local ws=".crayon/staging/evidence-unit/scratch/evidence"
    mkdir -p "$ws"
    # Contract 5.1's repo layout: `.crayon/staging/` is the consuming repo's
    # ignored scratch. The tool never writes a .gitignore — it is the repo's —
    # so the fixture states the documented layout before asserting on it.
    printf '.crayon/staging/\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore crayon staging"

    # --- a pass step with captured output -----------------------------------
    printf 'installed version 1.2.3\n' >"$ws/one.out"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "tool --version"}\n' \
        >"$ws/one.json"
    out=$("$CRAYON" step evidence-unit one --steps-seq "$seq" \
        --evidence-file "$ws/one.json" --output-file "$ws/one.out" 2>err.txt)
    rc=$?
    assert_eq "a pass step with an output file exits 0" "0" "$rc"
    assert_eq "the response is exactly one line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "the response names the step and the verdict" "$out" "one"
    assert_contains "the response names the verdict" "$out" "pass"

    local copy recorded
    copy=".crayon/staging/evidence-unit/scratch/evidence/${seq}-one.out"
    assert_file_exists "the tool's own copy exists" "$copy"
    assert_eq "the copy is byte-identical to the source" \
        "$(sha256_of_text "$(cat "$ws/one.out")")" \
        "$(sha256_of_text "$(cat "$copy")")"
    # D-04: the copy lives under the gitignored staging path, so the full bytes
    # are recoverable locally and never committed.
    git check-ignore -q "$copy"
    assert_eq "the copy is gitignored" "0" "$?"
    assert_eq "the copy is not in the worktree status" "" \
        "$(git status --porcelain -- "$copy")"
    assert_eq "the copy is not tracked" "" "$(git ls-files -- "$copy")"

    recorded=$(last_event evidence-unit step-recorded)
    # The digest is computed independently here, from the bytes on disk.
    assert_eq "output_sha256 is the sha256 of the captured bytes" \
        "$(python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$copy")" \
        "$(printf '%s' "$recorded" | json_field output_sha256)"
    assert_eq "the excerpt fits the 4096-byte cap" "yes" \
        "$(printf '%s' "$recorded" | python3 -c '
import json, sys
excerpt = json.load(sys.stdin)["output_excerpt"]
print("yes" if len(excerpt.encode("utf-8")) <= 4096 else "no")
')"
    assert_eq "the tool recorded the plan's text_hash for this step" \
        "$(sha256_of_text 'install the tool')" \
        "$(printf '%s' "$recorded" | json_field text_hash)"
    assert_eq "the payload is exactly the contract 5.3 key set" \
        "command,exit_code,mode,output_excerpt,output_sha256,step_id,steps_seq,text_hash,verdict" \
        "$(printf '%s' "$recorded" | python3 -c '
import json, sys
envelope = {"kind", "seq", "prev", "at", "actor", "tool_version", "contract", "commit"}
print(",".join(sorted(k for k in json.load(sys.stdin) if k not in envelope)))
')"
    assert_eq "the commit names the ledger alone" \
        ".crayon/units/evidence-unit/ledger.jsonl" \
        "$(git show --stat --format= --name-only HEAD | sed '/^$/d')"

    # T-17-21: the caller's source can change afterwards; the record cannot.
    printf 'TAMPERED\n' >"$ws/one.out"
    assert_eq "the recorded digest still matches the tool's copy" \
        "$(python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$copy")" \
        "$(printf '%s' "$recorded" | json_field output_sha256)"
    assert_not_contains "the recorded excerpt is not the tampered bytes" \
        "$(printf '%s' "$recorded" | json_field output_excerpt)" "TAMPERED"

    # --- the no-op: an identical re-record, field for field ------------------
    printf 'installed version 1.2.3\n' >"$ws/one.out"
    local lines_before head_before
    lines_before=$(wc -l <".crayon/units/evidence-unit/ledger.jsonl")
    head_before=$(git rev-parse HEAD)
    "$CRAYON" step evidence-unit one --steps-seq "$seq" \
        --evidence-file "$ws/one.json" --output-file "$ws/one.out" \
        >/dev/null 2>noop.txt
    rc=$?
    assert_eq "an identical re-record exits 3" "3" "$rc"
    assert_json_error "the no-op is already_recorded" "noop.txt" "already_recorded"
    assert_eq "the no-op appends nothing" "$lines_before" \
        "$(wc -l <".crayon/units/evidence-unit/ledger.jsonl")"
    assert_eq "the no-op commits nothing" "$head_before" "$(git rev-parse HEAD)"

    # --- D-03: a verdict that needs proof, with none --------------------------
    lines_before=$(wc -l <".crayon/units/evidence-unit/ledger.jsonl")
    local verdict
    for verdict in pass fail deviated; do
        python3 -c '
import json, sys
payload = {"verdict": sys.argv[2], "exit_code": 0, "mode": "agent",
           "command": "tool --version"}
if sys.argv[2] != "pass":
    payload["reason"] = "the tool printed nothing"
json.dump(payload, open(sys.argv[1], "w", encoding="utf-8"))
' "$ws/two.json" "$verdict"
        "$CRAYON" step evidence-unit two --steps-seq "$seq" \
            --evidence-file "$ws/two.json" >/dev/null 2>"noout-$verdict.txt"
        rc=$?
        assert_eq "a $verdict step with no output file exits 4" "4" "$rc"
        assert_json_error "the refusal is evidence_incomplete" \
            "noout-$verdict.txt" "evidence_incomplete"
    done
    assert_eq "no refusal appended anything" "$lines_before" \
        "$(wc -l <".crayon/units/evidence-unit/ledger.jsonl")"

    # --- D-03: a skipped step needs no output file ---------------------------
    python3 -c '
import json, sys
json.dump({"verdict": "skipped", "exit_code": 0, "mode": "ta",
           "reason": "the publish step needs a credential this environment lacks"},
          open(sys.argv[1], "w", encoding="utf-8"))
' "$ws/three.json"
    "$CRAYON" step evidence-unit three --steps-seq "$seq" \
        --evidence-file "$ws/three.json" >/dev/null 2>skip.txt
    rc=$?
    assert_eq "a skipped step with a reason exits 0" "0" "$rc"
    recorded=$(last_event evidence-unit step-recorded)
    assert_eq "a skipped step records the digest of zero bytes" \
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
        "$(printf '%s' "$recorded" | json_field output_sha256)"
    assert_eq "a skipped step records an empty excerpt" "" \
        "$(printf '%s' "$recorded" | json_field output_excerpt)"
    assert_eq "the reason carries the why" \
        "the publish step needs a credential this environment lacks" \
        "$(printf '%s' "$recorded" | json_field reason)"

    # --- Pitfall 5: an ALLOW-list, so every typed digest is refused by name ---
    # The legacy v1.2 evidence file carried these two literally, so a TA
    # copying an old recipe lands here rather than on a silent acceptance.
    local key
    for key in output_sha256 step_text_sha256 sha256 digest hash text_hash step; do
        python3 -c '
import json, sys
json.dump({"verdict": "pass", "exit_code": 0, "mode": "agent",
           "command": "tool --version", sys.argv[2]: "deadbeef"},
          open(sys.argv[1], "w", encoding="utf-8"))
' "$ws/typed.json" "$key"
        "$CRAYON" step evidence-unit two --steps-seq "$seq" \
            --evidence-file "$ws/typed.json" --output-file "$ws/one.out" \
            >/dev/null 2>"typed-$key.txt"
        rc=$?
        assert_eq "an evidence file carrying $key exits 4" "4" "$rc"
        assert_json_error "the refusal is evidence_incomplete" \
            "typed-$key.txt" "evidence_incomplete"
        assert_file_contains "the detail names the offending key" \
            "typed-$key.txt" "$key"
    done

    # --- T-17-18: the source path is contained BEFORE it is opened -----------
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "cat"}\n' \
        >"$ws/two.json"
    "$CRAYON" step evidence-unit two --steps-seq "$seq" \
        --evidence-file "$ws/two.json" --output-file /etc/hostname \
        >/dev/null 2>outside.txt
    rc=$?
    assert_eq "an output path outside the repository exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_write_path" "outside.txt" "bad_write_path"
    assert_file_not_exists "nothing was copied" \
        ".crayon/staging/evidence-unit/scratch/evidence/${seq}-two.out"

    ln -s /etc/hostname "$ws/linked.out"
    "$CRAYON" step evidence-unit two --steps-seq "$seq" \
        --evidence-file "$ws/two.json" --output-file "$ws/linked.out" \
        >/dev/null 2>symlink.txt
    rc=$?
    assert_eq "a symlink resolving outside the repository exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_write_path" "symlink.txt" "bad_write_path"
    assert_file_not_exists "nothing was copied" \
        ".crayon/staging/evidence-unit/scratch/evidence/${seq}-two.out"

    # --- CR-03: contained to the UNIT'S SCRATCH TREE, not to the repository --
    #
    # The excerpt is committed verbatim (`scrub_excerpt` strips control
    # characters, never credentials), so "inside the repository" is not a
    # boundary: a gitignored secrets file and `.git/config` are both inside it,
    # and an LLM following walk-protocol.md is the caller.
    printf 'SECRET_TOKEN=abc123\n' >.env.local
    local inside
    for inside in .env.local .git/config docs/how-to; do
        "$CRAYON" step evidence-unit two --steps-seq "$seq" \
            --evidence-file "$ws/two.json" --output-file "$inside" \
            >/dev/null 2>inrepo.txt
        rc=$?
        assert_eq "an in-repo path outside scratch/ exits 2 ($inside)" "2" "$rc"
        assert_json_error "the refusal is bad_write_path ($inside)" "inrepo.txt" \
            "bad_write_path"
        assert_file_contains "the detail names the scope it enforces ($inside)" \
            "inrepo.txt" ".crayon/staging/evidence-unit/scratch/"
        assert_file_not_exists "nothing was copied ($inside)" \
            ".crayon/staging/evidence-unit/scratch/evidence/${seq}-two.out"
    done
    assert_not_contains "and no byte of it reaches the record" \
        "$(cat .crayon/units/evidence-unit/ledger.jsonl)" "SECRET_TOKEN"

    # Another unit's scratch is another unit's evidence, and is refused too.
    mkdir -p .crayon/staging/other-unit/scratch
    printf 'not this unit\n' >.crayon/staging/other-unit/scratch/stray.out
    "$CRAYON" step evidence-unit two --steps-seq "$seq" \
        --evidence-file "$ws/two.json" \
        --output-file .crayon/staging/other-unit/scratch/stray.out \
        >/dev/null 2>crossunit.txt
    rc=$?
    assert_eq "another unit's scratch exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_write_path" "crossunit.txt" \
        "bad_write_path"

    # --- WR-01: the containment test cannot police its own anchor -----------
    #
    # `contained` resolves BOTH operands with `realpath`, and `guard_crayon_root`
    # only `islink`-checks `.crayon`, `.crayon/staging` and `.crayon/units` — one
    # level short of `<staging>/<id>` and `<staging>/<id>/scratch`. With either
    # of those a symlink, `realpath(scratch)` and `realpath(scratch/x)` both
    # resolve through it and CR-03's check passes for any target, putting 4 KiB
    # of an arbitrary file back into a committed ledger. The link's own path has
    # to be named, and before the containment test.
    local secret="$PWD/outside-secret.txt"
    printf 'SMUGGLED_TOKEN=xyz789\n' >"$secret"
    local elsewhere="$PWD/elsewhere"
    mkdir -p "$elsewhere"
    cp "$secret" "$elsewhere/loot.out"
    # The evidence JSON lives under scratch/, which the next two cases move out
    # of the way; read it from outside so the refusal under test is the one
    # reported and not an unreadable --evidence-file.
    cp "$ws/two.json" evidence-outside.json

    mv .crayon/staging/evidence-unit/scratch scratch-real
    ln -s "$elsewhere" .crayon/staging/evidence-unit/scratch
    "$CRAYON" step evidence-unit two --steps-seq "$seq" \
        --evidence-file evidence-outside.json \
        --output-file .crayon/staging/evidence-unit/scratch/loot.out \
        >/dev/null 2>linkscratch.txt
    rc=$?
    assert_eq "a symlinked scratch/ exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_write_path" "linkscratch.txt" \
        "bad_write_path"
    assert_file_contains "and names the link, not the target" "linkscratch.txt" \
        "is a symlink"
    rm .crayon/staging/evidence-unit/scratch
    mv scratch-real .crayon/staging/evidence-unit/scratch

    # The same one level up: a symlinked UNIT staging directory.
    mv .crayon/staging/evidence-unit unit-real
    ln -s "$elsewhere" .crayon/staging/evidence-unit
    "$CRAYON" step evidence-unit two --steps-seq "$seq" \
        --evidence-file evidence-outside.json \
        --output-file .crayon/staging/evidence-unit/loot.out \
        >/dev/null 2>linkunit.txt
    rc=$?
    assert_eq "a symlinked unit staging directory exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_write_path" "linkunit.txt" \
        "bad_write_path"
    rm .crayon/staging/evidence-unit
    mv unit-real .crayon/staging/evidence-unit

    assert_not_contains "and not one smuggled byte reached the record" \
        "$(cat .crayon/units/evidence-unit/ledger.jsonl)" "SMUGGLED_TOKEN"
    rm -rf "$elsewhere" "$secret"

    # --- contract 5.6: --steps-seq must name a steps-planned of this unit ----
    "$CRAYON" step evidence-unit one --steps-seq 0 \
        --evidence-file "$ws/one.json" --output-file "$ws/one.out" \
        >/dev/null 2>badseq.txt
    rc=$?
    assert_eq "a steps-seq that is not a steps-planned exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "badseq.txt" "bad_target"

    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "x"}\n' \
        >"$ws/ghost.json"
    "$CRAYON" step evidence-unit ghost --steps-seq "$seq" \
        --evidence-file "$ws/ghost.json" --output-file "$ws/one.out" \
        >/dev/null 2>ghost.txt
    rc=$?
    assert_eq "a step id absent from the plan exits 2" "2" "$rc"
    assert_json_error "the refusal is step_unknown" "ghost.txt" "step_unknown"

    # --- the excerpt is capped, and the digest is over the FULL bytes --------
    python3 -c '
import sys
sys.stdout.write(("colour \x1b[1;32mgreen\x1b[0m café\r\n" * 400))
' >"$ws/big.out"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "big"}\n' \
        >"$ws/big.json"
    "$CRAYON" step evidence-unit two --steps-seq "$seq" \
        --evidence-file "$ws/big.json" --output-file "$ws/big.out" \
        >/dev/null 2>big.txt
    rc=$?
    assert_eq "a large colourised capture exits 0" "0" "$rc"
    recorded=$(last_event evidence-unit step-recorded)
    assert_eq "the digest is over the full raw bytes" \
        "$(python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$ws/big.out")" \
        "$(printf '%s' "$recorded" | json_field output_sha256)"
    assert_eq "the excerpt is capped and carries the marker" "yes" \
        "$(printf '%s' "$recorded" | python3 -c '
import json, sys
excerpt = json.load(sys.stdin)["output_excerpt"]
ok = len(excerpt.encode("utf-8")) <= 4096 and "bytes total)" in excerpt
print("yes" if ok else "no")
')"
    assert_eq "no escape sequence survives in the committed excerpt" "yes" \
        "$(printf '%s' "$recorded" | python3 -c '
import json, re, sys
excerpt = json.load(sys.stdin)["output_excerpt"]
clean = "\x1b" not in excerpt and not re.search(r"\[[0-9;?]*[mK]", excerpt)
clean = clean and not [c for c in excerpt if ord(c) < 32 and c not in "\n\t"]
print("yes" if clean else "no")
')"

    cleanup
}


# WR-04: `not_actionable`, which was a dead row in `REASONS`.
#
# The reason sat in the tool's table and in contract 5.7's at exit 2 with no
# raiser anywhere, while all three skills' routing tables already told the
# author what it means and where it routes — so the surface documented a gate
# the tool did not have, and `plan-steps` / `step` recorded a step walk for a
# `reference` unit quite happily. Contract 5.4 makes `tutorial` and `how-to`
# the actionable intents; the other two are drafted from their sources.

test_n27_wr04_a_step_walk_is_refused_on_a_unit_that_is_not_actionable() {
    setup_repo
    crayon_unit_new still-unit "reference/still.rst" >/dev/null 2>&1
    "$CRAYON" signoff still-unit >/dev/null 2>&1

    local rc before
    before=$(ledger_digest still-unit)

    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps still-unit --steps-file - >/dev/null 2>plan.txt
    rc=$?
    assert_eq "planning steps on a reference unit exits 2" "2" "$rc"
    assert_json_error "the refusal is not_actionable" "plan.txt" "not_actionable"
    assert_file_contains "the detail names the declared intent" "plan.txt" \
        "'reference'"
    assert_contains "the hint routes to drafting from the sources" \
        "$(cat plan.txt)" "crayon draft still-unit"
    assert_eq "nothing is appended" "$before" "$(ledger_digest still-unit)"

    # `step` is held to the same precondition, on the one path that can reach
    # it: a how-to whose plan was recorded and whose intent was then re-signed
    # away from an actionable one. (On a unit that was never actionable there
    # is no `steps-planned` to name, and stage b refuses `bad_target` first —
    # b precedes c, and this is the ordering the contract states.)
    mkdir -p docs/how-to
    walk_unit_new turn-unit
    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps turn-unit --steps-file - >/dev/null 2>&1
    assert_eq "an actionable unit plans its steps" "0" "$?"
    local seq
    seq=$(last_plan_seq turn-unit)

    mkdir -p docs/reference
    "$CRAYON" unit edit turn-unit --intent reference \
        --target "reference/turn.rst" --re-sign >/dev/null 2>&1
    assert_eq "the unit is re-signed as a reference page" "0" "$?"
    before=$(ledger_digest turn-unit)

    local ws=".crayon/staging/turn-unit/scratch/evidence"
    mkdir -p "$ws"
    printf 'output\n' >"$ws/one.out"
    printf '{"verdict": "pass", "exit_code": 0, "mode": "agent", "command": "x"}\n' \
        >"$ws/one.json"
    "$CRAYON" step turn-unit one --steps-seq "$seq" \
        --evidence-file "$ws/one.json" --output-file "$ws/one.out" \
        >/dev/null 2>step.txt
    rc=$?
    assert_eq "recording a step against a re-signed reference unit exits 2" \
        "2" "$rc"
    assert_json_error "the refusal is not_actionable" "step.txt" "not_actionable"
    assert_eq "and nothing is appended" "$before" "$(ledger_digest turn-unit)"
    assert_eq "the routed token is the one the skills' tables name" "draft" \
        "$(refusal_next step.txt)"
    cleanup
}


# WR-02: a step's evidence `mode` against the mode its plan declares.
#
# `read_evidence_file` checked that `mode` was one of the two the contract
# names and stopped, while `text_hash` was taken from the PLAN — so a record
# could claim a `ta` execution for a step the plan declares `agent` and still
# look internally consistent. Contract 5.4's reuse prefix key is
# `(text_hash, mode, stateful)` OF THE PLAN, so the two diverged silently and
# the carry-forward walk reasoned over a mode the evidence contradicted.
# `evidence_mismatch` was in the reason table with no raiser anywhere.

test_n18_wr02_evidence_mode_must_be_the_mode_the_plan_declares() {
    setup_repo
    mkdir -p docs/how-to
    walk_unit_new mode-unit

    local rc seq lines_before
    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps mode-unit --steps-file - >/dev/null 2>&1
    seq=$(last_plan_seq mode-unit)
    lines_before=$(ledger_lines mode-unit)

    # Step `one` is declared `agent`; this evidence claims `ta`.
    record_step mode-unit one "$seq" pass "installed ok\n" ta >/dev/null 2>mode.txt
    rc=$?
    assert_eq "evidence in a mode the plan does not declare exits 4" "4" "$rc"
    assert_json_error "the refusal is evidence_mismatch" "mode.txt" \
        "evidence_mismatch"
    assert_file_contains "the detail names the declared mode" "mode.txt" "'agent'"
    assert_file_contains "and the claimed one" "mode.txt" "'ta'"
    assert_eq "nothing is appended" "$lines_before" "$(ledger_lines mode-unit)"

    # Symmetric: step `three` is declared `ta`, and `agent` evidence is refused.
    record_step mode-unit three "$seq" pass "published\n" agent >/dev/null 2>mode2.txt
    rc=$?
    assert_eq "the gate is symmetric" "4" "$rc"
    assert_json_error "the refusal is evidence_mismatch" "mode2.txt" \
        "evidence_mismatch"
    assert_eq "and still nothing is appended" "$lines_before" \
        "$(ledger_lines mode-unit)"

    record_step mode-unit one "$seq" pass "installed ok\n" agent >/dev/null 2>&1
    assert_eq "the declared mode records" "0" "$?"

    # V8 reports the same divergence over a record written before the gate
    # existed — chain-valid, structurally complete, and wrong.
    local forged
    forged=$(python3 - "$seq" <<'PY'
import hashlib
import json
import sys

seq = int(sys.argv[1])
with open(".crayon/units/mode-unit/ledger.jsonl", encoding="utf-8") as handle:
    events = [json.loads(line) for line in handle]
plan = [
    event
    for event in events
    if event.get("kind") == "steps-planned" and event.get("seq") == seq
][0]
step = [entry for entry in plan["steps"] if entry["id"] == "two"][0]
body = b"check ok\n"
print(
    json.dumps(
        {
            "step_id": "two",
            "steps_seq": seq,
            "text_hash": step["text_hash"],
            # The plan declares `agent` for step two.
            "mode": "ta",
            "verdict": "pass",
            "exit_code": 0,
            "output_sha256": hashlib.sha256(body).hexdigest(),
            "output_excerpt": body.decode("utf-8"),
        }
    )
)
PY
)
    forge_event mode-unit step-recorded "$forged"
    assert_eq "the forged ledger is still chain-valid" "[]" \
        "$(chain_problems mode-unit)"

    "$CRAYON" verify mode-unit >v8.txt 2>v8err.txt
    rc=$?
    assert_eq "a failing record check exits 6" "6" "$rc"
    assert_json_error "the refusal is ledger_corrupt" "v8err.txt" "ledger_corrupt"
    assert_file_contains "V8 is the check that failed" "v8err.txt" "V8"
    assert_contains "and the report names the claimed mode" "$(cat v8.txt)" "'ta'"
    assert_contains "and the mode the plan declares" "$(cat v8.txt)" "'agent'"
    # VOICE-04 / D-04: the default report opens on the damage, never reads as
    # healthy, and names what failed in plain words (D-16).
    assert_eq "the default report opens on the damage" "The record is damaged:" \
        "$(sed -n 1p v8.txt)"
    assert_plain "the damaged report speaks plainly" "$(cat v8.txt)"
    assert_eq "the refusal is the one stderr line" "1" \
        "$(wc -l <v8err.txt | tr -d ' ')"

    # WR-01: the default report names the check by its plain label, so the
    # refusal after it gives each failing V id beside that same label, read
    # from the one CHECK_LABELS; the rest of the refusal is as it was.
    local ledger_damaged="is damaged and nothing may be appended"
    assert_eq "the default refusal's hint pairs the id with the report's label" \
        "the report above names each failing check: V8 (the step evidence); .crayon/units/mode-unit/ledger.jsonl $ledger_damaged" \
        "$(json_field hint <v8err.txt)"
    assert_eq "the default refusal's detail is unchanged" \
        "record integrity failed: V8" "$(json_field detail <v8err.txt)"
    assert_eq "the default refusal still routes show" "show" \
        "$(json_field next <v8err.txt)"
    assert_eq "the default refusal names the unit" "mode-unit" \
        "$(json_field unit <v8err.txt)"
    assert_eq "the report prints that label" "1" \
        "$(grep -c '^  the step evidence: ' v8.txt || true)"
    assert_eq "and names no V id (D-04)" "0" "$(grep -cE '\bV8\b' v8.txt || true)"

    "$CRAYON" verify mode-unit --verbose >v8v.txt 2>v8verr.txt
    assert_eq "verify --verbose on the damage exits 6" "6" "$?"
    assert_json_error "the --verbose refusal is ledger_corrupt" "v8verr.txt" \
        "ledger_corrupt"
    assert_eq "the --verbose refusal's hint is unchanged" \
        "the report above names each failing check; .crayon/units/mode-unit/ledger.jsonl $ledger_damaged" \
        "$(json_field hint <v8verr.txt)"
    assert_eq "the --verbose report names V8 by id" "1" \
        "$(grep -c '^V8 fail — ' v8v.txt || true)"

    "$CRAYON" verify mode-unit --json >v8j.txt 2>v8jerr.txt
    assert_eq "verify --json on the damage exits 6" "6" "$?"
    assert_eq "the --json refusal's hint is unchanged" \
        "the report above names each failing check; .crayon/units/mode-unit/ledger.jsonl $ledger_damaged" \
        "$(tail -n 1 v8j.txt | json_field hint)"
    assert_eq "the --json refusal's detail is unchanged" \
        "record integrity failed: V8" "$(tail -n 1 v8j.txt | json_field detail)"
    assert_eq "the --json refusal is ledger_corrupt" "ledger_corrupt" \
        "$(tail -n 1 v8j.txt | json_field error)"

    # VOICE-04 concurrency edge: verify takes no lock and writes nothing, so a
    # second default run prints the same bytes on both streams.
    "$CRAYON" verify mode-unit >v8b.txt 2>v8berr.txt
    assert_eq "a second default run exits 6 too" "6" "$?"
    assert_eq "and prints byte-identical stdout" "same" \
        "$(cmp -s v8.txt v8b.txt && echo same || echo differs)"
    assert_eq "and byte-identical stderr" "same" \
        "$(cmp -s v8err.txt v8berr.txt && echo same || echo differs)"
    cleanup
}


# --- N-14/N-17/N-28/N-29/N-30/N-35/N-41: `resume` pass 1 and the dry-run -----
#
# T15 (pass 1; pass 2 lands in plan 17-07), T17 (the `resume_ambiguous`
# decision), T17b (nothing written before pass 2), T18 / T19 / T20 (three rows
# of contract 5.8's situation table seen from `resume`) and T33 (the write
# boundary: a dry-run leaves the repository byte-identical).
#
# Every interrupted state below is produced by the D-15 crash hook driving the
# REAL write protocol — never by hand-building a pending directory, because the
# thing under test is whether the tool can read back what the tool wrote.

# Every byte contract 5.8's write boundary promises a read-only path leaves
# alone: the ledger, every page, every file under `pending/`, and the git index.
resume_fingerprint() {
    local unit="$1"
    sha256_of_text "$(
        python3 - "$unit" <<'PY'
import hashlib, os, sys

unit = sys.argv[1]
rows = []
for root in (".crayon/units/%s" % unit, ".crayon/staging/%s" % unit, "docs"):
    for base, dirs, names in os.walk(root):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(base, name)
            with open(path, "rb") as handle:
                rows.append("%s %s" % (path, hashlib.sha256(handle.read()).hexdigest()))
print("\n".join(sorted(rows)))
PY
        git diff --cached --name-only
    )"
}

# A brand-new unit interrupted at `point` of its own opening transition.
crashed_unit_new() {
    local unit="$1" point="$2"
    CRAYON_CRASH_AT="$point" crayon_unit_new "$unit" "reference/${unit}.rst" >/dev/null 2>&1
    return 0
}

# The manifest's `files[]` order, which pass 1's report must follow exactly.
manifest_paths() {
    python3 -c '
import json, sys
print("\n".join(f["path"] for f in json.load(open(sys.argv[1]))["files"]))
' ".crayon/staging/$1/pending/manifest.json"
}

test_n14_t15_resume_pass_one_classifies_every_file() {
    setup_repo
    crashed_unit_new demo append
    assert_file_exists "the tail is on disk" ".crayon/units/demo/ledger.jsonl"

    # One file is put where the interrupted transition intended it, so the
    # report has to distinguish two classes rather than print one word twice.
    local first second
    first=$(manifest_paths demo | sed -n 1p)
    second=$(manifest_paths demo | sed -n 2p)
    mkdir -p "$(dirname "$first")"
    cp ".crayon/staging/demo/pending/after/$first" "$first"

    local out rc
    out=$("$CRAYON" resume demo --dry-run 2>err.txt)
    rc=$?
    assert_eq "a dry-run over an interrupted transition exits 0" "0" "$rc"
    assert_eq "stderr carries no refusal" "0" "$(wc -c <err.txt | tr -d ' ')"
    # One line per manifest file, in the manifest's own order, each beginning
    # with its class and naming its path.
    assert_eq "the first classification line" "done $first" \
        "$(printf '%s\n' "$out" | sed -n 1p)"
    assert_eq "the second classification line" "recoverable $second" \
        "$(printf '%s\n' "$out" | sed -n 2p)"
    assert_not_contains "a resumable report is not a refusal" "$out" "recovery_unsupported"
    cleanup
}

test_n29_t19_tail_is_a_byte_prefix() {
    setup_repo
    crashed_unit_new pre append

    # Every OTHER verb sees row 5 of the situation table and refuses, with the
    # hint that names this verb — the routing this plan makes true.
    "$CRAYON" steer pre --note "x" >/dev/null 2>err.txt
    assert_eq "another verb exits 6" "6" "$?"
    assert_json_error "uncommitted_tail" "err.txt" "uncommitted_tail"
    assert_file_contains "the hint names resume" "err.txt" "crayon resume pre"

    "$CRAYON" resume pre --dry-run >out.txt 2>err2.txt
    assert_eq "resume reports it as resumable instead of refusing" "0" "$?"
    assert_eq "stderr carries no refusal" "0" "$(wc -c <err2.txt | tr -d ' ')"

    # The other half of row 5: at most ONE truncated final line, itself a
    # byte-prefix of the next expected line. Truncating the ledger mid-line is
    # what an interrupted `write()` actually leaves behind.
    local size
    size=$(wc -c <".crayon/units/pre/ledger.jsonl" | tr -d ' ')
    python3 -c '
import sys
path, size = sys.argv[1], int(sys.argv[2])
with open(path, "r+b") as handle:
    handle.truncate(size - 30)
' ".crayon/units/pre/ledger.jsonl" "$size"
    "$CRAYON" resume pre --dry-run >out2.txt 2>err3.txt
    assert_eq "a truncated final line is still resumable" "0" "$?"
    assert_eq "stderr carries no refusal" "0" "$(wc -c <err3.txt | tr -d ' ')"
    cleanup
}

test_n28_t18_manifest_without_events() {
    setup_repo
    crayon_unit_new mwe "reference/mwe.rst" >/dev/null 2>&1
    CRAYON_CRASH_AT=manifest "$CRAYON" signoff mwe >/dev/null 2>&1
    assert_file_exists "the manifest is durable before the append" \
        ".crayon/staging/mwe/pending/manifest.json"

    local before out rc
    before=$(resume_fingerprint mwe)
    out=$("$CRAYON" resume mwe --dry-run 2>err.txt)
    rc=$?
    assert_eq "nothing to resume exits 3" "3" "$rc"
    assert_json_error "nothing_to_resume" "err.txt" "nothing_to_resume"
    assert_contains "the dry-run says what write mode would delete" "$out" \
        "would delete pending/: manifest_without_events"
    assert_file_exists "and deletes nothing" ".crayon/staging/mwe/pending/manifest.json"
    assert_eq "a dry-run is byte-identical" "$before" "$(resume_fingerprint mwe)"

    "$CRAYON" signoff mwe >/dev/null 2>&1
    assert_eq "the next write-mode verb proceeds" "0" "$?"
    assert_file_not_exists "and performs the cleanup" ".crayon/staging/mwe/pending"
    cleanup
}

test_n30_t20_committed_batch_awaiting_cleanup() {
    setup_repo
    crayon_unit_new cbc "reference/cbc.rst" >/dev/null 2>&1
    CRAYON_CRASH_AT=cleanup "$CRAYON" signoff cbc >/dev/null 2>&1
    assert_file_exists "pending/ survives the crash" ".crayon/staging/cbc/pending"
    assert_eq "the batch is committed" "crayon: signed-off cbc" "$(git log -1 --format=%s)"

    local before out
    before=$(resume_fingerprint cbc)
    out=$("$CRAYON" resume cbc --dry-run 2>err.txt)
    assert_eq "nothing to resume exits 3" "3" "$?"
    assert_json_error "nothing_to_resume" "err.txt" "nothing_to_resume"
    assert_contains "the dry-run names the situation" "$out" \
        "would delete pending/: committed_batch_awaiting_cleanup"
    assert_eq "a dry-run is byte-identical" "$before" "$(resume_fingerprint cbc)"

    "$CRAYON" steer cbc --note "onwards" >/dev/null 2>&1
    assert_eq "the next write-mode verb proceeds" "0" "$?"
    assert_file_not_exists "and performs the cleanup" ".crayon/staging/cbc/pending"
    cleanup
}

test_n17_t17_resume_ambiguous_writes_nothing() {
    setup_repo
    crashed_unit_new amb append
    local edited
    edited=$(manifest_paths amb | sed -n 1p)
    mkdir -p "$(dirname "$edited")"
    printf 'the author wrote this after the crash\n' >"$edited"

    local before out rc
    before=$(resume_fingerprint amb)
    out=$("$CRAYON" resume amb 2>err.txt)
    rc=$?
    assert_eq "an ambiguous decision exits 6" "6" "$rc"
    assert_json_error "resume_ambiguous" "err.txt" "resume_ambiguous"
    assert_contains "stdout carries the classification line" "$out" "unexpected $edited"
    # The diff is the whole point of the refusal: the author is asked to choose
    # between two byte strings, so both must be on screen.
    assert_contains "stdout carries the intended side's label" "$out" "intended:$edited"
    assert_contains "stdout carries the disk side's label" "$out" "disk:$edited"
    assert_contains "the diff lines are two-space indented" "$out" "  @@"
    assert_contains "the diff shows the author's bytes" "$out" \
        "+the author wrote this after the crash"

    # D-07: the refusal carries the same facts structurally.
    local files
    files=$(python3 -c '
import json, sys
payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
rows = payload.get("extra", payload).get("files") or payload.get("files")
print(";".join("%s=%s" % (r["path"], r["class"]) for r in rows))
' err.txt 2>/dev/null)
    assert_contains "extra.files names the path and its class" "$files" \
        "$edited=unexpected"

    assert_eq "nothing is written" "$before" "$(resume_fingerprint amb)"
    cleanup
}

test_n35_t17b_nothing_written_before_pass_two() {
    setup_repo
    crashed_unit_new b4 append

    # One file holds bytes the interrupted transition did not write, so the
    # decision REFUSES — and the refusal is the boundary this trace names: the
    # write half of the verb is reached only after the author has chosen.
    local edited before
    edited=$(manifest_paths b4 | sed -n 1p)
    mkdir -p "$(dirname "$edited")"
    printf 'the author wrote this after the crash\n' >"$edited"
    before=$(resume_fingerprint b4)

    local out rc
    out=$("$CRAYON" resume b4 2>err.txt)
    rc=$?
    assert_eq "the decision refuses" "6" "$rc"
    assert_eq "exactly one stderr line" "1" "$(wc -l <err.txt | tr -d ' ')"
    # Pass 1 ran before the decision: its report is the evidence that the
    # boundary this trace names is where the run actually stopped.
    assert_contains "pass 1 reported before the decision" "$out" "unexpected "
    assert_eq "nothing is written before the decision" "$before" \
        "$(resume_fingerprint b4)"

    "$CRAYON" resume b4 --dry-run >/dev/null 2>&1
    assert_eq "a dry-run stops one step earlier and writes nothing either" \
        "$before" "$(resume_fingerprint b4)"

    # And the author's decision is the ONE thing that unlocks the write.
    "$CRAYON" resume b4 --overwrite >/dev/null 2>&1
    rc=$?
    assert_eq "the decision is what unlocks pass 2" "0" "$rc"
    assert_file_not_exists "which consumed the pending directory" \
        ".crayon/staging/b4/pending"
    cleanup
}
test_n41_t33_dry_run_is_byte_identical() {
    setup_repo
    # One case per situation the table reaches from `resume`: resumable, a
    # manifest whose events never landed, and a committed batch awaiting
    # cleanup. Run TWICE, because a read-only path that writes once and is
    # idempotent afterwards still writes.
    crashed_unit_new r1 append

    crayon_unit_new r2 "reference/r2.rst" >/dev/null 2>&1
    CRAYON_CRASH_AT=manifest "$CRAYON" signoff r2 >/dev/null 2>&1

    crayon_unit_new r3 "reference/r3.rst" >/dev/null 2>&1
    CRAYON_CRASH_AT=cleanup "$CRAYON" signoff r3 >/dev/null 2>&1

    local unit before rc
    for unit in r1 r2 r3; do
        before=$(resume_fingerprint "$unit")
        "$CRAYON" resume "$unit" --dry-run >/dev/null 2>&1
        rc=$?
        # The classification result IS the exit code (contract 5.8): 0 for a
        # resumable unit, 3 for one whose pending/ is merely awaiting cleanup.
        assert_eq "$unit: the dry-run exits with its classification" \
            "$([ "$unit" = r1 ] && echo 0 || echo 3)" "$rc"
        assert_eq "$unit: the first dry-run writes nothing" "$before" \
            "$(resume_fingerprint "$unit")"
        "$CRAYON" resume "$unit" --dry-run >/dev/null 2>&1
        assert_eq "$unit: the second dry-run writes nothing" "$before" \
            "$(resume_fingerprint "$unit")"
        "$CRAYON" show "$unit" >/dev/null 2>&1
        assert_eq "$unit: show writes nothing" "$before" \
            "$(resume_fingerprint "$unit")"
        "$CRAYON" summary >/dev/null 2>&1
        assert_eq "$unit: summary writes nothing" "$before" \
            "$(resume_fingerprint "$unit")"
    done

    # A stray adopt directory is swept by the same boundary: reported by a
    # read-only path, deleted only by a write-mode one.
    mkdir -p .crayon/staging/r3/pending/adopt
    printf 'stray\n' >.crayon/staging/r3/pending/adopt/x
    before=$(resume_fingerprint r3)
    "$CRAYON" resume r3 --dry-run >/dev/null 2>&1
    assert_eq "a stray adopt tree survives a dry-run" "$before" \
        "$(resume_fingerprint r3)"
    cleanup
}

test_n41_nothing_to_resume() {
    setup_repo
    crayon_unit_new clean "reference/clean.rst" >/dev/null 2>&1
    local out rc
    out=$("$CRAYON" resume clean --dry-run 2>err.txt)
    rc=$?
    assert_eq "a clean unit exits 3" "3" "$rc"
    assert_json_error "nothing_to_resume" "err.txt" "nothing_to_resume"
    assert_not_contains "there is nothing to say would be deleted" "$out" \
        "would delete pending/"

    "$CRAYON" resume ghost --dry-run >/dev/null 2>ghost.txt
    assert_eq "an unknown unit exits 2" "2" "$?"
    assert_json_error "unit_not_found" "ghost.txt" "unit_not_found"
    cleanup
}

# --- N-13/N-14/N-42: T15's pass-2 half, T21 the pathspecs, T22 the index lock -
#
# Pass 1 made the interruption legible (plan 17-06); these are the write half.
# Every interrupted state is still produced by the D-15 crash hook driving the
# REAL write protocol, because the property under test is whether the tool can
# finish what the tool started.

# A file's raw-byte digest. `ledger_digest` above reads through a command
# substitution, which eats the trailing LF — and a truncated final line is
# exactly the byte a pass-2 assertion has to see.
file_sha() {
    python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$1"
}

# What the ledger of a unit whose batch starts at seq 0 must hold once pass 2
# has appended: the manifest's event lines, each followed by one LF, and
# nothing else. Only true for a batch that opens the record — every
# `crashed_unit_new` unit below is one.
batch_digest() {
    python3 -c '
import hashlib, json, sys
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
payload = "".join(line + "\n" for line in manifest["events"])
print(hashlib.sha256(payload.encode("utf-8")).hexdigest())
' ".crayon/staging/$1/pending/manifest.json"
}

file_mtime() {
    python3 -c '
import os, sys
print(os.stat(sys.argv[1]).st_mtime_ns)
' "$1"
}

# The token `show` routes to, which is the one observable that says whether the
# recovered unit landed in the state the uninterrupted verb would have left.
routed_next() {
    "$CRAYON" show "$1" 2>/dev/null | sed -n 's/.*Next: //p' | tail -1
}

test_n14_t15_resume_completes_pass_two() {
    setup_repo
    crashed_unit_new demo append

    local first second intended expected_ledger mtime_before
    first=$(manifest_paths demo | sed -n 1p)
    second=$(manifest_paths demo | sed -n 2p)
    # One file already holds the intended bytes — `done` — so this run has to
    # place exactly one of the two.
    mkdir -p "$(dirname "$first")"
    cp ".crayon/staging/demo/pending/after/$first" "$first"
    mtime_before=$(file_mtime "$first")
    intended=$(file_sha ".crayon/staging/demo/pending/after/$second")
    expected_ledger=$(batch_digest demo)

    local rc
    "$CRAYON" resume demo >out.txt 2>err.txt
    rc=$?
    assert_eq "pass 2 completes the interrupted transition" "0" "$rc"
    # stderr carries the git diagnostic every committed transition prints, and
    # no refusal — GATE-04's one JSON line is reserved for a non-zero exit.
    assert_not_contains "stderr carries no refusal" "$(cat err.txt)" '"error"'
    assert_file_exists "the unplaced file is placed" "$second"
    assert_eq "and holds the intended bytes" "$intended" "$(file_sha "$second")"
    # A `done` file already holds the intended bytes; re-placing it would move
    # its mtime for no reason at all.
    assert_eq "a done file is not re-placed" "$mtime_before" "$(file_mtime "$first")"
    assert_eq "the ledger holds exactly the batch" "$expected_ledger" \
        "$(file_sha .crayon/units/demo/ledger.jsonl)"
    assert_file_not_exists "the pending directory is gone" \
        ".crayon/staging/demo/pending"

    # `show` re-runs stage a, which verifies the chain and refuses
    # `ledger_corrupt` on a broken one — so an exit 0 here IS the chain check.
    "$CRAYON" show demo >show.txt 2>show-err.txt
    rc=$?
    assert_eq "show reads the recovered record" "0" "$rc"

    # And it routes exactly where an uninterrupted transition would have left
    # the unit: same verb, same arguments, no crash.
    crayon_unit_new ref "reference/demo.rst" >/dev/null 2>&1
    assert_eq "the recovered unit routes as an uninterrupted one does" \
        "$(routed_next ref)" "$(routed_next demo)"
    cleanup
}

test_n13_t21_pass_two_commits_with_manifest_pathspecs() {
    setup_repo
    crashed_unit_new paths append

    # The working tree during a recovery holds whatever the interruption left
    # behind — and whatever the author was doing at the time. A sweeping add
    # would commit it in the author's name, under the tool's trailers.
    printf 'unrelated work\n' >docs/unrelated.md
    git add docs/unrelated.md

    local expected
    expected=$( { manifest_paths paths; printf '%s\n' ".crayon/units/paths/ledger.jsonl"; } | sort)

    local rc
    "$CRAYON" resume paths >/dev/null 2>err.txt
    rc=$?
    assert_eq "pass 2 completes" "0" "$rc"

    local shown
    shown=$(git show --name-only --format= HEAD | grep -v '^$' | sort)
    assert_eq "the commit lists exactly the manifest's paths and the ledger" \
        "$expected" "$shown"
    assert_not_contains "the unrelated file is not swept in" "$shown" \
        "docs/unrelated.md"
    assert_file_exists "and it is still on disk, unrecorded" "docs/unrelated.md"

    local body
    body=$(git log -1 --format=%B)
    assert_eq "the subject names the recovered phase" "crayon: declared paths" \
        "$(git log -1 --format=%s)"
    assert_contains "the commit carries Crayon-Unit" "$body" "Crayon-Unit: paths"
    assert_contains "the commit carries Crayon-Phase" "$body" "Crayon-Phase: declared"
    assert_contains "the commit carries the recovered seq range" "$body" \
        "Crayon-Seq: 0-1"
    assert_contains "the commit carries Crayon-Head" "$body" "Crayon-Head: "
    cleanup
}

test_n14_partial_line_is_truncated() {
    setup_repo
    crashed_unit_new part append

    local expected size
    expected=$(batch_digest part)
    size=$(wc -c <".crayon/units/part/ledger.jsonl" | tr -d ' ')
    # What an interrupted `write()` actually leaves: a half-written final line.
    python3 -c '
import sys
path, size = sys.argv[1], int(sys.argv[2])
with open(path, "r+b") as handle:
    handle.truncate(size - 30)
' ".crayon/units/part/ledger.jsonl" "$size"

    local rc
    "$CRAYON" resume part >/dev/null 2>err.txt
    rc=$?
    assert_eq "pass 2 completes from a truncated final line" "0" "$rc"
    # Byte for byte the batch: no duplicated line and no half-written one.
    assert_eq "the ledger holds exactly the batch, once" "$expected" \
        "$(file_sha .crayon/units/part/ledger.jsonl)"
    assert_eq "the line count is the batch's own" "2" \
        "$(wc -l <.crayon/units/part/ledger.jsonl | tr -d ' ')"
    cleanup
}

test_n14_overwrite_discards_author_bytes() {
    setup_repo
    crashed_unit_new ow append

    local edited intended
    edited=$(manifest_paths ow | sed -n 1p)
    mkdir -p "$(dirname "$edited")"
    printf 'the author wrote this after the crash\n' >"$edited"
    intended=$(file_sha ".crayon/staging/ow/pending/after/$edited")

    local rc
    "$CRAYON" resume ow >/dev/null 2>err.txt
    rc=$?
    assert_eq "without the flag the same state exits 6" "6" "$rc"
    assert_json_error "resume_ambiguous" "err.txt" "resume_ambiguous"

    "$CRAYON" resume ow --overwrite >/dev/null 2>err2.txt
    rc=$?
    assert_eq "--overwrite completes the transition" "0" "$rc"
    assert_eq "the page holds the intended bytes" "$intended" \
        "$(file_sha "$edited")"
    assert_file_not_exists "the pending directory is gone" \
        ".crayon/staging/ow/pending"
    cleanup
}

test_n14_empty_manifest_commits_the_ledger_alone() {
    setup_repo
    crayon_unit_new emp "reference/emp.rst" >/dev/null 2>&1
    "$CRAYON" signoff emp >/dev/null 2>&1
    # `steer` writes no file at all: its only destination is the ledger, so its
    # manifest names zero files — the §5.8 empty edge, reached by a real verb.
    CRAYON_CRASH_AT=append "$CRAYON" steer emp --note "onwards" >/dev/null 2>&1
    assert_eq "the crash after the append is a hard exit" "137" "$?"
    assert_eq "the manifest names zero files" "0" \
        "$(python3 -c '
import json, sys
print(len(json.load(open(sys.argv[1], encoding="utf-8"))["files"]))
' .crayon/staging/emp/pending/manifest.json)"

    local rc
    "$CRAYON" resume emp >/dev/null 2>err.txt
    rc=$?
    assert_eq "a zero-file manifest completes by appending and committing" "0" "$rc"
    assert_eq "the commit lists the ledger alone" \
        ".crayon/units/emp/ledger.jsonl" \
        "$(git show --name-only --format= HEAD | grep -v '^$')"
    assert_eq "the subject names the steer it completed" "crayon: steered emp" \
        "$(git log -1 --format=%s)"
    assert_file_not_exists "the pending directory is gone" \
        ".crayon/staging/emp/pending"
    cleanup
}

test_n42_t22_index_lock_refuses() {
    setup_repo
    crashed_unit_new lk append

    local before rc
    before=$(resume_fingerprint lk)
    : >.git/index.lock
    "$CRAYON" resume lk >/dev/null 2>err.txt
    rc=$?
    assert_eq "a present index lock exits 5" "5" "$rc"
    assert_json_error "git_busy" "err.txt" "git_busy"
    assert_file_exists "crayon never deletes the lock it found" ".git/index.lock"
    assert_eq "and writes nothing at all" "$before" "$(resume_fingerprint lk)"

    rm -f .git/index.lock
    "$CRAYON" resume lk >/dev/null 2>err2.txt
    rc=$?
    assert_eq "the recovery completes once the lock is gone" "0" "$rc"
    cleanup
}

# --- N-15/N-29: T16 the adopt path, T19b the refusal it is not allowed on ----
#
# Contract 5.8's first hook shape: a hook rewrites a target and REJECTS the
# commit, so the transition ends interrupted with the hook's bytes on disk. The
# author's two answers are `--overwrite` (discard) and `--adopt` (keep, recorded
# as a reviewer EDIT naming the hook — a formatter is not a reviewer).

#: The fixed suffix contract 5.8 appends to the author's own words.
ADOPT_SUFFIX="(bytes changed outside crayon after recording; retained by the author)"

# A two-target drafted unit whose pre-commit hook rewrote ONE target and
# rejected the commit. Two targets, because the reviewer edit's `files[]` has
# to be the COMPLETE batch file set — with one file "complete" and "only the
# changed path" are the same list and the assertion proves nothing.
hook_rejected_draft() {
    local unit="$1"
    crayon_unit_new "$unit" "reference/${unit}-a.rst" \
        --also-target "reference/${unit}-b.rst" >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
    stage_draft "$unit" "reference/${unit}-a.rst" "A\n=\n\nBody a.\n"
    stage_draft "$unit" "reference/${unit}-b.rst" "B\n=\n\nBody b.\n"
    install_rewrite_and_reject_hook "docs/reference/${unit}-a.rst"
    "$CRAYON" draft "$unit" ".crayon/staging/${unit}/draft" >/dev/null 2>&1
    rm -f .git/hooks/pre-commit
    return 0
}

# An interrupted `unit edit --re-sign`: its batch's last event is a signoff, so
# it is exactly the state `--adopt` is NOT allowed on.
hook_rejected_resign() {
    local unit="$1"
    crayon_unit_new "$unit" "reference/${unit}.rst" >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
    install_rewrite_and_reject_hook ".crayon/units/${unit}/unit.md"
    "$CRAYON" unit edit "$unit" --audience "An amended audience" --re-sign \
        >/dev/null 2>&1
    rm -f .git/hooks/pre-commit
    return 0
}

ledger_lines() {
    wc -l <".crayon/units/$1/ledger.jsonl" | tr -d ' '
}

# One JSON object's `files[]`, read two ways: its length, and one path's digest.
event_file_count() {
    printf '%s' "$1" | python3 -c '
import json, sys
print(len(json.load(sys.stdin)["files"]))
'
}

event_file_sha() {
    printf '%s' "$1" | python3 -c '
import json, sys
rows = {row["path"]: row["sha256"] for row in json.load(sys.stdin)["files"]}
print(rows.get(sys.argv[1], "MISSING"))
' "$2"
}

# The pending manifest as the TOOL's own reader sees it — the single place an
# absolute path or a parent-directory segment is rejected (Pitfall 8).
manifest_through_read_manifest() {
    python3 -c '
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
manifest = module.read_manifest(os.getcwd(), sys.argv[2])
print("REJECTED" if manifest is None else json.dumps(manifest, sort_keys=True))
' "$CRAYON" "$1"
}

test_n15_t16_hook_rewrites_and_rejects() {
    setup_repo
    hook_rejected_draft hr

    local page=docs/reference/hr-a.rst other=docs/reference/hr-b.rst
    # The basis vocabulary, which is NOT the manifest's. A manifest entry names
    # a repo-relative path; every basis event — signoff `targets[]`, generation
    # `files[]`, reviewer-edit `files[]` — names a docs-root-relative target,
    # and V13 compares the two sets directly (CR-01).
    local page_basis=reference/hr-a.rst other_basis=reference/hr-b.rst
    assert_file_contains "the hook's bytes are on disk" "$page" "HOOKFORMATTED"

    local rc
    "$CRAYON" resume hr >/dev/null 2>err.txt
    rc=$?
    assert_eq "with no flag the interruption is ambiguous" "6" "$rc"
    assert_json_error "resume_ambiguous" "err.txt" "resume_ambiguous"

    local hook_sha other_sha lines_before batch_files
    hook_sha=$(file_sha "$page")
    other_sha=$(file_sha ".crayon/staging/hr/pending/after/$other")
    lines_before=$(ledger_lines hr)
    batch_files=$(manifest_paths hr | wc -l | tr -d ' ')

    "$CRAYON" resume hr --adopt --note "kept the formatter's output" \
        >/dev/null 2>err2.txt
    rc=$?
    assert_eq "--adopt completes the transition" "0" "$rc"
    assert_eq "the author keeps the hook's bytes" "$hook_sha" "$(file_sha "$page")"
    assert_eq "the untouched target is still placed" "$other_sha" \
        "$(file_sha "$other")"
    assert_eq "exactly one event is appended" "$((lines_before + 1))" \
        "$(ledger_lines hr)"

    local last
    last=$(tail -1 .crayon/units/hr/ledger.jsonl)
    assert_eq "it is a reviewer edit, not a review" "reviewer-edit" \
        "$(printf '%s' "$last" | json_field kind)"
    assert_eq "the hook flag is set" "True" "$(printf '%s' "$last" | json_field hook)"
    # A formatter is not a reviewer: no verdict is recorded, ever.
    assert_not_contains "no verdict is recorded" "$last" '"verdict"'
    assert_eq "files[] is the COMPLETE batch file set" "$batch_files" \
        "$(event_file_count "$last")"
    assert_eq "the adopted path carries its CURRENT digest" "$hook_sha" \
        "$(event_file_sha "$last" "$page_basis")"
    assert_eq "the unchanged path carries its RECORDED digest" "$other_sha" \
        "$(event_file_sha "$last" "$other_basis")"
    # CR-01: the two path forms are not interchangeable — pin that the
    # repo-relative form is ABSENT, or a regression that reintroduces it would
    # only have to also keep the docs-relative one to pass the two above.
    assert_eq "the repo-relative form is not what is recorded" "MISSING" \
        "$(event_file_sha "$last" "$page")"

    local note
    note=$(printf '%s' "$last" | json_field note)
    assert_contains "the note carries the author's words" "$note" \
        "kept the formatter's output"
    assert_contains "and the contract's fixed suffix" "$note" "$ADOPT_SUFFIX"

    assert_file_not_exists "the pending directory is gone" \
        ".crayon/staging/hr/pending"
    "$CRAYON" show hr >/dev/null 2>&1
    rc=$?
    assert_eq "the recovered record reads back" "0" "$rc"

    # CR-01: the escape must leave a record the tool still accepts. `verify`
    # runs V13 over the appended reviewer edit, and `review --verdict accept`
    # proves the derived state still sees the signed targets in the basis.
    # Without them an `--adopt` that writes the wrong path vocabulary exits 0,
    # bricks the unit `ledger_corrupt`, and every assertion above still passes.
    "$CRAYON" verify hr >/dev/null 2>verify-err.txt
    rc=$?
    assert_eq "the record is intact after the escape" "0" "$rc"
    assert_eq "verify prints no refusal" "0" "$(grep -c '"error"' verify-err.txt)"

    "$CRAYON" review hr --verdict accept >/dev/null 2>accept-err.txt
    rc=$?
    assert_eq "a verb still routes after the escape" "0" "$rc"
    assert_not_contains "and does not refuse target_missing" \
        "$(cat accept-err.txt)" "target_missing"
    cleanup
}

# WR-03: `--adopt` twice on ONE batch. The second call satisfies every
# condition the three routing rows and both SKILL.md steps published — the last
# event is a reviewer edit, something rewrote the placed bytes, the bytes are on
# disk — and the tool still degrades to a plain resume, because `resume_adopt`
# applies a FOURTH condition: the last event must not itself be an adoption. It
# used to do that above `read_note`, so the author's second note was never even
# read, let alone recorded, and the only signal was silence.
test_wr03_a_second_adopt_on_one_batch_records_nothing_and_says_so() {
    setup_repo
    crayon_unit_new dd reference/dd.rst >/dev/null 2>&1
    "$CRAYON" signoff dd >/dev/null 2>&1
    stage_draft dd reference/dd.rst 'D\n=\n\nBody.\n'
    install_appending_reject_hook docs/reference/dd.rst
    "$CRAYON" draft dd "$(draft_path dd reference/dd.rst)" >/dev/null 2>&1

    local rc
    "$CRAYON" resume dd --adopt --note "kept the first formatter output" \
        >/dev/null 2>adopt1.txt
    rc=$?
    assert_eq "the first adopt is blocked by the still-live hook" "6" "$rc"

    # The hook is gone, so nothing is refusing the transition any more — but it
    # rewrote the page once more on its way out, so the batch still classifies
    # `unexpected` and still reads as adoptable on every published surface.
    rm -f .git/hooks/pre-commit
    local lines_before last_before
    lines_before=$(ledger_lines dd)
    last_before=$(tail -1 .crayon/units/dd/ledger.jsonl)
    assert_eq "the batch's last event IS an adoption" "True" \
        "$(printf '%s' "$last_before" | json_field hook)"

    "$CRAYON" resume dd --adopt --note "kept the second formatter output" \
        >/dev/null 2>adopt2.txt
    rc=$?
    assert_eq "the second adopt completes the batch" "0" "$rc"
    assert_eq "and appends no event" "$lines_before" "$(ledger_lines dd)"
    assert_eq "the recorded note is still the first one" \
        "$(printf '%s' "$last_before" | json_field note)" \
        "$(tail -1 .crayon/units/dd/ledger.jsonl | json_field note)"

    # The whole finding: the author is told, rather than left to diff the
    # ledger against what they typed.
    assert_file_contains "the dropped note is reported, not swallowed" \
        adopt2.txt "--note was not recorded"
    assert_file_contains "and the reason names the fourth condition" \
        adopt2.txt "already an adoption"
    assert_file_contains "the divergent record is reported" adopt2.txt "leaves dd drifted"
    assert_file_contains "the remedy records the current bytes" adopt2.txt "crayon edits dd --note"
    assert_not_contains "no new hook is blamed" "$(cat adopt2.txt)" "hook changed"
    assert_file_contains "unchanged carried drift is reported neutrally" adopt2.txt \
        "docs/reference/dd.rst still differs from the recorded bytes after resume"
    "$CRAYON" verify dd >verify.txt 2>&1
    assert_eq "the record is still readable after repeated --adopt" "0" "$?"
    assert_file_contains "verify reports the drift" verify.txt "drifted"
    assert_eq "the next action records the edits" "record_edits" "$(derived dd next)"
    "$CRAYON" edits dd --note "kept the second formatter output" >/dev/null 2>&1
    assert_eq "the diagnostic's remedy succeeds" "0" "$?"
    "$CRAYON" verify dd >verify-fixed.txt 2>&1
    assert_eq "the repaired record verifies" "0" "$?"
    assert_not_contains "the edit clears the drift" "$(cat verify-fixed.txt)" "drifted"
    cleanup
}

setup_twice_rejected_adoption() {
    setup_repo
    crayon_unit_new dd reference/dd.rst >/dev/null 2>&1
    "$CRAYON" signoff dd >/dev/null 2>&1
    stage_draft dd reference/dd.rst 'D\n=\n\nBody.\n'
    install_appending_reject_hook docs/reference/dd.rst
    "$CRAYON" draft dd "$(draft_path dd reference/dd.rst)" >/dev/null 2>&1
    assert_eq "the draft is rejected" "6" "$?"
    "$CRAYON" resume dd --adopt --note "first" >/dev/null 2>&1
    assert_eq "the first adoption is rejected" "6" "$?"
}

test_wr01_repeated_adoption_refusal_is_one_json_line() {
    setup_twice_rejected_adoption
    local mode rc output
    local -a flags
    for mode in no-note note json; do
        flags=()
        output=err.txt
        [ "$mode" = note ] && flags=(--note "second")
        if [ "$mode" = json ]; then
            flags=(--note "second" --json)
            output=out.txt
        fi
        "$CRAYON" resume dd --adopt "${flags[@]}" >out.txt 2>err.txt
        rc=$?
        assert_eq "$mode: the hook still rejects the transition" "6" "$rc"
        assert_eq "$mode: the refusal occupies exactly one line" "1" "$(wc -l <"$output")"
        assert_json_error "$mode: the whole stream is a JSON refusal" "$output" recovery_unsupported
        assert_eq "$mode: the detail names the rejected commit" commit_rejected "$(json_field detail <"$output")"
        assert_not_contains "$mode: no uncommitted outcome is announced" "$(cat out.txt err.txt)" "leaves dd drifted"
        if [ "$mode" != no-note ]; then
            assert_contains "$mode: the unused note is in the structured payload" \
                "$(json_field notices <"$output")" "--note was not recorded"
        fi
    done
    # WR-04 (iteration 9): the SUCCESS document too. `--json` is consumed by
    # the three skills, and until now the dropped note reached them only as
    # stderr prose while the refusal arm above carried it as data — which is
    # "the only signal was silence" (iteration-7 WR-03) re-opened for the
    # machine surface. Same batch, same flags, with the blocker removed.
    local notices
    rm -f .git/hooks/pre-commit
    "$CRAYON" resume dd --adopt --note "second" --json >out.txt 2>err.txt
    assert_eq "success: the batch completes once the hook is gone" "0" "$?"
    assert_eq "success: the document is exactly one line" "1" "$(wc -l <out.txt)"
    assert_eq "success: and it is a success document" "True" "$(json_field ok <out.txt)"
    notices=$(json_field notices <out.txt)
    assert_contains "success: the dropped note is machine-readable" \
        "$notices" "--note was not recorded"
    assert_contains "success: so is the retained divergence" \
        "$notices" "leaves dd drifted"
    assert_not_contains "success: the notices are not the string null" "$notices" "null"
    assert_file_contains "success: and they are still said on stderr" err.txt \
        "--note was not recorded"
    cleanup
}

test_wr01_restoring_hook_clears_drift_before_the_notice() {
    setup_twice_rejected_adoption
    local lines_before
    lines_before=$(ledger_lines dd)
    cat >.git/hooks/pre-commit <<'HOOK'
#!/bin/sh
cp .crayon/staging/dd/pending/adopt/docs/reference/dd.rst docs/reference/dd.rst
git add -- docs/reference/dd.rst
HOOK
    # Phase-17 IN-02: this write passed only while `setup_twice_rejected_adoption`
    # happened to have left the file executable. A hook git cannot run is a hook
    # that is not installed, and every assert_not_contains below would then pass
    # for the wrong reason.
    chmod +x .git/hooks/pre-commit
    "$CRAYON" resume dd --adopt >out.txt 2>err.txt
    assert_eq "a restoring hook completes the batch" "0" "$?"
    assert_eq "no second adoption was appended" "$lines_before" "$(ledger_lines dd)"
    assert_file_contains "the final response routes to review" out.txt "Next: review"
    assert_eq "the final bytes are current" "false" "$(derived dd page_drift)"
    assert_not_contains "no stale drift notice" "$(cat err.txt)" "leaves dd drifted"
    assert_not_contains "no unnecessary edits remedy" "$(cat err.txt)" "crayon edits dd"
    assert_not_contains "no mismatch warning after restoration" "$(cat err.txt)" "hook changed"
    "$CRAYON" edits dd --note "nothing changed" >/dev/null 2>edits.txt
    assert_eq "edits confirms there is nothing to record" "3" "$?"
    assert_json_error "the no-op is no_edits" edits.txt no_edits
    cleanup
}

test_wr02_already_adopted_batch_requires_an_explicit_choice() {
    local choice lines_before page_before ledger_before saved_sha bare_hint
    for choice in --adopt --overwrite; do
        setup_twice_rejected_adoption
        rm -f .git/hooks/pre-commit
        lines_before=$(ledger_lines dd)
        page_before=$(sha256_of_file docs/reference/dd.rst)
        ledger_before=$(sha256_of_file .crayon/units/dd/ledger.jsonl)
        saved_sha=$(sha256_of_file .crayon/staging/dd/pending/adopt/docs/reference/dd.rst)
        "$CRAYON" resume dd >bare-out.txt 2>bare-err.txt
        assert_eq "$choice: bare resume refuses unexpected files" "6" "$?"
        assert_json_error "$choice: the refusal is resume_ambiguous" bare-err.txt resume_ambiguous
        assert_eq "$choice: bare resume leaves the page intact" "$page_before" "$(sha256_of_file docs/reference/dd.rst)"
        assert_eq "$choice: bare resume leaves the ledger intact" "$ledger_before" "$(sha256_of_file .crayon/units/dd/ledger.jsonl)"
        # WR-01 (iteration 9): the hint the routing row tells the skill to
        # relay verbatim has to describe THIS batch. Offering `--note` here
        # names a reviewer edit that is never written and a note that is
        # dropped on arrival — the iteration-7 WR-03 defect, re-stated by the
        # tool after the docs had been corrected.
        bare_hint=$(json_field hint <bare-err.txt)
        assert_not_contains "$choice: the already-adopted refusal offers no note" \
            "$bare_hint" "--note"
        assert_contains "$choice: it names the seq that already adopted" \
            "$bare_hint" "already an adoption"
        assert_contains "$choice: repeated adopt is the retain path" \
            "$bare_hint" "crayon resume dd --adopt retains the bytes on disk"
        assert_contains "$choice: overwrite restores the saved bytes, not a discard" \
            "$bare_hint" "crayon resume dd --overwrite restores the bytes that adoption saved"
        assert_not_contains "$choice: and it is not called a plain resume" \
            "${bare_hint#*already carrying one adoption}" "plain resume"
        # These are the literal commands the routing row offers for this batch.
        if [ "$choice" = --adopt ]; then
            "$CRAYON" resume dd --adopt >chosen-out.txt 2>chosen-err.txt
        else
            "$CRAYON" resume dd --overwrite >chosen-out.txt 2>chosen-err.txt
        fi
        assert_eq "$choice: the documented command completes" "0" "$?"
        assert_eq "$choice: no event is appended" "$lines_before" "$(ledger_lines dd)"
        assert_eq "$choice: the existing adoption note stands" "$ledger_before" "$(sha256_of_file .crayon/units/dd/ledger.jsonl)"
        if [ "$choice" = --adopt ]; then
            assert_eq "repeated adopt retains the divergent bytes" "$page_before" "$(sha256_of_file docs/reference/dd.rst)"
            assert_file_contains "retained divergence routes to edits" chosen-out.txt "Next: record_edits"
            "$CRAYON" edits dd --note "retained bytes after recovery" >/dev/null 2>&1
            assert_eq "the documented follow-up records the bytes" "0" "$?"
        else
            assert_eq "overwrite restores the saved adoption bytes" "$saved_sha" "$(sha256_of_file docs/reference/dd.rst)"
            assert_file_contains "restored bytes route to review" chosen-out.txt "Next: review"
        fi
        cleanup
    done
}

test_wr05_new_hook_rewrite_on_carried_drift_is_reported() {
    local mode ledger_before before_sha fresh_sha
    for mode in both disk-only head-only; do
        setup_twice_rejected_adoption
        ledger_before=$(sha256_of_file .crayon/units/dd/ledger.jsonl)
        cp docs/reference/dd.rst .crayon/staging/dd/snapshot.rst
        before_sha=$(sha256_of_file .crayon/staging/dd/snapshot.rst)
        printf 'THIRD FORMAT\n' >fresh.txt
        fresh_sha=$(sha256_of_file fresh.txt)
        assert_not_eq "$mode: the new bytes really differ" "$before_sha" "$fresh_sha"
        rm -f .git/hooks/pre-commit
        if [ "$mode" != disk-only ]; then
            cat >.git/hooks/pre-commit <<'HOOK'
#!/bin/sh
printf 'THIRD FORMAT\n' >docs/reference/dd.rst
git add -- docs/reference/dd.rst
HOOK
            chmod +x .git/hooks/pre-commit
        fi
        if [ "$mode" = disk-only ]; then
            cat >.git/hooks/post-commit <<'HOOK'
#!/bin/sh
printf 'THIRD FORMAT\n' >docs/reference/dd.rst
HOOK
            chmod +x .git/hooks/post-commit
        elif [ "$mode" = head-only ]; then
            cat >.git/hooks/post-commit <<'HOOK'
#!/bin/sh
cp .crayon/staging/dd/snapshot.rst docs/reference/dd.rst
HOOK
            chmod +x .git/hooks/post-commit
        fi
        "$CRAYON" resume dd --adopt >out.txt 2>err.txt
        assert_eq "$mode: the rewriting hook completes" "0" "$?"
        assert_eq "$mode: recovery appends no second adoption" "$ledger_before" \
            "$(sha256_of_file .crayon/units/dd/ledger.jsonl)"
        git show HEAD:docs/reference/dd.rst >committed.txt
        if [ "$mode" = disk-only ]; then
            assert_eq "HEAD retains the pre-resume bytes" "$before_sha" "$(sha256_of_file committed.txt)"
        else
            assert_eq "$mode: HEAD contains the fresh rewrite" "$fresh_sha" "$(sha256_of_file committed.txt)"
        fi
        if [ "$mode" = head-only ]; then
            assert_eq "disk retains the pre-resume bytes" "$before_sha" "$(sha256_of_file docs/reference/dd.rst)"
        else
            assert_eq "$mode: disk contains the fresh rewrite" "$fresh_sha" "$(sha256_of_file docs/reference/dd.rst)"
        fi
        assert_file_contains "$mode: the new hook change is attributed" err.txt \
            "hook changed docs/reference/dd.rst after recording"
        assert_not_contains "$mode: it is not just carried drift" "$(cat err.txt)" \
            "still differs from the recorded bytes after resume"
        assert_file_contains "$mode: final divergence routes to edits" out.txt "Next: record_edits"
        cleanup
    done
}

# CR-01 (iteration 9): a transition that COMMITTED must report itself, even
# when re-deriving state afterwards is impossible. The post-commit hook below
# replaces `docs` with a symlink pointing outside the repository — an ordinary
# committed blob of mode 120000, and precisely the threat `contained_page`
# refuses `bad_write_path` for. The commit has already landed by the time that
# refusal becomes possible, so contract 5.7 step 5 requires exit 0, the one
# success line, and a routed `Next:` — degraded to `show`, with the reason said
# on stderr, not a non-zero refusal that hides the landed commit from the caller.
test_cr01_a_committed_resume_reports_itself_when_derivation_fails() {
    local mode outside rc committed
    for mode in plain json; do
        setup_repo
        outside=$(mktemp -d) || exit 1
        crayon_unit_new dz reference/dz.rst >/dev/null 2>&1
        "$CRAYON" signoff dz >/dev/null 2>&1
        stage_draft dz reference/dz.rst 'Z\n=\n\nBody.\n'
        install_appending_reject_hook docs/reference/dz.rst
        "$CRAYON" draft dz "$(draft_path dz reference/dz.rst)" >/dev/null 2>&1
        assert_eq "$mode: the rejecting hook fails the draft" "6" "$?"
        rm -f .git/hooks/pre-commit
        cat >.git/hooks/post-commit <<HOOK
#!/bin/sh
cp -r docs '${outside}/docs'
rm -rf docs
ln -s '${outside}/docs' docs
HOOK
        chmod +x .git/hooks/post-commit

        if [ "$mode" = json ]; then
            "$CRAYON" resume dz --overwrite --json >out.txt 2>err.txt
        else
            "$CRAYON" resume dz --overwrite >out.txt 2>err.txt
        fi
        rc=$?
        # Restore a real `docs` BEFORE asserting, so an assertion that aborts
        # the body cannot leave the fixture wedged for `cleanup`.
        rm -f docs && cp -r "${outside}/docs" docs
        rm -f .git/hooks/post-commit
        committed=$(git log --oneline -1)
        rm -rf "$outside"

        assert_eq "$mode: state derivation really did fail" "1" \
            "$(grep -c 'bad_write_path\|could not be re-derived' err.txt)"
        assert_eq "$mode: a committed transition exits 0" "0" "$rc"
        assert_contains "$mode: and the commit really landed" "$committed" "crayon: drafted dz"
        assert_file_contains "$mode: the success line names the batch" out.txt "resumed dz"
        assert_not_contains "$mode: stdout carries no refusal" "$(cat out.txt)" '"error"'
        assert_file_contains "$mode: the reason is said on stderr" err.txt \
            "state could not be re-derived after the commit"
        assert_file_contains "$mode: and the transition is affirmed" err.txt \
            "the transition stands"
        if [ "$mode" = json ]; then
            assert_eq "$mode: the success document is exactly one line" "1" "$(wc -l <out.txt)"
            assert_eq "$mode: ok is true" "True" "$(json_field ok <out.txt)"
            assert_eq "$mode: next is the fallback token" "show" "$(json_field next <out.txt)"
        else
            assert_file_contains "$mode: the route degrades to show, never to nothing" \
                out.txt "Next: show"
        fi
        cleanup
    done
}

# WR-03: and the surfaces that route the author here say the same thing the
# code does. Read off the tool rather than restated, so a reworded constant
# cannot drift from the rows that mirror it.
test_wr03_every_adopt_offer_names_the_fourth_condition() {
    setup_repo
    crayon_unit_new dq reference/dq.rst >/dev/null 2>&1
    "$CRAYON" signoff dq >/dev/null 2>&1
    stage_draft dq reference/dq.rst 'Q\n=\n\nBody.\n'
    install_rewrite_and_reject_hook docs/reference/dq.rst
    "$CRAYON" draft dq "$(draft_path dq reference/dq.rst)" >/dev/null 2>&1
    rm -f .git/hooks/pre-commit

    "$CRAYON" resume dq >/dev/null 2>amb.txt
    assert_eq "an ambiguous resume refuses" "6" "$?"
    assert_json_error "it is resume_ambiguous" "amb.txt" "resume_ambiguous"
    local hint
    hint=$(json_field hint <amb.txt)
    assert_contains "the printed offer states the fourth condition" "$hint" \
        "NOT ITSELF AN ADOPTION"
    cleanup
}

# WR-10: `stage_rejected` end to end. Until now the only executable coverage
# called `refuse_transition` directly, so nothing proved the arm was reachable
# through `write_tail` and nothing would have noticed if `git add`'s failure
# stopped reaching it. A read-only object database is the real shape: `git add`
# cannot write the blob, while `git add --dry-run` — which `guard_ignored_paths`
# runs first — still succeeds, so the run gets past the write guard and fails
# where the transition actually happens.
test_wr10_a_read_only_object_database_is_stage_rejected() {
    setup_repo
    crayon_unit_new sr reference/sr.rst >/dev/null 2>&1
    "$CRAYON" signoff sr >/dev/null 2>&1
    stage_draft sr reference/sr.rst 'S\n=\n\nBody.\n'

    local rc first second
    chmod a-w .git/objects
    "$CRAYON" draft sr "$(draft_path sr reference/sr.rst)" >/dev/null 2>first.txt
    first=$?
    "$CRAYON" resume sr >/dev/null 2>second.txt
    second=$?
    # Restore BEFORE asserting: an assertion that aborts the body would
    # otherwise leave an unwritable object database behind.
    chmod u+w .git/objects

    assert_eq "the first git add failure offers one retry" "6" "$first"
    assert_json_error "and it is uncommitted_tail" "first.txt" "uncommitted_tail"

    assert_eq "the second failure on the same batch refuses" "6" "$second"
    assert_json_error "as recovery_unsupported" "second.txt" "recovery_unsupported"
    assert_eq "with detail stage_rejected, not commit_rejected" "stage_rejected" \
        "$(json_field detail <second.txt)"
    assert_eq "and the step that failed is named" "git add" \
        "$(json_field step <second.txt)"

    # WR-06's witness: this is the arm whose hint used to say a hook rewrote
    # the placed bytes in the same breath as saying no hook ran.
    local hint
    hint=$(json_field hint <second.txt)
    assert_contains "the hint names the index, not commit hooks" "$hint" \
        "\`git status\` and the index"
    assert_contains "it names a cause that can produce this" "$hint" \
        "an unstageable pathspec"
    assert_contains "it still names the escape that always works" "$hint" \
        "emove what is refusing the transition and run \`crayon resume sr\`"
    assert_not_contains "it does not claim only the commit was refused" "$hint" \
        "only the commit was refused"
    assert_not_contains "and it does not offer the hook-conditional escape" \
        "$hint" "--adopt --note"

    # The batch is still on the record and still recoverable once the cause is
    # gone — the hint says so, so the test proves it rather than trusting it.
    "$CRAYON" resume sr >/dev/null 2>third.txt
    rc=$?
    assert_eq "with the object database writable again the resume completes" \
        "0" "$rc"
    assert_file_contains "and the page holds the drafted bytes" \
        docs/reference/sr.rst "Body."
    cleanup
}

test_n15_the_revised_manifest_passes_the_same_reader() {
    setup_repo
    hook_rejected_draft rm

    local page=docs/reference/rm-a.rst
    local after_before events_before hook_sha
    after_before=$(file_sha ".crayon/staging/rm/pending/after/$page")
    events_before=$(python3 -c '
import json, sys
print("\n".join(json.load(open(sys.argv[1], encoding="utf-8"))["events"]))
' .crayon/staging/rm/pending/manifest.json)
    hook_sha=$(file_sha "$page")

    # Stop after the commit and before the cleanup, so the revised manifest is
    # still on disk to be read back.
    CRAYON_CRASH_AT=cleanup "$CRAYON" resume rm --adopt --note "kept it" \
        >/dev/null 2>&1
    assert_eq "the crash before the cleanup is a hard exit" "137" "$?"

    local manifest
    manifest=$(manifest_through_read_manifest rm)
    assert_not_contains "the revised manifest passes read_manifest" "$manifest" \
        "REJECTED"
    assert_eq "its adopted after entry resolves inside the adopt directory" \
        "adopt/$page" \
        "$(printf '%s' "$manifest" | python3 -c '
import json, sys
rows = {row["path"]: row.get("after_path") for row in json.load(sys.stdin)["files"]}
print(rows.get(sys.argv[1]) or "MISSING")
' "$page")"
    assert_eq "and carries the adopted bytes' digest" "$hook_sha" \
        "$(printf '%s' "$manifest" | python3 -c '
import json, sys
rows = {row["path"]: row["after_sha"] for row in json.load(sys.stdin)["files"]}
print(rows.get(sys.argv[1], "MISSING"))
' "$page")"
    assert_eq "the durable adopt copy holds those bytes" "$hook_sha" \
        "$(file_sha ".crayon/staging/rm/pending/adopt/$page")"
    # The original material is evidence of what the interrupted verb intended
    # and is never rewritten.
    assert_eq "the original after copy is untouched" "$after_before" \
        "$(file_sha ".crayon/staging/rm/pending/after/$page")"
    # The revised batch GAINS a line; it never rewrites one. The generation's
    # own bytes are what every chain link after it digests.
    assert_eq "the generation's event bytes are carried over verbatim" \
        "$events_before" \
        "$(printf '%s' "$manifest" | python3 -c '
import json, sys
events = json.load(sys.stdin)["events"]
print("\n".join(events[:-1]))
')"
    cleanup
}

test_n29_t19b_adopt_unsupported() {
    setup_repo
    hook_rejected_resign rs

    local before rc
    before=$(resume_fingerprint rs)
    "$CRAYON" resume rs --adopt --note "keep the hook's plan bytes" \
        >/dev/null 2>err.txt
    rc=$?
    assert_eq "an interrupted re-sign refuses --adopt" "6" "$rc"
    assert_json_error "adopt_unsupported" "err.txt" "adopt_unsupported"
    # The refusal has to name the way out, and for a re-signed plan file the
    # way out is the intended bytes, not the hook's.
    assert_file_contains "the hint names --overwrite" "err.txt" "--overwrite"
    assert_eq "and nothing is written" "$before" "$(resume_fingerprint rs)"

    # The precondition is asked BEFORE the note rule: a flag that is not
    # allowed here is not made allowed by supplying a note.
    "$CRAYON" resume rs --adopt >/dev/null 2>err2.txt
    assert_json_error "the precondition precedes note_required" "err2.txt" \
        "adopt_unsupported"

    "$CRAYON" resume rs --overwrite >/dev/null 2>&1
    rc=$?
    assert_eq "--overwrite is the way out and it works" "0" "$rc"
    assert_not_contains "the intended plan bytes are restored" \
        "$(cat .crayon/units/rs/unit.md)" "HOOKFORMATTED"
    cleanup
}

test_n15_adopt_requires_a_note() {
    setup_repo
    hook_rejected_draft nn

    local before rc
    before=$(resume_fingerprint nn)
    "$CRAYON" resume nn --adopt >/dev/null 2>err.txt
    rc=$?
    assert_eq "--adopt without a note exits 2" "2" "$rc"
    assert_json_error "note_required" "err.txt" "note_required"
    assert_eq "and nothing is written" "$before" "$(resume_fingerprint nn)"
    cleanup
}

test_n15_adopt_with_no_unexpected_files_is_a_plain_resume() {
    setup_repo
    crayon_unit_new pr "reference/pr.rst" >/dev/null 2>&1
    "$CRAYON" signoff pr >/dev/null 2>&1
    stage_draft pr "reference/pr.rst" "P\n=\n\nBody.\n"
    # Crashed after the append, with no hook: the page was never placed, so
    # every file classifies `recoverable` and there is nothing to adopt.
    CRAYON_CRASH_AT=append "$CRAYON" draft pr "$(draft_path pr reference/pr.rst)" \
        >/dev/null 2>&1
    assert_eq "the crash is a hard exit" "137" "$?"

    local lines_before rc
    lines_before=$(ledger_lines pr)
    "$CRAYON" resume pr --adopt --note "nothing to keep" >/dev/null 2>err.txt
    rc=$?
    assert_eq "--adopt over zero unexpected files completes" "0" "$rc"
    assert_eq "and appends no reviewer edit" "$lines_before" "$(ledger_lines pr)"
    assert_eq "the last event is still the generation" "generation" \
        "$(tail -1 .crayon/units/pr/ledger.jsonl | json_field kind)"
    assert_file_exists "the page is placed" "docs/reference/pr.rst"
    cleanup
}

# WR-09: the two halves of `resume`'s note pairing.
#
# `read_note` ran BEFORE both of `resume_adopt`'s "this is really a plain
# resume" early returns, so `--adopt` over zero `unexpected` files — which
# contract 5.8's last sentence calls a plain resume — refused `note_required`
# for a run that was going to record no note at all. And symmetrically,
# argparse puts `--note` outside the decision flags' mutually exclusive group,
# so `resume <id> --note "…"` parsed fine and the note was discarded in
# silence.

# A crashed-after-append draft with no hook: the page was never placed, so
# every file classifies `recoverable` and there is nothing to adopt.
plain_resumable_draft() {
    local unit="$1"
    crayon_unit_new "$unit" "reference/${unit}.rst" >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
    stage_draft "$unit" "reference/${unit}.rst" "P\n=\n\nBody.\n"
    CRAYON_CRASH_AT=append "$CRAYON" draft "$unit" \
        "$(draft_path "$unit" reference/${unit}.rst)" >/dev/null 2>&1
    return 0
}

test_n15_wr09_adopt_over_zero_unexpected_files_needs_no_note() {
    setup_repo
    plain_resumable_draft na

    local lines_before rc
    lines_before=$(ledger_lines na)
    "$CRAYON" resume na --adopt >/dev/null 2>err.txt
    rc=$?
    assert_eq "contract 5.8's plain resume completes without a note" "0" "$rc"
    assert_eq "stderr carries no refusal" "0" "$(grep -c '"error"' err.txt)"
    assert_eq "and appends no reviewer edit" "$lines_before" "$(ledger_lines na)"
    assert_eq "the last event is still the generation" "generation" \
        "$(tail -1 .crayon/units/na/ledger.jsonl | json_field kind)"
    assert_file_exists "the page is placed" "docs/reference/na.rst"
    cleanup
}

test_n15_wr09_a_note_with_no_decision_flag_is_refused_not_discarded() {
    setup_repo
    plain_resumable_draft nd

    local before rc
    before=$(resume_fingerprint nd)
    "$CRAYON" resume nd --note "a decision I never made" >/dev/null 2>err.txt
    rc=$?
    assert_eq "a note with nothing to attach it to exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "err.txt" "bad_target"
    assert_contains "the hint names the flag the note belongs to" \
        "$(cat err.txt)" "--adopt"
    assert_eq "and nothing is written" "$before" "$(resume_fingerprint nd)"

    # Without the note the same resume completes, so the refusal is about the
    # pairing and nothing else.
    "$CRAYON" resume nd >/dev/null 2>err2.txt
    assert_eq "the same resume without the note completes" "0" "$?"
    cleanup
}


# --- N-46: T16b — the hook shape where the rewrite RESTORES the old bytes ----
#
# CR-01. N-15 above drafts two brand-new pages, so `before_sha` is null for
# both and `HOOKFORMATTED` can only ever be `unexpected`; and it removes the
# hook before the resume. Neither is the shape a real canonicalising hook
# produces once it has been adopted once: the page on disk ALREADY holds the
# hook's output, the transition's `before_sha` IS that output, and the hook
# restores it on every rejected attempt. Classified on `before_sha` alone that
# reads `recoverable`, `resume` re-places the tool's bytes, the hook rewrites
# and rejects again, and every mode loops forever. The placement record step 3
# writes is what makes the page `unexpected` instead, which is the class that
# routes the author to the two answers contract 5.8 promises.

# A RE-drafted unit whose target already held the hook's canonical output
# before the transition, with the hook still installed after the rejected
# commit. The first draft is what puts those bytes on disk through the tool's
# own gate — a page written behind crayon's back refuses `target_exists`, and
# the adoption that resolves that is a different trace.
hook_restored_draft() {
    local unit="$1"
    local page="docs/reference/${unit}.rst"
    crayon_unit_new "$unit" "reference/${unit}.rst" >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
    # Draft 1: the page now holds exactly what the hook would write, which is
    # the steady state once a canonicalising hook has been adopted once.
    stage_draft "$unit" "reference/${unit}.rst" "HOOKFORMATTED\n"
    "$CRAYON" draft "$unit" "$(draft_path "$unit" reference/${unit}.rst)" \
        >/dev/null 2>&1
    "$CRAYON" steer "$unit" --note "make the body say something" >/dev/null 2>&1
    # Draft 2: different bytes, hook installed, and LEFT installed.
    stage_draft "$unit" "reference/${unit}.rst" "C\n=\n\nBody c.\n"
    install_canonicalising_reject_hook "$page"
    "$CRAYON" draft "$unit" "$(draft_path "$unit" reference/${unit}.rst)" \
        >/dev/null 2>&1
    return 0
}

test_n46_t16b_a_hook_that_restores_the_old_bytes_is_not_recoverable() {
    setup_repo
    hook_restored_draft hb
    local page=docs/reference/hb.rst

    assert_file_contains "the hook's bytes are back on disk" "$page" "HOOKFORMATTED"
    assert_file_exists "step 3's placement record survives the failed commit" \
        ".crayon/staging/hb/pending/progress.json"

    local out rc
    out=$("$CRAYON" resume hb --dry-run 2>err.txt)
    rc=$?
    assert_eq "a dry-run over the interrupted transition exits 0" "0" "$rc"
    # The defect in one line: `before_sha` alone would say `recoverable` here.
    assert_eq "the placed-then-rewritten page is unexpected" "unexpected $page" \
        "$(printf '%s\n' "$out" | sed -n 1p)"

    # The hook is STILL INSTALLED — the realistic case, and the one no other
    # fixture in either suite resumes under.
    assert_file_exists "the hook is still installed" ".git/hooks/pre-commit"
    "$CRAYON" resume hb >/dev/null 2>err2.txt
    rc=$?
    assert_eq "a plain resume offers the decision instead of looping" "6" "$rc"
    assert_json_error "the two answers are offered" "err2.txt" "resume_ambiguous"

    "$CRAYON" resume hb --adopt --note "the formatter's form is the house form" \
        >/dev/null 2>err3.txt
    rc=$?
    assert_eq "--adopt escapes, with the hook still live" "0" "$rc"
    assert_file_contains "the hook's bytes are what is recorded" "$page" \
        "HOOKFORMATTED"
    local last
    last=$(tail -1 .crayon/units/hb/ledger.jsonl)
    assert_eq "as a reviewer edit" "reviewer-edit" \
        "$(printf '%s' "$last" | json_field kind)"
    assert_eq "naming the hook" "True" "$(printf '%s' "$last" | json_field hook)"
    assert_file_not_exists "the pending directory is gone" \
        ".crayon/staging/hb/pending"
    cleanup
}

test_n46_t16b_a_second_rejected_commit_on_one_batch_is_not_a_loop() {
    setup_repo
    hook_restored_draft lp
    local page=docs/reference/lp.rst

    # `--overwrite` re-places the bytes the hook already rejected once. The
    # tool must not answer with `uncommitted_tail` and the hint that produced
    # it: that hint reproduces the refusal, which is the closed loop.
    local rc
    "$CRAYON" resume lp --overwrite >/dev/null 2>err.txt
    rc=$?
    assert_eq "the second rejected commit still exits 6" "6" "$rc"
    assert_json_error "but names the honest limit" "err.txt" "recovery_unsupported"
    assert_file_contains "with the write path's own detail" "err.txt" \
        "commit_rejected"
    # The hint must offer an escape, not repeat `crayon resume lp` — the hint
    # whose own outcome is this refusal.
    local hint
    hint=$(python3 -c '
import json
print(json.load(open("err.txt", encoding="utf-8"))["hint"])
')
    assert_contains "the hint names the escape" "$hint" "--adopt"
    # CR-01 (re-review): the hint must not read as "nothing happened". Step 2
    # appended the batch and step 3 placed the files; only step 4 was refused.
    # An operator told "nothing was committed" hears "nothing was written" and
    # walks away from a ledger tail and a placed page that are both on disk.
    assert_not_contains "the hint does not claim nothing was written" "$hint" \
        "Nothing was committed"
    assert_contains "it states what is actually on disk" "$hint" \
        "the files are "
    assert_contains "and that only step 4 was refused" "$hint" \
        "only the commit was refused"
    assert_file_exists "nothing is cleaned up: the batch is still resumable" \
        ".crayon/staging/lp/pending/manifest.json"
    assert_file_exists "the page the hint says is placed really is" "$page"

    # And the escape the refusal names actually works.
    "$CRAYON" resume lp --adopt --note "kept the formatter's output" \
        >/dev/null 2>err2.txt
    assert_eq "--adopt is the way out it points at" "0" "$?"
    assert_file_not_exists "and the transition completes" \
        ".crayon/staging/lp/pending"
    cleanup
}

# --- N-46: CR-01 (iteration 3) — the routed escape has a PRECONDITION --------
#
# The two shapes the first two CR-01 fixes never ran. Both were reproduced
# against the shipped executable in review; the gates that shipped with the
# iteration-2 fix all asserted that the string `--adopt` was PRESENT in some
# piece of prose, and none of them ran `--adopt` after a `commit_rejected` on
# any batch except `hook_restored_draft` — the one shape where it works. A gate
# that checks a command is mentioned is not a gate that the command works.

test_n46_adopt_after_commit_rejected_on_a_non_generation_batch_does_not_loop() {
    setup_repo
    crayon_unit_new sx "reference/sx.rst" >/dev/null 2>&1
    "$CRAYON" signoff sx >/dev/null 2>&1
    # Installed AFTER the declaration and the signoff, so those two commit and
    # the refused batch is the steering alone.
    install_reject_only_hook

    "$CRAYON" steer sx --note "please fix the body" >/dev/null 2>err.txt
    assert_eq "the first rejected commit is uncommitted_tail" "6" "$?"
    assert_json_error "on the first attempt" "err.txt" "uncommitted_tail"

    "$CRAYON" resume sx >/dev/null 2>err2.txt
    assert_eq "the second is the honest limit" "6" "$?"
    assert_json_error "named recovery_unsupported" "err2.txt" \
        "recovery_unsupported"
    assert_file_contains "with the write path's own detail" "err2.txt" \
        "commit_rejected"

    local hint
    hint=$(json_field hint <err2.txt)
    # The defect in one line: iteration 2 put `--adopt` in this hint with no
    # precondition, and on THIS batch `--adopt` refuses.
    assert_contains "the hint states the precondition on --adopt" "$hint" \
        "something REWROTE the placed bytes, and every unexpected file's current bytes are still on disk"
    assert_contains "and names the refusal --adopt would raise here" "$hint" \
        "adopt_unsupported"
    # On the stem: WR-03 widened "the commit" to "the transition", because the
    # `stage_rejected` arm never reaches a commit at all.
    assert_contains "the escape that always works is named first" "$hint" \
        "remove what is refusing the"

    # Run the routed escape. It refuses — which is the documented behaviour —
    # but its hint must not send the operator round the loop again.
    "$CRAYON" resume sx --adopt --note "keep the bytes" >/dev/null 2>err3.txt
    assert_eq "--adopt on a steering batch refuses" "6" "$?"
    assert_json_error "as adopt_unsupported" "err3.txt" "adopt_unsupported"
    local adopt_hint
    adopt_hint=$(json_field hint <err3.txt)
    # `--overwrite` is what this row used to route to unconditionally. On a
    # batch git has already refused it re-places the same bytes, meets the same
    # hook, and raises `commit_rejected` — whose hint named `--adopt`. Two hops,
    # no progress.
    assert_contains "the warning is conditional on a remaining blocker" \
        "$adopt_hint" "if something is still refusing"
    assert_contains "and routes to the one move that clears it" "$adopt_hint" \
        "remove what is refusing the"

    # Remove the blocker, then execute the remedy from the refusal itself.
    rm -f .git/hooks/pre-commit
    run_unblocked_hint err3.txt >/dev/null 2>err4.txt
    assert_eq "the escape the refusal names completes the batch" "0" "$?"
    assert_file_not_exists "and retires the pending directory" \
        ".crayon/staging/sx/pending"
    cleanup
}

test_n46_adopt_after_commit_rejected_without_a_rewrite_is_not_an_escape() {
    setup_repo
    crayon_unit_new dx "reference/dx.rst" >/dev/null 2>&1
    "$CRAYON" signoff dx >/dev/null 2>&1
    stage_draft dx "reference/dx.rst" "C\n=\n\nBody c.\n"
    # A GENERATION batch, so `adopt_unsupported`'s precondition is satisfied —
    # and the hook rewrites nothing, so there is no `unexpected` file to adopt.
    install_reject_only_hook
    "$CRAYON" draft dx "$(draft_path dx reference/dx.rst)" >/dev/null 2>err.txt
    assert_eq "the first rejected commit is uncommitted_tail" "6" "$?"

    "$CRAYON" resume dx >/dev/null 2>err2.txt
    assert_eq "the second is the honest limit" "6" "$?"
    assert_file_contains "with the write path's own detail" "err2.txt" \
        "commit_rejected"

    # The dry-run is what the skill is told to read before offering `--adopt`:
    # no path is `unexpected`, so there is nothing to adopt.
    local out
    out=$("$CRAYON" resume dx --dry-run 2>/dev/null)
    assert_contains "the placed page is done, not unexpected" "$out" \
        "done docs/reference/dx.rst"
    assert_not_contains "nothing on disk is unexpected" "$out" "unexpected "

    # So `--adopt` is a plain resume by contract 5.8, and reproduces the
    # refusal it was routed from. This is the behaviour the surfaces must now
    # warn about rather than route into.
    "$CRAYON" resume dx --adopt --note "keep the bytes" >/dev/null 2>err3.txt
    assert_eq "--adopt with nothing unexpected refuses again" "6" "$?"
    assert_json_error "with the same reason it was offered against" "err3.txt" \
        "recovery_unsupported"
    assert_file_contains "and the same detail" "err3.txt" "commit_rejected"
    local hint
    hint=$(json_field hint <err3.txt)
    assert_contains "the hint says so in as many words" "$hint" \
        "it is a plain resume that retries the same transition"

    # The escape that always works, again: remove the hook, resume once more.
    rm -f .git/hooks/pre-commit
    "$CRAYON" resume dx >/dev/null 2>err4.txt
    assert_eq "removing what refuses the commit completes the batch" "0" "$?"
    assert_file_not_exists "and retires the pending directory" \
        ".crayon/staging/dx/pending"
    cleanup
}


# --- N-46: CR-01 / CR-02 (iteration 4) — the sites the first three fixes -----
#     never walked.
#
# These walks cover both adopt refusal arms and blocker removal. Static S-13
# checks wording structure; only executing the printed remedy proves progress.

test_n46_adopt_on_a_deleted_target_does_not_route_back_into_overwrite() {
    setup_repo
    crayon_unit_new dw "reference/dw.rst" >/dev/null 2>&1
    "$CRAYON" signoff dw >/dev/null 2>&1
    stage_draft dw "reference/dw.rst" "D\n=\n\nBody d.\n"
    # Installed after the declaration and the signoff, so the refused batch is
    # the GENERATION — which is why the row's old opening claim ("a batch whose
    # last event is neither a generation nor a reviewer edit") does not describe
    # this arm at all.
    install_delete_and_reject_hook "docs/reference/dw.rst"

    "$CRAYON" draft dw "$(draft_path dw reference/dw.rst)" >/dev/null 2>err.txt
    assert_eq "the first rejected commit is uncommitted_tail" "6" "$?"
    assert_json_error "on the first attempt" "err.txt" "uncommitted_tail"

    "$CRAYON" resume dw --overwrite >/dev/null 2>err2.txt
    assert_eq "the second is the honest limit" "6" "$?"
    assert_file_contains "with the write path's own detail" "err2.txt" \
        "commit_rejected"

    # Two full laps of the walk the review drove three times. Nothing used to
    # change between them except the attempt counter.
    local lap hint
    for lap in 1 2; do
        "$CRAYON" resume dw --adopt --note "keep the bytes" >/dev/null 2>err3.txt
        assert_eq "lap $lap: the routed --adopt refuses" "6" "$?"
        assert_json_error "lap $lap: as adopt_unsupported" "err3.txt" \
            "adopt_unsupported"
        assert_file_contains "lap $lap: on the arm iteration 3 never reached" \
            "err3.txt" "has no current bytes to adopt"
        hint=$(json_field hint <err3.txt)
        assert_contains "lap $lap: the warning is conditional" \
            "$hint" "if something is still refusing"
        assert_contains "lap $lap: the remedy survives the warning" \
            "$hint" "With nothing refusing it, crayon resume dw --overwrite"
        assert_contains "lap $lap: and names the one move that clears it" \
            "$hint" "remove what is refusing the"
        "$CRAYON" resume dw --overwrite >/dev/null 2>err4.txt
        assert_eq "lap $lap: and it is refused, as the hint said" "6" "$?"
        assert_file_contains "lap $lap: by the same hook" "err4.txt" \
            "commit_rejected"
    done

    # The escape the hint names, driven to the end. The hook deleted the page,
    # so the plain resume lands on `resume_ambiguous` — the terminus
    # `escape_hint` deliberately leaves unbranched, because it is where the
    # escape LANDS — and `--overwrite` there completes the batch.
    rm -f .git/hooks/pre-commit
    "$CRAYON" resume dw >/dev/null 2>err5.txt
    assert_eq "the escape lands on the two-choice question" "6" "$?"
    assert_json_error "which is resume_ambiguous" "err5.txt" "resume_ambiguous"
    for refusal in err2.txt err5.txt; do
        assert_file_contains "$refusal: deleted bytes are not offered for adoption" \
            "$refusal" "still on disk"
    done
    for lap in 1 2 3 4; do
        "$CRAYON" resume dw --adopt --note keep >/dev/null 2>err6.txt
        hint=$(json_field hint <err6.txt)
        assert_not_contains "after removal $lap: no false prediction" "$hint" \
            "would re-place the same bytes and be refused again"
        assert_contains "after removal $lap: the remedy is still offered" "$hint" \
            "With nothing refusing it, crayon resume dw --overwrite"
        "$CRAYON" resume dw >/dev/null 2>err5.txt
    done
    run_unblocked_hint err6.txt >/dev/null 2>escape.txt
    assert_eq "and --overwrite completes the batch there" "0" "$?"
    assert_file_not_exists "retiring the pending directory" \
        ".crayon/staging/dw/pending"
    assert_file_exists "with the intended bytes placed" "docs/reference/dw.rst"
    cleanup
}

# Execute the remedy the refusal actually offers for the known unblocked state.
# No eval, no guessed fallback command: an unreadable/missing offer fails closed.
run_unblocked_hint() {
    python3 - "$CRAYON" "$1" <<'PY'
import json, re, shlex, subprocess, sys
hint = json.load(open(sys.argv[2], encoding="utf-8"))["hint"]
match = re.search(r"With nothing refusing it, (crayon resume [\w-]+ --overwrite)\b", hint)
if not match:
    sys.exit("no unblocked remedy in the refusal's hint")
sys.exit(subprocess.run([sys.argv[1]] + shlex.split(match[1])[1:]).returncode)
PY
}

test_n46_resume_ambiguous_routes_adopt_with_its_precondition() {
    setup_repo
    crayon_unit_new sq "reference/sq.rst" >/dev/null 2>&1
    # `signoff` writes `unit.md`, so the hook's rewrite makes a placed file
    # `unexpected` and the batch's last event is a signoff — a kind `--adopt`
    # cannot take. Seven verbs write `unit.md`; this is one of them.
    install_rewrite_and_reject_hook ".crayon/units/sq/unit.md"

    "$CRAYON" signoff sq >/dev/null 2>err.txt
    assert_eq "the rejected commit is uncommitted_tail" "6" "$?"

    "$CRAYON" resume sq >/dev/null 2>err2.txt
    assert_eq "the plain resume asks the two-choice question" "6" "$?"
    assert_json_error "resume_ambiguous" "err2.txt" "resume_ambiguous"
    local hint
    hint=$(json_field hint <err2.txt)
    # The CR-02 defect in one line: this hint used to offer `--adopt` with no
    # precondition at all, which is the iteration-2 defect one reason over.
    assert_contains "the routed --adopt carries its precondition" "$hint" \
        "ONLY when the batch's last event is a generation or a reviewer edit"
    assert_contains "and names the refusal it would raise here" "$hint" \
        "adopt_unsupported"
    assert_contains "and the move a refused batch needs before either choice" \
        "$hint" "remove what is refusing the commit"

    # The precondition is true of this batch, and the tool does what the hint
    # now says it will.
    "$CRAYON" resume sq --adopt --note "keep them" >/dev/null 2>err3.txt
    assert_eq "--adopt on a signoff batch refuses" "6" "$?"
    assert_json_error "as adopt_unsupported" "err3.txt" "adopt_unsupported"
    assert_file_contains "naming the kind it cannot adopt" "err3.txt" \
        "the batch's last event is a signoff"

    # The THIRD offer site, found by walking the offers rather than by
    # reproducing a transcript: `--note` with no decision to attach it to.
    "$CRAYON" resume sq --note "keep them" >/dev/null 2>err4.txt
    assert_eq "--note with no decision refuses" "2" "$?"
    assert_json_error "as bad_target" "err4.txt" "bad_target"
    hint=$(json_field hint <err4.txt)
    assert_contains "and its offer of --adopt is qualified too" "$hint" \
        "ONLY when the batch's last event is a generation or a reviewer edit"
    assert_contains "the third offer also excludes absent bytes" "$hint" "still on disk"

    # The choice that IS available here completes the batch once the hook is
    # gone, so the two-choice question is a terminus and not a lap.
    rm -f .git/hooks/pre-commit
    "$CRAYON" resume sq --overwrite >/dev/null 2>err5.txt
    assert_eq "--overwrite completes it" "0" "$?"
    assert_file_not_exists "retiring the pending directory" \
        ".crayon/staging/sq/pending"
    cleanup
}


# A bounded execution graph, separate from S-13's static wording checks. Each
# applicable printed command gets its own copy of the same pending repository.
# Conditions are evaluated against these known fixtures, not inferred from an
# attempt count. A repeated (refusal, command) on a path is a failed escape.
test_n46_every_applicable_printed_escape_terminates() {
    local shape classes
    # Outside any repo: `cleanup` removes each shape's TEST_DIR, and the
    # vacuity guard below is a claim about the four shapes TOGETHER.
    classes=$(mktemp)
    for shape in deleted signoff rewritten unchanged; do
        setup_repo
        crayon_unit_new graph reference/graph.rst >/dev/null 2>&1
        if [ "$shape" = signoff ]; then
            install_rewrite_and_reject_hook .crayon/units/graph/unit.md
            "$CRAYON" signoff graph >/dev/null 2>first.txt
        else
            "$CRAYON" signoff graph >/dev/null 2>&1
            stage_draft graph reference/graph.rst 'Graph\n=====\n\nBody.\n'
            case "$shape" in
                deleted) install_delete_and_reject_hook docs/reference/graph.rst ;;
                rewritten) install_canonicalising_reject_hook docs/reference/graph.rst ;;
                unchanged) install_reject_only_hook ;;
            esac
            "$CRAYON" draft graph "$(draft_path graph reference/graph.rst)" >/dev/null 2>first.txt
        fi
        "$CRAYON" resume graph --overwrite >/dev/null 2>limit.txt
        # Start at both the repeated git refusal and each adoption refusal.
        if [ "$shape" = deleted ] || [ "$shape" = signoff ]; then
            "$CRAYON" resume graph --adopt --note keep >/dev/null 2>adopt.txt
        fi
        rm -f .git/hooks/pre-commit
        python3 - "$CRAYON" "$shape" <<'PY'
import hashlib, json, pathlib, re, shutil, subprocess, sys, tempfile

tool, shape = sys.argv[1:]
repo = pathlib.Path.cwd()
command_re = re.compile(r"crayon resume ([a-z0-9-]+)(?: (--overwrite|--adopt))?")


def adoptable(directory, unit):
    """Contract 5.8's own four conditions, read off THIS repo.

    WR-02(c): the filters here used to be `shape in ("signoff", "unchanged")`
    and `shape == "deleted" and "still on disk" in hint` — the answer encoded
    in the fixture's name and in the wording of the hint under test. A future
    `--adopt` offer that loops on the signoff or unchanged shape was skipped by
    construction, and the deleted filter was keyed on the very sentence CR-02
    was filed about: reword the hint and it silently stops firing.

    Derived instead from the recorded facts — the pending manifest's last event
    and files[], and the bytes on disk — so a fixture becomes adoptable or
    stops being adoptable because of what it IS.
    """
    pending = directory / ".crayon" / "staging" / unit / "pending" / "manifest.json"
    if not pending.exists():
        return False
    manifest = json.loads(pending.read_text(encoding="utf-8"))
    last = json.loads(manifest["events"][-1])
    if last.get("kind") not in ("generation", "reviewer-edit"):
        return False
    if last.get("kind") == "reviewer-edit" and last.get("hook") is True:
        return False
    unexpected = []
    for entry in manifest["files"]:
        path = directory / entry["path"]
        digest = None
        if path.exists():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["after_sha"]:
            unexpected.append(digest)
    if not unexpected:
        return False              # nothing to adopt: a plain resume
    return all(digest is not None for digest in unexpected)


def choices(directory, refusal):
    """Every printed command, split into the applicable and the predicted.

    WR-02(c): nothing is dropped any more. A printed `--adopt` the recorded
    facts say is not adoptable is still RUN — once, in its own copy — and held
    to the prediction: the tool must say `adopt_unsupported`, or complete the
    batch as the plain resume contract 5.8 documents. Skipping it was how a
    future offer that loops could be skipped by construction.
    """
    hint = refusal["hint"]
    applicable, predicted = set(), set()
    for match in command_re.finditer(hint):
        unit, flag = match.groups()
        # This fixture has removed the blocker. A prediction of certain
        # rejection explicitly rules this command out; do not silently take
        # it anyway (the previous regression test did exactly that).
        if hint[match.end():].startswith("` would re-place the same bytes and be refused again"):
            continue
        command = ("resume", unit) + ((flag,) if flag else ())
        if flag == "--adopt":
            command += ("--note", "keep")
            if not adoptable(directory, unit):
                predicted.add(command)
                continue
        applicable.add(command)
    # The shared precondition also offers this flag without repeating the
    # already-named resume command and unit.
    if "`--overwrite` to restore the intended bytes" in hint:
        applicable.add(("resume", refusal["unit"], "--overwrite"))
    assert applicable, "no applicable printed escape: " + hint
    return applicable, predicted


def run(directory, command):
    """One command in a throwaway copy of `directory`."""
    scratch = tempfile.mkdtemp(prefix="crayon-route-")
    try:
        branch = pathlib.Path(scratch) / "repo"
        shutil.copytree(directory, branch)
        # WR-04: an explicit codec, not the locale's. Every refusal this
        # decodes is full of em-dashes, and under LC_ALL=C the walk died
        # on the first one instead of testing anything.
        result = subprocess.run(
            [tool, *command], cwd=branch,
            capture_output=True, text=True, encoding="utf-8",
        )
        return branch, result, scratch
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise


def walk(directory, refusal, seen):
    assert len(seen) < 6, "recovery did not terminate within six decisions"
    applicable, predicted = choices(directory, refusal)
    for command in predicted:
        branch, result, scratch = run(directory, command)
        try:
            assert result.returncode in (0, 6), result.stderr
            if result.returncode == 6:
                refused = json.loads(result.stderr)
                assert refused["error"] == "adopt_unsupported", (
                    "the recorded facts say this batch is not adoptable, so "
                    "`%s` must say so; it said %r"
                    % (" ".join(command), refused["error"])
                )
                ROUTED.add(("predicted", refused["error"]))
            else:
                # Contract 5.8's plain-resume degradation, and it must
                # actually complete rather than leave the batch pending.
                assert not (branch / ".crayon/staging/graph/pending").exists()
                ROUTED.add(("predicted", "plain resume"))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    for command in applicable:
        pair = (refusal["error"], command)
        assert pair not in seen, "repeated refusal/command: " + repr(pair)
        branch, result, scratch = run(directory, command)
        try:
            ROUTED.add(("driven", command[2] if len(command) > 2 else ""))
            if result.returncode == 0:
                assert not (branch / ".crayon/staging/graph/pending").exists(), "completion kept pending material"
            else:
                assert result.returncode == 6, result.stderr
                next_refusal = json.loads(result.stderr)
                walk(branch, next_refusal, seen | {pair})
        finally:
            shutil.rmtree(scratch, ignore_errors=True)


ROUTED = set()
for origin in ("limit.txt", "adopt.txt"):
    path = repo / origin
    if path.exists():
        walk(repo, json.loads(path.read_text(encoding="utf-8")), set())
# Vacuous-pass guard: a walk that drove nothing proves nothing.
assert ROUTED, "the escape graph drove no command at all on the %s shape" % shape
pathlib.Path("route-classes.txt").write_text(
    "\n".join(sorted("%s:%s" % pair for pair in ROUTED)) + "\n", encoding="utf-8"
)
PY
        assert_eq "$shape: every applicable printed escape reaches a completed commit" "0" "$?"
        # WR-02(c): the classes this shape actually exercised, accumulated
        # across the four shapes so the vacuous case — a filter that quietly
        # stopped admitting `--adopt` anywhere — cannot pass.
        cat route-classes.txt >>"$classes"
        cleanup
    done

    # Both halves have to be reached by the four shapes together: at least one
    # routed `--adopt` actually driven, and at least one predicted-inapplicable
    # `--adopt` held to its refusal. The old shape-name filters guaranteed
    # neither, which is how three of the four shapes never executed a routed
    # `--adopt` at all.
    assert_file_contains "some shape drives a routed --adopt" \
        "$classes" "driven:--adopt"
    assert_file_contains "and some shape holds an inapplicable one to its refusal" \
        "$classes" "predicted:"
    rm -f "$classes"
}


# --- N-37: T27 / T27b / T27c — the persistence invariant, and TEST-05 --------
#
# Contract 5.8 states the invariant as one sentence: every published manifest
# references durable copies matching all of its recovery digests. What that
# sentence BUYS is a property no amount of reading the code establishes — that
# a crash on either side of the publication leaves a state the next `resume`
# completes correctly. These cases are that proof, driven through the D-15
# crash hook rather than a signal or an external kill, because `os._exit` skips
# cleanup handlers and buffer flushing, which is what an interruption does.

# One manifest entry's `after_path`, or MISSING — which manifest is
# authoritative is the whole of the T27/T27b distinction.
after_path_of() {
    python3 -c '
import json, sys
rows = {
    row["path"]: row.get("after_path")
    for row in json.load(open(sys.argv[1], encoding="utf-8"))["files"]
}
print(rows.get(sys.argv[2]) or "MISSING")
' ".crayon/staging/$1/pending/manifest.json" "$2"
}

# How many events of one kind a unit's ledger holds. A duplicate reviewer edit
# would record one human decision twice (T-17-32), so the count is the assertion.
count_kind() {
    python3 -c '
import json, sys
total = 0
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if line and json.loads(line).get("kind") == sys.argv[2]:
        total += 1
print(total)
' ".crayon/units/$1/ledger.jsonl" "$2"
}

test_n37_t27_t27b_t27c_adopt_persistence_and_idempotence() {
    setup_repo

    # --- T27 (invariant i): a crash AFTER the copies, BEFORE the publication --
    hook_rejected_draft t27
    CRAYON_CRASH_AT=adopt "$CRAYON" resume t27 --adopt --note "kept it" \
        >/dev/null 2>&1
    assert_eq "the crash before the publication is a hard exit" "137" "$?"
    assert_file_exists "the adopt copies are already durable" \
        ".crayon/staging/t27/pending/adopt/docs/reference/t27-a.rst"
    # The old manifest is still authoritative, so those copies are stray: the
    # invariant holds because nothing published has ever referenced them.
    assert_eq "the OLD manifest is still authoritative" "MISSING" \
        "$(after_path_of t27 docs/reference/t27-a.rst)"
    assert_eq "no reviewer edit was appended" "0" "$(count_kind t27 reviewer-edit)"

    local before out rc
    before=$(resume_fingerprint t27)
    out=$("$CRAYON" resume t27 --dry-run 2>/dev/null)
    assert_contains "a dry-run reports the stray copies" "$out" \
        "would delete pending/adopt/"
    assert_eq "and deletes nothing" "$before" "$(resume_fingerprint t27)"

    "$CRAYON" resume t27 --adopt --note "kept it" >/dev/null 2>&1
    rc=$?
    assert_eq "the adopt re-runs from the stray state" "0" "$rc"
    assert_eq "and produces exactly one reviewer edit" "1" \
        "$(count_kind t27 reviewer-edit)"
    assert_file_not_exists "the pending directory, adopt copies and all, is gone" \
        ".crayon/staging/t27/pending"

    # A write-mode run that does NOT adopt sweeps the same stray copies.
    hook_rejected_draft t27s
    CRAYON_CRASH_AT=adopt "$CRAYON" resume t27s --adopt --note "kept it" \
        >/dev/null 2>&1
    "$CRAYON" resume t27s --overwrite >/dev/null 2>&1
    rc=$?
    assert_eq "a write-mode resume completes over the stray copies" "0" "$rc"
    assert_eq "recording no reviewer edit at all" "0" \
        "$(count_kind t27s reviewer-edit)"

    # --- T27b (invariant ii): a crash AFTER the publication, before the append
    hook_rejected_draft t27b
    CRAYON_CRASH_AT=manifest "$CRAYON" resume t27b --adopt --note "kept it" \
        >/dev/null 2>&1
    assert_eq "the crash after the publication is a hard exit" "137" "$?"
    assert_eq "the REVISED manifest is authoritative" \
        "adopt/docs/reference/t27b-a.rst" \
        "$(after_path_of t27b docs/reference/t27b-a.rst)"
    assert_eq "and its durable copy is there to match its digest" \
        "$(file_sha docs/reference/t27b-a.rst)" \
        "$(file_sha .crayon/staging/t27b/pending/adopt/docs/reference/t27b-a.rst)"
    assert_eq "nothing has been appended yet" "0" \
        "$(count_kind t27b reviewer-edit)"

    # The tail is a byte-prefix of the revised batch, so a PLAIN resume — no
    # flag at all — completes it, appending the line the manifest already holds.
    "$CRAYON" resume t27b >/dev/null 2>err.txt
    rc=$?
    assert_eq "a plain resume completes it" "0" "$rc"
    assert_eq "appending the reviewer edit the manifest already carried" "1" \
        "$(count_kind t27b reviewer-edit)"
    assert_eq "with the hook flag set" "True" \
        "$(tail -1 .crayon/units/t27b/ledger.jsonl | json_field hook)"
    assert_file_contains "and the author's bytes kept" docs/reference/t27b-a.rst \
        "HOOKFORMATTED"

    # --- T27c (idempotence): --adopt twice in a row --------------------------
    hook_rejected_draft t27c
    "$CRAYON" resume t27c --adopt --note "kept it" >/dev/null 2>&1
    local lines_after_first
    lines_after_first=$(ledger_lines t27c)
    "$CRAYON" resume t27c --adopt --note "kept it" >/dev/null 2>&1
    assert_eq "the ledger line count is identical after the second adopt" \
        "$lines_after_first" "$(ledger_lines t27c)"
    assert_eq "and exactly one reviewer edit exists" "1" \
        "$(count_kind t27c reviewer-edit)"
    "$CRAYON" show t27c >/dev/null 2>&1
    rc=$?
    assert_eq "the chain verifies (show re-runs stage a)" "0" "$rc"

    # The repeat that actually needs the guard: a crash between the publication
    # and the append, then `--adopt` AGAIN. The line is already in the batch.
    hook_rejected_draft t27d
    CRAYON_CRASH_AT=manifest "$CRAYON" resume t27d --adopt --note "kept it" \
        >/dev/null 2>&1
    "$CRAYON" resume t27d --adopt --note "a second time" >/dev/null 2>&1
    rc=$?
    assert_eq "a repeated adopt after the publication completes" "0" "$rc"
    assert_eq "and never appends a duplicate" "1" "$(count_kind t27d reviewer-edit)"
    assert_contains "the line kept is the first adopt's" \
        "$(tail -1 .crayon/units/t27d/ledger.jsonl | json_field note)" "kept it"
    cleanup
}

test_n37_every_crash_point_leaves_a_classifiable_state() {
    setup_repo
    # D-15's five write-protocol injection points, each driving the REAL
    # protocol. For each: what is on disk after the crash, what the next
    # `resume --dry-run` reports about it, and that the next write-mode
    # `resume` either completes the transition or refuses with a named
    # situation from contract 5.8's table. An UNCLASSIFIABLE state is the
    # failure this matrix exists to catch.
    local point unit expected rc out
    for point in manifest append place:1 commit cleanup; do
        unit="cp${point%%:*}"
        if [ "$point" = manifest ]; then
            # `unit new` has not written its ledger yet at this point, so there
            # would be no unit to resume. A signoff over a committed unit
            # reaches the same boundary with a record already on disk.
            crayon_unit_new "$unit" "reference/$unit.rst" >/dev/null 2>&1
            CRAYON_CRASH_AT="$point" "$CRAYON" signoff "$unit" >/dev/null 2>&1
        else
            crashed_unit_new "$unit" "$point"
        fi
        assert_file_exists "$point: the unit directory is preserved" \
            ".crayon/units/$unit"

        case "$point" in
            manifest | cleanup) expected=3 ;;
            *) expected=0 ;;
        esac

        out=$("$CRAYON" resume "$unit" --dry-run 2>"dry-$unit.txt")
        rc=$?
        assert_eq "$point: the dry-run classifies it" "$expected" "$rc"
        assert_not_contains "$point: never an unclassifiable state" \
            "$(cat "dry-$unit.txt")" "recovery_unsupported"
        if [ "$expected" = 0 ]; then
            assert_contains "$point: the dry-run names it resumable" "$out" \
                "resumable $unit"
        else
            assert_eq "$point: the refusal names a situation" "nothing_to_resume" \
                "$(json_field error <"dry-$unit.txt")"
            assert_contains "$point: and says what write mode would delete" \
                "$out" "would delete pending/:"
        fi

        "$CRAYON" resume "$unit" >/dev/null 2>"run-$unit.txt"
        rc=$?
        assert_eq "$point: the write-mode run answers the same way" "$expected" \
            "$rc"
        if [ "$expected" = 0 ]; then
            assert_file_not_exists "$point: and consumed the pending directory" \
                ".crayon/staging/$unit/pending"
        fi
    done
    cleanup
}

# TEST-05: the fixture hooks are inert in the shipped executable. The acceptance
# suite carries one assertion of this; it is repeated here so the property
# survives the suite split in plans 17-10 and 17-11 no matter which file a given
# test ends up in.
test_n37_test05_the_fixture_hooks_are_inert_without_the_switch() {
    setup_repo
    unset CRAYON_TEST_HOOKS

    local point unit rc
    for point in manifest append place:1 commit cleanup; do
        unit="in${point%%:*}"
        CRAYON_CRASH_AT="$point" crayon_unit_new "$unit" "reference/$unit.rst" \
            >/dev/null 2>&1
        rc=$?
        assert_eq "$point: the crash variable is inert without the switch" "0" "$rc"
        assert_file_not_exists "$point: and nothing is left pending" \
            ".crayon/staging/$unit/pending"
    done

    # The sixth point needs a state only a rejecting hook produces; it is armed
    # by the same switch and is equally inert.
    hook_rejected_draft ina
    CRAYON_CRASH_AT=adopt "$CRAYON" resume ina --adopt --note "kept it" \
        >/dev/null 2>&1
    rc=$?
    assert_eq "adopt: the crash variable is inert without the switch" "0" "$rc"

    # CRAYON_NOW rides the same switch: `setup_repo` exports it, and with the
    # switch off the recorded timestamp must be the real one.
    crayon_unit_new nowu "reference/nowu.rst" >/dev/null 2>&1
    assert_not_contains "the deterministic timestamp is inert too" \
        "$(head -1 .crayon/units/nowu/ledger.jsonl)" \
        '"at":"2026-01-01T00:00:00+00:00"'

    export CRAYON_TEST_HOOKS=1
    cleanup
}

# --- N-38: T28 / T28b — the honest limit's findings block --------------------
#
# Contract 5.8's honest limit is the one refusal whose OUTPUT is the deliverable:
# when the tool cannot complete a transition, what it prints is all the author
# has. The assertions below are therefore as much about what is NOT printed as
# about what is — a restore recipe the evidence does not support is how an
# author loses uncommitted work on the tool's advice (T-17-27).

# The manifest, rewritten through python3 so a fixture can express "not
# canonical" and "not a prefix of the batch" exactly. `patch_manifest` in
# tests/test_crayon_acceptance.sh is the same idea; it stays there because D-10
# keeps the reviewer's file recognisable, and only the two modes this suite needs are
# repeated here.
mangle_manifest() {
    python3 -c '
import json, sys
path, mode = sys.argv[1], sys.argv[2]
manifest = json.loads(open(path, encoding="utf-8").read())
if mode == "drop-first":
    manifest["events"] = manifest["events"][1:]
elif mode == "non-canonical":
    manifest["events"] = ["{\"b\": 1, \"a\": 2}"]
open(path, "w", encoding="utf-8").write(json.dumps(manifest))
' ".crayon/staging/${1}/pending/manifest.json" "$2"
}

# Every tracked-or-untracked file in the repository, .git excluded: "no new file
# exists anywhere" is a stronger claim than "nothing under the unit directory
# changed", and it is the claim 5.8 actually makes. The suite's own stderr
# captures are excluded by name — a test that counted its own scratch file as a
# write by the tool would fail for a reason that has nothing to do with crayon.
repo_files() {
    find . -path ./.git -prune -o -type f -print |
        grep -v '^\./err-[^/]*\.txt$' | sort
}

# The four headings, in the order they were printed. Joined into one string so a
# single assertion covers presence AND order — probe 24 is an ordering claim,
# and four separate "contains" assertions would pass on any permutation.
heading_order() {
    printf '%s\n' "$1" |
        grep -E '^(uncommitted tail|paths|safety boundary|supported steps):$' |
        tr '\n' '|'
}

# One `<path>: <verdict>` row per line under the `paths:` heading.
path_rows() {
    printf '%s\n' "$1" | sed -n '/^paths:$/,/^safety boundary:$/p' |
        sed '1d;$d'
}

HEADINGS="uncommitted tail:|paths:|safety boundary:|supported steps:|"

test_n38_t28_t28b_honest_limit_findings() {
    setup_repo
    mkdir -p docs/reference

    # One fixture per detail code the contract's table carries, each produced by
    # the D-15 crash hook driving the REAL write protocol.
    crashed_unit_new nm append          # no_material  (and T28b: no ledger in HEAD)
    rm -rf .crayon/staging/nm/pending

    crashed_unit_new tu append          # tail_unknown
    mangle_manifest tu drop-first

    crashed_unit_new mi append          # material_invalid
    printf 'tampered\n' >>".crayon/staging/mi/pending/after/.crayon/units/mi/unit.md"

    crashed_unit_new ei append          # event_invalid
    mangle_manifest ei non-canonical

    local unit detail out rc before_files before_bytes second
    for unit in nm tu mi ei; do
        case "$unit" in
            nm) detail=no_material ;;
            tu) detail=tail_unknown ;;
            mi) detail=material_invalid ;;
            ei) detail=event_invalid ;;
        esac
        before_files=$(repo_files)
        before_bytes=$(resume_fingerprint "$unit")

        out=$("$CRAYON" resume "$unit" 2>"err-$unit.txt")
        rc=$?
        assert_eq "$unit: the honest limit exits 6" "6" "$rc"
        assert_json_error "$unit" "err-$unit.txt" "recovery_unsupported"
        assert_json_detail "$unit" "err-$unit.txt" "$detail"

        # Probe 24: all four headings, in contract 5.8's order, always.
        assert_eq "$unit: four headings in contract order" "$HEADINGS" \
            "$(heading_order "$out")"

        # Every path row carries exactly one of the contract's four verdicts.
        local rows bad
        rows=$(path_rows "$out")
        bad=$(printf '%s\n' "$rows" | grep -v '^$' |
            grep -cvE ': (matches recorded digest|matches HEAD|neither|unaccounted)$')
        assert_eq "$unit: every path row carries one of the four verdicts" "0" "$bad"

        # The safety boundary is stated, not implied.
        assert_contains "$unit: the boundary preserves what it cannot attribute" \
            "$out" "cannot be attributed are preserved"
        assert_contains "$unit: the boundary refuses committed history as a source" \
            "$out" "nothing is restored from committed history"

        # The point of the test: no step the evidence does not support.
        local forbidden
        for forbidden in "commit it and continue" "git checkout HEAD" \
            "git restore" "git reset --hard"; do
            assert_not_contains "$unit: stdout never says '$forbidden'" \
                "$out" "$forbidden"
            assert_not_contains "$unit: stderr never says '$forbidden'" \
                "$(cat "err-$unit.txt")" "$forbidden"
        done

        # D-08: the same facts structurally, so a skill need not parse prose.
        local paths_json
        paths_json=$(python3 -c '
import json, sys
payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
rows = payload.get("extra", payload).get("paths")
if rows is None:
    rows = payload.get("paths")
print("ABSENT" if rows is None else ";".join(
    "%s=%s" % (r["path"], r["verdict"]) for r in rows))
' "err-$unit.txt" 2>/dev/null)
        assert_not_contains "$unit: extra.paths is present" "$paths_json" "ABSENT"

        # Nothing is written — not the ledger, not a page, not a file under
        # staging, not a recovery directory the block merely suggests.
        assert_eq "$unit: no byte under the unit or staging changes" \
            "$before_bytes" "$(resume_fingerprint "$unit")"
        assert_eq "$unit: no new file appears anywhere" \
            "$before_files" "$(repo_files)"

        # A report that changes between two identical invocations is not a
        # report of what is on disk.
        second=$("$CRAYON" resume "$unit" 2>/dev/null)
        assert_eq "$unit: a second identical invocation prints the same block" \
            "$out" "$second"
    done

    # T28b: a lost declaration — no ledger in HEAD at all — is the one situation
    # 5.8 gives a concrete step for, and that step is a MOVE. `nm` above is that
    # situation: `unit new` was interrupted before its own first commit.
    out=$("$CRAYON" resume nm 2>/dev/null)
    assert_contains "T28b: the lost declaration is named" "$out" \
        "no ledger for nm is in HEAD"
    assert_contains "T28b: the step moves the unit directory aside" "$out" \
        "mv .crayon/units/nm .crayon/staging/recovery-"
    assert_not_contains "T28b: and never offers to delete it" "$out" "delete"
    assert_not_contains "T28b: nor to remove it" "$out" "rm -rf"

    # Probe 22: a path whose disk bytes match BOTH the recorded digest and HEAD
    # reports the recorded digest — first match wins in the contract's order.
    crashed_unit_new bo append
    mangle_manifest bo drop-first
    local placed
    placed=$(manifest_paths bo | sed -n 1p)
    mkdir -p "$(dirname "$placed")"
    cp ".crayon/staging/bo/pending/after/$placed" "$placed"
    git add "$placed" >/dev/null 2>&1
    git commit -q -m "the author committed the intended bytes" >/dev/null 2>&1

    out=$("$CRAYON" show bo 2>err-bo.txt)
    assert_eq "a read-only verb prints the same block" "6" "$?"
    assert_json_error "bo" "err-bo.txt" "recovery_unsupported"
    assert_eq "bo: four headings in contract order" "$HEADINGS" \
        "$(heading_order "$out")"
    assert_contains "bo: matching both reports the recorded digest" "$out" \
        "$placed: matches recorded digest"
    assert_not_contains "bo: and never reports HEAD for that path" "$out" \
        "$placed: matches HEAD"
    # Evidence, not proof — the only claim the bytes support.
    assert_contains "bo: the step says evidence, not proof" "$out" \
        "evidence, not proof"

    # Probe 21 / probe 23: the stray-material row has neither a tail nor an
    # identifiable path, and both headings are printed anyway — with an empty
    # seq list, no rows, and the terminal answer under supported steps.
    crayon_unit_new st "reference/st.rst" >/dev/null 2>&1
    python3 -c '
import json, os
pending = ".crayon/staging/st/pending"
os.makedirs(pending, exist_ok=True)
lines = [l for l in open(".crayon/units/st/ledger.jsonl", encoding="utf-8").read().split("\n") if l]
manifest = {"events": [lines[0], json.dumps({"kind": "never-landed"}, sort_keys=True)],
            "files": []}
open(os.path.join(pending, "manifest.json"), "w", encoding="utf-8").write(json.dumps(manifest))
'
    before_files=$(repo_files)
    out=$("$CRAYON" resume st 2>err-st.txt)
    assert_eq "the stray row exits 6" "6" "$?"
    assert_json_error "st" "err-st.txt" "recovery_unsupported"
    assert_eq "st: four headings in contract order" "$HEADINGS" \
        "$(heading_order "$out")"
    assert_eq "st: the tail heading is printed with an empty seq list" "" \
        "$(printf '%s\n' "$out" | sed -n '/^uncommitted tail:$/,/^paths:$/p' | sed '1d;$d')"
    assert_eq "st: the paths heading is printed with no rows" "" \
        "$(path_rows "$out" | grep -v '^$' || true)"
    assert_contains "st: no safe step can be derived, and it says so" "$out" \
        "expert intervention required"
    assert_eq "st: nothing is written" "$before_files" "$(repo_files)"
    cleanup
}

# --- VERB-06 / V-05: `verify` over real history ------------------------------
#
# The report itself is pinned check by check in tests/test_crayon_unit.py, where
# V1–V13 are pure functions of the ledger's bytes and of the event list. What
# lives HERE is what only a real repository can produce: a squash merge, a
# cherry-pick onto a diverged history, a maintenance edit committed by hand, a
# target claimed on two branches, and an uncommitted tail.
#
# V-05 (T25) is the one non-N id in this block and its function name carries
# `v05` so `tests/check_traces.py` finds it (plan 17-01's decision, restated in
# this file's header).

# A signed-off, drafted unit at `reference/<unit>.rst`.
verify_unit() {
    local unit="$1"
    crayon_unit_new "$unit" "reference/${unit}.rst" >/dev/null 2>&1
    "$CRAYON" signoff "$unit" >/dev/null 2>&1
    stage_draft "$unit" "reference/${unit}.rst" "Demo\n====\n\nThe drafted body.\n"
    "$CRAYON" draft "$unit" "$(draft_path "$unit" "reference/${unit}.rst")" \
        >/dev/null 2>&1
}

# Run `verify --json` into verify.json; echo the exit code.
verify_run() {
    "$CRAYON" verify "$1" --json >verify.json 2>verify-err.txt
    printf '%s' "$?"
}

# `<status>\t<detail>` for one check id of the last `verify --json`.
verify_check() {
    python3 -c '
import json, sys
with open("verify.json", encoding="utf-8") as handle:
    data = json.loads(handle.readline())
for row in data["checks"]:
    if row["id"] == sys.argv[1]:
        print("%s\t%s" % (row["status"], row["detail"]))
        break
else:
    print("MISSING\t")
' "$1"
}

verify_status() { verify_check "$1" | cut -f1; }
verify_detail() { verify_check "$1" | cut -f2-; }

# The verdict, and the ids of every record-integrity check that FAILED.
verify_verdict() {
    python3 -c '
import json
with open("verify.json", encoding="utf-8") as handle:
    data = json.loads(handle.readline())
print(data["verdict"])
'
}

verify_failed_ids() {
    python3 -c '
import json
with open("verify.json", encoding="utf-8") as handle:
    data = json.loads(handle.readline())
print(",".join(r["id"] for r in data["checks"] if r["status"] == "fail"))
'
}

verify_warnings() {
    python3 -c '
import json
with open("verify.json", encoding="utf-8") as handle:
    data = json.loads(handle.readline())
print(len(data.get("warnings") or []))
'
}

test_verify_v15_history_squashed() {
    setup_repo
    # A branch carrying several transitions, squash-merged: main ends up with
    # every ledger line and NO `Crayon-Seq` trailer commit behind any of them.
    git checkout -q -b work
    verify_unit alpha
    "$CRAYON" steer alpha --note "mention the flag" >/dev/null 2>&1
    git checkout -q main
    git merge -q --squash work
    git commit -q -m "squashed: the whole alpha unit"

    local rc
    rc=$(verify_run alpha)
    assert_eq "a squash merge still exits 0" "0" "$rc"
    assert_eq "no record-integrity check fails" "" "$(verify_failed_ids)"
    assert_eq "V15 warns" "warn" "$(verify_status V15)"
    assert_contains "V15 names the squashed history by its reason" \
        "$(verify_detail V15)" "history_squashed"
    # Green EXCEPT that one warning: the same rewrite must not be reported a
    # second time under V16's name (contract 5.9's history policy).
    assert_eq "V16 stays silent about the same rewrite" "ok" "$(verify_status V16)"
    assert_eq "the verdict is a warning, not a failure" "warn" "$(verify_verdict)"
    cleanup
}

test_verify_v16_cherry_pick_reports_the_diverged_reason() {
    setup_repo
    # The unit is built on a branch and cherry-picked onto a main that moved on.
    # The trailers survive the copy, so V15 is satisfied — but every recorded
    # `commit` still names the branch's HEAD, which this history never had.
    git checkout -q -b work
    verify_unit beta
    git checkout -q main
    git commit -q --allow-empty -m "unrelated work on main"
    git cherry-pick main..work >/dev/null 2>&1

    local rc
    rc=$(verify_run beta)
    assert_eq "a cherry-picked unit still exits 0" "0" "$rc"
    assert_eq "no record-integrity check fails" "" "$(verify_failed_ids)"
    assert_eq "V15 finds the trailers the cherry-pick copied" "ok" \
        "$(verify_status V15)"
    assert_eq "V16 warns" "warn" "$(verify_status V16)"
    assert_contains "V16 names the divergence by its reason" \
        "$(verify_detail V16)" "ledger_diverged"
    cleanup
}

test_verify_maintenance_edit_is_drifted_never_fail() {
    setup_repo
    verify_unit gamma
    "$CRAYON" review gamma --verdict accept --note "ship it" >/dev/null 2>&1

    # A later hand edit to the published page, committed like any other change.
    printf 'Demo\n====\n\nEdited by a maintainer.\n' >docs/reference/gamma.rst
    git add docs/reference/gamma.rst
    git commit -q -m "docs: tighten the gamma page"

    local rc
    rc=$(verify_run gamma)
    assert_eq "a maintenance edit still exits 0" "0" "$rc"
    assert_eq "no record-integrity check fails" "" "$(verify_failed_ids)"
    assert_eq "V14 reports the page as drifted" "warn" "$(verify_status V14)"
    assert_contains "V14 says drifted, not failed" "$(verify_detail V14)" "drifted"
    assert_contains "V14 names the commit that holds the edit" \
        "$(verify_detail V14)" "drifted (committed in"
    cleanup
}

test_verify_v17_ignore_and_attributes() {
    setup_repo
    verify_unit delta

    # `setup_repo` writes no .gitignore — the staging path is the repository's
    # to ignore, not the tool's — so the INFO-level check reports it missing.
    verify_run delta >/dev/null
    assert_eq "V17 warns while the staging path is not ignored" "warn" \
        "$(verify_status V17)"
    assert_contains "V17 names the staging path" "$(verify_detail V17)" \
        ".crayon/staging"

    # The ledger's text attribute IS the tool's, written by `unit new`.
    assert_file_contains "the tool pinned the attribute" ".crayon/.gitattributes" \
        "*.jsonl -text"

    printf '.crayon/staging/\n' >.gitignore
    git add .gitignore
    git commit -q -m "ignore the crayon staging path"
    verify_run delta >/dev/null
    assert_eq "V17 clears once both are in place" "ok" "$(verify_status V17)"

    # Remove the attribute file and the same check names the other half.
    git rm -q .crayon/.gitattributes
    git commit -q -m "drop the attributes"
    verify_run delta >/dev/null
    assert_eq "V17 warns again" "warn" "$(verify_status V17)"
    assert_contains "V17 names the unpinned text attribute" \
        "$(verify_detail V17)" "jsonl"
    cleanup
}

test_verify_v18_target_overlap() {
    setup_repo
    # No single invocation can produce this: the claim policy refuses a target
    # another live unit holds. A MERGE can, which is why V18 exists.
    git checkout -q -b left
    crayon_unit_new alpha "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff alpha >/dev/null 2>&1
    git checkout -q main
    git checkout -q -b right
    crayon_unit_new beta "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff beta >/dev/null 2>&1
    git checkout -q left
    git merge -q --no-edit right

    verify_run alpha >/dev/null
    assert_eq "V18 warns on the overlap" "warn" "$(verify_status V18)"
    assert_contains "V18 names this unit" "$(verify_detail V18)" "alpha"
    assert_contains "V18 names the other one" "$(verify_detail V18)" "beta"
    assert_contains "V18 names the target they share" "$(verify_detail V18)" \
        "reference/shared.rst"

    "$CRAYON" unit retire beta --note "superseded by alpha" >/dev/null 2>&1
    verify_run alpha >/dev/null
    assert_eq "retiring the sibling releases the claim" "ok" "$(verify_status V18)"
    cleanup
}

# CR-03: a unit id is contributor content, so default `verify` names it as
# written. A timestamp id holds a 12-digit run that the plain-words table's
# digest rule used to cut to seven characters, naming a unit that does not exist.
test_verify_keeps_a_timestamp_unit_id_as_written() {
    setup_repo
    git checkout -q -b left
    crayon_unit_new release-202609181200 "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff release-202609181200 >/dev/null 2>&1
    git checkout -q main
    git checkout -q -b right
    crayon_unit_new cfg "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff cfg >/dev/null 2>&1
    git checkout -q left
    git merge -q --no-edit right

    local out rc
    out=$("$CRAYON" verify release-202609181200 2>/dev/null)
    rc=$?
    assert_eq "verify exits 0 on a target overlap" "0" "$rc"
    assert_eq "the report names both units and the page exactly as written" "1" \
        "$(printf '%s\n' "$out" | grep -cFx \
            '  pages another unit also claims: release-202609181200 and cfg both claim reference/shared.rst')"
    cleanup
}

test_verify_v19_context_digests() {
    setup_repo
    printf 'the source of record\n' >workshop.json
    git add workshop.json
    git commit -q -m "add a source"
    crayon_unit_new epsilon "reference/epsilon.rst" --source workshop.json \
        >/dev/null 2>&1
    "$CRAYON" signoff epsilon >/dev/null 2>&1

    verify_run epsilon >/dev/null
    assert_eq "V19 is clean while the source is unchanged" "ok" \
        "$(verify_status V19)"

    printf 'the source of record, revised\n' >workshop.json
    verify_run epsilon >/dev/null
    assert_eq "V19 warns once the source moves under the signoff" "warn" \
        "$(verify_status V19)"
    assert_contains "V19 names the source" "$(verify_detail V19)" "workshop.json"

    # A stale unit plan is the second half of the same check, by name.
    git checkout -q -- workshop.json
    printf '# Plan\n\nA hand-edited outline.\n' >>.crayon/units/epsilon/unit.md
    verify_run epsilon >/dev/null
    assert_eq "V19 warns on a stale plan" "warn" "$(verify_status V19)"
    assert_contains "V19 names plan_stale" "$(verify_detail V19)" "plan_stale"
    cleanup
}

test_v05_t25_unknown_kind_warns_once() {
    setup_repo
    verify_unit zeta

    # Two events of a kind this build does not know, appended through the tool's
    # own chain writer so the record stays canonical and linked. One of them
    # also carries 5.9's reserved `superseded_by`, which is parsed and NOT
    # evaluated.
    python3 - "$CRAYON" zeta <<'PY'
import importlib.machinery, importlib.util, json, os, sys

loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

unit = sys.argv[2]
path = module.ledger_path(os.getcwd(), unit)
records = module.read_events(path, unit)
last_line = records[-1][1]
seq = records[-1][0]["seq"] + 1
events = []
for offset in range(2):
    event = {
        "kind": "telemetry",
        "seq": seq + offset,
        "prev": None,
        "at": "2026-01-01T00:00:00+00:00",
        "actor": {"name": "Test Author", "email": "test@example.com"},
        "tool_version": module.__version__,
        "contract": module.CONTRACT,
        "commit": None,
        "note": "recorded by a later tool",
    }
    if offset:
        event["superseded_by"] = seq
    events.append(event)
events[0]["prev"] = module.chain_prev(last_line)
lines = []
previous = last_line
for event in events:
    event["prev"] = module.chain_prev(previous)
    line = module.canonical_line(event)
    lines.append(line)
    previous = line
module.append_batch(path, lines)
PY
    git add .crayon
    git commit -q -m "a later tool wrote two events"

    local rc
    rc=$(verify_run zeta)
    assert_eq "an unknown kind does not refuse the verb" "0" "$rc"
    assert_eq "no record-integrity check fails" "" "$(verify_failed_ids)"
    # TWO unknown events, exactly ONE warning about them (contract 5.9).
    assert_eq "exactly one warning, however many unknown events" "1" \
        "$(verify_warnings)"
    local plain
    plain=$("$CRAYON" verify zeta 2>/dev/null)
    assert_contains "the warning names the kind" "$plain" "telemetry"
    assert_eq "the default report opens on what needs a look" \
        "The record is intact; these need a look:" "$(printf '%s\n' "$plain" | sed -n 1p)"
    assert_plain "the warned report speaks plainly" "$plain"

    # The gates ran over the KNOWN kinds only: V7 in particular did not read the
    # two telemetry events as generations that skipped their steering.
    assert_eq "V7 is unaffected by the unknown kinds" "ok" "$(verify_status V7)"
    assert_eq "V5 is unaffected by the unknown kinds" "ok" "$(verify_status V5)"
    assert_eq "the verdict is the warning and nothing worse" "warn" \
        "$(verify_verdict)"
    cleanup
}

test_verify_runs_on_a_unit_with_an_uncommitted_tail() {
    setup_repo
    crashed_unit_new eta append
    assert_file_exists "the tail is on disk" ".crayon/units/eta/ledger.jsonl"

    # Every other read surface refuses at exit 6 before a single check runs.
    "$CRAYON" show eta >/dev/null 2>show-err.txt
    assert_eq "show refuses the same unit" "6" "$?"

    local rc
    rc=$(verify_run eta)
    assert_eq "verify reports instead of refusing" "0" "$rc"
    assert_eq "V1 ran" "ok" "$(verify_status V1)"
    assert_eq "V2 ran" "ok" "$(verify_status V2)"
    assert_eq "V3 ran" "ok" "$(verify_status V3)"
    assert_eq "V4 ran" "ok" "$(verify_status V4)"
    cleanup
}


# --- migrated from tests/test_crayon_acceptance.sh in plan 17-11 (D-10) ------
#
# The 181 bodies below were written in the acceptance file and moved here
# unchanged: D-10 makes that file the reviewer's A-01 … A-35 and nothing else. Every
# function that a trace-table row names now carries its N-id and its trace ids
# (D-09), so tests/check_traces.py finds it by grep; the rest keep the
# descriptive names they were written with, because no trace row names them.
# Not one assertion changed in the move.

# --- J1: the tracer journey, end to end --------------------------------------

test_j1_unit_new_end_to_end() {
    setup_repo
    local before
    before=$(git rev-list --count HEAD)

    # An unrelated uncommitted edit INSIDE docs/ — audit defect 4 (RESEARCH P-12).
    printf 'untouched by crayon\n' >docs/unrelated-page.md

    local out rc
    out=$(crayon_unit_new demo-unit "reference/demo.rst" 2>/tmp/crayon-j1-err.$$)
    rc=$?
    assert_eq "J1 exits 0" "0" "$rc"
    assert_eq "J1 prints exactly one stdout line" "1" "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "J1 response routes to sign_off" "$out" "Next: sign_off"
    assert_eq "J1 response ends with the routed token" "Next: sign_off" "${out##* · }"

    assert_file_exists "J1 writes unit.md" ".crayon/units/demo-unit/unit.md"
    local reparsed
    reparsed=$(python3 -c '
import importlib.machinery, importlib.util, json, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
text = open(sys.argv[2], encoding="utf-8").read()
front, body = module.parse_unit_md(text)
print(json.dumps([front["title"], front["intent"], front["targets"]]))
' "$CRAYON" ".crayon/units/demo-unit/unit.md" 2>&1)
    assert_eq "J1 unit.md re-parses to the declared frontmatter" \
        '["Demo", "reference", ["reference/demo.rst"]]' "$reparsed"

    assert_eq "J1 ledger holds exactly two lines" "2" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    local line1 line2
    line1=$(ledger_line demo-unit 1)
    line2=$(ledger_line demo-unit 2)
    assert_eq "J1 line 1 is the ledger event" "ledger" "$(printf '%s' "$line1" | json_field kind)"
    assert_eq "J1 line 1 seq is 0" "0" "$(printf '%s' "$line1" | json_field seq)"
    assert_eq "J1 line 1 prev is null" "null" "$(printf '%s' "$line1" | json_field prev)"
    assert_eq "J1 line 1 carries the contract number" "1" \
        "$(printf '%s' "$line1" | json_field contract)"
    assert_eq "J1 line 2 is unit-declared" "unit-declared" \
        "$(printf '%s' "$line2" | json_field kind)"
    assert_eq "J1 line 2 seq is 1" "1" "$(printf '%s' "$line2" | json_field seq)"
    assert_eq "J1 line 2 carries the contract number" "1" \
        "$(printf '%s' "$line2" | json_field contract)"
    assert_eq "J1 line 2 prev is sha256 of line 1's bytes without the LF" \
        "$(sha256_of_text "$line1")" "$(printf '%s' "$line2" | json_field prev)"

    assert_file_contains "J1 pins jsonl as binary" ".crayon/.gitattributes" "*.jsonl -text"

    local after
    after=$(git rev-list --count HEAD)
    assert_eq "J1 makes exactly one commit" "$((before + 1))" "$after"
    assert_eq "J1 commit subject" "crayon: declared demo-unit" "$(git log -1 --format=%s)"
    assert_eq "J1 Crayon-Unit trailer" "demo-unit" \
        "$(git log -1 --format='%(trailers:key=Crayon-Unit,valueonly)' | tr -d '\n')"
    assert_eq "J1 Crayon-Phase trailer" "declared" \
        "$(git log -1 --format='%(trailers:key=Crayon-Phase,valueonly)' | tr -d '\n')"
    assert_eq "J1 Crayon-Seq trailer spans the batch" "0-1" \
        "$(git log -1 --format='%(trailers:key=Crayon-Seq,valueonly)' | tr -d '\n')"
    local head16
    head16=$(git log -1 --format='%(trailers:key=Crayon-Head,valueonly)' | tr -d '\n')
    assert_eq "J1 Crayon-Head is 16 hex characters" "yes" \
        "$(printf '%s' "$head16" | grep -qE '^[0-9a-f]{16}$' && echo yes || echo no)"

    local committed
    committed=$(git show --name-only --format= HEAD)
    assert_contains "J1 commits the ledger" "$committed" ".crayon/units/demo-unit/ledger.jsonl"
    assert_contains "J1 commits unit.md" "$committed" ".crayon/units/demo-unit/unit.md"
    assert_not_contains "J1 never sweeps an unrelated docs/ edit" \
        "$committed" "docs/unrelated-page.md"

    assert_file_not_exists "J1 deletes pending/ on success" \
        ".crayon/staging/demo-unit/pending"
    rm -f /tmp/crayon-j1-err.$$
    cleanup
}

test_unit_new_twice_refuses_unit_exists() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    local before
    before=$(git rev-list --count HEAD)
    local ledger_before
    ledger_before=$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.jsonl)")

    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a second unit new exits 2" "2" "$rc"
    assert_json_error "unit_exists" "err.txt" "unit_exists"
    assert_eq "a refused unit new makes no commit" "$before" "$(git rev-list --count HEAD)"
    assert_eq "a refused unit new leaves the ledger byte-unchanged" "$ledger_before" \
        "$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.jsonl)")"
    cleanup
}

test_symlinked_docs_root_refuses_bad_write_path() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    mkdir -p "$outside/real-docs"
    rm -rf docs
    ln -s "$outside/real-docs" docs

    crayon_unit_new sym-unit "reference/x.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a symlinked docs root exits 2" "2" "$rc"
    assert_json_error "symlinked docs root" "err.txt" "bad_write_path"
    assert_file_not_exists "a refused unit new writes no unit dir" ".crayon/units/sym-unit"
    assert_file_not_exists "a refused unit new writes no page" "$outside/real-docs/reference"
    rm -rf "$outside"
    cleanup
}

# CR-01: containment is checked at the ONE choke point every write passes
# through, not only at declaration time. A docs *subdirectory* re-pointed
# between signoff and draft used to escape: the existing symlinked-docs-root
# test only covers the root, and `draft` never re-checked its destinations.
test_symlinked_docs_subdir_refuses_draft_before_any_write() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    mkdir -p "$outside/evil"
    crayon_unit_new esc-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff esc-unit >/dev/null 2>&1
    stage_draft esc-unit "reference/demo.rst" "PWNED\n"
    # The target was containable at signoff; it is not any more.
    rm -rf docs/reference
    ln -s "$outside/evil" docs/reference
    local ledger_before head_before
    ledger_before=$(ledger_digest esc-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft esc-unit "$(draft_path esc-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a re-pointed docs subdir exits 2" "2" "$rc"
    assert_json_error "symlinked docs subdir" "err.txt" "bad_write_path"
    assert_file_not_exists "nothing is written outside the repository" \
        "$outside/evil/demo.rst"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest esc-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "the refusal leaves no pending/" \
        ".crayon/staging/esc-unit/pending"
    rm -rf "$outside"
    cleanup
}

# CR-01: the `.crayon/` symlink guard used to live in `cmd_unit_new` alone, so
# every other mutating verb appended the record through the link.
test_symlinked_crayon_dir_refuses_every_mutating_verb() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    crayon_unit_new link-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff link-unit >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest link-unit)
    head_before=$(git rev-parse HEAD)
    mv .crayon "$outside/crayon-real"
    ln -s "$outside/crayon-real" .crayon

    "$CRAYON" steer link-unit --note "second thoughts" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "steer through a symlinked .crayon exits 2" "2" "$rc"
    assert_json_error "symlinked .crayon (steer)" "err.txt" "bad_write_path"
    assert_eq "the steer refusal appends nothing outside the repository" \
        "$ledger_before" "$(ledger_digest link-unit)"

    printf '# Plan\n\nA revised outline.\n' |
        "$CRAYON" unit edit link-unit --body-file - >/dev/null 2>err2.txt
    assert_eq "unit edit through a symlinked .crayon exits 2" "2" "$?"
    assert_json_error "symlinked .crayon (unit edit)" "err2.txt" "bad_write_path"
    assert_eq "the edit refusal appends nothing outside the repository" \
        "$ledger_before" "$(ledger_digest link-unit)"
    assert_eq "no refusal commits anything" "$head_before" "$(git rev-parse HEAD)"

    rm -f .crayon
    mv "$outside/crayon-real" .crayon
    rm -rf "$outside"
    cleanup
}

# CR-02: contract 5.6's write-destination row has five clauses, and the fifth
# is "pending/evidence inside `.crayon/staging/`". `guard_crayon_root` stated only
# the first, and the sole implementation of the fifth
# (`contained(root/.crayon/staging, pending)`) resolved BOTH operands through the
# very link it was meant to catch — so a symlinked `.crayon/staging` produced a
# complete, exit-0, silently successful `draft` that wrote its lock, its
# pending/before/after material and the page bytes outside the repository. One
# case per link position; the child links are the regression.

# Every regular file under $1 as "relative-path sha256", sorted. WR-07: the
# fixture deliberately moves a POPULATED `.crayon` child out of the repository,
# so "the tree out here is empty" is not the property under test and never was
# -- "crayon added or changed nothing out here" is. A snapshot comparison says
# that, and unlike the old post-loop `find`, it can fail.
outside_digest() {
    python3 - "$1" <<'PY'
import hashlib, os, sys
root = sys.argv[1]
rows = []
for base, _dirs, names in os.walk(root):
    for name in names:
        full = os.path.join(base, name)
        if os.path.islink(full) or not os.path.isfile(full):
            continue
        with open(full, "rb") as handle:
            rows.append("%s %s" % (os.path.relpath(full, root),
                                   hashlib.sha256(handle.read()).hexdigest()))
print(chr(10).join(sorted(rows)))
PY
}

test_a_symlinked_crayon_child_refuses_and_writes_nothing_outside() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    crayon_unit_new st-unit "reference/st.rst" >/dev/null 2>&1
    "$CRAYON" signoff st-unit >/dev/null 2>&1
    stage_draft st-unit "reference/st.rst" "PAGE BYTES\n"
    local ledger_before head_before
    ledger_before=$(ledger_digest st-unit)
    head_before=$(git rev-parse HEAD)

    local relative
    for relative in ".crayon/staging" ".crayon/units"; do
        local target
        target="$outside/$(basename "$relative")-real"
        rm -rf "$target"
        # The lock already exists from `unit new`/`signoff` and would move out
        # WITH the directory, so "no lock outside" could not tell "crayon made
        # one through the link" from "the fixture carried one out there". Gone
        # first, its reappearance means exactly one thing.
        rm -f .crayon/staging/lock
        mv "$relative" "$target"
        ln -s "$target" "$relative"

        local outside_before
        outside_before=$(outside_digest "$outside")

        "$CRAYON" draft st-unit "$(draft_path st-unit reference/st.rst)" \
            >/dev/null 2>err.txt
        assert_eq "draft through a symlinked $relative exits 2" "2" "$?"
        assert_json_error "symlinked $relative" "err.txt" "bad_write_path"
        assert_json_detail "symlinked $relative names the link" "err.txt" \
            "$relative/ is a symlink or resolves outside the repository"

        # WR-07: asserted HERE, with the link STILL in place. Run after the
        # restore below -- as they were -- everything crayon wrote through the
        # link has just been moved back into the repository with its target, so
        # `find "$outside"` was empty by construction and both containment
        # assertions passed while the escape was live.
        #
        # The lock is the earliest thing a mutating verb writes, so a refusal
        # that only fired later would already have created it through the link.
        assert_file_not_exists "$relative: no lock is created outside" \
            "$target/lock"
        assert_eq "$relative: crayon changed nothing outside the repository" \
            "$outside_before" "$(outside_digest "$outside")"

        rm -f "$relative"
        mv "$target" "$relative"

        assert_eq "$relative: no refusal appends to the ledger" \
            "$ledger_before" "$(ledger_digest st-unit)"
        assert_eq "$relative: no refusal commits anything" "$head_before" \
            "$(git rev-parse HEAD)"
        assert_file_not_exists "$relative: no page is published" \
            "docs/reference/st.rst"

        # Each link position starts from the same state. Without this, with the
        # guard weakened the `.crayon/staging` case published the page and
        # committed, and the `.crayon/units` case then returned identical_draft
        # (3) instead of exercising its own escape -- so "one case per link
        # position" was not what the loop measured.
        git reset -q --hard "$head_before"
        rm -f docs/reference/st.rst
        stage_draft st-unit "reference/st.rst" "PAGE BYTES\n"
    done

    rm -rf "$outside"
    cleanup
}

# CR-03: CRAYON_ROOTS guards three DIRECTORIES, and `os.open` follows symlinks,
# so a link at the lock file's own path cleared every directory check and still
# created the repository's write mutex at an arbitrary absolute path — on the
# exit-0 SUCCESS path, with no diagnostic of any kind. The assertions below run
# while the link is still in place, so `find` cannot be empty by construction
# (WR-07).
test_a_symlinked_lock_file_refuses_and_creates_nothing_outside() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    crayon_unit_new lk-unit "reference/lk.rst" >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest lk-unit)
    head_before=$(git rev-parse HEAD)

    rm -f .crayon/staging/lock
    ln -s "$outside/evil-lock" .crayon/staging/lock

    "$CRAYON" signoff lk-unit >/dev/null 2>err.txt
    assert_eq "signoff through a symlinked lock exits 2" "2" "$?"
    assert_json_error "symlinked lock" "err.txt" "bad_write_path"
    assert_json_detail "symlinked lock names the lock" "err.txt" \
        ".crayon/staging/lock is a symlink"

    # Asserted with the link STILL in place: the mutex must not have been
    # created through it, and nothing else may have escaped either.
    assert_file_not_exists "no lock is created through the link" "$outside/evil-lock"
    assert_eq "nothing at all is written outside the repository" "" \
        "$(find "$outside" -type f 2>/dev/null)"
    assert_eq "a refused lock appends nothing to the ledger" "$ledger_before" \
        "$(ledger_digest lk-unit)"
    assert_eq "a refused lock commits nothing" "$head_before" "$(git rev-parse HEAD)"

    rm -f .crayon/staging/lock
    rm -rf "$outside"
    cleanup
}

# WR-15: the CR-03 fix wrapped `os.open` in a blanket `except OSError` that
# reported `.crayon/staging/lock cannot be opened as a real file` — wording only
# true for ELOOP/EISDIR/ENOTDIR. Every other failure (permissions, a read-only
# filesystem, ENOSPC, EMFILE) got a cause that is FALSE, and strictly worse than
# what `main`'s OSError backstop said before the commit. That is the same
# "invented cause" defect WR-01 and WR-12 were filed for.
test_wr15_an_unopenable_lock_reports_the_real_fault_not_an_invented_one() {
    setup_repo
    crayon_unit_new perm-unit "reference/perm.rst" >/dev/null 2>&1
    if [ "$(id -u)" = "0" ]; then
        # Running as root, EACCES is not reachable; record the skip as a pass so
        # the "no assertions" guard does not read it as a vacuous test.
        assert_eq "skipped as root: EACCES is unreachable" "0" "0"
        cleanup
        return 0
    fi

    rm -f .crayon/staging/lock
    chmod 500 .crayon/staging
    "$CRAYON" signoff perm-unit >/dev/null 2>err.txt
    local rc=$?
    chmod 700 .crayon/staging

    assert_eq "an unwritable staging dir still exits 2" "2" "$rc"
    assert_json_error "an unwritable staging dir" "err.txt" "bad_target"
    assert_contains "the refusal names the real errno" "$(cat err.txt)" \
        "PermissionError"
    assert_contains "the refusal points at permissions, not at the file's kind" \
        "$(cat err.txt)" "check the path's permissions and the filesystem"
    assert_not_contains "the refusal does not claim the lock is not a real file" \
        "$(cat err.txt)" "must be a real file inside the repository"
    # WR-22: this test used to assert the errno and the hint and NOT the absence
    # of the absolute path, so it pinned in the leak `ledger_label` exists to
    # close (WR-10). `OSError.__str__` embeds the absolute filename, and the
    # WR-15 re-raise routes the common permission case through this arm.
    assert_not_contains "the refusal does not leak the absolute path" \
        "$(cat err.txt)" "$PWD"
    assert_contains "it still names the lock, repo-relatively" \
        "$(cat err.txt)" ".crayon/staging/lock"
    cleanup
}

# The other half of the same branch: the three errnos the wording IS true for
# must still be reported as what they are, or the fix would have traded one
# false diagnostic for a missing one.
test_wr15_a_lock_path_that_is_a_directory_is_still_bad_write_path() {
    setup_repo
    crayon_unit_new dir-unit "reference/dir.rst" >/dev/null 2>&1

    rm -f .crayon/staging/lock
    mkdir -p .crayon/staging/lock
    "$CRAYON" signoff dir-unit >/dev/null 2>err.txt
    local rc=$?
    rmdir .crayon/staging/lock

    assert_eq "a directory at the lock path exits 2" "2" "$rc"
    assert_json_error "a directory at the lock path" "err.txt" "bad_write_path"
    assert_json_detail "the refusal names the errno it identified" "err.txt" \
        ".crayon/staging/lock is not a real file (EISDIR)"
    cleanup
}

test_leading_docs_target_refuses_bad_write_path() {
    setup_repo
    crayon_unit_new dd-unit "docs/reference/x.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a leading docs/ target exits 2" "2" "$rc"
    assert_json_error "docs/docs trap" "err.txt" "bad_write_path"
    assert_file_not_exists "a refused unit new writes no unit dir" ".crayon/units/dd-unit"
    cleanup
}

# WR-01: a source was only passed through control-character hygiene, so an
# absolute or traversing path was digested by `sign_sources` and both the raw
# path and its sha256 were COMMITTED into the signoff's `context` map — an
# existence-and-content oracle for files outside the repository, and a V19
# check over paths that are not part of the repository at all.
test_an_absolute_or_traversing_source_is_refused() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    printf 'OUTSIDE SECRET\n' >"$outside/secret.txt"

    crayon_unit_new abs-unit "reference/a.rst" --source "/etc/hostname" \
        >/dev/null 2>err.txt
    assert_eq "an absolute source exits 2" "2" "$?"
    assert_json_error "absolute source" "err.txt" "unit_invalid"
    assert_file_not_exists "nothing is declared" ".crayon/units/abs-unit"

    crayon_unit_new trav-unit "reference/t.rst" --source "../../../../etc/hostname" \
        >/dev/null 2>err2.txt
    assert_eq "a traversing source exits 2" "2" "$?"
    assert_json_error "traversing source" "err2.txt" "unit_invalid"
    assert_file_not_exists "nothing is declared" ".crayon/units/trav-unit"

    crayon_unit_new ok-unit "reference/o.rst" --source "docs/index.md" >/dev/null 2>&1
    assert_eq "a repo-relative source is accepted" "0" "$?"

    printf 'x\n' |
        "$CRAYON" unit edit ok-unit --source "/etc/hostname" --body-file - \
            >/dev/null 2>err3.txt
    assert_eq "unit edit refuses an absolute source too" "2" "$?"
    assert_json_error "absolute source (edit)" "err3.txt" "unit_invalid"
    rm -rf "$outside"
    cleanup
}

# WR-01: `unit.md` is a plain file an author may hand-edit and `signoff` reads
# it fresh, so declaration-time validation cannot be the only guard.
# WR-05: the first fix recorded the outside source as {path, commit: null} with
# no digest and carried on, so signoff SUCCEEDED with no indication that a
# declared source had never been read — and `commit: null` was already this
# record's encoding for "an in-repo source nothing pins", so one value carried
# two incompatible meanings and V19 saw an absence it could not attribute.
# Silently downgrading a provenance record is the failure mode the design is
# against. The answer is the one `unit new` / `unit edit` give for the same
# string.
test_signoff_refuses_a_source_outside_the_repository() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    printf 'OUTSIDE SECRET\n' >"$outside/secret.txt"
    crayon_unit_new hand-unit "reference/h.rst" --source "docs/index.md" >/dev/null 2>&1
    # Hand-edit the plan file past the declaration-time rule.
    hand_edit_source hand-unit "docs/index.md" "$outside/secret.txt"
    local ledger_before head_before
    ledger_before=$(ledger_digest hand-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" signoff hand-unit >/dev/null 2>err.txt
    assert_eq "signoff refuses rather than signing a source it cannot read" "2" "$?"
    assert_json_error "outside source" "err.txt" "unit_invalid"
    assert_contains "the refusal names the source flag" "$(json_field hint <err.txt)" \
        "--source"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest hand-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_not_contains "nothing outside the repository is digested" \
        "$(cat .crayon/units/hand-unit/ledger.jsonl)" "secret.txt"

    # And the same string refused at declaration time, so the two answers agree.
    crayon_unit_new decl-unit "reference/d.rst" --source "$outside/secret.txt" \
        >/dev/null 2>err2.txt
    assert_eq "the declaring verb refuses it too" "2" "$?"
    assert_json_error "outside source at declaration" "err2.txt" "unit_invalid"

    rm -rf "$outside"
    cleanup
}

# WR-05: `commit: null` now means exactly one thing — an in-repo source that
# nothing pins — because the value an out-of-repo source used to share with it
# can no longer be recorded at all.
test_an_uncommitted_in_repo_source_still_signs_with_a_null_commit() {
    setup_repo
    printf 'not yet committed\n' >docs/fresh.md
    crayon_unit_new fresh-unit "reference/f.rst" --source "docs/fresh.md" >/dev/null 2>&1
    "$CRAYON" signoff fresh-unit >/dev/null 2>&1
    assert_eq "an uncommitted in-repo source still signs" "0" "$?"
    local commits
    commits=$(ledger_line fresh-unit 3 | python3 -c '
import json, sys
print(json.dumps([e["commit"] for e in json.loads(sys.stdin.read())["sources"]]))
')
    assert_eq "nothing pins it, so the commit is null" "[null]" "$commits"
    local digested
    digested=$(ledger_line fresh-unit 3 | python3 -c '
import json, sys
print(json.dumps(sorted(json.loads(sys.stdin.read()).get("context") or {})))
')
    assert_eq "but it IS digested — it was read" '["docs/fresh.md"]' "$digested"

    # WR-13's invariant, on the path that is SUPPOSED to succeed: `sources` and
    # `context` are the same key set by construction. Without it the two
    # assertions above pass for a record that pinned a commit and read nothing.
    local keys
    keys=$(ledger_line fresh-unit 3 | python3 -c '
import json, sys
event = json.loads(sys.stdin.read())
print(json.dumps([
    sorted(s["path"] for s in event["sources"]),
    sorted(event.get("context") or {}),
]))
')
    assert_eq "every recorded source is a digested source" \
        '[["docs/fresh.md"], ["docs/fresh.md"]]' "$keys"
    cleanup
}

# WR-13: WR-05's fix closed the out-of-repo STRING and stopped there. Two
# in-repo cases still reached `sources.append(...)` with `digest_file() is
# None` and both succeeded at exit 0 with no diagnostic -- `context: {}`,
# verbatim the state the first review called "silently downgrading a
# provenance record".
test_signoff_refuses_a_source_it_never_read() {
    setup_repo
    # WR-17 (phase 18): the declaring verbs now apply the same two filesystem
    # rules, so neither source below can be DECLARED any more. Both are reached
    # the way the out-of-repo case above is -- by hand-editing the plan file
    # past the declaration-time rule -- because `unit.md` is a plain file an
    # author may edit and `signoff` re-reads it fresh. The declaration-time
    # refusals are asserted at the bottom of this function, so the two guards
    # are pinned together rather than one replacing the other.
    crayon_unit_new gone-unit "reference/g.rst" \
        --source "docs/index.md" >/dev/null 2>&1
    hand_edit_source gone-unit "docs/index.md" "docs/never-existed.md"
    local ledger_before head_before
    ledger_before=$(ledger_digest gone-unit)
    head_before=$(git rev-parse HEAD)

    # A. a source that does not exist. It used to sign as `{"commit": null}`
    # with no digest -- which is the encoding for "an in-repo source nothing
    # pins", so one value carried two incompatible meanings again.
    "$CRAYON" signoff gone-unit >/dev/null 2>err.txt
    assert_eq "a missing source refuses rather than signing" "2" "$?"
    assert_json_error "missing source" "err.txt" "unit_invalid"
    assert_contains "the refusal names the source flag" \
        "$(json_field hint <err.txt)" "--source"
    assert_contains "the refusal names the source it could not read" \
        "$(json_field detail <err.txt)" "docs/never-existed.md"
    assert_eq "the refusal appends nothing" "$ledger_before" \
        "$(ledger_digest gone-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"

    # B. a source naming a DIRECTORY. Worse than A: `git log` pins a directory
    # happily, so this recorded a real commit hash -- an assertion of
    # provenance -- while `digest_file` returned None and nothing was read.
    crayon_unit_new dir-unit "reference/d.rst" --source "docs/index.md" >/dev/null 2>&1
    hand_edit_source dir-unit "docs/index.md" "docs"
    "$CRAYON" signoff dir-unit >/dev/null 2>err2.txt
    assert_eq "a directory source refuses rather than signing" "2" "$?"
    assert_json_error "directory source" "err2.txt" "unit_invalid"
    assert_contains "the refusal names the directory" \
        "$(json_field detail <err2.txt)" "'docs'"
    assert_not_contains "no commit hash is asserted for it" \
        "$(cat .crayon/units/dir-unit/ledger.jsonl)" '"context"'

    # WR-17 (phase 18): and the declaring verb refuses both of them, so the
    # unsignable plan the two arms above reach by hand can no longer be
    # committed by a command. `--source` REPLACES the list, so `unit edit` is
    # the named way back for a plan that already carries one.
    local decl_head
    decl_head=$(git rev-parse HEAD)
    crayon_unit_new miss-unit "reference/m.rst" --source "docs/never-existed.md" \
        >/dev/null 2>err3.txt
    assert_eq "declaring a missing source refuses" "2" "$?"
    assert_json_error "missing source at declaration" "err3.txt" "unit_invalid"
    assert_file_not_exists "and writes no unit" ".crayon/units/miss-unit"
    crayon_unit_new dird-unit "reference/dd.rst" --source "docs" >/dev/null 2>err4.txt
    assert_eq "declaring a directory source refuses" "2" "$?"
    assert_json_error "directory source at declaration" "err4.txt" "unit_invalid"
    assert_file_not_exists "and writes no unit" ".crayon/units/dird-unit"
    assert_eq "neither declaration committed anything" "$decl_head" \
        "$(git rev-parse HEAD)"
    "$CRAYON" unit edit gone-unit --source "docs/index.md" >/dev/null 2>&1
    assert_eq "unit edit repoints a source that cannot be read" "0" "$?"
    cleanup
}

# WR-04 / WR-10: `find_claim` wrapped the sibling's `unit_state` in
# `except ValueError: continue`, and the only ValueError that reached it was
# `json.loads` failing inside `read_events` — exactly the corrupt sibling the
# contract's first mechanism promises will refuse loudly. Its targets vanished
# from the claim set instead, so a second unit claimed a target a live unit
# holds. `read_events` now raises `ledger_corrupt` (6), not a bare ValueError
# that `main` turned into `bad_target`/2 with a JSON-decoder message.
test_a_corrupt_sibling_ledger_never_silently_waives_the_claim_policy() {
    setup_repo
    crayon_unit_new holder-unit "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff holder-unit >/dev/null 2>&1

    # The claim policy holds while the sibling is readable.
    crayon_unit_new rival-unit "reference/shared.rst" >/dev/null 2>err0.txt
    assert_eq "a claimed target exits 1" "1" "$?"
    assert_json_error "target_claimed" "err0.txt" "target_claimed"

    printf 'this is not json\n' >>.crayon/units/holder-unit/ledger.jsonl
    crayon_unit_new rival-unit "reference/shared.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an unreadable sibling exits 6, not 0" "6" "$rc"
    assert_json_error "ledger_corrupt (sibling)" "err.txt" "ledger_corrupt"
    assert_file_contains "the refusal names the sibling" "err.txt" "holder-unit"
    assert_file_not_exists "the rival unit is never declared" ".crayon/units/rival-unit"
    cleanup
}

# WR-10: the unit's OWN corrupt ledger is exit 6 with a line number, not
# exit 2 "bad input" with a JSON-decoder message.
test_a_corrupt_ledger_is_ledger_corrupt_not_bad_target() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    printf 'not json at all\n' >>.crayon/units/demo-unit/ledger.jsonl

    "$CRAYON" show demo-unit >/dev/null 2>err.txt
    assert_eq "a corrupt ledger exits 6" "6" "$?"
    assert_json_error "ledger_corrupt" "err.txt" "ledger_corrupt"
    cleanup
}

test_bad_unit_id_and_bad_target_are_refused() {
    setup_repo
    crayon_unit_new "Bad_Unit" "reference/x.rst" >/dev/null 2>err.txt
    assert_eq "an invalid unit id exits 2" "2" "$?"
    assert_json_error "bad unit id" "err.txt" "bad_target"

    crayon_unit_new traversal-unit "../escape.rst" >/dev/null 2>err2.txt
    assert_eq "a traversal target exits 2" "2" "$?"
    assert_json_error "traversal target" "err2.txt" "bad_target"

    crayon_unit_new ext-unit "reference/x.txt" >/dev/null 2>err3.txt
    assert_eq "a non-.md/.rst target exits 2" "2" "$?"
    assert_json_error "bad extension" "err3.txt" "bad_target"
    cleanup
}

# --- stage a: contract 5.8's situation table, the two busy reasons -----------

# Hold the repo-wide lock from another process until the marker appears, so the
# verb under test cannot race the holder (RESEARCH Pattern 5).
hold_lock() {
    mkdir -p .crayon/staging
    flock -x .crayon/staging/lock -c 'touch .crayon/staging/held; sleep 5' &
    HOLDER_PID=$!
    local waited=0
    while [ ! -f .crayon/staging/held ] && [ "$waited" -lt 50 ]; do
        sleep 0.1
        waited=$((waited + 1))
    done
}

release_holder() {
    if [ -n "${HOLDER_PID:-}" ]; then
        kill "$HOLDER_PID" 2>/dev/null || true
        wait "$HOLDER_PID" 2>/dev/null || true
        HOLDER_PID=""
    fi
}


# Rewrite the pending manifest through python3 so the fixture can express
# "not canonical" and "not a prefix of the batch" exactly.
patch_manifest() {
    local unit="$1" mode="$2"
    python3 -c '
import json, sys
path, mode = sys.argv[1], sys.argv[2]
manifest = json.loads(open(path, encoding="utf-8").read())
if mode == "drop-first":
    manifest["events"] = manifest["events"][1:]
elif mode == "non-canonical":
    manifest["events"] = ["{\"b\": 1, \"a\": 2}"]
elif mode == "files-are-strings":
    manifest["files"] = [entry["path"] for entry in manifest["files"]]
elif mode == "files-have-no-path":
    manifest["files"] = [{}]
elif mode == "files-traverse":
    for entry in manifest["files"]:
        entry["path"] = "../../../../etc/foo"
open(path, "w", encoding="utf-8").write(json.dumps(manifest))
' ".crayon/staging/${unit}/pending/manifest.json" "$mode"
}

# CR-04: every file-reading helper caught only the (FileNotFoundError,
# IsADirectoryError, NotADirectoryError) tuple and `main` converted only
# Refusal/UnitInvalid/ValueError, so a PermissionError — or an ENOSPC, or any
# other OSError — escaped as a stack trace with exit 1, which is the contract's
# code for a GATE refusal. Contract 5.7: one JSON line, never a stack trace.
test_an_unreadable_file_is_one_json_line_never_a_traceback() {
    setup_repo
    if [ "$(id -u)" = "0" ]; then
        # chmod 000 does not deny root, so the fixture cannot express the case.
        assert_eq "skipped as root" "0" "0"
        cleanup
        return 0
    fi

    printf '# Plan\n\nAn outline.\n' >noread.md
    chmod 000 noread.md
    "$CRAYON" unit new perm-unit --intent reference --audience A --title T \
        --target reference/p.rst --body-file noread.md >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an unreadable --body-file exits 2" "2" "$rc"
    assert_json_error "unreadable --body-file" "err.txt" "unit_invalid"
    assert_file_not_exists "nothing is declared" ".crayon/units/perm-unit"

    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note-file noread.md >/dev/null 2>err2.txt
    assert_eq "an unreadable --note-file exits 2" "2" "$?"
    assert_json_error "unreadable --note-file" "err2.txt" "note_required"

    stage_draft demo-unit "reference/demo.rst" "body\n"
    chmod 000 "$(draft_path demo-unit reference/demo.rst)"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        >/dev/null 2>err3.txt
    assert_eq "an unreadable staged page exits 2" "2" "$?"
    assert_json_error "unreadable staged page" "err3.txt" "bad_draft_path"
    assert_file_not_exists "no page is written" "docs/reference/demo.rst"
    chmod 644 "$(draft_path demo-unit reference/demo.rst)"

    # And the backstop in main() itself: an OSError from a helper that has no
    # refusal of its own is still one JSON line, not a traceback.
    chmod 000 .crayon/units/demo-unit/ledger.jsonl
    "$CRAYON" show demo-unit >/dev/null 2>err4.txt
    assert_eq "an unreadable ledger exits 2, not 1" "2" "$?"
    assert_json_error "unreadable ledger" "err4.txt" "bad_target"
    chmod 644 .crayon/units/demo-unit/ledger.jsonl
    chmod 644 noread.md
    cleanup
}

# WR-04: CR-04's fix widened the read helpers from the three-member tuple to
# OSError so "the common cases stay specific". UnicodeDecodeError is NOT an
# OSError — it is a ValueError — so the single most common "this file cannot be
# read as text" sailed past the specific refusal into main's generic ValueError
# arm: `bad_target`, no unit, and an EMPTY hint, the one field whose job is to
# say what to do next. Contract 5.6 is explicit that a body deviation is
# `unit_invalid` with the flag that fixes it. Needs no chmod, so it runs as root.
test_a_non_utf8_input_file_is_refused_with_its_own_flag() {
    setup_repo
    printf '\377\376\000binary\n' >bin.md

    "$CRAYON" unit new bin-unit --intent reference --audience A --title T \
        --target reference/b.rst --body-file bin.md >/dev/null 2>err.txt
    assert_eq "a non-UTF-8 --body-file exits 2" "2" "$?"
    assert_json_error "non-UTF-8 --body-file" "err.txt" "unit_invalid"
    assert_json_detail "the refusal names the flag and the fault" "err.txt" \
        "--body-file bin.md is not UTF-8 text"
    assert_eq "the refusal names the unit" "bin-unit" "$(json_field unit <err.txt)"
    assert_not_contains "the hint is not empty" "$(json_field hint <err.txt)" "null"
    assert_contains "the hint says what to do" "$(json_field hint <err.txt)" \
        "pass a UTF-8 file"
    assert_file_not_exists "nothing is declared" ".crayon/units/bin-unit"

    # The stdin branch reads through the same codec and used to crash there too.
    "$CRAYON" unit new stdin-unit --intent reference --audience A --title T \
        --target reference/s.rst --body-file - <bin.md >/dev/null 2>err2.txt
    assert_eq "a non-UTF-8 stdin body exits 2" "2" "$?"
    assert_json_error "non-UTF-8 stdin body" "err2.txt" "unit_invalid"
    assert_json_detail "the stdin refusal names the fault" "err2.txt" \
        "the body read from stdin is not UTF-8 text"
    assert_eq "the stdin refusal names the unit" "stdin-unit" \
        "$(json_field unit <err2.txt)"
    assert_contains "the stdin hint says what to do" \
        "$(json_field hint <err2.txt)" "pass a UTF-8 body"
    assert_file_not_exists "the stdin refusal declares nothing" \
        ".crayon/units/stdin-unit"

    crayon_unit_new note-unit "reference/n.rst" >/dev/null 2>&1
    "$CRAYON" signoff note-unit >/dev/null 2>&1
    "$CRAYON" steer note-unit --note-file bin.md >/dev/null 2>err3.txt
    assert_eq "a non-UTF-8 --note-file exits 2" "2" "$?"
    assert_json_error "non-UTF-8 --note-file" "err3.txt" "note_required"
    assert_json_detail "the note refusal names its flag" "err3.txt" \
        "--note-file bin.md is not UTF-8 text"

    stage_draft note-unit "reference/n.rst" "body\n"
    "$CRAYON" draft note-unit "$(draft_path note-unit reference/n.rst)" \
        --report bin.md >/dev/null 2>err4.txt
    assert_eq "a non-UTF-8 --report exits 2" "2" "$?"
    assert_json_error "non-UTF-8 --report" "err4.txt" "bad_draft_path"
    assert_json_detail "the report refusal says UTF-8, not JSON" "err4.txt" \
        "--report bin.md is not UTF-8 text"
    cleanup
}

# WR-09: the same fault on the same codec, one layer in. WR-04 widened the
# three helpers that read AUTHOR input; the readers of the RECORD still let a
# bare UnicodeDecodeError escape to `main`'s generic ValueError arm, which
# answered `bad_target` (2, "bad input" -- what a skill reads as "I mistyped an
# argument") with an EMPTY hint, for "the hash-chained record of truth is
# unreadable". Every verb, read-only ones included, because stage a reads the
# ledger before anything else.
test_a_non_utf8_ledger_is_ledger_corrupt_on_every_verb() {
    setup_repo
    crayon_unit_new rec-unit "reference/r.rst" >/dev/null 2>&1
    printf '\377\376 not utf8\n' >>.crayon/units/rec-unit/ledger.jsonl
    local head_before
    head_before=$(git rev-parse HEAD)

    local verb
    for verb in show signoff; do
        "$CRAYON" "$verb" rec-unit >/dev/null 2>err.txt
        assert_eq "a non-UTF-8 ledger makes $verb exit 6" "6" "$?"
        assert_json_error "non-UTF-8 ledger via $verb" "err.txt" "ledger_corrupt"
        assert_eq "$verb: the refusal names the unit" "rec-unit" \
            "$(json_field unit <err.txt)"
        assert_contains "$verb: the detail names the codec" \
            "$(json_field detail <err.txt)" "is not UTF-8 text"
        # The empty hint was the whole point: `hint` is the one field whose job
        # is to say what to do next.
        assert_contains "$verb: the hint says what the ledger must be" \
            "$(json_field hint <err.txt)" "UTF-8 JSONL"
        assert_eq "$verb: recovery is the routed exit" "resume" \
            "$(json_field next <err.txt)"
    done

    "$CRAYON" steer rec-unit --note "hello there" >/dev/null 2>err5.txt
    assert_eq "a non-UTF-8 ledger makes steer exit 6" "6" "$?"
    assert_json_error "non-UTF-8 ledger via steer" "err5.txt" "ledger_corrupt"
    assert_eq "an undecodable ledger commits nothing" "$head_before" \
        "$(git rev-parse HEAD)"
    cleanup
}

# WR-10: CR-01 threaded the unit into the three GENERIC backstops and left the
# `except Refusal` arm -- the one every STRUCTURED refusal comes through --
# reading `refusal.unit` verbatim, while raisers that had the unit right there
# in scope omitted it. So the commonest refusal a second concurrent skill sees
# reported `"unit": ""` while the rarer generic backstops had just learned to
# name it: the inverse of the intended outcome. `busy` is the reachable case;
# `main`'s fallback is what keeps a future raiser from regressing it silently.
test_a_busy_refusal_names_the_unit_it_refused() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1

    hold_lock
    "$CRAYON" signoff demo-unit >/dev/null 2>err.txt
    local rc=$?
    release_holder

    assert_eq "a held lock exits 5" "5" "$rc"
    assert_json_error "busy names its unit" "err.txt" "busy"
    assert_eq "the busy refusal names the unit it refused" "demo-unit" \
        "$(json_field unit <err.txt)"
    cleanup
}

# WR-10, second half: every other refusal in the tool spells the ledger from
# the repository root (`os.path.relpath(path, root)` in `classify_stage_a`);
# the ones raised below the verb embedded the ABSOLUTE path, leaking the
# caller's filesystem layout into a diagnostic a skill is invited to paste
# into an issue or a commit message.
test_a_ledger_refusal_spells_the_ledger_from_the_repo_root() {
    setup_repo
    crayon_unit_new attr-unit "reference/a.rst" >/dev/null 2>&1
    printf '\377\376 not utf8\n' >>.crayon/units/attr-unit/ledger.jsonl

    "$CRAYON" show attr-unit >/dev/null 2>err.txt
    assert_json_error "undecodable ledger" "err.txt" "ledger_corrupt"
    # $TEST_DIR is the absolute prefix; neither field may carry it.
    assert_not_contains "the detail leaks no absolute path" \
        "$(json_field detail <err.txt)" "$TEST_DIR"
    assert_not_contains "the hint leaks no absolute path" \
        "$(json_field hint <err.txt)" "$TEST_DIR"
    assert_contains "the hint names the ledger from the repo root" \
        "$(json_field hint <err.txt)" ".crayon/units/attr-unit/ledger.jsonl"
    cleanup
}

test_stage_a_busy_refuses_with_nothing_written() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    local head_before ledger_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest demo-unit)

    hold_lock
    crayon_unit_new other-unit "reference/other.rst" >/dev/null 2>err.txt
    local rc=$?
    release_holder

    assert_eq "a held lock exits 5" "5" "$rc"
    assert_json_error "busy" "err.txt" "busy"
    assert_eq "busy leaves HEAD unchanged" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "busy leaves the ledger byte-unchanged" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_file_not_exists "busy writes no unit directory" ".crayon/units/other-unit"
    cleanup
}

test_stage_a_precedes_input_validation() {
    setup_repo
    hold_lock
    crayon_unit_new stage-order "../escape.rst" >/dev/null 2>err.txt
    local rc=$?
    release_holder
    # Both a stage-a refusal (busy) and a stage-b one (bad target) apply; the
    # earlier stage wins, and that is the whole of GATE-01's ordering claim.
    assert_eq "stage a beats stage b: exit 5" "5" "$rc"
    assert_json_error "stage order" "err.txt" "busy"
    cleanup
}

test_stage_a_git_busy_never_deletes_the_index_lock() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    local head_before ledger_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest demo-unit)

    touch .git/index.lock
    crayon_unit_new other-unit "reference/other.rst" >/dev/null 2>err.txt
    local rc=$?

    assert_eq "a present .git/index.lock exits 5" "5" "$rc"
    assert_json_error "git_busy" "err.txt" "git_busy"
    assert_file_exists "the tool never deletes .git/index.lock" ".git/index.lock"
    assert_eq "git_busy leaves HEAD unchanged" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "git_busy leaves the ledger byte-unchanged" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_file_not_exists "git_busy writes no unit directory" ".crayon/units/other-unit"
    rm -f .git/index.lock
    cleanup
}

test_stage_a_clean_unit_proceeds() {
    setup_repo
    crayon_unit_new clean-unit "reference/clean.rst" >/dev/null 2>&1
    assert_eq "no pending and no tail: the verb proceeds" "0" "$?"
    assert_file_not_exists "a clean run leaves no pending/" ".crayon/staging/clean-unit/pending"
    cleanup
}

test_stage_a_deletes_pending_without_a_complete_manifest() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    mkdir -p .crayon/staging/demo-unit/pending/after
    printf 'junk\n' >.crayon/staging/demo-unit/pending/after/stray

    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_file_not_exists "pending without a manifest is deleted" \
        ".crayon/staging/demo-unit/pending"
    # Deleted, then the verb PROCEEDS — into its own stage-c refusal here,
    # which is what proves stage a did not stop the invocation.
    assert_eq "the verb proceeds past stage a" "2" "$rc"
    assert_json_error "proceeds to stage c" "err.txt" "unit_exists"
    cleanup
}

test_stage_a_deletes_a_manifest_whose_events_never_landed() {
    setup_repo
    CRAYON_CRASH_AT=manifest crayon_unit_new t18-unit "reference/t18.rst" >/dev/null 2>&1
    assert_eq "the crash at manifest is a hard exit" "137" "$?"
    assert_file_exists "the manifest is durable before the append" \
        ".crayon/staging/t18-unit/pending/manifest.json"
    assert_file_not_exists "nothing was appended" ".crayon/units/t18-unit/ledger.jsonl"
    assert_file_not_exists "nothing was placed (2 precedes 3)" ".crayon/units/t18-unit/unit.md"

    crayon_unit_new t18-unit "reference/t18.rst" >/dev/null 2>&1
    local rc=$?
    assert_eq "the next verb proceeds and succeeds" "0" "$rc"
    assert_file_not_exists "the stale pending/ is deleted" ".crayon/staging/t18-unit/pending"
    cleanup
}

test_stage_a_deletes_a_committed_batch_awaiting_cleanup() {
    setup_repo
    CRAYON_CRASH_AT=cleanup crayon_unit_new t20-unit "reference/t20.rst" >/dev/null 2>&1
    assert_eq "the crash at cleanup is a hard exit" "137" "$?"
    assert_file_exists "pending/ survives the crash" ".crayon/staging/t20-unit/pending"
    assert_eq "the batch is committed" "crayon: declared t20-unit" "$(git log -1 --format=%s)"

    crayon_unit_new t20-unit "reference/t20.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_file_not_exists "the committed batch's pending/ is deleted" \
        ".crayon/staging/t20-unit/pending"
    assert_eq "the verb proceeds past stage a" "2" "$rc"
    assert_json_error "proceeds to stage c" "err.txt" "unit_exists"
    cleanup
}

test_stage_a_refuses_an_uncommitted_tail() {
    setup_repo
    CRAYON_CRASH_AT=place:1 crayon_unit_new t19-unit "reference/t19.rst" >/dev/null 2>&1
    assert_eq "the crash at place:1 is a hard exit" "137" "$?"
    assert_file_exists "the tail is on disk" ".crayon/units/t19-unit/ledger.jsonl"
    local head_before ledger_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest t19-unit)

    crayon_unit_new t19-unit "reference/t19.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an uncommitted tail exits 6" "6" "$rc"
    assert_json_error "uncommitted_tail" "err.txt" "uncommitted_tail"
    assert_file_contains "the hint names resume even though resume is a stub" \
        "err.txt" "crayon resume t19-unit"
    assert_eq "the refusal leaves HEAD unchanged" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the refusal leaves the ledger byte-unchanged" "$ledger_before" \
        "$(ledger_digest t19-unit)"
    cleanup
}

# WR-02: `route()` reads `uncommitted_tail` (row 1) and `steps_resolved`
# (the rows 6/7/9 qualifier), and `derive()` produced NEITHER — both read None
# in production, so row 1 was unreachable and the tool told a skill to
# `review` a unit whose contract 5.5 `next` is `resume`.
# WR-03: a target under a gitignored directory made `git add` fail at step 4,
# after the append and the place, so the unit was wedged for EVERY verb —
# including the read-only `show` — and `resume` is a stub in this build. No
# crash fixture is needed to reach it: `docs/reference/` in .gitignore is an
# ordinary repo layout. It is probed before step 1, where a refusal is free.
test_an_ignored_destination_is_refused_before_anything_is_written() {
    setup_repo
    crayon_unit_new ign-unit "reference/ign.rst" >/dev/null 2>&1
    "$CRAYON" signoff ign-unit >/dev/null 2>&1
    stage_draft ign-unit "reference/ign.rst" "body\n"
    printf 'docs/reference/\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore the reference dir"
    local ledger_before head_before
    ledger_before=$(ledger_digest ign-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft ign-unit "$(draft_path ign-unit reference/ign.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an ignored destination exits 2, not 6" "2" "$rc"
    assert_json_error "ignored destination" "err.txt" "bad_write_path"
    assert_file_not_exists "no page is placed" "docs/reference/ign.rst"
    assert_eq "nothing is appended" "$ledger_before" "$(ledger_digest ign-unit)"
    assert_eq "nothing is committed" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "no pending/ is left behind" ".crayon/staging/ign-unit/pending"

    # And the unit is NOT wedged: the read surface still answers.
    "$CRAYON" show ign-unit >/dev/null 2>&1
    assert_eq "the unit is still readable" "0" "$?"
    cleanup
}

# CR-01: the ignore probe asks GIT's opinion of the destinations; it never
# asked the FILESYSTEM's. `place_files` runs at step 3, after the append at
# step 2, so an OSError from `publish_atomic`'s makedirs/open wedged the unit
# with an uncommitted tail no verb in this build can clear — and reported it as
# `bad_target`/2, the exit code a skill reads as "nothing happened". Neither
# layout needs a crash fixture.
test_a_destination_the_filesystem_rejects_is_refused_before_the_append() {
    setup_repo
    crayon_unit_new fs-unit "reference/fs.rst" >/dev/null 2>&1
    "$CRAYON" signoff fs-unit >/dev/null 2>&1
    stage_draft fs-unit "reference/fs.rst" "body\n"
    local ledger_before head_before
    ledger_before=$(ledger_digest fs-unit)
    head_before=$(git rev-parse HEAD)

    # A. the target's parent path component is a regular file, not a directory.
    rm -rf docs/reference
    printf 'I am a file not a dir\n' >docs/reference
    "$CRAYON" draft fs-unit "$(draft_path fs-unit reference/fs.rst)" >/dev/null 2>err.txt
    assert_eq "a non-directory parent exits 2" "2" "$?"
    assert_json_error "non-directory parent" "err.txt" "bad_write_path"
    assert_json_detail "the refusal names the offending component" "err.txt" \
        "'docs/reference/fs.rst' cannot be created: docs/reference is not a directory"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest fs-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "the refusal leaves no pending/" \
        ".crayon/staging/fs-unit/pending"
    "$CRAYON" show fs-unit >/dev/null 2>&1
    assert_eq "the unit is not wedged" "0" "$?"
    rm -f docs/reference
    mkdir -p docs/reference

    # B. the docs subdirectory exists but is not writable. os.access is an
    # effective-permission check, and 0500 does not deny root.
    if [ "$(id -u)" = "0" ]; then
        assert_eq "skipped as root" "0" "0"
        cleanup
        return 0
    fi
    chmod 500 docs/reference
    "$CRAYON" draft fs-unit "$(draft_path fs-unit reference/fs.rst)" >/dev/null 2>err.txt
    local rc=$?
    chmod 700 docs/reference
    assert_eq "an unwritable parent exits 2" "2" "$rc"
    assert_json_error "unwritable parent" "err.txt" "bad_write_path"
    assert_json_detail "the refusal names the unwritable directory" "err.txt" \
        "'docs/reference/fs.rst' cannot be created: docs/reference is not writable"
    assert_eq "the second refusal appends nothing" "$ledger_before" \
        "$(ledger_digest fs-unit)"
    assert_eq "the second refusal commits nothing" "$head_before" \
        "$(git rev-parse HEAD)"
    "$CRAYON" show fs-unit >/dev/null 2>&1
    assert_eq "the unit is still not wedged" "0" "$?"

    # And the same destination, once the layout is sane, still lands.
    "$CRAYON" draft fs-unit "$(draft_path fs-unit reference/fs.rst)" >/dev/null 2>&1
    assert_eq "a placeable destination still drafts" "0" "$?"
    assert_file_contains "the page holds the drafted bytes" "docs/reference/fs.rst" "body"
    cleanup
}

# CR-01: `main`'s generic backstops reported `"unit": ""`, so the one line a
# skill gets could not name what it had refused. The parsed namespace carries
# the id for every unit-scoped verb.
#
# WR-08: this test used to drive `draft` with `docs/reference` as a regular
# file -- which CR-01's OWN placeability guard refuses as a structured
# `Refusal`, handled by `main`'s `except Refusal` arm, which reads
# `refusal.unit` and never calls `_argv_unit` at all. It asserted a property
# that already held before the fix, and `_argv_unit` could be replaced with
# `return ""` with all 1,341 assertions still green. Both arms below reach it:
# the first because `not_a_repo` is raised with no unit and `main` falls back
# (WR-10), the second because a PermissionError lands in the generic `OSError`
# backstop, which is the arm CR-01 was filed about.
test_a_backstop_refusal_names_its_unit() {
    setup_repo

    # A. no repository at all. Nothing below `main` knows the unit, so the id
    # can only come from the parsed namespace.
    local bare
    bare=$(mktemp -d)
    (cd "$bare" && "$CRAYON" show attr-unit) >/dev/null 2>err.txt
    assert_eq "a not_a_repo refusal exits 2" "2" "$?"
    assert_json_error "not_a_repo" "err.txt" "not_a_repo"
    assert_eq "a not_a_repo refusal is attributable" "attr-unit" \
        "$(json_field unit <err.txt)"
    rm -rf "$bare"

    # B. the generic OSError backstop itself.
    crayon_unit_new attr-unit "reference/a.rst" >/dev/null 2>&1
    "$CRAYON" signoff attr-unit >/dev/null 2>&1
    stage_draft attr-unit "reference/a.rst" "body\n"
    if [ "$(id -u)" = "0" ]; then
        # chmod 000 does not deny root, so the fixture cannot express the case.
        assert_eq "skipped as root" "0" "0"
    else
        chmod 000 docs/reference
        "$CRAYON" draft attr-unit "$(draft_path attr-unit reference/a.rst)" \
            >/dev/null 2>err2.txt
        chmod 755 docs/reference
        assert_json_error "the OSError backstop" "err2.txt" "bad_target"
        assert_contains "the backstop really is the OSError arm" \
            "$(json_field detail <err2.txt)" "PermissionError"
        assert_eq "an OSError backstop is attributable" "attr-unit" \
            "$(json_field unit <err2.txt)"
    fi
    cleanup
}

# WR-01: a non-zero `git add --dry-run` is not synonymous with "ignored". The
# probe scraped stderr for "offenders" and presented whatever it found as a
# path, so the hint came back as `git check-ignore -v fatal: pathspec ... is
# beyond a symbolic link` — not a command anyone can run. The hint must
# reproduce the refusal, and the detail must be git's own words.
test_an_ignore_refusal_hints_a_runnable_command() {
    setup_repo
    crayon_unit_new hint-unit "reference/h.rst" >/dev/null 2>&1
    "$CRAYON" signoff hint-unit >/dev/null 2>&1
    stage_draft hint-unit "reference/h.rst" "body\n"
    printf 'docs/reference/\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore the reference dir"

    "$CRAYON" draft hint-unit "$(draft_path hint-unit reference/h.rst)" >/dev/null 2>err.txt
    assert_eq "an ignored destination exits 2" "2" "$?"
    local hint
    hint=$(json_field hint <err.txt)
    assert_contains "the hint is a runnable git command" "$hint" \
        'git add --dry-run --ignore-missing -- docs/reference/h.rst'
    assert_not_contains "the hint is not a mangled check-ignore" "$hint" \
        "check-ignore -v fatal:"
    # The whole command up to the backtick must be runnable as written.
    local command
    command=$(printf '%s' "$hint" | sed -n 's/^`\(.*\)` reproduces this.*/\1/p')
    assert_not_contains "the quoted command reproduces the failure" \
        "$(eval "$command" 2>&1 >/dev/null; echo "rc=$?")" "rc=0"
    # WR-12: this used to pin exactly the uninformative header as the whole
    # detail, which made the regression load-bearing. For the ignore case git's
    # FIRST line is a constant and the offenders are on the lines after it, so
    # the detail was the same string for every ignore refusal in the tool.
    local detail
    detail=$(json_field detail <err.txt)
    # Phase-16 IN-03: git's own first line, read from git rather than spelled
    # out in English here. The property is "the detail is git's own words";
    # pinning one release's translation of them was a locale dependency.
    assert_contains "git's own first line is still verbatim" "$detail" \
        "git will not stage this write: $(git_add_first_line docs/reference/h.rst)"
    assert_contains "the detail names a path git actually named" "$detail" \
        "docs/reference/h.rst"
    cleanup
}

# WR-12: the discriminating case. With one destination the header alone is
# survivable -- the hint lists the only candidate. With more than one, a detail
# that is a constant string tells the author nothing about WHICH write git
# refused, and `_first_line` discarded exactly the lines git uses to say so.
test_an_ignore_refusal_names_which_destination_is_ignored() {
    setup_repo
    crayon_unit_new pick-unit "reference/keep.rst" \
        --also-target "reference/drop.rst" >/dev/null 2>&1
    "$CRAYON" signoff pick-unit >/dev/null 2>&1
    stage_draft pick-unit "reference/keep.rst" "keep\n"
    stage_draft pick-unit "reference/drop.rst" "drop\n"
    printf 'docs/reference/drop.rst\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore exactly one of the two"

    "$CRAYON" draft pick-unit ".crayon/staging/pick-unit/draft" >/dev/null 2>err.txt
    assert_eq "an ignored destination exits 2" "2" "$?"
    assert_json_error "one of two destinations ignored" "err.txt" "bad_write_path"
    local detail
    detail=$(json_field detail <err.txt)
    assert_contains "the detail names the ignored destination" "$detail" \
        "docs/reference/drop.rst"
    # Negative keystone: naming every destination would satisfy the assertion
    # above while saying just as little as the constant header did.
    assert_not_contains "the detail does not name the writable one" "$detail" \
        "docs/reference/keep.rst"
    assert_contains "git's own first line is still verbatim" "$detail" \
        "$(git_add_first_line docs/reference/keep.rst docs/reference/drop.rst)"
    # Phase-16 IN-03: git's diagnostic PREFIXES are its own UI, never offenders.
    # Asserted at the prefix (which `_GIT_UI_PREFIXES` pins and the unit suite
    # checks) rather than at one English advice sentence.
    for prefix in "hint:" "warning:" "error:" "fatal:"; do
        assert_not_contains "the detail carries no git $prefix line" "$detail" \
            "$prefix"
    done
    cleanup
}

# WR-12: single-line stderr has nothing after the first line to add, so the
# verbatim-first-line discipline must be exactly what it was.
test_a_non_ignore_git_add_failure_reports_gits_one_line_unchanged() {
    setup_repo
    crayon_unit_new link-unit "reference/l.rst" >/dev/null 2>&1
    "$CRAYON" signoff link-unit >/dev/null 2>&1
    stage_draft link-unit "reference/l.rst" "body\n"
    rmdir docs/reference
    ln -s missing-dir docs/reference

    "$CRAYON" draft link-unit "$(draft_path link-unit reference/l.rst)" \
        >/dev/null 2>err.txt
    assert_eq "a destination beyond a symlink exits 2" "2" "$?"
    assert_json_detail "git's single line is reported verbatim" "err.txt" \
        "git will not stage this write: $(git_add_first_line docs/reference/l.rst)"
    rm -f docs/reference
    cleanup
}

# WR-03: the probe is `git add --dry-run`, not `git check-ignore`, because
# only the former is git's own decision. A TRACKED page matching a file-level
# ignore pattern is reported ignored by `check-ignore --no-index` and staged
# happily by `git add` — refusing it would be a false refusal that no `git add`
# would ever have produced.
test_a_tracked_page_matching_a_file_level_ignore_pattern_is_still_writable() {
    setup_repo
    crayon_unit_new trk-unit "reference/trk.rst" >/dev/null 2>&1
    "$CRAYON" signoff trk-unit >/dev/null 2>&1
    stage_draft trk-unit "reference/trk.rst" "first\n"
    "$CRAYON" draft trk-unit "$(draft_path trk-unit reference/trk.rst)" >/dev/null 2>&1
    assert_eq "the first draft lands" "0" "$?"

    printf 'docs/reference/trk.rst\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore the page by name"
    assert_eq "check-ignore alone would call it ignored" "0" \
        "$(git check-ignore --no-index -q -- docs/reference/trk.rst; echo $?)"
    "$CRAYON" steer trk-unit --note "please rewrite the intro" >/dev/null 2>&1
    stage_draft trk-unit "reference/trk.rst" "second\n"

    "$CRAYON" draft trk-unit "$(draft_path trk-unit reference/trk.rst)" >/dev/null 2>err.txt
    assert_eq "a redraft of a tracked page still lands" "0" "$?"
    assert_file_contains "the page holds the new bytes" "docs/reference/trk.rst" "second"
    cleanup
}

# WR-03: an ignored DIRECTORY is refused even when the page inside it is
# already tracked — `git add` refuses that too, so recording it is impossible.
test_an_ignored_directory_is_refused_even_for_a_tracked_page() {
    setup_repo
    crayon_unit_new dir-ign-unit "reference/d.rst" >/dev/null 2>&1
    "$CRAYON" signoff dir-ign-unit >/dev/null 2>&1
    stage_draft dir-ign-unit "reference/d.rst" "first\n"
    "$CRAYON" draft dir-ign-unit "$(draft_path dir-ign-unit reference/d.rst)" >/dev/null 2>&1
    assert_eq "the first draft lands" "0" "$?"

    printf 'docs/reference/\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore the reference dir"
    "$CRAYON" steer dir-ign-unit --note "please rewrite the intro" >/dev/null 2>&1
    stage_draft dir-ign-unit "reference/d.rst" "second\n"
    local ledger_before head_before page_before
    ledger_before=$(ledger_digest dir-ign-unit)
    head_before=$(git rev-parse HEAD)
    page_before=$(sha256_of_file docs/reference/d.rst)

    "$CRAYON" draft dir-ign-unit "$(draft_path dir-ign-unit reference/d.rst)" \
        >/dev/null 2>err.txt
    assert_eq "an ignored directory exits 2, not 6" "2" "$?"
    assert_json_error "ignored directory (tracked page)" "err.txt" "bad_write_path"
    assert_eq "the page is left untouched" "$page_before" \
        "$(sha256_of_file docs/reference/d.rst)"
    assert_eq "nothing is appended" "$ledger_before" "$(ledger_digest dir-ign-unit)"
    assert_eq "nothing is committed" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_a_unit_with_an_uncommitted_tail_routes_to_resume() {
    setup_repo
    CRAYON_CRASH_AT=place:1 crayon_unit_new tail-unit "reference/t.rst" >/dev/null 2>&1
    assert_eq "the crash at place:1 is a hard exit" "137" "$?"
    assert_file_exists "the tail is on disk" ".crayon/units/tail-unit/ledger.jsonl"

    assert_eq "the derived state carries the tail" "true" \
        "$(derived tail-unit uncommitted_tail)"
    assert_eq "contract 5.5 row 1 routes to resume" "resume" "$(derived tail-unit next)"

    # And the verb the routing names finishes the transition (plan 17-07): the
    # circle contract 5.5 row 1 used to close on a stub now ends in a commit.
    "$CRAYON" resume tail-unit >/dev/null 2>err.txt
    assert_eq "the routed verb completes the interrupted transition" "0" "$?"
    assert_eq "the tail is committed" "crayon: declared tail-unit" \
        "$(git log -1 --format=%s)"
    assert_eq "the unit no longer carries a tail" "false" \
        "$(derived tail-unit uncommitted_tail)"
    cleanup
}

test_stage_a_refuses_recovery_unsupported_no_material() {
    setup_repo
    CRAYON_CRASH_AT=append crayon_unit_new nm-unit "reference/nm.rst" >/dev/null 2>&1
    rm -rf .crayon/staging/nm-unit/pending
    local ledger_before
    ledger_before=$(ledger_digest nm-unit)

    crayon_unit_new nm-unit "reference/nm.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a tail with no manifest exits 6" "6" "$rc"
    assert_json_error "no_material" "err.txt" "recovery_unsupported"
    assert_json_detail "no_material" "err.txt" "no_material"
    assert_file_exists "the unit directory is preserved" ".crayon/units/nm-unit"
    assert_eq "nothing is written" "$ledger_before" "$(ledger_digest nm-unit)"
    cleanup
}

# WR-05: `pending_stray` — some but not all of the manifest's events in the
# ledger, none of them uncommitted — is NOT a row of contract 5.8's situation
# table, and it is the one case where the material is the only evidence of what
# a half-applied batch intended. Stage a used to delete it, silently, in write
# mode. 5.8's honest limit says every file whose bytes it cannot attribute is
# preserved.
test_stage_a_preserves_a_stray_pending_batch_instead_of_deleting_it() {
    setup_repo
    crayon_unit_new stray-unit "reference/s.rst" >/dev/null 2>&1
    # A manifest naming the committed opening batch plus one event that is not
    # in the ledger at all: a partly-present batch with no uncommitted tail.
    python3 -c '
import json, os, sys
pending = ".crayon/staging/stray-unit/pending"
os.makedirs(os.path.join(pending, "after"), exist_ok=True)
lines = [l for l in open(".crayon/units/stray-unit/ledger.jsonl", encoding="utf-8").read().split("\n") if l]
manifest = {"events": [lines[0], json.dumps({"kind": "never-landed"}, sort_keys=True)], "files": []}
open(os.path.join(pending, "manifest.json"), "w", encoding="utf-8").write(json.dumps(manifest))
open(os.path.join(pending, "evidence.txt"), "w", encoding="utf-8").write("the only copy\n")
'
    local ledger_before head_before
    ledger_before=$(ledger_digest stray-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" steer stray-unit --note "anything" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a stray pending batch exits 6" "6" "$rc"
    assert_json_error "pending_stray" "err.txt" "recovery_unsupported"
    assert_json_detail "pending_stray" "err.txt" "material_invalid"
    assert_file_exists "the material is preserved, not deleted" \
        ".crayon/staging/stray-unit/pending/evidence.txt"
    assert_eq "nothing is appended" "$ledger_before" "$(ledger_digest stray-unit)"
    assert_eq "nothing is committed" "$head_before" "$(git rev-parse HEAD)"

    # Read-only verbs classify identically (5.8's write boundary), so `show`
    # reports the same refusal rather than a would-delete line.
    "$CRAYON" show stray-unit >/dev/null 2>err2.txt
    assert_eq "show classifies it the same way" "6" "$?"
    assert_json_error "pending_stray (show)" "err2.txt" "recovery_unsupported"
    assert_file_exists "show deletes nothing either" \
        ".crayon/staging/stray-unit/pending/evidence.txt"
    cleanup
}

# WR-03: preserving the material was right; leaving no way out was the cost the
# fix did not account for. Every verb refused, `resume` is a D-16 stub, and the
# routed `next` fell to row 10 and said `review` — a verb that refuses
# identically, so the author was routed in a circle. The refusal must name an
# escape and the routing must name the only verb that could ever clear it.
test_a_stray_pending_batch_routes_to_resume_and_names_an_escape() {
    setup_repo
    crayon_unit_new circle-unit "reference/c.rst" >/dev/null 2>&1
    python3 -c '
import json, os
pending = ".crayon/staging/circle-unit/pending"
os.makedirs(os.path.join(pending, "after"), exist_ok=True)
lines = [l for l in open(".crayon/units/circle-unit/ledger.jsonl", encoding="utf-8").read().split("\n") if l]
manifest = {"events": [lines[0], json.dumps({"kind": "never-landed"}, sort_keys=True)], "files": []}
open(os.path.join(pending, "manifest.json"), "w", encoding="utf-8").write(json.dumps(manifest))
open(os.path.join(pending, "evidence.txt"), "w", encoding="utf-8").write("the only copy\n")
'

    # The refusal itself points at resume and names the manual escape.
    "$CRAYON" show circle-unit >/dev/null 2>err.txt
    assert_eq "show exits 6" "6" "$?"
    assert_eq "the refusal routes to resume" "resume" "$(json_field next <err.txt)"
    local hint
    hint=$(json_field hint <err.txt)
    assert_contains "the hint names the directory to inspect" "$hint" \
        ".crayon/staging/circle-unit/pending"
    assert_contains "the hint names the escape" "$hint" "remove it once its contents"

    # And `resume`, which derives its `next` independently, agrees — it used to
    # answer `review`, a verb that refuses with the same refusal. Since plan
    # 17-06 the verb has a real body, so it answers with the same honest limit
    # rather than the transitional stub refusal: this row of the table is not
    # one `resume` can complete, and saying so is the point.
    "$CRAYON" resume circle-unit >/dev/null 2>err2.txt
    assert_eq "resume refuses the stray batch" "6" "$?"
    assert_json_error "the same honest limit" "err2.txt" "recovery_unsupported"
    assert_eq "resume does not route the author in a circle" "resume" \
        "$(json_field next <err2.txt)"

    # The named escape actually works: nothing else had to change.
    rm -rf .crayon/staging/circle-unit/pending
    "$CRAYON" show circle-unit >/dev/null 2>&1
    assert_eq "removing the material clears the state" "0" "$?"
    "$CRAYON" signoff circle-unit >/dev/null 2>&1
    assert_eq "and the unit is usable again" "0" "$?"
    cleanup
}

test_stage_a_refuses_recovery_unsupported_tail_unknown() {
    setup_repo
    CRAYON_CRASH_AT=append crayon_unit_new tu-unit "reference/tu.rst" >/dev/null 2>&1
    patch_manifest tu-unit drop-first
    local ledger_before
    ledger_before=$(ledger_digest tu-unit)

    crayon_unit_new tu-unit "reference/tu.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a tail that is not a prefix exits 6" "6" "$rc"
    assert_json_error "tail_unknown" "err.txt" "recovery_unsupported"
    assert_json_detail "tail_unknown" "err.txt" "tail_unknown"
    assert_eq "nothing is written" "$ledger_before" "$(ledger_digest tu-unit)"
    cleanup
}

test_stage_a_refuses_recovery_unsupported_material_invalid() {
    setup_repo
    CRAYON_CRASH_AT=append crayon_unit_new mi-unit "reference/mi.rst" >/dev/null 2>&1
    printf 'tampered\n' >>".crayon/staging/mi-unit/pending/after/.crayon/units/mi-unit/unit.md"
    local ledger_before
    ledger_before=$(ledger_digest mi-unit)

    crayon_unit_new mi-unit "reference/mi.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an after/ copy failing its digest exits 6" "6" "$rc"
    assert_json_error "material_invalid" "err.txt" "recovery_unsupported"
    assert_json_detail "material_invalid" "err.txt" "material_invalid"
    assert_eq "nothing is written" "$ledger_before" "$(ledger_digest mi-unit)"
    cleanup
}

# CR-03: `read_manifest` validated `files` only as "a list", so a mangled
# entry reached `entry.get("path")` and `os.path.join(...)` in
# `classify_stage_a` — which runs FIRST on every verb — and crashed the
# process with a traceback and exit 1, the contract's code for a GATE refusal.
# Every shape below must be one JSON line, exit 6, nothing written; and the
# read-only `show` an author reaches for to diagnose it must still answer.
test_stage_a_refuses_a_structurally_invalid_manifest() {
    setup_repo
    local mode
    for mode in files-are-strings files-have-no-path files-traverse; do
        local unit="mf-${mode}"
        CRAYON_CRASH_AT=append crayon_unit_new "$unit" "reference/mf.rst" >/dev/null 2>&1
        patch_manifest "$unit" "$mode"
        local ledger_before
        ledger_before=$(ledger_digest "$unit")

        "$CRAYON" show "$unit" >/dev/null 2>err.txt
        local rc=$?
        assert_eq "$mode: show exits 6, never 1 with a traceback" "6" "$rc"
        assert_json_error "$mode (show)" "err.txt" "recovery_unsupported"
        assert_json_detail "$mode (show)" "err.txt" "material_invalid"

        "$CRAYON" steer "$unit" --note "x" >/dev/null 2>err2.txt
        assert_eq "$mode: a mutating verb exits 6" "6" "$?"
        assert_json_error "$mode (steer)" "err2.txt" "recovery_unsupported"
        assert_json_detail "$mode (steer)" "err2.txt" "material_invalid"
        assert_eq "$mode: nothing is written" "$ledger_before" "$(ledger_digest "$unit")"
        assert_file_exists "$mode: the unit directory is preserved" \
            ".crayon/units/$unit"
    done
    cleanup
}

# CR-03: the same shapes with NO tail are the "pending without a complete
# manifest" row instead — deleted, and the verb proceeds.
test_stage_a_deletes_a_structurally_invalid_manifest_with_no_tail() {
    setup_repo
    CRAYON_CRASH_AT=manifest crayon_unit_new nt-unit "reference/nt.rst" >/dev/null 2>&1
    assert_file_exists "the manifest is durable before the append" \
        ".crayon/staging/nt-unit/pending/manifest.json"
    patch_manifest nt-unit files-have-no-path

    crayon_unit_new nt-unit "reference/nt.rst" >/dev/null 2>&1
    assert_eq "the next verb proceeds and succeeds" "0" "$?"
    assert_file_not_exists "the invalid pending/ is deleted" \
        ".crayon/staging/nt-unit/pending"
    cleanup
}

test_stage_a_refuses_recovery_unsupported_event_invalid() {
    setup_repo
    CRAYON_CRASH_AT=append crayon_unit_new ei-unit "reference/ei.rst" >/dev/null 2>&1
    patch_manifest ei-unit non-canonical
    local ledger_before
    ledger_before=$(ledger_digest ei-unit)

    crayon_unit_new ei-unit "reference/ei.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a non-canonical manifest event exits 6" "6" "$rc"
    assert_json_error "event_invalid" "err.txt" "recovery_unsupported"
    assert_json_detail "event_invalid" "err.txt" "event_invalid"
    assert_eq "nothing is written" "$ledger_before" "$(ledger_digest ei-unit)"
    cleanup
}

test_stage_a_refuses_a_rewritten_committed_prefix() {
    setup_repo
    crayon_unit_new dv-unit "reference/dv.rst" >/dev/null 2>&1
    # Rewrite the LAST committed line only: the chain still verifies (prev looks
    # backwards), so the committed-prefix check is the one that must catch it.
    sed -i '2s/2026-01-01T00:00:00/2026-01-02T00:00:00/' .crayon/units/dv-unit/ledger.jsonl
    local head_before
    head_before=$(git rev-parse HEAD)

    crayon_unit_new dv-unit "reference/dv.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a rewritten committed prefix exits 6" "6" "$rc"
    assert_json_error "ledger_diverged" "err.txt" "ledger_diverged"
    assert_eq "nothing is written" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_stage_a_refuses_a_tampered_ledger_line() {
    setup_repo
    crayon_unit_new tamper-unit "reference/tamper.rst" >/dev/null 2>&1
    # N-12: editing line 1 breaks line 2's prev, so the chain check fires first.
    sed -i '1s/2026-01-01T00:00:00/2026-01-02T00:00:00/' .crayon/units/tamper-unit/ledger.jsonl
    local ledger_before head_before
    ledger_before=$(ledger_digest tamper-unit)
    head_before=$(git rev-parse HEAD)

    crayon_unit_new tamper-unit "reference/tamper.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a tampered ledger line exits 6" "6" "$rc"
    assert_json_error "ledger_corrupt" "err.txt" "ledger_corrupt"
    assert_eq "the tampered file is left exactly as found" "$ledger_before" \
        "$(ledger_digest tamper-unit)"
    assert_eq "nothing is written" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_crayon_crash_at_is_inert_when_unset() {
    setup_repo
    crayon_unit_new inert-unit "reference/inert.rst" >/dev/null 2>&1
    local without
    without=$(ledger_digest inert-unit)
    cleanup

    setup_repo
    CRAYON_CRASH_AT=no-such-point crayon_unit_new inert-unit "reference/inert.rst" >/dev/null 2>&1
    local rc=$?
    assert_eq "an unmatched crash point changes nothing" "0" "$rc"
    assert_eq "the ledger bytes are identical with and without the variable" \
        "$without" "$(ledger_digest inert-unit)"
    cleanup
}


test_hook_that_rewrites_a_recorded_file_warns_and_the_transition_stands() {
    setup_repo
    install_rewrite_and_succeed_hook ".crayon/units/hook-unit/unit.md"
    local before
    before=$(git rev-list --count HEAD)

    local out
    out=$(crayon_unit_new hook-unit "reference/hook.rst" 2>err.txt)
    local rc=$?
    assert_eq "a rewriting hook does not fail the verb" "0" "$rc"
    assert_eq "the transition stands: exactly one commit" "$((before + 1))" \
        "$(git rev-list --count HEAD)"
    assert_file_contains "the warning names the rewritten path" "err.txt" \
        "hook changed .crayon/units/hook-unit/unit.md after recording"
    assert_eq "HEAD carries the hook's bytes, not the tool's" "HOOKFORMATTED" \
        "$(git show HEAD:.crayon/units/hook-unit/unit.md)"
    assert_eq "the hook's change is never undone on disk" "HOOKFORMATTED" \
        "$(cat .crayon/units/hook-unit/unit.md)"
    assert_contains "state is re-derived and a routed token is printed" "$out" "Next: "
    assert_file_not_exists "pending/ is still cleaned up" \
        ".crayon/staging/hook-unit/pending"
    cleanup
}

test_hook_that_rewrites_without_staging_is_caught_by_the_disk_side() {
    setup_repo
    install_rewrite_without_staging_hook ".crayon/units/disk-unit/unit.md"

    crayon_unit_new disk-unit "reference/disk.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "the verb still succeeds" "0" "$rc"
    assert_file_contains "the disk side detects it" "err.txt" \
        "hook changed .crayon/units/disk-unit/unit.md after recording"
    assert_eq "the hook's bytes are on disk and are never undone" "HOOKFORMATTED" \
        "$(cat .crayon/units/disk-unit/unit.md)"
    # HEAD holds what the tool recorded: git read the worktree into the partial
    # commit's temporary index before the hook ran. `git show HEAD:` alone would
    # have reported this file as unchanged — which is the whole reason the check
    # asks both git and the disk.
    assert_not_contains "HEAD holds the recorded bytes, not the hook's" \
        "$(git show HEAD:.crayon/units/disk-unit/unit.md)" "HOOKFORMATTED"
    cleanup
}

test_n36_t29c_hook_stages_an_unrelated_path_is_named_and_never_undone() {
    setup_repo
    install_rewrite_and_stage_unrelated_hook \
        ".crayon/units/t29c-unit/unit.md" "docs/other-page.md"

    crayon_unit_new t29c-unit "reference/t29c.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "the verb still succeeds" "0" "$rc"
    assert_file_contains "the unrelated path is warned by name" "err.txt" \
        "hook staged unrelated paths: docs/other-page.md"
    assert_eq "the unrelated path is never undone" "hook wrote this" \
        "$(cat docs/other-page.md)"
    # The tool's own pathspecs leaving the index is normal after a partial
    # commit (RESEARCH P-3) and must never be reported as a hook's doing.
    assert_not_contains "the verb's own pathspecs are not warned" \
        "$(cat err.txt)" ".crayon/units/t29c-unit/ledger.jsonl"
    cleanup
}

test_no_hook_is_silent() {
    setup_repo
    crayon_unit_new quiet-unit "reference/quiet.rst" >/dev/null 2>err.txt
    assert_eq "the verb succeeds" "0" "$?"
    assert_not_contains "no hook, no change warning" "$(cat err.txt)" "hook changed"
    assert_not_contains "no hook, no unrelated-path warning" "$(cat err.txt)" \
        "hook staged unrelated paths"
    cleanup
}

test_hook_whitespace_only_rewrite_is_detected() {
    setup_repo
    install_whitespace_hook ".crayon/units/ws-unit/unit.md"
    crayon_unit_new ws-unit "reference/ws.rst" >/dev/null 2>err.txt
    local rc=$?
    # The comparison is over raw bytes from `git show HEAD:<path>`, so a change
    # a diff would call invisible is still a change.
    assert_eq "a whitespace-only rewrite does not fail the verb" "0" "$rc"
    assert_file_contains "a whitespace-only rewrite is still detected" "err.txt" \
        "hook changed .crayon/units/ws-unit/unit.md after recording"
    cleanup
}

test_rejecting_hook_leaves_head_unchanged_and_a_classifiable_tail() {
    setup_repo
    install_rewrite_and_reject_hook ".crayon/units/reject-unit/unit.md"
    local head_before
    head_before=$(git rev-parse HEAD)

    crayon_unit_new reject-unit "reference/reject.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a rejecting hook leaves HEAD unchanged" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the verb reports the interrupted transition" "6" "$rc"
    assert_json_error "rejected commit" "err.txt" "uncommitted_tail"
    assert_file_exists "the ledger tail is present" ".crayon/units/reject-unit/ledger.jsonl"

    # The next verb classifies it from the record alone — resume --adopt is
    # phase-17 work, the classification is not.
    rm -f .git/hooks/pre-commit
    crayon_unit_new reject-unit "reference/reject.rst" >/dev/null 2>err2.txt
    assert_eq "the next verb classifies the tail" "6" "$?"
    assert_json_error "next verb" "err2.txt" "uncommitted_tail"
    cleanup
}

# --- shared fixtures for the plan-stage verbs --------------------------------


# Append a chained event of a kind no phase-16 verb emits yet (`generation`,
# `review accept`, `retired`) through the tool's OWN writer, then commit it, so
# a test can reach a state whose verb lands in plan 16-05 or phase 17. Nothing
# is hand-serialised: the envelope, the chain and the canonical bytes all come
# from `crayon` itself.
append_event() {
    local unit="$1" kind="$2"
    python3 -c '
import importlib.machinery, importlib.util, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
repo = os.getcwd()
unit, kind = sys.argv[2], sys.argv[3]
path = module.ledger_path(repo, unit)
records = module.read_events(path)
prev = module.chain_prev(records[-1][1]) if records else None
seq = len(records)
state = module.derive([event for event, _ in records], {"unit_md_sha": None, "paths": {}})
so = state["so"]
actor = {"name": "Test Author", "email": "test@example.com"}
events = []
if kind == "retired":
    events.append(module.build_event("retired", seq, prev, actor, None, {"note": "abandoned"}))
elif kind == "reviewer-edit":
    # The complete basis set over whatever is on disk right now. Used where a
    # test needs a basis WITHOUT a generation (brownfield, T24d) or a basis that
    # is an edit (T6) before `crayon edits` itself exists.
    gen = state["gen"]
    files = []
    for target in so["targets"]:
        page = os.path.join(repo, "docs", target)
        if not os.path.exists(page):
            continue
        with open(page, "rb") as handle:
            data = handle.read()
        files.append({"path": target, "sha256": module.sha256_bytes(data)})
    events.append(module.build_event("reviewer-edit", seq, prev, actor, None, {
        "files": files,
        "generation_seq": gen["seq"] if gen is not None else None,
        "note": "fixture reviewer edit",
    }))
else:
    files = []
    for target in so["targets"]:
        page = os.path.join(repo, "docs", target)
        parent = os.path.dirname(page)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(page):
            with open(page, "w", encoding="utf-8") as handle:
                handle.write("fixture page\n")
        with open(page, "rb") as handle:
            data = handle.read()
        files.append({"path": target, "sha256": module.sha256_bytes(data), "bytes": len(data)})
    events.append(module.build_event("generation", seq, prev, actor, None, {
        "files": files,
        "signoff_seq": so["seq"],
        "plan_hash": so["plan_hash"],
        "model": "fixture-model",
        "model_origin": "configured",
        "basis_seq": None,
        "unsteered": False,
    }))
    if kind == "sealed":
        events.append(module.build_event("review", seq + 1, None, actor, None, {
            "verdict": "accept",
            "generation_seq": seq,
            "note": "fixture accept",
            "basis_seq": seq,
            "files": files,
            "resolves": [],
            "withdraws": [],
        }))
module.append_batch(path, module.chain_lines(events))
' "$CRAYON" "$unit" "$kind"
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: ${kind} ${unit}" >/dev/null 2>&1
}

# CR-04: append ONE event with a caller-supplied payload, chained through the
# tool's own writer. `verify_chain` checks `seq` contiguity and `prev` digests
# and nothing beneath them, so this is exactly the shape a hand-repaired,
# forged or future-tool-written ledger has: chain-valid, structurally
# unexpected, and accepted by stage a on every verb.
forge_event() {
    local unit="$1" kind="$2" payload="$3"
    python3 -c '
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
repo = os.getcwd()
unit, kind, payload = sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
path = module.ledger_path(repo, unit)
records = module.read_events(path)
prev = module.chain_prev(records[-1][1]) if records else None
event = module.build_event(kind, len(records), prev,
                           {"name": "Test Author", "email": "test@example.com"},
                           None, payload)
module.append_batch(path, module.chain_lines([event]))
' "$CRAYON" "$unit" "$kind" "$payload"
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: forged ${kind} ${unit}" >/dev/null 2>&1
}

# CR-04: a `TypeError` raised while deriving state from a damaged-but-chain-valid
# ledger escaped all four of `main`'s arms, printed a Python traceback on stderr
# and exited 1 — which contract 5.7 and REASONS both define as a GATE refusal
# ("no signoff / plan stale / drift"). `derive()` runs on EVERY verb including
# the read-only `show` an author reaches for precisely when the record is
# damaged, so the invariant this file states three times ("one JSON line —
# never zero, never two, never a stack trace") was reachable from any committed
# `.crayon/`.
test_cr04_a_withdraws_entry_without_a_seq_does_not_crash_show() {
    setup_repo
    crayon_unit_new wd-unit "reference/wd.rst" >/dev/null 2>&1
    "$CRAYON" signoff wd-unit >/dev/null 2>&1
    forge_event wd-unit review \
        '{"verdict":"accept","generation_seq":null,"note":"forged","basis_seq":null,"files":[],"resolves":[],"withdraws":[{"note":"no seq"}]}'
    assert_eq "the forged ledger is still chain-valid" "[]" "$(chain_problems wd-unit)"

    "$CRAYON" show wd-unit >out.txt 2>err.txt
    local rc=$?
    assert_not_contains "show prints no Python traceback" "$(cat err.txt)" "Traceback"
    assert_not_contains "show prints no TypeError" "$(cat err.txt)" "TypeError"
    assert_eq "show writes nothing to stderr" "" "$(cat err.txt)"
    assert_eq "show exits 0, not the gate code 1" "0" "$rc"
    assert_contains "show still derives a state" "$(cat out.txt)" "state:"
    assert_contains "show still routes" "$(cat out.txt)" "Next:"
    cleanup
}

test_cr04_a_recorded_path_that_is_not_a_string_refuses_on_every_reader() {
    setup_repo
    crayon_unit_new np-unit "reference/np.rst" >/dev/null 2>&1
    "$CRAYON" signoff np-unit >/dev/null 2>&1
    forge_event np-unit generation \
        '{"files":[{"path":null,"sha256":"0000000000000000000000000000000000000000000000000000000000000000","bytes":1}],"signoff_seq":2,"plan_hash":null,"model":"m","model_origin":"configured","basis_seq":null,"unsteered":false}'
    assert_eq "the forged ledger is still chain-valid" "[]" "$(chain_problems np-unit)"

    "$CRAYON" show np-unit >/dev/null 2>err.txt
    assert_eq "show exits 6 (ledger/recovery), not the gate code 1" "6" "$?"
    assert_json_error "a non-string recorded path via show" "err.txt" "ledger_corrupt"
    assert_not_contains "show prints no Python traceback" "$(cat err.txt)" "Traceback"

    "$CRAYON" summary np-unit --md >/dev/null 2>err2.txt
    assert_eq "summary --md exits 6, not the gate code 1" "6" "$?"
    assert_json_error "a non-string recorded path via summary" "err2.txt" "ledger_corrupt"
    assert_not_contains "summary prints no Python traceback" "$(cat err2.txt)" "Traceback"
    cleanup
}


# CR-05: every WRITE path runs `validate_target` (which refuses `..` segments,
# absolute paths and backslashes) and `contained()`. Every READ path ran
# neither: `read_fs`, `read_page_bytes` and `render_diff` took the path straight
# out of the ledger's `signoff.targets` / `basis.files[].path` and joined it
# onto the repo root. `.crayon/` is COMMITTED, so the reviewer's own
# `crayon show <unit> --diff` printed the contents of an arbitrary host file
# named by an untrusted branch, `show --json` returned its sha256, and
# `crayon edits` recorded that digest into a committed ledger — an offline
# content oracle for files outside the repository. This is
# `validate_source`'s own argument applied to the DERIVED path as well as the
# declared one.
test_cr05_a_recorded_path_outside_the_docs_root_is_never_read() {
    setup_repo
    local outside relative digest
    outside=$(mktemp -d)
    printf 'SECRET-TOKEN-abc123\n' >"$outside/outside-secret.txt"
    digest=$(sha256_of_text "SECRET-TOKEN-abc123
")
    crayon_unit_new esc-unit "reference/esc.rst" >/dev/null 2>&1
    "$CRAYON" signoff esc-unit >/dev/null 2>&1
    relative=$(forge_escaping_target esc-unit "$outside/outside-secret.txt")
    assert_contains "the forged target really does traverse out" "$relative" ".."
    assert_eq "the forged ledger is still chain-valid" "[]" "$(chain_problems esc-unit)"

    # --diff is the leak the review reproduced: the bytes themselves.
    "$CRAYON" show esc-unit --diff >out.txt 2>err.txt
    assert_eq "show --diff exits 6 (ledger/recovery)" "6" "$?"
    assert_json_error "an escaping recorded path via show --diff" "err.txt" \
        "ledger_corrupt"
    assert_not_contains "the host file's contents are never printed" \
        "$(cat out.txt)" "SECRET-TOKEN-abc123"
    assert_not_contains "the host file's contents never reach stderr either" \
        "$(cat err.txt)" "SECRET-TOKEN-abc123"

    # --json is the digest half: an existence-and-content oracle even without
    # the bytes.
    "$CRAYON" show esc-unit --json >j.txt 2>/dev/null
    assert_eq "show --json exits 6" "6" "$?"
    assert_not_contains "no digest of the host file is returned" "$(cat j.txt)" \
        "$digest"

    # summary --md is documented as paste-ready PR text, so its derived data
    # can be published.
    "$CRAYON" summary esc-unit --md >s.txt 2>err2.txt
    assert_eq "summary --md exits 6" "6" "$?"
    assert_not_contains "no digest of the host file is published" "$(cat s.txt)" \
        "$digest"

    # `edits` never called guard_targets, so the digest landed in a COMMITTED
    # ledger.
    local ledger_before head_before
    ledger_before=$(ledger_digest esc-unit)
    head_before=$(git rev-parse HEAD)
    "$CRAYON" edits esc-unit --note "record what I already did" >/dev/null 2>err3.txt
    assert_eq "edits exits 6" "6" "$?"
    assert_json_error "an escaping recorded path via edits" "err3.txt" \
        "ledger_corrupt"
    assert_eq "edits appends nothing to the ledger" "$ledger_before" \
        "$(ledger_digest esc-unit)"
    assert_eq "edits commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "no digest of the host file is ever committed" "0" \
        "$(grep -c -- "$digest" .crayon/units/esc-unit/ledger.jsonl || true)"

    rm -rf "$outside"
    cleanup
}

# Vacuous-pass guard for the test above: with the containment check mis-scoped
# so that it refuses everything, the assertions there would all pass while
# `show --diff` had stopped working. An ordinary in-root target must still be
# digested, still be reported as drifted, and still have its bytes diffed.
test_cr05_an_ordinary_recorded_path_is_still_read_and_diffed() {
    setup_repo
    crayon_unit_new ok-unit "reference/ok.rst" >/dev/null 2>&1
    "$CRAYON" signoff ok-unit >/dev/null 2>&1
    append_event ok-unit generation
    printf 'EDITED IN PLACE\n' >docs/reference/ok.rst

    local out
    out=$("$CRAYON" show ok-unit --diff 2>err.txt)
    assert_eq "show --diff over an in-root target exits 0" "0" "$?"
    assert_contains "the in-root page is reported" "$out" "reference/ok.rst"
    assert_contains "the in-root page is reported as drifted" "$out" "drifted"
    assert_contains "the in-root page's current bytes are diffed" "$out" \
        "EDITED IN PLACE"
    cleanup
}

# CR-05 (re-opened in round 5): the round-4 fix contained a recorded page
# *within whatever `docs` resolves to* and never restated `guard_targets`'
# companion check that `docs` itself resolves inside the repository. A git tree
# can carry `docs` as mode 120000, so the same untrusted branch that carries a
# forged ledger carries the link that makes an ordinary-looking in-root target
# resolve to the reviewer's home directory. Both are ordinary committed blobs;
# the reviewer types nothing beyond `crayon show`.
test_cr05_a_committed_docs_symlink_never_reads_through_to_the_host() {
    setup_repo
    local outside digest rc
    outside=$(mktemp -d)
    mkdir -p "$outside/reference"
    printf 'SECRET-TOKEN-xyz789\n' >"$outside/reference/esc.rst"
    digest=$(sha256_of_text "SECRET-TOKEN-xyz789
")
    crayon_unit_new sym-unit "reference/esc.rst" >/dev/null 2>&1
    "$CRAYON" signoff sym-unit >/dev/null 2>&1

    # The ledger is honest: `reference/esc.rst` spells no `..` and is an
    # ordinary in-root target. The escape is the SECOND committed blob.
    rm -rf docs
    ln -s "$outside" docs
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: docs committed as a symlink" >/dev/null 2>&1
    assert_eq "docs really is committed as a symlink (mode 120000)" "120000" \
        "$(git ls-tree HEAD docs | awk '{print $1}')"
    assert_eq "the link really does reach the host file" "SECRET-TOKEN-xyz789" \
        "$(cat docs/reference/esc.rst)"

    # --diff is the leak: the host file's bytes, printed to the reviewer.
    "$CRAYON" show sym-unit --diff >out.txt 2>err.txt
    rc=$?
    assert_eq "show --diff over a symlinked docs root exits 2" "2" "$rc"
    assert_json_error "a symlinked docs root via show --diff" "err.txt" \
        "bad_write_path"
    assert_not_contains "the host file's contents are never printed" \
        "$(cat out.txt)" "SECRET-TOKEN-xyz789"
    assert_not_contains "the host file's contents never reach stderr either" \
        "$(cat err.txt)" "SECRET-TOKEN-xyz789"

    # --json is the digest half: a content oracle even without the bytes.
    "$CRAYON" show sym-unit --json >j.txt 2>/dev/null
    assert_eq "show --json exits 2" "2" "$?"
    assert_not_contains "no digest of the host file is returned" "$(cat j.txt)" \
        "$digest"

    # summary --md is documented as paste-ready PR text.
    "$CRAYON" summary sym-unit --md >s.txt 2>err2.txt
    assert_eq "summary --md exits 2" "2" "$?"
    assert_not_contains "no digest of the host file is published" "$(cat s.txt)" \
        "$digest"

    # `edits` is the offline oracle: the digest used to land in a COMMITTED,
    # hash-chained ledger.
    local ledger_before head_before
    ledger_before=$(ledger_digest sym-unit)
    head_before=$(git rev-parse HEAD)
    "$CRAYON" edits sym-unit --note "record what I already did" >/dev/null 2>err3.txt
    assert_eq "edits exits 2" "2" "$?"
    assert_json_error "a symlinked docs root via edits" "err3.txt" \
        "bad_write_path"
    assert_eq "edits appends nothing to the ledger" "$ledger_before" \
        "$(ledger_digest sym-unit)"
    assert_eq "edits commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "no digest of the host file is ever committed" "0" \
        "$(grep -c -- "$digest" .crayon/units/sym-unit/ledger.jsonl || true)"

    rm -f docs
    rm -rf "$outside"
    cleanup
}

# CR-06 (a regression from the round-4 CR-05 fix): `contained()` resolves the
# LEAF with `realpath`, so it answers a question about the file on disk. The
# CR-05 fix reported that answer as if it were about the ledger — "recorded path
# 'reference/a.rst' resolves outside docs/ … inspect the ledger … next: resume"
# — for an ordinary symlinked page, a normal docs-repo pattern (a shared
# CHANGELOG.rst, a `docs/api -> ../src/api-docs` Sphinx tree). `find_claim` then
# escalated that single unit's refusal into a repo-wide one, so ONE linked page
# refused `unit new` and `signoff` for EVERY unit, and the recovery the hint
# named (`crayon show <that unit>`) refused identically.
test_cr06_a_symlinked_page_names_the_link_and_wedges_nothing_else() {
    setup_repo
    local outside rc
    outside=$(mktemp -d)
    printf 'shared changelog\n' >"$outside/CHANGELOG.rst"
    crayon_unit_new unit-a "reference/a.rst" >/dev/null 2>&1
    "$CRAYON" signoff unit-a >/dev/null 2>&1
    ln -s "$outside/CHANGELOG.rst" docs/reference/a.rst
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: a shared page linked in under docs/" >/dev/null 2>&1

    # Half 1 — the refusal tells the truth about which condition was hit.
    "$CRAYON" show unit-a >/dev/null 2>err.txt
    rc=$?
    assert_eq "a symlinked page exits 2 (bad input), not 6 (damaged record)" \
        "2" "$rc"
    assert_json_error "a symlinked page" "err.txt" "bad_write_path"
    assert_contains "the refusal names the one fact the author needs" \
        "$(cat err.txt)" "is a link that resolves outside"
    assert_not_contains "it does not blame the hash-chained record" \
        "$(cat err.txt)" "ledger"
    assert_not_contains "and does not route to resume, which cannot rewrite a link" \
        "$(cat err.txt)" "resume"
    assert_eq "the ledger it used to blame is in fact chain-valid" "[]" \
        "$(chain_problems unit-a)"

    # Half 2 — no cascade: every OTHER unit in the repository still works.
    crayon_unit_new unit-b "reference/b.rst" >/dev/null 2>err2.txt
    assert_eq "unit new for an unrelated unit still exits 0" "0" "$?"
    "$CRAYON" signoff unit-b >/dev/null 2>err3.txt
    assert_eq "signoff for an unrelated unit still exits 0" "0" "$?"
    assert_eq "the unrelated unit's ledger is chain-valid" "[]" \
        "$(chain_problems unit-b)"

    # The fall-through is a narrowing, not an opening: the write surface still
    # refuses to place a page through the link.
    crayon_unit_new unit-c "reference/a.rst" >/dev/null 2>err4.txt
    assert_eq "a unit that would write through the link is still refused" "2" "$?"
    assert_json_error "a target that is a link out of docs/" "err4.txt" \
        "bad_write_path"

    rm -f docs/reference/a.rst
    rm -rf "$outside"
    cleanup
}

# --- J1 continued: signoff, the HITL gate ------------------------------------

test_signoff_freezes_the_plan_hash_end_to_end() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    local before
    before=$(git rev-list --count HEAD)

    local out rc
    out=$("$CRAYON" signoff demo-unit 2>err.txt)
    rc=$?
    assert_eq "signoff exits 0" "0" "$rc"
    assert_eq "signoff prints exactly one stdout line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "signoff routes onward" "$out" "Next: draft"

    assert_eq "signoff appends exactly one ledger line" "3" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    local line3
    line3=$(ledger_line demo-unit 3)
    assert_eq "the appended event is a signoff" "signoff" \
        "$(printf '%s' "$line3" | json_field kind)"
    assert_eq "plan_hash is sha256 of the WHOLE unit.md" \
        "$(sha256_of_file .crayon/units/demo-unit/unit.md)" \
        "$(printf '%s' "$line3" | json_field plan_hash)"
    assert_eq "the first signoff supersedes nothing" "null" \
        "$(printf '%s' "$line3" | json_field supersedes)"
    assert_eq "the signoff records the declared intent" "reference" \
        "$(printf '%s' "$line3" | json_field intent)"
    assert_contains "the signoff records the signed targets" "$line3" \
        '"targets":["reference/demo.rst"]'

    assert_eq "signoff makes exactly one commit" "$((before + 1))" \
        "$(git rev-list --count HEAD)"
    assert_eq "signoff commit subject" "crayon: signed-off demo-unit" \
        "$(git log -1 --format=%s)"
    assert_eq "Crayon-Seq names the single event" "2" \
        "$(git log -1 --format='%(trailers:key=Crayon-Seq,valueonly)' | tr -d '\n')"
    assert_eq "Crayon-Phase is the signoff phase" "signed-off" \
        "$(git log -1 --format='%(trailers:key=Crayon-Phase,valueonly)' | tr -d '\n')"
    assert_eq "the derived state is signed-off" "signed-off" "$(derived demo-unit state)"
    assert_file_not_exists "signoff deletes pending/ on success" \
        ".crayon/staging/demo-unit/pending"
    cleanup
}

test_a_second_signoff_with_no_change_is_already_signed() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local head_before ledger_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" signoff demo-unit >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a second signoff exits 3" "3" "$rc"
    assert_json_error "already_signed" "err.txt" "already_signed"
    assert_eq "the no-op payload carries the existing event's seq" "2" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["seq"])' err.txt)"
    assert_eq "the no-op payload carries the current next" "draft" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next"])' err.txt)"
    assert_contains "the no-op payload carries a commit key" "$(cat err.txt)" '"commit"'
    assert_eq "the no-op appends no ledger line" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the no-op makes no commit" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_signoff_after_a_hand_edit_supersedes_the_previous_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local first_hash
    first_hash=$(printf '%s' "$(ledger_line demo-unit 3)" | json_field plan_hash)

    # The TA may edit unit.md by hand (contract 5.1); after signoff that sets
    # plan_stale, and re-signing is the recorded act that clears it.
    printf '\nA hand-written addition.\n' >>.crayon/units/demo-unit/unit.md
    assert_eq "a hand edit makes the plan stale" "re_sign" "$(derived demo-unit next)"

    "$CRAYON" signoff demo-unit >/dev/null 2>err.txt
    local rc=$?
    assert_eq "re-signing a changed plan exits 0" "0" "$rc"
    local line4
    line4=$(ledger_line demo-unit 4)
    assert_eq "the second signoff supersedes the first" "2" \
        "$(printf '%s' "$line4" | json_field supersedes)"
    assert_eq "the second signoff freezes the new bytes" \
        "$(sha256_of_file .crayon/units/demo-unit/unit.md)" \
        "$(printf '%s' "$line4" | json_field plan_hash)"
    assert_not_contains "the plan hash actually changed" "$line4" "$first_hash"
    assert_eq "the plan is no longer stale" "false" "$(derived demo-unit plan_stale)"
    cleanup
}

test_target_claimed_blocks_a_second_in_flight_unit() {
    setup_repo
    # Both units are declared before either signs off: the claim attaches to the
    # CURRENT SIGNOFF, so nothing is claimed while both are merely declared.
    crayon_unit_new first-unit "reference/shared.rst" >/dev/null 2>&1
    crayon_unit_new second-unit "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff first-unit >/dev/null 2>&1
    local head_before ledger_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest second-unit)

    "$CRAYON" signoff second-unit >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a claimed target exits 1" "1" "$rc"
    assert_json_error "target_claimed" "err.txt" "target_claimed"
    assert_file_contains "the detail names the claiming unit" "err.txt" "first-unit"
    assert_file_contains "the hint names the releasing command" "err.txt" "crayon unit retire"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest second-unit)"
    assert_eq "the refusal makes no commit" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_target_claimed_blocks_when_the_claiming_unit_is_sealed() {
    setup_repo
    crayon_unit_new first-unit "reference/shared.rst" >/dev/null 2>&1
    crayon_unit_new second-unit "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff first-unit >/dev/null 2>&1
    append_event first-unit sealed
    assert_eq "the claiming unit is sealed, not in flight" "sealed" \
        "$(derived first-unit state)"

    "$CRAYON" signoff second-unit >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a sealed claimant still blocks: exit 1" "1" "$rc"
    assert_json_error "target_claimed (sealed)" "err.txt" "target_claimed"
    assert_file_contains "the detail names the sealed claiming unit" "err.txt" "first-unit"
    cleanup
}

test_signoff_adopts_a_unit_with_no_ledger() {
    setup_repo
    # Brownfield: a hand-written plan file and no ledger at all. (Deleting a
    # COMMITTED ledger is a different situation — the committed prefix no longer
    # matches HEAD, and stage a refuses it 6 ledger_diverged.)
    mkdir -p .crayon/units/adopt-unit
    cat >.crayon/units/adopt-unit/unit.md <<'UNIT'
---
title: "Adopted"
intent: reference
audience: "TAs onboarding to the docs repo"
targets:
  - "reference/adopt.rst"
---
# Plan

An outline written by hand.
UNIT
    local before
    before=$(git rev-list --count HEAD)

    "$CRAYON" signoff adopt-unit >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an adopting signoff exits 0" "0" "$rc"
    assert_eq "the adopting batch is exactly three events" "3" \
        "$(wc -l <".crayon/units/adopt-unit/ledger.jsonl" | tr -d ' ')"
    assert_eq "line 1 is the ledger event" "ledger" \
        "$(printf '%s' "$(ledger_line adopt-unit 1)" | json_field kind)"
    assert_eq "line 2 is unit-declared" "unit-declared" \
        "$(printf '%s' "$(ledger_line adopt-unit 2)" | json_field kind)"
    assert_eq "line 2 is marked adopted" "True" \
        "$(printf '%s' "$(ledger_line adopt-unit 2)" | json_field adopted)"
    assert_eq "line 3 is the signoff" "signoff" \
        "$(printf '%s' "$(ledger_line adopt-unit 3)" | json_field kind)"
    assert_eq "the whole batch lands in ONE commit" "$((before + 1))" \
        "$(git rev-list --count HEAD)"
    assert_eq "Crayon-Seq spans the adopting batch" "0-2" \
        "$(git log -1 --format='%(trailers:key=Crayon-Seq,valueonly)' | tr -d '\n')"
    assert_contains "the adopting commit carries the hand-written unit.md" \
        "$(git show --name-only --format= HEAD)" ".crayon/units/adopt-unit/unit.md"
    cleanup
}

test_signoff_on_an_unknown_unit_is_refused() {
    setup_repo
    local head_before
    head_before=$(git rev-parse HEAD)
    "$CRAYON" signoff unknown-id >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an unknown unit exits 2" "2" "$rc"
    assert_json_error "unit_not_found" "err.txt" "unit_not_found"
    assert_eq "nothing is committed" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "no unit directory is created" ".crayon/units/unknown-id"
    cleanup
}

test_before_any_signoff_the_unit_is_declared_and_routes_to_sign_off() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    assert_eq "no signoff derives declared" "declared" "$(derived demo-unit state)"
    assert_eq "no signoff routes to sign_off" "sign_off" "$(derived demo-unit next)"
    cleanup
}

test_no_verb_exposes_a_force_flag() {
    setup_repo
    local found
    found=$("$CRAYON" --help 2>&1 | grep -c -- '--force')
    assert_eq "crayon --help carries no --force" "0" "$found"
    found=$("$CRAYON" signoff --help 2>&1 | grep -c -- '--force')
    assert_eq "signoff --help carries no --force" "0" "$found"
    cleanup
}

# T29 / T29b end to end: both routed tokens need a signoff to be reachable, so
# they could not be covered before this plan (recorded in .planning/WINDOWS.md).

test_signoff_routes_to_record_edits_when_the_target_already_exists() {
    setup_repo
    printf 'A brownfield page nobody told crayon about.\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1

    local out
    out=$("$CRAYON" signoff brown-unit 2>err.txt)
    assert_eq "signoff over an existing page exits 0" "0" "$?"
    assert_contains "an existing signed target routes to record_edits" "$out" \
        "Next: record_edits"
    assert_eq "the derived route agrees" "record_edits" "$(derived brown-unit next)"
    cleanup
}

test_n36_t29b_hook_that_rewrites_unit_md_routes_to_re_sign() {
    setup_repo
    crayon_unit_new t29b-unit "reference/t29b.rst" >/dev/null 2>&1
    install_rewrite_and_succeed_hook ".crayon/units/t29b-unit/unit.md"
    local before
    before=$(git rev-list --count HEAD)

    local out
    out=$("$CRAYON" signoff t29b-unit 2>err.txt)
    local rc=$?
    assert_eq "the transition stands" "0" "$rc"
    assert_eq "exactly one commit" "$((before + 1))" "$(git rev-list --count HEAD)"
    assert_file_contains "the warning names unit.md" "err.txt" \
        "hook changed .crayon/units/t29b-unit/unit.md after recording"
    assert_contains "state is re-derived: a changed unit.md is plan_stale" "$out" \
        "Next: re_sign"
    rm -f .git/hooks/pre-commit
    cleanup
}

# --- J3: unit edit — the amendment path --------------------------------------

test_unit_edit_amends_the_plan_and_routes_to_re_sign() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local before hash_before
    before=$(git rev-list --count HEAD)
    hash_before=$(sha256_of_file .crayon/units/demo-unit/unit.md)

    local out rc
    out=$("$CRAYON" unit edit demo-unit --audience "New readers" 2>err.txt)
    rc=$?
    assert_eq "a plain edit exits 0" "0" "$rc"
    assert_eq "a plain edit appends exactly one ledger line" "4" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    local line4
    line4=$(ledger_line demo-unit 4)
    assert_eq "the appended event is unit-edited" "unit-edited" \
        "$(printf '%s' "$line4" | json_field kind)"
    assert_eq "unit_hash_before is the pre-edit file" "$hash_before" \
        "$(printf '%s' "$line4" | json_field unit_hash_before)"
    assert_eq "unit_hash_after is the post-edit file" \
        "$(sha256_of_file .crayon/units/demo-unit/unit.md)" \
        "$(printf '%s' "$line4" | json_field unit_hash_after)"
    assert_contains "the new frontmatter is recorded" "$line4" '"audience":"New readers"'
    assert_file_contains "unit.md carries the new audience" \
        ".crayon/units/demo-unit/unit.md" "New readers"
    assert_eq "a plain edit makes exactly one commit" "$((before + 1))" \
        "$(git rev-list --count HEAD)"
    assert_eq "the commit subject names the phase" "crayon: edited demo-unit" \
        "$(git log -1 --format=%s)"
    assert_contains "editing a signed plan routes to re_sign" "$out" "Next: re_sign"
    assert_eq "the plan is stale after a plain edit" "true" "$(derived demo-unit plan_stale)"
    cleanup
}

test_unit_edit_with_no_change_is_noop_unchanged() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local head_before ledger_before unit_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest demo-unit)
    unit_before=$(sha256_of_file .crayon/units/demo-unit/unit.md)

    "$CRAYON" unit edit demo-unit >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an edit that changes nothing exits 3" "3" "$rc"
    assert_json_error "noop_unchanged" "err.txt" "noop_unchanged"
    assert_eq "the no-op appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the no-op makes no commit" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the no-op leaves unit.md byte-unchanged" "$unit_before" \
        "$(sha256_of_file .crayon/units/demo-unit/unit.md)"
    cleanup
}

test_unit_edit_re_sign_is_one_command_one_commit_and_two_events() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local before lines_before
    before=$(git rev-list --count HEAD)
    lines_before=$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')

    local out rc
    out=$("$CRAYON" unit edit demo-unit --audience "Amended audience" --re-sign 2>err.txt)
    rc=$?
    assert_eq "a re-sign exits 0" "0" "$rc"
    assert_eq "a re-sign appends exactly two ledger lines" "$((lines_before + 2))" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    assert_eq "the first of the batch is unit-edited" "unit-edited" \
        "$(printf '%s' "$(ledger_line demo-unit $((lines_before + 1)))" | json_field kind)"
    assert_eq "the second of the batch is the signoff" "signoff" \
        "$(printf '%s' "$(ledger_line demo-unit $((lines_before + 2)))" | json_field kind)"
    assert_eq "the re-signed signoff supersedes the previous one" "2" \
        "$(printf '%s' "$(ledger_line demo-unit $((lines_before + 2)))" | json_field supersedes)"
    assert_eq "ONE command is ONE commit" "$((before + 1))" "$(git rev-list --count HEAD)"
    local seq_trailer
    seq_trailer=$(git log -1 --format='%(trailers:key=Crayon-Seq,valueonly)' | tr -d '\n')
    assert_eq "Crayon-Seq spans the 2-event batch" "yes" \
        "$(printf '%s' "$seq_trailer" | grep -qE '^[0-9]+-[0-9]+$' && echo yes || echo no)"
    assert_eq "the plan is no longer stale" "false" "$(derived demo-unit plan_stale)"
    assert_not_contains "the success line no longer routes to re_sign" "$out" "Next: re_sign"
    cleanup
}

test_unit_edit_adding_a_claimed_target_is_refused() {
    setup_repo
    crayon_unit_new first-unit "reference/shared.rst" >/dev/null 2>&1
    "$CRAYON" signoff first-unit >/dev/null 2>&1
    crayon_unit_new second-unit "reference/second.rst" >/dev/null 2>&1
    local head_before ledger_before unit_before
    head_before=$(git rev-parse HEAD)
    ledger_before=$(ledger_digest second-unit)
    unit_before=$(sha256_of_file .crayon/units/second-unit/unit.md)

    "$CRAYON" unit edit second-unit --also-target "reference/shared.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "claiming another unit's target exits 1" "1" "$rc"
    assert_json_error "target_claimed on edit" "err.txt" "target_claimed"
    assert_file_contains "the detail names the claiming unit" "err.txt" "first-unit"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest second-unit)"
    assert_eq "the refusal makes no commit" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the refusal leaves unit.md byte-unchanged" "$unit_before" \
        "$(sha256_of_file .crayon/units/second-unit/unit.md)"
    cleanup
}

test_unit_edit_re_sign_reports_a_dropped_target_once_and_keeps_it_on_disk() {
    setup_repo
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    printf 'the orphaned page\n' >docs/reference/two.rst

    local out rc
    out=$("$CRAYON" unit edit multi-unit --target "reference/one.rst" --re-sign 2>err.txt)
    rc=$?
    assert_eq "dropping a target exits 0" "0" "$rc"
    assert_file_exists "the orphaned page is kept on disk" "docs/reference/two.rst"
    assert_eq "the orphaned page is never rewritten" "the orphaned page" \
        "$(cat docs/reference/two.rst)"
    assert_eq "the success line names the orphan exactly once" "1" \
        "$(printf '%s\n' "$out" | grep -o 'reference/two.rst' | wc -l | tr -d ' ')"
    assert_contains "the orphan is described, not deleted" "$out" \
        "no longer a target; kept on disk"
    assert_eq "the new signoff lists only the surviving target" \
        '"targets":["reference/one.rst"]' \
        "$(ledger_line multi-unit 5 | grep -o '"targets":\[[^]]*\]')"
    cleanup
}

test_unit_edit_on_an_invalid_unit_md_names_the_line_and_the_flag() {
    setup_repo
    crayon_unit_new bad-unit "reference/bad.rst" >/dev/null 2>&1
    # A hand edit that leaves the contract 5.6 subset.
    sed -i 's/^intent: .*/intent: "bogus"/' .crayon/units/bad-unit/unit.md
    local head_before
    head_before=$(git rev-parse HEAD)

    "$CRAYON" unit edit bad-unit --audience "Anyone" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an out-of-subset unit.md exits 2" "2" "$rc"
    assert_json_error "unit_invalid" "err.txt" "unit_invalid"
    assert_file_contains "the detail names the 1-based line" "err.txt" "line 3:"
    assert_file_contains "the hint names the flag that fixes it" "err.txt" "--intent"
    assert_eq "nothing is committed" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_unit_edit_on_an_unknown_unit_is_refused() {
    setup_repo
    local head_before
    head_before=$(git rev-parse HEAD)
    "$CRAYON" unit edit unknown-id --audience "Anyone" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an unknown unit exits 2" "2" "$rc"
    assert_json_error "unit_not_found on edit" "err.txt" "unit_not_found"
    assert_file_not_exists "no unit directory is created" ".crayon/units/unknown-id"
    assert_eq "nothing is committed" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_unit_edit_replaces_the_body_from_stdin() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    printf '# Plan\n\nA rewritten outline.\n' |
        "$CRAYON" unit edit demo-unit --body-file - >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a body-only edit exits 0" "0" "$rc"
    assert_file_contains "the new body is on disk" ".crayon/units/demo-unit/unit.md" \
        "A rewritten outline."
    assert_eq "a body-only edit appends one ledger line" "3" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    assert_eq "the appended event is unit-edited" "unit-edited" \
        "$(printf '%s' "$(ledger_line demo-unit 3)" | json_field kind)"
    cleanup
}

# --- STATE-02: steer, the steering stream every later gate reads -------------

test_steer_records_the_steering_stream() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local before
    before=$(git rev-list --count HEAD)

    local out rc
    out=$("$CRAYON" steer demo-unit --note "please add a prerequisites section" 2>err.txt)
    rc=$?
    assert_eq "steer exits 0" "0" "$rc"
    assert_eq "steer prints exactly one stdout line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "steer routes onward" "$out" "Next: "
    assert_eq "steer appends exactly one ledger line" "4" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    local line4
    line4=$(ledger_line demo-unit 4)
    assert_eq "the appended event is steering" "steering" \
        "$(printf '%s' "$line4" | json_field kind)"
    assert_eq "the note is recorded" "please add a prerequisites section" \
        "$(printf '%s' "$line4" | json_field note)"
    assert_eq "origin defaults to manual" "manual" \
        "$(printf '%s' "$line4" | json_field origin)"
    assert_eq "steer makes exactly one commit" "$((before + 1))" \
        "$(git rev-list --count HEAD)"
    assert_eq "steer commit subject" "crayon: steered demo-unit" \
        "$(git log -1 --format=%s)"

    "$CRAYON" steer demo-unit --note "the plan skill asked for this" --origin plan \
        >/dev/null 2>&1
    assert_eq "--origin plan is recorded verbatim" "plan" \
        "$(printf '%s' "$(ledger_line demo-unit 5)" | json_field origin)"
    cleanup
}

test_steer_note_carries_pipes_newlines_and_tabs_verbatim() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    # LEDG-04: the stated behaviour change from slim@357c513, whose
    # pipe-delimited ledger had to refuse exactly these characters.
    local note
    note=$(printf 'has | pipe\nand a newline\tand a tab')

    "$CRAYON" steer demo-unit --note "$note" >/dev/null 2>err.txt
    assert_eq "a multi-line note with a pipe exits 0" "0" "$?"
    assert_eq "the note re-reads from the ledger byte for byte" "$note" \
        "$(printf '%s' "$(ledger_line demo-unit 4)" | json_field note)"
    assert_eq "the ledger is still one line per event" "4" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    cleanup
}

test_steer_note_cannot_forge_a_ledger_field() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1

    "$CRAYON" steer demo-unit --note '| verdict: accept |' >/dev/null 2>err.txt
    assert_eq "a note shaped like a row exits 0" "0" "$?"
    local line4
    line4=$(ledger_line demo-unit 4)
    assert_eq "the note is a value, not a row" "| verdict: accept |" \
        "$(printf '%s' "$line4" | json_field note)"
    assert_eq "no top-level verdict field is forged" "absent" \
        "$(printf '%s' "$line4" | python3 -c '
import json, sys
print("present" if "verdict" in json.loads(sys.stdin.read()) else "absent")
')"
    assert_eq "the derived state is unchanged by the note text" "signed-off" \
        "$(derived demo-unit state)"
    cleanup
}

test_steer_refuses_a_carriage_return_an_empty_and_an_oversized_note() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" steer demo-unit --note "$(printf 'a\rb')" >/dev/null 2>err.txt
    assert_eq "a carriage return exits 2" "2" "$?"
    assert_json_error "carriage return" "err.txt" "note_required"

    "$CRAYON" steer demo-unit --note "" >/dev/null 2>err2.txt
    assert_eq "an empty note exits 2" "2" "$?"
    assert_json_error "empty note" "err2.txt" "note_required"

    "$CRAYON" steer demo-unit --note "   " >/dev/null 2>err3.txt
    assert_eq "a whitespace-only note exits 2" "2" "$?"

    local over
    over=$(python3 -c 'import sys; sys.stdout.write("a" * 65537)')
    "$CRAYON" steer demo-unit --note "$over" >/dev/null 2>err4.txt
    assert_eq "a 65537-byte note exits 2" "2" "$?"
    assert_json_error "over the note cap" "err4.txt" "note_required"

    assert_eq "no refused note appends anything" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "no refused note commits anything" "$head_before" "$(git rev-parse HEAD)"

    local at_cap
    at_cap=$(python3 -c 'import sys; sys.stdout.write("a" * 65536)')
    "$CRAYON" steer demo-unit --note "$at_cap" >/dev/null 2>err5.txt
    assert_eq "a 65536-byte note is accepted (the cap is inclusive)" "0" "$?"
    assert_eq "the accepted note appends one line" "4" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    cleanup
}

test_steer_refuses_an_unknown_origin() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" steer demo-unit --origin bogus --note "x" >/dev/null 2>err.txt
    assert_eq "an unknown origin exits 2" "2" "$?"
    assert_json_error "unknown origin" "err.txt" "bad_target"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    cleanup
}

test_steer_before_any_signoff_is_no_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" steer demo-unit --note "too early" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "steering an unsigned plan exits 1" "1" "$rc"
    assert_json_error "no_signoff" "err.txt" "no_signoff"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_steer_on_a_retired_unit_is_refused() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    append_event demo-unit retired
    assert_eq "the unit is retired" "retired" "$(derived demo-unit state)"
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" steer demo-unit --note "too late" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "steering a retired unit exits 1" "1" "$rc"
    assert_json_error "retired" "err.txt" "retired"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    cleanup
}

test_steer_reads_a_note_from_stdin() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1

    printf 'a note that arrived on stdin' |
        "$CRAYON" steer demo-unit --note-file - >/dev/null 2>err.txt
    assert_eq "--note-file - exits 0" "0" "$?"
    assert_eq "the stdin note is recorded identically" "a note that arrived on stdin" \
        "$(printf '%s' "$(ledger_line demo-unit 4)" | json_field note)"

    printf 'a note that arrived in a file' >note.txt
    "$CRAYON" steer demo-unit --note-file note.txt >/dev/null 2>err2.txt
    assert_eq "--note-file F exits 0" "0" "$?"
    assert_eq "the file note is recorded identically" "a note that arrived in a file" \
        "$(printf '%s' "$(ledger_line demo-unit 5)" | json_field note)"
    cleanup
}

test_steer_makes_the_next_draft_steerable() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    append_event demo-unit generation
    assert_eq "a fresh generation has no steering after it" "false" \
        "$(derived demo-unit steered_since_gen)"

    "$CRAYON" steer demo-unit --note "restore the removed section" >/dev/null 2>err.txt
    assert_eq "steer exits 0 over a generation" "0" "$?"
    assert_eq "steering after a generation satisfies the steering gate" "true" \
        "$(derived demo-unit steered_since_gen)"
    assert_eq "the steering request is pending" "1" \
        "$(derived demo-unit pending | python3 -c '
import json, sys
print(len(json.loads(sys.stdin.read())))
')"
    cleanup
}

# --- VERB-04 / STATE-05: draft, the first verb that moves bytes --------------


event_paths() {
    python3 -c '
import json, sys
print(" ".join(e.get("path") for e in json.loads(sys.stdin.read()).get("files") or []))
'
}

test_j1_draft_writes_the_page_and_records_the_generation() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "Demo\n====\n\nThe drafted body.\n"
    local before lines_before
    before=$(git rev-list --count HEAD)
    lines_before=$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')

    local out rc
    out=$("$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --model "fixture-model" --model-origin configured 2>err.txt)
    rc=$?
    assert_eq "draft exits 0" "0" "$rc"
    assert_eq "draft prints exactly one stdout line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "the draft response routes to review" "$out" "Next: review"
    assert_eq "the response ends with the routed token" "Next: review" "${out##* · }"

    assert_file_exists "the page is written" "docs/reference/demo.rst"
    assert_eq "the page holds the staging bytes" \
        "$(sha256_of_file "$(draft_path demo-unit reference/demo.rst)")" \
        "$(sha256_of_file docs/reference/demo.rst)"

    assert_eq "draft appends exactly one ledger line" "$((lines_before + 1))" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    local gen
    gen=$(ledger_line demo-unit $((lines_before + 1)))
    assert_eq "the appended event is a generation" "generation" \
        "$(printf '%s' "$gen" | json_field kind)"
    assert_eq "files[] is exactly the signed target set" \
        "reference/demo.rst $(sha256_of_file docs/reference/demo.rst) $(wc -c <docs/reference/demo.rst | tr -d ' ')" \
        "$(printf '%s' "$gen" | event_files)"
    assert_eq "the generation cites the current signoff" "2" \
        "$(printf '%s' "$gen" | json_field signoff_seq)"
    assert_eq "the generation freezes the signed plan hash" \
        "$(sha256_of_file .crayon/units/demo-unit/unit.md)" \
        "$(printf '%s' "$gen" | json_field plan_hash)"
    assert_eq "the model claim is recorded verbatim" "fixture-model" \
        "$(printf '%s' "$gen" | json_field model)"
    assert_eq "the model origin is recorded" "configured" \
        "$(printf '%s' "$gen" | json_field model_origin)"
    assert_eq "a first draft has no basis" "null" \
        "$(printf '%s' "$gen" | json_field basis_seq)"
    assert_eq "a gated draft is not unsteered" "False" \
        "$(printf '%s' "$gen" | json_field unsteered)"

    assert_eq "draft makes exactly one commit" "$((before + 1))" "$(git rev-list --count HEAD)"
    assert_eq "draft commit subject" "crayon: drafted demo-unit" "$(git log -1 --format=%s)"
    assert_eq "Crayon-Phase is the draft phase" "drafted" \
        "$(git log -1 --format='%(trailers:key=Crayon-Phase,valueonly)' | tr -d '\n')"
    local committed
    committed=$(git show --name-only --format= HEAD)
    assert_contains "the commit carries the page" "$committed" "docs/reference/demo.rst"
    assert_contains "the commit carries the ledger" "$committed" \
        ".crayon/units/demo-unit/ledger.jsonl"
    assert_eq "the derived state is drafted" "drafted" "$(derived demo-unit state)"
    assert_file_not_exists "draft deletes pending/ on success" \
        ".crayon/staging/demo-unit/pending"
    cleanup
}

test_draft_without_a_model_records_the_honest_unknown_default() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "body\n"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    assert_eq "a draft with no model claim exits 0" "0" "$?"
    local gen
    gen=$(ledger_line demo-unit 4)
    assert_eq "an unrecorded model is the empty string" "" \
        "$(printf '%s' "$gen" | json_field model)"
    assert_eq "its origin is the honest unknown" "unknown" \
        "$(printf '%s' "$gen" | json_field model_origin)"
    cleanup
}

test_draft_refuses_a_model_that_contradicts_its_origin() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "body\n"
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --model "claimed" --model-origin unknown >/dev/null 2>err.txt
    assert_eq "a named model with an unknown origin exits 2" "2" "$?"
    assert_json_error "model/origin contradiction" "err.txt" "bad_target"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_file_not_exists "the refusal writes no page" "docs/reference/demo.rst"
    cleanup
}

test_draft_writes_every_signed_target_from_a_directory_source() {
    setup_repo
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/one.rst" "page one\n"
    stage_draft multi-unit "reference/two.rst" "page two\n"
    local before
    before=$(git rev-list --count HEAD)

    local out rc
    out=$("$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" 2>err.txt)
    rc=$?
    assert_eq "a directory source exits 0" "0" "$rc"
    assert_eq "page one holds its staging bytes" "page one" "$(cat docs/reference/one.rst)"
    assert_eq "page two holds its staging bytes" "page two" "$(cat docs/reference/two.rst)"
    assert_eq "both pages land in ONE commit" "$((before + 1))" "$(git rev-list --count HEAD)"
    assert_eq "files[] lists both targets in the signoff's order" \
        "reference/one.rst reference/two.rst" \
        "$(printf '%s' "$(ledger_line multi-unit 4)" | event_paths)"

    local committed
    committed=$(git show --name-only --format= HEAD | LC_ALL=C sort | tr '\n' ' ')
    assert_eq "the commit carries exactly the two pages and the ledger" \
        ".crayon/units/multi-unit/ledger.jsonl docs/reference/one.rst docs/reference/two.rst " \
        "$committed"
    assert_contains "the response names the file count" "$out" "2 file(s)"
    cleanup
}

test_draft_crash_after_page_one_leaves_a_classifiable_tail() {
    setup_repo
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/one.rst" "page one\n"
    stage_draft multi-unit "reference/two.rst" "page two\n"
    local head_before
    head_before=$(git rev-parse HEAD)

    CRAYON_CRASH_AT=place:1 "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" \
        >/dev/null 2>&1
    assert_eq "the crash at place:1 is a hard exit" "137" "$?"
    assert_file_exists "page 1 is placed" "docs/reference/one.rst"
    assert_file_not_exists "page 2 is absent" "docs/reference/two.rst"
    assert_eq "nothing was committed" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the ledger carries the uncommitted tail" "4" \
        "$(wc -l <".crayon/units/multi-unit/ledger.jsonl" | tr -d ' ')"

    "$CRAYON" steer multi-unit --note "anything at all" >/dev/null 2>err.txt
    assert_eq "the next mutating verb exits 6" "6" "$?"
    assert_json_error "uncommitted_tail" "err.txt" "uncommitted_tail"
    cleanup
}

test_draft_before_any_signoff_is_no_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "body\n"
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "drafting an unsigned plan exits 1" "1" "$rc"
    assert_json_error "no_signoff" "err.txt" "no_signoff"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "the refusal writes no page" "docs/reference/demo.rst"
    cleanup
}

test_draft_on_a_retired_unit_is_refused() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    append_event demo-unit retired
    stage_draft demo-unit "reference/demo.rst" "body\n"
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    assert_eq "drafting a retired unit exits 1" "1" "$?"
    assert_json_error "retired" "err.txt" "retired"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_file_not_exists "the refusal writes no page" "docs/reference/demo.rst"
    cleanup
}

test_n08_draft_after_a_hand_edit_to_unit_md_is_plan_stale() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "body\n"
    printf '\nA hand-written addition.\n' >>.crayon/units/demo-unit/unit.md
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "drafting a stale plan exits 1" "1" "$rc"
    assert_json_error "plan_stale" "err.txt" "plan_stale"
    assert_eq "the refusal routes to re_sign" "re_sign" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next"])' err.txt)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "the refusal writes no page" "docs/reference/demo.rst"
    cleanup
}

test_n10_t5_draft_over_a_hand_edited_basis_page_is_page_drift() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "first body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1

    # A hand edit, committed OUTSIDE crayon: drift is git-independent, so the
    # commit changes nothing about the refusal.
    printf 'hand-edited by the author\n' >docs/reference/demo.rst
    git add -A && git commit -q -m "author edit"
    stage_draft demo-unit "reference/demo.rst" "second body\n"
    "$CRAYON" steer demo-unit --note "please rewrite the intro" >/dev/null 2>&1
    local ledger_before head_before page_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)
    page_before=$(sha256_of_file docs/reference/demo.rst)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "drafting over a drifted page exits 1" "1" "$rc"
    assert_json_error "page_drift" "err.txt" "page_drift"
    assert_eq "the refusal routes to record_edits" "record_edits" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next"])' err.txt)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the author's bytes are untouched" "$page_before" \
        "$(sha256_of_file docs/reference/demo.rst)"

    # T5's tail: recording the hand edit clears the drift, and the SAME draft
    # then lands — `edits` has no drift precondition of its own (T9).
    "$CRAYON" edits demo-unit --note "keeping the author's rewrite" >/dev/null 2>err2.txt
    assert_eq "edits over the drift exits 0" "0" "$?"
    assert_eq "the drift is resolved" "false" "$(derived demo-unit page_drift)"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err3.txt
    assert_eq "the same draft now exits 0" "0" "$?"
    assert_eq "the page carries the redrafted bytes" "second body" \
        "$(cat docs/reference/demo.rst)"
    cleanup
}

test_draft_over_an_unadopted_existing_page_is_target_exists() {
    setup_repo
    printf 'A brownfield page nobody told crayon about.\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1
    "$CRAYON" signoff brown-unit >/dev/null 2>&1
    stage_draft brown-unit "reference/brown.rst" "a generated replacement\n"
    local ledger_before page_before
    ledger_before=$(ledger_digest brown-unit)
    page_before=$(sha256_of_file docs/reference/brown.rst)

    "$CRAYON" draft brown-unit "$(draft_path brown-unit reference/brown.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "drafting over an unadopted page exits 1" "1" "$rc"
    assert_json_error "target_exists" "err.txt" "target_exists"
    assert_eq "the refusal routes to record_edits" "record_edits" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next"])' err.txt)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest brown-unit)"
    assert_eq "the existing page is never clobbered" "$page_before" \
        "$(sha256_of_file docs/reference/brown.rst)"
    cleanup
}

test_n34_t26d_a_deleted_target_never_blocks_drafting_and_is_restored() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "the page body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1

    rm docs/reference/demo.rst
    assert_eq "absence is not drift" "false" "$(derived demo-unit page_drift)"
    assert_eq "the page is reported missing" "true" "$(derived demo-unit page_missing)"
    "$CRAYON" steer demo-unit --note "restore the deleted page" >/dev/null 2>&1

    local out rc
    out=$("$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" 2>err.txt)
    rc=$?
    assert_eq "a restoring draft exits 0" "0" "$rc"
    assert_file_exists "the page is restored" "docs/reference/demo.rst"
    assert_eq "the restored page holds the staging bytes" "the page body" \
        "$(cat docs/reference/demo.rst)"
    assert_contains "the restoring draft routes to review" "$out" "Next: review"
    cleanup
}

test_d18_an_actionable_unit_with_no_step_plan_is_steps_missing() {
    setup_repo
    crayon_unit_new howto-unit "how-to/guide.rst" --intent how-to >/dev/null 2>&1
    "$CRAYON" signoff howto-unit >/dev/null 2>&1
    assert_eq "an actionable unit routes to walk" "walk" "$(derived howto-unit next)"
    stage_draft howto-unit "how-to/guide.rst" "step one\n"
    local ledger_before head_before
    ledger_before=$(ledger_digest howto-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft howto-unit "$(draft_path howto-unit how-to/guide.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "drafting an actionable unit with no steps exits 4" "4" "$rc"
    assert_json_error "steps_missing" "err.txt" "steps_missing"
    assert_eq "the refusal routes to walk" "walk" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next"])' err.txt)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest howto-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_file_not_exists "the refusal writes no page" "docs/how-to/guide.rst"
    cleanup
}

test_n31_t23_a_draft_source_outside_the_staging_dir_is_bad_draft_path() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    # T23: write the destination first, then hand it back as the source.
    printf 'smuggled bytes\n' >docs/reference/demo.rst
    local ledger_before head_before page_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)
    page_before=$(sha256_of_file docs/reference/demo.rst)

    "$CRAYON" draft demo-unit "docs/reference/demo.rst" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a source outside the staging draft dir exits 2" "2" "$rc"
    assert_json_error "bad_draft_path" "err.txt" "bad_draft_path"
    assert_eq "stage b beats stage c's target_exists" "$page_before" \
        "$(sha256_of_file docs/reference/demo.rst)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"

    # A sibling of draft/ inside the same staging tree is still outside it.
    mkdir -p .crayon/staging/demo-unit/scratch
    printf 'scratch bytes\n' >.crayon/staging/demo-unit/scratch/demo.rst
    "$CRAYON" draft demo-unit ".crayon/staging/demo-unit/scratch/demo.rst" >/dev/null 2>err2.txt
    assert_eq "a staging sibling of draft/ exits 2" "2" "$?"
    assert_json_error "bad_draft_path (sibling)" "err2.txt" "bad_draft_path"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err3.txt
    assert_eq "a source that does not exist exits 2" "2" "$?"
    assert_json_error "bad_draft_path (absent)" "err3.txt" "bad_draft_path"
    cleanup
}

# CR-02: a DIRECTORY source is walked and each member opened by name, so a
# symlinked member used to draw bytes from anywhere on the filesystem into a
# signed target and commit them, exit 0. This is also the T23/N-31 bypass: the
# link is spelled `draft/<target>` -> `docs/<target>`, which the direct-path
# N-31 test cannot see.
test_n31_t23_a_symlinked_member_of_a_directory_source_is_bad_draft_path() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    printf 'OUTSIDE SECRET\n' >"$outside/outside.rst"
    crayon_unit_new lnk-unit "reference/lnk.rst" >/dev/null 2>&1
    "$CRAYON" signoff lnk-unit >/dev/null 2>&1
    mkdir -p .crayon/staging/lnk-unit/draft/reference
    ln -s "$outside/outside.rst" .crayon/staging/lnk-unit/draft/reference/lnk.rst
    local ledger_before head_before
    ledger_before=$(ledger_digest lnk-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft lnk-unit ".crayon/staging/lnk-unit/draft" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a symlinked draft member exits 2" "2" "$rc"
    assert_json_error "bad_draft_path (symlinked member)" "err.txt" "bad_draft_path"
    assert_file_not_exists "no page is written" "docs/reference/lnk.rst"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest lnk-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"

    # The T23 shape: the link points at the destination inside the docs root.
    rm -f .crayon/staging/lnk-unit/draft/reference/lnk.rst
    printf 'smuggled bytes\n' >docs/reference/lnk.rst
    ln -s "$PWD/docs/reference/lnk.rst" .crayon/staging/lnk-unit/draft/reference/lnk.rst
    "$CRAYON" draft lnk-unit ".crayon/staging/lnk-unit/draft" >/dev/null 2>err2.txt
    assert_eq "a link back to the docs root exits 2" "2" "$?"
    assert_json_error "bad_draft_path (docs-root link)" "err2.txt" "bad_draft_path"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest lnk-unit)"
    rm -rf "$outside"
    cleanup
}

# CR-02: a linked SUBDIRECTORY would smuggle a whole tree in once nested
# targets are used; os.walk never descends into it, so it is refused by name.
test_a_symlinked_draft_subdirectory_is_bad_draft_path() {
    setup_repo
    local outside
    outside=$(mktemp -d)
    mkdir -p "$outside/reference"
    printf 'OUTSIDE\n' >"$outside/reference/dir.rst"
    crayon_unit_new dir-unit "reference/dir.rst" >/dev/null 2>&1
    "$CRAYON" signoff dir-unit >/dev/null 2>&1
    mkdir -p .crayon/staging/dir-unit/draft
    ln -s "$outside/reference" .crayon/staging/dir-unit/draft/reference

    "$CRAYON" draft dir-unit ".crayon/staging/dir-unit/draft" >/dev/null 2>err.txt
    assert_eq "a symlinked draft subdirectory exits 2" "2" "$?"
    assert_json_error "bad_draft_path (symlinked subdir)" "err.txt" "bad_draft_path"
    assert_file_not_exists "no page is written" "docs/reference/dir.rst"
    rm -rf "$outside"
    cleanup
}

test_a_directory_source_must_hold_exactly_the_signed_targets() {
    setup_repo
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/one.rst" "page one\n"
    local ledger_before
    ledger_before=$(ledger_digest multi-unit)

    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>err.txt
    assert_eq "a directory missing a signed target exits 2" "2" "$?"
    assert_json_error "bad_draft_path (missing)" "err.txt" "bad_draft_path"
    assert_file_not_exists "nothing is written" "docs/reference/one.rst"

    stage_draft multi-unit "reference/two.rst" "page two\n"
    stage_draft multi-unit "reference/three.rst" "an unsigned extra\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>err2.txt
    assert_eq "a directory holding an unsigned page exits 2" "2" "$?"
    assert_json_error "bad_draft_path (extra)" "err2.txt" "bad_draft_path"
    assert_file_not_exists "nothing is written" "docs/reference/one.rst"

    assert_eq "no refused draft appends anything" "$ledger_before" "$(ledger_digest multi-unit)"
    cleanup
}

test_a_file_source_cannot_draw_a_multi_target_unit() {
    setup_repo
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/one.rst" "page one\n"

    "$CRAYON" draft multi-unit "$(draft_path multi-unit reference/one.rst)" >/dev/null 2>err.txt
    assert_eq "one file for two signed targets exits 2" "2" "$?"
    assert_json_error "bad_draft_path (file for many)" "err.txt" "bad_draft_path"
    assert_file_not_exists "nothing is written" "docs/reference/one.rst"
    cleanup
}

test_an_empty_staging_file_is_not_a_draft() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" ""

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    assert_eq "a zero-byte draft source exits 2" "2" "$?"
    assert_json_error "bad_draft_path (empty)" "err.txt" "bad_draft_path"
    assert_file_not_exists "nothing is written" "docs/reference/demo.rst"
    cleanup
}

test_draft_records_report_origins_and_gaps() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "body\n"
    mkdir -p .crayon/staging/demo-unit
    cat >.crayon/staging/demo-unit/report.json <<'REPORT'
{"origins": ["workshop/schema.json", "README.md"],
 "gaps": ["the retry budget is undocumented"],
 "gaps_note": "one source could not be reached"}
REPORT

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --report .crayon/staging/demo-unit/report.json >/dev/null 2>err.txt
    assert_eq "a draft with a report exits 0" "0" "$?"
    local gen
    gen=$(ledger_line demo-unit 4)
    assert_contains "the origins are recorded" "$gen" '"origins":["workshop/schema.json","README.md"]'
    assert_contains "the gaps are recorded" "$gen" '"gaps":["the retry budget is undocumented"]'
    assert_eq "the gaps note is recorded" "one source could not be reached" \
        "$(printf '%s' "$gen" | json_field gaps_note)"
    cleanup
}

test_draft_omits_the_optional_generation_fields_when_absent() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1

    local keys
    keys=$(printf '%s' "$(ledger_line demo-unit 4)" | python3 -c '
import json, sys
payload = json.loads(sys.stdin.read())
print(",".join(sorted(k for k in ("unsteered_reason", "steps_seq", "origins", "gaps", "gaps_note") if k in payload)))
')
    assert_eq "no optional field is recorded as a null placeholder" "" "$keys"
    cleanup
}

# --- STATE-05 / STATE-06: the no-op, the steering gate, and their order ------

test_n09_a_second_draft_with_no_steering_is_unsteered() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "first body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "second body, nobody asked for it\n"
    local ledger_before head_before page_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)
    page_before=$(sha256_of_file docs/reference/demo.rst)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a second unsteered draft exits 1" "1" "$rc"
    assert_json_error "unsteered" "err.txt" "unsteered"
    # A model follows the hint in front of it, so the hint leads with the STOP:
    # ask the author first, and only then the verb that records their words.
    assert_eq "the unsteered hint leads with asking the author" \
        "a STOP, not a retry: ask the author what should change" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hint"].split(", then")[0])' err.txt)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the refusal leaves the page byte-unchanged" "$page_before" \
        "$(sha256_of_file docs/reference/demo.rst)"

    "$CRAYON" steer demo-unit --note "rewrite the introduction" >/dev/null 2>&1
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err2.txt
    assert_eq "a recorded steering opens the gate" "0" "$?"
    assert_eq "the steered draft replaces the page" "second body, nobody asked for it" \
        "$(cat docs/reference/demo.rst)"
    cleanup
}

test_n09_unsteered_reason_records_the_override_on_one_generation() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "first body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "second body\n"

    local out rc
    out=$("$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --unsteered-reason "restoring after a lost working copy" 2>err.txt)
    rc=$?
    assert_eq "the override exits 0" "0" "$rc"
    local gen
    gen=$(ledger_line demo-unit 5)
    assert_eq "the second generation is marked unsteered" "True" \
        "$(printf '%s' "$gen" | json_field unsteered)"
    assert_eq "the reason is recorded verbatim" "restoring after a lost working copy" \
        "$(printf '%s' "$gen" | json_field unsteered_reason)"
    assert_contains "the override still routes onward" "$out" "Next: review"

    # The override is not an H event: it enters no steering stream, so a further
    # draft with nothing new recorded is refused again (D5/AC5).
    stage_draft demo-unit "reference/demo.rst" "third body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err2.txt
    assert_eq "the override satisfies no later gate" "1" "$?"
    assert_json_error "unsteered again" "err2.txt" "unsteered"
    assert_eq "the pending stream is untouched by the override" "0" \
        "$(derived demo-unit pending | python3 -c '
import json, sys
print(len(json.loads(sys.stdin.read())))
')"
    cleanup
}

test_a_first_draft_needs_no_steering() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "the very first body\n"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    assert_eq "the gate does not apply before a generation exists" "0" "$?"
    assert_eq "the steering stream is empty" "0" \
        "$(derived demo-unit pending | python3 -c '
import json, sys
print(len(json.loads(sys.stdin.read())))
')"
    assert_file_exists "the page is written" "docs/reference/demo.rst"
    cleanup
}

test_n45_t11_an_identical_retry_is_identical_draft() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "the body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "an identical retry exits 3" "3" "$rc"
    assert_json_error "identical_draft" "err.txt" "identical_draft"
    assert_eq "the no-op payload carries the existing generation's seq" "3" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["seq"])' err.txt)"
    assert_contains "the no-op payload carries its commit" "$(cat err.txt)" '"commit"'
    assert_eq "the no-op payload carries the current next" "review" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["next"])' err.txt)"
    assert_eq "the no-op appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the no-op commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_n39_t11b_t11c_identical_bytes_with_a_missing_destination_is_not_a_no_op() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "the body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1

    # T11b: the bytes are identical, but the destination is gone. Comparison is
    # against the DESTINATION, so this is not a no-op — and defeating the no-op
    # does not waive the steering gate.
    rm docs/reference/demo.rst
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a missing destination is refused 1, not 3" "1" "$rc"
    assert_json_error "unsteered (T11b)" "err.txt" "unsteered"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_file_not_exists "the refusal restores nothing" "docs/reference/demo.rst"

    # T11c: the author records the restoration request, and the same draft lands.
    "$CRAYON" steer demo-unit --note "restore the page I deleted" >/dev/null 2>&1
    local out
    out=$("$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" 2>err2.txt)
    assert_eq "the restoring draft exits 0" "0" "$?"
    assert_file_exists "the page is restored" "docs/reference/demo.rst"
    assert_eq "the restored page holds the staging bytes" "the body" \
        "$(cat docs/reference/demo.rst)"
    assert_eq "the printed token is review" "Next: review" "${out##* · }"
    # 1-2 unit new, 3 signoff, 4 the first generation, 5 the restoration
    # request, 6 the generation that restored the page.
    assert_eq "a second generation is recorded" "generation" \
        "$(printf '%s' "$(ledger_line demo-unit 6)" | json_field kind)"
    cleanup
}

test_n39_t24d_a_brownfield_basis_with_no_generation_is_never_a_no_op() {
    setup_repo
    printf 'the adopted page\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1
    "$CRAYON" signoff brown-unit >/dev/null 2>&1
    append_event brown-unit reviewer-edit
    assert_eq "the basis is an edit with no generation" "null" \
        "$(derived brown-unit gen_seq)"

    # The staging bytes equal the adopted page exactly — and it is still not a
    # no-op, because no generation exists to be identical to.
    stage_draft brown-unit "reference/brown.rst" "the adopted page\n"
    local lines_before
    lines_before=$(wc -l <".crayon/units/brown-unit/ledger.jsonl" | tr -d ' ')

    "$CRAYON" draft brown-unit "$(draft_path brown-unit reference/brown.rst)" >/dev/null 2>err.txt
    assert_eq "the first draft over a brownfield basis exits 0" "0" "$?"
    assert_eq "a generation is appended" "generation" \
        "$(printf '%s' "$(ledger_line brown-unit $((lines_before + 1)))" | json_field kind)"
    assert_eq "the page is unchanged in content" "the adopted page" \
        "$(cat docs/reference/brown.rst)"
    cleanup
}

test_n11_t6_the_no_op_is_recognised_before_the_steering_gate() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "first body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1

    # The author edits the page by hand and the edit is recorded, so the basis
    # is the edit. No H event has happened since the generation.
    printf 'hand-edited body\n' >docs/reference/demo.rst
    append_event demo-unit reviewer-edit
    assert_eq "the basis is the reviewer edit" "false" "$(derived demo-unit page_drift)"
    assert_eq "nothing has steered since the generation" "false" \
        "$(derived demo-unit steered_since_gen)"

    # Staging now equals the edited destination: stage d (no-op) precedes
    # stage e (the steering gate), so the outcome is 3, never 1.
    stage_draft demo-unit "reference/demo.rst" "hand-edited body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "stage d wins over stage e: exit 3" "3" "$rc"
    assert_json_error "identical_draft (T6)" "err.txt" "identical_draft"

    # And with staging that DIFFERS from the edited destination, stage e owns it.
    stage_draft demo-unit "reference/demo.rst" "a third body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err2.txt
    assert_eq "differing staging falls through to stage e" "1" "$?"
    assert_json_error "unsteered (T6)" "err2.txt" "unsteered"
    cleanup
}

# --- VERB-05: edits — the complete basis set and brownfield adoption ---------


test_n26_t24_edits_adopts_a_brownfield_page() {
    setup_repo
    printf 'A page that predates crayon.\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1
    "$CRAYON" signoff brown-unit >/dev/null 2>&1
    assert_eq "an unadopted page routes to record_edits" "record_edits" \
        "$(derived brown-unit next)"
    local before page_before
    before=$(git rev-list --count HEAD)
    page_before=$(sha256_of_file docs/reference/brown.rst)

    local out rc
    out=$("$CRAYON" edits brown-unit --note "adopted existing page" 2>err.txt)
    rc=$?
    assert_eq "edits exits 0" "0" "$rc"
    assert_eq "edits prints exactly one stdout line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_eq "the adopted unit routes to draft" "Next: draft" "${out##* · }"

    assert_eq "edits appends exactly one ledger line" "4" \
        "$(wc -l <".crayon/units/brown-unit/ledger.jsonl" | tr -d ' ')"
    local edit
    edit=$(ledger_line brown-unit 4)
    assert_eq "the appended event is a reviewer-edit" "reviewer-edit" \
        "$(printf '%s' "$edit" | json_field kind)"
    assert_eq "files[] is the adopted page with its disk digest" \
        "reference/brown.rst $page_before" "$(printf '%s' "$edit" | edit_files)"
    assert_eq "generation_seq is null when no generation exists" "null" \
        "$(printf '%s' "$edit" | json_field generation_seq)"
    assert_eq "the note is recorded verbatim" "adopted existing page" \
        "$(printf '%s' "$edit" | json_field note)"

    assert_eq "edits makes exactly one commit" "$((before + 1))" "$(git rev-list --count HEAD)"
    assert_eq "edits never writes a page" "$page_before" \
        "$(sha256_of_file docs/reference/brown.rst)"
    assert_eq "the commit carries the ledger and nothing else" \
        ".crayon/units/brown-unit/ledger.jsonl" "$(git show --name-only --format= HEAD)"
    assert_eq "the derived basis is the edit" "3" "$(derived brown-unit basis_seq)"
    assert_eq "the unit is still signed-off, not drafted" "signed-off" \
        "$(derived brown-unit state)"
    cleanup
}

test_n26_t24b_adoption_lists_only_the_existing_page_then_draft_writes_both() {
    setup_repo
    printf 'the existing page\n' >docs/reference/one.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1

    "$CRAYON" edits multi-unit --note "adopted the one page that exists" >/dev/null 2>err.txt
    assert_eq "the partial adoption exits 0" "0" "$?"
    assert_eq "only the existing page is adopted" "reference/one.rst" \
        "$(printf '%s' "$(ledger_line multi-unit 4)" | event_paths)"
    assert_file_not_exists "the new target is not conjured into existence" \
        "docs/reference/two.rst"

    stage_draft multi-unit "reference/one.rst" "the existing page\n"
    stage_draft multi-unit "reference/two.rst" "the brand new page\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>err2.txt
    assert_eq "the first draft over a partial adoption exits 0" "0" "$?"
    assert_eq "the generation lists both targets" "reference/one.rst reference/two.rst" \
        "$(printf '%s' "$(ledger_line multi-unit 5)" | event_paths)"
    assert_file_exists "the new page is written" "docs/reference/two.rst"
    cleanup
}

test_n26_t24c_a_second_edits_before_the_first_draft_is_no_edits() {
    setup_repo
    printf 'the existing page\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1
    "$CRAYON" signoff brown-unit >/dev/null 2>&1
    "$CRAYON" edits brown-unit --note "adopted" >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest brown-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" edits brown-unit --note "nothing changed since" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "a second edits with nothing changed exits 3" "3" "$rc"
    assert_json_error "no_edits" "err.txt" "no_edits"
    assert_eq "the no-op appends nothing" "$ledger_before" "$(ledger_digest brown-unit)"
    assert_eq "the no-op commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_n11_t7_edits_records_the_complete_basis_set_never_a_delta() {
    setup_repo
    crayon_unit_new multi-unit "reference/one.rst" --also-target "reference/two.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/one.rst" "page one\n"
    stage_draft multi-unit "reference/two.rst" "page two\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>&1
    local untouched
    untouched=$(sha256_of_file docs/reference/two.rst)

    printf 'page one, edited by the author\n' >docs/reference/one.rst
    "$CRAYON" edits multi-unit --note "tightened the intro by hand" >/dev/null 2>err.txt
    assert_eq "edits over a drifted page exits 0" "0" "$?"
    local edit
    edit=$(ledger_line multi-unit 5)
    assert_eq "files[] carries BOTH paths, not just the changed one" \
        "reference/one.rst $(sha256_of_file docs/reference/one.rst)
reference/two.rst $untouched" "$(printf '%s' "$edit" | edit_files)"
    assert_eq "generation_seq names the last generation" "3" \
        "$(printf '%s' "$edit" | json_field generation_seq)"
    assert_eq "the untouched page is never rewritten" "$untouched" \
        "$(sha256_of_file docs/reference/two.rst)"
    assert_eq "the basis is now the edit" "4" "$(derived multi-unit basis_seq)"
    assert_eq "the drift is resolved" "false" "$(derived multi-unit page_drift)"

    # T7's tail: a recorded steering opens the gate and the draft lands.
    "$CRAYON" steer multi-unit --note "restore the intro I cut" >/dev/null 2>&1
    stage_draft multi-unit "reference/one.rst" "page one, redrafted\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>err2.txt
    assert_eq "the draft after edits + steer exits 0" "0" "$?"
    assert_eq "the redraft replaces the page" "page one, redrafted" \
        "$(cat docs/reference/one.rst)"
    cleanup
}

test_n34_t26e_deleting_a_current_target_is_never_an_edit() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "the body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1
    local recorded
    recorded=$(sha256_of_file docs/reference/demo.rst)

    rm docs/reference/demo.rst
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)
    "$CRAYON" edits demo-unit --note "the page is gone" >/dev/null 2>err.txt
    assert_eq "absence alone is not an edit: exit 3" "3" "$?"
    assert_json_error "no_edits (T26e)" "err.txt" "no_edits"
    assert_eq "the no-op appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the basis still carries the last recorded digest" \
        "reference/demo.rst $recorded $(printf '%s' "$(ledger_line demo-unit 4)" | python3 -c '
import json, sys
print(json.loads(sys.stdin.read())["files"][0]["bytes"])
')" "$(printf '%s' "$(ledger_line demo-unit 4)" | event_files)"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err2.txt
    assert_eq "the first draft after the deletion exits 1" "1" "$?"
    assert_json_error "unsteered (T26e)" "err2.txt" "unsteered"

    "$CRAYON" steer demo-unit --note "restore it" >/dev/null 2>&1
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>err3.txt
    assert_eq "the steered draft exits 0" "0" "$?"
    assert_file_exists "the page is restored" "docs/reference/demo.rst"
    cleanup
}

test_n34_t26b_a_hand_rename_drops_the_old_path_and_adopts_the_new() {
    setup_repo
    crayon_unit_new demo-unit "reference/old.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/old.rst" "the body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/old.rst)" >/dev/null 2>&1
    local body
    body=$(sha256_of_file docs/reference/old.rst)

    "$CRAYON" unit edit demo-unit --target "reference/new.rst" --re-sign >/dev/null 2>&1
    git mv docs/reference/old.rst docs/reference/new.rst
    git commit -q -m "author renamed the page"
    assert_eq "a moved page is not drift" "false" "$(derived demo-unit page_drift)"
    assert_eq "the new path is an unadopted target" "record_edits" "$(derived demo-unit next)"

    "$CRAYON" edits demo-unit --note "renamed the page by hand" >/dev/null 2>err.txt
    assert_eq "edits after a rename exits 0" "0" "$?"
    local edit
    edit=$(ledger_line demo-unit 7)
    assert_eq "the new path is adopted and the old one dropped" \
        "reference/new.rst $body" "$(printf '%s' "$edit" | edit_files)"
    assert_file_not_exists "the author's rename is respected" "docs/reference/old.rst"
    assert_file_exists "the new page is untouched on disk" "docs/reference/new.rst"
    cleanup
}

test_n33_t26_a_re_signed_target_change_reports_the_orphan_and_keeps_it() {
    setup_repo
    crayon_unit_new demo-unit "reference/old.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/old.rst" "the body\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/old.rst)" >/dev/null 2>&1
    local orphan_before
    orphan_before=$(sha256_of_file docs/reference/old.rst)

    # T26: nobody edits the old page; the plan simply names a different target.
    "$CRAYON" unit edit demo-unit --target "reference/new.rst" --re-sign >/dev/null 2>&1
    assert_eq "an untouched old page is not drift" "false" "$(derived demo-unit page_drift)"
    assert_eq "the unwritten new target does not exist yet" "false" \
        "$(derived demo-unit target_exists)"
    stage_draft demo-unit "reference/new.rst" "the body\n"

    local out
    out=$("$CRAYON" draft demo-unit "$(draft_path demo-unit reference/new.rst)" 2>err.txt)
    assert_eq "drafting the renamed target exits 0" "0" "$?"
    assert_file_exists "the new page is written" "docs/reference/new.rst"
    assert_eq "the orphan is kept on disk, byte for byte" "$orphan_before" \
        "$(sha256_of_file docs/reference/old.rst)"
    assert_contains "the draft response names the orphan" "$out" \
        "no longer a target; kept on disk"
    assert_eq "it is named exactly once" "1" \
        "$(printf '%s\n' "$out" | grep -o 'reference/old.rst' | wc -l | tr -d ' ')"
    # 1-2 unit new, 3 signoff, 4 the first generation, 5-6 the re-sign batch,
    # 7 the generation that wrote the renamed target.
    assert_eq "the generation's files[] is exactly the NEW target set" \
        "reference/new.rst" "$(printf '%s' "$(ledger_line demo-unit 7)" | event_paths)"
    assert_eq "the orphan is gone from the basis" "[]" "$(derived demo-unit orphans)"
    cleanup
}

test_edits_files_follow_the_signed_target_order() {
    setup_repo
    crayon_unit_new multi-unit "reference/b.rst" --also-target "reference/a.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/b.rst" "page b\n"
    stage_draft multi-unit "reference/a.rst" "page a\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>&1

    printf 'page a, edited\n' >docs/reference/a.rst
    "$CRAYON" edits multi-unit --note "edited a" >/dev/null 2>&1
    assert_eq "files[] follows the signoff's target order, not the alphabet" \
        "reference/b.rst reference/a.rst" \
        "$(printf '%s' "$(ledger_line multi-unit 5)" | event_paths)"
    cleanup
}

test_edits_before_any_signoff_is_no_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" edits demo-unit --note "too early" >/dev/null 2>err.txt
    local rc=$?
    assert_eq "edits before a signoff exits 1" "1" "$rc"
    assert_json_error "no_signoff on edits" "err.txt" "no_signoff"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_edits_on_a_retired_unit_is_refused() {
    setup_repo
    printf 'the existing page\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1
    "$CRAYON" signoff brown-unit >/dev/null 2>&1
    append_event brown-unit retired
    local ledger_before
    ledger_before=$(ledger_digest brown-unit)

    "$CRAYON" edits brown-unit --note "too late" >/dev/null 2>err.txt
    assert_eq "edits on a retired unit exits 1" "1" "$?"
    assert_json_error "retired on edits" "err.txt" "retired"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest brown-unit)"
    cleanup
}

test_edits_refuses_an_empty_note_and_reads_one_from_stdin() {
    setup_repo
    printf 'the existing page\n' >docs/reference/brown.rst
    git add -A && git commit -q -m "pre-existing page"
    crayon_unit_new brown-unit "reference/brown.rst" >/dev/null 2>&1
    "$CRAYON" signoff brown-unit >/dev/null 2>&1

    "$CRAYON" edits brown-unit --note "   " >/dev/null 2>err.txt
    assert_eq "a whitespace-only note exits 2" "2" "$?"
    assert_json_error "note_required on edits" "err.txt" "note_required"

    printf 'a note that arrived on stdin' | "$CRAYON" edits brown-unit --note-file - \
        >/dev/null 2>err2.txt
    assert_eq "--note-file - exits 0" "0" "$?"
    assert_eq "the stdin note is recorded identically" "a note that arrived on stdin" \
        "$(printf '%s' "$(ledger_line brown-unit 4)" | json_field note)"
    cleanup
}

# --- GATE-07 / VERB-04: review — verdicts and recorded dispositions ----------


test_j5_review_accept_seals_the_unit_end_to_end() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    local before lines_before
    before=$(git rev-list --count HEAD)
    lines_before=$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')

    local out rc
    out=$("$CRAYON" review demo-unit --verdict accept --note "looks good" 2>err.txt)
    rc=$?
    assert_eq "accept exits 0" "0" "$rc"
    assert_eq "accept prints exactly one stdout line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    # D-03 / CLOSE-04: the accepted pages, then the plain handover; no count,
    # no "sealed" and no resolved/withdrawn counts segment.
    assert_eq "the accept response hands over plainly" \
        "reviewed demo-unit: accept · accepted reference/demo.rst · Next: yours — crayon stops here" \
        "$out"
    assert_eq "accept appends exactly one event" "$((lines_before + 1))" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    assert_eq "accept makes exactly one commit" "$((before + 1))" \
        "$(git rev-list --count HEAD)"

    local event
    event=$(ledger_line demo-unit 5)
    assert_eq "the event kind is review" "review" "$(printf '%s' "$event" | json_field kind)"
    assert_eq "the verdict is recorded" "accept" \
        "$(printf '%s' "$event" | json_field verdict)"
    assert_eq "the generation is cited" "3" \
        "$(printf '%s' "$event" | json_field generation_seq)"
    assert_eq "the basis is cited" "3" \
        "$(printf '%s' "$event" | json_field basis_seq)"
    assert_eq "accept files[] equals the basis" "reference/demo.rst" \
        "$(printf '%s' "$event" | event_paths)"
    assert_eq "nothing was resolved" "[]" "$(printf '%s' "$event" | json_field resolves)"
    assert_eq "nothing was withdrawn" "[]" "$(printf '%s' "$event" | json_field withdraws)"

    assert_eq "the fifth trailer carries the verdict" "accept" \
        "$(git log -1 --format='%(trailers:key=Crayon-Verdict,valueonly)' | tr -d '\n')"
    assert_eq "the four trailers are still there" "demo-unit" \
        "$(git log -1 --format='%(trailers:key=Crayon-Unit,valueonly)' | tr -d '\n')"
    assert_eq "the commit subject names the phase" "crayon: reviewed demo-unit" \
        "$(git log -1 --format=%s)"

    assert_eq "the unit is sealed" "sealed" "$(derived demo-unit state)"
    assert_eq "a sealed unit routes to publish" "publish" "$(derived demo-unit next)"

    # D-16: the author reads `accepted`; the JSON state stays `sealed`.
    local shown
    shown=$("$CRAYON" show demo-unit 2>show-err.txt)
    assert_contains "human show says the unit is accepted" "$shown" "state: accepted"
    assert_not_contains "human show never says sealed" "$shown" "sealed"
    assert_plain "show on an accepted unit speaks plainly" "$shown"
    assert_eq "show --json keeps the sealed state" "sealed" \
        "$("$CRAYON" show demo-unit --json 2>/dev/null | json_field state)"
    cleanup
}

test_review_fix_and_redraft_record_the_verdict_and_route_to_draft() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    local out
    out=$("$CRAYON" review demo-unit --verdict fix --note "tighten the intro" 2>err.txt)
    assert_eq "fix exits 0" "0" "$?"
    assert_contains "fix routes to draft" "$out" "Next: draft"
    local event
    event=$(ledger_line demo-unit 5)
    assert_eq "the verdict is fix" "fix" "$(printf '%s' "$event" | json_field verdict)"
    assert_eq "a fix cites the generation" "3" \
        "$(printf '%s' "$event" | json_field generation_seq)"
    assert_eq "a fix records no basis" "null" \
        "$(printf '%s' "$event" | json_field basis_seq)"
    assert_eq "the trailer carries the verdict" "fix" \
        "$(git log -1 --format='%(trailers:key=Crayon-Verdict,valueonly)' | tr -d '\n')"
    assert_eq "a fix is a pending request" "[4]" "$(derived demo-unit pending)"
    assert_eq "the state is reviewed, never sealed" "reviewed" "$(derived demo-unit state)"

    "$CRAYON" review demo-unit --verdict redraft --note "start over" >/dev/null 2>&1
    assert_eq "redraft exits 0" "0" "$?"
    assert_eq "the verdict is redraft" "redraft" \
        "$(printf '%s' "$(ledger_line demo-unit 6)" | json_field verdict)"
    assert_eq "both requests are pending" "[4, 5]" "$(derived demo-unit pending)"
    cleanup
}

test_n20_t1_an_undisposed_fix_request_blocks_the_accept() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    # T1: an UNRELATED edit lands after the request; the request is untouched.
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    "$CRAYON" edits demo-unit --note "unrelated wording fix" >/dev/null 2>&1

    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err.txt
    assert_eq "an accept over a pending request exits 1" "1" "$?"
    assert_json_error "unapplied_steering on accept" "err.txt" "unapplied_steering"
    assert_contains "the detail lists the undisposed seq" "$(cat err.txt)" "disposition: 4"
    # The hint leads with the act its routing row prescribes, before the flags.
    assert_eq "the unapplied_steering hint leads with asking the reviewer" \
        "put each pending seq to the reviewer" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["hint"].split(", then")[0])' err.txt)"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"

    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        >/dev/null 2>err2.txt
    assert_eq "disposing the request seals the unit" "0" "$?"
    assert_eq "the unit is sealed" "sealed" "$(derived demo-unit state)"
    assert_eq "the disposition is recorded" "[4]" \
        "$(printf '%s' "$(ledger_line demo-unit 7)" | json_field resolves)"
    cleanup
}

test_n21_t2_two_requests_with_only_one_resolved_still_refuses() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "first request" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict fix --note "second request" >/dev/null 2>&1
    assert_eq "both are pending" "[4, 5]" "$(derived demo-unit pending)"

    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        >/dev/null 2>err.txt
    assert_eq "one disposition short exits 1" "1" "$?"
    assert_json_error "unapplied_steering with one left" "err.txt" "unapplied_steering"
    assert_contains "the detail names the unresolved seq only" "$(cat err.txt)" \
        "disposition: 5"

    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        --withdraw 5 "out of scope for this page" >/dev/null 2>err2.txt
    assert_eq "resolving one and withdrawing the other seals" "0" "$?"
    # 1-4 the drafted unit, 5-6 the two fix requests, 7 the accept that seals.
    local event
    event=$(ledger_line demo-unit 7)
    assert_eq "the withdrawal carries its reason" "out of scope for this page" \
        "$(printf '%s' "$event" | python3 -c '
import json, sys
print(json.loads(sys.stdin.read())["withdraws"][0]["reason"])
')"
    cleanup
}

test_n43_t3_a_request_before_the_newer_generation_is_not_pending() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" steer demo-unit --note "add an example" >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "Demo\n====\n\nWith an example.\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" >/dev/null 2>&1
    assert_eq "pending counts from the newer generation" "[]" "$(derived demo-unit pending)"

    "$CRAYON" review demo-unit --verdict accept --note "good" >/dev/null 2>err.txt
    assert_eq "T3 accepts cleanly" "0" "$?"
    assert_eq "the unit is sealed" "sealed" "$(derived demo-unit state)"
    cleanup
}

test_n22_t4_a_steer_after_a_seal_unseals_and_blocks_the_retry() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1
    assert_eq "the unit seals" "sealed" "$(derived demo-unit state)"

    "$CRAYON" steer demo-unit --note "one more thing" >/dev/null 2>&1
    assert_eq "a steer after a seal reads as reviewed, never sealed" "reviewed" \
        "$(derived demo-unit state)"
    assert_eq "the request is pending" "[5]" "$(derived demo-unit pending)"

    "$CRAYON" review demo-unit --verdict accept --note "still good" >/dev/null 2>err.txt
    assert_eq "the retry exits 1" "1" "$?"
    assert_json_error "unapplied_steering after a seal" "err.txt" "unapplied_steering"
    cleanup
}

test_n23_t10_an_accept_retry_after_a_steer_is_not_already_accepted() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1

    # No change at all: the retry is the accept no-op.
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err.txt
    assert_eq "an unchanged retry exits 3" "3" "$?"
    assert_json_error "already_accepted" "err.txt" "already_accepted"
    assert_eq "the no-op payload names the existing event" "4" \
        "$(python3 -c '
import json, sys
print(json.loads(open("err.txt", encoding="utf-8").read())["seq"])
')"

    # T10: a later steer turns the same retry into a refusal, not a no-op.
    "$CRAYON" steer demo-unit --note "one more thing" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err2.txt
    assert_eq "the retry after a steer exits 1" "1" "$?"
    assert_json_error "unapplied_steering, not already_accepted" "err2.txt" \
        "unapplied_steering"
    cleanup
}

test_n32_t30_dispositions_must_be_disjoint_and_drawn_from_pending() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" review demo-unit --verdict accept --note "ok" --resolves 4 \
        --withdraw 4 "changed my mind" >/dev/null 2>err.txt
    assert_eq "resolving and withdrawing one seq exits 2" "2" "$?"
    assert_json_error "bad_resolution on an overlap" "err.txt" "bad_resolution"

    "$CRAYON" review demo-unit --verdict accept --note "ok" --withdraw 4 "" \
        >/dev/null 2>err2.txt
    assert_eq "an empty withdrawal reason exits 2" "2" "$?"
    assert_json_error "bad_resolution on an empty reason" "err2.txt" "bad_resolution"

    "$CRAYON" review demo-unit --verdict accept --note "ok" --resolves 99 \
        >/dev/null 2>err3.txt
    assert_eq "a seq outside pending exits 2" "2" "$?"
    assert_json_error "bad_resolution on an unknown seq" "err3.txt" "bad_resolution"

    "$CRAYON" review demo-unit --verdict accept --note "ok" --resolves 4,4 \
        >/dev/null 2>err4.txt
    assert_eq "a duplicated seq exits 2" "2" "$?"
    assert_json_error "bad_resolution on a duplicate" "err4.txt" "bad_resolution"

    "$CRAYON" review demo-unit --verdict accept --note "ok" --resolves four \
        >/dev/null 2>err5.txt
    assert_eq "a non-integer seq exits 2" "2" "$?"
    assert_json_error "bad_resolution on a non-integer" "err5.txt" "bad_resolution"

    "$CRAYON" review demo-unit --verdict fix --note "another" --resolves 4 \
        >/dev/null 2>err6.txt
    assert_eq "dispositions on a fix exit 2" "2" "$?"
    assert_json_error "bad_resolution on a non-accept verdict" "err6.txt" "bad_resolution"

    assert_eq "every bad_resolution appends nothing" "$ledger_before" \
        "$(ledger_digest demo-unit)"
    assert_eq "every bad_resolution commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_n19_t8_t9b_a_re_signed_plan_can_never_accept_the_old_generation() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" unit edit demo-unit --audience "A different audience" --re-sign \
        >/dev/null 2>&1
    assert_eq "the old generation is stale" "true" "$(derived demo-unit generation_stale)"
    assert_eq "a stale generation routes to draft" "draft" "$(derived demo-unit next)"

    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err.txt
    assert_eq "accepting a stale generation exits 1" "1" "$?"
    assert_json_error "generation_stale on accept" "err.txt" "generation_stale"
    assert_eq "the refusal routes to draft" "draft" "$(refusal_next err.txt)"

    # T9b: the stale gate is read BEFORE drift, and `edits` does not clear it.
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    assert_eq "the page is drifted" "true" "$(derived demo-unit page_drift)"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err2.txt
    assert_json_error "generation_stale beats page_drift" "err2.txt" "generation_stale"

    "$CRAYON" edits demo-unit --note "hand edit" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err3.txt
    assert_eq "it is still stale after edits" "1" "$?"
    assert_json_error "generation_stale survives edits" "err3.txt" "generation_stale"
    cleanup
}

test_n34_t26c_deleting_a_current_target_is_target_missing_not_page_drift() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    rm docs/reference/demo.rst
    assert_eq "absence is never drift" "false" "$(derived demo-unit page_drift)"

    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>err.txt
    assert_eq "accepting a deleted target exits 1" "1" "$?"
    assert_json_error "target_missing, not page_drift" "err.txt" "target_missing"
    cleanup
}

test_routing_8b_a_missing_target_after_a_seal_routes_to_steer() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1
    rm docs/reference/demo.rst
    assert_eq "a sealed unit with a missing target routes to steer" "steer" \
        "$(derived demo-unit next)"

    "$CRAYON" review demo-unit --verdict accept --note "again" >/dev/null 2>err.txt
    assert_eq "the retry exits 1" "1" "$?"
    assert_json_error "target_missing beats already_accepted" "err.txt" "target_missing"
    assert_eq "the refusal routes to steer" "steer" "$(refusal_next err.txt)"
    cleanup
}

test_review_fix_and_redraft_require_a_note() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" review demo-unit --verdict fix >/dev/null 2>err.txt
    assert_eq "fix with no note exits 2" "2" "$?"
    assert_json_error "note_required on fix" "err.txt" "note_required"

    "$CRAYON" review demo-unit --verdict redraft >/dev/null 2>err2.txt
    assert_eq "redraft with no note exits 2" "2" "$?"
    assert_json_error "note_required on redraft" "err2.txt" "note_required"

    assert_eq "neither refusal appends anything" "$ledger_before" \
        "$(ledger_digest demo-unit)"
    cleanup
}

test_review_before_any_generation_is_no_generation() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" review demo-unit --verdict accept --note "nothing to see" >/dev/null 2>err.txt
    assert_eq "reviewing before a generation exits 1" "1" "$?"
    assert_json_error "no_generation" "err.txt" "no_generation"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

test_review_on_a_unit_with_no_signoff_is_no_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "too early" >/dev/null 2>err.txt
    assert_eq "review before a signoff exits 1" "1" "$?"
    assert_json_error "no_signoff on review" "err.txt" "no_signoff"
    cleanup
}

test_review_on_a_retired_unit_is_refused() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    append_event demo-unit retired
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" review demo-unit --verdict accept --note "too late" >/dev/null 2>err.txt
    assert_eq "review on a retired unit exits 1" "1" "$?"
    assert_json_error "retired on review" "err.txt" "retired"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    cleanup
}

# --- VERB-02: show — the state the author and every skill act on -------------

# Everything a read-only verb must leave untouched, in one digest: the ledger,
# every page under docs/, every byte under the unit's pending/ tree, and the
# git index (contract 5.8's write boundary).
readonly_fingerprint() {
    python3 - "$1" <<'PY'
import hashlib, os, subprocess, sys

unit = sys.argv[1]
digest = hashlib.sha256()


def feed(text):
    digest.update(text.encode("utf-8") + b"\0")


def of(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return "absent"


feed(of(os.path.join(".crayon", "units", unit, "ledger.jsonl")))
for root in ("docs", os.path.join(".crayon", "staging", unit, "pending")):
    for where, dirs, names in os.walk(root):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(where, name)
            feed(path)
            feed(of(path))
feed(subprocess.run(
    ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True
).stdout)
print(digest.hexdigest())
PY
}

last_line() {
    printf '%s\n' "$1" | tail -1
}

test_show_on_a_drafted_unit_reports_the_basis_and_routes_to_review() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    local out rc
    out=$("$CRAYON" show demo-unit 2>err.txt)
    rc=$?
    assert_eq "show exits 0" "0" "$rc"
    assert_contains "show prints the title" "$out" "Demo"
    assert_contains "show prints the intent" "$out" "intent: reference"
    assert_contains "show prints the state" "$out" "state: drafted"
    assert_contains "the basis path is current" "$out" "reference/demo.rst — current"
    assert_eq "the last line is the routed token" "Next: review" "$(last_line "$out")"
    assert_plain "show on a drafted unit speaks plainly" "$out"
    cleanup
}

test_show_qualifies_a_state_that_would_mislead() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1
    "$CRAYON" unit edit demo-unit --audience "A different audience" --re-sign \
        >/dev/null 2>&1

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_eq "show exits 0 on an amended seal" "0" "$?"
    # P-19: the accept is named by the commit its Crayon-Seq trailer is on, never
    # by its seq and never by the event's parent commit.
    local accept_sha shown_sha state_line
    accept_sha=$(git log --format='%H %(trailers:key=Crayon-Verdict,valueonly)' \
        | sed -n 's/^\([0-9a-f]*\) accept$/\1/p' | head -1 | cut -c1-7)
    shown_sha=$(printf '%s\n' "$out" | sed -n 's/.*accepted in \([0-9a-f]*\).*/\1/p')
    assert_eq "the qualifier names the accept by a 7-character sha" "7" "${#shown_sha}"
    assert_eq "it is the accept's own commit" "$accept_sha" "$shown_sha"
    assert_contains "the qualifier names the amendment" "$out" "plan amended since the draft"
    assert_not_contains "an amended unit never reads as sealed" "$out" "state: sealed"
    assert_not_contains "an amended unit never reads as accepted" "$out" "state: accepted"
    state_line=$(printf '%s\n' "$out" | grep '^state:')
    assert_not_contains "the state line names no seq" "$state_line" "seq"
    assert_plain "show on an amended unit speaks plainly" "$out"
    assert_eq "an amended seal routes to draft" "Next: draft" "$(last_line "$out")"
    # SC3: the JSON qualifier keeps its seqs.
    assert_contains "show --json's qualifier is unchanged" \
        "$("$CRAYON" show demo-unit --json 2>/dev/null | json_field qualifier)" \
        "accepted at seq 4"

    # The other misleading state: a drafted unit with requests waiting.
    setup_drafted_unit two-unit "reference/two.rst"
    "$CRAYON" steer two-unit --note "first" >/dev/null 2>&1
    "$CRAYON" steer two-unit --note "second" >/dev/null 2>&1
    local pending_out
    pending_out=$("$CRAYON" show two-unit 2>err2.txt)
    assert_contains "the pending count qualifies drafted" "$pending_out" \
        "state: drafted — 2 requests pending"
    cleanup
}

test_show_distinguishes_uncommitted_from_committed_drift() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_contains "an uncommitted hand edit is uncommitted drift" "$out" \
        "reference/demo.rst — drifted (uncommitted)"

    git add docs/reference/demo.rst
    git commit -q -m "the author committed the edit outside crayon"
    local committed
    committed=$("$CRAYON" show demo-unit 2>err2.txt)
    assert_contains "a committed edit names the commit" "$committed" \
        "drifted (committed in "
    local sha
    sha=$(printf '%s\n' "$committed" | sed -n 's/.*drifted (committed in \([0-9a-f]*\)).*/\1/p')
    assert_eq "the commit is named by a 7-character sha" "7" "${#sha}"
    assert_eq "it is the commit that changed the page" "$(git rev-parse --short=7 HEAD)" "$sha"
    cleanup
}

test_show_reports_a_deleted_target_as_missing_not_drifted() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    rm docs/reference/demo.rst

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_contains "an absent page is missing" "$out" "reference/demo.rst — missing"
    assert_not_contains "missing and drifted never merge" "$out" "drifted"
    cleanup
}

test_show_reports_a_dropped_target_as_no_longer_a_target() {
    setup_repo
    setup_drafted_unit demo-unit "reference/old.rst"
    "$CRAYON" unit edit demo-unit --target "reference/new.rst" --re-sign >/dev/null 2>&1

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_contains "the dropped path is named as an orphan" "$out" \
        "reference/old.rst — no longer a target (file kept)"
    assert_file_exists "the orphan is kept on disk" "docs/reference/old.rst"
    assert_contains "the new signed target is new" "$out" "reference/new.rst — new"
    cleanup
}

test_show_rows_follow_the_signed_order_and_name_each_path_once() {
    setup_repo
    crayon_unit_new multi-unit "reference/b.rst" --also-target "reference/a.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/b.rst" "page b\n"
    stage_draft multi-unit "reference/a.rst" "page a\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>&1
    "$CRAYON" unit edit multi-unit --also-target "reference/c.rst" --re-sign \
        >/dev/null 2>&1

    local out rows
    out=$("$CRAYON" show multi-unit 2>err.txt)
    rows=$(printf '%s\n' "$out" | sed -n 's/^  \(reference\/[a-z]*\.rst\) —.*/\1/p' | tr '\n' ' ')
    assert_eq "rows follow the signoff's target order, not the alphabet" \
        "reference/b.rst reference/a.rst reference/c.rst " "$rows"
    assert_eq "a path that is target and basis appears exactly once" "1" \
        "$(printf '%s\n' "$out" | grep -c 'reference/b.rst — ')"
    cleanup
}

test_show_omits_empty_sections_but_always_prints_next() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_eq "show exits 0 with no basis" "0" "$?"
    assert_not_contains "a unit with no basis prints no per-path section" "$out" "paths:"
    assert_not_contains "a unit with no requests prints no request section" "$out" \
        "requests:"
    assert_eq "Next: is printed in every case" "Next: draft" "$(last_line "$out")"
    cleanup
}

test_show_lists_requests_with_their_dispositions() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "mention the flag" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        --withdraw 5 "out of scope for this page" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "one more thing" >/dev/null 2>&1

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_contains "a disposed request reads resolved" "$out" "request 4 — resolved"
    assert_contains "a withdrawn request carries its reason" "$out" \
        "request 5 — withdrawn: out of scope for this page"
    assert_contains "an undisposed request reads pending" "$out" "request 7 — pending"
    local order
    order=$(printf '%s\n' "$out" | sed -n 's/^  request \([0-9]*\) —.*/\1/p' | tr '\n' ' ')
    assert_eq "requests are listed in ascending order" "4 5 7 " "$order"
    assert_plain "show's request rows speak plainly" "$out"
    cleanup
}

# D-16: a reviewer edit is listed by its note alone; the seq it sits at stays
# in show --json's `reviewer_edits`.
test_show_lists_reviewer_edits_by_their_note() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    "$CRAYON" edits demo-unit --note "the hand edit" >/dev/null 2>&1

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_contains "the edit is listed" "$out" "reviewer edits:"
    assert_contains "the edit row is its note" "$out" "  - the hand edit"
    assert_not_contains "the edit row names no seq" "$out" "edit at seq"
    assert_plain "show's edit rows speak plainly" "$out"
    assert_eq "show --json keeps the edit's seq" "4" \
        "$("$CRAYON" show demo-unit --json 2>/dev/null | python3 -c '
import json, sys
print(json.load(sys.stdin)["reviewer_edits"][0]["seq"])')"
    cleanup
}

# SURF-02 (D-10, D-11): `show --json` and `summary --json` carry the same
# `handover`. The fix at seq 4 was accepted with no page change since, so it is
# judged; the steer at seq 5 was withdrawn with its reason.
test_show_and_summary_json_carry_the_handover() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "mention the flag" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        --withdraw 5 "out of scope for this page" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "one more thing" >/dev/null 2>&1

    "$CRAYON" show demo-unit --json >show.json 2>err.txt
    assert_eq "show --json exits 0" "0" "$?"
    "$CRAYON" summary demo-unit --json >summary.json 2>>err.txt
    assert_eq "summary --json exits 0" "0" "$?"
    local probe='
import json, sys
handover = json.load(open(sys.argv[1], encoding="utf-8"))["handover"]
print("%s|%s|%s|%s" % (
    ",".join(str(row["seq"]) for row in handover["judged"]),
    handover["judged"][0]["origin"] if handover["judged"] else "",
    ",".join(str(row["seq"]) for row in handover["withdrawn"]),
    handover["withdrawn"][0]["reason"] if handover["withdrawn"] else "",
))
'
    assert_eq "show --json hands over the judged request and the withdrawal" \
        "4|review fix|5|out of scope for this page" "$(python3 -c "$probe" show.json)"
    assert_eq "summary --json carries the same handover" \
        "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))["handover"], sort_keys=True))' show.json)" \
        "$(python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))["handover"], sort_keys=True))' summary.json)"
    assert_not_contains "human show prints no handover block" \
        "$("$CRAYON" show demo-unit 2>&1)" "handover"
    cleanup
}

# SURF-02 (D-10): a skipped step is handed over from the moment it is recorded,
# before any draft or accept.
test_show_json_hands_over_a_skipped_step_before_any_accept() {
    setup_repo
    walk_unit_new walk-unit
    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>&1
    local seq1
    seq1=$(last_plan_seq walk-unit)
    record_step walk-unit one "$seq1" pass "installed ok\n" >/dev/null 2>&1
    skip_step walk-unit three "$seq1" "the publish step needs a credential" \
        >/dev/null 2>&1

    "$CRAYON" show walk-unit --json >show.json 2>err.txt
    assert_eq "show --json exits 0" "0" "$?"
    assert_eq "the skipped step is handed over with its reason" \
        "three|skipped|the publish step needs a credential|publish the result" \
        "$(python3 -c '
import json, sys
steps = json.load(open(sys.argv[1], encoding="utf-8"))["handover"]["steps"]
print("|".join(steps[0][key] for key in ("id", "verdict", "reason", "text"))
      if len(steps) == 1 else json.dumps(steps))
' show.json)"
    assert_eq "nothing is judged before an accept" "[] []" "$(python3 -c '
import json, sys
handover = json.load(open(sys.argv[1], encoding="utf-8"))["handover"]
print(json.dumps(handover["judged"]), json.dumps(handover["withdrawn"]))
' show.json)"
    cleanup
}

# D-03 / SC2: the plainer accept line costs the record nothing — accept's
# `--json` still routes `publish` and carries the accepted files, the requests
# judged satisfied and the withdrawals with their reasons, copied from the event.
test_accept_json_carries_files_resolves_and_withdraws() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "mention the flag" >/dev/null 2>&1

    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        --withdraw 5 "out of scope for this page" --json >accept.json 2>err.txt
    assert_eq "accept --json exits 0" "0" "$?"
    assert_eq "accept --json prints exactly one line" "1" \
        "$(wc -l <accept.json | tr -d ' ')"
    assert_eq "accept --json still routes publish" "publish" \
        "$(json_field next <accept.json)"
    # CR-01 (contract 1): the plainer human line leaves the message as it was.
    assert_eq "accept --json keeps its contract-1 message" \
        "reviewed demo-unit: accept · 1 file(s) sealed · 1 request(s) judged satisfied, 1 withdrawn (a recorded judgment, never proof that the bytes changed)" \
        "$(json_field message <accept.json)"
    assert_eq "accept --json carries the resolves" "[4]" "$(python3 -c '
import json, sys
print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")).get("resolves")))
' accept.json)"
    assert_eq "accept --json carries the withdrawals with their reasons" \
        '[{"seq": 5, "reason": "out of scope for this page"}]' "$(python3 -c '
import json, sys
print(json.dumps(json.load(open(sys.argv[1], encoding="utf-8")).get("withdraws")))
' accept.json)"
    assert_eq "accept --json carries the accepted files" "reference/demo.rst" \
        "$(event_paths <accept.json)"
    assert_eq "the files are the recorded accept event's, verbatim" \
        "$(sed -n '$p' .crayon/units/demo-unit/ledger.jsonl | event_files)" \
        "$(event_files <accept.json)"
    cleanup
}

# D-03: every page of the accepted set, uncapped, comma-separated, in the
# order the accept recorded them (the signoff's target order, not the alphabet).
test_accept_names_every_accepted_page_in_recorded_order() {
    setup_repo
    crayon_unit_new multi-unit "reference/b.rst" --also-target "reference/a.rst" \
        >/dev/null 2>&1
    "$CRAYON" signoff multi-unit >/dev/null 2>&1
    stage_draft multi-unit "reference/b.rst" "page b\n"
    stage_draft multi-unit "reference/a.rst" "page a\n"
    "$CRAYON" draft multi-unit ".crayon/staging/multi-unit/draft" >/dev/null 2>&1

    local out
    out=$("$CRAYON" review multi-unit --verdict accept --note "both read well" 2>err.txt)
    assert_eq "the two-page accept exits 0" "0" "$?"
    assert_eq "the accept line names both pages in recorded order" \
        "reviewed multi-unit: accept · accepted reference/b.rst, reference/a.rst · Next: yours — crayon stops here" \
        "$out"
    cleanup
}

# D-16: the harness's ledger-vocabulary check, driven against a PRIVATE
# results file so its deliberate failures are this test's evidence rather than
# the suite's (the WR-12 shape). It must bite on each forbidden sample and pass
# the plain accept line.
test_d16_assert_plain_bites_on_ledger_vocabulary() {
    setup_repo
    local outer="$RESULTS" probe
    probe=$(mktemp)
    RESULTS="$probe"

    assert_plain "a plan hash" "signed off u · plan_hash 0123456789ab · Next: draft"
    assert_plain "the basis" "recorded edits on u · 1 file(s) in the basis · Next: review"
    assert_plain "a request seq" "seq 4 — resolved"
    assert_plain "sealed" "state: sealed"
    assert_plain "a digest" \
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    local forbidden_fails forbidden_passes
    forbidden_fails=$(grep -c '^FAIL' "$probe" || true)
    forbidden_passes=$(grep -c '^PASS' "$probe" || true)

    : >"$probe"
    assert_plain "the plain accept" \
        "reviewed u: accept · accepted reference/a.rst · Next: yours — crayon stops here"
    assert_plain "a short sha" "resumed u · completed the interrupted write · 0123abc"
    local plain_passes plain_fails
    plain_passes=$(grep -c '^PASS' "$probe" || true)
    plain_fails=$(grep -c '^FAIL' "$probe" || true)

    RESULTS="$outer"
    rm -f "$probe"

    assert_eq "every forbidden sample fails" "5" "$forbidden_fails"
    assert_eq "and none of them passes" "0" "$forbidden_passes"
    assert_eq "the plain lines pass" "2" "$plain_passes"
    assert_eq "and record no failure" "0" "$plain_fails"
    cleanup
}

# D-16 (P-03): signoff and --re-sign say what changed, where, what remains and
# Next — the ledger path in place of a plan-hash prefix.
test_d16_signoff_and_re_sign_lines_are_plain() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >so-out.txt 2>so-err.txt
    assert_eq "signoff exits 0" "0" "$?"
    assert_response_line "signoff" so-out.txt "draft"
    assert_eq "the signoff line names the ledger and the frozen targets" \
        "signed off demo-unit · .crayon/units/demo-unit/ledger.jsonl · 1 target(s) frozen · Next: draft" \
        "$(cat so-out.txt)"
    assert_plain "the signoff line" "$(cat so-out.txt)"

    "$CRAYON" unit edit demo-unit --audience "A different audience" --re-sign \
        >rs-out.txt 2>rs-err.txt
    assert_eq "the re-sign exits 0" "0" "$?"
    assert_response_line "re-sign" rs-out.txt "draft"
    assert_eq "the re-sign line has the same shape" \
        "re-signed demo-unit · .crayon/units/demo-unit/ledger.jsonl · 1 target(s) frozen · Next: draft" \
        "$(cat rs-out.txt)"
    assert_plain "the re-sign line" "$(cat rs-out.txt)"
    cleanup
}

# The plan hash of the ledger's last event, cut to the 12 hex digits the
# contract-1 signoff message carries. Read from the record, never a literal.
last_plan_hash_prefix() {
    python3 -c '
import json, sys
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
print(json.loads(lines[-1])["plan_hash"][:12])
' ".crayon/units/$1/ledger.jsonl"
}

# CR-01 (contract 1): the plain human line costs `--json` nothing. signoff's
# `message` keeps the wording it had before the human line was reworded,
# plan-hash prefix included; the human line is pinned by the test above.
test_signoff_json_message_keeps_its_contract_1_wording() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit --json >so.json 2>so-err.txt
    assert_eq "signoff --json exits 0" "0" "$?"
    assert_eq "signoff --json prints exactly one line" "1" \
        "$(wc -l <so.json | tr -d ' ')"
    assert_eq "signoff --json routes draft" "draft" "$(json_field next <so.json)"
    assert_eq "signoff --json keeps its contract-1 message" \
        "signed off demo-unit · plan_hash $(last_plan_hash_prefix demo-unit) · 1 target(s) frozen" \
        "$(json_field message <so.json)"
    cleanup
}

# CR-01 (contract 1): `unit edit --re-sign --json` keeps the plan-hash prefix
# of the re-sign, read from the ledger's last event.
test_re_sign_json_message_keeps_its_contract_1_wording() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    "$CRAYON" unit edit demo-unit --audience "A different audience" --re-sign --json \
        >rs.json 2>rs-err.txt
    assert_eq "the re-sign --json exits 0" "0" "$?"
    assert_eq "the re-sign --json prints exactly one line" "1" \
        "$(wc -l <rs.json | tr -d ' ')"
    assert_eq "the re-sign --json routes draft" "draft" "$(json_field next <rs.json)"
    assert_eq "the re-sign --json keeps its contract-1 message" \
        "re-signed demo-unit · plan_hash $(last_plan_hash_prefix demo-unit) · 1 target(s) frozen" \
        "$(json_field message <rs.json)"
    cleanup
}

# CR-01 (contract 1): `edits --json` still counts the files in the basis; the
# human line's plainer count is pinned by test_d16_edits_line_is_plain.
test_edits_json_message_keeps_its_contract_1_wording() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    "$CRAYON" edits demo-unit --note "the hand edit" --json >e.json 2>e-err.txt
    assert_eq "edits --json exits 0" "0" "$?"
    assert_eq "edits --json prints exactly one line" "1" \
        "$(wc -l <e.json | tr -d ' ')"
    assert_eq "edits --json routes review" "review" "$(json_field next <e.json)"
    assert_eq "edits --json keeps its contract-1 message" \
        "recorded edits on demo-unit · .crayon/units/demo-unit/ledger.jsonl · 1 file(s) in the basis" \
        "$(json_field message <e.json)"
    cleanup
}

# D-16 (P-02): edits records the pages as they are now; nothing has accepted
# them yet, so the line claims no acceptance and names no basis.
test_d16_edits_line_is_plain() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    "$CRAYON" edits demo-unit --note "the hand edit" >e-out.txt 2>e-err.txt
    assert_eq "edits exits 0" "0" "$?"
    assert_response_line "edits" e-out.txt "review"
    assert_contains "the edits line counts the pages recorded" "$(cat e-out.txt)" \
        "1 page(s) recorded as they are now"
    assert_plain "the edits line" "$(cat e-out.txt)"
    cleanup
}

# D-16 (P-04): resume and its dry run say what happened in words; the seq range
# stays in the refusal that shares the classification, which is exempt.
test_d16_resume_lines_are_plain() {
    setup_repo
    crashed_unit_new dry append
    "$CRAYON" resume dry --dry-run >dry-out.txt 2>dry-err.txt
    assert_eq "the dry run exits 0" "0" "$?"
    local dry_line
    dry_line=$(tail -n 1 dry-out.txt)
    assert_contains "the dry run counts the uncommitted events" "$dry_line" \
        "uncommitted event(s) from an interrupted write"
    assert_not_contains "the dry run names no seq" "$dry_line" "seq"
    assert_plain "the dry-run line" "$dry_line"

    "$CRAYON" resume dry >res-out.txt 2>res-err.txt
    assert_eq "resume exits 0" "0" "$?"
    local resume_line
    resume_line=$(tail -n 1 res-out.txt)
    assert_contains "resume says it completed the write" "$resume_line" \
        "resumed dry · completed the interrupted write"
    assert_not_contains "resume names no seq" "$resume_line" "seq"
    assert_plain "the resume line" "$resume_line"
    cleanup
}

# CR-01 (contract 1): the dry run and the resume keep their seq ranges in
# `--json` — the dry run's with an en dash, from the classification's detail,
# and the resume's with an ASCII hyphen — and the resume names the new HEAD.
# The two files are the unit's `unit.md` and `.crayon/.gitattributes`, as the
# tool at eeb33aa counts them on this fixture.
test_resume_json_messages_keep_their_contract_1_wording() {
    setup_repo
    crashed_unit_new dry append
    "$CRAYON" resume dry --dry-run --json >dry.json 2>dry-err.txt
    assert_eq "the dry run --json exits 0" "0" "$?"
    assert_eq "the dry run --json prints exactly one line" "1" \
        "$(wc -l <dry.json | tr -d ' ')"
    assert_eq "the dry run --json keeps its contract-1 message" \
        "resumable dry · uncommitted event(s) at seq 0–1 · 2 file(s)" \
        "$(json_field message <dry.json)"

    "$CRAYON" resume dry --json >res.json 2>res-err.txt
    assert_eq "resume --json exits 0" "0" "$?"
    assert_eq "resume --json prints exactly one line" "1" \
        "$(wc -l <res.json | tr -d ' ')"
    assert_eq "resume --json keeps its contract-1 message" \
        "resumed dry · seq 0-1 · $(git rev-parse --short HEAD) · 2 file(s) placed" \
        "$(json_field message <res.json)"
    cleanup
}

test_show_diff_prints_the_recorded_basis_bytes() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst

    local out
    out=$("$CRAYON" show demo-unit --diff 2>err.txt)
    assert_eq "show --diff exits 0" "0" "$?"
    assert_contains "the diff drops the recorded line" "$out" "-The drafted body."
    assert_contains "the diff adds the current line" "$out" "+Edited by hand."
    # P-20: the human label says what the side is; --json keeps `basis:` (SC3).
    assert_contains "the recorded side is labelled plainly" "$out" \
        "--- recorded:reference/demo.rst"
    assert_plain "show --diff speaks plainly" "$out"
    local diff_json
    diff_json=$("$CRAYON" show demo-unit --json --diff 2>/dev/null | python3 -c '
import json, sys
print(json.load(sys.stdin)["diff"]["reference/demo.rst"])')
    assert_contains "show --json --diff keeps the basis label" "$diff_json" \
        "--- basis:reference/demo.rst"
    cleanup
}

test_show_diff_says_so_when_the_recorded_bytes_are_unreachable() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    # History rewriting: the tree is untouched (so the committed prefix still
    # matches) but the Crayon-Seq trailer that located the basis bytes is gone.
    git commit -q --amend -m "rewritten history"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst

    local out
    out=$("$CRAYON" show demo-unit --diff 2>err.txt)
    assert_eq "show --diff still exits 0" "0" "$?"
    assert_contains "it says the recorded bytes are unavailable" "$out" \
        "the recorded bytes for reference/demo.rst are unavailable"
    assert_contains "it shows the current content instead" "$out" "Edited by hand."
    assert_not_contains "it never invents a diff" "$out" "-The drafted body."
    assert_plain "the unreachable case speaks plainly" "$out"
    local diff_json
    diff_json=$("$CRAYON" show demo-unit --json --diff 2>/dev/null | python3 -c '
import json, sys
print(json.load(sys.stdin)["diff"]["reference/demo.rst"])')
    assert_contains "show --json --diff keeps its wording" "$diff_json" \
        "the recorded basis bytes for reference/demo.rst are unavailable"
    cleanup
}

test_show_json_parses_and_carries_hashes_and_seqs() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    local out
    out=$("$CRAYON" show demo-unit --json 2>err.txt)
    assert_eq "show --json exits 0" "0" "$?"
    local probe
    probe=$(printf '%s' "$out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
row = data["paths"][0]
print("%s|%s|%s|%s" % (
    data["state"], data["next"], data["seqs"]["basis"], row["recorded_sha"][:8]))
')
    assert_eq "the object carries state, next, seqs and hashes" \
        "drafted|review|3|$(sha256_of_file docs/reference/demo.rst | cut -c1-8)" "$probe"
    cleanup
}

test_show_is_read_only_over_a_stray_pending_tree() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    mkdir -p .crayon/staging/demo-unit/pending/after/docs/reference
    printf 'half-written recovery material\n' \
        >.crayon/staging/demo-unit/pending/after/docs/reference/demo.rst
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst

    local before after out
    before=$(readonly_fingerprint demo-unit)
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_eq "show exits 0 with a stray pending/" "0" "$?"
    assert_contains "it reports what write mode would delete" "$(cat err.txt)" \
        "would delete pending/"
    assert_file_exists "it deletes nothing" ".crayon/staging/demo-unit/pending"
    after=$(readonly_fingerprint demo-unit)
    assert_eq "ledger, pages, pending/ and the index are byte-identical" \
        "$before" "$after"

    # The same boundary under --diff and --json.
    "$CRAYON" show demo-unit --diff >/dev/null 2>&1
    "$CRAYON" show demo-unit --json >/dev/null 2>&1
    assert_eq "--diff and --json write nothing either" "$before" \
        "$(readonly_fingerprint demo-unit)"
    cleanup
}

test_show_on_an_unknown_unit_is_refused() {
    setup_repo
    "$CRAYON" show unknown-id >/dev/null 2>err.txt
    assert_eq "show on an unknown unit exits 2" "2" "$?"
    assert_json_error "unit_not_found on show" "err.txt" "unit_not_found"
    cleanup
}

# --- VERB-03: summary — the paste-ready PR text ------------------------------

# The set of column counts across every Markdown table row. One element means
# every row has the same column count; a note that broke a table would add a
# second.
md_table_columns() {
    python3 -c '
import re, sys
counts = set()
for line in sys.stdin.read().splitlines():
    if line.startswith("|"):
        counts.add(len(re.findall(r"(?<!\\)\|", line)))
print(",".join(str(count) for count in sorted(counts)))
'
}

test_summary_reports_the_record_and_the_page_on_a_sealed_unit() {
    setup_repo
    # The transient staging path is the repository's to ignore, and V17 asks git
    # about it — so a repo that has the pattern is what a CLEAN verdict looks
    # like. Without it the verdict would be `warn` and this test would be
    # pinning the fixture's hygiene rather than the sealed unit's provenance.
    printf '.crayon/staging/\n' >.gitignore
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1

    local out
    out=$("$CRAYON" summary demo-unit 2>err.txt)
    assert_eq "summary exits 0" "0" "$?"
    assert_contains "summary prints the title" "$out" "Demo"
    assert_contains "a single-file unit still lists its file" "$out" \
        "reference/demo.rst"
    assert_contains "summary prints the intent" "$out" "  intent: reference"
    assert_contains "summary prints the audience" "$out" \
        "  audience: TAs onboarding to the docs repo"
    # SURF-01 (D-12): the author's decisions are read before the file list.
    assert_eq "the author's decisions open the report, after the title" \
        "author decisions:" "$(printf '%s\n' "$out" | sed -n '2p')"
    assert_eq "the intent sits in that block, before the files" "yes" \
        "$(printf '%s\n' "$out" | awk '/^  intent: / {i=NR} /^files changed:/ {f=NR}
            END {print (i && f && i < f) ? "yes" : "no"}')"
    assert_plain "summary's text carries no ledger vocabulary" "$out"
    # D-06: the human line says the record is intact, in plain words; the
    # counts stay in `summary --json` and `verify --json`.
    assert_contains "the record half says the record is intact" "$out" \
        "record: intact at "
    assert_not_contains "and quotes no check counts" "$out" "19 checks"
    assert_not_contains "the phase-16 placeholder is gone" "$out" \
        "verify has not run"
    assert_contains "the page half is reported" "$out" "page: current"
    cleanup
}

test_summary_never_claims_that_steering_was_applied() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" steer demo-unit --note "mention the flag" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        >/dev/null 2>&1

    local out
    out=$("$CRAYON" summary demo-unit 2>err.txt)
    assert_contains "requests are reported as recorded" "$out" "recorded requests:"
    assert_contains "with their disposition" "$out" "request 4 — resolved"
    assert_plain "the request rows carry no ledger vocabulary" "$out"
    assert_not_contains "summary never claims the steering was applied" "$out" \
        "steering applied"
    cleanup
}

test_summary_omits_sections_with_no_content() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1

    local out
    out=$("$CRAYON" summary demo-unit 2>err.txt)
    assert_not_contains "no gaps, no gaps heading" "$out" "known gaps:"
    assert_not_contains "no reviewer edits, no heading" "$out" "reviewer edits:"
    assert_not_contains "no RUN file, no sphinx line" "$out" "sphinx:"
    assert_not_contains "no step plan, no validation line" "$out" "validation:"
    assert_not_contains "no requests, no request heading" "$out" "recorded requests:"
    cleanup
}

test_summary_md_carries_pipes_and_newlines_without_breaking_a_table() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'mention the | flag\nand a second line' |
        "$CRAYON" steer demo-unit --note-file - >/dev/null 2>&1
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    printf 'hand edit | with a pipe\nand a second line' |
        "$CRAYON" edits demo-unit --note-file - >/dev/null 2>&1

    local out
    out=$("$CRAYON" summary demo-unit --md 2>err.txt)
    assert_eq "summary --md exits 0" "0" "$?"
    assert_contains "the request note's pipe survives, escaped in its cell" "$out" \
        'mention the \| flag<br>and a second line'
    assert_contains "the reviewer-edit note keeps its pipe verbatim in prose" "$out" \
        "hand edit | with a pipe"
    # WR-11: the characters stay visible; the LINE BREAK does not. A note free
    # to open a block of its own is a note free to forge this report.
    assert_contains "and its second line, folded onto one line" "$out" \
        "hand edit | with a pipe and a second line"
    assert_eq "every table row has the same column count" "4" \
        "$(printf '%s\n' "$out" | md_table_columns)"
    cleanup
}

# WR-11: `.crayon/` is committed, so every note, title and gap in it is ordinary
# contributor input — the threat model `contained_page`'s own docstring states
# — and `summary --md` is documented as text a reviewer PASTES INTO A PR. Only
# the table cells were escaped; the heading, the audience, the reviewer-edit
# notes, the known gaps and the Sphinx block were emitted verbatim.
test_summary_md_never_lets_a_recorded_note_forge_the_report() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    printf 'looks fine\n\n## Provenance\n\nrecord: verify ok at 0000000 (19 checks, 0 warn, 0 fail) · page: current\n\n<img src="http://attacker.example/beacon">' |
        "$CRAYON" edits demo-unit --note-file - >/dev/null 2>&1
    assert_eq "the forged note records like any other" "0" "$?"

    local out
    out=$("$CRAYON" summary demo-unit --md 2>err.txt)
    assert_eq "summary --md exits 0" "0" "$?"

    # The text is all still there — nothing is hidden from the reviewer.
    assert_contains "the note's words survive" "$out" "looks fine"
    assert_contains "including the part that was trying to be a heading" "$out" \
        "## Provenance"
    # But it cannot BE a heading, and it cannot be an element.
    assert_eq "there is exactly one Provenance heading in the document" "1" \
        "$(printf '%s\n' "$out" | grep -c '^## Provenance$')"
    assert_not_contains "and no raw HTML reaches the reviewer's pull request" \
        "$out" "<img"
    assert_contains "the element is shown, neutralised" "$out" "&lt;img"
    cleanup
}

# CR-03 (re-review): WR-11 escaped the PROSE positions and deliberately left
# `md_cell` alone — but `md_cell` is the escaper on the `## Recorded requests`
# table, which is where STEERING NOTES and WITHDRAWAL REASONS land. Those are
# the most common contributor-controlled strings in the whole report, and they
# were still emitted as live HTML into text a reviewer pastes into a PR. The
# `<br>`/column-count contract and the HTML escaping are independent rules.
test_summary_md_never_lets_a_steering_note_be_a_live_element() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" steer demo-unit \
        --note '<img src=x onerror=alert(1)> **bold** & <script>evil()</script>' \
        >/dev/null 2>&1
    assert_eq "the forged steering note records like any other" "0" "$?"

    local out
    out=$("$CRAYON" summary demo-unit --md 2>err.txt)
    assert_eq "summary --md exits 0" "0" "$?"
    assert_contains "the request reaches the table" "$out" "## Recorded requests"

    # Visible, and inert — the same rule every other position follows.
    assert_contains "the element is shown, neutralised" "$out" "&lt;img"
    assert_contains "so is the script tag" "$out" "&lt;script&gt;"
    assert_contains "and the bare ampersand" "$out" "&amp;"
    assert_not_contains "no raw element reaches the reviewer's pull request" \
        "$out" "<img"
    assert_not_contains "and no raw script tag either" "$out" "<script"
    assert_contains "the author's own words survive" "$out" "onerror=alert(1)"

    # The cell contract the escaping had to be threaded through is intact.
    assert_eq "every table row still has the same column count" "4" \
        "$(printf '%s\n' "$out" | md_table_columns)"
    cleanup
}

# CR-03: a newline in a steering note must still be a `<br>` after the HTML
# escaping, not the literal text `&lt;br&gt;` — the order inside `md_cell` is
# the whole of that property.
test_summary_md_keeps_the_cell_break_a_break_after_escaping() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'first line <b>x</b>\nsecond line\n' |
        "$CRAYON" steer demo-unit --note-file - >/dev/null 2>&1
    assert_eq "the two-line note records" "0" "$?"

    local out
    out=$("$CRAYON" summary demo-unit --md 2>err.txt)
    assert_contains "the newline is still a break" "$out" "<br>"
    assert_not_contains "and the break was not itself escaped" "$out" "&lt;br&gt;"
    assert_contains "while the note's own tag was" "$out" "&lt;b&gt;"
    assert_eq "every table row still has the same column count" "4" \
        "$(printf '%s\n' "$out" | md_table_columns)"
    cleanup
}

# WR-11: `validation/RUN-*.json` is UNTRACKED, unvalidated working-tree input
# whose `sphinx` value was `%s`-formatted into the document whatever it was.
test_summary_md_reports_only_a_bounded_string_from_an_unvalidated_run_file() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    mkdir -p validation

    # A non-string result is no result: a dict rendered into the document used
    # to become the whole `## Sphinx` section.
    printf '{"sphinx": {"status": "ok", "warnings": 3}}\n' \
        >validation/RUN-1.json
    local out
    out=$("$CRAYON" summary demo-unit --md 2>err.txt)
    assert_not_contains "a non-string sphinx result is not reported" "$out" \
        "## Sphinx"

    # A string one is, capped and folded.
    printf '{"sphinx": "%s"}\n' "$(python3 -c 'print("ok " * 200, end="")')" \
        >validation/RUN-1.json
    out=$("$CRAYON" summary demo-unit --md 2>err2.txt)
    assert_contains "a string sphinx result is reported" "$out" "## Sphinx"
    assert_eq "and is one bounded line" "1" \
        "$(printf '%s\n' "$out" | grep -c 'validation/RUN-1.json')"
    assert_eq "capped at the result-line budget" "yes" \
        "$(printf '%s\n' "$out" | awk '/validation\/RUN-1.json/ {print (length($0) <= 200) ? "yes" : "no"}')"
    cleanup
}

test_summary_reports_the_page_half_as_drifted_then_missing() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    printf 'Demo\n====\n\nEdited by hand.\n' >docs/reference/demo.rst
    git add docs/reference/demo.rst
    git commit -q -m "the author committed the edit outside crayon"

    local out sha
    out=$("$CRAYON" summary demo-unit 2>err.txt)
    assert_contains "a drifted page is named as drifted" "$out" "page: drifted since "
    sha=$(printf '%s\n' "$out" | sed -n 's/.*page: drifted since \([0-9a-f]*\).*/\1/p')
    assert_eq "the basis commit is named by a 7-character sha" "7" "${#sha}"

    rm docs/reference/demo.rst
    local gone
    gone=$("$CRAYON" summary demo-unit 2>err2.txt)
    assert_contains "a deleted page is missing" "$gone" "page: missing"
    cleanup
}

test_summary_json_parses() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    local out probe
    out=$("$CRAYON" summary demo-unit --json 2>err.txt)
    assert_eq "summary --json exits 0" "0" "$?"
    probe=$(printf '%s' "$out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
print("%s|%s|%s" % (data["title"], data["files"][0], data["provenance"][:14]))
')
    assert_eq "the object carries the title, the files and the provenance" \
        "Demo|reference/demo.rst|record: verify" "$probe"
    cleanup
}

# SURF-01's data (D-13, D-15): `summary --json` carries every note the author
# wrote, oldest first; an accept's own note precedes its withdrawals.
test_summary_json_carries_the_authors_notes() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "mention the flag" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        --withdraw 5 "out of scope for this page" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "one more thing" >/dev/null 2>&1

    "$CRAYON" summary demo-unit --json >summary.json 2>err.txt
    assert_eq "summary --json exits 0" "0" "$?"
    assert_eq "the author's notes are listed oldest first, by origin" \
        "review fix,steering (manual),review accept,withdrawal,steering (manual)" \
        "$(python3 -c '
import json, sys
notes = json.load(open(sys.argv[1], encoding="utf-8"))["author_notes"]
print(",".join(row["origin"] for row in notes))
' summary.json)"
    assert_eq "the withdrawal carries its reason and names the request" \
        "6|out of scope for this page|5" "$(python3 -c '
import json, sys
notes = json.load(open(sys.argv[1], encoding="utf-8"))["author_notes"]
row = [row for row in notes if row["origin"] == "withdrawal"]
print("%s|%s|%s" % (row[0]["seq"], row[0]["note"], row[0]["request"]) if row else "none")
' summary.json)"
    assert_eq "show --json does not carry the notes list" "False" \
        "$("$CRAYON" show demo-unit --json | python3 -c '
import json, sys
print("author_notes" in json.load(sys.stdin))
')"
    cleanup
}

# SURF-01 (D-12, D-13, D-14): `summary --md` opens with the author's decisions:
# intent, audience, every note the author wrote, and what is still open.
test_summary_md_opens_with_the_authors_decisions() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict fix --note "tighten the intro" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "mention the flag" >/dev/null 2>&1
    "$CRAYON" review demo-unit --verdict accept --note "ship it" --resolves 4 \
        --withdraw 5 "out of scope for this page" >/dev/null 2>&1

    local out
    out=$("$CRAYON" summary demo-unit --md 2>err.txt)
    assert_eq "summary --md exits 0" "0" "$?"
    assert_eq "Author decisions is the first section" "## Author decisions" \
        "$(printf '%s\n' "$out" | grep -m1 '^## ')"
    assert_contains "the author's notes are listed" "$out" "### The author's notes"
    assert_contains "a fix reads as a request" "$out" \
        "- request 4, fix: tighten the intro"
    assert_contains "a withdrawal names its request and reason" "$out" \
        "- request 5 withdrawn: out of scope for this page"
    assert_contains "the accept's own note is the author's" "$out" "- accepted: ship it"
    assert_contains "what is open at handover is listed" "$out" \
        "### Still open at handover"
    assert_contains "a judged request reads as a plain statement" "$out" \
        "Request 4 was accepted without a page change: tighten the intro"
    assert_contains "the request table names requests" "$out" \
        "| request | disposition | note |"
    assert_not_contains "the old section is gone" "$out" "## Intent and audience"
    assert_plain "summary --md carries no ledger vocabulary" "$out"

    local text
    text=$("$CRAYON" summary demo-unit 2>err2.txt)
    assert_contains "the text render carries the same open item" "$text" \
        "    Request 4 was accepted without a page change: tighten the intro"
    assert_contains "and the same note" "$text" "    request 4, fix: tighten the intro"
    cleanup
}

# SURF-01 (D-14): a skipped step is open from the moment it is recorded, and the
# report says so plainly, before any draft or accept.
test_summary_lists_a_skipped_step_as_open_before_any_accept() {
    setup_repo
    walk_unit_new walk-unit
    printf '%s' "$THREE_STEPS" |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>&1
    local seq1
    seq1=$(last_plan_seq walk-unit)
    record_step walk-unit one "$seq1" pass "installed ok\n" >/dev/null 2>&1
    skip_step walk-unit three "$seq1" "the publish step needs a credential" \
        >/dev/null 2>&1

    local out
    out=$("$CRAYON" summary walk-unit 2>err.txt)
    assert_eq "summary exits 0 before any draft" "0" "$?"
    assert_contains "the skipped step is open, in plain words" "$out" \
        "Step three was skipped: the publish step needs a credential"
    assert_not_contains "the step's reason is not presented as the author's note" \
        "$out" "  notes:"
    assert_contains "a unit with no page says so plainly" "$out" \
        "page: no page recorded yet"
    assert_plain "the whole report is plain" "$out"
    cleanup
}

test_summary_is_read_only() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    mkdir -p .crayon/staging/demo-unit/pending/after/docs/reference
    printf 'half-written recovery material\n' \
        >.crayon/staging/demo-unit/pending/after/docs/reference/demo.rst

    local before
    before=$(readonly_fingerprint demo-unit)
    "$CRAYON" summary demo-unit >/dev/null 2>err.txt
    assert_eq "summary exits 0 with a stray pending/" "0" "$?"
    assert_contains "it reports what write mode would delete" "$(cat err.txt)" \
        "would delete pending/"
    assert_file_exists "it deletes nothing" ".crayon/staging/demo-unit/pending"
    "$CRAYON" summary demo-unit --md >/dev/null 2>&1
    "$CRAYON" summary demo-unit --json >/dev/null 2>&1
    assert_eq "ledger, pages, pending/ and the index are byte-identical" \
        "$before" "$(readonly_fingerprint demo-unit)"
    cleanup
}

test_summary_on_an_unknown_unit_is_refused() {
    setup_repo
    "$CRAYON" summary unknown-id >/dev/null 2>err.txt
    assert_eq "summary on an unknown unit exits 2" "2" "$?"
    assert_json_error "unit_not_found on summary" "err.txt" "unit_not_found"
    cleanup
}

# --- N-47: the `context` verbs (repo-level) — T35 record, T35b names, T35c no-op, T36 drift ---

stage_context() {
    # stage_context <name> <content> [--source …]: one artefact through the tool.
    local name="$1" content="$2"
    shift 2
    printf '%b' "$content" | "$CRAYON" context stage "$name" --body-file - "$@"
}

test_n47_t35_context_record_commits_the_staged_set_without_a_unit() {
    setup_repo
    # The documented install ignores `.crayon/staging/`; this repo does the same
    # so "the tree is clean" is a statement about the record, not the fixture.
    printf '.crayon/staging/\n' >.gitignore
    git add .gitignore && git commit -q -m "ignore staging"
    local head_before rc
    head_before=$(git rev-parse HEAD)

    assert_contains "an empty repo routes onboard" \
        "$("$CRAYON" context show 2>&1)" "Next: onboard"

    stage_context doc-style.md "# Style\n\nImperative.\n" --source docs/index.md >out.txt 2>err.txt
    assert_eq "stage exits 0" "0" "$?"
    assert_contains "stage routes record" "$(cat out.txt)" "Next: record"
    assert_file_exists "the staged artefact is under the tool's own staging dir" \
        ".crayon/staging/_context/doc-style.md"
    stage_context glossary.md "# Glossary\n" >/dev/null 2>&1
    stage_context structure.md "# Structure\n" >/dev/null 2>&1
    assert_eq "staging is gitignored" "" "$(git status --porcelain -- .crayon)"

    "$CRAYON" context record --model m1 --model-origin skill --note "first walk" >out.txt 2>err.txt
    rc=$?
    assert_eq "record exits 0" "0" "$rc"
    assert_contains "record routes plan" "$(cat out.txt)" "Next: plan"
    assert_contains "record reports the commit on stderr" "$(cat err.txt)" "git: committed"
    assert_not_eq "record made one commit" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the commit subject is the repo-level phase" "crayon: context recorded" \
        "$(git log -1 --format=%s)"
    assert_eq "the pathspecs are the three artefacts and the manifest, explicitly" \
        ".crayon/context/doc-style.md .crayon/context/glossary.md .crayon/context/manifest.json .crayon/context/structure.md" \
        "$(git show --name-only --format= HEAD | sort | tr '\n' ' ' | sed 's/ $//')"
    local trailers
    trailers=$(git log -1 --format='%(trailers)')
    assert_contains "Crayon-Phase names the context record" "$trailers" "Crayon-Phase: context-recorded"
    assert_contains "Crayon-Head is the head before" "$trailers" "Crayon-Head: ${head_before:0:16}"
    assert_contains "Crayon-Model carries the claim" "$trailers" "Crayon-Model: m1"
    assert_not_contains "no Crayon-Unit: the context belongs to the repo" "$trailers" "Crayon-Unit"
    assert_not_contains "no Crayon-Seq: no event was written" "$trailers" "Crayon-Seq"
    assert_file_not_exists "no unit ledger appeared" ".crayon/units"

    # Every manifest digest is the digest of the committed bytes.
    local ok
    ok=$(python3 -c '
import hashlib, json, sys
m = json.load(open(".crayon/context/manifest.json"))
bad = [n for n, e in m["artifacts"].items()
       if e["sha256"] != hashlib.sha256(open(".crayon/context/" + n, "rb").read()).hexdigest()]
print("ok" if not bad and sorted(m["artifacts"]) == ["doc-style.md", "glossary.md", "structure.md"]
      and m["artifacts"]["doc-style.md"]["sources"] == ["docs/index.md"] and m["commit"] == sys.argv[1]
      else "bad %r" % bad)' "$head_before")
    assert_eq "the manifest freezes tool-computed digests and the declared sources" "ok" "$ok"
    assert_file_not_exists "staging is cleared after the record" ".crayon/staging/_context"
    assert_eq "the tree is clean after the record" "" "$(git status --porcelain -- .crayon)"
    assert_contains "show now routes plan" "$("$CRAYON" context show 2>&1)" "Next: plan"
    cleanup
}

test_n47_t35b_an_unrecognised_artefact_name_and_a_stray_staged_file_are_refused() {
    setup_repo
    local rc
    stage_context profile.md "# P\n" >/dev/null 2>err.txt
    rc=$?
    assert_eq "an unknown name exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "err.txt" "bad_target"
    assert_file_contains "the hint names the five artefacts" "err.txt" "doc-gaps.md"
    assert_file_not_exists "nothing was staged" ".crayon/staging/_context"

    stage_context doc-style.md "# S\n" >/dev/null 2>&1
    echo smuggled >.crayon/staging/_context/evil.md
    "$CRAYON" context record >/dev/null 2>err.txt
    rc=$?
    assert_eq "a stray staged file exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "err.txt" "bad_target"
    assert_file_contains "the detail names the stray file" "err.txt" "evil.md"
    assert_file_not_exists "nothing was promoted" ".crayon/context"
    cleanup
}

test_n47_t35c_a_recorded_set_restaged_is_a_noop_and_a_partial_restage_keeps_the_rest() {
    setup_repo
    stage_context doc-style.md "# S\n" --source docs/index.md >/dev/null 2>&1
    stage_context glossary.md "# G\n" >/dev/null 2>&1
    "$CRAYON" context record >/dev/null 2>&1
    local head rc
    head=$(git rev-parse HEAD)

    stage_context glossary.md "# G\n" >/dev/null 2>&1
    "$CRAYON" context record --json >out.txt 2>err.txt
    rc=$?
    assert_eq "the same bytes no-op with exit 3" "3" "$rc"
    assert_contains "the refusal is noop_unchanged" "$(cat out.txt)" '"error": "noop_unchanged"'
    assert_contains "the payload carries the commit the record was made against" \
        "$(cat out.txt)" "$(python3 -c 'import json;print(json.load(open(".crayon/context/manifest.json"))["commit"])')"
    assert_eq "no commit was made" "$head" "$(git rev-parse HEAD)"
    assert_file_not_exists "the staged copies are discarded on the no-op" ".crayon/staging/_context"

    stage_context glossary.md "# G v2\n" >/dev/null 2>&1
    stage_context doc-gaps.md "# Gaps\n" >/dev/null 2>&1
    "$CRAYON" context record >/dev/null 2>&1
    rc=$?
    assert_eq "changed bytes record with exit 0" "0" "$rc"
    assert_eq "only the restaged artefacts and the manifest are in the commit" \
        ".crayon/context/doc-gaps.md .crayon/context/glossary.md .crayon/context/manifest.json" \
        "$(git show --name-only --format= HEAD | sort | tr '\n' ' ' | sed 's/ $//')"
    assert_eq "the manifest keeps every published row" "doc-gaps.md doc-style.md glossary.md" \
        "$(python3 -c 'import json;print(" ".join(sorted(json.load(open(".crayon/context/manifest.json"))["artifacts"])))')"
    assert_eq "an untouched row keeps its sources" "docs/index.md" \
        "$(python3 -c 'import json;print(" ".join(json.load(open(".crayon/context/manifest.json"))["artifacts"]["doc-style.md"]["sources"]))')"
    cleanup
}

test_n47_t36_a_hand_edit_after_the_record_is_reported_never_refused() {
    setup_repo
    stage_context doc-style.md "# S\n" >/dev/null 2>&1
    stage_context glossary.md "# G\n" >/dev/null 2>&1
    stage_context structure.md "# T\n" >/dev/null 2>&1
    "$CRAYON" context record >/dev/null 2>&1
    echo "edited by hand" >>.crayon/context/glossary.md
    echo "# by hand" >.crayon/context/code-to-docs-map.md

    local out rc
    out=$("$CRAYON" context show 2>err.txt)
    rc=$?
    assert_eq "show exits 0 over drift" "0" "$rc"
    assert_eq "show writes nothing to stderr" "0" "$(wc -c <err.txt | tr -d ' ')"
    assert_contains "the drifted artefact is named" "$out" "drifted: glossary.md"
    assert_contains "a hand-placed artefact is unrecorded, not drifted" "$out" \
        "unrecorded: code-to-docs-map.md"
    assert_contains "the three onboarding artefacts present route plan" "$out" "Next: plan"

    "$CRAYON" context record >/dev/null 2>err.txt
    rc=$?
    assert_eq "record with nothing staged exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "err.txt" "bad_target"
    assert_eq "the refusal routes per the context table" "plan" "$(refusal_next err.txt)"
    cleanup
}

# --- VERB-01 / VERB-08 / D-16: the whole verb surface, version, legacy units --

# Every phase-17 stub refuses identically: one JSON line, the transitional
# reason, a hint naming the phase, a routing token — and nothing written.
# D-16's stub census is gone with the last stub. `unit retire` (17-01),
# `plan-steps` / `step` (17-05), `resume` (17-06, 17-07) and now `verify`
# (17-09) are all implemented and covered end to end by
# `test_n40_t31_t32_…`, `test_n27_t12_t13_t14_…`, `test_n18_…`, the
# N-14/N-17/N-28/N-29/N-30/N-35/N-41 family and the `verify` block in
# tests/test_crayon_lifecycle.sh. `stub_verb`, `refuse_unimplemented` and
# STUB_REASON went with it, and `not_implemented` appears nowhere.
#
# What the census WAS worth keeping is its invariant — the verb wrote nothing —
# and for `verify` that is not a transitional fact but the verb's contract: it
# is read-only. So the two tests below inherit those assertions rather than
# deleting them.

test_verb06_verify_is_read_only_and_repeatable() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    local head_before ledger_before first second rc
    head_before=$(git rev-parse HEAD)
    ledger_before=$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.jsonl)")

    first=$("$CRAYON" verify demo-unit --verbose 2>err.txt)
    rc=$?
    assert_eq "verify exits 0 on a healthy unit" "0" "$rc"
    assert_eq "verify writes nothing to stderr" "0" "$(wc -c <err.txt | tr -d ' ')"
    assert_eq "--verbose prints 19 check lines and one summary line" "20" \
        "$(printf '%s\n' "$first" | wc -l | tr -d ' ')"
    assert_contains "the first line is V1" "$(printf '%s\n' "$first" | sed -n 1p)" "V1 "
    assert_contains "the last line is the summary" \
        "$(printf '%s\n' "$first" | sed -n 20p)" "verdict:"

    second=$("$CRAYON" verify demo-unit --verbose 2>/dev/null)
    assert_eq "a second run prints byte-identical output" "$first" "$second"
    assert_eq "verify makes no commit" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "verify leaves the ledger byte-unchanged" "$ledger_before" \
        "$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.jsonl)")"
    assert_file_not_exists "verify writes no pending/" \
        ".crayon/staging/demo-unit/pending"
    cleanup
}

# VOICE-04 / D-04: the default answers "is my record all right?" in one line
# when it is. The repository's own hygiene is fixed first, as
# TestSummaryGolden.build_fixture does, so V17 has nothing to say.
test_verb06_plain_verify_is_one_line_on_an_intact_record() {
    setup_repo
    printf '.crayon/staging/\n' >.gitignore
    git add .gitignore
    git commit -q -m "ignore the staging area"
    setup_drafted_unit demo-unit "reference/demo.rst"

    local head_before ledger_before first second rc
    head_before=$(git rev-parse HEAD)
    ledger_before=$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.jsonl)")

    first=$("$CRAYON" verify demo-unit 2>err.txt)
    rc=$?
    assert_eq "verify exits 0 on an intact record" "0" "$rc"
    assert_eq "and writes nothing to stderr" "0" "$(wc -c <err.txt | tr -d ' ')"
    assert_eq "the default report is exactly one line" "The record is intact." "$first"
    assert_plain "the intact line speaks plainly" "$first"

    second=$("$CRAYON" verify demo-unit 2>/dev/null)
    assert_eq "a second run prints byte-identical output" "$first" "$second"
    assert_eq "verify makes no commit" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "verify leaves the ledger byte-unchanged" "$ledger_before" \
        "$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.jsonl)")"
    cleanup
}

# CR-03: a page path is contributor content, so default `verify` names it as
# written. A UUID tail holds a 12-hex run that the plain-words table's digest
# rule used to cut to seven characters, naming a page that does not exist.
test_verify_keeps_a_uuid_page_path_as_written() {
    setup_repo
    printf '.crayon/staging/\n' >.gitignore
    git add .gitignore
    git commit -q -m "ignore the staging area"
    local unit="release-202609181200"
    local page="reference/550e8400-e29b-41d4-a716-446655440000.md"
    setup_drafted_unit "$unit" "$page"
    printf 'Demo\n====\n\nEdited by hand.\n' >"docs/$page"

    local head_before ledger_before first second rc detail
    head_before=$(git rev-parse HEAD)
    ledger_before=$(sha256_of_text "$(cat ".crayon/units/$unit/ledger.jsonl")")

    first=$("$CRAYON" verify "$unit" 2>/dev/null)
    rc=$?
    assert_eq "verify exits 0 on a drifted page" "0" "$rc"
    assert_eq "the report names the page exactly as written" \
        "The record is intact; these need a look:
  the pages on disk: $page: drifted (uncommitted)" "$first"

    second=$("$CRAYON" verify "$unit" 2>/dev/null)
    assert_eq "a second run prints byte-identical output" "$first" "$second"
    assert_eq "verify makes no commit" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "verify leaves the ledger byte-unchanged" "$ledger_before" \
        "$(sha256_of_text "$(cat ".crayon/units/$unit/ledger.jsonl")")"

    detail=$("$CRAYON" verify "$unit" --json 2>/dev/null | python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print([row for row in data["checks"] if row["id"] == "V14"][0]["detail"])
')
    assert_eq "--json carries the same detail" "$page: drifted (uncommitted)" "$detail"
    cleanup
}

test_verb06_the_json_report_goes_to_stdout_with_nothing_on_stderr() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" verify demo-unit --json >out.txt 2>err.txt
    assert_eq "the report is one JSON line on stdout" "1" \
        "$(wc -l <out.txt | tr -d ' ')"
    assert_eq "stderr carries nothing" "0" "$(wc -c <err.txt | tr -d ' ')"
    local shape
    shape=$(python3 -c '
import json, sys
data = json.loads(open(sys.argv[1], encoding="utf-8").readline())
row = data["checks"][0]
print("%s\t%d\t%s\t%s" % (
    ",".join(sorted(data)), len(data["checks"]), ",".join(sorted(row)),
    data["verdict"]))
' out.txt)
    assert_eq "the payload names the unit, the head, the verdict and the checks" \
        "checks,head,unit,verdict,warnings" "$(printf '%s' "$shape" | cut -f1)"
    assert_eq "the checks array carries 19 entries" "19" \
        "$(printf '%s' "$shape" | cut -f2)"
    assert_eq "each entry carries id, level, status and detail" \
        "detail,id,level,status" "$(printf '%s' "$shape" | cut -f3)"
    # P-07: with both flags --json wins, byte for byte.
    "$CRAYON" verify demo-unit --json --verbose >both.txt 2>/dev/null
    assert_eq "--json --verbose prints exactly what --json prints" \
        "$(cat out.txt)" "$(cat both.txt)"
    cleanup
}

test_verb08_version_reports_the_tool_and_contract_numbers() {
    setup_repo
    local out rc
    out=$("$CRAYON" version 2>err.txt)
    rc=$?
    assert_eq "version exits 0" "0" "$rc"
    assert_eq "version prints exactly one line" "1" \
        "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
    assert_contains "version names the tool version" "$out" "0.2.0"
    assert_contains "version names the contract number" "$out" "contract 1"

    local keys
    keys=$("$CRAYON" version --json | python3 -c '
import json, sys
print(",".join(sorted(json.load(sys.stdin))))
')
    assert_eq "version --json emits exactly the two compatibility keys" \
        "contract,tool" "$keys"
    assert_eq "version --json reports contract 1" "1" \
        "$("$CRAYON" version --json | json_field contract)"
    assert_eq "version --json reports the tool version" "0.2.0" \
        "$("$CRAYON" version --json | json_field tool)"
    cleanup
}

test_verb08_a_legacy_pipe_delimited_unit_is_refused_with_an_archive_hint() {
    setup_repo
    mkdir -p .crayon/units/legacy-unit
    printf '0|ledger|2026-01-01|v1\n1|declared|2026-01-01|legacy-unit\n' \
        >.crayon/units/legacy-unit/ledger.md
    local before
    before=$(sha256_of_text "$(cat .crayon/units/legacy-unit/ledger.md)")

    "$CRAYON" show legacy-unit >/dev/null 2>err.txt
    assert_eq "a legacy unit exits 2" "2" "$?"
    assert_json_error "legacy unit" "err.txt" "legacy_unit"
    assert_contains "the refusal hints at archiving" "$(cat err.txt)" "archive"
    assert_eq "the legacy ledger is byte-unchanged" "$before" \
        "$(sha256_of_text "$(cat .crayon/units/legacy-unit/ledger.md)")"
    assert_file_not_exists "no jsonl ledger is written in its place" \
        ".crayon/units/legacy-unit/ledger.jsonl"

    "$CRAYON" signoff legacy-unit >/dev/null 2>err2.txt
    assert_eq "a mutating verb on a legacy unit exits 2" "2" "$?"
    assert_json_error "legacy unit (mutating)" "err2.txt" "legacy_unit"
    assert_eq "a refused mutating verb leaves the legacy ledger unchanged" \
        "$before" "$(sha256_of_text "$(cat .crayon/units/legacy-unit/ledger.md)")"
    cleanup
}

# WR-03: contract 5.10's OTHER half — a FUTURE contract's ledger.
#
# `classify_stage_a` checked the header's `kind` and `unit` and never its `v`,
# so a `v: 2` record was parsed, derived from, and appended to by a contract-1
# tool. Only the read-only `verify` noticed (V1). `ledger_version_unsupported`
# sat in the reason table at exit 6 with no raiser anywhere in the tool.

# Rewrite the header's contract version and re-chain every line after it, so
# the result is what a future tool's ledger looks like to this one: chain-valid
# and unreadable.
restamp_ledger_version() {
    local unit="$1" version="$2"
    python3 -c '
import importlib.machinery, importlib.util, json, sys
loader = importlib.machinery.SourceFileLoader("crayon", sys.argv[1])
spec = importlib.util.spec_from_loader("crayon", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)
path = ".crayon/units/%s/ledger.jsonl" % sys.argv[2]
with open(path, encoding="utf-8") as handle:
    events = [json.loads(line) for line in handle if line.strip()]
events[0]["v"] = int(sys.argv[3])
lines, prev = [], None
for event in events:
    event["prev"] = prev
    line = module.canonical_line(event)
    lines.append(line)
    prev = module.chain_prev(line)
with open(path, "w", encoding="utf-8") as handle:
    handle.write("".join(line + "\n" for line in lines))
' "$CRAYON" "$unit" "$version"
    git add -A >/dev/null 2>&1
    git commit -q -m "fixture: ledger restamped to v${version}" >/dev/null 2>&1
}

test_verb08_wr03_a_future_contract_ledger_is_refused_never_half_read() {
    setup_repo
    crayon_unit_new future-unit "reference/future.rst" >/dev/null 2>&1
    "$CRAYON" signoff future-unit >/dev/null 2>&1
    restamp_ledger_version future-unit 2
    assert_eq "the restamped ledger is still chain-valid" "[]" \
        "$(chain_problems future-unit)"

    local before rc
    before=$(ledger_digest future-unit)

    # The read-only verb an author reaches for first.
    "$CRAYON" show future-unit >/dev/null 2>err.txt
    rc=$?
    assert_eq "a future-contract ledger exits 6" "6" "$rc"
    assert_json_error "the refusal names the version" "err.txt" \
        "ledger_version_unsupported"
    assert_file_contains "the detail says which version it read" "err.txt" \
        "ledger version 2"
    assert_file_contains "and which one this tool reads" "err.txt" "v1"
    assert_contains "the hint is archive, never migrate" "$(cat err.txt)" "archive"

    # And the mutating verb that would otherwise have APPENDED to it.
    "$CRAYON" steer future-unit --note "a note this tool must not record" \
        >/dev/null 2>err2.txt
    rc=$?
    assert_eq "a mutating verb exits 6 too" "6" "$rc"
    assert_json_error "the same refusal" "err2.txt" "ledger_version_unsupported"
    assert_eq "not one byte is appended" "$before" "$(ledger_digest future-unit)"
    cleanup
}

test_verb08_wr03_the_header_this_tool_writes_carries_its_own_contract_number() {
    setup_repo
    crayon_unit_new stamped-unit "reference/stamped.rst" >/dev/null 2>&1
    # The two header writers used to spell the literal `1` while V1 compared
    # against CONTRACT, so the first bump would have made every freshly written
    # ledger fail its own verifier.
    assert_eq "the header's v is the tool's own contract number" \
        "$("$CRAYON" version --json | json_field contract)" \
        "$(head -1 .crayon/units/stamped-unit/ledger.jsonl | json_field v)"
    "$CRAYON" verify stamped-unit --verbose >v1.txt 2>&1
    assert_eq "and the tool's own verifier passes V1" "0" "$?"
    assert_contains "V1 is reported ok" "$(cat v1.txt)" "V1 ok"
    cleanup
}

test_verb08_a_legacy_ledger_beside_a_jsonl_one_is_silently_ignored() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    # D-13: the five bash scripts still write ledger.md in the same directory
    # through phase 16, so coexistence must be silent, not an error.
    printf '0|ledger|2026-01-01|v1\n' >.crayon/units/demo-unit/ledger.md
    local legacy_before
    legacy_before=$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.md)")

    local out
    out=$("$CRAYON" show demo-unit 2>err.txt)
    assert_eq "a coexisting legacy file does not refuse" "0" "$?"
    assert_contains "the unit still routes normally" "$out" "Next: sign_off"
    assert_eq "the legacy file is left byte-unchanged" "$legacy_before" \
        "$(sha256_of_text "$(cat .crayon/units/demo-unit/ledger.md)")"
    assert_not_contains "the legacy file is never mentioned" "$(cat err.txt)" \
        "ledger.md"
    cleanup
}

test_stage_a_outside_a_git_repository_is_not_a_repo() {
    export GIT_CONFIG_GLOBAL=/dev/null
    export GIT_CONFIG_SYSTEM=/dev/null
    TEST_DIR=$(mktemp -d)
    cd "$TEST_DIR" || exit 1

    "$CRAYON" show demo-unit >/dev/null 2>err.txt
    assert_eq "a read verb outside a repo exits 2" "2" "$?"
    assert_json_error "not a repo (read)" "err.txt" "not_a_repo"

    "$CRAYON" signoff demo-unit >/dev/null 2>err2.txt
    assert_eq "a mutating verb outside a repo exits 2" "2" "$?"
    assert_json_error "not a repo (mutating)" "err2.txt" "not_a_repo"
    assert_file_not_exists "nothing is written outside a repository" ".crayon"
    cleanup
}

test_stage_a_a_repo_without_an_identity_refuses_before_writing() {
    setup_repo
    git config --unset user.name
    git config --unset user.email
    local head_before
    head_before=$(git rev-parse HEAD)

    crayon_unit_new id-unit "reference/x.rst" >/dev/null 2>err.txt
    assert_eq "a missing git identity exits 2" "2" "$?"
    assert_json_error "git identity" "err.txt" "git_identity_missing"
    assert_file_not_exists "nothing is written without an identity" \
        ".crayon/units/id-unit"
    assert_eq "no commit is made without an identity" "$head_before" \
        "$(git rev-parse HEAD)"
    cleanup
}

test_stage_a_a_ledger_whose_unit_field_disagrees_is_refused() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    mkdir -p .crayon/units/other-unit
    cp .crayon/units/demo-unit/ledger.jsonl .crayon/units/other-unit/ledger.jsonl
    cp .crayon/units/demo-unit/unit.md .crayon/units/other-unit/unit.md
    local before
    before=$(sha256_of_text "$(cat .crayon/units/other-unit/ledger.jsonl)")

    "$CRAYON" show other-unit >/dev/null 2>err.txt
    assert_eq "a unit id mismatch exits 6" "6" "$?"
    assert_json_error "unit id mismatch" "err.txt" "unit_id_mismatch"

    "$CRAYON" signoff other-unit >/dev/null 2>err2.txt
    assert_eq "a mutating verb on a mismatched ledger exits 6" "6" "$?"
    assert_json_error "unit id mismatch (mutating)" "err2.txt" "unit_id_mismatch"
    assert_eq "a mismatched ledger is left byte-unchanged" "$before" \
        "$(sha256_of_text "$(cat .crayon/units/other-unit/ledger.jsonl)")"
    cleanup
}

test_verb01_the_help_is_the_contract_verb_table_and_has_no_force() {
    setup_repo
    local help_out verb
    help_out=$("$CRAYON" --help 2>&1)
    for verb in unit signoff steer plan-steps step draft edits review resume \
        show summary verify version; do
        assert_contains "--help lists $verb" "$help_out" "$verb"
    done
    assert_not_contains "--help registers no --force" "$help_out" "--force"

    local unit_help
    unit_help=$("$CRAYON" unit --help 2>&1)
    for verb in new edit retire; do
        assert_contains "unit --help lists $verb" "$unit_help" "$verb"
    done

    for verb in signoff steer plan-steps step draft edits review resume show \
        summary verify version; do
        assert_not_contains "$verb --help registers no --force" \
            "$("$CRAYON" "$verb" --help 2>&1)" "--force"
    done
    for verb in new edit retire; do
        assert_not_contains "unit $verb --help registers no --force" \
            "$("$CRAYON" unit "$verb" --help 2>&1)" "--force"
    done
    cleanup
}

# --- VERB-04 / D-11: the author journeys, end to end, and the response shape --

# Test-id policy (D-03, RESEARCH Open Question 3): these are whole-flow
# acceptance functions carrying JOURNEY-DESCRIPTIVE names, not A-series ids.
# The concrete A-series ids were assigned in plan 17-10, when the 32 functions
# of the v1.x bash suite (`git show 357c513:tests/test_dogen_scripts.sh`) were
# ported and the whole A range could be enumerated at once; assigning a few
# earlier would either have collided with that port or reserved a range nothing
# had measured. Those functions are A-01…A-35, at the foot of this file; the
# journey-named functions here move to their own ids in plan 17-11. The N-series
# ids already used by the refusal tests below are fully enumerated and do not
# move.

# VERB-04: an exit-0 mutating verb answers in ONE stdout line whose segments
# are joined by ` · ` in a fixed order — what changed · where · what remains ·
# `Next: <token>`. The separator is checked as well as the token, because a
# line that runs two segments together is a line no reader can split.
assert_response_line() {
    local desc="$1" outfile="$2" expected_next="$3"
    assert_eq "$desc prints exactly one stdout line" "1" \
        "$(wc -l <"$outfile" | tr -d ' ')"
    local shape
    shape=$(python3 -c '
import sys
line = open(sys.argv[1], encoding="utf-8").read().rstrip("\n")
parts = line.split(" · ")
print("%d\t%s\t%s" % (
    len(parts),
    parts[-1],
    "empty" if any(not part.strip() for part in parts) else "full"))
' "$outfile")
    assert_eq "$desc ends with the routed token" "$(human_next_line "$expected_next")" \
        "$(printf '%s' "$shape" | cut -f2)"
    # D-03 (P-01): on `publish` the plain handover is itself the "what remains"
    # segment, so an accept's `reviewed · accepted · Next` is complete at three.
    local min_segments=4
    [ "$expected_next" = "publish" ] && min_segments=3
    assert_eq "$desc carries what changed, where, what remains and Next" "yes" \
        "$([ "$(printf '%s' "$shape" | cut -f1)" -ge "$min_segments" ] && echo yes || echo no)"
    assert_eq "$desc never runs two segments together" "full" \
        "$(printf '%s' "$shape" | cut -f3)"
    # D-16: no success line carries ledger vocabulary.
    assert_plain "$desc speaks plainly" "$(cat "$outfile")"
    return 0
}

# GATE-04: a non-zero exit is ONE stderr line, a JSON object carrying the five
# refusal keys. The only additional keys the contract allows are the no-op
# payload's `seq` and `commit`, which point the caller at the transition that
# already happened. `--json` moves that same line to stdout and changes
# nothing else.
assert_refusal_shape() {
    local desc="$1"
    shift
    "$CRAYON" "$@" >shape-out.txt 2>shape-err.txt
    local rc=$?
    assert_eq "$desc exits non-zero" "yes" \
        "$([ "$rc" -ne 0 ] && echo yes || echo no)"
    assert_eq "$desc prints exactly one stderr line" "1" \
        "$(wc -l <shape-err.txt | tr -d ' ')"
    assert_eq "$desc prints nothing on stdout" "0" \
        "$(wc -c <shape-out.txt | tr -d ' ')"
    assert_eq "$desc carries the five refusal keys and nothing undocumented" "ok" \
        "$(python3 -c '
import json, sys
payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
five = {"error", "unit", "detail", "hint", "next"}
missing = five - set(payload)
extra = set(payload) - five
print("ok" if not missing and extra <= {"seq", "commit"}
      else "missing=%s extra=%s" % (sorted(missing), sorted(extra)))
' shape-err.txt 2>/dev/null)"

    "$CRAYON" "$@" --json >shape-out2.txt 2>shape-err2.txt
    assert_eq "$desc inverts to stdout under --json" "1" \
        "$(wc -l <shape-out2.txt | tr -d ' ')"
    assert_eq "$desc leaves stderr carrying no JSON line under --json" "0" \
        "$(wc -c <shape-err2.txt | tr -d ' ')"
    return 0
}

# The sha256 of a file's BYTES — sha256_of_text drops a trailing newline.
page_digest() {
    python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$1"
}


# J5: the token `crayon show <id>` ALONE yields — no other state consulted. Read
# from `--json`, where the token is the routing token (CLOSE-04 maps only the
# human line).
show_next() {
    "$CRAYON" show "$1" --json 2>/dev/null | json_field next
}

# One journey transition: exit 0, the one-line response, exactly N commits, a
# chain that still verifies over every line, and `show` alone agreeing with the
# token the verb just printed.
journey_step() {
    local desc="$1" unit="$2" expected_next="$3" expected_commits="$4"
    shift 4
    local before
    before=$(git rev-list --count HEAD)
    "$CRAYON" "$@" >j-out.txt 2>j-err.txt
    local rc=$?
    assert_eq "$desc exits 0" "0" "$rc"
    assert_response_line "$desc" j-out.txt "$expected_next"
    assert_eq "$desc makes exactly $expected_commits commit(s)" \
        "$((before + expected_commits))" "$(git rev-list --count HEAD)"
    assert_eq "$desc leaves the chain verifying over every line" "[]" \
        "$(chain_problems "$unit")"
    assert_eq "$desc: show alone routes to the same token" "$expected_next" \
        "$(show_next "$unit")"
    assert_eq "$desc: the human show ends with the same Next line" \
        "$(human_next_line "$expected_next")" \
        "$("$CRAYON" show "$unit" 2>/dev/null | tail -n 1)"
    assert_eq "$desc names the unit in the commit trailer" "$unit" \
        "$(git log -1 --format='%(trailers:key=Crayon-Unit,valueonly)' | tr -d '\n')"
    return 0
}

test_j1_greenfield_end_to_end() {
    setup_repo
    local before
    before=$(git rev-list --count HEAD)

    crayon_unit_new j1-unit "reference/j1.rst" >j-out.txt 2>j-err.txt
    assert_eq "J1 unit new exits 0" "0" "$?"
    assert_response_line "J1 unit new" j-out.txt "sign_off"

    journey_step "J1 signoff" j1-unit draft 1 signoff j1-unit
    journey_step "J1 steer" j1-unit draft 1 \
        steer j1-unit --note "lead with why the reader is here"
    stage_draft j1-unit "reference/j1.rst" "J1\n==\n\nThe drafted body.\n"
    journey_step "J1 draft" j1-unit review 1 \
        draft j1-unit "$(draft_path j1-unit reference/j1.rst)"
    journey_step "J1 accept" j1-unit publish 1 \
        review j1-unit --verdict accept --note "reads well"

    assert_eq "J1 is exactly five commits, one per transition" "$((before + 5))" \
        "$(git rev-list --count HEAD)"
    assert_eq "J1 seals the unit" "sealed" "$(derived j1-unit state)"
    assert_eq "J1 ends at publish" "publish" "$(show_next j1-unit)"
    assert_eq "J1 writes the staged bytes to docs/<target>" \
        "$(cat .crayon/staging/j1-unit/draft/reference/j1.rst)" \
        "$(cat docs/reference/j1.rst)"
    assert_eq "J1's chain verifies over every ledger line" "[]" \
        "$(chain_problems j1-unit)"
    cleanup
}

test_j2_bounded_correction() {
    setup_repo
    setup_drafted_unit j2-unit "reference/j2.rst"

    # The fix verdict IS the steering: no separate `steer` is needed before the
    # corrective draft (contract 5.4 — a review is an H event).
    journey_step "J2 fix" j2-unit draft 1 \
        review j2-unit --verdict fix --note "tighten the intro"
    assert_eq "the fix is a pending request" "[4]" "$(derived j2-unit pending)"

    stage_draft j2-unit "reference/j2.rst" "J2\n==\n\nTightened.\n"
    journey_step "J2 corrective draft" j2-unit review 1 \
        draft j2-unit "$(draft_path j2-unit reference/j2.rst)"

    # Contract 5.4 counts `pending` from the LAST generation (T3): the
    # corrective draft answered the request, so disposing of it explicitly is
    # out of range — dispositions are drawn from pending, never invented.
    assert_eq "the corrective draft closed the request" "[]" \
        "$(derived j2-unit pending)"
    "$CRAYON" review j2-unit --verdict accept --note "ok" --resolves 4 \
        >/dev/null 2>j2-err.txt
    assert_eq "disposing of a request that is no longer pending exits 2" "2" "$?"
    assert_json_error "J2 bad_resolution" "j2-err.txt" "bad_resolution"

    journey_step "J2 accept" j2-unit publish 1 \
        review j2-unit --verdict accept --note "ok"
    assert_eq "J2 seals" "sealed" "$(derived j2-unit state)"
    cleanup
}

test_j3_plan_amendment() {
    setup_repo
    crayon_unit_new j3-unit "reference/j3.rst" \
        --also-target "reference/j3-extra.rst" >/dev/null 2>&1
    "$CRAYON" signoff j3-unit >/dev/null 2>&1
    stage_draft j3-unit "reference/j3.rst" "J3\n==\n\nOne.\n"
    stage_draft j3-unit "reference/j3-extra.rst" "Extra\n=====\n\nTwo.\n"
    "$CRAYON" draft j3-unit ".crayon/staging/j3-unit/draft" >/dev/null 2>&1
    assert_file_exists "both pages are written" "docs/reference/j3-extra.rst"

    journey_step "J3 amendment" j3-unit draft 1 \
        unit edit j3-unit --target "reference/j3.rst" --re-sign
    assert_contains "the dropped target is reported once, as kept on disk" \
        "$(cat j-out.txt)" "no longer a target; kept on disk: reference/j3-extra.rst"
    assert_file_exists "the orphaned page is kept on disk" \
        "docs/reference/j3-extra.rst"

    "$CRAYON" review j3-unit --verdict accept --note "ok" >/dev/null 2>j3-err.txt
    assert_eq "the old generation cannot be accepted" "1" "$?"
    assert_json_error "J3 generation_stale" "j3-err.txt" "generation_stale"

    rm -rf .crayon/staging/j3-unit/draft
    stage_draft j3-unit "reference/j3.rst" "J3\n==\n\nAmended.\n"
    journey_step "J3 redraft" j3-unit review 1 \
        draft j3-unit "$(draft_path j3-unit reference/j3.rst)"
    journey_step "J3 accept" j3-unit publish 1 \
        review j3-unit --verdict accept --note "ok"
    assert_eq "J3 seals" "sealed" "$(derived j3-unit state)"
    cleanup
}

test_j4_hand_edit_before_accept() {
    setup_repo
    setup_drafted_unit j4-unit "reference/j4.rst"

    printf 'J4\n==\n\nEdited by hand before the review.\n' >docs/reference/j4.rst
    assert_eq "show alone routes a hand edit to record_edits" "record_edits" \
        "$(show_next j4-unit)"

    journey_step "J4 edits" j4-unit review 1 \
        edits j4-unit --note "tightened the intro by hand"
    journey_step "J4 accept" j4-unit publish 1 \
        review j4-unit --verdict accept --note "the hand edit is what we want"
    assert_eq "J4 seals" "sealed" "$(derived j4-unit state)"
    assert_eq "the sealed basis is the hand-edited bytes" \
        "$(page_digest docs/reference/j4.rst)" \
        "$(printf '%s' "$(ledger_line j4-unit 5)" | python3 -c '
import json, sys
print((json.loads(sys.stdin.read()).get("files") or [{}])[0].get("sha256"))
')"
    cleanup
}

test_j5_fresh_conversation_routing() {
    setup_repo
    crayon_unit_new j5-unit "reference/j5.rst" >/dev/null 2>&1
    assert_eq "after unit new, show alone says sign_off" "sign_off" \
        "$(show_next j5-unit)"

    "$CRAYON" signoff j5-unit >/dev/null 2>&1
    assert_eq "after signoff, show alone says draft" "draft" "$(show_next j5-unit)"

    "$CRAYON" steer j5-unit --note "lead with the why" >/dev/null 2>&1
    assert_eq "after steer, show alone still says draft" "draft" \
        "$(show_next j5-unit)"

    stage_draft j5-unit "reference/j5.rst" "J5\n==\n\nBody.\n"
    "$CRAYON" draft j5-unit "$(draft_path j5-unit reference/j5.rst)" >/dev/null 2>&1
    assert_eq "after draft, show alone says review" "review" "$(show_next j5-unit)"

    printf 'J5\n==\n\nHand edited.\n' >docs/reference/j5.rst
    assert_eq "after a hand edit, show alone says record_edits" "record_edits" \
        "$(show_next j5-unit)"

    "$CRAYON" edits j5-unit --note "hand edit" >/dev/null 2>&1
    assert_eq "after edits, show alone says review" "review" "$(show_next j5-unit)"

    "$CRAYON" review j5-unit --verdict accept --note "ok" >/dev/null 2>&1
    assert_eq "after the accept, show alone says publish" "publish" \
        "$(show_next j5-unit)"

    "$CRAYON" unit edit j5-unit --audience "readers new to the repo" >/dev/null 2>&1
    assert_eq "after an amendment, show alone says re_sign" "re_sign" \
        "$(show_next j5-unit)"
    cleanup
}

test_j8_brownfield_adoption() {
    setup_repo
    printf 'the existing page\n' >docs/reference/j8.rst
    git add -A
    git commit -q -m "a page that predates crayon"

    crayon_unit_new j8-unit "reference/j8.rst" \
        --also-target "reference/j8-new.rst" >/dev/null 2>&1
    "$CRAYON" signoff j8-unit >j8-out.txt 2>j8-err.txt
    assert_eq "signoff over an existing page exits 0" "0" "$?"
    assert_response_line "J8 signoff" j8-out.txt "record_edits"

    journey_step "J8 adoption" j8-unit draft 1 \
        edits j8-unit --note "adopted existing page"
    assert_eq "the adoption lists only the page that exists" "reference/j8.rst" \
        "$(printf '%s' "$(ledger_line j8-unit 4)" | event_paths)"
    assert_file_not_exists "the new target is not conjured into existence" \
        "docs/reference/j8-new.rst"

    stage_draft j8-unit "reference/j8.rst" "the rewritten page\n"
    stage_draft j8-unit "reference/j8-new.rst" "the brand new page\n"
    journey_step "J8 draft" j8-unit review 1 \
        draft j8-unit ".crayon/staging/j8-unit/draft"
    assert_eq "the generation lists both targets" \
        "reference/j8.rst reference/j8-new.rst" \
        "$(printf '%s' "$(ledger_line j8-unit 5)" | event_paths)"
    assert_file_exists "the new page is written" "docs/reference/j8-new.rst"

    journey_step "J8 accept" j8-unit publish 1 \
        review j8-unit --verdict accept --note "both read well"
    assert_eq "J8 seals" "sealed" "$(derived j8-unit state)"
    cleanup
}

test_n36_t29_the_response_reports_the_token_the_hook_left_behind() {
    setup_repo
    setup_drafted_unit hook4-unit "reference/hook4.rst"
    "$CRAYON" steer hook4-unit --note "rewrite the opening" >/dev/null 2>&1
    stage_draft hook4-unit "reference/hook4.rst" "Hook\n====\n\nA second body.\n"
    install_rewrite_and_succeed_hook "docs/reference/hook4.rst"

    "$CRAYON" draft hook4-unit "$(draft_path hook4-unit reference/hook4.rst)" \
        >h-out.txt 2>h-err.txt
    assert_eq "a rewriting hook does not fail the draft" "0" "$?"
    assert_file_contains "the warning names the rewritten page" "h-err.txt" \
        "hook changed docs/reference/hook4.rst after recording"
    # The line is printed AFTER the post-commit check re-derived state, so it
    # reports what the hook left behind rather than what the tool meant.
    assert_response_line "a hook-rewritten page" h-out.txt "record_edits"
    rm -f .git/hooks/pre-commit

    # WR-05: the follow-up `edits`. T29 used to say it records the hook change
    # "with `hook:true`", which contradicted §5.3's own catalogue — that field
    # is scoped to `resume --adopt`, where the author was shown the bytes and
    # answered. A succeeding hook's rewrite is committed before anyone is
    # asked, so the note is the carrier and the clause was untested in either
    # direction. It is asserted here now, in the direction the code and §5.3
    # already agree on.
    "$CRAYON" edits hook4-unit --note "the formatter rewrote the page; kept" \
        >e-out.txt 2>e-err.txt
    assert_eq "the follow-up edits records the hook's bytes" "0" "$?"
    local edit
    edit=$(tail -1 .crayon/units/hook4-unit/ledger.jsonl)
    assert_eq "as a reviewer edit" "reviewer-edit" \
        "$(printf '%s' "$edit" | json_field kind)"
    assert_contains "whose note is the carrier" \
        "$(printf '%s' "$edit" | json_field note)" "the formatter rewrote the page"
    assert_not_contains "and which sets no hook flag: edits was never asked" \
        "$edit" '"hook"'
    cleanup
}

test_verb04_every_refusal_is_one_json_line_inverted_by_json() {
    setup_repo
    crayon_unit_new shape-unit "reference/shape.rst" >/dev/null 2>&1

    assert_refusal_shape "an unknown unit" show nope-unit
    assert_refusal_shape "a gate refusal" \
        draft shape-unit ".crayon/staging/shape-unit/draft"
    assert_refusal_shape "a bad-input refusal" signoff "Bad_Unit"
    assert_refusal_shape "a transitional stub" resume shape-unit
    # WR-06: `as_json` was assigned only AFTER parse_args, so a USAGE refusal —
    # the one class of error a skill hits while wiring up arguments — went to
    # stderr under --json and left stdout empty.
    assert_refusal_shape "a usage refusal" draft
    assert_refusal_shape "an unknown verb" nosuchverb

    "$CRAYON" signoff shape-unit >/dev/null 2>&1
    assert_refusal_shape "a no-op refusal" signoff shape-unit
    cleanup
}


# --- N-44: T9 — neither drift nor a stale generation is a precondition on `edits`

# The only trace-table row plan 17-11 had to WRITE rather than migrate. Every
# other T# already had a body in the acceptance suite; T9 had none, because the
# suite's `--re-sign` coverage all ran through the ACCEPT gate (N-19/T8, T9b) and
# T9 is the mirror image of it: the same sealed-then-re-signed unit taken down
# the `edits` → `draft` path instead, where the gates that stop an accept do not
# apply. `edits` is a recording verb, not a gated one — contract 5.7 c lists no
# drift or stale precondition for it — and the `--re-sign` signoff is itself an H
# event, so the generation it invalidated is also the steering the next draft
# needs. Asserting only the two exit codes would prove nothing about WHY, so the
# derived fields are read on both sides of each verb.
test_n44_t9_edits_then_draft_clear_a_re_signed_hand_edited_unit() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    "$CRAYON" review demo-unit --verdict accept --note "ship it" >/dev/null 2>&1
    assert_eq "the unit is sealed" "publish" "$(derived demo-unit next)"

    "$CRAYON" unit edit demo-unit --audience "A different audience" --re-sign \
        >/dev/null 2>&1
    assert_eq "the re-sign exits 0" "0" "$?"
    assert_eq "and invalidates the accepted generation" "true" \
        "$(derived demo-unit generation_stale)"

    # The author edits the page by hand and commits it outside crayon, so the
    # unit is BOTH drifted and stale when `edits` is called.
    printf 'Demo\n====\n\nEdited by hand after the re-sign.\n' >docs/reference/demo.rst
    git add -A >/dev/null 2>&1
    git commit -q -m "hand edit"
    assert_eq "the page is drifted" "true" "$(derived demo-unit page_drift)"
    assert_eq "drift routes to record_edits" "record_edits" "$(derived demo-unit next)"

    "$CRAYON" edits demo-unit --note "the hand edit" >e-out.txt 2>e-err.txt
    assert_eq "edits exits 0: neither drift nor staleness gates it" "0" "$?"
    assert_eq "the stderr line is git's, not a refusal" "0" \
        "$(grep -c '"error"' e-err.txt)"
    assert_contains "the edit is recorded as the new basis" "$(cat e-out.txt)" \
        "1 page(s) recorded as they are now"
    assert_eq "the recorded edit clears the drift" "false" \
        "$(derived demo-unit page_drift)"
    assert_eq "the generation is still stale — edits does not re-generate" "true" \
        "$(derived demo-unit generation_stale)"
    assert_eq "and the unit routes to draft" "draft" "$(derived demo-unit next)"

    # The `--re-sign` signoff is an H event since the generation, so the
    # steering gate is already satisfied: this draft is neither `unsteered` nor
    # blocked by the stale generation it replaces.
    assert_eq "the signoff counts as steering since the generation" "true" \
        "$(derived demo-unit steered_since_gen)"
    stage_draft demo-unit "reference/demo.rst" "Demo\n====\n\nA third body.\n"
    local out
    out=$("$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        2>d-err.txt)
    assert_eq "the draft exits 0: signoff is in H" "0" "$?"
    assert_eq "no refusal is printed" "0" "$(grep -c '"error"' d-err.txt)"
    assert_eq "the printed token is review" "Next: review" "${out##* · }"
    assert_file_contains "the page holds the new generation's bytes" \
        "docs/reference/demo.rst" "A third body."
    cleanup
}


main "$@"
