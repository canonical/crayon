#!/usr/bin/env bash
# run_matrix.sh — the local 3.9 / 3.12 / 3.13 interpreter matrix.
#
# Usage: bash tests/run_matrix.sh   (run from the repository root)
#
# The boundary, stated once: **uv is the interpreter FETCHER and nothing
# else.** It downloads CPython builds; it never installs a Python PACKAGE. The
# tool and both Python suites are stdlib-only (AGENTS.md forbids a dependency),
# `--no-project` keeps uv from reading or creating any project environment, and
# no `uv pip` / `uv add` / `pip install` appears anywhere in this file. CI uses
# `actions/setup-python` for the same matrix; this script is the local proof.
#
# An interpreter already present on the machine is REUSED — `uv python install`
# is idempotent and re-downloads nothing — so the 3.12 leg normally runs on the
# system interpreter with no network at all.
#
# Exit codes follow the project's 0/1/2 lint contract:
#   0  every interpreter that ran reported OK
#   1  at least one interpreter ran and failed
#   2  NO interpreter ran — a matrix that ran nothing is a vacuous pass, and
#      reporting it green is the one outcome this script must never produce
#
# An interpreter uv cannot provide prints a loud SKIP and does NOT count as a
# failure: an absent download is a fact about the machine, not about the code.
# The script still fails if any interpreter that DID run failed.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSIONS=(3.9 3.12 3.13)
SUITE="tests/test_crayon_unit.py"

ran=0
failed=0
skipped=0

cd "$REPO_ROOT" || exit 2

if ! command -v uv >/dev/null 2>&1; then
    echo "matrix: ERROR - uv is not on PATH; it is the interpreter fetcher" >&2
    echo "matrix: 0 interpreters ran, 0 failed, 0 skipped"
    exit 2
fi

# Pre-fetch the two interpreters that are not the usual system one. Present
# interpreters are reused; a failure here is not fatal, because the per-version
# loop below reports the miss as a SKIP naming the interpreter.
echo "── fetching interpreters (present ones are reused) ──"
uv python install 3.9 3.13 || true

for version in "${VERSIONS[@]}"; do
    echo ""
    echo "── python ${version} ──"
    if ! uv run --python "$version" --no-project python3 -c 'import sys; print(sys.version)'; then
        echo "!! SKIP python ${version}: uv could not provide this interpreter" >&2
        skipped=$((skipped + 1))
        continue
    fi
    ran=$((ran + 1))
    if uv run --python "$version" --no-project python3 -m unittest "$SUITE"; then
        echo "── python ${version}: OK ──"
    else
        echo "!! python ${version}: FAILED" >&2
        failed=$((failed + 1))
    fi
done

echo ""
echo "matrix: ${ran} interpreters ran, ${failed} failed, ${skipped} skipped"

if [ "$ran" -eq 0 ]; then
    echo "matrix: ERROR - no interpreter ran (vacuous pass guard)" >&2
    exit 2
fi
if [ "$failed" -ne 0 ]; then
    exit 1
fi
exit 0
