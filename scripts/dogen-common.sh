#!/usr/bin/env bash
# Shared helpers for dogen scripts. Sourced by other scripts, not run directly.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Validate a unit id: reject empty, path traversal, and unsafe characters.
# Usage: validate_unit_id <id>  (exits 2 on failure)
validate_unit_id() {
    local id="$1"
    if [ -z "$id" ]; then
        echo "ERROR: unit id is empty" >&2
        exit 2
    fi
    if [[ "$id" == *..* ]] || [[ "$id" == /* ]] || [[ "$id" == */* ]]; then
        echo "ERROR: unit id contains path separators or traversal: ${id}" >&2
        exit 2
    fi
}

# Print a field from unit.md YAML frontmatter.
# Usage: get_unit_field <unit_file> <field_name>
get_unit_field() {
    local file="$1"
    local field="$2"
    awk -F': ' "/^${field}:/{print \$2}" "$file" | head -1 | tr -d '"'
}

# Compute SHA-256 of a file (portable: sha256sum on Linux, shasum on macOS).
sha256_file() {
    local file="$1"
    if command -v sha256sum &>/dev/null; then
        sha256sum "$file" | cut -d' ' -f1
    else
        shasum -a 256 "$file" | cut -d' ' -f1
    fi
}

# Compute SHA-256 of a string.
sha256_str() {
    if command -v sha256sum &>/dev/null; then
        printf '%s' "$1" | sha256sum | cut -d' ' -f1
    else
        printf '%s' "$1" | shasum -a 256 | cut -d' ' -f1
    fi
}

# Get git identity (name).
get_author() {
    git config user.name 2>/dev/null || echo "unknown"
}

# Get current ISO-8601 UTC timestamp.
get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%S+00:00"
}

# Get git HEAD commit SHA (or "none" if not a repo).
get_head_commit() {
    git rev-parse --short HEAD 2>/dev/null || echo "none"
}

# Ensure .dogen/.gitignore ignores staging/.
ensure_dogen_gitignore() {
    local gitignore=".dogen/.gitignore"
    mkdir -p .dogen
    if [ ! -f "$gitignore" ]; then
        echo "staging/" >"$gitignore"
    elif ! grep -q '^staging/' "$gitignore"; then
        echo "staging/" >>"$gitignore"
    fi
}

# Check if a ledger section exists.
# Usage: ledger_has_section <ledger_file> <section_name>
ledger_has_section() {
    local ledger="$1"
    local section="$2"
    grep -q "^## ${section}$" "$ledger"
}

# Print unresolved (unverified) step ids in the ledger's ## steps section, one per line.
# Usage: unresolved_steps <ledger_file>
unresolved_steps() {
    local ledger="$1"
    ledger_section_rows "$ledger" "steps" | grep 'status: unverified' |
        sed -E 's/^([^ ]+).*/\1/' || true
}

# Print all data rows in a ledger section (excluding header and blank lines).
# Usage: ledger_section_rows <ledger_file> <section_name>
ledger_section_rows() {
    local ledger="$1"
    local section="$2"
    awk -v section="## ${section}" '
    $0 == section { in_section=1; next }
    /^## / { in_section=0 }
    in_section && NF { print }
  ' "$ledger"
}

# Append a row to a ledger section (creates the section if missing).
# Rows are separated from their neighbours by exactly one blank line, and each
# section header is preceded by one blank line (the header itself is followed
# directly by its first row — no blank).
# Usage: ledger_append_row <ledger_file> <section_name> <row_text>
ledger_append_row() {
    local ledger="$1"
    local section="$2"
    local row="$3"
    local tmp
    tmp=$(mktemp)

    if ! ledger_has_section "$ledger" "$section"; then
        # New section: ensure a blank line, then header + first row.
        printf '\n## %s\n%s\n' "$section" "$row" >>"$ledger"
        return
    fi

    # Existing section: find the section header's line, then its last data row
    # (skipping blank lines), and insert a blank line + the new row right after
    # it — so the new row becomes the section's last row, blank-separated.
    local s_ln
    s_ln=$(grep -n "^## ${section}\$" "$ledger" | head -1 | cut -d: -f1)

    local last_ln
    last_ln=$(awk -v s="$s_ln" '
        NR > s {
            if ($0 ~ /^## /) exit
            if ($0 != "") last = NR
        }
        END { if (last == "") last = s; print last }
    ' "$ledger")

    awk -v ln="$last_ln" -v row="${row}" '
        { print }
        NR == ln { print ""; print row }
    ' "$ledger" >"$tmp"
    mv "$tmp" "$ledger"
}

# Replace a step row in the ledger (matched by step-id as literal first field).
# Usage: ledger_replace_step <ledger_file> <step_id> <new_row>
ledger_replace_step() {
    local ledger="$1"
    local step_id="$2"
    local new_row="$3"
    local tmp
    tmp=$(mktemp)
    awk -v step_id="${step_id}" -v new_row="${new_row}" '
    BEGIN { OFS=" | " }
    {
        n = split($0, parts, " | ")
        if (parts[1] == step_id) { print new_row; next }
        print $0
    }
  ' "$ledger" >"$tmp"
    mv "$tmp" "$ledger"
}

# Commit with Dogen trailers. Stages only .dogen/ and docs/ (never the whole repo).
# Usage: dogen_commit <unit_id> <phase> [extra_trailer...]
dogen_commit() {
    local unit_id="$1"
    local phase="$2"
    shift 2
    local trailers=(
        --trailer "Dogen-Unit: ${unit_id}"
        --trailer "Dogen-Phase: ${phase}"
    )
    for t in "$@"; do
        trailers+=(--trailer "$t")
    done
    git add .dogen/ 2>/dev/null || true
    [ -d docs/ ] && git add docs/ 2>/dev/null || true
    local commit_paths=(".dogen/")
    [ -d docs/ ] && commit_paths+=("docs/")
    if git diff --cached --quiet -- "${commit_paths[@]}" 2>/dev/null; then
        echo "warn: nothing to commit for phase ${phase}" >&2
        return 0
    fi
    git commit -q -m "dogen: ${phase} ${unit_id}" "${trailers[@]}" -- "${commit_paths[@]}"
    local sha
    sha=$(git rev-parse --short HEAD)
    echo "git: committed ${sha} — dogen: ${phase} ${unit_id}" >&2
}
