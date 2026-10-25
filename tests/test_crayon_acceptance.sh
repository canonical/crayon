#!/usr/bin/env bash
# test_crayon_acceptance.sh — the ported acceptance suite, A-01 … A-35.
#
# Usage: bash tests/test_crayon_acceptance.sh
#
# Every test drives the real `crayon` executable in a hermetic temp git repo:
# argparse, the lock, containment, derivation, routing, the six-step write
# protocol, the trailered pathspec-scoped commit and the post-commit check.
# Each test function runs in a SUBSHELL so `cd` cannot leak, and assertions are
# recorded through a results file because a subshell cannot write the parent's
# counters. The harness shape (run_test / assert_* / auto-discovery / the
# "Results: N passed, N failed" line) is copied from the v1.x bash suite,
# `git show 357c513:tests/test_dogen_scripts.sh`, and now lives in tests/lib.sh,
# shared with tests/test_crayon_lifecycle.sh.

set -u

# The harness is tests/lib.sh and lives there ONLY. The hermetic temp repo
# (`setup_repo` / `cleanup`), the assertion set, `crayon_unit_new`, the ledger
# readers, the five pre-commit hook fixtures, the vacuous-test guard in
# `run_test` and the TAP `main` all moved out of this file and are shared with
# tests/test_crayon_lifecycle.sh. Nothing below redefines any of them: a second
# copy is exactly how the two suites would drift apart.
#
# The 181 T-labelled bodies that used to sit above the A-series moved,
# unchanged, into tests/test_crayon_lifecycle.sh under their N-ids, and the
# fixtures both suites read state through (`derived`, `stage_draft`,
# `setup_drafted_unit`, …) moved into the shared harness with them. What is
# left below is the original reviewer's suite and nothing else, which is the
# whole point: its author opens this file and recognises it.
# shellcheck source=tests/lib.sh
. "$(dirname "$0")/lib.sh"

# --- A-01 … A-35: the reviewer's suite, ported by intent ---------------------
#
# The port source is `git show 357c513:tests/test_dogen_scripts.sh` — the
# thirty-two test functions of the v1.x bash layer, frozen in git history so the
# port does not depend on a working-tree copy, which no longer exists. Every
# function below carries a comment naming the source function it came from and
# that commit, so a reviewer can diff intent against source without leaving the
# file.
#
# What is ported is the INTENT, not the invocation. The source drove five bash
# scripts against a pipe-delimited markdown ledger; the port drives the v2.0
# verbs that replaced them against the JSONL record, and asserts the contract's
# own reason keys and exit codes (§5.7) rather than a script's message text.
# Where an assertion had to change, the comment above the function says what
# changed and why — the underlying protection, not the mechanism, is what the
# port is obliged to preserve.
#
# Three source functions split in two, because the v2.0 verb surface separates
# behaviours the bash scripts combined: ledger creation from signoff
# (A-01/A-02), the step plan from the evidence that resolves it (A-14/A-15),
# and the review verdict from the steering stream (A-19/A-20). Twenty-seven
# source functions therefore become A-01 … A-30, and the five Aug-31 regression
# tests become A-31 … A-35.

# A-01 ← test_signoff_creates_ledger_lazily (357c513), split half 1 of 2.
# In v1.x the ledger did not exist until `dogen-signoff.sh` created it, so one
# test covered both the lazy creation and the signoff row. v2.0 separates the
# two verbs: `unit new` opens the record, `signoff` (A-02) appends to it.
# Changed assertion: the source asserted `.crayon/.gitignore` carries `staging/`.
# v2.0 has no such file — the working area is kept out of git by the commit
# side instead, because every commit names explicit pathspecs and never a
# directory (§5.3). The property asserted is the same one: the staging tree is
# never tracked.
test_a01_signoff_creates_ledger_lazily() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1

    assert_file_exists "the ledger is created with the unit" \
        ".crayon/units/demo-unit/ledger.jsonl"
    assert_eq "the ledger opens with the ledger event" "ledger" \
        "$(printf '%s' "$(ledger_line demo-unit 1)" | json_field kind)"
    assert_eq "the ledger event names the unit" "demo-unit" \
        "$(printf '%s' "$(ledger_line demo-unit 1)" | json_field unit)"
    assert_eq "the ledger event names the docs root" "docs" \
        "$(printf '%s' "$(ledger_line demo-unit 1)" | json_field docs_root)"
    assert_eq "the declaration follows it" "unit-declared" \
        "$(printf '%s' "$(ledger_line demo-unit 2)" | json_field kind)"
    assert_eq "the declaration records the plan digest" "64" \
        "$(printf '%s' "$(ledger_line demo-unit 2)" | json_field unit_hash | wc -c |
            tr -d ' ' | awk '{print $1 - 1}')"

    # The v1.x `.gitignore` entry's replacement: the staging tree is untracked
    # because nothing ever adds it.
    assert_eq "the staging tree is never tracked" "" "$(git ls-files .crayon/staging)"
    assert_eq "the tracked .crayon files are exactly the record" \
        ".crayon/.gitattributes .crayon/units/demo-unit/ledger.jsonl .crayon/units/demo-unit/unit.md" \
        "$(git ls-files .crayon | tr '\n' ' ' | sed 's/ $//')"
    cleanup

    # This suite's copy of the inertness property. The fixture hooks —
    # `CRAYON_CRASH_AT`, which aborts the write protocol at a named point, and
    # `CRAYON_NOW`, which pins the recorded timestamp — are armed ONLY by
    # `CRAYON_TEST_HOOKS`, which `setup_repo` exports and nothing in a shipped
    # install ever sets. With the switch off, both are dead variables: the same
    # `unit new` runs to completion and records the real clock.
    # tests/test_crayon_lifecycle.sh asserts the same property over every crash
    # point (`test_n37_the_fixture_hooks_…`); the copy is deliberate, because a
    # single copy is one careless move away from this whole class of hook being
    # unasserted anywhere. It rides on A-01 rather than standing as its own
    # function because this file's contents are fixed at A-01 … A-35 exactly,
    # and the evidence is the same lazily created ledger the assertions above
    # have just read.
    setup_repo
    unset CRAYON_TEST_HOOKS
    CRAYON_CRASH_AT=manifest crayon_unit_new inert-unit "reference/inert.rst" \
        >/dev/null 2>&1
    assert_eq "the crash hook is inert without the switch" "0" "$?"
    assert_file_exists "the transition completed" \
        ".crayon/units/inert-unit/ledger.jsonl"
    assert_file_not_exists "and left nothing pending" \
        ".crayon/staging/inert-unit/pending"
    assert_not_contains "the deterministic timestamp is inert too" \
        "$(ledger_line inert-unit 1)" '"at":"2026-01-01T00:00:00+00:00"'
    export CRAYON_TEST_HOOKS=1
    cleanup
}

# A-02 ← test_signoff_creates_ledger_lazily (357c513), split half 2 of 2.
# Changed assertion: the source asserted the trailer `Crayon-Phase: signoff`.
# v2.0's phase token for this transition is `signed-off` (§5.3) and the ledger
# field is `plan_hash` on a `signoff` EVENT rather than a `## signoff` heading;
# the trailer pair the source cared about — which unit, which phase — is
# unchanged.
test_a02_signoff_records_the_plan_hash_and_the_trailers() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1

    "$CRAYON" signoff demo-unit >/dev/null 2>err.txt
    assert_eq "signoff creates ledger exit code" "0" "$?"
    assert_eq "the appended event is a signoff" "signoff" \
        "$(printf '%s' "$(ledger_line demo-unit 3)" | json_field kind)"
    assert_eq "ledger has plan_hash" \
        "$(sha256_of_file .crayon/units/demo-unit/unit.md)" \
        "$(printf '%s' "$(ledger_line demo-unit 3)" | json_field plan_hash)"

    local log
    log=$(git log --format="%B" -1)
    assert_contains "signoff commit trailer" "$log" "Crayon-Phase: signed-off"
    assert_contains "commit Crayon-Unit" "$log" "Crayon-Unit: demo-unit"
    assert_eq "the derived state is signed-off" "signed-off" "$(derived demo-unit state)"
    cleanup
}

