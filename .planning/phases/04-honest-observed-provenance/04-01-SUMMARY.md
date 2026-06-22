---
phase: 04-honest-observed-provenance
plan: 01
subsystem: api
tags: [copilot-sdk, provenance, seam, mapping, tdd, pytest-asyncio]

# Dependency graph
requires:
  - phase: 03-live-copilot-path
    provides: "Working live draft (CopilotDraftingProvider, READONLY grep/glob/view session, mapping.to_draft_result) — the path whose tool-call events Phase 4 observes"
provides:
  - "tool_events_to_provenance(events) -> (context_origins, tools_used) — the pure seam helper that translates observed TOOL_EXECUTION_START events to two plain str lists"
  - "provider._run_draft observes session.get_events() inside the open session block and attaches both lists via model_copy(update=...)"
  - "_StubSession.get_events() in the shared conftest (default empty = honest-empty), threaded through _StubClient/install_stub_client"
  - "tests/test_copilot_provenance.py — pure-helper translation tests + fake-SDK end-to-end provenance tests (criterion 4)"
affects: [provenance, audit, copilot-adapter, seam]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Observe-then-translate: read full session history with get_events() inside the open session block, translate in a pure mapping helper (provider stays a thin orchestration site)"
    - "Named-constant centralisation of CLI-owned arg keys (_VIEW_PATH_KEY) so a runtime drift is a one-line localised fix"

key-files:
  created:
    - "tests/test_copilot_provenance.py"
  modified:
    - "src/dogen/adapters/copilot/mapping.py"
    - "src/dogen/adapters/copilot/provider.py"
    - "tests/conftest.py"

key-decisions:
  - "Implemented tool_events_to_provenance as a SEPARATE pure sibling of to_draft_result (Claude's discretion under D-04) — keeps to_draft_result unchanged and makes the translation independently unit-testable (D-06)"
  - "Filter SessionEventType.TOOL_EXECUTION_START exclusively — name/arguments ride only on START; COMPLETE carries neither (RESEARCH Pitfall 1) — confirms the RESEARCH correction over CONTEXT.md's ToolInvocation"
  - "Only view's path qualifies as a context origin; grep/glob record the builtin:<name> tool but no origin (their path is a search scope, omit-on-doubt, D-02)"
  - "Defensive getattr + isinstance(args, dict) + isinstance(path, str) guards — a malformed/None-arg event degrades to honest-empty, never crashes the draft (T-04-01, Pitfall 2)"
  - "get_events() called INSIDE the async-with session block (Pitfall 3 — it raises once the session closes)"

patterns-established:
  - "Provenance attach point: provider extends the existing model_copy(update=...) call (alongside effort_used) rather than adding a new attach mechanism"
  - "Honest-empty default everywhere: _StubSession events default to [] so existing happy-path tests stay green and no-tool drafts honestly record empty lists (D-05/BL-01)"

requirements-completed: [PROV-01, PROV-02]

# Metrics
duration: 12min
completed: 2026-06-22
status: complete
---

# Phase 4 Plan 01: Honest Observed Provenance Summary

**Adapter-only PROV-01/02: a pure `tool_events_to_provenance` seam helper plus a `get_events()` observation in `_run_draft` now fill `context_origins`/`tools_used` from observed `TOOL_EXECUTION_START` events — view paths as origins, `builtin:<name>` as tools, first-seen de-duped, honest-empty when nothing is observed.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-22T11:44:00Z (approx)
- **Completed:** 2026-06-22T11:56:00Z
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- New pure `tool_events_to_provenance(events) -> tuple[list[str], list[str]]` in `mapping.py`: the single seam translation, returning plain `str` lists only (no SDK shape crosses to `core/`).
- `provider._run_draft` observes `session.get_events()` inside the open session block and attaches both lists via the existing `model_copy(update=...)`.
- Shared `_StubSession.get_events()` (default empty) threaded through `_StubClient`/`install_stub_client`, keeping `conftest` SDK-free at collection (WR-02) and all happy-path tests green.
- New `tests/test_copilot_provenance.py`: 8 pure-helper translation tests + 2 fake-SDK end-to-end tests (criterion 4) proving scripted `TOOL_EXECUTION_START` events populate the `DraftResult`, and honest-empty when none.

## Task Commits

Each task was committed atomically (TDD RED → GREEN per task 2/3):

