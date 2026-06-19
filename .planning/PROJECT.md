# Agentic Documentation Drafting Framework

<!-- Working title. Epic: DOCPR-2845 — Agentic documentation creation (26.10 cycle). -->

## What This Is

A reusable, distributable Python package that helps a person in a Technical Author (TA) role draft complete documentation sets iteratively. It rides on an adopted agent SDK and adds a doc-drafting layer on top — it does exactly one thing: draft documentation in a Sphinx-publishable format. It is steered by human intent and product expertise, layers org-wide guidance + per-repo knowledge + writer preferences, and stays deliberately "dumb" outside drafting: no committing-at-scale, pushing, PR review, building, or auto-publishing. The hard border is singular, traceable local commits.

## Core Value

A TA (or anyone acting in that capacity) can reliably draft review-ready documentation faster than starting from scratch, with a human owning intent and review at every step — "quality at speed," without AI slop.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- The full-framework vision (the destination). These are hypotheses until shipped. The CURRENT milestone scopes a thin slice of these — see Context and REQUIREMENTS.md. -->

- [ ] Iteratively draft complete doc sets (per problem / topic / cross-section) across greenfield and brownfield projects, human-in-the-loop, rather than one-shot
- [ ] Ingest diverse source inputs (code, specs, existing docs, PR discussions, bug reports, commit histories) and draft from them
- [ ] Provide an abstraction layer over the AI platform/provider (and ideally the doc stack), proven first on GitHub + RTD + Sphinx
- [ ] Output publishable content only — stop at singular traceable local commits
- [ ] Be steerable with operator-supplied product expertise (point the agent at the right sources for a feature)
- [ ] Layered customization: org-wide guidance (called externally) → per-repo product knowledge → writer preferences
- [ ] Reuse and contribute back to existing docs skills/instructions (skills-playground, AI-resources-for-docs)
- [ ] Track provenance (model/version/effort, tooling version, context origins, reviewer edits) for internal observability
- [ ] Keep a human in the loop provably, via recorded steering on intent and audience, within the existing repo accountability model
- [ ] Local onboarding tool (style scraper) producing the code-to-docs map plus repo doc-style, glossary, and structure artefacts
- [ ] Type-aware generation steered by intent (reference / tutorial / how-to / explanation as *direction*), with an evidence-gated verification step on actionable content
- [ ] Coexist with the separate org-wide doc QA stage (DOCPR-2822) without absorbing it (optional extension point)
- [ ] Observable drafting loop, instrumented independently of the agentic SDK (provider-independent telemetry)
- [ ] Deployable out-of-the-box by any TA; proven to scale across multiple products (greenfield + brownfield)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Committing-at-scale, pushing, PR review, building, auto-publishing — framework stays "dumb" outside drafting; the reviewer/merger owns the output; hard border is singular traceable local commits
- The org-wide doc QA/testing stage (DOCPR-2822) — separate epic; we coexist and may optionally call it, but do not absorb it
- Continuous verification of content over time — handled by DOCPR-2822
- A public "AI-generated" disclaimer on shipped content — provenance is internal observability only; humans own and stand behind whatever ships
- Mode B (agent-guided research/planning across a wide surface) — deferred to end-cycle / a later milestone; largest net-new build, lowest risk to defer
- Persistent agentic memory (Cognee, mem0, similar) — Mode-B-facing; not needed for human-guided, unit-scoped Mode A
- Context-augmentation *build* (semantic or structural index) — gated behind the S1 spike; default is do-not-build
- Doc-stack/provider agnosticism beyond the proven stack and the SDK's native reach — prove one stack this cycle; broader agnosticism is a later property
- Building agent machinery — we adopt an SDK and build the drafting layer on top, not the agent core

## Context

- Part of Canonical's 26.10 cycle documentation effort (epic **DOCPR-2845**, "Agentic documentation creation"). Aligns with Canonical's AI policy and accountability standards.
- **Current milestone = MVP**, delivered agile. We **plan one pulse ahead, no further**. The epic's full task breakdown (components A–H, pulse plan) is a *frame of reference*, not a fixed task list.
- **First pulse, in-repo scope = A2 + F1 only:**
  - **A2 — Walking skeleton:** thin end-to-end loop where the agent drafts one small unit from human-pointed sources into Sphinx-publishable output. No commit logic. Proves the *loop*, not quality.
  - **F1 — Planning directory schema v0:** on-disk structure for intent/audience steering, unit plan, provenance fields, and progress (SDD-style). Becomes the future audit surface and provenance store.
