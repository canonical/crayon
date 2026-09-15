#!/usr/bin/env bash
# dogen-signoff.sh — the HITL gate act. Freezes SHA-256 of unit.md + repo HEAD.
# Lazy-creates the ledger if it doesn't exist (folds the old init-unit step).
#
# Usage: dogen-signoff.sh <unit-id> [--force]
# Exit: 0 success, 1 gate refusal (already signed), 2 bad input
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dogen-common.sh"

unit_id="${1:-}"
force=0

if [ -z "$unit_id" ]; then
    echo "Usage: dogen-signoff.sh <unit-id> [--force]" >&2
    exit 2
fi
shift
for arg in "$@"; do
    case "$arg" in
    --force) force=1 ;;
    *)
        echo "ERROR: unknown flag: ${arg}" >&2
        exit 2
        ;;
    esac
done

validate_unit_id "$unit_id"

unit_dir=".dogen/units/${unit_id}"
unit_file="${unit_dir}/unit.md"
ledger="${unit_dir}/ledger.md"

if [ ! -f "$unit_file" ]; then
    echo "ERROR: unit not found: ${unit_id} (expected ${unit_file})" >&2
    exit 2
fi

# Lazy-create the ledger if it doesn't exist (folds old init-unit step).
if [ ! -f "$ledger" ]; then
    ensure_dogen_gitignore
    cat >"$ledger" <<EOF
# dogen ledger — unit: ${unit_id}
EOF
fi

plan_hash=$(sha256_file "$unit_file")
head_commit=$(get_head_commit)
author=$(get_author)
timestamp=$(get_timestamp)

# Gate: refuse re-signoff at the same plan hash (unless --force).
if ledger_has_section "$ledger" "signoff"; then
    existing_hash=$(ledger_section_rows "$ledger" "signoff" | tail -1 | grep -o 'plan_hash: [a-f0-9]*' | cut -d' ' -f2)
    if [ "$existing_hash" = "$plan_hash" ] && [ "$force" -eq 0 ]; then
        echo "ERROR: already signed off at this plan hash (${plan_hash:0:12}...). Use --force to re-sign." >&2
        exit 1
    fi
fi

# Write the signoff row.
row="${timestamp} | author: ${author} | plan_hash: ${plan_hash} | commit: ${head_commit}"
ledger_append_row "$ledger" "signoff" "$row"

dogen_commit "$unit_id" "signoff"
echo "Signed off ${unit_id} (plan_hash: ${plan_hash:0:12}...)"
