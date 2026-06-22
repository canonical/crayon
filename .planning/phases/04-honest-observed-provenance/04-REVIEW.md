---
phase: 04-honest-observed-provenance
reviewed: 2026-06-22T12:02:50Z
depth: deep
files_reviewed: 4
files_reviewed_list:
  - src/dogen/adapters/copilot/mapping.py
  - src/dogen/adapters/copilot/provider.py
  - tests/conftest.py
  - tests/test_copilot_provenance.py
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-22T12:02:50Z
**Depth:** deep
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the observed-provenance change (PROV-01/02): a pure `tool_events_to_provenance(events)` helper in `mapping.py`, its wiring in `provider._run_draft` via `session.get_events()` + `model_copy`, the shared fake-SDK harness extension in `conftest.py`, and the new `test_copilot_provenance.py` suite.

The core helper is **correct on every property I traced**: START-only filtering avoids the COMPLETE double-count (verified against the real `ToolExecutionStartData`/`ToolExecutionCompleteData` shapes in the installed SDK — `tool_name`/`arguments` ride only on START), first-seen de-dup is sound (`not in` guards), the `view`→`path`→origin extraction is defensively guarded against `None`/non-dict/non-str (no crash path found), and the honest-empty contract holds (empty lists when nothing observed; `sources` are never substituted — confirmed in `orchestrator._record_generation`). The anti-corruption SEAM is intact: the helper returns plain `list[str]`, and `SessionEvent`/`SessionEventType` imports stay confined to `adapters/copilot/`. REUSE SPDX headers are present on all files. All 130 tests pass.

No BLOCKER-class defects (no crashes, no injection, no honest-empty violation, no double-count, no seam leak). The findings below are honesty/coverage concerns: provenance comments and a test-module docstring **claim observation guarantees the code does not actually provide**, which is precisely the failure class this phase exists to prevent. None falsify a recorded value at runtime today, so they are WARNINGs, not BLOCKERs.

## Warnings

### WR-01: `effort_used` records the *requested* effort but provenance comments claim it is the *observed* effort

**File:** `src/dogen/adapters/copilot/provider.py:289-300`, reinforced by `src/dogen/core/orchestrator.py:280-283`

**Issue:** The provider attaches `"effort_used": self._effort` — the value the operator *requested* — while the surrounding comment states "report the effort the SDK actually ran at, so the recorded provenance reflects the real effort rather than only the requested one." The orchestrator then treats `result.effort_used` as the authoritative single-source-of-truth, overriding `request.effort` ("the effort the provider actually ran at"). Nothing in the path observes the SDK's actual effort; the SDK-reported effort is never read. The result is a requested value dressed up as an observed one — the same dishonest-provenance pattern (representing intent as observation) that PROV-01/02 / BL-01 / D-37 were created to eliminate for `context_origins`. This is a pre-existing line (IN-03, phase 3), but this diff re-touches the exact `model_copy` block and keeps the misleading comment, so it is in scope.

**Fix:** Either (a) observe the real effort from the SDK if it is reported (e.g. on the assistant-message event or a session-config event) and attach that, falling back to `None` when absent; or (b) if the SDK does not report it, set `effort_used=None` here and let the orchestrator's `result.effort_used or request.effort` honestly fall back to the requested value, and correct both comments to say the requested effort is recorded because the backend does not report an observed one. Do not keep a comment that asserts observation while the code copies a request.

### WR-02: Test-module docstring overclaims end-to-end coverage that the tests do not exercise

**File:** `tests/test_copilot_provenance.py:26-30`

**Issue:** The module docstring states the end-to-end layer "asserts the populated lists reach the `DraftResult` **and the recorded `Generation` through the orchestrator's verbatim copy**." Neither `test_draft_populates_provenance_from_observed_events` nor `test_draft_honest_empty_when_no_events` invokes the orchestrator or `_record_generation`, nor constructs/asserts a `Generation`. They assert only `result.context_origins` / `result.tools_used` on the `DraftResult`. The `DraftResult → Generation` hop (`orchestrator.py:291-292`) — the step that actually proves the honest-empty contract survives into the on-disk audit record — is untested by this suite. A reader trusting the docstring believes the orchestrator copy is covered when it is not.

