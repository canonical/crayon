# Phase 4: Honest observed provenance - Research

**Researched:** 2026-06-22
**Domain:** Copilot SDK session-event observation → provenance translation (adapter-only, brownfield)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01: Observe via `session.get_events()` after the turn completes.** Keep the existing blocking `await session.send_and_wait(prompt, …)` as-is; then, still inside the `async with session` block, call `session.get_events()`, filter for the tool-execution event(s), and feed them to the mapping translation alongside the final assistant event. Chosen over the streaming `on_event=` collector and `SessionHooks` callbacks (least invasive, authoritative history, stays inside the adapter seam).
- **D-02: `context_origins` = the concrete file paths a *content-read* tool (primarily `view`) actually opened, de-duplicated in first-seen order.** `grep`/`glob` are discovery/query tools — a bare search contributes to `tools_used` but NOT to `context_origins` unless it yields a concrete read path. **Omit-on-doubt:** if an invocation's arguments don't resolve to a concrete path, it adds no context origin. Keeps `context_origins` distinct from human-pointed `sources`.
- **D-03: `tools_used` = source-qualified `builtin:<tool_name>` identifiers, de-duplicated in first-seen order.** Map the observed tool name → `builtin:<name>`. For the READONLY allowlist (`grep`/`glob`/`view`, all built-in) the `builtin:` qualifier is correct.
- **D-04: Collect in the provider, translate in a pure `mapping.py` helper — the seam holds.** `provider._run_draft` gathers the SDK events; a pure function in `mapping.py` converts them to the two domain `list[str]` and attaches them to the `DraftResult`. No `copilot`/SDK shape crosses into `core/` (SEAM-01/03).
- **D-05: Honest-empty stays honest.** When no tool-execution events are observed, both lists remain empty — never fabricated, never back-filled from `sources` (BL-01). The regression test `test_generation_does_not_fabricate_context_origins` must keep passing.
- **D-06: Extend the `_StubClient` fake-SDK harness to emit tool-call events.** The stub session's `get_events()` returns a scripted sequence of fake tool-execution `SessionEvent`s; the test asserts the resulting `DraftResult.context_origins` == the read paths and `.tools_used` == `["builtin:view", "builtin:grep"]` (first-seen, de-duped) and that the recorded `Generation` carries them. Add a focused unit test on the pure `mapping.py` translation (events → the two lists).

### Claude's Discretion
- Precise argument-key lookup per tool (research confirms them below); whether `to_draft_result` is extended in place or paired with a new `tool_events_to_provenance(...)` helper; the precise fake `SessionEvent` construction in the stub.
- Whether `grep`/`glob` that *name a concrete file* (vs a directory/pattern) should add a context origin — omit-on-doubt default is "no", but a tightly scoped, well-tested inclusion is acceptable if research shows the argument reliably carries a single read path. **Research finding (below): `grep`/`glob` `path` is a *search scope* (file OR directory), not a guaranteed content-read — keep the omit-on-doubt "no".**

### Deferred Ideas (OUT OF SCOPE)
- Recording tool *outputs* / results / content hashes in provenance.
- Treating `grep`/`glob` match results as `context_origins`.
- Backfilling / re-running old v1.0 provenance.
- An always-on live CI provenance assertion (live path stays manual-only, D-24).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROV-01 | After a successful live draft, `provenance.yaml`'s `context_origins` lists what the agent actually read, derived from observed tool-call events and kept distinct from human-pointed `sources` — no longer empty. | Event recipe (filter `TOOL_EXECUTION_START`, read `data.tool_name`/`data.arguments`); path-extraction rule (`view` → `arguments["path"]`); seam-safe translation in `mapping.py`; distinctness already guarded by `test_sources_and_context_origins_are_distinct_fields` + orchestrator D-37 ban. |
| PROV-02 | After a successful live draft, `provenance.yaml`'s `tools_used` lists the tools the agent actually invoked, derived from observed tool-call events — no longer empty. | Same event recipe; `tools_used` = `builtin:<data.tool_name>` first-seen de-duped; `builtin:` qualifier confirmed correct (built-in tools carry `mcp_server_name=None`). |
</phase_requirements>

## Summary

