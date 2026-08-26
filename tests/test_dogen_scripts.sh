#!/usr/bin/env bash
# test_dogen_scripts.sh — bash test suite for the 4 dogen deterministic scripts.
#
# Usage: bash tests/test_dogen_scripts.sh
#
# Tests: dogen-signoff.sh, dogen-record-draft.sh, dogen-record-review.sh,
#        dogen-record-step.sh (plus dogen-common.sh helpers).
# Each test runs in a SUBSHELL so cwd changes can't leak into the main repo.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_SCRIPTS="$SCRIPT_DIR/../scripts"

PASS=0
FAIL=0
FAILED_TESTS=()

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        FAILED_TESTS+=("$desc")
        echo "  FAIL: $desc (expected: '$expected', got: '$actual')"
    fi
}

assert_contains() {
    local desc="$1" haystack="$2" needle="$3"
    if echo "$haystack" | grep -qF "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        FAILED_TESTS+=("$desc")
        echo "  FAIL: $desc (expected to contain: '$needle')"
    fi
}

assert_file_contains() {
    local desc="$1" file="$2" needle="$3"
    if grep -qF "$needle" "$file" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        FAILED_TESTS+=("$desc")
        echo "  FAIL: $desc (file $file expected to contain: '$needle')"
    fi
}

assert_file_not_exists() {
    local desc="$1" file="$2"
    if [ ! -e "$file" ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        FAILED_TESTS+=("$desc")
        echo "  FAIL: $desc (file $file should not exist)"
    fi
}

# Each test runs in a subshell — cwd changes cannot leak.
run_test() {
    local name="$1"
    shift
    (
        eval "$@"
    )
    local rc=$?
    if [ $rc -ne 0 ]; then
        FAIL=$((FAIL + 1))
        FAILED_TESTS+=("$name (subshell exited $rc)")
    fi
}

setup_repo() {
    TEST_DIR=$(mktemp -d)
    cd "$TEST_DIR"
    git init -q
    git config user.name "Test Author"
    git config user.email "test@example.com"
    echo "# Test source" >source.md
    git add -A
    git commit -q -m "initial"
    echo "$TEST_DIR"
}

setup_unit() {
    local unit_id="$1"
    local intent="${2:-reference}"
    mkdir -p ".dogen/units/${unit_id}"
    cat >".dogen/units/${unit_id}/unit.md" <<EOF
---
unit_id: ${unit_id}
intent: ${intent}
audience: developers
title: Test Unit
sources:
  - path: source.md
sphinx_target: ${unit_id}.md
extra_targets: []
steering_notes: ""
---

# ${unit_id}

A test unit.
EOF
}

cleanup() {
    [ -n "$TEST_DIR" ] && rm -rf "$TEST_DIR"
    TEST_DIR=""
}

# --- Tests: dogen-signoff.sh ---

test_signoff_creates_ledger_lazily() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    local rc=$?
    assert_eq "signoff creates ledger exit code" "0" "$rc"
    assert_file_contains "ledger created lazily" ".dogen/units/test-unit/ledger.md" "# dogen ledger — unit: test-unit"
    assert_file_contains "ledger has signoff" ".dogen/units/test-unit/ledger.md" "## signoff"
    assert_file_contains "ledger has plan_hash" ".dogen/units/test-unit/ledger.md" "plan_hash:"
    assert_file_contains "gitignore has staging" ".dogen/.gitignore" "staging/"
    local log
    log=$(git log --format="%B" -1)
    assert_contains "signoff commit trailer" "$log" "Dogen-Phase: signoff"
    assert_contains "commit Dogen-Unit" "$log" "Dogen-Unit: test-unit"
    cleanup
}

test_signoff_missing_unit_md() {
    setup_repo
    "$REPO_SCRIPTS/dogen-signoff.sh" "nonexistent" >/dev/null 2>&1
    local rc=$?
    assert_eq "signoff missing unit exit code" "2" "$rc"
    cleanup
}

test_signoff_double_signoff() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    local rc=$?
    assert_eq "double signoff exit code" "1" "$rc"
    cleanup
}

test_signoff_force() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" --force >/dev/null 2>&1
    local rc=$?
    assert_eq "force signoff exit code" "0" "$rc"
    local count
    count=$(grep -c 'plan_hash:' ".dogen/units/test-unit/ledger.md")
    assert_eq "two signoff rows after force" "2" "$count"
    cleanup
}

