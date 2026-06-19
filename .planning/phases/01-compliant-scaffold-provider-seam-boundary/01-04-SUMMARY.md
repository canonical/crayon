---
phase: 01-compliant-scaffold-provider-seam-boundary
plan: 04
subsystem: ci-quality-gates
status: complete
tags: [github-actions, pre-commit, reuse, spdx, seam, d-10-demo, ci-gates, supply-chain]
dependency_graph:
  requires:
    - "scripts/seam_check.py — the runnable AST seam guardrail (plan 01-02)"
    - "committed uv.lock + pyproject.toml dev group (plan 01-02, D-18)"
    - "LICENSES/GPL-3.0-only.txt + .reuse/templates/canonical.jinja2 (plan 01-01)"
    - "REUSE-annotated source + hygiene files (plans 01-02, 01-03)"
  provides:
    - ".github/workflows/ci.yml — the standing commit-1 CI gate suite (D-13), 3.12+3.13 matrix"
    - ".pre-commit-config.yaml — local mirror of the CI gates, single-sourcing the seam check"
    - "REUSE.toml — bulk annotation for non-source meta so whole-repo reuse lint exits 0 (LIC-01)"
    - "seam-demo-evidence.md — captured D-10 one-time seam-guardrail demo (SC4 evidence)"
  affects:
    - "Phase 2 (every future commit is gated by this CI/pre-commit suite; import-linter is the named seam upgrade)"
tech_stack:
  added:
    - "GitHub Actions (actions/checkout v5.0.0, astral-sh/setup-uv v8.2.0 — SHA-pinned)"
    - "pre-commit hooks: fsfe/reuse-tool v6.2.0, astral-sh/ruff-pre-commit v0.15.18, local seam-check + ty"
    - "REUSE.toml (REUSE spec 3.3 bulk annotation for meta dirs)"
  patterns:
    - "Single-source the seam check across CI step, pre-commit hook, and pytest (no drift)"
    - "uvx reuse in CI + matching pre-commit rev = one resolved reuse version (no action drift)"
    - "First-party GitHub Actions only, pinned to commit SHA (supply-chain hardening)"
    - "ty as a plain hard gate (no gate-silencing flag); documented continue-on-error beta fallback that never swaps the checker"
    - "REUSE-IgnoreStart/End HTML comments to stop reuse misparsing SPDX-tag-quoting prose in planning docs"
key_files:
  created:
    - .github/workflows/ci.yml
    - .pre-commit-config.yaml
    - REUSE.toml
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/seam-demo-evidence.md
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/seam-demo-evidence.md.license
  modified:
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/01-01-SUMMARY.md
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/01-03-PLAN.md
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/01-03-SUMMARY.md
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/01-04-PLAN.md
    - .planning/phases/01-compliant-scaffold-provider-seam-boundary/01-RESEARCH.md
decisions:
  - "actions/checkout pinned to v5.0.0 (08c6903) and astral-sh/setup-uv to v8.2.0 (fac544c) — current majors resolved live via gh, SHA-pinned for supply-chain (T-04-01)"
  - "REUSE.toml bulk-annotates .planning/** and .claude/** (non-source meta) so whole-repo reuse lint is green; per-file inline headers on real source still win by REUSE precedence (D-04 preserved)"
  - "Wrapped SPDX-tag-quoting prose in 5 prior planning docs with REUSE-IgnoreStart/End HTML comments — reuse's own documented mechanism for false-positive tags; HTML comments render invisibly"
  - "Reworded the ty-step comment to avoid the literal 'exit-zero' token so the plan's `! grep exit-zero` gate is unambiguous (same class as plan 02's 'OSI Approved' fix)"
metrics:
  duration_min: 14
  completed_date: 2026-06-19
requirements: [SEAM-02, LIC-01]
---
<!-- REUSE-IgnoreStart -->


# Phase 1 Plan 04: CI Quality Gates & Seam-Guardrail Demo Summary