This phase is a small, fully-localised adapter change. The domain plumbing already flows end-to-end: `DraftResult.context_origins/tools_used` exist (`core/models.py:416-417`), `Generation` carries them (`models.py:251-252`), and `core/orchestrator.py:_record_generation` (lines 284-296) already copies `result.context_origins`/`tools_used` verbatim and is forbidden (D-37/BL-01) from substituting `sources`. **Confirmed: no `core/` change is needed** — populating the provider's lists is sufficient. The only gap is provider-side: the Copilot adapter never observes tool-call events, so both lists are always empty (verified against the real 2026-06-20 live artifact at `temp/.dogen/units/temperature-api/provenance.yaml`, which shows `context_origins: []` / `tools_used: []`).

All three Open Research Items are resolved against the **installed `github-copilot-sdk==1.0.2`** and the **bundled Copilot CLI** (`~/.copilot/pkg/universal/0.0.420/index.js`):

1. **Event carrier:** `get_events()` returns `list[SessionEvent]` (the full `session.getMessages` history, chronological). The tool name + arguments ride on **`TOOL_EXECUTION_START`**, whose `SessionEvent.data` is a `ToolExecutionStartData` dataclass with `.tool_name`, `.arguments` (a raw dict), and `.mcp_server_name`/`.mcp_tool_name` (both `None` for built-ins). `TOOL_EXECUTION_COMPLETE` does **NOT** carry the name or arguments (only `tool_call_id` + result) — so filtering on `TOOL_EXECUTION_START` counts each call **exactly once** with no START+COMPLETE double-counting. **`ToolInvocation` is NOT the `get_events()` carrier** — it is the dataclass passed to a custom tool *handler*; do not use it here.
2. **Per-tool argument keys (confirmed from the bundled CLI zod schemas):** `view` → `arguments["path"]` ("Full absolute path to file or directory. File MUST exist to view."); `grep` → `{"pattern", optional "path" (file OR dir search scope), "output_mode"}`; `glob` → `{"pattern", optional "path" (search dir)}`. Only `view`'s `path` is a guaranteed content-read → the sole `context_origins` contributor (D-02). `grep`/`glob` `path` is a search scope, not a guaranteed read → contributes to `tools_used` only.
3. **Source qualifier:** built-in tools report `mcp_server_name=None`/`mcp_tool_name=None` on the event; MCP tools populate them. For v1.1's all-builtin READONLY allowlist, hardcoded `builtin:` is correct. A future-proofing helper *could* derive the qualifier from `mcp_server_name`, but that is out of scope — hardcode `builtin:`.

