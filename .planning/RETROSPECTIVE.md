# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-06-20
**Phases:** 2 | **Plans:** 8 | **Sessions:** ~5 (git-clustered across 2 days; not separately tracked)

### What Was Built
- **Phase 1 — Compliant Scaffold & Provider-Seam Boundary:** a REUSE-compliant `src/dogen/` package from commit 1 (per-file SPDX via a committed Jinja2 notice template, GPL-3.0-only), a hexagonal layout confining all vendor imports to `adapters/copilot/`, an AST seam guardrail single-sourced across pytest/CI/pre-commit, and a SHA-pinned least-privilege CI gate suite.
- **Phase 2 — Walking Skeleton, Planning Schema, Provable HITL & Observability:** the F1 planning-directory schema v0 (Pydantic v2, `schema_version: 0`, reserved verification fields, `sources` vs `context_origins` kept distinct), the async `core/orchestrator.py` drafting use-case enforcing "no recorded steering → no draft", a deterministic SDK-free `MockDraftingProvider` plus the real `CopilotDraftingProvider` on the pinned `github-copilot-sdk==1.0.2` behind one `DraftingProvider` port, OTel-API observability with `run_id`↔provenance correlation, and the `dogen unit new / steer / draft / review` CLI emitting Sphinx-publishable MyST and stopping at `reviewed`.

### What Worked
- **Foundations-first paid off.** Setting the seam boundary, REUSE licensing, and CI enforcement *before any drafting logic* (Phase 1) made the Phase-2 provider swap cheap — the real Copilot adapter slotted in behind the very port the mock had already proven, with no core rewrite. The "pour concrete in stages" philosophy held.
- **Single-sourcing invariants across enforcement surfaces.** The seam check (and later the import-linter contract) was wired once into pytest + CI + pre-commit (+ the editor via config), so the three gates cannot drift. Same pattern reused for both phases.
- **A deterministic, SDK-free mock as the CI proof.** The whole loop runs in CI with no Copilot token or network, keeping the skeleton always demoable and making the swappability claim testable (`isinstance` against the port for both providers).
- **Cross-model review caught the highest-stakes bug.** The single blocker (BL-01: orchestrator fabricating `context_origins`/`tools_used` on the real path) was surfaced by the Codex cross-model review and *missed* by the Claude review — an audit surface that lies about what was read would have undermined the project's core AC5 value.

### What Was Inefficient
- **`reuse lint` on planning prose was a recurring tax.** A whole-repo `reuse lint` gate also lints committed `.planning/` docs; any doc that *quotes* an SPDX token in prose is misread as a real declaration. The false-positive count crept 1 → 2 → 4 as each new SUMMARY described the prior one, and it forced a post-audit quick task (260620-sa1) to wrap the prose and get CI green.
- **Three CI gates were red at audit time** (reuse lint, `ty` test-double, a stray `ruff format`), all non-functional but all latent until the milestone audit ran them against the working tree. A green local "full gate suite" run at phase close — not just the test subset — would have caught them earlier.
- **A stated invariant ("no `REUSE.toml` ever", D-04) had to be reversed mid-phase** once it became clear committed `.planning/` meta is in `reuse lint` scope — costing a re-plan and a security ratification.
- **A point-in-time security disposition ("#1606 eliminated") was carried as if permanent** and had to be explicitly un-carried in Phase 2 once the SDK became a real runtime dependency.

### Patterns Established
- **`.license` sidecars** for files that can't carry an inline header (generated lockfiles, Markdown/docs, the Jinja2 template itself, published content).
- **Meta-only `REUSE.toml` at aggregate precedence** so per-file source headers still win while whole-repo lint goes green; **`REUSE-IgnoreStart/End`** to suppress SPDX-token-in-prose false positives.
- **Anti-corruption mapping at the seam** (SDK event → domain `DraftResult` via defensive `getattr`) so wide vendor union types never reach core.
- **Lazy provider-factory dispatch + a no-import regression test** so the mock path never loads the SDK adapter; **import-linter declarative contract kept belt-and-braces alongside the AST check** (D-29 keep-both).
- **Durability ordering for audit-first writes:** record provenance before the observable draft, write YAML atomically (temp + fsync + `os.replace`).
- **AST-scan tests for "never reachable" invariants** (e.g. `committed` is never written).

### Key Lessons
1. **A whole-repo lint gate lints your planning prose too.** Anything git-tracked is in scope; SPDX tokens quoted in narrative trip `reuse`. Wrap new planning docs proactively or the red count creeps every milestone.
2. **Run the *full* gate suite (not just tests) at phase close.** `ty`, `ruff format --check`, and `reuse lint` reds stayed invisible until the milestone audit because phase verification leaned on the test subset.
3. **Foundations that are expensive to retrofit should go in first** — the seam + licensing + observability sequencing made later work cheap and is worth repeating.
4. **Record requirement IDs in a machine-readable key, not just `tags:`.** SKEL-02's tags-only record made the audit rollup flag it `partial` despite being fully verified — pure bookkeeping cost.
5. **Cross-model / adversarial review earns its keep on audit-integrity bugs.** The one real blocker was only caught by the second model.
6. **A schema field documented as a "mirror" must be maintained or marked reserved** — a silently-stale field (`Unit.status`) is an audit-integrity hazard, not cosmetic.

### Cost Observations
- Model mix: not instrumented this milestone (config `model_profile: quality`, opus-leaning). Add per-session model accounting before v1.1 if cost tracking matters.
- Sessions: ~5 working clusters across 2 calendar days (2026-06-19 → 2026-06-20), 85 commits.
- Notable: the GSD per-plan → verify → validate → security → audit chain added overhead but caught real, shippable-affecting issues (BL-01, the stale dogfood provenance, the CI-red gates) before close.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~5 | 2 | Foundations-first sequencing; single-sourced invariants across CI/pre-commit/pytest; cross-model review adopted |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|--------------------|
| v1.0 | 97 passing | not measured | AST seam guardrail (pure stdlib); deterministic SDK-free mock |

### Top Lessons (Verified Across Milestones)

1. *(needs a second milestone to cross-validate)* — candidate: whole-repo lint gates lint planning prose; wrap SPDX tokens proactively.
2. *(needs a second milestone to cross-validate)* — candidate: run the full gate suite at phase close, not just tests.
