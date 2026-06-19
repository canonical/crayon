---
phase: 01-compliant-scaffold-provider-seam-boundary
plan: 03
subsystem: repo-hygiene
status: complete
tags: [oss-hygiene, reuse, spdx, cla, gpl-3.0-only, canonical-conventions]
dependency_graph:
  requires:
    - "canonical REUSE annotation template (.reuse/templates/canonical.jinja2) — plan 01-01"
    - "LICENSES/GPL-3.0-only.txt + top-level LICENSE — plan 01-01"
  provides:
    - "standard OSS hygiene file set (D-16): README, CONTRIBUTING, SECURITY.md, CODE_OF_CONDUCT, .editorconfig, .gitignore"
    - "CLA reference + License-granted-by-Canonical notice variant in CONTRIBUTING (D-06)"
    - "repo .gitignore covering build/venv/cache artifacts"
  affects:
    - "plan 01-04 (reuse lint CI gate counts these annotated files toward LIC-01)"
tech_stack:
  added: []
  patterns:
    - "Per-file REUSE info via plan-01 machinery: .license sidecars for .md + .gitignore; inline header for .editorconfig"
    - "reuse annotate --copyright-prefix spdx --template canonical (no literal 'Copyright' word)"
    - "INI/.editorconfig inline header via reuse --style python (# comments)"
key_files:
  created:
    - README.md
    - README.md.license
    - CONTRIBUTING.md
    - CONTRIBUTING.md.license
    - SECURITY.md
    - SECURITY.md.license
    - CODE_OF_CONDUCT.md
    - CODE_OF_CONDUCT.md.license
    - .editorconfig
    - .gitignore
    - .gitignore.license
  modified: []
decisions:
  - "All four .md hygiene files use .license sidecars (RESEARCH A4 RESOLVED — sidecar is the verified path; inline HTML-comment variant left unverified)"
  - ".gitignore annotated via sidecar (keeps the ignore file clean) rather than inline # comment"
  - ".editorconfig annotated inline via reuse --style python (# is a valid INI comment); 'ini' is not a reuse style name"
  - "sidecars carry the FULL Canonical notice block (D-04 per-file policy), not the bare two-tag form"
  - "uv.lock deliberately NOT ignored (D-18 commits it)"
metrics:
  duration_min: 3
  completed_date: 2026-06-19
requirements: [LIC-01, LIC-02]
---

# Phase 1 Plan 03: OSS Repo-Hygiene File Set Summary

Landed the standard OSS hygiene file set (D-16) with Canonical conventions, each REUSE-annotated so it counts toward the LIC-01 surface: README (scope border + uv quickstart), CONTRIBUTING (Canonical CLA + License-granted-by-Canonical notice, D-06), SECURITY.md (brief vulnerability-reporting policy), CODE_OF_CONDUCT (Contributor Covenant 2.1), .editorconfig (inline header), and .gitignore (sidecar) covering build/venv/cache artifacts.

## What Was Built

**Task 1 — README, CONTRIBUTING (CLA), SECURITY, CODE_OF_CONDUCT (commit 27a4b33)**
- `README.md` — what dogen is (agentic doc-drafting framework that drafts Sphinx-publishable docs and stops at a singular local commit), the hard scope border (no push/PR/build/publish), a uv-based dev quickstart, and pointers to AGENTS.md, the coding guide, and licensing.md.
- `CONTRIBUTING.md` — trunk-based flow + branch naming (`docpr-<ticket>-<objective>`), squash-and-merge, small-PR / two-maintainer-review norms (coding-guide §8), and an explicit reference to the Canonical CLA at `ubuntu.com/legal/contributors/agreement` plus the "License granted by Canonical Limited" notice variant for CLA-contributed files (licensing.md §3.3) — satisfies **D-06**.
- `SECURITY.md` — brief private vulnerability-reporting policy (email security@canonical.com, no public issues), no secrets, no Phase-2 SDK detail (RESEARCH Security Domain).
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1 adaptation.
- Each `.md` carries a `<file>.md.license` sidecar with the full Canonical notice block (both SPDX tags + GPL warranty paragraph).