**Primary recommendation:** Add one pure helper in `mapping.py` (e.g. `tool_events_to_provenance(events: list[SessionEvent]) -> tuple[list[str], list[str]]`) that filters `TOOL_EXECUTION_START`, reads `data.tool_name`/`data.arguments`, builds `tools_used` (`builtin:<name>`, first-seen de-duped) and `context_origins` (`view`'s `path` only, first-seen de-duped, omit-on-doubt). In `provider._run_draft`, call `events = await session.get_events()` immediately after `send_and_wait` (still inside the `async with session` block), then attach both lists onto the `DraftResult`. Verify with one fake-SDK unit test (scripted `get_events()`) plus a focused pure-helper unit test; live path stays manual-only.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Observe tool-call events from the session | Adapter (`provider.py`) | — | The session is an SDK object; only the adapter may touch SDK shapes (SEAM-01/03). |
| Translate SDK events → domain `list[str]` | Adapter (`mapping.py`) | — | `mapping.py` is the single sanctioned translation point; no SDK type may reach `core/`. |
| Record the two lists into `provenance.yaml` | Core (`orchestrator._record_generation`) | — | Already wired (verbatim copy, D-37 ban); unchanged this phase. |
| Persist provenance to disk | Core/store | — | Unchanged; already serialises `Generation.context_origins/tools_used`. |

## Standard Stack

This is a brownfield adapter change on the already-adopted stack. **No new packages.** All work uses symbols already importable inside `adapters/copilot/`.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `github-copilot-sdk` | 1.0.2 (pinned) | `SessionEvent`, `SessionEventType`, `ToolExecutionStartData`, `CopilotSession.get_events()` | Already the adopted backend; v1.0.2 verified installed at `.venv/.../site-packages/copilot`, version `1.0.2`. [VERIFIED: `.venv/bin/python -c "import copilot; copilot.__version__"`] |
| `pytest` + `pytest-asyncio` | installed | Async unit tests against the fake SDK | The async drafting loop is already tested this way; new tests extend the existing `_StubClient` pattern. [VERIFIED: pyproject `[dependency-groups]`] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | — | — | No supporting library is added; the feature is pure event-shape translation. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `session.get_events()` (D-01) | `on_event=` streaming collector | Threads a mutable collector through a callback; more wiring; `send_and_wait` flow disturbed. Rejected per D-01. |
| `session.get_events()` (D-01) | `SessionHooks(pre_tool_use/post_tool_use)` | Hooks can *intercept/modify* tool use — more power than observation needs; new handler wiring. Rejected per D-01. |
| Hardcoded `builtin:` (D-03) | Derive from `data.mcp_server_name` | Forward-looking but unused in v1.1 (no MCP/non-builtin tools); adds branchy logic for no behaviour change. Note it, don't adopt. |

**Installation:** None — no dependency change.

**Version verification:** `github-copilot-sdk` confirmed at `1.0.2` via `.venv/bin/python -c "import copilot; print(copilot.__version__)"` → `1.0.2`. [VERIFIED]

## Package Legitimacy Audit

> No external packages are installed by this phase. The only third-party dependency touched (`github-copilot-sdk==1.0.2`) is already an adopted, pinned project dependency (verified installed locally). Audit not applicable; no new install.

## Architecture Patterns

### System Architecture Diagram

```
dogen draft --provider copilot
        │
        ▼
CopilotDraftingProvider.draft_unit()           [adapters/copilot/provider.py]
        │  compose prompt + steering (domain inputs only)
        ▼
  _run_draft(prompt, steer)
        │  async with CopilotClient() as client:
        │     await _require_available_backend(client)
        │     session_cm = await client.create_session(... READONLY/DENY, approve_all ...)
        │     async with session_cm as session:
        │  ┌─────────────────────────────────────────────────────────┐
        │  │ event = await session.send_and_wait(prompt, timeout)     │  ← unchanged (D-01)
        │  │ events = await session.get_events()   ← NEW (D-01)       │
        │  └─────────────────────────────────────────────────────────┘
        │     (still inside the session block, before __aexit__)
        ▼
  mapping.tool_events_to_provenance(events)      [adapters/copilot/mapping.py] ← NEW pure helper
        │  filter TOOL_EXECUTION_START events
        │  data.tool_name → builtin:<name>  (tools_used, first-seen de-dup)   D-03
        │  view → data.arguments["path"]    (context_origins, first-seen de-dup, omit-on-doubt)  D-02
        ▼
  to_draft_result(final_event, run_id) → DraftResult(..., context_origins=[...], tools_used=[...])
        │  ONLY list[str] crosses the seam — no SDK shape reaches core/  (SEAM-01/03, D-04)
        ▼
core/orchestrator._record_generation(result, run_id)   [UNCHANGED — verbatim copy, D-37 ban]
        ▼
provenance.yaml  generations[].context_origins / .tools_used   (non-empty after a real read)
```

### Recommended Project Structure
```
src/dogen/adapters/copilot/
├── provider.py    # _run_draft: add `events = await session.get_events()` after send_and_wait;
│                  # thread events + final event into the DraftResult via mapping
├── mapping.py     # NEW pure helper: tool_events_to_provenance(events) -> (context_origins, tools_used)
│                  # + wire the two lists onto DraftResult (extend to_draft_result OR a sibling)
└── tools.py       # READONLY allowlist {grep, glob, view} — the closed observed set (UNCHANGED)
tests/
├── test_copilot_provenance.py        # NEW: fake-SDK get_events() emits tool events (D-06, criterion 4)
└── (extend) test_*                   # the pure-helper translation test can live in the same file
```

### Pattern 1: Observe-then-translate inside the session block (D-01/D-04)
**What:** Read the full event history with `get_events()` right after the blocking turn completes, while the session is still open, then hand it to a pure translation function.
**When to use:** Always, on the success path in `_run_draft`.
**Example:**
```python
# Source: installed SDK CopilotSession.get_events docstring + ToolExecutionStartData dataclass
# (.venv/.../copilot/session.py, copilot/generated/session_events.py) [VERIFIED]
async with session_cm as session:
    event = await session.send_and_wait(prompt, timeout=_DRAFT_TIMEOUT)
    events = await session.get_events()  # complete chronological history (session.getMessages)
# translation happens outside the SDK calls but still inside the adapter:
context_origins, tools_used = tool_events_to_provenance(events)
result = _require_assistant_message(event)
return result.model_copy(update={
    "effort_used": self._effort,
    "context_origins": context_origins,
    "tools_used": tools_used,
})
```
> Note: `get_events()` is `async` and must be `await`ed. It returns the full session history; filter to tool events inside the pure helper (the provider stays a thin orchestration site).

### Pattern 2: The pure translation helper (D-02/D-03/D-04)
**What:** A side-effect-free function that turns `list[SessionEvent]` into the two domain `list[str]`. Lives in `mapping.py` (the one translation point). Returns plain strings so no SDK shape leaks to `core/`.
**When to use:** Called once per draft, from the provider.
**Example:**
```python
# Source: confirmed event/arg shapes from installed SDK + bundled CLI zod schemas [VERIFIED]
from copilot import SessionEvent, SessionEventType

# Built-in read tool whose `path` argument is a guaranteed content-read (D-02).
_CONTENT_READ_TOOLS = frozenset({"view"})
_VIEW_PATH_KEY = "path"  # confirmed: view arguments carry the read file under "path"


def tool_events_to_provenance(
    events: list[SessionEvent],
) -> tuple[list[str], list[str]]:
    """Derive (context_origins, tools_used) from observed tool-execution events.

    context_origins: the concrete file paths content-read tools opened, first-seen
        de-duped (D-02). Only `view`'s `path` qualifies; grep/glob are discovery
        tools whose `path` is a search scope, not a guaranteed read (omit-on-doubt).
    tools_used: source-qualified `builtin:<name>` identifiers, first-seen de-duped (D-03).
    """
    context_origins: list[str] = []
    tools_used: list[str] = []
    for evt in events:
        if evt.type is not SessionEventType.TOOL_EXECUTION_START:
            continue  # name+args ride only on START; COMPLETE has neither → no double count
        data = evt.data
        name = getattr(data, "tool_name", "") or ""
        if not name:
            continue
        qualified = f"builtin:{name}"
        if qualified not in tools_used:
            tools_used.append(qualified)
        if name in _CONTENT_READ_TOOLS:
            args = getattr(data, "arguments", None)
            path = args.get(_VIEW_PATH_KEY) if isinstance(args, dict) else None
            if isinstance(path, str) and path and path not in context_origins:
                context_origins.append(path)
    return context_origins, tools_used
```
> `arguments` is typed `Any` on the SDK dataclass and is the raw dict the CLI sent; guard with `isinstance(args, dict)` (omit-on-doubt, D-02/D-05). Built-in tools carry `mcp_server_name=None`, so `builtin:` is the correct qualifier (D-03).

### Anti-Patterns to Avoid
- **Filtering on both `TOOL_EXECUTION_START` and `TOOL_EXECUTION_COMPLETE`:** double-counts (or errors on COMPLETE, which has no `tool_name`/`arguments`). Filter on START only.
- **Using `ToolInvocation` to read the event:** `ToolInvocation` is the tool-*handler* context, not the `get_events()` payload. The payload type is `ToolExecutionStartData`.
- **Doing the path/name extraction inline in `provider.py`:** splits translation across two files; violates the one-translation-point rule (D-04). Keep it in `mapping.py`.
- **Letting any `SessionEvent`/`ToolExecutionStartData` reach `core/`:** seam violation (SEAM-01/03); the helper must return `list[str]`/`tuple[list[str], ...]` only.
- **Back-filling `context_origins` from `sources` when no events seen:** BL-01/D-05 violation; keep honest-empty.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading session history | A custom event collector threaded through `on_event=` | `await session.get_events()` (D-01) | SDK gives the authoritative, complete, chronological history in one call. |
| Parsing the tool event payload | Manual JSON-RPC frame parsing | `evt.data` (already a typed `ToolExecutionStartData`) | The SDK already deserialises `session.getMessages` into typed dataclasses. |
| Detecting "is this a built-in tool" | A name allowlist re-check | `data.mcp_server_name is None` (or just hardcode `builtin:` for v1.1) | Built-ins report `mcp_server_name=None`; the observed set is already constrained to READONLY. |

**Key insight:** The SDK already does all the deserialisation — the only custom logic is a 20-line pure filter/de-dup. Anything more is reinventing the SDK's event model.

## Runtime State Inventory

> Not a rename/refactor/migration phase — this is additive observation logic. Inventory not applicable. **No stored data, live-service config, OS-registered state, secrets/env vars, or build artifacts are renamed or migrated.** The one historical artifact found (`temp/.dogen/units/temperature-api/provenance.yaml`, the 2026-06-20 live run with empty lists) is explicitly **left as-is** — backfilling old provenance is Out of Scope (REQUIREMENTS Out of Scope; D-24).

## Common Pitfalls

### Pitfall 1: Assuming `TOOL_EXECUTION_COMPLETE` carries the tool name/arguments
**What goes wrong:** Code filters COMPLETE (or both START+COMPLETE) expecting `tool_name`; gets nothing or double-counts.
**Why it happens:** Both event types exist in `SessionEventType`; only START's data has `tool_name`/`arguments`.
**How to avoid:** Filter `SessionEventType.TOOL_EXECUTION_START` exclusively. [VERIFIED: `ToolExecutionCompleteData` has `success`, `tool_call_id`, `result`, `error` — no `tool_name`/`arguments`.]
**Warning signs:** `tools_used` is empty after a run that clearly used tools, or each tool appears twice.

### Pitfall 2: `arguments` is `Any` and may be a non-dict or carry `None` path
**What goes wrong:** `args["path"]` raises `TypeError`/`KeyError` when `arguments` is `None` or not a dict.
**Why it happens:** `ToolExecutionStartData.arguments: Any = None` passes the raw CLI dict through unparsed; a malformed/empty event can carry `None`.
**How to avoid:** `isinstance(args, dict)` then `args.get("path")`, and `isinstance(path, str) and path` before appending (omit-on-doubt, D-02/D-05).
**Warning signs:** A crash on a draft where the agent ran a tool with unexpected args.

### Pitfall 3: Reading events after the session context exits
**What goes wrong:** Calling `get_events()` after `async with session_cm as session:` closes raises (session disconnected).
**Why it happens:** `get_events()` issues a live `session.getMessages` JSON-RPC request; the session must still be connected.
**How to avoid:** Call `get_events()` **inside** the `async with session` block, right after `send_and_wait`. [CITED: get_events docstring — "Raises: Exception: If the session has been disconnected".]
**Warning signs:** Intermittent disconnection errors only on the provenance path.

### Pitfall 4: A CLI version drift changing the `view` argument key
**What goes wrong:** A future Copilot CLI renames `view`'s `path` key; `context_origins` silently goes empty.
**Why it happens:** The arg schema is owned by the CLI runtime (verified here against bundled `0.0.420`; the live run used `1.0.64-0`), not the pinned SDK. The SDK types `arguments` as `Any`, so a key rename is invisible to type checks.
**How to avoid:** Centralise `_VIEW_PATH_KEY = "path"` as a named constant; the fake-SDK unit test pins the contract; one manual live run (D-24) confirms the real key. Omit-on-doubt means a rename degrades to honest-empty, never a crash.
**Warning signs:** Live `context_origins` empty while `tools_used` shows `builtin:view`.

## Code Examples

### Scripting the fake `_StubClient` session for the criterion-4 unit test (D-06)
The existing `_StubClient` (`tests/test_copilot_backend_unavailable.py:60-97`) only scripts `get_status`/lifecycle. For PROV, add a stub **session** whose `send_and_wait` returns a fake `assistant.message` event and whose `get_events()` returns scripted tool events. Construct the events directly (no `from_dict` round-trip needed — verified working):

```python
# Source: verified by constructing these objects against installed SDK 1.0.2 [VERIFIED]
import uuid
from datetime import datetime, timezone

from copilot import SessionEvent, SessionEventType
from copilot.session_events import ToolExecutionStartData, AssistantMessageData


def _tool_start(tool_name: str, arguments: dict | None) -> SessionEvent:
    return SessionEvent(
        data=ToolExecutionStartData(
            tool_call_id=str(uuid.uuid4()),
            tool_name=tool_name,
            arguments=arguments,
        ),
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        type=SessionEventType.TOOL_EXECUTION_START,
    )


def _assistant_message(content: str) -> SessionEvent:
    return SessionEvent(
        data=AssistantMessageData(content=content, message_id=str(uuid.uuid4())),  # both required (verified)
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        type=SessionEventType.ASSISTANT_MESSAGE,
    )


class _StubSession:
    def __init__(self, *, final_event, events):
        self._final_event = final_event
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_and_wait(self, prompt, timeout=None):
        return self._final_event

    async def get_events(self):
        return list(self._events)
```

Then the stub client's `create_session` returns this session (note: `create_session` is a coroutine returning an async-CM — mirror the real shape: `async def create_session(self, **kw): return _StubSession(...)`). The test scripts e.g. a `view README.md` + a `grep` and asserts:
```python
result = await provider.draft_unit(...)
assert result.context_origins == ["README.md"]        # only view's path
assert result.tools_used == ["builtin:view", "builtin:grep"]  # first-seen, de-duped
# and end-to-end: the recorded Generation carries them (orchestrator verbatim copy)
```

### Focused pure-helper test (translation pinned independently)
```python
# events list with a duplicate view + a grep with only a pattern
events = [
    _tool_start("view", {"path": "README.md"}),
    _tool_start("grep", {"pattern": "TODO"}),        # no concrete read path → no origin
    _tool_start("view", {"path": "README.md"}),       # duplicate → de-duped
    _tool_start("glob", {"pattern": "**/*.md"}),
]
origins, tools = tool_events_to_provenance(events)
assert origins == ["README.md"]
assert tools == ["builtin:view", "builtin:grep", "builtin:glob"]
```

## State of the Art

| Old Approach (v1.0) | Current Approach (v1.1 Phase 4) | When Changed | Impact |
|--------------------|----------------------------------|--------------|--------|
| `to_draft_result` reads only the final `assistant.message`; provenance lists honestly empty | Harvest `TOOL_EXECUTION_START` events from `get_events()`; fill `context_origins`/`tools_used` | This phase | Audit surface reflects what the agent actually read/ran (BL-01 completed). |
| Fabrication risk (copying `sources`) — already removed | Honest-empty when nothing observed; fill only on real evidence | v1.0 → v1.1 | No regression: `test_generation_does_not_fabricate_context_origins` still passes (D-05). |

**Deprecated/outdated:**
- `ToolInvocation` as the `get_events()` payload type: a plausible-but-wrong assumption from discussion. The real `get_events()` tool payload is `ToolExecutionStartData`. `ToolInvocation` is the custom-tool-*handler* context dataclass only.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `view`'s file-path argument key is `"path"` in the live CLI (`1.0.64-0`). Confirmed against bundled CLI `0.0.420` zod schema (`"Full absolute path to file or directory. File MUST exist to view."`); a different bundled version may differ. | Pitfall 4, Pattern 2 | `context_origins` degrades to honest-empty (no crash, omit-on-doubt). One manual live run (D-24) confirms; named constant + unit test localise the fix. |
**If this table is empty:** N/A — one assumption (A1) needs manual-live confirmation. (A2 — `AssistantMessageData` required fields — was verified this session: it requires `content` AND `message_id`; the stub helper passes both.)

## Open Questions

1. **Does a real live `get_events()` reliably include the just-completed turn's tool events?**
   - What we know: `get_events()` returns the complete chronological history via `session.getMessages`, called inside the open session block after `send_and_wait` returns (the turn is complete). The 2026-06-20 live run demonstrably read files (the agent produced a source-grounded page), so tool events existed in that session.
   - What's unclear: not re-confirmed by a *fresh* live run this session (live path is manual-only, D-24 — no live call made here).
   - Recommendation: the single manual live run that validates this phase (alongside the CI fake-SDK test) is where this is confirmed. The fake-SDK test pins the translation deterministically regardless.

2. **`grep`/`glob` with a concrete single-file `path` — include as origin?**
   - What we know: their `path` is documented as "File or directory to search in" — a *scope*, not a guaranteed content-read.
   - What's unclear: whether the agent ever passes a single existing file to `grep` such that it functionally reads it.
   - Recommendation: keep omit-on-doubt "no" (D-02 default). Discretion allows a tightly-tested inclusion later; not needed for the success criteria.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `github-copilot-sdk` | Event observation types (import in adapter only) | ✓ | 1.0.2 | — |
| Copilot CLI runtime | Live manual validation only (not CI) | ✓ (bundled) | bundled `0.0.420` present; live run used `1.0.64-0` | Fake-SDK unit test is the CI proof (D-24) |
| `pytest` / `pytest-asyncio` | Unit tests | ✓ | installed | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** Live CLI for an in-CI assertion — intentionally absent; the fake-SDK unit test (D-06) is the CI-runnable proof (D-24).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_copilot_provenance.py -x` (new file) |
| Full suite command | `uv run pytest` |

> Async tests use explicit `@pytest.mark.asyncio` markers (verified in `tests/test_orchestrator_hitl.py`); mirror that for any new async test.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROV-01 | `context_origins` = `view` read paths, first-seen de-duped, distinct from `sources` | unit (pure helper) | `uv run pytest tests/test_copilot_provenance.py -k context_origins -x` | ❌ Wave 0 |
| PROV-02 | `tools_used` = `builtin:<name>`, first-seen de-duped | unit (pure helper) | `uv run pytest tests/test_copilot_provenance.py -k tools_used -x` | ❌ Wave 0 |
| PROV-01/02 | Fake-SDK `get_events()` emits tool events → `DraftResult` lists populated → `Generation` carries them (criterion 4) | unit (fake SDK, async) | `uv run pytest tests/test_copilot_provenance.py -k end_to_end -x` | ❌ Wave 0 |
| PROV-01 (regression) | Honest-empty kept when no events (D-05/BL-01) | unit | `uv run pytest tests/test_orchestrator_hitl.py -k does_not_fabricate -x` | ✅ exists |
| PROV-01 (distinctness) | `sources` vs `context_origins` stay distinct | unit | `uv run pytest tests/test_models.py -k distinct -x` | ✅ exists |
| Seam | No SDK shape reaches `core/`; import-linter + AST guard pass | unit | `uv run pytest tests/test_seam.py tests/test_seam_importlinter.py -x` | ✅ exists |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_copilot_provenance.py tests/test_seam.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** full suite green before `/gsd-verify-work`; plus one manual live `dogen draft --provider copilot` run confirming non-empty `context_origins`/`tools_used` in `provenance.yaml` (D-24).

### Wave 0 Gaps
- [ ] `tests/test_copilot_provenance.py` — new file: the fake-SDK `_StubSession.get_events()` end-to-end test + the focused pure-helper translation tests (covers PROV-01/02, criterion 4).
- [ ] (Stub) extend the fake-SDK harness with a session object exposing `send_and_wait` + `get_events` (criterion-4 mechanism). No new fixtures or framework install needed.

## Security Domain

> `security_enforcement` is enabled. This phase adds **read-only observation** of already-constrained tool events; it introduces no new tool, no write/exec/network surface, and no new external input beyond what the READONLY allowlist already permits.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface touched (session auth handled by Phase 3). |
| V3 Session Management | no | No new session lifecycle; reuses the existing bounded session. |
| V4 Access Control | yes (unchanged) | The READONLY allowlist + DENY denylist (`tools.py`) remain the boundary; this phase only *observes* what ran within it. |
| V5 Input Validation | yes | `arguments` is untrusted `Any` from the CLI — guard with `isinstance(args, dict)` and `isinstance(path, str)` before recording (omit-on-doubt). A malformed event must never crash the draft (SKEL-05/D-27) nor inject a non-string into `context_origins`. |
| V6 Cryptography | no | No crypto. |

### Known Threat Patterns for {Copilot adapter / event observation}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/garbage `arguments` payload from a compromised/buggy runtime causing a crash or bad provenance | Tampering / DoS | Defensive `getattr`/`isinstance` guards; omit-on-doubt; lists are plain `str` only (Pitfall 2). |
| Recorded `context_origins` leaking a path the human never pointed at (over-disclosure) | Information Disclosure | This is *intended* honesty (records what was read), but it must stay within the READONLY scope — which `approve_all` + the allowlist already bound to repo reads. No new disclosure surface. |
| A renamed CLI arg key silently emptying provenance (integrity of the audit record) | Tampering (integrity) | Named constant + unit test pin the key; manual live run confirms; degrade to honest-empty, never fabricate (Pitfall 4, D-05). |
| SDK type crossing into `core/` (architectural integrity) | Tampering | import-linter forbidden contract + AST seam guard (`test_seam*.py`) — translation returns `list[str]` only (D-04). |

## Project Constraints (from CLAUDE.md)

- **Seam rule (hard):** `copilot`/SDK types (`SessionEvent`, `SessionEventType`, `ToolExecutionStartData`) may be imported **only** under `src/dogen/adapters/copilot/`. Enforced by `scripts/seam_check.py` (AST) + the `[tool.importlinter]` forbidden contract (`dogen.core` may not import `copilot`/`github_copilot_sdk`/`logfire`/`opentelemetry.sdk`). The new helper lives in `mapping.py` and returns plain `str` lists.
- **`mapping.py` is the single translation point:** all event→domain conversion stays there; do not extract names/paths inline in `provider.py` (D-04).
- **REUSE/SPDX:** any new file (e.g. `tests/test_copilot_provenance.py`) must carry the SPDX header block used by every existing module (`SPDX-License-Identifier: GPL-3.0-only`, Canonical copyright) — copy the header from any current source file.
- **Tech stack pins:** `github-copilot-sdk==1.0.2` (do not float); Python 3.12 target. No new runtime dependency.
- **GSD workflow:** file-changing work must go through a GSD command (this is planning input only).
- **No `Co-Authored-By: Claude` trailer** on any commit (global user instruction).
- **Docstrings:** numpy convention (ruff `pydocstyle`), full annotations on non-test code (`ANN`/`D` enforced; tests exempt).

## Sources

### Primary (HIGH confidence)
- Installed `github-copilot-sdk==1.0.2` source — `.venv/.../site-packages/copilot/`: `generated/session_events.py` (`ToolExecutionStartData`, `ToolExecutionCompleteData`, `ToolUserRequestedData`, `ToolInvocation`), `session.py` (`CopilotSession.get_events` docstring + body), `SessionEvent`/`SessionEventType` (`__all__`, members). Verified via `.venv/bin/python -c "import inspect; ..."` and direct object construction.
- Bundled Copilot CLI `~/.copilot/pkg/universal/0.0.420/index.js` — zod input schemas for `view` (`path` = "Full absolute path to file or directory"), `grep` (`pattern` + optional `path` + `output_mode`), `glob` (`pattern` + optional `path`). Extracted by regex over the bundled runtime.
- Repo files — `src/dogen/adapters/copilot/{provider.py,mapping.py,tools.py}`, `src/dogen/core/{models.py,orchestrator.py}`, `tests/test_copilot_backend_unavailable.py`, `tests/test_orchestrator_hitl.py`, `tests/test_models.py`, `tests/test_seam.py`, `scripts/seam_check.py`, `pyproject.toml`. Live artifact `temp/.dogen/units/temperature-api/provenance.yaml` (empty lists confirm the gap).
- Memory `[[live-copilot-path-findings]]` — the 2026-06-20 live run (account `akcano`, CLI `1.0.64-0`, SDK `1.0.2`) where the agent read files but provenance stayed empty.

### Secondary (MEDIUM confidence)
- GitHub Docs "About Copilot CLI" (WebFetch) — confirmed it does NOT document `view`/`grep`/`glob` arg keys (forced reliance on the bundled-CLI schema, which is authoritative for the local runtime).

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Event observation recipe (which type, `data` path, dedup): HIGH — read directly from installed SDK dataclasses; `TOOL_EXECUTION_START` carries name+args, `COMPLETE` does not.
- Argument keys (`view`→`path`): HIGH for bundled CLI `0.0.420`; MEDIUM for the live `1.0.64-0` (A1 — manual-live confirmation pending; omit-on-doubt makes a mismatch safe).
- Seam / no-core-change: HIGH — orchestrator verbatim-copy + import-linter contract read directly.
- Source qualifier (`builtin:`): HIGH — built-ins report `mcp_server_name=None`; hardcoded `builtin:` matches existing asserted tests.

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stable; the one volatile item is the CLI arg-key schema A1 — re-confirm on a CLI upgrade).
