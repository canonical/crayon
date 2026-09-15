#!/usr/bin/env bash
# dogen-record-step.sh — evidence micro-gate for tutorial/how-to steps.
# Verifies evidence, updates step status, commits.
#
# Usage: dogen-record-step.sh <unit-id> <step-id> --evidence-file <path>
# Exit: 0 verified, 1 evidence incomplete, 2 bad input, 3 stale evidence
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dogen-common.sh"

unit_id="${1:-}"
step_id="${2:-}"
evidence_file=""

if [ -z "$unit_id" ] || [ -z "$step_id" ]; then
    echo "Usage: dogen-record-step.sh <unit-id> <step-id> --evidence-file <path>" >&2
    exit 2
fi
shift 2
while [ $# -gt 0 ]; do
    case "$1" in
    --evidence-file)
        evidence_file="$2"
        shift 2
        ;;
    *)
        echo "ERROR: unknown flag: $1" >&2
        exit 2
        ;;
    esac
done

validate_unit_id "$unit_id"

if [ -z "$evidence_file" ]; then
    echo "ERROR: --evidence-file is required" >&2
    exit 2
fi

unit_dir=".dogen/units/${unit_id}"
unit_file="${unit_dir}/unit.md"
ledger="${unit_dir}/ledger.md"

if [ ! -f "$unit_file" ]; then
    echo "ERROR: unit not found: ${unit_id}" >&2
    exit 2
fi
if [ ! -f "$ledger" ]; then
    echo "ERROR: ledger not found: ${ledger}" >&2
    exit 2
fi
if [ ! -f "$evidence_file" ]; then
    echo "ERROR: evidence file not found: ${evidence_file}" >&2
    exit 2
fi

# Parse evidence file (simple key: value format).
ev_field() {
    local field="$1"
    awk -F': ' "/^${field}:/{print \$2}" "$evidence_file" | head -1 | tr -d '"'
}

exit_code=$(ev_field "exit_code")
output_sha=$(ev_field "output_sha256")
verdict=$(ev_field "verdict")
mode=$(ev_field "mode")
command=$(ev_field "command")
step_text_sha=$(ev_field "step_text_sha256")
reason=$(ev_field "reason")

# Validate verdict is one of the allowed values.
case "$verdict" in
pass | fail | skipped | deviated) ;;
"")
    echo "ERROR: evidence incomplete: verdict is missing" >&2
    exit 1
    ;;
*)
    echo "ERROR: evidence incomplete: verdict must be pass/fail/skipped/deviated (got: ${verdict})" >&2
    exit 1
    ;;
esac

# Gate: required fields per verdict type.
if [ "$verdict" = "pass" ] || [ "$verdict" = "fail" ]; then
    if [ -z "$output_sha" ] || [ -z "$exit_code" ]; then
        echo "ERROR: evidence incomplete: pass/fail requires output_sha256 and exit_code" >&2
        exit 1
    fi
fi

if [ "$verdict" = "skipped" ] || [ "$verdict" = "deviated" ]; then
    if [ -z "$output_sha" ]; then
        echo "ERROR: evidence incomplete: skipped/deviated requires output_sha256" >&2
        exit 1
    fi
    if [ -z "$reason" ]; then
        echo "ERROR: evidence incomplete: skipped/deviated requires a reason" >&2
        exit 1
    fi
fi

# Require step_text_sha256 for staleness detection.
if [ -z "$step_text_sha" ]; then
    echo "ERROR: evidence incomplete: step_text_sha256 is required" >&2
    exit 1
fi

# Find the step in the ledger.
step_line=$(ledger_section_rows "$ledger" "steps" | grep "^${step_id} |" || true)
if [ -z "$step_line" ]; then
    echo "ERROR: step ${step_id} not found in ledger" >&2
    exit 2
fi

# Extract the recorded text_hash from the step row.
recorded_text_hash=$(echo "$step_line" | grep -o 'text_hash: [a-f0-9]*' | cut -d' ' -f2)

# Staleness check: evidence step_text_sha256 must match the recorded text_hash.
if [ "$step_text_sha" != "$recorded_text_hash" ]; then
    echo "ERROR: stale evidence: step text has changed since evidence was captured" >&2
    echo "  recorded: ${recorded_text_hash:0:12}..." >&2
    echo "  evidence: ${step_text_sha:0:12}..." >&2
    exit 3
fi

# Determine new status: pass/skipped/deviated → resolved; fail → stays unverified.
case "$verdict" in
pass | skipped | deviated)
    new_status="resolved"
    ;;
fail)
    new_status="unverified"
    ;;
esac

# Build the new step row.
new_row="${step_id} | text_hash: ${recorded_text_hash} | status: ${new_status} | exit_code: ${exit_code:-} | output_sha256: ${output_sha} | verdict: ${verdict} | mode: ${mode:-}"
if [ -n "$reason" ]; then
    new_row="${new_row} | reason: ${reason}"
fi
if [ -n "$command" ]; then
    new_row="${new_row} | command: ${command}"
fi

ledger_replace_step "$ledger" "$step_id" "$new_row"

dogen_commit "$unit_id" "step" "Dogen-Step: ${step_id}"

echo "Recorded evidence for ${unit_id}/${step_id} (verdict: ${verdict}, status: ${new_status})"
