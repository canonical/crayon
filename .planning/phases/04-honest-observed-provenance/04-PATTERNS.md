# Phase 4: Honest observed provenance - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 3 (2 modified, 1 created)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/dogen/adapters/copilot/mapping.py` (MODIFY) | adapter/seam-translator | transform (event → domain list) | `to_draft_result` in the same file | exact (same file, same role) |
| `src/dogen/adapters/copilot/provider.py` (MODIFY) | adapter/provider | event-driven → request-response | `_run_draft` / `_require_assistant_message` in the same file | exact (same file, same flow) |
| `tests/test_copilot_provenance.py` (CREATE) | test (unit + fake-SDK async) | transform + event-driven | `tests/test_copilot_backend_unavailable.py` (`_StubClient` + monkeypatch); honesty asserts in `tests/test_orchestrator_hitl.py` / `tests/test_models.py` | exact (stub pattern) + role-match (assertions) |

**Read-only analogs (no change — planner must respect their shape):**
`src/dogen/core/models.py` (`DraftResult`/`Generation` fields exist), `src/dogen/core/orchestrator.py:_record_generation` (verbatim copy), `src/dogen/adapters/copilot/tools.py` (READONLY allowlist).

## Pattern Assignments

### `src/dogen/adapters/copilot/mapping.py` (adapter, transform) — ADD a pure helper

**Analog:** the existing `to_draft_result` in the same file — the sanctioned single seam-translation point.

**SPDX header + module docstring convention** (lines 1-29): the 16-line GPL-3.0-only block, then a `"""..."""` module docstring naming the seam rule. Any new symbol stays under this same header — do not add a new file header here (this is a MODIFY).

**Import convention** (lines 31-33): SDK type first, domain type second:
```python
from copilot import SessionEvent

from dogen.core.models import DraftResult
```
New helper additionally needs `SessionEventType` (and the value is read off `evt.data` — no new SDK type beyond these two). Add module-level named constants the way `_UNKNOWN_MODEL` is declared (lines 35-39) — e.g. `_CONTENT_READ_TOOLS = frozenset({"view"})` and `_VIEW_PATH_KEY = "path"` (RESEARCH Pitfall 4: centralise the arg key so a CLI rename localises to one constant).

**NumPy-style docstring + defensive `getattr` pattern** (lines 42-81) — the template the new helper must mirror exactly:
```python
def to_draft_result(evt: SessionEvent, run_id: str) -> DraftResult:
    """Translate an ``assistant.message`` event into a domain ``DraftResult``.

    Parameters
    ----------
    evt : SessionEvent
        The final ``assistant.message`` event from ``send_and_wait`` ...
    run_id : str
        ...

    Returns
    -------
    DraftResult
        ...
    """
    data = evt.data
    text = getattr(data, "content", None) or ""
    model = getattr(data, "model", None) or _UNKNOWN_MODEL
    ...
```
Key conventions to copy: NumPy `Parameters`/`Returns` sections; read SDK union payload off `evt.data`; guard every field with `getattr(..., default)` (omit-on-doubt, D-05/V5). The new `tool_events_to_provenance(events: list[SessionEvent]) -> tuple[list[str], list[str]]` returns plain `list[str]` only — no SDK shape crosses the seam (D-04/SEAM-01). RESEARCH Pattern 2 (04-RESEARCH.md lines 162-200) gives the verified body; reproduce its `isinstance(args, dict)` / `isinstance(path, str)` guards.

**Decision: extend in place vs sibling helper** — Claude's discretion (CONTEXT D-04). Recommended: a sibling `tool_events_to_provenance` (pure, independently unit-testable per D-06) called by the provider, with `to_draft_result` unchanged; the provider attaches the two lists via `model_copy(update=...)` (see provider pattern below).

---

### `src/dogen/adapters/copilot/provider.py` (adapter, event-driven → request-response) — observe events

**Analog:** the existing `_run_draft` (lines 239-283) and `_require_assistant_message` (lines 322-347) in the same file.

**The exact insertion site** — `_run_draft`'s `async with session` block (lines 278-283). Current:
```python
            async with session_cm as session:
                event = await session.send_and_wait(prompt, timeout=_DRAFT_TIMEOUT)
        result = _require_assistant_message(event)
        # IN-03: report the effort the SDK actually ran at ...
        return result.model_copy(update={"effort_used": self._effort})
```
The new `events = await session.get_events()` MUST go **inside** the `async with session` block, right after `send_and_wait` (RESEARCH Pitfall 3: `get_events()` is async and raises if the session is closed). Then translate via the mapping helper and extend the existing `model_copy(update={...})` call (already the established way the provider attaches provider-observed fields — `effort_used` is set exactly this way on line 283):
```python
            async with session_cm as session:
                event = await session.send_and_wait(prompt, timeout=_DRAFT_TIMEOUT)
                events = await session.get_events()
        context_origins, tools_used = tool_events_to_provenance(events)
        result = _require_assistant_message(event)
        return result.model_copy(update={
            "effort_used": self._effort,
            "context_origins": context_origins,
            "tools_used": tools_used,
        })
```

**Import convention** (lines 43-58): SDK imports grouped from `copilot`, then domain imports; add the mapping helper to the existing `from dogen.adapters.copilot.mapping import to_draft_result` line. `SessionEvent`/`SessionEventType` are already imported here — no new SDK import needed in the provider (translation owns the event-type filtering).