# A-03 ← test_signoff_missing_unit_md (357c513).
# Intent unchanged; v2.0 names the reason (`unit_not_found`, exit 2) where the
# source could only assert the bare exit code.
test_a03_signoff_missing_unit_md() {
    setup_repo
    local head_before
    head_before=$(git rev-parse HEAD)

    "$CRAYON" signoff nonexistent >/dev/null 2>err.txt
    assert_eq "signoff missing unit exit code" "2" "$?"
    assert_json_error "signoff on an unknown unit" "err.txt" "unit_not_found"
    assert_file_not_exists "no ledger is invented for an unknown unit" \
        ".crayon/units/nonexistent/ledger.jsonl"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

# A-04 ← test_signoff_double_signoff (357c513).
# Changed assertion: the source asserted exit 1, the v1.x code for a gate
# refusal. In v2.0 a second signoff over an unchanged `unit.md` is a NO-OP, not
# a refusal — §5.7 stage d — so it exits 3 `already_signed` and the payload
# carries the existing event's seq, its commit and the current `next`, which is
# what lets a skill carry on rather than stop. The protection is the same: the
# record never grows a second identical signoff.
test_a04_signoff_double_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" signoff demo-unit >/dev/null 2>err.txt
    assert_eq "double signoff exit code" "3" "$?"
    assert_json_error "a second signoff" "err.txt" "already_signed"
    assert_eq "the no-op names the existing signoff's seq" "2" \
        "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["seq"])' err.txt)"
    assert_eq "the no-op carries the current next" "draft" "$(refusal_next err.txt)"
    assert_eq "the no-op appends no second signoff" "$ledger_before" \
        "$(ledger_digest demo-unit)"
    assert_eq "the no-op commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

# A-05 ← test_signoff_force (357c513) — PORTED AS AN INVERSION.
# The source asserted that `dogen-signoff.sh <id> --force` exits 0 and writes a
# SECOND signoff row over an unchanged plan. v2.0 exposes no `--force` flag on
# any verb: an override that bypasses a gate leaves no record of what it
# bypassed, which is the whole point of the ledger. The capability the author
# actually needed — re-signing an amended plan — is `crayon unit edit <id> …
# --re-sign`, which records the amendment AND the superseding signoff as one
# committed batch under the ordinary gates. So the port asserts the flag's
# ABSENCE and the supported path's presence.
test_a05_signoff_force_is_gone_and_re_signing_is_unit_edit_re_sign() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1

    "$CRAYON" signoff demo-unit --force >/dev/null 2>err.txt
    assert_eq "force signoff exit code" "2" "$?"
    assert_contains "signoff does not recognise --force" "$(cat err.txt)" \
        "unrecognized arguments: --force"
    "$CRAYON" unit edit demo-unit --force >/dev/null 2>err2.txt
    assert_eq "unit edit does not recognise --force either" "2" "$?"

    # The supported way to sign a second time: amend, then re-sign.
    local lines_before
    lines_before=$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')
    "$CRAYON" unit edit demo-unit --audience "Amended audience" --re-sign >/dev/null 2>err3.txt
    assert_eq "unit edit --re-sign exits 0" "0" "$?"
    assert_eq "two signoff rows after re-sign" "2" \
        "$(grep -c '"kind":"signoff"' .crayon/units/demo-unit/ledger.jsonl)"
    assert_eq "the second signoff supersedes the first" "2" \
        "$(printf '%s' "$(ledger_line demo-unit $((lines_before + 2)))" | json_field supersedes)"
    cleanup
}

# A-06 ← test_signoff_path_traversal (357c513).
# Intent unchanged. v2.0 validates the unit id against §5.6's regex at stage b,
# so both of the source's cases — a traversing id and a slashed id — refuse
# `bad_target` (exit 2) with the regex quoted back at the author.
test_a06_signoff_path_traversal() {
    setup_repo
    "$CRAYON" signoff "../evil" >/dev/null 2>err.txt
    assert_eq "path traversal rejected" "2" "$?"
    assert_json_error "a traversing unit id" "err.txt" "bad_target"
    assert_file_not_exists "nothing is created outside the repository" "../evil"

    "$CRAYON" signoff "foo/bar" >/dev/null 2>err2.txt
    assert_eq "slash in id rejected" "2" "$?"
    assert_json_error "a slashed unit id" "err2.txt" "bad_target"
    assert_file_not_exists "no nested unit directory is created" ".crayon/units/foo"
    cleanup
}

# A-07 ← test_record_draft_happy_path (357c513).
# Changed assertion: the source asserted the trailers `Dogen-Phase: draft` and
# `Dogen-Draft: <hash>`. v2.0's phase token is `drafted`, and the draft digest
# is not a trailer at all — §5.3 fixes the trailer set at four, and the digest
# of every written file lives in the `generation` event's `files[]`, where it is
# hash-chained instead of merely present in a commit message. The source's other
# three ledger assertions (sha256, model, a generation row) port unchanged.
test_a07_record_draft_happy_path() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "# Test Unit Draft\n"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        --model "claude-sonnet-4" --model-origin configured >/dev/null 2>err.txt
    assert_eq "record draft exit code" "0" "$?"
    assert_file_contains "page written to docs" "docs/reference/demo.rst" \
        "# Test Unit Draft"

    local gen
    gen=$(ledger_line demo-unit 4)
    assert_eq "ledger has generation" "generation" \
        "$(printf '%s' "$gen" | json_field kind)"
    assert_eq "ledger has sha256" \
        "reference/demo.rst $(sha256_of_file docs/reference/demo.rst) $(wc -c <docs/reference/demo.rst | tr -d ' ')" \
        "$(printf '%s' "$gen" | event_files)"
    assert_eq "ledger has model" "claude-sonnet-4" \
        "$(printf '%s' "$gen" | json_field model)"

    local log
    log=$(git log --format="%B" -1)
    assert_contains "draft commit trailer" "$log" "Crayon-Phase: drafted"
    # The v1.x `Dogen-Draft:` trailer's replacement: the digest is in the event.
    assert_not_contains "the draft digest is no longer a trailer" "$log" "Crayon-Draft:"
    assert_contains "the commit head trailer is present instead" "$log" "Crayon-Head:"
    cleanup
}

# A-08 ← test_record_draft_gate_refusal_no_signoff (357c513).
# Intent unchanged: no signoff, no page. v2.0 names the reason `no_signoff`.
test_a08_record_draft_gate_refusal_no_signoff() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "# Draft\n"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        >/dev/null 2>err.txt
    assert_eq "draft gate refusal (no signoff) exit code" "1" "$?"
    assert_json_error "drafting before any signoff" "err.txt" "no_signoff"
    assert_file_not_exists "no page on gate refusal" "docs/reference/demo.rst"
    cleanup
}

