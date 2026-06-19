---
phase: 01-compliant-scaffold-provider-seam-boundary
plan: 02
subsystem: package-scaffold
status: complete
tags: [src-layout, hexagonal, seam, ast-guardrail, pep639, uv, hatchling, pytest]
dependency_graph:
  requires:
    - "canonical REUSE annotation template (.reuse/templates/canonical.jinja2) from plan 01"
    - "GPL-3.0-only license text (LICENSES/GPL-3.0-only.txt) + top-level LICENSE from plan 01"
  provides:
    - "importable src-layout dogen package (core/ adapters/copilot/ cli/)"
    - "scripts/seam_check.py — the runnable AST seam guardrail (SEAM-02)"
    - "committed uv.lock + uv.lock.license sidecar (D-18)"
    - "pyproject.toml with PEP 639 license = GPL-3.0-only (LIC-02)"
    - "pytest harness (smoke + seam) single-sourcing the seam check"
  affects:
    - "plan 03 (.gitignore + OSS hygiene files build on this tree)"
    - "plan 04 (CI + pre-commit wire scripts/seam_check.py and the gates; D-10 demo)"
tech_stack:
  added:
    - "hatchling (build backend)"
    - "ruff, ty, pytest, pytest-asyncio, pre-commit (dev group, locked in uv.lock)"
  patterns:
    - "Hexagonal src-layout with adapters/copilot/ as the sole sanctioned import site"
    - "Pure-stdlib AST seam guardrail (ast/sys/pathlib only) — no regex, no SDK"
    - "Single-source the seam check: pytest test imports scripts/seam_check.py"
    - "PEP 639 SPDX license string -> License-Expression in wheel METADATA"
    - "ty extra-paths to resolve a runtime-path import without duplicating logic"
key_files:
  created:
    - pyproject.toml
    - uv.lock
    - uv.lock.license
    - src/dogen/__init__.py
    - src/dogen/core/__init__.py
    - src/dogen/adapters/__init__.py
    - src/dogen/adapters/copilot/__init__.py
    - src/dogen/cli/__init__.py
    - scripts/seam_check.py
    - tests/__init__.py
    - tests/test_smoke.py
    - tests/test_seam.py
  modified: []
decisions:
  - "ty extra-paths=[scripts] so the static resolver finds the seam check that tests import at runtime — keeps a single source of truth without copying check logic into tests"
  - "Reworded the pyproject license comment to avoid the literal 'OSI Approved' string so the plan's `! grep OSI Approved` gate is unambiguous"
  - "tests/** ignore D/ANN/PLR2004 in ruff — tests don't carry the public-API docstring/annotation discipline"
metrics:
  duration_min: 6
  completed_date: 2026-06-19
requirements: [SEAM-01, SEAM-02, LIC-02]
---

# Phase 1 Plan 02: Package Scaffold & Seam Guardrail Summary

Poured the package concrete: the src-layout `dogen` package with the hexagonal
`core` / `adapters/copilot` / `cli` boundary, PEP 639 SPDX packaging metadata, a
committed `uv.lock`, a smoke + seam pytest harness, and the load-bearing piece —
a pure-stdlib AST seam guardrail (`scripts/seam_check.py`) that fails the build on
any Copilot SDK import outside the sanctioned adapter. The `adapters/copilot/`
package exists as the designated sole-importer shape but takes no real
`github-copilot-sdk` dependency (D-08). Every created file carries the full
Canonical header.

## What Was Built

**Task 1 — src-layout scaffold + PEP 639 packaging (commit 6fff8a5)**
- `src/dogen/` with `__init__.py` (`__version__ = "0.0.0"`), `core/` (pure, zero
  vendor imports), `adapters/__init__.py`, `adapters/copilot/__init__.py` (the
  empty seam boundary, D-08), and `cli/__init__.py` (empty stub — no
  `[project.scripts]`, no Typer this phase).
