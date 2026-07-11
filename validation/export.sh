#!/usr/bin/env sh
# validation/export.sh <harness> [SRC|-]
# Writes a raw transcript VERBATIM to validation/SESSION-<harness>.md.
# Raw, never distilled (D-07) — fixes round-3's fidelity gap (claude distilled
# ~1400 lines vs raw ~20k). Harness-agnostic: NO per-harness export recipes.
set -eu
harness="${1:?usage: export.sh <harness> [src|-]}"
src="${2:--}"                                       # default: stdin
dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"  # this script's own dir
out="$dir/SESSION-${harness}.md"                    # canonical name by construction
if [ "$src" = "-" ]; then cat > "$out"; else cat -- "$src" > "$out"; fi
echo "wrote $out ($(wc -l < "$out") lines)"