# A-09 ← test_record_draft_gate_refusal_stale_plan (357c513).
# Intent unchanged: editing `unit.md` after signing invalidates the signoff
# rather than passing silently. v2.0 names the reason `plan_stale`.
test_a09_record_draft_gate_refusal_stale_plan() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    printf '\n## New section\n' >>".crayon/units/demo-unit/unit.md"
    stage_draft demo-unit "reference/demo.rst" "# Draft\n"

    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        >/dev/null 2>err.txt
    assert_eq "draft gate refusal (stale plan) exit code" "1" "$?"
    assert_json_error "drafting over an amended plan" "err.txt" "plan_stale"
    assert_eq "the refusal routes to re_sign" "re_sign" "$(refusal_next err.txt)"
    assert_file_not_exists "no page on stale plan" "docs/reference/demo.rst"
    cleanup
}

# A-10 ← test_record_draft_identical (357c513).
# Intent unchanged: an identical redraft is a no-op and the record does not grow
# a second generation. The exit code is the same 3; v2.0 names it
# `identical_draft` and carries the existing generation's seq in the payload.
test_a10_record_draft_identical() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "# Identical draft\n"
    local source_path
    source_path=$(draft_path demo-unit reference/demo.rst)
    "$CRAYON" draft demo-unit "$source_path" >/dev/null 2>&1
    local head_before
    head_before=$(git rev-parse HEAD)

    "$CRAYON" draft demo-unit "$source_path" >/dev/null 2>err.txt
    assert_eq "identical redraft exit code" "3" "$?"
    assert_json_error "an identical redraft" "err.txt" "identical_draft"
    assert_eq "only one generation row" "1" \
        "$(grep -c '"kind":"generation"' .crayon/units/demo-unit/ledger.jsonl)"
    assert_eq "the no-op commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

# A-11 ← test_record_draft_path_traversal (357c513).
# Intent unchanged: a traversing unit id never reaches the write protocol. The
# id is validated at stage b, before any destination is computed.
test_a11_record_draft_path_traversal() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    stage_draft demo-unit "reference/demo.rst" "# Draft\n"

    "$CRAYON" draft "../evil" "$(draft_path demo-unit reference/demo.rst)" \
        >/dev/null 2>err.txt
    assert_eq "record draft path traversal rejected" "2" "$?"
    assert_json_error "a traversing unit id on draft" "err.txt" "bad_target"
    assert_file_not_exists "nothing is written outside the repository" "../evil"
    cleanup
}

# A-12 ← test_record_draft_evidence_gate_unresolved (357c513).
# Changed assertion: the source hand-appended a `## steps` row to the markdown
# ledger and asserted exit 4. In v2.0 the step plan is a recorded
# `steps-planned` event written by `plan-steps` (A-14) — no test writes ledger
# rows by hand — and the exit code is still 4, named `steps_unresolved`.
test_a12_record_draft_evidence_gate_unresolved() {
    setup_repo
    crayon_unit_new walk-unit "tutorial/walk.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff walk-unit >/dev/null 2>&1
    printf '[{"id":"step-1","text":"Run crayon --version","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>&1
    stage_draft walk-unit "tutorial/walk.rst" "# Draft\n"

    "$CRAYON" draft walk-unit "$(draft_path walk-unit tutorial/walk.rst)" \
        >/dev/null 2>err.txt
    assert_eq "actionable draft with unresolved step exit code" "4" "$?"
    assert_json_error "an unresolved step blocks the draft" "err.txt" "steps_unresolved"
    assert_contains "the refusal names the unresolved step" "$(cat err.txt)" "step-1"
    assert_file_not_exists "no page on unresolved step" "docs/tutorial/walk.rst"
    cleanup
}

# A-13 ← test_record_draft_evidence_gate_no_steps (357c513).
# Intent unchanged: an actionable unit with no step plan at all cannot draft.
# v2.0 separates this from A-12 by name — `steps_missing`, still exit 4.
test_a13_record_draft_evidence_gate_no_steps() {
    setup_repo
    crayon_unit_new walk-unit "tutorial/walk.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff walk-unit >/dev/null 2>&1
    stage_draft walk-unit "tutorial/walk.rst" "# Draft\n"

    "$CRAYON" draft walk-unit "$(draft_path walk-unit tutorial/walk.rst)" \
        >/dev/null 2>err.txt
    assert_eq "actionable draft with no step plan exit code" "4" "$?"
    assert_json_error "an actionable unit with no plan" "err.txt" "steps_missing"
    assert_eq "the refusal routes to walk" "walk" "$(refusal_next err.txt)"
    cleanup
}

# A-14 ← test_record_draft_evidence_gate_resolved (357c513), split half 1 of 2.
# The source reached "all steps resolved" by writing `step-1 | text_hash: aaa111
# | status: resolved` into the markdown ledger by hand — the state the evidence
# gate reads was typed, not earned. v2.0 splits the plan from the evidence:
# `plan-steps` records the steps and the TOOL computes each `text_hash`, so a
# digest can never be typed into the record (§5.6). This half asserts that.
test_a14_plan_steps_records_the_plan_and_the_tool_computes_the_text_hash() {
    setup_repo
    crayon_unit_new walk-unit "tutorial/walk.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff walk-unit >/dev/null 2>&1

    printf '[{"id":"step-1","text":"Run crayon --version","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>err.txt
    assert_eq "plan-steps exits 0" "0" "$?"
    local plan
    plan=$(ledger_line walk-unit 4)
    assert_eq "the appended event is the step plan" "steps-planned" \
        "$(printf '%s' "$plan" | json_field kind)"
    assert_contains "the plan carries the step id" "$plan" '"id":"step-1"'
    assert_contains "the tool computed the step's text_hash" "$plan" \
        "\"text_hash\":\"$(sha256_of_text 'Run crayon --version')\""
    assert_eq "the step is unresolved until evidence is recorded" "walk" \
        "$(derived walk-unit next)"
    cleanup
}

# A-15 ← test_record_draft_evidence_gate_resolved (357c513), split half 2 of 2.
# The source's own assertion, unchanged in intent: with every step resolved the
# draft exits 0 and the page is written. What resolves the step is now recorded
# evidence (`step`, A-24) rather than a typed `status: resolved`.
test_a15_record_draft_evidence_gate_resolved() {
    setup_repo
    crayon_unit_new walk-unit "tutorial/walk.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff walk-unit >/dev/null 2>&1
    printf '[{"id":"step-1","text":"Run crayon --version","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps walk-unit --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/walk-unit/scratch
    printf 'crayon 0.2.0\n' >.crayon/staging/walk-unit/scratch/step-1.out
    printf '{"verdict":"pass","exit_code":0,"mode":"agent","command":"crayon --version"}\n' \
        >.crayon/staging/walk-unit/scratch/step-1.json
    "$CRAYON" step walk-unit step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/walk-unit/scratch/step-1.json \
        --output-file .crayon/staging/walk-unit/scratch/step-1.out >/dev/null 2>&1
    stage_draft walk-unit "tutorial/walk.rst" "# Draft\n"

    "$CRAYON" draft walk-unit "$(draft_path walk-unit tutorial/walk.rst)" \
        >/dev/null 2>err.txt
    assert_eq "actionable draft with all steps resolved exit code" "0" "$?"
    assert_file_contains "page written" "docs/tutorial/walk.rst" "# Draft"
    assert_eq "the generation records the step plan it drafted over" "3" \
        "$(printf '%s' "$(ledger_line walk-unit 6)" | json_field steps_seq)"
    cleanup
}