1. **Task 1: Wave-0 test scaffold (_StubSession.get_events + provenance test file)** - `ac2b99e` (test)
2. **Task 2: pure helper — RED** - `29019b1` (test)
2. **Task 2: pure helper — GREEN** - `cce2620` (feat)
3. **Task 3: provider observation — RED** - `694c34d` (test)
3. **Task 3: provider observation — GREEN** - `8fe228d` (feat)

_Note: REFACTOR for Task 2 (named constants `_CONTENT_READ_TOOLS`/`_VIEW_PATH_KEY`/`_BUILTIN_PREFIX`) was folded into the GREEN commit since the constants are part of the verified RESEARCH recipe — no behaviour change beyond GREEN._

## TDD Gate Compliance

Both behaviour-adding tasks followed the gate sequence (verified in git log): a `test(...)` RED commit precedes each `feat(...)` GREEN commit (Task 2: `29019b1` → `cce2620`; Task 3: `694c34d` → `8fe228d`). Task 1 is a pure test-scaffold task (no source behaviour), committed as `test(...)`.

## Files Created/Modified
- `src/dogen/adapters/copilot/mapping.py` - Added `tool_events_to_provenance` pure helper + `_CONTENT_READ_TOOLS`/`_VIEW_PATH_KEY`/`_BUILTIN_PREFIX` constants; extended the `copilot` import with `SessionEventType`. `to_draft_result` unchanged.
- `src/dogen/adapters/copilot/provider.py` - `_run_draft` now reads `events = await session.get_events()` inside the session block and extends `model_copy(update=...)` with `context_origins`/`tools_used`; import extended with `tool_events_to_provenance`.
- `tests/conftest.py` - `_StubSession.get_events()` (default empty) + an `events` arg threaded through `_StubSession`/`_StubClient`/`install_stub_client`, mirroring `send_error`. Stays SDK-free at collection.
- `tests/test_copilot_provenance.py` - NEW (SPDX header): `_tool_start`/`_tool_complete` builders (function-local copilot import), 8 pure-helper tests, 2 fake-SDK end-to-end tests.

## Decisions Made
See `key-decisions` in frontmatter. The headline call was the RESEARCH correction over CONTEXT.md: the event carrier is `TOOL_EXECUTION_START`/`ToolExecutionStartData` (filtered START-only), NOT `ToolInvocation`, and `view.arguments["path"]` is the only origin source.

## Deviations from Plan

None - plan executed exactly as written. (One mechanical lint fixup: ruff `UP017` rewrote the test builders' `datetime.now(timezone.utc)` — copied from RESEARCH — to `datetime.now(UTC)`. In-scope formatting of code created this task, committed in the Task 3 GREEN commit; not a behavioural deviation.)

## Issues Encountered
- `reuse lint` reports 4 missing-SPDX files, all under the untracked `temp/.dogen/` live-run artifact directory (the 2026-06-20 run, explicitly left as-is per RESEARCH "Runtime State Inventory"). Out of scope and untracked — not committed. The new test file carries the mandatory SPDX header (161/165 files compliant; the 4 are the temp artifacts).

## User Setup Required
None - no external service configuration required. The criterion-4 proof is the CI-runnable fake-SDK test. The D-24 manual live run (one `dogen draft --provider copilot` confirming non-empty `context_origins`/`tools_used` in a real `provenance.yaml`) remains a separate, human-only verification step, deliberately out of CI (no token/network).

## Self-Check: PASSED

- `src/dogen/adapters/copilot/mapping.py` — FOUND (helper present)
- `src/dogen/adapters/copilot/provider.py` — FOUND (get_events observation present)
- `tests/test_copilot_provenance.py` — FOUND
- `tests/conftest.py` — FOUND (get_events present)
- Commits `ac2b99e`, `29019b1`, `cce2620`, `694c34d`, `8fe228d` — all FOUND in git log
- Full suite: 131 passed; seam guards green; `does_not_fabricate` regression green; ruff/format/ty clean on modified non-test files.

## Next Phase Readiness
- PROV-01/02 are CI-provable; this closes the fourth and last gap the 2026-06-20 live run surfaced (BL-01 honesty work complete: v1.0 stopped fabricating; v1.1 truthfully fills).
- The only remaining v1.1 verification is the D-24 manual live run (human-only). No code blockers.

---
*Phase: 04-honest-observed-provenance*
*Completed: 2026-06-22*