test_signoff_path_traversal() {
    setup_repo
    "$REPO_SCRIPTS/dogen-signoff.sh" "../evil" >/dev/null 2>&1
    local rc=$?
    assert_eq "path traversal rejected" "2" "$rc"
    "$REPO_SCRIPTS/dogen-signoff.sh" "foo/bar" >/dev/null 2>&1
    local rc2=$?
    assert_eq "slash in id rejected" "2" "$rc2"
    cleanup
}

# --- Tests: dogen-record-draft.sh ---

test_record_draft_happy_path() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Test Unit Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" --model "claude-sonnet-4" >/dev/null 2>&1
    local rc=$?
    assert_eq "record draft exit code" "0" "$rc"
    assert_file_contains "page written to docs" "docs/test-unit.md" "# Test Unit Draft"
    assert_file_contains "ledger has generation" ".dogen/units/test-unit/ledger.md" "## generations"
    assert_file_contains "ledger has sha256" ".dogen/units/test-unit/ledger.md" "sha256:"
    assert_file_contains "ledger has model" ".dogen/units/test-unit/ledger.md" "model: claude-sonnet-4"
    local log
    log=$(git log --format="%B" -1)
    assert_contains "draft commit trailer" "$log" "Dogen-Phase: draft"
    assert_contains "draft hash trailer" "$log" "Dogen-Draft:"
    cleanup
}

test_record_draft_gate_refusal_no_signoff() {
    setup_repo
    setup_unit "test-unit"
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "draft gate refusal (no signoff) exit code" "1" "$rc"
    assert_file_not_exists "no page on gate refusal" "docs/test-unit.md"
    cleanup
}

test_record_draft_gate_refusal_stale_plan() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    echo "## New section" >>".dogen/units/test-unit/unit.md"
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "draft gate refusal (stale plan) exit code" "1" "$rc"
    assert_file_not_exists "no page on stale plan" "docs/test-unit.md"
    cleanup
}

test_record_draft_identical() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Identical draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "identical redraft exit code" "3" "$rc"
    local count
    count=$(grep -c 'mode: passenger' ".dogen/units/test-unit/ledger.md" || true)
    assert_eq "only one generation row" "1" "$count"
    cleanup
}

test_record_draft_path_traversal() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "../evil" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "record draft path traversal rejected" "2" "$rc"
    cleanup
}

# --- Tests: evidence gate (record-draft, actionable units) ---

test_record_draft_evidence_gate_unresolved() {
    setup_repo
    setup_unit "walk-unit" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "walk-unit" >/dev/null 2>&1
    local ledger=".dogen/units/walk-unit/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: aaa111 | status: unverified" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "walk-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "actionable draft with unresolved step exit code" "4" "$rc"
    assert_file_not_exists "no page on unresolved step" "docs/walk-unit.md"
    cleanup
}

test_record_draft_evidence_gate_no_steps() {
    setup_repo
    setup_unit "walk-unit" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "walk-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "walk-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "actionable draft with no step plan exit code" "4" "$rc"
    cleanup
}

test_record_draft_evidence_gate_resolved() {
    setup_repo
    setup_unit "walk-unit" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "walk-unit" >/dev/null 2>&1
    local ledger=".dogen/units/walk-unit/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: aaa111 | status: resolved" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "walk-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "actionable draft with all steps resolved exit code" "0" "$rc"
    assert_file_contains "page written" "docs/walk-unit.md" "# Draft"
    cleanup
}

test_record_draft_reference_skips_evidence_gate() {
    setup_repo
    setup_unit "ref-unit" "reference"
    "$REPO_SCRIPTS/dogen-signoff.sh" "ref-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "ref-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    local rc=$?
    assert_eq "reference draft skips evidence gate exit code" "0" "$rc"
    cleanup
}

# --- Tests: dogen-record-review.sh ---

test_review_accept_happy_path() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft page" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-review.sh" "test-unit" --verdict accept --note "Looks good" >/dev/null 2>&1
    local rc=$?
    assert_eq "review accept exit code" "0" "$rc"
    assert_file_contains "ledger has reviews" ".dogen/units/test-unit/ledger.md" "## reviews"
    assert_file_contains "ledger has accept" ".dogen/units/test-unit/ledger.md" "verdict: accept"
    assert_file_contains "ledger has sealed" ".dogen/units/test-unit/ledger.md" "sealed:"
    local log
    log=$(git log --format="%B" -1)
    assert_contains "review commit" "$log" "Dogen-Phase: review"
    assert_contains "verdict trailer" "$log" "Dogen-Verdict: accept"
    cleanup
}

