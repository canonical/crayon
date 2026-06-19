# Phase 1: Compliant Scaffold & Provider-Seam Boundary - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers a **distributable, REUSE-clean Python package skeleton** with the Copilot SDK confined to a single adapter module and that boundary CI-enforced — the licensing, packaging, and provider-swappability concrete, poured *before any drafting logic*. Covers **SEAM-01, SEAM-02, LIC-01, LIC-02**.

**In scope:** REUSE compliance + `reuse lint` in CI; chosen OSS license recorded as SPDX; the hexagonal package scaffold; the seam *boundary* (adapter module shape) and its CI enforcement; commit-1 quality gates (lint/format/type/seam) and repo hygiene.

**Out of scope (Phase 2):** the drafting loop, the `DraftingProvider` port contract + mock-provider swap proof (SEAM-03/04), the real `github-copilot-sdk` dependency + pinned CLI (SKEL-05), the planning-directory schema (PLAN-*), HITL gate, observability, and the Sphinx/RTD docs toolchain.
</domain>

<decisions>
## Implementation Decisions

### Licensing & REUSE
- **D-01 — OSS license = `GPL-3.0-only`.** Per Canonical's Licensing policy: *"not 'v3 or later'"* → the `-only` SPDX variant (corrects the earlier `-or-later`). `dogen` is classified as a tool/application (CLI is the primary UX) → the policy's "everything else" bucket, matching Canonical craft apps. Apache-2.0 is reserved for charms; any non-default license needs **CEO approval**, so we stay on the policy default.
- **D-02 — Copyright = `Canonical Ltd.`; year = year of first publication = `2026`.**
- **D-03 — License granularity = single license now.** No separate content license at Phase 1 (almost no prose/data yet). A docs/content license is deferred to when real docs land (policy default CC-BY-SA-4.0; confirm against the policy's own CC-BY-NC-SA-4.0 inconsistency first).
- **D-04 — REUSE annotation style = per-file full Canonical notice block** (program name + one-line description, copyright, `SPDX-License-Identifier: GPL-3.0-only`, GPL warranty-disclaimer paragraph) — **not** `REUSE.toml` bulk mapping. Use `SPDX-FileCopyrightText: 2026 Canonical Ltd.` (not a bare `Copyright` line) so `reuse lint` passes cleanly while preserving the policy block. Exact header in `coding-guide.md` §7.
- **D-05 — License text** lives in `LICENSES/GPL-3.0-only.txt` (REUSE requirement) **plus** a top-level `LICENSE` (policy ask). `reuse lint` gates CI (satisfies LIC-01); SPDX identifier in package metadata satisfies LIC-02 / SC2.
- **D-06 — CONTRIBUTING references the Canonical CLA.** CLA-contributed files use the policy's "License granted by Canonical Limited" notice variant (relevant for future external contributions, not commit-1 code).

### Provider seam & enforcement
- **D-07 — Hot-swap = design property, not runtime machinery.** Clean inward-only boundary + a single Copilot adapter make a future swap cheap. No runtime/config provider-selection mechanism is built in Phase 1. The `DraftingProvider` port contract + the mock-provider swap *proof* are Phase 2 (SEAM-03/04). Third-party entry-point/plugin discovery = v2 / non-goal.
- **D-08 — Phase-1 adapter depth = empty boundary.** `adapters/copilot/` exists as the *designated sole importer* shape, but takes **no `github-copilot-sdk` dependency yet**. Keeps Phase-1 CI fast and free of the issue #1606 CLI auto-update fragility. The real SDK + import + pinned CLI land in Phase 2 (SKEL-05).
- **D-09 — Seam enforcement = static AST-based check** (no SDK install needed) that flags any `copilot` / `github_copilot_sdk` import outside `adapters/copilot/`. AST-based (not regex grep) so it resists aliasing/evasion. Runs on **every CI build** (satisfies SEAM-02 / SC4). `import-linter` is named as the natural Phase-2 upgrade once the SDK is a real, installable dependency.
- **D-10 — Guardrail proof (SC4) = one-time manual demo.** Demonstrate the check catching a deliberately-misplaced import once and capture the log as the AC evidence; the AST check is the standing CI protection. *Trade-off accepted:* no committed negative-test fixture, so the check's own correctness isn't continuously regression-tested (candidate future hardening — see Deferred).

### Packaging & project identity
- **D-11 — Package name = `dogen`** (distribution + import name; `src/dogen/` layout). Verify PyPI-name availability before first publish (publishing is well out of v1 scope).
- **D-12 — Toolchain = uv + hatchling + src layout.** `requires-python = ">=3.12"` (matches the 3.12 target that later covers Sphinx 9.x; tightening the floor afterwards would be breaking and there are no users yet). CI matrix on 3.12, plus 3.13 as cheap forward-compat insurance.

### CI & quality gates
- **D-13 — CI = GitHub Actions.** Commit-1 gates run together: `reuse lint` + `ruff` (lint + format) + `ty` (type check) + the seam AST check + a `pytest` harness (smoke/import test). A `pre-commit` config mirrors the gates for local DX.
- **D-14 — Type checker = `ty` (Astral)**, per the Handbook's mandated Python toolchain — this refines the earlier mypy/pyright assumption.
- **D-15 — Coding standards = follow `.planning/refs/coding-guide.md`** (binding). `AGENTS.md` is the agent operating contract; synthetic code carries provenance per `.planning/refs/synthetic-code-provenance.md`. These were synthesized from Canonical's engineering Handbook with emphasis on its machine-assisted-development critique.

### Repo hygiene
- **D-16 — Standard OSS file set at commit 1, Canonical conventions:** README, CONTRIBUTING (with CLA), SECURITY.md, CODE_OF_CONDUCT, `.editorconfig`, `.gitignore`. `AGENTS.md` already created this session.

### Docs toolchain
- **D-17 — Sphinx/MyST + RTD toolchain deferred entirely to Phase 2.** Phase 1 is the package scaffold; standing up `conf.py`/`.readthedocs.yaml` with nothing to render (and a 3.12-only Sphinx toolchain not yet needed) is premature.

### Dependency management
- **D-18 — Commit `uv.lock` from commit 1.** The dependency-update bot (Renovate/Dependabot) is deferred to Phase 2 — there is no SDK/CLI pin to watch until then, which is exactly when issue #1606 makes pin-watching matter.

### Process (adopted from the Handbook)
- **D-19 — Trunk-based development.** `main` is default + stable. Feature branches ~one pulse, named `docpr-<ticket>-<objective>` (kebab-case). Squash-merge, delete on merge, keep PRs small. Two maintainer reviews; reviewers check out and run the change locally (no spot-checks).

### Claude's Discretion
- Exact `ruff` ruleset selection and `ty` strictness flags (within the coding-guide constraints), and the `pytest`/`tests/` layout — specs are fixed in `coding-guide.md`; the concrete config is implemented during execution.
- The sub-layout inside `src/dogen/` (`core/`, `adapters/copilot/`, `cli/`) per ARCHITECTURE.md.
- Exact wording/structure of README, SECURITY.md, CODE_OF_CONDUCT (follow Canonical conventions).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### In-repo binding references (read first)
- `.planning/refs/coding-guide.md` — **binding** coding standards: ruff + `ty`, the AI-anti-pattern→rule table, testing rules, architecture invariants, and the exact REUSE/Canonical file header (§7). Created this session from the Handbook.
- `AGENTS.md` — agent operating contract: the seam invariant, coding rules, AI discipline (provenance, shell-allowlists), licensing header, branching.
- `.planning/refs/synthetic-code-provenance.md` — reusable synthetic-code provenance prompt + output templates (dev-process record; mirrors the Phase-2 product `provenance.yaml`).

### Canonical org policy (internal — distilled into the refs above; do NOT commit to the OSS repo)
- `~/Downloads/Licensing policy.md` — Canonical Licensing policy (Corporate Reference Library; approved 2023-01-01). Operative rules already distilled into D-01..D-06 and `coding-guide.md` §7: GPLv3-only / LGPLv3-only / AGPLv3-only by project type, per-file notice block, CLA. Internal doc — its rules travel via this CONTEXT + the coding guide, the doc itself is not committed.
- `~/Downloads/Handbook for engineering practice in documentation.md` — Canonical engineering Handbook. Source for `coding-guide.md` and the branching/review model (D-19). Substantive content: *Machine-assisted development*, *Code rules*, *Code review practice*, *Branching*; many later policy sections are still empty stubs. Internal doc — not committed.

### Project planning & research
- `.planning/ROADMAP.md` → "Phase 1" — goal, requirements (SEAM-01/02, LIC-01/02), the four success criteria.
- `.planning/REQUIREMENTS.md` — SEAM-01/02 + LIC-01/02 (and SEAM-03/04, SKEL-05 for the Phase-2 boundary).
- `.planning/research/ARCHITECTURE.md` → "Repository layout", "Pattern 1: Provider Port + Adapter", "Anti-Pattern 1/2" — the hexagonal layout (`core/` / `adapters/copilot/` / `cli/`), the seam, and the CI-guardrail concept.
- `.planning/research/STACK.md` — uv + hatchling + src layout, Typer, Python 3.12 target, SDK/CLI pin guidance, issue #1606.
- `.planning/research/PITFALLS.md` → "Pitfall 4" (seam leak) and "Pitfall 9" (scope border past commit) — invariants the scaffold and guardrail must protect.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None in-repo. Greenfield: only `.claude/CLAUDE.md` is tracked outside `.planning/`. This phase pours the first concrete. No codebase maps exist (`.planning/codebase/` empty).

### Established Patterns
- No in-repo patterns yet. The **binding** patterns for new code are in `.planning/refs/coding-guide.md` (style + AI rules) and `.planning/research/ARCHITECTURE.md` (hexagonal layout). Prescribed layout: `src/dogen/{core/` (pure, zero vendor imports), `adapters/copilot/` (sole SDK importer — empty in Phase 1), `cli/}`.

### Integration Points
- None yet — Phase 1 takes no real `github-copilot-sdk` dependency (D-08). The only "integration" is the CI guardrail asserting the seam boundary holds.
</code_context>

<specifics>
## Specific Ideas

- Both incoming reference guides were located in `~/Downloads/` and read this session: the **Licensing policy** and the **Handbook for engineering practice in documentation**.
- Rather than adopt the Handbook verbatim, the user asked for a **synthesized, stricter project coding guide** plus **AI coding artefacts for agents**, with special weight on the Handbook's machine-assisted-development critique — produced this session (`coding-guide.md`, `AGENTS.md`, `synthetic-code-provenance.md`).
- Package name `dogen` was chosen by the user (not the working title).
- Type checker is `ty` (Astral), explicitly per the Handbook — not mypy/pyright.
</specifics>

<deferred>
## Deferred Ideas

- **Runtime/config provider selection** + `DraftingProvider` port contract + mock-provider swap proof → Phase 2 (SEAM-03/04).
- **Real `github-copilot-sdk` dependency** + pinned Copilot CLI + drafting-loop smoke test → Phase 2 (SKEL-05).
- **`import-linter` upgrade** for seam enforcement (over the static AST check) → Phase 2, once the SDK is a real installable dependency.
- **Committed negative-test fixture** for the seam guardrail (vs the one-time manual demo, D-10) → optional future hardening.
- **Docs/content license** (CC-BY-SA-4.0 candidate) → when first docs land (Phase 2).
- **Sphinx/MyST + RTD docs toolchain** → Phase 2.
- **Dependency-update bot** (Renovate/Dependabot) → Phase 2.
- **Third-party plugin/entry-point provider discovery** → v2 / non-goal for this milestone.
</deferred>

---

*Phase: 1-Compliant Scaffold & Provider-Seam Boundary*
*Context gathered: 2026-06-19*