# A-16 ← test_record_draft_reference_skips_evidence_gate (357c513).
# Intent unchanged: the evidence gate is for actionable intents only, so a
# reference unit drafts with no step plan at all.
test_a16_record_draft_reference_skips_evidence_gate() {
    setup_repo
    crayon_unit_new ref-unit "reference/ref.rst" >/dev/null 2>&1
    "$CRAYON" signoff ref-unit >/dev/null 2>&1
    stage_draft ref-unit "reference/ref.rst" "# Draft\n"

    "$CRAYON" draft ref-unit "$(draft_path ref-unit reference/ref.rst)" >/dev/null 2>err.txt
    assert_eq "reference draft skips evidence gate exit code" "0" "$?"
    assert_eq "no step plan was needed" "0" \
        "$(grep -c '"kind":"steps-planned"' .crayon/units/ref-unit/ledger.jsonl || true)"
    assert_file_exists "the page is written" "docs/reference/ref.rst"
    cleanup
}

# A-17 ← test_review_accept_happy_path (357c513).
# Changed assertion: the source asserted a `sealed:` field in a `## reviews`
# markdown section. v2.0 records the seal as the accept event's `files[]` — the
# complete set of sealed paths with their digests — and the derived state
# `sealed` (§5.4), which is stronger than a single string. The `verdict: accept`
# assertion and both trailers port unchanged.
test_a17_review_accept_happy_path() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    "$CRAYON" review demo-unit --verdict accept --note "Looks good" >/dev/null 2>err.txt
    assert_eq "review accept exit code" "0" "$?"
    local rev
    rev=$(ledger_line demo-unit 5)
    assert_eq "ledger has reviews" "review" "$(printf '%s' "$rev" | json_field kind)"
    assert_eq "ledger has accept" "accept" "$(printf '%s' "$rev" | json_field verdict)"
    # The `sealed:` field's replacement.
    assert_eq "ledger has sealed" \
        "reference/demo.rst $(sha256_of_file docs/reference/demo.rst)" \
        "$(printf '%s' "$rev" | edit_files)"
    assert_eq "the accept cites the generation it sealed" "3" \
        "$(printf '%s' "$rev" | json_field basis_seq)"
    assert_eq "the derived state is sealed" "sealed" "$(derived demo-unit state)"

    local log
    log=$(git log --format="%B" -1)
    assert_contains "review commit" "$log" "Crayon-Phase: reviewed"
    assert_contains "verdict trailer" "$log" "Crayon-Verdict: accept"
    cleanup
}

# A-18 ← test_review_accept_no_generation (357c513).
# Intent unchanged: there is nothing to accept before a draft exists. v2.0 names
# the reason `no_generation` and keeps exit 1.
test_a18_review_accept_no_generation() {
    setup_repo
    crayon_unit_new demo-unit "reference/demo.rst" >/dev/null 2>&1
    "$CRAYON" signoff demo-unit >/dev/null 2>&1
    local head_before
    head_before=$(git rev-parse HEAD)

    "$CRAYON" review demo-unit --verdict accept --note "premature" >/dev/null 2>err.txt
    assert_eq "review accept no generation exit code" "1" "$?"
    assert_json_error "accepting before any draft" "err.txt" "no_generation"
    assert_eq "the refusal routes to draft" "draft" "$(refusal_next err.txt)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

# A-19 ← test_review_fix_appends_steering (357c513), split half 1 of 2.
# Changed assertion: the source asserted that a `fix` verdict ALSO wrote a
# steering row with `origin: review`, because the v1.x script fused the two. In
# v2.0 the streams are separate (§5.3): `review --verdict fix` appends exactly
# one `review` event carrying the note, and the note becomes a PENDING request
# that a later accept must dispose of — a stronger guarantee than a steering row
# nothing checked. `steer` is the other half of the split (A-20).
test_a19_review_fix_records_one_verdict_and_leaves_the_request_pending() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    local lines_before
    lines_before=$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')

    "$CRAYON" review demo-unit --verdict fix --note "Fix the intro" >/dev/null 2>err.txt
    assert_eq "review fix exit code" "0" "$?"
    assert_eq "a fix verdict appends exactly one event" "$((lines_before + 1))" \
        "$(wc -l <".crayon/units/demo-unit/ledger.jsonl" | tr -d ' ')"
    local rev
    rev=$(ledger_line demo-unit $((lines_before + 1)))
    assert_eq "ledger has reviews" "review" "$(printf '%s' "$rev" | json_field kind)"
    assert_eq "ledger has fix verdict" "fix" "$(printf '%s' "$rev" | json_field verdict)"
    assert_eq "steering has the note" "Fix the intro" \
        "$(printf '%s' "$rev" | json_field note)"
    # The source's "ledger has steering from review" row: v2.0 writes no
    # steering event here; the request is pending on the review event itself.
    assert_eq "no steering event is forged by the review" "0" \
        "$(grep -c '"kind":"steering"' .crayon/units/demo-unit/ledger.jsonl || true)"
    assert_contains "the request is pending" "$("$CRAYON" show demo-unit 2>&1)" "pending"
    assert_eq "the unit routes back to draft" "draft" "$(derived demo-unit next)"

    local log
    log=$(git log --format="%B" -1)
    assert_contains "verdict trailer" "$log" "Crayon-Verdict: fix"
    cleanup
}

# A-20 ← test_review_fix_appends_steering (357c513), split half 2 of 2.
# The steering half the source folded into the review. v2.0 gives it its own
# verb and its own event, with `origin ∈ {plan, manual}` — `review` is no longer
# one of the origins, because a review verdict is recorded as a review.
test_a20_steer_is_the_separate_steering_stream() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"

    "$CRAYON" steer demo-unit --note "Fix the intro" --origin plan >/dev/null 2>err.txt
    assert_eq "steer exits 0" "0" "$?"
    local steering
    steering=$(ledger_line demo-unit 5)
    assert_eq "ledger has steering" "steering" \
        "$(printf '%s' "$steering" | json_field kind)"
    assert_eq "steering records its origin" "plan" \
        "$(printf '%s' "$steering" | json_field origin)"
    assert_eq "steering has the note" "Fix the intro" \
        "$(printf '%s' "$steering" | json_field note)"

    # `origin: review` was the v1.x value; a review is recorded as a review now.
    "$CRAYON" steer demo-unit --note "x" --origin review >/dev/null 2>err2.txt
    assert_eq "origin review is no longer a steering origin" "2" "$?"

    # What the steering is FOR: it defeats the `unsteered` gate on the redraft
    # the fix asked for. Without it the second draft is refused (§5.7 e).
    stage_draft demo-unit "reference/demo.rst" "Demo\n====\n\nA shorter intro.\n"
    "$CRAYON" draft demo-unit "$(draft_path demo-unit reference/demo.rst)" \
        >/dev/null 2>err3.txt
    assert_eq "the steering makes the next draft steerable" "0" "$?"
    assert_eq "the steered redraft is not unsteered" "False" \
        "$(printf '%s' "$(ledger_line demo-unit 6)" | json_field unsteered)"
    cleanup
}