**Task 2 — .editorconfig and .gitignore (commit 21114b4)**
- `.editorconfig` — `root = true`, utf-8, LF, final newline, trimmed trailing whitespace, 4-space Python / 2-space YAML+TOML+JSON (consistent with ruff format), Makefile tabs; carries the full Canonical header **inline** (`#` comments, applied via `reuse --style python`).
- `.gitignore` — ignores `__pycache__/`, `*.py[cod]`, `*.egg-info/`, `build/`, `dist/` (incl. the plan-02 `dist/_wheel/` scratch dir), `.venv/`/`venv/`, and tool caches (`.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.ty_cache/`, coverage). Does **not** ignore `uv.lock` (D-18).
- `.gitignore.license` sidecar with the full Canonical notice block.
- Side effect: the previously-untracked `__pycache__/` directories (from plan 02) are now ignored — `git status` is clean.

## Verification Evidence

- **Task 1 automated check passed:** all four `.md` files non-empty; `CONTRIBUTING.md` matches `CLA`/`contributor agreement`; all four `.md.license` sidecars contain `SPDX-License-Identifier: GPL-3.0-only`.
- **D-06 evidence:** `CONTRIBUTING.md` contains both `ubuntu.com/legal/contributors/agreement` and `License granted by Canonical Limited`.
- **D-17 evidence:** `test ! -e docs/conf.py && test ! -e .readthedocs.yaml` — no Sphinx/MyST/RTD files created.
- **Task 2 automated check passed:** `.editorconfig` non-empty with `SPDX-License-Identifier: GPL-3.0-only`; `.gitignore` contains `dist/` and `__pycache__`, does NOT match `^uv.lock$`; `.gitignore.license` contains the SPDX license tag.
- **reuse lint scoped check:** all six hygiene files (and their sidecars) are NOT in the "MISSING COPYRIGHT AND LICENSING INFORMATION" list; `Missing licenses: 0`. The repo-wide lint still reports non-compliant solely because `.planning/` artifacts carry no headers — that is out of scope (planning docs are never annotated), consistent with the plan 01-01 note.
- **git status clean** after both commits; no unexpected file deletions in either commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `reuse --style ini` is not a valid style name**
- **Found during:** Task 2 (annotating `.editorconfig` inline).
- **Issue:** The plan called for an "INI-style `#`" inline header; `reuse annotate --style ini` errors (`'ini' is not one of ...`). `ini` is not an accepted reuse comment style.
- **Fix:** Used `--style python`, which emits `#`-prefixed comment lines — byte-identical to the intended INI `#` header. The resulting `.editorconfig` carries the full Canonical block and passes lint.
- **Files modified:** `.editorconfig`
- **Commit:** 21114b4

No architectural changes; no other deviations. The `.md` sidecar vs inline-HTML-comment choice was already RESOLVED in RESEARCH (A4) to sidecars, which is what was used.

## Threat Surface

Matches the plan's threat model exactly; no new surface.
- **T-03-01 (Repudiation, inbound contributions) — mitigated:** CONTRIBUTING references the Canonical CLA (D-06), establishing provenance/licensing of external code, plus the License-granted-by-Canonical notice variant for CLA-contributed files.
- **T-03-02 (Info Disclosure, SECURITY.md) — accepted:** brief reporting policy only; no secrets, no internal infra detail.
- **T-03-03 (Tampering, licensing gaps) — mitigated:** every hygiene file carries REUSE info (sidecar/inline), so the plan-04 `reuse lint` gate will fail on any future un-annotated file — closing the LIC-01 surface for these files.

## Requirements Satisfied

- **LIC-01** (hygiene-file portion): every D-16 hygiene file now carries REUSE info (full Canonical notice via `.license` sidecar or inline header) and passes `reuse lint` — extending the LIC-01 surface from source (plan 02) to the non-source hygiene set. Full CI gate lands in plan 04.
- **LIC-02:** these files consume the single `GPL-3.0-only` SPDX identifier sourced from the plan-01 template/LICENSES, no divergent license string introduced.

## Handoff to Next Plans

- Plan 04 (`reuse lint` CI gate) can now count the six annotated hygiene files; the only repo-level lint gap remaining is `.planning/` (planning artifacts, out of REUSE scope for source).
- `.gitignore` is in place; future build/cache artifacts (`dist/`, `__pycache__/`, tool caches) will not pollute `git status`. `uv.lock` remains tracked (D-18).

## Self-Check: PASSED

- Files: all 11 present (README.md + sidecar, CONTRIBUTING.md + sidecar, SECURITY.md + sidecar, CODE_OF_CONDUCT.md + sidecar, .editorconfig, .gitignore + sidecar).
- Commits: 27a4b33 (Task 1), 21114b4 (Task 2) both present in git log.