- `pyproject.toml`: hatchling backend; `license = "GPL-3.0-only"` +
  `license-files = ["LICENSE", "LICENSES/*.txt"]`; `requires-python = ">=3.12"`;
  dev group (ruff/ty/pytest/pytest-asyncio/pre-commit); ruff lint select
  (`E,F,I,UP,B,SIM,C901,PL,ANN,D`), numpy pydocstyle convention; ty
  `python-version = "3.12"`. No license trove classifier (PEP 639 conflict).
- `uv lock` run; `uv.lock` committed (D-18) with a `uv.lock.license` sidecar.
- All created `.py` files and `pyproject.toml` annotated with the full Canonical
  header via the plan-01 template.

**Task 2 — AST seam guardrail (commit 67459c9)**
- `scripts/seam_check.py`: pure-stdlib (`ast`/`sys`/`pathlib`) walker over
  `src/dogen` excluding `adapters/copilot/`. Flags `ast.Import` (incl. aliased),
  `ast.ImportFrom` (incl. submodules), and `importlib.import_module(...)` calls
  with a banned string constant — AST not regex (D-09). Scan root resolved from
  the script's own location (Pitfall 4). Returns 0 clean, 1 on violation
  (file:line listed), 2 on a misconfigured/empty scan root.
- Functions ≤ 60 lines, fully annotated, NumPy docstrings; ruff + ty clean.

**Task 3 — test harness + LIC-02 wheel-metadata proof (commit a26b54d)**
- `tests/test_smoke.py`: asserts `dogen` and all sub-packages import (src-layout
  wired) and the version marker is present.
- `tests/test_seam.py`: puts `scripts/` on `sys.path`, imports `seam_check`, and
  asserts `seam_check.main() == 0` — the test runs the SAME code as CI/pre-commit
  (single source, no drift).
- `uv build` produces a wheel whose `*.dist-info/METADATA` carries
  `Metadata-Version: 2.4` and `License-Expression: GPL-3.0-only` — LIC-02 / SC2
  proven end-to-end.

## Verification Evidence

- Imports: `uv run python -c "import dogen, dogen.core, dogen.adapters.copilot, dogen.cli"` exits 0.
- Seam check (clean tree): `seam-check: OK - 4 files, no vendor imports outside adapters/copilot/`, exit 0.
- Seam behaviour (8/8 via ephemeral probes, no committed fixture):
  - `import copilot` -> 1; `import copilot as c` -> 1; `from copilot.session import X` -> 1;
    `import github_copilot_sdk` -> 1; `importlib.import_module("copilot")` -> 1 (all name the file:line).
  - The same `import copilot` placed under `adapters/copilot/` -> 0 (sanctioned site).
  - Misconfigured/empty scan root -> 2 (not a vacuous 0, Pitfall 4).
  - Clean tree restored to exit 0 after each probe removed.
- `uv run pytest -q`: 3 passed.
- Full D-13 gate set green: `ruff check .`, `ruff format --check .`, `ty check`,
  `seam_check.py`, `pytest -q` all pass.
- Wheel METADATA: `License-Expression: GPL-3.0-only`, `License-File: LICENSE`,
  `License-File: LICENSES/GPL-3.0-only.txt`.
