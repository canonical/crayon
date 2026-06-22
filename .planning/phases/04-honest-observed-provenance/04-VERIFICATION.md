---
phase: 04-honest-observed-provenance
verified: 2026-06-22T00:00:00Z
status: verified
human_verified: 2026-06-22T13:20:00Z
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Run `dogen draft --provider copilot` against a real Copilot account and inspect the generated `provenance.yaml`"
    expected: "`context_origins` is non-empty and lists the file paths the agent actually read via the `view` tool; `tools_used` is non-empty and lists the `builtin:<name>` identifiers the agent invoked — both derived from live session events, not from `unit.sources`"
    why_human: "The live Copilot path is manually-only (D-24) — CI has no token or network access. The fake-SDK tests prove the code path works with scripted events; only a real session confirms the SDK actually emits `TOOL_EXECUTION_START` events with `arguments[\"path\"]` populated as expected in production."
    outcome: "CONFIRMED 2026-06-22 via /gsd-verify-work 4 (UAT Test 1 = pass). Operator ran the live draft and confirmed `context_origins`/`tools_used` were populated from observed session events, distinct from `sources`."
---

# Phase 4: Honest Observed Provenance Verification Report

**Phase Goal:** After a successful live draft the audit surface reflects what actually happened — `context_origins` and `tools_used` are populated from the session's observed tool-call events, completing the BL-01 honesty work (v1.0 stopped fabricating them; v1.1 truthfully fills them)
**Verified:** 2026-06-22
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After a draft that observed read tools, `DraftResult.context_origins` lists the view-read file paths (first-seen, de-duped), non-empty (PROV-01) | ✓ VERIFIED (live) | Code path fully implemented and wired; fake-SDK test `test_draft_populates_provenance_from_observed_events` passes with scripted events. **D-24 live confirmation passed 2026-06-22** (UAT Test 1): a real `dogen draft --provider copilot` run populated `context_origins` from observed `view` reads. |
| 2 | `context_origins` records what was READ (view path), kept distinct from the human-pointed `unit.sources` — never copied from sources (PROV-01 / D-02 / D-37) | ✓ VERIFIED | `_record_generation` (orchestrator.py:250–297) receives only `result`, not `unit.sources`. `context_origins=list(result.context_origins)` at line 291. The docstring at line 259 explicitly names the D-37 ban. `test_generation_does_not_fabricate_context_origins` passes (1 passed). |
| 3 | After a draft that observed tools, `DraftResult.tools_used` lists `builtin:<name>` identifiers (first-seen, de-duped), non-empty (PROV-02) | ✓ VERIFIED (live) | Code path fully implemented and wired; fake-SDK test `test_draft_populates_provenance_from_observed_events` passes with scripted events. **D-24 live confirmation passed 2026-06-22** (UAT Test 1): a real `dogen draft --provider copilot` run populated `tools_used` with `builtin:<name>` identifiers from observed events. |
| 4 | A fake-SDK test whose stub `session.get_events()` emits scripted `TOOL_EXECUTION_START` events drives the full provider→orchestrator path and asserts the populated lists reach the recorded `Generation` (criterion 4 / D-06) | ✓ VERIFIED | `tests/test_copilot_provenance.py`: 10/10 tests pass. `test_draft_populates_provenance_from_observed_events` and `test_draft_honest_empty_when_no_events` drive `CopilotDraftingProvider` with a stubbed SDK session whose `get_events()` returns scripted events; both assert on `DraftResult.context_origins` and `tools_used`. Confirmed by running `uv run pytest tests/test_copilot_provenance.py -v` — 10 passed. |
| 5 | When no tool-execution events are observed, both lists stay honestly empty — `test_generation_does_not_fabricate_context_origins` still passes (D-05 / BL-01) | ✓ VERIFIED | `uv run pytest tests/test_orchestrator_hitl.py -k does_not_fabricate -v` — 1 passed. `test_draft_honest_empty_when_no_events` also passes. `_StubSession.get_events()` defaults to `[]` — existing happy-path tests remain green. |
| 6 | No SDK shape (`SessionEvent` / `SessionEventType` / `ToolExecutionStartData`) crosses into `core/` — `tests/test_seam.py` and `tests/test_seam_importlinter.py` still pass (D-04 / SEAM-01/03) | ✓ VERIFIED | `uv run pytest tests/test_seam.py tests/test_seam_importlinter.py -v` — 2 passed. `tool_events_to_provenance` returns `tuple[list[str], list[str]]` only. `conftest.py` has zero top-level `from copilot` / `import copilot` lines (confirmed by grep returning empty). |