Wired the commit-1 quality gates together and proved them green end-to-end. A
GitHub Actions workflow runs the full gate suite in order — `reuse lint` → `ruff
check` → `ruff format --check` → `ty check` → seam AST check → `pytest` → `uv
build` — on a 3.12 + 3.13 matrix with least-privilege permissions and SHA-pinned
first-party actions; a `.pre-commit-config.yaml` mirrors the gates for local DX,
single-sourcing `scripts/seam_check.py`. This wave closes **LIC-01** (whole-repo
`uvx reuse lint` exits 0 — 66/66 files carry SPDX info) and operationalizes
**SEAM-02** (the seam check is a standing build gate). The one-time **D-10**
demo is captured as **SC4 evidence**: the guardrail observed catching a
deliberately-misplaced `import copilot`, after which the repo was restored clean
and green — no committed failing fixture.

## What Was Built

**Task 1 — GitHub Actions CI gate suite (commit 3b8b6de)**
- `.github/workflows/ci.yml`: triggers on push + pull_request; top-level
  least-privilege `permissions: contents: read`; no secrets (default token only).
- Matrix over `python-version: ["3.12", "3.13"]` (D-12), `fail-fast: false`.
- Steps in the exact D-13 order: checkout → setup-uv → `uv sync --frozen` (D-18)
  → `uvx reuse lint` (LIC-01) → `uv run ruff check .` → `uv run ruff format
  --check .` → `uv run ty check` (D-14 hard gate) → `uv run python
  scripts/seam_check.py` (SEAM-02) → `uv run pytest -q` → `uv build` (LIC-02).
- First-party actions only, pinned to commit SHA (supply-chain, T-04-01):
  `actions/checkout@08c6903…` (v5.0.0), `astral-sh/setup-uv@fac544c…` (v8.2.0) —
  current majors resolved live via `gh api` at execution time (A1).
- The ty step is a plain `ty check` (no gate-silencing flag, D-14); an inline
  comment documents the beta fallback (temporary `continue-on-error` + tracked
  issue, NEVER a checker swap).
- Full Canonical inline REUSE header via the plan-01 template.

**Task 2 — pre-commit mirror + whole-repo LIC-01 green (commit f92a64a)**
- `.pre-commit-config.yaml`: `fsfe/reuse-tool` `rev: v6.2.0` (matches the uvx
  reuse version — no drift); `astral-sh/ruff-pre-commit` `rev: v0.15.18` (matches
  the locked ruff, A2) with `ruff` + `ruff-format`; a `local` `seam-check` hook
  running `python scripts/seam_check.py` with `pass_filenames: false` (the SAME
  script CI and pytest run); a `local` `ty` hook via `uv run ty check` (no
  published stable hook yet, A3). Full Canonical inline header.
- `REUSE.toml`: bulk-annotates non-source meta (`.planning/**`, `.claude/**`)
  with the GPL-3.0-only SPDX expression so every tracked file carries REUSE info,
  while per-file inline headers on real source win by REUSE precedence (D-04
  preserved). Carries its own SPDX header.
- `uv run pre-commit run --all-files` exits 0 (all five hooks pass).

**Task 3 — D-10 seam demo (SC4 evidence) + LIC-01 standing (commit b9bbe2b)**
- Performed the one-time manual demo: created `src/dogen/core/_demo_violation.py`
  (`import copilot`) → seam check exit 1 naming `file:line`; placed the same
  import at `src/dogen/adapters/copilot/_demo_allowed.py` → exit 0 (sanctioned
  site). Captured both runs (timestamp, command, stderr/stdout, exit codes) into
  `seam-demo-evidence.md`.
- Removed both demo files; final seam check exits 0 — tree clean, no committed
  failing fixture (D-10 trade-off honored).
- `uvx reuse lint` exits 0 across the whole repo (66/66 files). Evidence file
  carries REUSE info via a `.license` sidecar.

## Verification Evidence

- **Task 1:** `ci.yml` present; contains `reuse lint`, `ruff format --check`, `ty
  check`, `seam_check.py`, `pytest`, `uv build`, `3.13`, `permissions`, the SPDX
  header; does NOT contain `exit-zero`. PASS.