- No `github-copilot-sdk` / `github_copilot_sdk` in `pyproject.toml` or `uv.lock` (D-08).
- No license trove classifier; no `.gitignore` created (owned by plan 03).
- `reuse lint`: none of this plan's real source files appear in the
  missing-license list (remaining flags are `.planning/`/`.claude/` files owned by
  other plans, plus untracked `__pycache__/*.pyc` build artifacts).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ty check` could not resolve the `seam_check` import**
- **Found during:** Task 3.
- **Issue:** `tests/test_seam.py` imports `seam_check` via a runtime
  `sys.path.insert` (the verified single-source pattern). `ty` resolves imports
  statically and could not find `scripts/seam_check.py`, failing the D-14 type
  gate with `unresolved-import`.
- **Fix:** Added `extra-paths = ["scripts"]` under `[tool.ty.environment]` so the
  static resolver finds the module — preserving the single-source design rather
  than duplicating check logic into the test.
- **Files modified:** pyproject.toml.
- **Commit:** a26b54d.

**2. [Rule 1 - Bug] `ruff format --check` would reformat `scripts/seam_check.py`**
- **Found during:** Task 3 (running the full D-13 gate set).
- **Issue:** Manual line-wrapping in the seam check (added in Task 2 to satisfy
  E501) was not in ruff's canonical format; `ruff format --check .` — a CI gate
  per D-13 — would fail.
- **Fix:** Ran `ruff format scripts/seam_check.py` (collapsed two wraps back to
  one-liners now that em-dashes were replaced with ASCII hyphens). Re-verified
  the seam behaviour and pytest after reformat.
- **Files modified:** scripts/seam_check.py.
- **Commit:** a26b54d.

**3. [Rule 1 - Bug] Plan verify `! grep -q "OSI Approved"` tripped on a comment**
- **Found during:** Task 1.
- **Issue:** An explanatory comment in `pyproject.toml` contained the literal
  phrase `OSI Approved`, which made the plan's verification command
  (`! grep -q "OSI Approved"`) fail even though no trove classifier exists.
- **Fix:** Reworded the comment to "no license trove classifier" so the intent
  (no OSI-Approved classifier) holds and the gate is unambiguous.
- **Files modified:** pyproject.toml.
- **Commit:** 6fff8a5.

## Threat Surface

No new security-relevant surface beyond the plan's threat model.
- T-02-01 (dev-dep tampering): mitigated — versions pinned in the committed
  `uv.lock`; all dev tools are canonical Astral/pytest-dev tooling
  (legitimacy-audited in RESEARCH; no human checkpoint warranted).
- T-02-02 (seam tampering): mitigated — the AST check catches all six
  banned-import forms including aliasing and `import_module`-by-constant.
- T-02-SC (SDK supply chain): mitigated — no `github-copilot-sdk` dependency in
  Phase 1 (D-08); wheel and lockfile asserted SDK-free.
- T-02-03 (build-time code execution): accepted — hatchling build runs no
  untrusted code; the Phase-1 tools have no postinstall scripts.

## Requirements Satisfied

- **SEAM-01**: `copilot` / `github_copilot_sdk` are importable only under
  `adapters/copilot/`; `core/` has zero vendor imports — enforced by the AST check.
- **SEAM-02**: `scripts/seam_check.py` is the runnable guardrail, exercised by
  `tests/test_seam.py` (the same `main()` CI/pre-commit will run). The standing
  CI/pre-commit wiring and the one-time D-10 misplacement demo are plan 04 scope.
- **LIC-02**: the GPL-3.0-only SPDX expression is recorded in `pyproject.toml`
  and proven in the built wheel's METADATA (`License-Expression: GPL-3.0-only`).

## Handoff to Next Plans

- **Plan 03** owns `.gitignore` (must ignore `dist/`, `*.egg-info/`, `.venv/`,
  `__pycache__/`) and the OSS hygiene files (README, CONTRIBUTING, SECURITY,
  CODE_OF_CONDUCT, `.editorconfig`) — building on this importable tree.
- **Plan 04** wires `scripts/seam_check.py` into GitHub Actions + pre-commit (the
  full D-13 gate order), pins `ty`/`ruff`, and captures the one-time D-10
  misplaced-import demo as SC4 evidence.

## Known Stubs

- `src/dogen/core/__init__.py`, `adapters/__init__.py`,
  `adapters/copilot/__init__.py`, `cli/__init__.py` are intentionally empty
  package markers for Phase 1. `adapters/copilot/` is empty of the SDK by design
  (D-08); the real adapter and the CLI/Typer surface land in Phase 2. These are
  scaffold stubs, not data-wiring gaps — documented and expected.

## Self-Check: PASSED

- Files: all 12 created files present (verified via `find`).
- Commits: 6fff8a5, 67459c9, a26b54d all present in git log.