**Score:** 6/6 truths verified (the 2 previously D-24-gated truths confirmed by the live run on 2026-06-22; 0 failed)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/dogen/adapters/copilot/mapping.py` | Pure `tool_events_to_provenance(events) -> tuple[list[str], list[str]]` seam helper | ✓ VERIFIED | Function exists at line 96–145. Contains `_CONTENT_READ_TOOLS`, `_VIEW_PATH_KEY`, `_BUILTIN_PREFIX` named constants. Full NumPy docstring, correct type annotations, defensive `getattr`/`isinstance` guards. |
| `src/dogen/adapters/copilot/provider.py` | `_run_draft` observes `get_events()` and attaches both lists via `model_copy` | ✓ VERIFIED | `events = await session.get_events()` at line 285 — inside `async with session_cm as session:` block (line 281). `tool_events_to_provenance(events)` called at line 288. `model_copy(update={"effort_used": ..., "context_origins": context_origins, "tools_used": tools_used})` at lines 294–300. |
| `tests/test_copilot_provenance.py` | Pure-helper translation tests + fake-SDK end-to-end provenance test (criterion 4) | ✓ VERIFIED | File exists with SPDX header. Contains `_tool_start`, `_tool_complete` builders with function-local copilot imports. 8 pure-helper tests + 2 fake-SDK end-to-end tests. All 10 pass. |
| `tests/conftest.py` | `_StubSession.get_events()` returning scripted (default empty) tool-event history | ✓ VERIFIED | `async def get_events(self)` at line 189, returning `list(self._events)`. `events` arg threaded through `_StubClient.__init__` → `create_session` → `_StubSession.__init__`. `install_stub_client` fixture exposes `events=` parameter. No top-level `from copilot` import. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/dogen/adapters/copilot/provider.py` | `src/dogen/adapters/copilot/mapping.py` | `_run_draft` calls `tool_events_to_provenance(events)` and attaches both lists via `model_copy(update=...)` | ✓ WIRED | Import at line 59; call at line 288; attach at lines 294–300. |
| `src/dogen/adapters/copilot/provider.py` | `github-copilot-sdk session` | `events = await session.get_events()` inside `async with session` block, after `send_and_wait` | ✓ WIRED | Line 285 inside block opened at line 281. Order: `send_and_wait` (line 282) then `get_events` (line 285), both inside the open session. |
| `src/dogen/core/orchestrator.py` | `provenance.yaml` | `_record_generation` copies `result.context_origins`/`result.tools_used` verbatim, never `unit.sources` | ✓ WIRED | Lines 291–292: `context_origins=list(result.context_origins)`, `tools_used=list(result.tools_used)`. `_record_generation` receives no `unit` argument — `sources` cannot be accidentally copied. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `provider.py:_run_draft` | `events` | `await session.get_events()` inside open session block | Yes (scripted in fake-SDK tests; real SDK events in live run) | ✓ FLOWING (CI-proven via fake-SDK) |
| `mapping.py:tool_events_to_provenance` | `context_origins`, `tools_used` | Iterates `events`, filters `TOOL_EXECUTION_START`, reads `tool_name`/`arguments` defensively | Yes | ✓ FLOWING |
| `orchestrator.py:_record_generation` | `Generation.context_origins`, `Generation.tools_used` | `list(result.context_origins)`, `list(result.tools_used)` — verbatim copy from `DraftResult` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Pure-helper tests (8 cases: view→origin, dedup, grep/glob no origin, ordering, empty, malformed, COMPLETE-only) | `uv run pytest tests/test_copilot_provenance.py -v` | 10 passed in 0.01s | ✓ PASS |
| Fake-SDK end-to-end: scripted events populate `DraftResult` | `uv run pytest tests/test_copilot_provenance.py::test_draft_populates_provenance_from_observed_events -v` | PASSED | ✓ PASS |
| Honest-empty regression | `uv run pytest tests/test_orchestrator_hitl.py -k does_not_fabricate -v` | 1 passed | ✓ PASS |
| Seam guards | `uv run pytest tests/test_seam.py tests/test_seam_importlinter.py -v` | 2 passed | ✓ PASS |
| Full suite | `uv run pytest -q` | 131 passed in 1.52s | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PROV-01 | 04-01-PLAN.md | After a successful live draft, `provenance.yaml`'s `context_origins` lists what the agent actually read, derived from observed tool-call events and distinct from `sources` | ✓ SATISFIED (CI) / D-24 live confirmation pending | `tool_events_to_provenance` maps `view` events to origins; orchestrator copies verbatim from `result`, never from `sources`; fake-SDK test proves the path. Live run is D-24 human-only. |
| PROV-02 | 04-01-PLAN.md | After a successful live draft, `provenance.yaml`'s `tools_used` lists the tools the agent actually invoked, derived from observed tool-call events | ✓ SATISFIED (CI) / D-24 live confirmation pending | `tool_events_to_provenance` maps all `TOOL_EXECUTION_START` events to `builtin:<name>` identifiers; fake-SDK test proves the path. Live run is D-24 human-only. |