# A-21 ← test_ledger_blank_line_separation (357c513) — PORTED TO THE PROPERTY
# THAT REPLACED IT.
# The source asserted a layout property of the MARKDOWN ledger: no two adjacent
# non-blank lines are both data rows, because a row that ran into its neighbour
# could not be parsed back out. A JSON-lines record has no such property to
# assert — and no such failure mode. The property that replaced it, and that the
# chain depends on, is the one asserted here: exactly one canonical JSON object
# per line, every line terminated by exactly one newline, no blank lines
# anywhere, and the seq sequence contiguous from zero. Canonical means
# `sort_keys` with no spacing — the same bytes the chain digest is taken over,
# so a line that is merely *valid* JSON but not canonical would break the
# chain silently.
test_a21_ledger_blank_line_separation() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    # Two fix verdicts, as the source did, so the record carries several rows.
    "$CRAYON" review demo-unit --verdict fix --note "Fix A" >/dev/null 2>&1
    "$CRAYON" steer demo-unit --note "and shorten it" --origin manual >/dev/null 2>&1

    local report
    report=$(python3 -c '
import json, sys
raw = open(sys.argv[1], "rb").read()
text = raw.decode("utf-8")
problems = []
if not raw.endswith(b"\n"):
    problems.append("no trailing newline")
if b"\n\n" in raw:
    problems.append("a blank line")
rows = text.split("\n")[:-1]
seqs = []
for number, row in enumerate(rows, start=1):
    if not row.strip():
        problems.append("line %d is blank" % number)
        continue
    event = json.loads(row)
    if row != json.dumps(event, sort_keys=True, separators=(",", ":")):
        problems.append("line %d is not canonical" % number)
    seqs.append(event["seq"])
if seqs != list(range(len(seqs))):
    problems.append("seqs are not contiguous from zero: %r" % seqs)
print("%d\t%s" % (len(rows), ", ".join(problems)))
' ".crayon/units/demo-unit/ledger.jsonl")
    assert_eq "no adjacent non-blank data rows" "" "${report#*$'\t'}"
    assert_eq "the record really did grow several rows" "6" "${report%%$'\t'*}"
    assert_eq "the chain over those lines is intact" "[]" "$(chain_problems demo-unit)"
    cleanup
}

# A-22 ← test_review_fix_requires_note (357c513).
# Intent and exit code unchanged: a fix verdict that does not say what should
# change is refused. v2.0 names the reason `note_required` (§5.7 e).
test_a22_review_fix_requires_note() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    local ledger_before head_before
    ledger_before=$(ledger_digest demo-unit)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" review demo-unit --verdict fix >/dev/null 2>err.txt
    assert_eq "review fix without note exit code" "2" "$?"
    assert_json_error "a fix with no note" "err.txt" "note_required"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

# A-23 ← test_review_invalid_verdict (357c513).
# Intent and exit code unchanged: a verdict outside the contract's set is
# refused. v2.0 refuses it at argument parsing and names the three it does
# accept, so the author is told what to type rather than only that they were
# wrong.
test_a23_review_invalid_verdict() {
    setup_repo
    setup_drafted_unit demo-unit "reference/demo.rst"
    local ledger_before
    ledger_before=$(ledger_digest demo-unit)

    "$CRAYON" review demo-unit --verdict reject --note "no" >/dev/null 2>err.txt
    assert_eq "review invalid verdict exit code" "2" "$?"
    # argparse quotes each choice on some Python versions, but not on 3.14.
    local choices
    choices=$(python3 -c '
import json, re, sys
detail = json.load(sys.stdin)["detail"]
match = re.search(r"choose from (.*)\)$", detail)
print(" ".join(re.findall(r"[a-z]+", match.group(1))) if match else "")
' <err.txt)
    assert_eq "the refusal names exactly the three verdicts" \
        "accept fix redraft" "$choices"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest demo-unit)"
    cleanup
}

# A-24 ← test_record_step_happy_path (357c513).
# Changed assertion: the source's evidence file carried `output_sha256` and
# `step_text_sha256` as typed text, and asserted them back out of the ledger. In
# v2.0 digests are never typed (§5.6) — the tool hashes the bytes it copied and
# takes the text hash from the step plan — so the port passes the OUTPUT and
# asserts the tool computed the same digest the fixture would have typed. The
# source's three ledger assertions (resolved, verdict, output digest) survive.
test_a24_record_step_happy_path() {
    setup_repo
    crayon_unit_new install-cli "tutorial/install-cli.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff install-cli >/dev/null 2>&1
    printf '[{"id":"step-1","text":"Run crayon --version","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps install-cli --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/install-cli/scratch
    printf 'crayon 0.2.0\n' >.crayon/staging/install-cli/scratch/step-1.out
    printf '{"verdict":"pass","exit_code":0,"mode":"agent","command":"crayon --version"}\n' \
        >.crayon/staging/install-cli/scratch/step-1.json

    "$CRAYON" step install-cli step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/install-cli/scratch/step-1.json \
        --output-file .crayon/staging/install-cli/scratch/step-1.out >/dev/null 2>err.txt
    assert_eq "record step exit code" "0" "$?"
    local recorded
    recorded=$(ledger_line install-cli 5)
    assert_eq "the appended event is the step record" "step-recorded" \
        "$(printf '%s' "$recorded" | json_field kind)"
    assert_eq "step verdict" "pass" "$(printf '%s' "$recorded" | json_field verdict)"
    assert_eq "step output_sha" "$(sha256_of_text 'crayon 0.2.0
')" "$(printf '%s' "$recorded" | json_field output_sha256)"
    assert_eq "the text hash comes from the plan, not the evidence file" \
        "$(sha256_of_text 'Run crayon --version')" \
        "$(printf '%s' "$recorded" | json_field text_hash)"
    # The source's "step resolved" assertion, read through the real derivation
    # and through the surface the author sees.
    assert_eq "step resolved" "true" "$(derived install-cli steps_resolved)"
    assert_contains "the author is told nothing is outstanding" \
        "$("$CRAYON" show install-cli 2>&1)" "unresolved 0"
    assert_eq "a resolved plan lets the unit draft" "draft" "$(derived install-cli next)"
    cleanup
}

# A-25 ← test_record_step_fail_stays_unverified (357c513).
# Intent unchanged, and it is the one the contract states outright: `fail` never
# resolves (§5.4). The step is still RECORDED — exit 0 — so the failure is on
# the record rather than lost; it simply does not count as evidence.
test_a25_record_step_fail_stays_unverified() {
    setup_repo
    crayon_unit_new install-cli "tutorial/install-cli.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff install-cli >/dev/null 2>&1
    printf '[{"id":"step-1","text":"Run failing cmd","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps install-cli --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/install-cli/scratch
    printf 'boom\n' >.crayon/staging/install-cli/scratch/step-1.out
    printf '{"verdict":"fail","exit_code":1,"mode":"agent","command":"false"}\n' \
        >.crayon/staging/install-cli/scratch/step-1.json

    "$CRAYON" step install-cli step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/install-cli/scratch/step-1.json \
        --output-file .crayon/staging/install-cli/scratch/step-1.out >/dev/null 2>err.txt
    assert_eq "record step fail exit code" "0" "$?"
    assert_eq "has fail verdict" "fail" \
        "$(printf '%s' "$(ledger_line install-cli 5)" | json_field verdict)"
    assert_eq "fail stays unverified" "false" "$(derived install-cli steps_resolved)"
    assert_contains "the author is told which step is outstanding" \
        "$("$CRAYON" show install-cli 2>&1)" "unresolved 1: step-1"

    # And the unresolved step still blocks the draft (A-12's gate).
    stage_draft install-cli "tutorial/install-cli.rst" "# Draft\n"
    "$CRAYON" draft install-cli "$(draft_path install-cli tutorial/install-cli.rst)" \
        >/dev/null 2>err2.txt
    assert_eq "a failed step is not evidence" "4" "$?"
    assert_json_error "a failed step leaves the draft blocked" "err2.txt" "steps_unresolved"
    cleanup
}

