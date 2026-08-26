#!/usr/bin/env bash
# dogen-record-review.sh — record a structured review verdict (accept/fix/redraft).
# Accept: seals page SHA-256 hashes. Fix/redraft: appends note to steering stream.
#
# Usage: dogen-record-review.sh <unit-id> --verdict accept|fix|redraft [--note <text>] [--note-file <path>]
# Exit: 0 success, 1 no generation to seal (accept only), 2 bad input
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dogen-common.sh"

unit_id="${1:-}"
verdict=""
note=""
note_file=""

if [ -z "$unit_id" ]; then
    echo "Usage: dogen-record-review.sh <unit-id> --verdict accept|fix|redraft [--note <text>] [--note-file <path>]" >&2
    exit 2
fi
shift
while [ $# -gt 0 ]; do
    case "$1" in
    --verdict)
        verdict="$2"
        shift 2
        ;;
    --note)
        note="$2"
        shift 2
        ;;
    --note-file)
        note_file="$2"
        shift 2
        if [ "$note_file" = "-" ]; then
            note=$(cat)
        elif [ -f "$note_file" ]; then
            note=$(cat "$note_file")
        else
            echo "ERROR: note file not found: ${note_file}" >&2
            exit 2
        fi
        ;;
    *)
        echo "ERROR: unknown flag: $1" >&2
        exit 2
        ;;
    esac
done

validate_unit_id "$unit_id"

if [ "$verdict" != "accept" ] && [ "$verdict" != "fix" ] && [ "$verdict" != "redraft" ]; then
    echo "ERROR: --verdict must be accept, fix, or redraft (got: ${verdict:-<empty>})" >&2
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

# Gate: at least one generation must exist.
if ! ledger_has_section "$ledger" "generations"; then
    echo "ERROR: no generation to review for unit ${unit_id}" >&2
    exit 1
fi

reviewer=$(get_author)
timestamp=$(get_timestamp)

# Build the review row.
review_row="${timestamp} | reviewer: ${reviewer} | verdict: ${verdict}"
extra_trailers=("Dogen-Verdict: ${verdict}")

if [ "$verdict" = "accept" ]; then
    # Seal page hashes: compute SHA-256 of the drafted page.
    target=$(get_unit_field "$unit_file" "sphinx_target")
    if [ -z "$target" ]; then
        echo "ERROR: sphinx_target not found in ${unit_file}" >&2
        exit 2
    fi
    page_path="docs/${target}"
    if [ ! -f "$page_path" ]; then
        echo "ERROR: draft page not found: ${page_path}" >&2
        exit 2
    fi
    sealed_hash=$(sha256_file "$page_path")
    review_row="${review_row} | sealed: ${page_path}:${sealed_hash}"
else
    # fix / redraft: append the note to the steering stream.
    if [ -z "$note" ]; then
        echo "ERROR: --note or --note-file is required for fix/redraft verdicts" >&2
        exit 2
    fi
    steering_row="${timestamp} | author: ${reviewer} | origin: review | ${note}"
    ledger_append_row "$ledger" "steering" "$steering_row"
fi

if [ -n "$note" ]; then
    note_first_line=$(echo "$note" | head -1)
    review_row="${review_row} | note: ${note_first_line}"
fi

ledger_append_row "$ledger" "reviews" "$review_row"

dogen_commit "$unit_id" "review" "${extra_trailers[@]}"

echo "Recorded review for ${unit_id} (verdict: ${verdict})"
