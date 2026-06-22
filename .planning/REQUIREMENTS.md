# Requirements: Agentic Documentation Drafting Framework

**Defined:** 2026-06-22
**Milestone:** v1.1 — Live Copilot Path Hardening
**Core Value:** A TA (or anyone acting in that capacity) can reliably draft review-ready documentation faster than from scratch, with a human owning intent and review at every step — "quality at speed," without AI slop.

> **Milestone scope.** v1.1 is a **brownfield hardening** milestone — no net-new domain features. v1.0 proved the Mode-A loop on the deterministic mock and a contrived live run; the first real `dogen draft --provider copilot` run surfaced four concrete gaps that make the live path unusable out of the box and leave its audit surface blind. This milestone closes exactly those four gaps. The live path is **manual-only** (D-24, kept out of CI — no token or network in CI), so these requirements are validated by manual live runs plus unit tests against a fake/stub SDK. The wider framework vision (v2 destination) is archived in [milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) and is unchanged.

## v1.1 Requirements

The thinnest set of fixes that makes the real Copilot drafting path run end-to-end out of the box and record honest provenance.

### Live Drafting Path (LIVE) — the real `--provider copilot` loop works out of the box

- [x] **LIVE-01**: Operator can choose the drafting model on `dogen draft` (e.g. a `--model` option), and the default is a model available on a standard Copilot account — the hardcoded, unavailable `gpt-5` default is retired *(Finding 1)*
- [x] **LIVE-02**: In a non-interactive run the agent can actually read the human-pointed sources — the Copilot provider supplies a permission handler that auto-approves the already-read-only lookup allowlist (`grep`/`glob`/`view`), so source reads are not denied. Auto-approval is safe because the toolset is read-only with write/exec/network already denied *(Finding 2)*
- [x] **LIVE-03**: Drafting succeeds on any available model regardless of family — the provider sends `reasoning_effort` only to models that accept it (GPT-5 family) and omits it for Claude-family models that reject it, so selecting a Claude model no longer errors on the parameter *(Finding 3)*

### Live Error Mapping (ERR) — clean failures, never a raw traceback (closes accepted debt #4)

- [x] **ERR-01**: When the backend rejects the requested model (e.g. a JSON-RPC `-32603 Model "X" is not available`), `dogen draft` exits nonzero with a clear, actionable message naming the rejected model — never a raw `JsonRpcError` traceback *(Finding 1 / known debt item #4)*
- [x] **ERR-02**: Other live backend / JSON-RPC errors raised on the draft path are classified into a handled failure with a clear message and a nonzero exit — extending the v1.0 "backend unavailable" handling across the live-error surface — never an uncaught crash *(Finding 1, generalised)*

### Honest Provenance (PROV) — the audit surface reflects what actually happened (completes BL-01)

- [x] **PROV-01**: After a successful live draft, `provenance.yaml`'s `context_origins` lists what the agent actually read, derived from the session's observed tool-call events and kept distinct from the human-pointed `sources` — it is no longer left empty *(Finding 4)*
- [x] **PROV-02**: After a successful live draft, `provenance.yaml`'s `tools_used` lists the tools the agent actually invoked, derived from the session's observed tool-call events — it is no longer left empty *(Finding 4)*

## Future Requirements

The v2 destination (Steering Quality & Type-Aware Generation, Onboarding/Style Scraper, Evidence-Gated Actionable Verification, SDLC Connectors & Portfolio Scale, Context Augmentation, Mode B) is tracked unchanged in the archived [milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) v2 block. Promoting any of it requires a new milestone; none of it is in v1.1.

## Out of Scope

Explicitly excluded from v1.1 to prevent scope creep.

| Feature | Reason |
|---------|--------|
| An always-on live drafting smoke test in CI | The live Copilot path stays manual-only (D-24) — CI has no token or network; v1.1 adds unit tests against a fake/stub SDK, not a live CI call |
| Model auto-discovery / a "list available models" subsystem | Beyond the four findings; a clear error that names the rejected model (ERR-01) is sufficient — discovery is a separate capability |
| Interactive / streaming permission prompts (human-approves-each-read UX) | v1.1 auto-approves the read-only allowlist; an interactive permission UI is out of scope and unnecessary while the toolset is read-only |
| Broadening the agent toolset beyond `grep`/`glob`/`view` | The read-only allowlist is the security boundary (SKEL-04/D-28); v1.1 does not add tools, only lets the existing ones run |
| Retroactively re-running or backfilling v1.0 dogfood provenance | v1.1 fixes the live path forward; existing recorded artifacts are left as historical evidence |
| Any committing / pushing / PR / build / publish step | Unchanged hard border — framework stays "dumb" outside drafting (SKEL-03) |

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LIVE-01 | Phase 3 | Complete |
| LIVE-02 | Phase 3 | Complete |
| LIVE-03 | Phase 3 | Complete |
| ERR-01 | Phase 3 | Complete |
| ERR-02 | Phase 3 | Complete |
| PROV-01 | Phase 4 | Complete |
| PROV-02 | Phase 4 | Complete |

**Coverage:**

- v1.1 requirements: 7 total
- Mapped to phases: 7 (Phase 3: LIVE-01/02/03 + ERR-01/02; Phase 4: PROV-01/02)
- Unmapped: 0
- Orphaned: 0

---
*Requirements defined: 2026-06-22*
*Last updated: 2026-06-22 after roadmap creation (Phases 3-4 mapped)*