# A-26 ← test_record_step_stale_evidence (357c513).
# Changed assertion: the source made evidence stale by typing a
# `step_text_sha256` that disagreed with the plan's `text_hash`, and asserted
# exit 3. Digests are not typed in v2.0, so staleness cannot be expressed that
# way — the tool takes the text hash from the plan the evidence names. The same
# condition is reached the way it actually happens: the step plan is superseded
# by a newer one, and evidence captured against the old plan is refused
# `evidence_stale`. The exit code moves 3 → 4, the contract's code for the
# evidence family (§5.7).
test_a26_record_step_stale_evidence() {
    setup_repo
    crayon_unit_new install-cli "tutorial/install-cli.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff install-cli >/dev/null 2>&1
    printf '[{"id":"step-1","text":"Run crayon --version","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps install-cli --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/install-cli/scratch
    printf 'out\n' >.crayon/staging/install-cli/scratch/step-1.out
    printf '{"verdict":"pass","exit_code":0,"mode":"agent"}\n' \
        >.crayon/staging/install-cli/scratch/step-1.json
    # The plan the evidence was captured against is superseded.
    printf '[{"id":"step-1","text":"Run crayon version","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps install-cli --steps-file - >/dev/null 2>&1
    local ledger_before
    ledger_before=$(ledger_digest install-cli)

    "$CRAYON" step install-cli step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/install-cli/scratch/step-1.json \
        --output-file .crayon/staging/install-cli/scratch/step-1.out >/dev/null 2>err.txt
    assert_eq "stale evidence exit code" "4" "$?"
    assert_json_error "evidence against a superseded plan" "err.txt" "evidence_stale"
    assert_contains "the refusal names the current plan's seq" "$(cat err.txt)" \
        "--steps-seq 4"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest install-cli)"
    cleanup
}

# A-27 ← test_record_step_incomplete (357c513).
# Intent unchanged: evidence that is not a complete claim is refused and nothing
# is recorded. The source's file omitted `exit_code` and `output_sha256`; the
# port omits `exit_code`, the only one of the two that is still an author's to
# supply. Exit moves 1 → 4, the evidence family's code.
test_a27_record_step_incomplete() {
    setup_repo
    crayon_unit_new install-cli "tutorial/install-cli.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff install-cli >/dev/null 2>&1
    printf '[{"id":"step-1","text":"test","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps install-cli --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/install-cli/scratch
    printf 'out\n' >.crayon/staging/install-cli/scratch/step-1.out
    printf '{"verdict":"pass","mode":"agent"}\n' \
        >.crayon/staging/install-cli/scratch/step-1.json
    local ledger_before head_before
    ledger_before=$(ledger_digest install-cli)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" step install-cli step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/install-cli/scratch/step-1.json \
        --output-file .crayon/staging/install-cli/scratch/step-1.out >/dev/null 2>err.txt
    assert_eq "incomplete evidence exit code" "4" "$?"
    assert_json_error "evidence with no exit code" "err.txt" "evidence_incomplete"
    assert_contains "the refusal names the missing field" "$(cat err.txt)" "exit_code"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest install-cli)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    cleanup
}

# A-28 ← test_record_step_missing_step_text_sha (357c513) — PORTED AS AN
# INVERSION.
# The source asserted that evidence WITHOUT `step_text_sha256` is refused,
# because the v1.x script had no other way to tie the captured bytes to the step
# text the author had read. In v2.0 that field is FORBIDDEN, not required
# (§5.6): the evidence file is exactly `{verdict, exit_code, mode, command,
# reason}` and digests are never typed, because a digest an author can type is a
# digest an author can get wrong or forge. The tool takes the text hash from the
# plan the evidence names. The port therefore inverts the assertion — typing the
# field is what is refused now — and keeps the protection the source was after:
# evidence can never claim a step text it was not captured against.
test_a28_record_step_missing_step_text_sha() {
    setup_repo
    crayon_unit_new install-cli "tutorial/install-cli.rst" --intent tutorial >/dev/null 2>&1
    "$CRAYON" signoff install-cli >/dev/null 2>&1
    printf '[{"id":"step-1","text":"test","mode":"agent","stateful":false}]' |
        "$CRAYON" plan-steps install-cli --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/install-cli/scratch
    printf 'out\n' >.crayon/staging/install-cli/scratch/step-1.out
    printf '{"verdict":"pass","exit_code":0,"mode":"agent","step_text_sha256":"%s"}\n' \
        "$(sha256_of_text 'test')" >.crayon/staging/install-cli/scratch/step-1.json
    local ledger_before
    ledger_before=$(ledger_digest install-cli)

    "$CRAYON" step install-cli step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/install-cli/scratch/step-1.json \
        --output-file .crayon/staging/install-cli/scratch/step-1.out >/dev/null 2>err.txt
    assert_eq "missing step_text_sha256 exit code" "4" "$?"
    assert_json_error "a typed step_text_sha256" "err.txt" "evidence_incomplete"
    assert_contains "the refusal names the key it will not take" "$(cat err.txt)" \
        "step_text_sha256"
    assert_contains "the refusal says why" "$(cat err.txt)" "digests are never typed"
    assert_eq "the refusal appends nothing" "$ledger_before" "$(ledger_digest install-cli)"

    # The same evidence WITHOUT the typed digest is accepted, and the tool
    # supplies the text hash itself — so the refusal above is about the typing,
    # not about the step.
    printf '{"verdict":"pass","exit_code":0,"mode":"agent"}\n' \
        >.crayon/staging/install-cli/scratch/step-1.json
    "$CRAYON" step install-cli step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/install-cli/scratch/step-1.json \
        --output-file .crayon/staging/install-cli/scratch/step-1.out >/dev/null 2>err2.txt
    assert_eq "untyped evidence is accepted" "0" "$?"
    assert_eq "the tool supplied the text hash" "$(sha256_of_text 'test')" \
        "$(printf '%s' "$(ledger_line install-cli 5)" | json_field text_hash)"
    cleanup
}

# A-29 ← test_commit_trailers_full_loop (357c513).
# Changed assertion: the phase TOKENS moved. v1.x wrote `signoff` / `draft` /
# `review`; v2.0 writes the completed-transition tense — `signed-off`,
# `drafted`, `reviewed` (§5.3) — and fixes the trailer set at four, plus
# `Crayon-Verdict` on a review. `Crayon-Unit` is unchanged, and the property the
# source was really asserting is: every transition of a unit is findable in the
# log by that one trailer.
test_a29_commit_trailers_full_loop() {
    setup_repo
    setup_drafted_unit trailer-test "reference/trailer.rst"
    "$CRAYON" review trailer-test --verdict accept --note "ok" >/dev/null 2>&1

    local log
    log=$(git log --format="%B" --grep="Crayon-Unit")
    assert_contains "log has Crayon-Unit" "$log" "Crayon-Unit: trailer-test"
    assert_contains "log has signoff" "$log" "Crayon-Phase: signed-off"
    assert_contains "log has draft" "$log" "Crayon-Phase: drafted"
    assert_contains "log has review" "$log" "Crayon-Phase: reviewed"

    # The four trailers §5.3 fixes, plus the review's fifth.
    local last
    last=$(git log --format="%B" -1)
    assert_contains "Crayon-Unit on the review commit" "$last" "Crayon-Unit: trailer-test"
    assert_contains "Crayon-Phase on the review commit" "$last" "Crayon-Phase: reviewed"
    assert_contains "Crayon-Seq on the review commit" "$last" "Crayon-Seq:"
    assert_contains "Crayon-Head on the review commit" "$last" "Crayon-Head:"
    assert_contains "Crayon-Verdict on the review commit" "$last" "Crayon-Verdict: accept"
    cleanup
}