test_review_accept_no_generation() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-review.sh" "test-unit" --verdict accept --note "premature" >/dev/null 2>&1
    local rc=$?
    assert_eq "review accept no generation exit code" "1" "$rc"
    cleanup
}

test_review_fix_appends_steering() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft page" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-review.sh" "test-unit" --verdict fix --note "Fix the intro" >/dev/null 2>&1
    local rc=$?
    assert_eq "review fix exit code" "0" "$rc"
    assert_file_contains "ledger has reviews" ".dogen/units/test-unit/ledger.md" "## reviews"
    assert_file_contains "ledger has fix verdict" ".dogen/units/test-unit/ledger.md" "verdict: fix"
    assert_file_contains "ledger has steering from review" ".dogen/units/test-unit/ledger.md" "origin: review"
    assert_file_contains "steering has the note" ".dogen/units/test-unit/ledger.md" "Fix the intro"
    local log
    log=$(git log --format="%B" -1)
    assert_contains "verdict trailer" "$log" "Dogen-Verdict: fix"
    cleanup
}

test_review_fix_requires_note() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-review.sh" "test-unit" --verdict fix >/dev/null 2>&1
    local rc=$?
    assert_eq "review fix without note exit code" "2" "$rc"
    cleanup
}

test_review_invalid_verdict() {
    setup_repo
    setup_unit "test-unit"
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "test-unit" ".dogen/staging/draft.md" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-review.sh" "test-unit" --verdict reject --note "no" >/dev/null 2>&1
    local rc=$?
    assert_eq "review invalid verdict exit code" "2" "$rc"
    cleanup
}

# --- Tests: dogen-record-step.sh ---

test_record_step_happy_path() {
    setup_repo
    setup_unit "install-cli" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "install-cli" >/dev/null 2>&1
    local step_hash
    step_hash=$(printf '%s' "Run dogen --version" | sha256sum | cut -d' ' -f1)
    local ledger=".dogen/units/install-cli/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: ${step_hash} | status: unverified" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    local ev_file=".dogen/staging/ev-test.txt"
    mkdir -p .dogen/staging
    cat >"$ev_file" <<EOF
exit_code: 0
output_sha256: abc123def456
verdict: pass
mode: agent
command: dogen --version
step_text_sha256: ${step_hash}
EOF
    "$REPO_SCRIPTS/dogen-record-step.sh" "install-cli" "step-1" --evidence-file "$ev_file" >/dev/null 2>&1
    local rc=$?
    assert_eq "record step exit code" "0" "$rc"
    assert_file_contains "step resolved" "$ledger" "status: resolved"
    assert_file_contains "step verdict" "$ledger" "verdict: pass"
    assert_file_contains "step output_sha" "$ledger" "output_sha256: abc123def456"
    cleanup
}

test_record_step_fail_stays_unverified() {
    setup_repo
    setup_unit "install-cli" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "install-cli" >/dev/null 2>&1
    local step_hash
    step_hash=$(printf '%s' "Run failing cmd" | sha256sum | cut -d' ' -f1)
    local ledger=".dogen/units/install-cli/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: ${step_hash} | status: unverified" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    local ev_file=".dogen/staging/ev-fail.txt"
    mkdir -p .dogen/staging
    cat >"$ev_file" <<EOF
exit_code: 1
output_sha256: abc123
verdict: fail
mode: agent
step_text_sha256: ${step_hash}
EOF
    "$REPO_SCRIPTS/dogen-record-step.sh" "install-cli" "step-1" --evidence-file "$ev_file" >/dev/null 2>&1
    local rc=$?
    assert_eq "record step fail exit code" "0" "$rc"
    assert_file_contains "fail stays unverified" "$ledger" "status: unverified"
    assert_file_contains "has fail verdict" "$ledger" "verdict: fail"
    cleanup
}

test_record_step_stale_evidence() {
    setup_repo
    setup_unit "install-cli" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "install-cli" >/dev/null 2>&1
    local ledger=".dogen/units/install-cli/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: aaa111 | status: unverified" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    local ev_file=".dogen/staging/ev-stale.txt"
    mkdir -p .dogen/staging
    cat >"$ev_file" <<EOF
exit_code: 0
output_sha256: abc123
verdict: pass
mode: agent
step_text_sha256: bbb222
EOF
    "$REPO_SCRIPTS/dogen-record-step.sh" "install-cli" "step-1" --evidence-file "$ev_file" >/dev/null 2>&1
    local rc=$?
    assert_eq "stale evidence exit code" "3" "$rc"
    cleanup
}