No orphaned requirements. PROV-01 and PROV-02 are the only Phase 4 requirements in REQUIREMENTS.md. Both are mapped and covered.

### Anti-Patterns Found

No debt markers (TBD/FIXME/XXX) found in any of the four files modified this phase. No stubs, hardcoded empty returns, or placeholder implementations found.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

### Advisory Notes (non-blocking, from code review)

WR-01: `effort_used` in the provenance record reflects the *requested* effort rather than confirmed observed effort (pre-existing Phase 3 `IN-03` code in the `model_copy` attach point, outside PROV-01/02 scope). Not a gap for this phase.

### Human Verification Required

#### 1. Live Draft Provenance Confirmation (D-24) — ✅ CONFIRMED 2026-06-22

**Outcome:** Passed via `/gsd-verify-work 4` (UAT Test 1 = pass). The operator ran a live `dogen draft --provider copilot` and confirmed the latest `generations[]` entry had non-empty `context_origins` (observed `view` reads) and `tools_used` (`builtin:<name>`), distinct from `unit.sources`. The real Copilot CLI runtime emits `TOOL_EXECUTION_START` events with `arguments["path"]` populated as the bundled-schema probe predicted (RESEARCH open question A1 closed).

**Test:** Run `dogen draft --provider copilot` with real Copilot credentials against a unit that has sources and recorded steering. After the draft completes, inspect the generated `provenance.yaml` and read the latest `generations[]` entry.

**Expected:**
- `context_origins` is non-empty, listing the file path(s) the agent read via the `view` tool (e.g. `["README.md"]` if the agent viewed README.md during the draft)
- `tools_used` is non-empty, listing the `builtin:<name>` identifiers the agent invoked (e.g. `["builtin:view", "builtin:grep"]`)
- Neither list matches `unit.sources` verbatim (they reflect what was observed, not what was pointed)
- If the agent happened not to use any tools during the draft, both lists are honestly empty (`[]`) — that is correct behaviour, not a bug

**Why human:** The live Copilot path is deliberately kept out of CI (D-24 — no token or network in CI). The fake-SDK tests prove the code path is correct with scripted events; only a live session can confirm the real Copilot CLI runtime emits `TOOL_EXECUTION_START` events in the expected shape with `arguments["path"]` populated for `view` reads. This is the same category of check that Phase 3 ended awaiting.

---

## Gaps Summary

No gaps. All six must-haves are fully verified — including the D-24 manual live run, which was confirmed on 2026-06-22 via `/gsd-verify-work 4`. The implementation is complete and the live audit surface is honest.

---

_Verified: 2026-06-22_
_Verifier: Claude (gsd-verifier)_
