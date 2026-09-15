#!/usr/bin/env bash
# dogen-record-draft.sh — record a drafted page. WR-03: ledger before page.
# Inlines the gate check (folds the old verify-gate step).
#
# Usage: dogen-record-draft.sh <unit-id> <draft-file> [--model <model>]
# Exit: 0 success, 1 gate refusal, 2 bad input, 3 identical redraft (no-op), 4 evidence incomplete
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dogen-common.sh"

unit_id="${1:-}"
draft_file="${2:-}"
model=""

if [ -z "$unit_id" ] || [ -z "$draft_file" ]; then
    echo "Usage: dogen-record-draft.sh <unit-id> <draft-file> [--model <model>]" >&2
    exit 2
fi
validate_unit_id "$unit_id"
shift 2
while [ $# -gt 0 ]; do
    case "$1" in
    --model)
        model="$2"
        shift 2
        ;;
    *)
        echo "ERROR: unknown flag: $1" >&2
        exit 2
        ;;
    esac
done

unit_dir=".dogen/units/${unit_id}"
unit_file="${unit_dir}/unit.md"
ledger="${unit_dir}/ledger.md"

if [ ! -f "$unit_file" ]; then
    echo "ERROR: unit not found: ${unit_id}" >&2
    exit 2
fi
if [ ! -f "$ledger" ]; then
    # No ledger = no signoff ever recorded = gate refusal (not bad input).
    echo "ERROR: gate check failed: no signoff recorded for unit ${unit_id}" >&2
    exit 1
fi
if [ ! -f "$draft_file" ]; then
    echo "ERROR: draft file not found: ${draft_file}" >&2
    exit 2
fi

# --- Inline gate check (folds old verify-gate.sh) ---
if ! ledger_has_section "$ledger" "signoff"; then
    echo "ERROR: gate check failed: no signoff recorded for unit ${unit_id}" >&2
    exit 1
fi

current_hash=$(sha256_file "$unit_file")
signed_hash=$(ledger_section_rows "$ledger" "signoff" | tail -1 | grep -o 'plan_hash: [a-f0-9]*' | cut -d' ' -f2)

if [ "$current_hash" != "$signed_hash" ]; then
    echo "ERROR: gate check failed: plan has changed since signoff (stale plan hash)" >&2
    echo "  signed: ${signed_hash:0:12}..." >&2
    echo "  current: ${current_hash:0:12}..." >&2
    exit 1
fi
# --- End gate check ---

# --- Evidence gate (actionable units only) ---
intent=$(get_unit_field "$unit_file" "intent")
if [ "$intent" = "tutorial" ] || [ "$intent" = "how-to" ]; then
    if ! ledger_has_section "$ledger" "steps"; then
        echo "ERROR: evidence incomplete: no step plan recorded for actionable unit ${unit_id}" >&2
        exit 4
    fi
    unresolved=$(unresolved_steps "$ledger")
    if [ -n "$unresolved" ]; then
        echo "ERROR: evidence incomplete: unverified step(s) for ${unit_id}:" >&2
        echo "$unresolved" | sed 's/^/  - /' >&2
        exit 4
    fi
fi
# --- End evidence gate ---

# Read target path from unit.md frontmatter.
target=$(get_unit_field "$unit_file" "sphinx_target")
if [ -z "$target" ]; then
    echo "ERROR: sphinx_target not found in ${unit_file}" >&2
    exit 2
fi
validate_target "$target"

# Compute draft hash.
draft_sha=$(sha256_file "$draft_file")

# Identical-redraft check: compare to last generation's sha256.
if ledger_has_section "$ledger" "generations"; then
    last_gen_sha=$(ledger_section_rows "$ledger" "generations" | tail -1 | grep -o 'sha256: [a-f0-9]*' | cut -d' ' -f2)
    if [ "$last_gen_sha" = "$draft_sha" ]; then
        echo "Identical redraft (sha256: ${draft_sha:0:12}...) — no-op" >&2
        exit 3
    fi
fi

# Count steering entries (for the generation row).
steering_count=0
if ledger_has_section "$ledger" "steering"; then
    steering_count=$(ledger_section_rows "$ledger" "steering" | wc -l)
fi

# Generate a run_id: nanosecond timestamp + random suffix (collision-resistant
# even within the same second in scripted/batch runs).
run_id="$(date -u +%Y%m%d%H%M%S%N)-$(printf '%04x%04x' $((RANDOM)) $((RANDOM)))"
timestamp=$(get_timestamp)

# WR-03: write ledger row FIRST (before the page).
gen_row="${timestamp} | model: ${model} | provider: host-harness | mode: passenger | file: docs/${target} | sha256: ${draft_sha} | run_id: ${run_id} | steering_count: ${steering_count}"
ledger_append_row "$ledger" "generations" "$gen_row"

# Now write the page.
page_path="docs/${target}"
mkdir -p "$(dirname "$page_path")"
cp "$draft_file" "$page_path"

# Commit.
dogen_commit "$unit_id" "draft" "Dogen-Draft: ${draft_sha:0:12}"

echo "Recorded draft for ${unit_id} → ${page_path}"
