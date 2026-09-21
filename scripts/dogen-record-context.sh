#!/usr/bin/env bash
# dogen-record-context.sh — record repo-level documentation context artifacts.
# Promotes the agent-staged context artifacts into .dogen/context/, freezes a
# manifest (SHA-256 per artifact), and commits with Dogen-Phase: onboard.
#
# This is a repo-level recorder, not a per-unit gate: it produces the shared
# context (doc-style / glossary / structure) that later grounds dogen-plan. The
# skill owns the semantic judgment; this script owns the promotion, the manifest
# freeze, the no-op check, and the commit seam.
#
# Usage: dogen-record-context.sh --staging <dir> --model <model> [--force]
# Exit: 0 success, 2 bad input, 3 no-op (artifacts unchanged since last record)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dogen-common.sh"

# The enumerated set of artifacts this recorder will promote. A staged file whose
# name is not in this set is refused — the skill cannot smuggle an arbitrary write
# into .dogen/context/ through the staging dir.
RECOGNIZED_ARTIFACTS=(doc-style.md glossary.md structure.md)

staging=""
model=""
force=0

while [ $# -gt 0 ]; do
    case "$1" in
    --staging)
        staging="$2"
        shift 2
        ;;
    --model)
        model="$2"
        shift 2
        ;;
    --force)
        force=1
        shift
        ;;
    *)
        echo "ERROR: unknown flag: $1" >&2
        exit 2
        ;;
    esac
done

if [ -z "$staging" ] || [ -z "$model" ]; then
    echo "Usage: dogen-record-context.sh --staging <dir> --model <model> [--force]" >&2
    exit 2
fi

# The model lands in the manifest and the commit trailer; keep it single-line and
# free of the ledger/manifest field separator.
validate_ledger_freetext "model" "$model"

if [ ! -d "$staging" ]; then
    echo "ERROR: staging dir not found: ${staging}" >&2
    exit 2
fi

# Refuse a staging dir that escapes the repo root.
repo_root="$(pwd)"
staging_abs="$(cd "$staging" && pwd)"
case "$staging_abs" in
"$repo_root" | "$repo_root"/*) ;;
*)
    echo "ERROR: staging dir escapes the repo: ${staging}" >&2
    exit 2
    ;;
esac

is_recognized() {
    local name="$1"
    for a in "${RECOGNIZED_ARTIFACTS[@]}"; do
        [ "$name" = "$a" ] && return 0
    done
    return 1
}

# Enumerate staged regular files; refuse any that are not recognized artifacts.
present=()
for f in "$staging_abs"/*; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    if ! is_recognized "$base"; then
        echo "ERROR: unrecognized artifact in staging: ${base}" >&2
        echo "       allowed: ${RECOGNIZED_ARTIFACTS[*]}" >&2
        exit 2
    fi
    present+=("$base")
done

if [ "${#present[@]}" -eq 0 ]; then
    echo "ERROR: no recognized artifacts found in staging: ${staging}" >&2
    echo "       expected one or more of: ${RECOGNIZED_ARTIFACTS[*]}" >&2
    exit 2
fi

context_dir=".dogen/context"
manifest="${context_dir}/manifest.md"

# No-op detection: every staged artifact is byte-identical to the already
# published context file, and the published set holds nothing the staged set drops.
if [ "$force" -eq 0 ] && [ -f "$manifest" ]; then
    unchanged=1
    for base in "${present[@]}"; do
        if [ ! -f "${context_dir}/${base}" ] ||
            [ "$(sha256_file "$staging_abs/$base")" != "$(sha256_file "${context_dir}/${base}")" ]; then
            unchanged=0
            break
        fi
    done
    if [ "$unchanged" -eq 1 ]; then
        for a in "${RECOGNIZED_ARTIFACTS[@]}"; do
            if [ -f "${context_dir}/${a}" ] && ! printf '%s\n' "${present[@]}" | grep -qx "$a"; then
                unchanged=0
                break
            fi
        done
    fi
    if [ "$unchanged" -eq 1 ]; then
        echo "no-op: context artifacts unchanged since last record" >&2
        exit 3
    fi
fi

ensure_dogen_gitignore
mkdir -p "$context_dir"

# Promote each staged artifact. Destinations are the fixed whitelist names, so no
# path traversal is possible here.
for base in "${present[@]}"; do
    cp "$staging_abs/$base" "${context_dir}/${base}"
done

timestamp=$(get_timestamp)
head_commit=$(get_head_commit)
author=$(get_author)
{
    echo "# dogen context manifest"
    echo ""
    echo "generated ${timestamp} | author ${author} | model ${model} | commit ${head_commit}"
    echo ""
    echo "## artifacts"
    # Freeze the complete published set, not just this run's staged subset — a
    # partial re-stage must still yield a manifest that lists every live artifact.
    for a in "${RECOGNIZED_ARTIFACTS[@]}"; do
        [ -f "${context_dir}/${a}" ] || continue
        echo "${a} | sha256: $(sha256_file "${context_dir}/${a}")"
    done
} >"$manifest"

dogen_commit_repo "onboard" "Dogen-Model: ${model}"

echo "Recorded context artifacts: ${present[*]}"
