#!/usr/bin/env sh
# validation/sync.sh
# One-directional, idempotent overwrite mirror of the kit files from this repo's
# validation/ (the single source of truth) into the smoke-docs-1 mirror (D-02).
#
# Copies EXACTLY the three kit files (score.py, rubric.md, export.sh) — nothing
# else. It only overwrites; it never compares. Refresh assets and captures are
# never synced by this script. Overwrite + re-runnable = idempotent.
#
# NON-ATOMIC (WR-08): the mid-loop `cp` sequence is not transactional. Under
# `set -eu`, a failure on a later file (permissions, disk-full) aborts with the
# earlier files already overwritten, leaving the mirror in a mixed-version state.
# Low risk (three small local files); re-run once the cause is fixed to converge.
#
# HUMAN-RUN (D-01): running this is NOT part of phase execution and lands zero
# commits in any sibling repo. From dogen-mvp-1/validation/ a human runs `sh sync.sh`.
set -eu

# Resolve this script's own dir (robust to the caller's CWD; Pitfall 6).
src="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Default mirror: dogen-mvp-1 and DOCPR-2845 are siblings under ~/Documents/.
# DOGEN_SYNC_DST is a TEST SEAM only — it does not change default behaviour.
dst="${DOGEN_SYNC_DST:-$src/../../DOCPR-2845/smoke-docs-1/validation}"

# Loud guard before any write (T-11-09).
[ -d "$dst" ] || { echo "mirror not found: $dst" >&2; exit 1; }

# Copy exactly the three kit files, fixed names, no globs, option-injection safe.
for f in score.py rubric.md export.sh; do
  cp -- "$src/$f" "$dst/$f"
done

echo "synced score.py, rubric.md, export.sh -> $dst"
