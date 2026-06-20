# Requirements: Agentic Documentation Drafting Framework

**Defined:** 2026-06-19
**Core Value:** A TA (or anyone acting in that capacity) can reliably draft review-ready documentation faster than from scratch, with a human owning intent and review at every step — "quality at speed," without AI slop.

> **Milestone scope.** This is the **MVP / first pulse**, delivered agile (one pulse planned ahead). v1 below = the epic's **A2 (walking skeleton)** + **F1 (planning-directory schema v0)**, plus the **project foundations** that must be right from commit 1: a genuinely multi-provider abstraction seam, provider-independent observability, and REUSE-compliant licensing. The wider framework vision lives in PROJECT.md; the suggested destination phases live in `.planning/research/SUMMARY.md`. v2 here records that destination so nothing is lost — it is *not* being planned yet.
>
> **Open questions to resolve at `/gsd-discuss-phase 1` (with per-phase research):** (a) observability backend — Logfire vs OTel-direct vs leaning on the SDK's `[telemetry]` extra; (b) provider strategy — how far to validate OpenCode SDK / homegrown Pydantic AI as alternates in v1 vs design-only; (c) the specific OSS license for the distributable core. Requirements below marked _(research + discuss)_ carry these flags.

## v1 Requirements

The thinnest end-to-end slice that proves the drafting loop and establishes the audit/provenance surface everything later hangs off. Each maps to the first-milestone roadmap.

### Walking Skeleton (A2) — the thin drafting loop

- [x] **SKEL-01**: Operator can define a documentation *unit* and point the agent at human-specified source inputs for that unit
- [x] **SKEL-02**: The agent drafts the unit end-to-end into Sphinx-publishable output (MyST Markdown) via CLI → orchestrator → Copilot adapter
- [x] **SKEL-03**: The drafting loop produces output only and stops before any commit — no committing, pushing, PR, build, or publish
- [x] **SKEL-04**: The agent operates with a bounded, read-only toolset (grep / glob / view) — no write, exec, or network tools
- [x] **SKEL-05**: The drafting backend runs on a pinned `github-copilot-sdk==1.0.2` with a compatible pinned Copilot CLI, and "backend unavailable" is a handled, non-crashing state (a drafting-loop smoke test gates SDK/CLI upgrades)

### SDK Abstraction Seam (A2) — provider-agnostic core

- [x] **SEAM-01**: The GitHub Copilot SDK is imported in exactly one adapter module; the domain core has zero vendor imports
- [x] **SEAM-02**: A CI guardrail fails the build if any Copilot SDK import appears outside the adapter module
- [x] **SEAM-03**: The `DraftingProvider` port is shaped by domain verbs (not SDK method signatures), so the agentic-logic provider is swappable; a mock provider slots into it to prove swappability without any real SDK
- [x] **SEAM-04**: The seam is multi-provider *by design* — Copilot SDK is the v1 adapter, with the OpenCode SDK or a homegrown Pydantic AI agent named as viable target alternates; the port contract is documented and carries no Copilot-specific assumptions _(research + discuss)_

### Planning Directory Schema v0 (F1) — the audit/provenance surface

- [x] **PLAN-01**: The framework persists a per-unit planning directory (`unit.md`, draft, `provenance.yaml`, `progress.yaml`) plus a steering record, on disk
- [x] **PLAN-02**: The schema carries a `schema_version` field so future migrations are explicit and detectable
- [x] **PLAN-03**: `unit.md` front-matter records intent + audience + steering notes and the human-pointed sources for the unit
- [x] **PLAN-04**: `provenance.yaml` records, per generation pass, model / model version / effort, tooling version, SDK version, context origins (what the agent actually read — distinct from the human-pointed sources), and tools used
- [x] **PLAN-05**: `provenance.yaml` records reviewer edits (timestamp, reviewer, summary) made after generation
- [x] **PLAN-06**: `progress.yaml` tracks the unit lifecycle `pending → sourced → drafted → reviewed → committed` and stops at `committed` (no push / PR / build / publish states exist)
- [x] **PLAN-07**: The schema structurally reserves (present but may be empty at v0) the evidence fields for actionable-content verification: step state, evidence pointer, environment fingerprint

### Provable Human-in-the-Loop Gate (A2 + F1)

- [x] **HITL-01**: The orchestrator refuses to draft a unit unless intent + audience steering has been recorded first ("no recorded steering → no draft")
- [x] **HITL-02**: Recorded steering captures author and timestamp, so an audit of the planning directory shows no substantial draft without a recorded human steering input (AC5 evidence)

### Observability (foundation) — instrumented independently of the SDK

- [x] **OBS-01**: The drafting loop emits structured observability (traces/spans of the loop, key run metrics, run logs) through a provider-independent instrumentation layer in the core — not via the Copilot SDK's own telemetry — so observability survives an SDK swap
- [x] **OBS-02**: A concrete observability backend is wired at a basic level for local runs, layered on top of whatever the SDK already emits; Logfire (OpenTelemetry-based, pairs with Pydantic v2) is the leading candidate, final choice confirmed at planning _(research + discuss)_
- [x] **OBS-03**: Run-level observability correlates with the F1 provenance record (a run maps to its `provenance.yaml` generation entry), so the runtime trace and the on-disk audit surface line up