# A-30 ← test_git_add_isolation (357c513).
# Intent unchanged, and it is audit defect 4: a crayon commit names its own
# pathspecs and sweeps nothing else in. The source staged an unrelated file and
# asserted it did not land in the signoff commit; the port does the same and
# additionally asserts the file is STILL staged afterwards — the tool neither
# committed the author's work nor un-staged it.
test_a30_git_add_isolation() {
    setup_repo
    crayon_unit_new test-unit "reference/test.rst" >/dev/null 2>&1
    # An unrelated file that should NOT be committed by crayon commits.
    printf 'unrelated\n' >unrelated.txt
    git add unrelated.txt

    "$CRAYON" signoff test-unit >/dev/null 2>&1
    local files_in_commit
    files_in_commit=$(git show --name-only --format= HEAD)
    assert_contains "signoff commit includes ledger" "$files_in_commit" \
        ".crayon/units/test-unit/ledger.jsonl"
    assert_eq "signoff commit names exactly one path" "1" \
        "$(printf '%s\n' "$files_in_commit" | grep -c .)"
    assert_not_contains "unrelated.txt was not committed by crayon signoff" \
        "$files_in_commit" "unrelated.txt"
    assert_contains "the author's staged file is left staged" \
        "$(git status --short)" "A  unrelated.txt"
    cleanup
}

# --- A-31 … A-35: the five Aug-31 regression tests ---------------------------
#
# These five are the tests the reviewer added in the v1 review for the three holes they
# closed in the v1.x bash layer — two path-traversal cases in record-draft, one
# in record-review accept, the ledger note delimiter, and the `unresolved_steps`
# substring false positive. The README credits those fixes, so each function
# below says which of the five it is: a reviewer looking for them should find
# them by name.

# A-31 ← test_record_draft_rejects_target_traversal (357c513).
# One of the five Aug-31 regressions (sphinx_target path traversal, issues
# #1/#2). Intent unchanged: a target that escapes the docs root never has
# anything written to it. v2.0 refuses it two layers earlier than the source
# could — at declaration, by §5.6's target rule — so the port asserts the
# declaration refusal AND, with the escaping target forged straight into the
# record past every input check, that the write protocol still refuses and the
# host file is untouched.
test_a31_record_draft_rejects_target_traversal() {
    setup_repo
    local escape="/tmp/crayon_test_escape_$$.md"
    rm -f "$escape"

    crayon_unit_new evil-draft "../../../../tmp/crayon_test_escape_$$.md" >/dev/null 2>err.txt
    assert_eq "record-draft rejects target traversal (exit 2)" "2" "$?"
    assert_json_error "a traversing target at declaration" "err.txt" "bad_target"
    assert_file_not_exists "record-draft did not escape docs/" "$escape"

    # Forged past declaration: the signoff's targets are rewritten directly in
    # the ledger, which is the only way a traversing target can exist at all.
    local outside relative
    outside=$(mktemp -d)
    printf 'HOST FILE\n' >"$outside/victim.md"
    crayon_unit_new esc-unit "reference/esc.rst" >/dev/null 2>&1
    "$CRAYON" signoff esc-unit >/dev/null 2>&1
    relative=$(forge_escaping_target esc-unit "$outside/victim.md")
    assert_contains "the forged target really does traverse out" "$relative" ".."

    stage_draft esc-unit "reference/esc.rst" "PWNED\n"
    "$CRAYON" draft esc-unit ".crayon/staging/esc-unit/draft/$relative" >/dev/null 2>err2.txt
    assert_eq "a forged traversing target is still refused" "2" "$?"
    assert_json_error "a draft source that escapes staging" "err2.txt" "bad_draft_path"
    assert_eq "the host file is untouched" "HOST FILE" "$(cat "$outside/victim.md")"

    rm -rf "$outside"
    rm -f "$escape"
    cleanup
}

# A-32 ← test_record_draft_rejects_absolute_target (357c513).
# One of the five Aug-31 regressions. Intent unchanged: an absolute
# `sphinx_target` never becomes a write destination. v2.0 refuses it on every
# route into the record — declaration, amendment, and a hand-edited `unit.md`
# read back at signoff — and the port walks all three, because the source could
# only reach the last of them.
test_a32_record_draft_rejects_absolute_target() {
    setup_repo
    local escape="/tmp/crayon_test_abs_$$.md"
    rm -f "$escape"

    crayon_unit_new evil-abs "$escape" >/dev/null 2>err.txt
    assert_eq "record-draft rejects absolute target (exit 2)" "2" "$?"
    assert_json_error "an absolute target at declaration" "err.txt" "bad_target"
    assert_contains "the refusal says targets are docs-relative" "$(cat err.txt)" \
        "targets are docs-relative"

    crayon_unit_new abs-unit "reference/abs.rst" >/dev/null 2>&1
    "$CRAYON" unit edit abs-unit --target "$escape" >/dev/null 2>err2.txt
    assert_eq "an absolute target on amendment is refused" "2" "$?"
    assert_json_error "an absolute target at unit edit" "err2.txt" "bad_target"

    # The source's own route: the target is written into unit.md by hand.
    python3 -c '
import re, sys
path, target = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(
    re.sub(r"^  - .*$", "  - \"%s\"" % target, text, count=1, flags=re.M))
' .crayon/units/abs-unit/unit.md "$escape"
    "$CRAYON" signoff abs-unit >/dev/null 2>err3.txt
    assert_eq "a hand-written absolute target is refused at signoff" "2" "$?"
    assert_json_error "an absolute target in unit.md" "err3.txt" "bad_target"
    assert_file_not_exists "record-draft did not write absolute path" "$escape"

    rm -f "$escape"
    cleanup
}

