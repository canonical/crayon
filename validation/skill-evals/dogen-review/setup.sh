#!/usr/bin/env bash
# Stand up a reviewable eval fixture in a scratch git repo, driving the real
# dogen verbs so every hash, commit stamp, and provenance record is genuine —
# nothing is hand-forged. The mock provider cannot carry seeded defects (it
# authors its own canned draft), so the host-harness --draft-file path is the
# seeding mechanism.
#
# Usage: setup.sh <fixture-name> [<scratch-dir>]
#   fixture-name  pipeline-config-seeded | pipeline-config-clean
#   scratch-dir   where to create the repo (default: a fresh mktemp -d)
#
# Requires the dogen CLI on PATH; from the dogen repo checkout, pass an
# absolute path (the script cd's away, so a bare `uv run dogen` breaks):
#   DOGEN="$PWD/.venv/bin/dogen" bash validation/skill-evals/dogen-review/setup.sh …
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE="${1:?usage: setup.sh <fixture-name> [<scratch-dir>]}"
SCRATCH="${2:-$(mktemp -d)}"
DOGEN="${DOGEN:-dogen}"
UNIT_ID=pipeline-definition

FIX_DIR="$HERE/fixtures/$FIXTURE"
[ -d "$FIX_DIR" ] || { echo "unknown fixture: $FIXTURE" >&2; exit 2; }

mkdir -p "$SCRATCH"
cd "$SCRATCH"
git init -q .
git config user.name "Eval Fixture"
git config user.email "eval@example.invalid"

# The invented-neutral product source (shared by both fixtures) + docs scaffold.
cp -R "$HERE/fixtures/src/." .
mkdir -p docs
git add -A
git commit -qm "fixture: pipeline source tree"

# Declare -> outline -> signoff -> host-harness draft, all through the CLI.
$DOGEN unit new "$UNIT_ID" \
  --intent reference \
  --audience "operators authoring pipeline definition files" \
  --title "Pipeline definition file reference" \
  --source internal/pipeline/pipeline_file.py \
  --source tests/test_pipeline_file.py \
  --target reference/config/pipeline-definition.rst \
  --notes "State every field, default, bound, and validation rule in the reader's terms." \
  --json
$DOGEN unit edit "$UNIT_ID" --body-file - --json < "$FIX_DIR/plan-body.md"
$DOGEN signoff "$UNIT_ID" --json

mkdir -p ".dogen/staging/$UNIT_ID"
cp "$FIX_DIR/draft.rst" ".dogen/staging/$UNIT_ID/handoff.rst"
HEAD_SHA=$(git rev-parse HEAD)
sed "s/HEAD_STAMP/$HEAD_SHA/" "$FIX_DIR/report.yaml" \
  > ".dogen/staging/$UNIT_ID/report.yaml"
$DOGEN draft "$UNIT_ID" \
  --draft-file ".dogen/staging/$UNIT_ID/handoff.rst" \
  --report ".dogen/staging/$UNIT_ID/report.yaml" \
  --provider host-harness --json

echo
echo "fixture ready: $SCRATCH (unit: $UNIT_ID; progress should be drafted)"
echo "run the skill under evaluation from that directory: /dogen-review"
