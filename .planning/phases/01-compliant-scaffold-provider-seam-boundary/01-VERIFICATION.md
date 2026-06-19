---
phase: 01-compliant-scaffold-provider-seam-boundary
verified: 2026-06-19T20:35:37Z
status: passed
score: 4/4
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 1: Compliant Scaffold & Provider-Seam Boundary — Verification Report

**Phase Goal:** A distributable Python package exists that is REUSE-compliant from commit 1, with the Copilot SDK confined to a single adapter module and that boundary enforced in CI — so the licensing, packaging, and provider-swappability invariants are set before any drafting logic is written.
**Verified:** 2026-06-19T20:35:37Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `reuse lint` passes on the repository — every file carries SPDX license + copyright info and `LICENSES/` is populated (LIC-01) | VERIFIED | `uvx reuse lint` run live: 67/67 files with copyright + license info, 0 bad licenses, exit 0. REUSE spec 3.3 compliant. |
| 2 | The chosen OSS license (GPL-3.0-only) is applied and recorded as an SPDX identifier in the package metadata (LIC-02) | VERIFIED | `pyproject.toml` carries `license = "GPL-3.0-only"` + `license-files`; built wheel METADATA confirms `License-Expression: GPL-3.0-only` (Metadata-Version 2.4). |
| 3 | The Copilot SDK is imported in exactly one adapter module (`src/dogen/adapters/copilot/`); the domain core has zero vendor imports (SEAM-01) | VERIFIED | `seam_check.py` run live: "OK - 4 files, no vendor imports outside adapters/copilot/", exit 0. Manual grep of `src/dogen/core/`, `src/dogen/cli/`, `src/dogen/__init__.py` confirms zero copilot/github_copilot_sdk imports. No real SDK dependency in `pyproject.toml` or `uv.lock` (D-08). |
| 4 | The CI build fails if any Copilot SDK import appears outside that adapter module — the seam check is wired as a CI gate and pre-commit hook, and D-10 demo evidence records it catching a deliberately misplaced import with the repo restored clean (SEAM-02) | VERIFIED | `ci.yml` contains `uv run python scripts/seam_check.py` as a build step; `.pre-commit-config.yaml` contains a `seam-check` local hook pointing to the same script; `seam-demo-evidence.md` captures a live run where `import copilot` in `src/dogen/core/_demo_violation.py` caused exit 1 naming the file:line, and exit 0 for the same import inside `adapters/copilot/`; demo files removed, tree clean. |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `LICENSES/GPL-3.0-only.txt` | Canonical SPDX GPL-3.0-only license text | VERIFIED | Exists, non-empty (232 lines), contains "GNU GENERAL PUBLIC LICENSE" and "Version 3". Fetched via `uvx reuse download GPL-3.0-only`, not hand-pasted. |
| `LICENSE` | Top-level license copy (Canonical policy D-05) | VERIFIED | Exists and is non-empty. |
| `.reuse/templates/canonical.jinja2` | Full Canonical notice block template reproducing coding-guide section 7 | VERIFIED | Contains: "This file is part of dogen" identity line, `copyright_lines` iteration, `spdx_expressions` iteration, full three-paragraph GPL warranty block ("This program is free software", "This program is distributed in the hope", "You should have received a copy"). |
| `.reuse/templates/canonical.jinja2.license` | Sidecar SPDX annotation for the template itself | VERIFIED | Contains `SPDX-FileCopyrightText: 2026 Canonical Ltd.` and `SPDX-License-Identifier: GPL-3.0-only`. |
| `pyproject.toml` | hatchling backend, PEP 639 `license = "GPL-3.0-only"`, `license-files`, `requires-python >= 3.12`, dev deps, ruff/ty/pytest config | VERIFIED | All fields present; no OSI Approved trove classifier; no `github-copilot-sdk` dep; full Canonical SPDX inline header. |
| `src/dogen/__init__.py` | Importable package marker with full Canonical header | VERIFIED | Exists with SPDX header and full GPL warranty block. `import dogen` succeeds. |
| `src/dogen/core/__init__.py` | Pure domain home — zero vendor imports | VERIFIED | Exists. No copilot/github_copilot_sdk imports. Full Canonical header. |
| `src/dogen/adapters/__init__.py` | Adapters namespace package marker | VERIFIED | Exists with full Canonical header. |
| `src/dogen/adapters/copilot/__init__.py` | Seam boundary — sole sanctioned import site, empty of SDK (D-08) | VERIFIED | Exists, carries SPDX header. No real SDK import (D-08). |
| `src/dogen/cli/__init__.py` | Empty CLI stub — no entrypoint, no Typer (Phase 2) | VERIFIED | Exists with full Canonical header, intentionally empty per plan. |
| `scripts/seam_check.py` | Pure-stdlib AST guardrail (`find_violations`, `main`) | VERIFIED | Pure stdlib (ast, sys, pathlib only). Handles: `ast.Import` (incl. aliased), `ast.ImportFrom` (incl. submodules), `importlib.import_module` by string constant. Scan root resolved from `__file__` location (Pitfall 4). Returns 0 clean, 1 on violation, 2 on empty scan root. Full Canonical header. |
| `tests/__init__.py` | Test package marker | VERIFIED | Exists with full Canonical header. |
| `tests/test_smoke.py` | Import smoke test | VERIFIED | Exists with full Canonical header. 3/3 pytest pass. |
| `tests/test_seam.py` | Seam pytest wrapper — single-sources `seam_check.main()` | VERIFIED | Imports `seam_check` via `sys.path.insert` and calls `seam_check.main()` directly; the same function CI and pre-commit invoke. 3/3 pytest pass. |
| `uv.lock` | Committed lockfile (D-18) | VERIFIED | Exists; no `github-copilot-sdk` or `github_copilot_sdk` reference. |
| `uv.lock.license` | SPDX sidecar for lockfile | VERIFIED | Exists with GPL-3.0-only annotation. |
| `README.md` (+ `.license`) | Project overview, scope border, dev-setup quickstart | VERIFIED | Exists with `.license` sidecar carrying full Canonical notice block. |
| `CONTRIBUTING.md` (+ `.license`) | Canonical CLA reference (D-06) | VERIFIED | Contains `https://ubuntu.com/legal/contributors/agreement` and `License granted by Canonical Limited`. `.license` sidecar exists. |
| `SECURITY.md` (+ `.license`) | Vulnerability-reporting policy | VERIFIED | Exists with sidecar. |
| `CODE_OF_CONDUCT.md` (+ `.license`) | Code of conduct | VERIFIED | Exists with sidecar. |
| `.editorconfig` | Editor defaults with inline SPDX header | VERIFIED | Exists; inline `# SPDX-License-Identifier: GPL-3.0-only` header via `--style python`. |
| `.gitignore` (+ `.license`) | Ignores build/venv/cache; does NOT ignore `uv.lock` | VERIFIED | Contains `dist/`, `__pycache__/`, does not contain `uv.lock`. `.license` sidecar exists. |
| `.github/workflows/ci.yml` | Full gate suite, 3.12+3.13 matrix, least-privilege, pinned actions | VERIFIED | Steps in order: reuse lint, ruff check, ruff format --check, ty check, seam_check.py, pytest, uv build. Matrix: ["3.12", "3.13"]. `permissions: contents: read`. `actions/checkout` and `astral-sh/setup-uv` SHA-pinned. No `--exit-zero`. Full Canonical inline header. |
| `.pre-commit-config.yaml` | Local mirror of CI gates, single-sourcing seam check | VERIFIED | Contains: `fsfe/reuse-tool` (v6.2.0), `astral-sh/ruff-pre-commit` (v0.15.18) with ruff + ruff-format hooks, local `seam-check` hook calling `python scripts/seam_check.py` with `pass_filenames: false`, local ty hook via `uv run ty check`. Full Canonical inline header. |
| `REUSE.toml` | Bulk annotation for non-source meta dirs ONLY (.planning/**, .claude/**) | VERIFIED | Covers only `.planning/**` and `.claude/**` at `precedence = "aggregate"`. Source dirs (src/, scripts/, tests/, pyproject.toml, .github/) are NOT covered — each carries per-file inline SPDX headers or .license sidecars. D-04 fully preserved. |
| `.planning/phases/01-compliant-scaffold-provider-seam-boundary/seam-demo-evidence.md` | D-10 one-time seam-guardrail demo (SC4 evidence) | VERIFIED | Records timestamp 2026-06-19T20:24:48Z, command, captured output, exit codes for: (1) `import copilot` in `src/dogen/core/_demo_violation.py` → exit 1 naming file:line; (2) same import in `adapters/copilot/` → exit 0; (3) both files removed → exit 0. `.license` sidecar exists. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_seam.py` | `scripts/seam_check.py` | `sys.path.insert` + `import seam_check` + calls `seam_check.main()` | WIRED | Single source of truth confirmed. No duplicated check logic. |
| `pyproject.toml` | `LICENSES/GPL-3.0-only.txt` | `license = "GPL-3.0-only"` + `license-files = ["LICENSE", "LICENSES/*.txt"]` → `License-Expression: GPL-3.0-only` in wheel METADATA | WIRED | Built wheel METADATA verified to contain `License-Expression: GPL-3.0-only`. |
| `.github/workflows/ci.yml` | `scripts/seam_check.py` | `uv run python scripts/seam_check.py` step (SEAM-02 CI gate) | WIRED | Step present and named "Seam check". |
| `.github/workflows/ci.yml` | `LICENSES/GPL-3.0-only.txt` | `uvx reuse lint` step enforces all files annotated (LIC-01) | WIRED | `uvx reuse lint` step present; exits 0 live. |
| `.pre-commit-config.yaml` | `scripts/seam_check.py` | local `seam-check` hook entry `python scripts/seam_check.py` | WIRED | Hook present with `pass_filenames: false`; same script as CI and pytest. |

---

### D-04 Deviation Check (REUSE.toml scope vs per-file headers)

The instruction specifically requested: verify that REUSE.toml only bulk-annotates non-source meta directories and that actual source files (src/, scripts/, tests/) still carry per-file SPDX headers.

**Finding: D-04 preserved.**

- `REUSE.toml` covers only two glob patterns: `.planning/**` and `.claude/**`, both at `precedence = "aggregate"`.
- No entry in REUSE.toml covers `src/`, `scripts/`, `tests/`, `pyproject.toml`, `.github/`, or any other source/build artifact.
- All 9 Python files across `src/dogen/`, `scripts/`, and `tests/` carry per-file inline SPDX headers with the full Canonical GPL warranty block (9/9 match confirmed by grep).
- `pyproject.toml`, `ci.yml`, `.pre-commit-config.yaml`, and `.editorconfig` each carry inline full Canonical headers.
- Hygiene `.md` files use `.license` sidecars with the full notice block (confirmed on README.md.license).

The REUSE.toml addition (plan 04, deviation #1) was necessitated by `.planning/` files being tracked by git and therefore linted by `reuse lint`. This is the REUSE spec 3.3 documented mechanism for files that "cannot or should not be annotated inline." REUSE precedence rules mean any inline header always overrides REUSE.toml — D-04's per-file policy is unaffected for all source, test, script, and CI files.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `reuse lint` passes whole-repo (LIC-01) | `uvx reuse lint` | 67/67 files, 0 bad licenses, exit 0. "Your project is compliant with version 3.3 of the REUSE Specification." | PASS |
| Seam check passes on clean tree (SEAM-01/02) | `uv run python scripts/seam_check.py` | "seam-check: OK - 4 files, no vendor imports outside adapters/copilot/", exit 0 | PASS |
| Package imports cleanly with hexagonal layout | `uv run python -c "import dogen, dogen.core, dogen.adapters.copilot, dogen.cli"` | exit 0, no output | PASS |
| pytest passes (smoke + seam tests) | `uv run pytest -q` | 3 passed, exit 0 | PASS |
| Wheel METADATA carries `License-Expression: GPL-3.0-only` (LIC-02) | `unzip -p dist/*.whl "*/METADATA" \| grep License` | `License-Expression: GPL-3.0-only`, `Metadata-Version: 2.4` | PASS |
| No SDK dependency in lockfile or pyproject | `grep github.copilot.sdk pyproject.toml uv.lock` | no output, exit 1 (not found) | PASS |
| Demo violation files absent (D-10 clean) | `test ! -e src/dogen/core/_demo_violation.py` | both demo files absent | PASS |

---

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|---------|
| LIC-01 | 01-01, 01-02, 01-03, 01-04 | Repository REUSE-compliant; every file carries SPDX info; `LICENSES/` populated; `reuse lint` passes in CI | SATISFIED | `uvx reuse lint` exits 0, 67/67 files. CI step `uvx reuse lint` wired as first gate. |
| LIC-02 | 01-01, 01-02 | GPL-3.0-only chosen, applied, recorded as SPDX identifier in package metadata | SATISFIED | `pyproject.toml license = "GPL-3.0-only"`; built wheel `License-Expression: GPL-3.0-only` (Metadata-Version 2.4). |
| SEAM-01 | 01-02 | Copilot SDK imported in exactly one adapter module; domain core has zero vendor imports | SATISFIED | No imports of `copilot`/`github_copilot_sdk` outside `adapters/copilot/`. Seam check confirms 4 files clean. No real SDK dep (D-08). |
| SEAM-02 | 01-02, 01-04 | CI guardrail fails build if Copilot SDK import appears outside adapter module | SATISFIED | CI step wired. Pre-commit hook wired. D-10 demo evidence captures exit 1 on misplaced import. `seam-demo-evidence.md` is the SC4 artifact. |

---

### Anti-Patterns Found

No debt markers (TBD, FIXME, XXX), stubs, or hardcoded empty values were found in any source file modified by this phase. The empty `__init__.py` files in `core/`, `adapters/`, `adapters/copilot/`, and `cli/` are intentional Phase-1 scaffold stubs (documented in plan 01-02 "Known Stubs" section), not data-wiring gaps. `adapters/copilot/__init__.py` being empty is the D-08 design decision (no real SDK dependency until Phase 2). These are not anti-patterns.

---

### Human Verification Required

None. All success criteria are mechanically verifiable and were verified against the live codebase. The seam-guardrail demo evidence is captured in a committed artifact rather than requiring a re-run.

---

## Gaps Summary

No gaps. All 4 success criteria from ROADMAP.md are verified against the actual codebase with live tool execution:

1. `reuse lint` passes (67/67 files, exit 0 — confirmed live).
2. GPL-3.0-only recorded in wheel METADATA as `License-Expression` (confirmed by unzipping the built wheel).
3. Seam boundary exists and is clean (seam_check.py exits 0 on live run; grep of core/cli confirms zero vendor imports).
4. Seam guardrail is a standing CI gate (ci.yml + pre-commit wired) with D-10 demo evidence captured.

The REUSE.toml addition (plan 04 deviation #1) is consistent with D-04: it bulk-annotates only `.planning/**` and `.claude/**` (non-source meta), and the REUSE precedence rules preserve per-file headers for all actual source files. This is the REUSE spec 3.3 mechanism for files that should not be annotated inline, and it achieves the LIC-01 whole-repo lint green while leaving D-04 intact.

---

_Verified: 2026-06-19T20:35:37Z_
_Verifier: Claude (gsd-verifier)_