- Other Pulse #12 work (SDK decision A1, UX baseline H1, candidate-project assessment H2) runs **outside this repo**; results are brought in.
- Primary docs-as-code scenario: **GitHub + Read the Docs + Sphinx**.
- Testing grounds: KernelFactory was an initial suggestion; candidates assessed separately (ideally one per epic member, including one intentionally unwieldy brownfield repo for the future context-augmentation spike). Workshop is adopted to contain documentation tests and define the repeatable deployment model.
- Sibling epic **DOCPR-2822** provides the org-wide doc QA framework — an external extension point this core optionally calls.
- Shared resources to reuse and contribute back to: skills-playground, AI-resources-for-docs.
- Two operating modes: **Mode A** (human-guided, in-cycle target) → **Mode B** (agent-guided, deferred).

## Constraints

- **Tech stack**: Python package; rides on the **Copilot SDK behind a thin, genuinely multi-provider abstraction seam** (alternate targets: OpenCode SDK, or a homegrown Pydantic AI agent) so the agentic-logic provider can be swapped cheaply — Why: pragmatic-first per the epic, with agnosticism kept as a core design property
- **Output**: must be Sphinx-publishable — Why: primary docs-as-code stack this cycle is GitHub + RTD + Sphinx
- **Scope border**: drafting only; stop at singular traceable local commits — Why: framework stays dumb outside drafting; reviewer/merger owns output
- **Process**: human-in-the-loop is mandatory and must be *provable* (recorded steering on intent + audience) — Why: accountability and the AC5 audit
- **Decoupling**: the reusable core stays distinct from the guidance it consumes (defined company-wide once and maintained, or scraped per repo) — Why: portfolio updates benefit everyone instead of fragmenting
- **Provenance**: internal observability only, about the harness/tooling — not a published content disclaimer — Why: humans own and stand behind shipped output
- **Observability**: instrumented independently of the agentic SDK (provider-independent layer; Logfire / OpenTelemetry the leading candidate) — Why: observability must survive an SDK swap and not depend on the SDK's own telemetry
- **Licensing**: REUSE-compliant from commit 1 (SPDX headers, `reuse lint` in CI); specific OSS license TBD via discussion — Why: clean, auditable licensing/provenance of own and third-party code
- **Delivery cadence**: agile; plan one pulse in advance; epic breakdown is a reference frame, not a fixed task list — Why: holiday/critical-path risk plus the "pour concrete in stages" philosophy
- **UX**: good design is a primary requirement — Why: if it's easier to circumvent than to use, it will be circumvented

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Adopt the Copilot SDK behind a thin, multi-provider abstraction seam | Pragmatic-first; thin seam keeps the provider swappable (OpenCode SDK / homegrown Pydantic AI as alternates) and preserves agnosticism as a core design property | ◆ Phase 1 — seam boundary established & CI-enforced (no-vendor-import AST guardrail, single adapter site); provider swap proof lands Phase 2 |
| Build the drafting layer, not agent machinery | Adopt-not-build keeps the core thin and focused on value-add | — Pending |
| Deliver agile — plan one pulse ahead | Critical-path/holiday risk + iterative "pour concrete in stages" philosophy | — Pending |
| First milestone (MVP) = walking skeleton (A2) + planning directory schema v0 (F1) + foundations (seam, observability, licensing) | Thinnest end-to-end proof of the loop, plus the SDD-style audit/provenance surface and the foundations that are expensive to retrofit | — Pending |
| Observability is provider-independent (Logfire / OTel candidate), not tied to the SDK | Keep telemetry durable across an SDK swap; don't depend on the SDK for it | — Pending (research + discuss) |
| REUSE framework for licensing compliance from commit 1 | Auditable SPDX licensing of own + third-party code; CI-enforced | ✓ Delivered (Phase 1) — GPL-3.0-only chosen; whole-repo `reuse lint` green and enforced in CI |
| RAG / context-augmentation is spike-gated, not a dependency | Avoid over-engineering; steering-first by default | — Pending |
| Stop at singular traceable local commits | Reviewer/merger owns output; framework stays dumb outside drafting | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-19 after Phase 1 (Compliant Scaffold & Provider-Seam Boundary) completion*