- **Task 2:** `.pre-commit-config.yaml` contains `fsfe/reuse-tool`,
  `ruff-pre-commit`, `ruff-format`, `seam-check`, `seam_check.py`, `ty check`,
  the SPDX header; `pre-commit run --all-files` exits 0 (reuse / ruff /
  ruff-format / seam-check / ty all Passed). PASS.
- **Task 3:** `seam-demo-evidence.md` non-empty, records exit codes; demo file
  absent; `seam_check.py` exits 0; `uvx reuse lint` exits 0 (66/66). PASS.
- **Full D-13 gate suite green locally:** reuse lint, ruff check, ruff format
  --check, ty check, seam check all OK; `pytest -q` → 3 passed.
- **Supply-chain:** only `actions/checkout` + `astral-sh/setup-uv`, both SHA-pinned;
  no secrets; least-privilege permissions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Whole-repo `reuse lint` failed on committed `.planning/` meta**
- **Found during:** Task 2 (running `pre-commit run --all-files`).
- **Issue:** `.planning/` (44 tracked files, `commit_docs: true`) and
  `.claude/CLAUDE.md` are committed and therefore linted by reuse. They carried no
  REUSE info (37 "missing copyright/licensing" files), so both the CI `uvx reuse
  lint` gate and the pre-commit reuse hook exited 1 — the plan's "whole-repo reuse
  lint exits 0" success criterion (LIC-01) could not be met. Prior summaries
  (01-02, 01-03) treated `.planning/` as out-of-REUSE-scope meta, but the plan-04
  CI gate runs unscoped, so the conflict had to be resolved for CI to be green.
- **Fix:** Added a `REUSE.toml` (REUSE spec 3.3) that bulk-annotates `.planning/**`
  and `.claude/**` with the GPL-3.0-only SPDX expression at `precedence =
  "aggregate"`. This is the REUSE-blessed mechanism for files that are not
  distributable source and should not carry the per-file inline notice; per-file
  inline headers on real source still win by REUSE precedence, so D-04 (per-file
  full notice for source) is preserved. Result: 65/65 files carry copyright +
  license info.
- **Files modified:** REUSE.toml (created).
- **Commit:** f92a64a.

