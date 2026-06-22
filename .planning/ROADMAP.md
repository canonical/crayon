# Roadmap: Agentic Documentation Drafting Framework

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-06-20) — full detail: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- 🔄 **v1.1 Live Copilot Path Hardening** — Phases 3-4 (in progress) — closes the four gaps the first live `dogen draft --provider copilot` run surfaced

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-2) — SHIPPED 2026-06-20</summary>

- [x] Phase 1: Compliant Scaffold & Provider-Seam Boundary (4/4 plans) — completed 2026-06-19
- [x] Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability (4/4 plans) — completed 2026-06-20

Full phase details, success criteria, and milestone summary archived in
[milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

</details>

### 🔄 v1.1 Live Copilot Path Hardening (Phases 3-4)

Pure hardening of the existing live `--provider copilot` path — no net-new domain
features. The v1.0 walking skeleton proved the loop on the deterministic mock and a
contrived live run; the first *real* live run surfaced four concrete gaps that make the
path unusable out of the box and leave its audit surface blind. v1.1 closes exactly those
gaps across 7 requirements. The live path is **manual-only** (D-24, kept out of CI — no
token or network in CI), so phases are validated by manual live runs **plus** unit tests
against a fake/stub SDK; no CI live-call gate is added.

- [x] **Phase 3: Live Copilot path runs out of the box** - Operator selects an available model, non-interactive source reads are allowed, any model family drafts successfully, and every failure surfaces as a clean message + nonzero exit instead of a traceback (autonomous code done 2026-06-22; awaiting D-24 manual live-run verification) (completed 2026-06-22)
- [ ] **Phase 4: Honest observed provenance** - After a successful live draft, `provenance.yaml` truthfully records what the agent actually read and which tools it actually invoked, derived from observed tool-call events

## Phase Details

### Phase 3: Live Copilot path runs out of the box

**Goal**: A TA can run `dogen draft --provider copilot` out of the box and either get a written draft on an available model of any family, or a clear actionable failure — never a hardcoded-unavailable default, a denied source read, a parameter rejection, or a raw traceback
**Depends on**: Phase 2 (v1.0 walking skeleton, Copilot adapter, orchestrator/CLI seam)
**Requirements**: LIVE-01, LIVE-02, LIVE-03, ERR-01, ERR-02
**Success Criteria** (what must be TRUE):

  1. Operator runs `dogen draft --provider copilot --model <available>` (and a bare `dogen draft --provider copilot` using the new default) and gets a written Sphinx-publishable draft — the hardcoded, unavailable `gpt-5` default is gone
  2. In a non-interactive live run the agent actually reads the human-pointed sources — `grep`/`glob`/`view` are auto-approved by the provider's permission handler rather than denied, while write/exec/network stay denied
  3. Selecting a Claude-family model drafts successfully — `reasoning_effort` is sent only to GPT-5-family models and omitted for models that reject it, so the parameter no longer errors
  4. Requesting a model the backend rejects prints a clear message naming the rejected model and exits nonzero — never a raw `JsonRpcError` traceback (closes accepted debt item #4)
  5. Any other live backend / JSON-RPC error on the draft path surfaces as a handled failure with a clear message and a nonzero exit, never an uncaught crash

**Plans**: 2/2 plans complete
**Wave 1**

- [x] 03-01-PLAN.md — Wave-0 fake-SDK test harness (kwargs-capturing _StubClient in conftest) + the D-08 private-import and V4 toolset-boundary regression guards

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — TDD all five fixes in the adapter/seam/CLI (gpt-5-mini default + --model, approve_all, family-gated reasoning_effort, ModelRejectedError/BackendUnavailableError mapping) + manual live verification

**UI hint**: no

### Phase 4: Honest observed provenance

**Goal**: After a successful live draft the audit surface reflects what actually happened — `context_origins` and `tools_used` are populated from the session's observed tool-call events, completing the BL-01 honesty work (v1.0 stopped fabricating them; v1.1 truthfully fills them)
**Depends on**: Phase 3 (a successful live draft must run before its tool-call events can be observed and recorded)
**Requirements**: PROV-01, PROV-02
**Success Criteria** (what must be TRUE):

  1. After a successful live draft, `provenance.yaml`'s `context_origins` is non-empty and lists what the agent actually read, derived from observed tool-call events
  2. The recorded `context_origins` is kept distinct from the human-pointed `sources` — it reflects what was read, not what was pointed at
  3. After a successful live draft, `provenance.yaml`'s `tools_used` is non-empty and lists the tools the agent actually invoked, derived from observed tool-call events
  4. The same provenance population is exercised by a unit test against a fake/stub SDK that emits tool-call events (manual-only live path stays out of CI)

**Plans**: TBD
**UI hint**: no

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Compliant Scaffold & Provider-Seam Boundary | v1.0 | 4/4 | Complete | 2026-06-19 |
| 2. Walking Skeleton, Planning Schema, Provable HITL & Observability | v1.0 | 4/4 | Complete | 2026-06-20 |
| 3. Live Copilot path runs out of the box | v1.1 | 2/2 | Complete    | 2026-06-22 |
| 4. Honest observed provenance | v1.1 | 0/? | Not started | - |