### Licensing & Compliance (foundation) — REUSE from commit 1

- [x] **LIC-01**: The repository is REUSE-compliant — every file carries SPDX license + copyright info (inline header, `.license` file, or `REUSE.toml`), `LICENSES/` is populated, and `reuse lint` passes in CI
- [x] **LIC-02**: A license for the distributable core is chosen, applied, and recorded as an SPDX identifier; selection confirmed at planning _(discuss)_

## v2 Requirements

Deferred to future milestones. Tracked but **not** in the current roadmap. These are the destination phases from `.planning/research/SUMMARY.md`; promoting any of them to v1 requires a new milestone.

### Steering Quality & Type-Aware Generation (D + E)

- **STEER-01**: Layered customization — org → repo → writer guidance merged, with org guidance fetched externally (remote URL/repo, evolving toward MCP)
- **STEER-02**: Type-aware generation surfaced as one capability steered by intent (reference / tutorial / how-to / explanation as direction)
- **STEER-03**: Singular traceable local-commit boundary (atomic, author-legible commits — still no push/PR/build/publish)
- **STEER-04**: Cheap slop-detection pre-review pass (banned-phrase / repetition checks)

### Onboarding / Style Scraper (B)

- **ONB-01**: Local onboarding tool producing a code-to-docs map plus repo doc-style, glossary, and structure artifacts
- **ONB-02**: Pre-filled steering defaults so authors edit rather than start from blank

### Evidence-Gated Actionable Verification (E — spike-gated)

- **VERIFY-01**: Reproducible sandbox (Workshop-contained) where drafted steps can actually execute and state can be inspected — **spike required first**
- **VERIFY-02**: Actionable content defaults to `unverified`; only a captured run (command, exit code, output, env fingerprint) flips it to `verified`

### SDLC Connectors & Portfolio Scale (C + G)

- **CONN-01**: Bounded read-only connectors for non-file SDLC sources (PR threads, bug reports, commit discussion) behind the `SourceLookup` port
- **CONN-02**: Proven across multiple products (greenfield + brownfield)
- **CONN-03**: Optional DOCPR-2822 QA extension point (real adapter replacing the no-op hook)

### Context Augmentation (S1 — spike-gated, conditional)

- **AUG-01**: Retrieval/index backing for the lookup seam — only if the S1 spike proves a concrete need steering-first cannot meet (default: do not build)

### Mode B — Agent-Guided (deferred)

- **MODEB-01**: Agent leads research/investigation/planning across a wider surface and presents a vetted vision before drafting

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-commit / push / open PRs / build / auto-publish | Crosses the accountability border; framework stays "dumb" outside drafting — hard stop at singular local commits |
| One-shot full-set generation | Unreviewable volume; maximizes AI slop; the tool is iterative by necessity |
| Public "AI-generated" disclaimer on shipped content | Provenance is internal observability only; humans own and stand behind whatever ships |
| Premature RAG / context-augmentation build (before S1 spike) | Over-engineering; steering-first is sufficient for Mode A |
| Reader-facing AI assistant / chat-over-docs | Different product entirely |
| The org-wide doc QA/testing stage itself (DOCPR-2822) | Separate epic; we coexist and optionally call it, never absorb it |
| Continuous verification of content over time | Handled by DOCPR-2822 |
| Doc-stack / provider agnosticism beyond the proven stack + SDK's native reach | Prove one stack (GitHub + RTD + Sphinx) this cycle; agnosticism is a design property, not multi-stack support now |
| Building agent machinery | We adopt the Copilot SDK and build the drafting layer on top |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SKEL-01 | Phase 2 | Complete |
| SKEL-02 | Phase 2 | Complete |
| SKEL-03 | Phase 2 | Complete |
| SKEL-04 | Phase 2 | Complete |
| SKEL-05 | Phase 2 | Complete |
| SEAM-01 | Phase 1 | Complete |
| SEAM-02 | Phase 1 | Complete |
| SEAM-03 | Phase 2 | Complete |
| SEAM-04 | Phase 2 | Complete |
| PLAN-01 | Phase 2 | Complete |
| PLAN-02 | Phase 2 | Complete |
| PLAN-03 | Phase 2 | Complete |
| PLAN-04 | Phase 2 | Complete |
| PLAN-05 | Phase 2 | Complete |
| PLAN-06 | Phase 2 | Complete |
| PLAN-07 | Phase 2 | Complete |
| HITL-01 | Phase 2 | Complete |
| HITL-02 | Phase 2 | Complete |
| OBS-01 | Phase 2 | Complete |
| OBS-02 | Phase 2 | Complete |
| OBS-03 | Phase 2 | Complete |
| LIC-01 | Phase 1 | Complete |
| LIC-02 | Phase 1 | Complete |

**Coverage:**

- v1 requirements: 23 total
- Mapped to phases: 23 (Phase 1: 4 — SEAM-01, SEAM-02, LIC-01, LIC-02; Phase 2: 19 — all others)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-19*
*Last updated: 2026-06-19 after roadmap creation (traceability populated, 23/23 mapped)*