**2. [Rule 3 - Blocking] reuse misparsed SPDX-tag-quoting prose in planning docs**
- **Found during:** Task 2 (after the REUSE.toml fix, 10 "Invalid SPDX License
  Expressions" remained).
- **Issue:** Five prior planning artifacts (01-01-SUMMARY, 01-03-PLAN,
  01-03-SUMMARY, 01-04-PLAN, 01-RESEARCH) quote `SPDX-License-Identifier:
  GPL-3.0-only` inside prose, verify commands, and the Jinja2 template example.
  reuse parses any line containing the tag as a real license declaration and
  flagged them as invalid expressions, keeping `reuse lint` (and the CI gate) red.
- **Fix:** Wrapped each offending file's body in REUSE-Ignore-Start /
  REUSE-Ignore-End HTML comments — reuse's own documented mechanism for
  false-positive tags ("put it between the Ignore-Start and Ignore-End markers").
  Markers are placed AFTER the YAML frontmatter (verified frontmatter still
  parses) and render invisibly in Markdown, so the artifacts' content is
  unchanged. Result: 0 invalid expressions; `uvx reuse lint` exits 0.
- **Files modified:** the five `.planning/.../*.md` files listed above.
- **Commit:** f92a64a.

**3. [Rule 1 - Bug] Plan verify `! grep -q "exit-zero"` tripped on the doc comment**
- **Found during:** Task 1.
- **Issue:** The ty step's explanatory comment said "Do NOT add --exit-zero",
  which made the plan's verification (`! grep -q "exit-zero"`) fail even though
  the flag is not used. Same class as plan 02's "OSI Approved" comment.
- **Fix:** Reworded the comment to "Do NOT pass the gate-silencing flag that
  forces a zero exit" — preserves the warning, drops the literal token, makes the
  gate unambiguous. The ty step remains a plain `ty check`.
- **Files modified:** .github/workflows/ci.yml.
- **Commit:** 3b8b6de.

No architectural changes (Rule 4) were required: the REUSE-scope resolution
followed the standing decision (planning meta out of per-file scope) via REUSE's
own bulk + ignore mechanisms, so no checkpoint was warranted.

## Threat Surface

Matches the plan's threat model; no new surface.
- **T-04-01 (Tampering/EoP, third-party Actions) — mitigated:** only
  `actions/checkout` + `astral-sh/setup-uv`, both pinned to commit SHA; no other
  `uses:` entries.
- **T-04-02 (EoP, token scope) — mitigated:** top-level `permissions: contents:
  read`; no secrets added.
- **T-04-03 (Tampering, seam bypass) — mitigated:** the AST seam check runs on
  every CI build and as a pre-commit hook; the D-10 demo proves it catches a real
  misplacement (SC4). Residual: dynamic string-constructed imports out of scope
  (import-linter is the Phase-2 successor).
- **T-04-04 (Tampering, gate silencing) — mitigated:** ty runs as plain `ty
  check`; documented beta fallback is `continue-on-error` + a tracked issue,
  never a checker swap (D-14).
- **T-04-SC (Tampering, dev-tool supply chain) — mitigated:** `uv sync --frozen`
  installs only the pinned `uv.lock`; `uvx reuse` resolves the same version as
  pre-commit. All tools legitimacy-audited in RESEARCH.

## Requirements Satisfied

- **SEAM-02:** the seam AST check is wired as a standing CI build gate and a
  pre-commit hook (both single-sourcing `scripts/seam_check.py`); the one-time
  D-10 demo (SC4) confirms it fails the build on a misplaced Copilot import and
  permits the same import inside `adapters/copilot/`.
- **LIC-01:** `uvx reuse lint` exits 0 across the whole repo (66/66 files carry
  copyright + license info), and is enforced as the first CI gate and a pre-commit
  hook — every file now carries SPDX info.

## Handoff to Next Plans

- This CI/pre-commit suite now gates **every** future commit. Phase 2 work
  (real `github-copilot-sdk` dep, `DraftingProvider` port, mock-provider swap,
  CLI/Typer, Sphinx/MyST/RTD) must keep all gates green.
- **Seam upgrade:** `import-linter` is the named Phase-2 successor to the AST
  check once the SDK is an installable dependency (D-09).
- **ty beta posture:** if a `ty` bump ever blocks delivery, the documented
  fallback is a temporary `continue-on-error: true` on the ty step + a tracked
  issue — never a swap to mypy/pyright (D-14).
- **Future planning docs:** any new `.planning/` doc that quotes an
  `SPDX-License-Identifier:` tag in prose must wrap it in `REUSE-IgnoreStart/End`
  (or avoid the literal tag) to keep the whole-repo reuse lint green.
- **PyPI name:** `dogen` is taken on PyPI (Red Hat tool) — the distribution name
  needs reconsideration before any publish (out of v1 scope; recorded in STATE).

## Known Stubs

None introduced by this plan. The empty `core/`, `adapters/copilot/`, and `cli/`
package markers remain intentional Phase-1 scaffold stubs (documented in plan
01-02); the real adapter, CLI, and docs toolchain land in Phase 2.

## Self-Check: PASSED

- Files: `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `REUSE.toml`,
  `seam-demo-evidence.md` (+ `.license` sidecar) all present (verified on disk).
- Commits: 3b8b6de, f92a64a, b9bbe2b all present in git log.
- Demo file removed: `src/dogen/core/_demo_violation.py` and
  `src/dogen/adapters/copilot/_demo_allowed.py` both absent.
- Gates green: full D-13 suite + `uvx reuse lint` (66/66) + `pre-commit run
  --all-files` all exit 0.
<!-- REUSE-IgnoreEnd -->
