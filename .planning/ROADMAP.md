# Roadmap: Agentic Documentation Drafting Framework

## Overview

This is the MVP / first pulse, delivered agile — we plan one pulse ahead and no further. The milestone delivers the epic's **A2 (walking skeleton)** + **F1 (planning-directory schema v0)** plus the three foundations that are expensive to retrofit: a genuinely multi-provider abstraction seam, provider-independent observability, and REUSE-compliant licensing. We pour the concrete that everything later hangs off — a REUSE-clean repo with the provider-seam boundary CI-enforced from commit 1, then the thinnest possible end-to-end loop where the agent drafts one human-pointed unit into Sphinx-publishable output, writing intent/audience steering, provenance, and progress into the on-disk audit surface, with no commit logic. The v2 destination (steering quality, onboarding/style scraper, evidence-gated verification, SDLC connectors, RAG, Mode B) lives in REQUIREMENTS.md and research/SUMMARY.md and is deliberately NOT planned here.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Compliant Scaffold & Provider-Seam Boundary** - REUSE-clean Python package with the Copilot adapter isolated behind a CI-enforced no-vendor-import boundary
- [ ] **Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability** - End-to-end draft loop for one unit into Sphinx-publishable output, writing the F1 audit/provenance surface, gated on recorded steering and instrumented independently of the SDK

## Phase Details

### Phase 1: Compliant Scaffold & Provider-Seam Boundary
**Goal**: A distributable Python package exists that is REUSE-compliant from commit 1, with the Copilot SDK confined to a single adapter module and that boundary enforced in CI — so the licensing, packaging, and provider-swappability invariants are set before any drafting logic is written.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SEAM-01, SEAM-02, LIC-01, LIC-02
**Success Criteria** (what must be TRUE):
  1. `reuse lint` passes on the repository in CI — every file carries SPDX license + copyright info and `LICENSES/` is populated
  2. The chosen OSS license is applied and recorded as an SPDX identifier in the package metadata
  3. The Copilot SDK is imported in exactly one adapter module; the domain core has zero vendor imports
  4. The CI build fails if any Copilot SDK import appears outside that adapter module (a guardrail check can be observed catching a deliberately misplaced import)
**Plans**: TBD

Plans:
- [ ] 01-01: TBD

**Notes / open decisions (settle at `/gsd-discuss-phase 1`):**
- LIC-02: the specific OSS license for the distributable core is not pre-resolved here — confirm at discuss.
- This phase establishes the seam *boundary and its enforcement*; the port contract and swappability proof (SEAM-03/04) land with the skeleton in Phase 2 where a mock provider exercises them.

### Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability
**Goal**: The agent drafts one operator-defined documentation unit end-to-end — from human-pointed sources into Sphinx-publishable MyST output — stopping before any commit, while writing the F1 planning directory (steering, provenance, progress), refusing to draft without recorded steering, and emitting SDK-independent observability that correlates with the provenance record. This is the inseparable A2 + F1 slice: the skeleton needs the schema to write to, and the schema needs a real producer to validate it.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: SKEL-01, SKEL-02, SKEL-03, SKEL-04, SKEL-05, SEAM-03, SEAM-04, PLAN-01, PLAN-02, PLAN-03, PLAN-04, PLAN-05, PLAN-06, PLAN-07, HITL-01, HITL-02, OBS-01, OBS-02, OBS-03
**Success Criteria** (what must be TRUE):
  1. Operator can define a unit, point the agent at human-specified sources, record intent + audience steering, and get a Sphinx-publishable MyST draft — and the orchestrator refuses to draft when no steering has been recorded ("no recorded steering → no draft")
  2. The drafting loop produces output only and stops before any commit/push/PR/build/publish, using a bounded read-only toolset (grep/glob/view) on a pinned `github-copilot-sdk==1.0.2`, with "backend unavailable" handled without crashing
  3. A per-unit planning directory is persisted on disk (`unit.md`, draft, `provenance.yaml`, `progress.yaml`) with a `schema_version` field, full provenance (model/version/effort, tooling/SDK version, context origins, tools, reviewer edits), a `pending → … → committed` lifecycle that stops at `committed`, and structurally-reserved (possibly-empty) verification-evidence fields
  4. An audit of the planning directory shows no substantial draft without a recorded human steering input (author + timestamp), satisfying the AC5 evidence requirement
  5. The loop emits structured traces/metrics/logs through a provider-independent instrumentation layer (not the SDK's own telemetry) wired to a concrete local backend, and each run correlates with its `provenance.yaml` generation entry
  6. The `DraftingProvider` port is shaped by domain verbs and a mock provider slots into it to prove swappability without any real SDK; the port contract is documented with no Copilot-specific assumptions
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

**Notes / open decisions (settle at `/gsd-discuss-phase 2`):**
- OBS-02: observability backend (Logfire vs OTel-direct vs leaning on the SDK's `[telemetry]` extra) — leading candidate is Logfire; confirm at discuss/planning.
- SEAM-04: how far to validate the OpenCode SDK / homegrown Pydantic AI alternates in v1 (design-only vs a real second adapter) — name them as viable targets and keep the contract Copilot-agnostic; resolve the depth at discuss.
- Research flag: verify the exact `github-copilot-sdk==1.0.2` Python API names (method signatures, event types, `SessionConfig`, `@define_tool`) against the installed package at the start of planning — architecture examples are illustrative.
- F1 schema must reserve `schema_version` + verification/steering/reviewer fields at v0 even when empty; the `sources` (human-pointed) vs `context_origins` (agent-actually-read) gap must be preserved as two distinct fields.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Compliant Scaffold & Provider-Seam Boundary | 0/TBD | Not started | - |
| 2. Walking Skeleton, Planning Schema, Provable HITL & Observability | 0/TBD | Not started | - |