**Fix:** Either add an end-to-end assertion that drives a draft through the orchestrator and checks the resulting `Generation.context_origins`/`Generation.tools_used` match (and that empty stays empty, never substituted with `unit.sources`), or correct the docstring to state coverage stops at `DraftResult`.

### WR-03: The fake `_StubAssistantData.model_version` masks that the real SDK event has no `model_version` field

**File:** `tests/conftest.py:67-89` (stub), affecting `src/dogen/adapters/copilot/mapping.py:85`

**Issue:** `mapping.to_draft_result` reads `getattr(data, "model_version", None) or _UNKNOWN_MODEL_VERSION`. The installed SDK's `AssistantMessageData` (verified: `copilot/generated/session_events.py:455-473`) has **no `model_version` attribute** — so against a real event this `getattr` always returns `None` and `model_version` is always `"unknown"`. The conftest stub, however, defines `model_version: str = "gpt-5-mini-2026-01"`, so every test sees a populated version that production can never produce. This is a false-confidence stub: it tests a field shape the SDK does not deliver, hiding that the live provenance record will always carry `"unknown"`. (Not in this diff's primary changeset, but the harness is in scope and the stub field actively misleads.)

**Fix:** Drop `model_version` from `_StubAssistantData` (or add a test asserting that a real-shaped event with no `model_version` yields `"unknown"`), so the harness reflects the actual SDK surface and the always-`unknown` outcome is visible/intentional rather than masked.

## Info

### IN-01: `builtin:` prefix is unconditional and relies entirely on the locked allowlist — no guard if MCP tools are ever added

**File:** `src/dogen/adapters/copilot/mapping.py:135`

**Issue:** Every observed tool is recorded as `builtin:<tool_name>`. This is correct *today* only because `tools.READONLY` exposes solely built-ins (`grep`/`glob`/`view`) and MCP is impossible, so `mcp_server_name` is always `None` (the real `ToolExecutionStartData` does carry `mcp_server_name`/`mcp_tool_name`). If a future phase adds an MCP server to the session, this helper would silently mislabel MCP tool calls as `builtin:`, producing a dishonest tool identifier with no failing test. The coupling between this constant and `tools.py`'s allowlist is implicit.

**Fix:** Add a defensive branch: if `getattr(data, "mcp_server_name", None)` is set, qualify with the MCP source (or omit-on-doubt) instead of `builtin:`. At minimum, leave a comment cross-linking `_BUILTIN_PREFIX` to the `tools.READONLY` invariant so the assumption is discoverable when the allowlist changes.

### IN-02: `_VIEW_PATH_KEY = "path"` is the load-bearing extraction key but rests on a single manual run

**File:** `src/dogen/adapters/copilot/mapping.py:48`, `142`

**Issue:** The entire `context_origins` signal depends on `view`'s argument dict using the key `"path"`. The code correctly degrades to honest-empty if the key is wrong (no crash — verified), and the docstring acknowledges "confirmed by one manual run." But if the real `view` tool uses a different key (e.g. `file`, `filename`), `context_origins` is silently always-empty in production while every CI test passes (the tests construct the argument dict with `"path"` themselves, so they can never catch a key mismatch). This is a verification gap, not a runtime defect, and the manual-only live path (D-24) limits how far it can be closed in CI.

**Fix:** Capture the real `view` argument-key shape in `.planning/intel/` from a live probe and cite it next to `_VIEW_PATH_KEY`, so the constant is grounded in recorded evidence rather than memory. Optionally assert the key against a captured fixture of a real `view` START event.

### IN-03: `output_tokens=0` and `model="unknown"` fallbacks can record indistinguishably from a genuine zero/unknown

**File:** `src/dogen/adapters/copilot/mapping.py:84`, `86`

**Issue:** `output_tokens = getattr(data, "output_tokens", None) or 0` coerces both "field absent/None" and "field is genuinely 0" to `0`, and `model` coerces absent/None to `"unknown"`. For a provenance/audit record, "the backend did not report tokens" and "the backend reported 0 tokens" are different facts; collapsing them slightly weakens the audit signal. Low severity — `0`/`"unknown"` are reasonable honest defaults and the domain model requires concrete values — but worth noting given the phase's honesty theme.

**Fix:** Acceptable as-is for v0. If audit fidelity later matters, consider `output_tokens: int | None` on `DraftResult` to distinguish unreported from zero.

---

_Reviewed: 2026-06-22T12:02:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