**Error-handling envelope is already in place** — `draft_unit` (lines 196-211) wraps `_run_draft` in the `StopError`/`JsonRpcError`/`ProcessExitedError`/`Connection*` handlers. A malformed-event guard belongs in the pure helper (omit-on-doubt), not new try/except here; do not add a new catch.

---

### `tests/test_copilot_provenance.py` (test, fake-SDK async + pure-helper unit) — CREATE

**Primary analog:** `tests/test_copilot_backend_unavailable.py` — the `_StubClient` + `monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", factory)` pattern.

**New-file SPDX header** (copy verbatim, lines 1-16 of any source file): the 16-line `SPDX-License-Identifier: GPL-3.0-only` / `SPDX-FileCopyrightText: 2026 Canonical Ltd.` block. Tests are exempt from `ANN`/`D` (no annotation/docstring enforcement) but the SPDX header is mandatory.

**Stub + monkeypatch pattern** (test_copilot_backend_unavailable.py lines 60-97) — extend, do not rewrite:
```python
class _StubClient:
    async def __aenter__(self) -> "_StubClient": ...
    async def __aexit__(self, *exc: object) -> bool: return False
    async def get_status(self) -> None: ...
    async def get_auth_status(self) -> None: return None

def _install_stub(monkeypatch, ...):
    def _factory(*_a, **_k): return _StubClient(...)
    monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", _factory)
```
For PROV, the stub `_StubClient` gains an `async def create_session(self, **kw)` returning a `_StubSession` (an async-CM exposing `send_and_wait` + `get_events`). RESEARCH 04-RESEARCH.md lines 254-301 gives the verified `_StubSession`, `_tool_start`, `_assistant_message` helpers and the verified SDK import path:
```python
from copilot import SessionEvent, SessionEventType
from copilot.session_events import ToolExecutionStartData, AssistantMessageData
```
(import path confirmed importable against installed `github-copilot-sdk==1.0.2`).

**Async test marker** — copy the `@pytest.mark.asyncio` + `async def test_...` shape from test_copilot_backend_unavailable.py lines 106-131 and the `_draft(provider)` / `_steering()` helpers (lines 42-57).

**Assertion format to reproduce exactly** — the `builtin:`-qualified, first-seen-de-duped contract is already asserted elsewhere; match it.
- From `test_orchestrator_hitl.py` lines 242-270 (`test_generation_records_provider_reported_context`):
  ```python
  context_origins=["docs/actually_read.md"],
  tools_used=["builtin:view"],
  ...
  assert generation.context_origins == ["docs/actually_read.md"]
  assert generation.tools_used == ["builtin:view"]
  ```
- From `test_models.py` lines 144-145: `tools_used=["builtin:grep"]`.
- End-to-end target (RESEARCH lines 304-308): `result.context_origins == ["README.md"]`, `result.tools_used == ["builtin:view", "builtin:grep"]`.
- Pure-helper target (RESEARCH lines 312-323): duplicate `view` de-duped, `grep`/`glob` add tools but no origin.

**Regression to NOT break** — `test_generation_does_not_fabricate_context_origins` (test_orchestrator_hitl.py lines 226-238) asserts both lists are `[]` when nothing is observed (D-05/BL-01). The new code must keep honest-empty: no events → empty lists.

## Shared Patterns

### Seam discipline (SEAM-01/03, D-04)
**Source:** module docstring of `mapping.py` (lines 18-29) and `provider.py` (lines 18-38).
**Apply to:** the new `mapping.py` helper and the `provider.py` edit.
SDK types (`SessionEvent`, `SessionEventType`, `ToolExecutionStartData`) are importable **only** under `src/dogen/adapters/copilot/`. The helper returns `tuple[list[str], list[str]]` — plain strings only. Enforced by `tests/test_seam.py` / `tests/test_seam_importlinter.py` (must stay green; run per task commit).

### Defensive boundary coercion (V5 / omit-on-doubt, D-05)
**Source:** `mapping.py` `to_draft_result` lines 64-74 (`getattr(data, x, None) or default`).
**Apply to:** the new helper's reading of `data.tool_name` / `data.arguments` — `arguments` is `Any`; guard `isinstance(args, dict)` then `args.get(path_key)`, and `isinstance(path, str) and path` before appending. A malformed event degrades to honest-empty, never crashes the draft.

### Provider attaches observed fields via `model_copy(update=...)`
**Source:** `provider.py` line 283 (`effort_used` set this way).
**Apply to:** add `context_origins` / `tools_used` to the same `update` dict — the established single attach point for provider-observed provenance.

### NumPy docstrings + SPDX header
**Source:** every source file lines 1-16 (header) + `mapping.py` lines 42-59 (docstring shape).
**Apply to:** the new `mapping.py` helper (full Parameters/Returns/annotations — `ANN`/`D` enforced on non-test code). Tests carry the SPDX header but are `ANN`/`D`-exempt.

## No Analog Found

None. Every file in scope has a close in-repo analog (the two modified files are extended in place; the new test extends an existing stub-harness pattern).

## Metadata

**Analog search scope:** `src/dogen/adapters/copilot/`, `src/dogen/core/`, `tests/`
**Files scanned:** mapping.py, provider.py, tools.py, models.py, orchestrator.py, test_copilot_backend_unavailable.py, test_orchestrator_hitl.py, test_models.py
**SDK import path verified:** `from copilot.session_events import ToolExecutionStartData, AssistantMessageData` importable against installed `github-copilot-sdk==1.0.2`.
**Pattern extraction date:** 2026-06-22