# A-33 ← test_record_review_accept_rejects_target_traversal (357c513).
# One of the five Aug-31 regressions. Intent unchanged, and this is the sharpest
# of the three: the source corrupted the target AFTER a legitimate draft, so the
# escaping path reached the accept path rather than the draft path, and asserted
# that no sealed digest naming a path outside `docs/` was written. v2.0 refuses
# it as `ledger_corrupt` (exit 6) — a recorded path that escapes the docs root is
# a corrupt RECORD, not bad input, because no supported command could have put it
# there.
test_a33_record_review_accept_rejects_target_traversal() {
    setup_repo
    local outside relative digest ledger_before head_before
    outside=$(mktemp -d)
    printf 'HOST FILE\n' >"$outside/victim.md"
    digest=$(sha256_of_text 'HOST FILE
')
    setup_drafted_unit review-evil "reference/review-evil.rst"
    # Corrupt the target after a legit draft, then attempt accept.
    relative=$(forge_escaping_target review-evil "$outside/victim.md")
    assert_contains "the forged target really does traverse out" "$relative" ".."
    ledger_before=$(ledger_digest review-evil)
    head_before=$(git rev-parse HEAD)

    "$CRAYON" review review-evil --verdict accept --note "seal it" >/dev/null 2>err.txt
    assert_eq "record-review accept rejects target traversal (exit 6)" "6" "$?"
    assert_json_error "accepting an escaping recorded path" "err.txt" "ledger_corrupt"
    # The ledger must not contain a sealed digest pointing outside docs/.
    assert_eq "record-review accept sealed no escaping path" "0" \
        "$(grep -c -- "$digest" .crayon/units/review-evil/ledger.jsonl || true)"
    assert_eq "the refusal appends nothing" "$ledger_before" \
        "$(ledger_digest review-evil)"
    assert_eq "the refusal commits nothing" "$head_before" "$(git rev-parse HEAD)"
    assert_eq "the host file is untouched" "HOST FILE" "$(cat "$outside/victim.md")"

    rm -rf "$outside"
    cleanup
}

# A-34 ← test_record_review_note_rejects_pipe (357c513) — PORTED AS AN
# INVERSION. One of the five Aug-31 regressions (ledger row integrity, note
# delimiter injection, issue #3).
#
# The old assertion was exit 2 on a pipe. The new assertion is that no field was
# forged. Both defend the same thing; the mechanism changed.
#
# In v1.x the ledger was pipe-delimited, so `|` in a note was a field separator
# and a note carrying `| verdict: accept | sealed: …` could write a verdict the
# reviewer never gave. Refusing the character was the right fix for that format.
# In v2.0 the record is JSON, `|` and newlines are ordinary characters in a note
# (§5.6 records this as a stated behaviour change), and the forgery is
# structurally impossible rather than merely refused. So the port records the
# source's exact injection string — pipes and a newline — and asserts the three
# things that actually matter: the verb exits 0, the stored note is
# byte-identical to what was passed, and the event carries exactly the fields
# §5.3 lists for a fix review and no others.
test_a34_record_review_note_rejects_pipe() {
    # The property asserted in place of the refusal: no field is forged.
    setup_repo
    setup_drafted_unit note-pipe "reference/note-pipe.rst"
    local note='bad | verdict: accept | sealed: docs/note-pipe.md:deadbeef
a second line'

    "$CRAYON" review note-pipe --verdict fix --note "$note" >/dev/null 2>err.txt
    assert_eq "a pipe in a note is ordinary text (exit 0)" "0" "$?"
    local rev
    rev=$(ledger_line note-pipe 5)
    assert_eq "the stored note is byte-identical to the input" "$note" \
        "$(printf '%s' "$rev" | json_field note)"
    # No field was forged: the event has exactly the keys the contract lists for
    # a fix review — the envelope plus {verdict, generation_seq, note}. A forged
    # `verdict: accept` or `sealed:` would have to appear as a KEY to do harm.
    assert_eq "the event carries no field the contract does not list" \
        "actor at commit contract generation_seq kind note prev seq tool_version verdict" \
        "$(printf '%s' "$rev" |
            python3 -c 'import json,sys; print(" ".join(sorted(json.loads(sys.stdin.read()))))')"
    assert_eq "the recorded verdict is the one the reviewer gave" "fix" \
        "$(printf '%s' "$rev" | json_field verdict)"
    assert_eq "no accept verdict leaked into the ledger" "0" \
        "$(grep -c '"verdict":"accept"' .crayon/units/note-pipe/ledger.jsonl || true)"
    assert_eq "the unit is not sealed" "reviewed" "$(derived note-pipe state)"
    assert_eq "the chain over the injected note is intact" "[]" \
        "$(chain_problems note-pipe)"
    cleanup
}

# A-35 ← test_unresolved_steps_no_substring_false_positive (357c513).
# One of the five Aug-31 regressions (`unresolved_steps` substring robustness).
# Intent unchanged: prose that happens to contain the words of a status must not
# be read as that status. v1.x grepped the ledger text, so a resolved step whose
# reason mentioned "status: unverified" was reported unresolved; v2.0 derives
# step status from the `verdict` FIELD of a `step-recorded` event (§5.4), so the
# class of bug is gone by construction. The port proves it with the same shape of
# fixture: a step that IS resolved, whose reason text names every unresolved
# status it can.
test_a35_unresolved_steps_no_substring_false_positive() {
    setup_repo
    crayon_unit_new steps-fp "how-to/steps-fp.rst" --intent how-to >/dev/null 2>&1
    "$CRAYON" signoff steps-fp >/dev/null 2>&1
    printf '[{"id":"step-1","text":"Publish the result","mode":"ta","stateful":true}]' |
        "$CRAYON" plan-steps steps-fp --steps-file - >/dev/null 2>&1
    mkdir -p .crayon/staging/steps-fp/scratch
    # A resolved step whose reason text literally contains the old status words.
    printf '{"verdict":"skipped","exit_code":0,"mode":"ta","reason":"note about status: unverified and unresolved step(s): step-1 earlier"}\n' \
        >.crayon/staging/steps-fp/scratch/step-1.json

    "$CRAYON" step steps-fp step-1 --steps-seq 3 \
        --evidence-file .crayon/staging/steps-fp/scratch/step-1.json >/dev/null 2>err.txt
    assert_eq "a skipped step with a reason exits 0" "0" "$?"
    assert_file_contains "the reason text really does carry the status words" \
        ".crayon/units/steps-fp/ledger.jsonl" "status: unverified"
    assert_eq "unresolved_steps ignores substring in reason" "true" \
        "$(derived steps-fp steps_resolved)"
    assert_contains "the author is told nothing is outstanding" \
        "$("$CRAYON" show steps-fp 2>&1)" "unresolved 0"
    assert_eq "the unit routes onward, not back to walk" "draft" \
        "$(derived steps-fp next)"

    # The gate agrees with the derivation: the draft is not blocked.
    stage_draft steps-fp "how-to/steps-fp.rst" "# Draft\n"
    "$CRAYON" draft steps-fp "$(draft_path steps-fp how-to/steps-fp.rst)" >/dev/null 2>err2.txt
    assert_eq "a resolved step does not block the draft" "0" "$?"
    assert_file_exists "the page is written" "docs/how-to/steps-fp.rst"
    cleanup
}


# A-38 — the `context` verbs, end to end through the executable. New in this
# series (A-36 is retired, A-37 is the install smoke): a skill that holds no
# write tool hands the tool each artefact's text through `context stage`, and
# `context record` is the one repo-level transition — one commit, no unit.
test_a38_context_verbs_stage_record_and_show_end_to_end() {
    setup_repo
    local rc
    printf '# Style\n' | "$CRAYON" context stage doc-style.md --body-file - >/dev/null 2>&1
    printf '# Glossary\n' | "$CRAYON" context stage glossary.md --body-file - >/dev/null 2>&1
    printf '# Structure\n' | "$CRAYON" context stage structure.md --body-file - >/dev/null 2>&1
    "$CRAYON" context record --model m --model-origin skill >out.txt 2>err.txt
    rc=$?
    assert_eq "context record exits 0" "0" "$rc"
    assert_contains "the response routes plan" "$(cat out.txt)" "Next: plan"
    assert_file_exists "doc-style.md is published" ".crayon/context/doc-style.md"
    assert_file_exists "the manifest is published" ".crayon/context/manifest.json"
    assert_contains "the commit carries the context phase" \
        "$(git log -1 --format=%B)" "Crayon-Phase: context-recorded"
    assert_not_contains "the commit names no unit" "$(git log -1 --format=%B)" "Crayon-Unit"
    "$CRAYON" context record >/dev/null 2>err.txt
    rc=$?
    assert_eq "a second record with nothing staged exits 2" "2" "$rc"
    assert_json_error "the refusal is bad_target" "err.txt" "bad_target"
    assert_contains "show reports the three as present" \
        "$("$CRAYON" context show 2>&1)" "3 of 5 artefact(s) present"
    cleanup
}


main "$@"
