---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Live Copilot Path Hardening
current_phase: 3
status: planning
stopped_at: Phase 3 context gathered
last_updated: "2026-06-22T09:00:59.537Z"
last_activity: 2026-06-22
last_activity_desc: v1.1 roadmap created (Phases 3-4, 7/7 requirements mapped)
progress:
  total_phases: 2
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-22 — v1.1 Live Copilot Path Hardening milestone started)

**Core value:** A TA (or anyone acting in that capacity) can reliably draft review-ready documentation faster than from scratch, with a human owning intent and review at every step — "quality at speed," without AI slop.
**Current focus:** v1.1 roadmap created (Phases 3-4) — closing the four live-Copilot gaps; ready to plan Phase 3.

## Current Position

Phase: 3 — Live Copilot path runs out of the box (not started)
Plan: —
Status: Roadmap created — ready for `/gsd-plan-phase 3`
Last activity: 2026-06-22 — v1.1 roadmap created (Phases 3-4, 7/7 requirements mapped)

## Performance Metrics

**Velocity:**

- Total plans completed: 8
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 4 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 2 | 2 tasks | 4 files |
| Phase 01 P02 | 6 | 3 tasks | 12 files |
| Phase 01 P03 | 3 | 2 tasks | 11 files |
| Phase 01 P04 | 14 | 3 tasks | 4 files |
| Phase 02 P01 | 40min | 3 tasks | 13 files |
| Phase 02 P02 | 45min | 3 tasks | 10 files |
| Phase 02 P03 | ~50min | 2 tasks | 12 files |
| Phase 02 P04 | 25min | 2 tasks | 16 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v1.1 is a brownfield hardening milestone — no net-new domain features; closes exactly the four gaps the first real live `dogen draft --provider copilot` run surfaced (7 requirements: LIVE-01/02/03, ERR-01/02, PROV-01/02).
- Roadmap split into 2 phases (coarse granularity): Phase 3 = "live path runs out of the box" (LIVE-01/02/03 + clean error mapping ERR-01/02, same code surface, one live-run verification); Phase 4 = "honest observed provenance" (PROV-01/02, depends on a working live draft to observe tool-call events).
- Implementation surface is almost entirely the single Copilot adapter (`src/dogen/adapters/copilot/provider.py`, `mapping.py`, `tools.py`) plus the existing orchestrator/CLI seam.
- Live path stays manual-only (D-24, out of CI — no token/network). Verification = manual live runs PLUS unit tests against a fake/stub SDK; no CI live-call gate is added (explicitly out of scope).
- ERR-01 closes accepted v1.0 tech-debt item #4 (raw `JsonRpcError` traceback on model rejection); PROV-01/02 complete the BL-01 honesty work (v1.0 stopped fabricating provenance; v1.1 truthfully fills it).
- Milestone scope = MVP: walking skeleton (A2) + planning schema v0 (F1) + foundations (seam, observability, licensing). v2 destination deferred. *(v1.0)*
- A2 and F1 are inseparable — kept together in Phase 2. *(v1.0)*
- The provider-seam boundary + CI guardrail + REUSE licensing are commit-1 foundations — set in Phase 1 before any drafting logic. *(v1.0)*

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

None open. Carried context from the first live run (see MEMORY.md "Live Copilot path findings") is exactly what Phases 3-4 address:

- gpt-5 unavailable on a standard account → LIVE-01 (operator-selectable model + available default).
- No permission handler → non-interactive `grep`/`glob`/`view` reads denied → LIVE-02 (auto-approve read-only allowlist).
- `reasoning_effort` rejected by Claude-family models → LIVE-03 (model-family-aware parameter).
- Empty `context_origins`/`tools_used` → PROV-01/02 (populate from observed tool-call events).
- Raw `JsonRpcError` traceback on model rejection → ERR-01/02 (clean handled failure + nonzero exit).

Carried tech debt (cosmetic, CI green): SKEL-02 tags-only bookkeeping (v1.0). The live-backend error-mapping breadth item is now scheduled work (ERR-01/02), not carried debt.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260620-sa1 | Fix two CI-red gates from v1.0 audit (reuse-lint prose false-positives + ty test-double); also fixed a third pre-existing ruff-format gate | 2026-06-20 | e9cede0 | [260620-sa1-fix-two-ci-red-gates-from-v1-0-audit-reu](./quick/260620-sa1-fix-two-ci-red-gates-from-v1-0-audit-reu/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-22T09:00:59.533Z
Stopped at: Phase 3 context gathered
Resume file: .planning/phases/03-live-copilot-path-runs-out-of-the-box/03-CONTEXT.md

## Operator Next Steps

- Plan the first v1.1 phase: `/gsd-plan-phase 3`