test_record_step_incomplete() {
    setup_repo
    setup_unit "install-cli" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "install-cli" >/dev/null 2>&1
    local step_hash
    step_hash=$(printf '%s' "test" | sha256sum | cut -d' ' -f1)
    local ledger=".dogen/units/install-cli/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: ${step_hash} | status: unverified" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    local ev_file=".dogen/staging/ev-incomplete.txt"
    mkdir -p .dogen/staging
    cat >"$ev_file" <<EOF
verdict: pass
mode: agent
step_text_sha256: ${step_hash}
EOF
    "$REPO_SCRIPTS/dogen-record-step.sh" "install-cli" "step-1" --evidence-file "$ev_file" >/dev/null 2>&1
    local rc=$?
    assert_eq "incomplete evidence exit code" "1" "$rc"
    cleanup
}

test_record_step_missing_step_text_sha() {
    setup_repo
    setup_unit "install-cli" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "install-cli" >/dev/null 2>&1
    local step_hash
    step_hash=$(printf '%s' "test" | sha256sum | cut -d' ' -f1)
    local ledger=".dogen/units/install-cli/ledger.md"
    echo "" >>"$ledger"
    echo "## steps" >>"$ledger"
    echo "step-1 | text_hash: ${step_hash} | status: unverified" >>"$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    local ev_file=".dogen/staging/ev-nosha.txt"
    mkdir -p .dogen/staging
    cat >"$ev_file" <<EOF
exit_code: 0
output_sha256: abc123
verdict: pass
mode: agent
EOF
    "$REPO_SCRIPTS/dogen-record-step.sh" "install-cli" "step-1" --evidence-file "$ev_file" >/dev/null 2>&1
    local rc=$?
    assert_eq "missing step_text_sha256 exit code" "1" "$rc"
    cleanup
}

# --- Tests: commit trailers across the full loop ---

test_commit_trailers_full_loop() {
    setup_repo
    setup_unit "trailer-test"
    "$REPO_SCRIPTS/dogen-signoff.sh" "trailer-test" >/dev/null 2>&1
    mkdir -p .dogen/staging
    echo "# Draft" >.dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "trailer-test" ".dogen/staging/draft.md" >/dev/null 2>&1
    "$REPO_SCRIPTS/dogen-record-review.sh" "trailer-test" --verdict accept --note "ok" >/dev/null 2>&1
    local log
    log=$(git log --format="%B" --grep="Dogen-Unit")
    assert_contains "log has Dogen-Unit" "$log" "Dogen-Unit: trailer-test"
    assert_contains "log has signoff" "$log" "Dogen-Phase: signoff"
    assert_contains "log has draft" "$log" "Dogen-Phase: draft"
    assert_contains "log has review" "$log" "Dogen-Phase: review"
    cleanup
}

# --- Tests: git add isolation (not staging unrelated files) ---

test_git_add_isolation() {
    setup_repo
    setup_unit "test-unit"
    # Create an unrelated file that should NOT be committed by dogen commits
    echo "unrelated" >unrelated.txt
    git add unrelated.txt
    "$REPO_SCRIPTS/dogen-signoff.sh" "test-unit" >/dev/null 2>&1
    # The signoff commit should NOT include unrelated.txt
    local files_in_commit
    files_in_commit=$(git log --name-only --format="" -1)
    assert_contains "signoff commit includes ledger" "$files_in_commit" "ledger.md"
    # unrelated.txt should NOT be in the commit
    if echo "$files_in_commit" | grep -q "unrelated.txt"; then
        FAIL=$((FAIL + 1))
        FAILED_TESTS+=("git_add_isolation: unrelated.txt was committed")
        echo "  FAIL: unrelated.txt was committed by dogen-signoff.sh"
    else
        PASS=$((PASS + 1))
    fi
    cleanup
}

# --- Runner ---

main() {
    echo "Running dogen script tests (4 scripts)..."
    echo ""

    for test_fn in $(declare -F | awk '{print $3}' | grep '^test_'); do
        echo "→ ${test_fn}"
        "$test_fn"
    done

    echo ""
    echo "Results: ${PASS} passed, ${FAIL} failed"

    if [ "$FAIL" -gt 0 ]; then
        echo ""
        echo "Failed tests:"
        for t in "${FAILED_TESTS[@]}"; do
            echo "  - $t"
        done
        exit 1
    fi
    exit 0
}

main "$@"
