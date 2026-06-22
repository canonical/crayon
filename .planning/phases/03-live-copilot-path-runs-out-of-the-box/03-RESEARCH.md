# Phase 3: Live Copilot path runs out of the box - Research

**Researched:** 2026-06-22
**Domain:** Brownfield hardening of the live `github-copilot-sdk` adapter — model selection, permission handling, family-aware `reasoning_effort`, and JSON-RPC error mapping
**Confidence:** HIGH — every SDK signature, the private-symbol question, the `-32603` semantics, and both seam guardrails were verified by reading the installed SDK source and the project code directly.

## Summary

This phase closes five concrete plumbing gaps in the **existing** Copilot adapter — no net-new domain features. All five land in one code surface: `src/dogen/adapters/copilot/provider.py` (the only place `create_session` is called and the only place backend errors are caught), plus a one-line signature extension in `mock_provider.select_provider` and a one-option addition to the `draft` CLI command. The orchestrator, ports, and `tools.py` are untouched in shape.

The three locked "open research" questions all resolve cleanly in the SDK source: (1) `JsonRpcError` lives at the private `copilot._jsonrpc` module and is **not** re-exported in `copilot.__all__`, but `from copilot._jsonrpc import JsonRpcError` is the sanctioned move **inside the adapter only** — it passes both the AST seam-check and the import-linter contract because both forbid only the top-level `copilot` package *outside* `adapters/copilot/`. (2) The backend model strings are exactly `gpt-5`, `gpt-5-mini`, `claude-sonnet-4.5`, `claude-haiku-4.5` (probed live); a `model.startswith("gpt-5")` prefix predicate is correct and forward-safe. (3) `-32603` is the JSON-RPC internal-error code the backend returns for a rejected model (`Model "X" is not available`), but it is **also** the SDK's generic catch-all internal-error code — so ERR-01 detection must combine `code == -32603` **and** a message signature, falling through to ERR-02 otherwise.

A decisive implementation insight: the SDK already conditionally omits `reasoningEffort` from the wire payload (`client.py:1843`: `if reasoning_effort: payload["reasoningEffort"] = reasoning_effort`). So D-05 is implemented by computing `reasoning_effort = self._effort.value if _is_gpt5_family(self._model) else None` and passing it unconditionally — the SDK drops it when `None`. No conditional-kwargs dict gymnastics are needed.

**Primary recommendation:** Implement all five fixes in `provider.py`'s `_run_draft` and its `try/except`, plus a private `_is_gpt5_family` predicate and a new `ModelRejectedError(RuntimeError)`; extend `select_provider(name, *, model=None, effort=None)` (mock ignores both); add `--model` to `draft`; catch `from copilot._jsonrpc import JsonRpcError` inside the adapter, guarded by a new regression test. Unit-test everything against the existing `_StubClient` fake-SDK pattern — no network in CI.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New default model = `gpt-5-mini` (replaces `_DEFAULT_MODEL = "gpt-5"` in `provider.py`). Stays in the GPT-5 family so the default run still exercises the LIVE-03 reasoning-effort happy path; confirmed available on a standard account.
- **D-02:** Add a `--model` option to `dogen draft` (Typer `Option`, default `None` → provider falls back to its `gpt-5-mini` constant). Mirrors the existing `--provider` shape.
- **D-03:** Thread the chosen model through `select_provider(name, *, model=None, effort=None)`; each factory accepts the kwargs — the **mock factory ignores them** (stays SDK-free, deterministic), the copilot factory forwards them to `CopilotDraftingProvider(model=…)`. Keep dict-dispatch + lazy import (D-25) intact.
- **D-04:** Wire `on_permission_request=PermissionHandler.approve_all` on `create_session` (`from copilot.session import PermissionHandler`). Safe by construction — only `grep`/`glob`/`view` are available (`READONLY`); every write/exec/network tool is unavailable AND on `DENY`.
- **D-05:** Gate `reasoning_effort` with a hardcoded GPT-5-family heuristic — send it only for GPT-5 family, omit for everything else (Claude, unknown). Omit-on-doubt. **Do NOT** adopt `client.list_models()` capability discovery.
- **D-06:** Two handled error types, both `RuntimeError` subclasses — a dedicated model-rejection error (ERR-01, names the model) + broaden the existing `BackendUnavailableError` to also wrap other draft-path `JsonRpcError`s (ERR-02). Both exit nonzero (exit 1).
- **D-07:** Name the rejected model from `self._model`, not by parsing the backend string. Detect "model rejected" by `JsonRpcError` shape (`code == -32603` + not-available signature) but report `self._model`, appending the backend's message for detail.
- **D-08:** Catch `JsonRpcError` inside the adapter (the sanctioned SDK-import site), converting it to the handled domain errors.

### Claude's Discretion

- Exact GPT-5-family match predicate (D-05) and the precise wording of the ERR-01/02 user messages (D-07) — planner/executor choose, within the decisions above.
- Whether `select_provider`'s new `effort` kwarg is wired now or left for a later `--effort` option — model is the LIVE-01 requirement; effort threading is optional scaffolding (the `Effort` enum + per-pass default already exist).

### Deferred Ideas (OUT OF SCOPE)

- **Populating `context_origins`/`tools_used` from observed tool-call events** — that is PROV-01/02, explicitly **Phase 4** (depends on a working live draft from this phase to observe). `mapping.to_draft_result` still honestly records empties until then.
- **Model auto-discovery / "list available models"** — out of scope for v1.1; a clear ERR-01 message naming the rejected model is the sanctioned substitute.
- **Interactive / streaming permission prompts** — out of scope while the toolset is read-only; `approve_all` is sufficient.
- **An `--effort` CLI option** — not required by any v1.1 requirement.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIVE-01 | Operator can choose the model (`--model`); the default is an available model (retire `gpt-5`) | `create_session(model=…)` confirmed (`client.py:1616`, `str \| None`); the available set `gpt-5-mini`/`claude-sonnet-4.5`/`claude-haiku-4.5` is verified live; `_DEFAULT_MODEL` at `provider.py:62`; `--model` mirrors the existing `--provider` Typer option. |
| LIVE-02 | Non-interactive run can read sources — permission handler auto-approves read-only allowlist | `PermissionHandler.approve_all` is a `@staticmethod(request, invocation) -> PermissionDecisionApproveOnce()` (`session.py:350`); `create_session` accepts `on_permission_request`; the SDK gates `requestPermission` on `bool(on_permission_request)` (`client.py:1865`), so a handler must be present for source reads to be approved at all. Safety rests on the existing `READONLY`/`DENY` ToolSets. |
| LIVE-03 | Drafting succeeds on any family — `reasoning_effort` only to GPT-5-family models | `ReasoningEffort = Literal["low","medium","high","xhigh"]` (`session.py:156`); the SDK already omits the param when falsy (`client.py:1843`), so passing `None` for non-GPT-5 models is the clean implementation. Live: `claude-sonnet-4.5` rejects `reasoning_effort`; GPT-5 family accepts it. |
| ERR-01 | Model rejection → clear message naming the model, nonzero exit, never a raw traceback | `JsonRpcError(code, message, data=None)` with `.code`/`.message`/`.data` (`_jsonrpc.py:23`); live signature `-32603 Model "X" is not available`. Report `self._model` (D-07). New `RuntimeError` subclass classified by name in the existing CLI `except RuntimeError` block. |
| ERR-02 | Other live JSON-RPC/backend errors → handled failure + nonzero exit, never a crash | Broaden the `except` list (currently `StopError`/`ConnectionError`/`OSError`/`TimeoutError` — `provider.py:138-145`) to also catch `JsonRpcError` and `ProcessExitedError`, mapping non-model-rejection cases to `BackendUnavailableError`. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Model selection (`--model`) | CLI (`cli/main.py`) | Provider seam (`mock_provider.select_provider`) | The flag is parsed at the CLI, threaded through the by-name dispatch seam, never touching `core/` — `core.DraftingProvider` stays model-agnostic. |
| Provider construction with model/effort | Provider seam (`mock_provider`) | Copilot adapter | `select_provider` is the single construction point (D-25); it forwards to the adapter constructor or ignores in the mock. |
| Permission handling | Copilot adapter (`provider.py`) | SDK (`copilot.session`) | `on_permission_request` is an SDK-coupled concern; it lives entirely behind the seam. The mock has no permission concept. |
| Family-aware `reasoning_effort` | Copilot adapter (`provider.py`) | — | A backend-capability concern (which models accept the param); belongs in the adapter that owns SDK knowledge, not in `core/`. |
| JSON-RPC error → domain error mapping | Copilot adapter (`provider.py`) | CLI classifier (`cli/main.py`) | The adapter catches SDK exceptions (the only place SDK types may appear) and raises `RuntimeError` subclasses; the CLI maps those to exit codes by class name without importing the SDK. |
| Exit-code rendering | CLI (`cli/main.py`) | — | The CLI owns user-facing messages and `typer.Exit` codes; the domain raises, the CLI renders. |

## Standard Stack

This is a brownfield phase: **no new dependencies**. Everything is already installed and pinned. The "stack" below is the verified API surface the phase consumes.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| github-copilot-sdk | 1.0.2 (pinned) | The agent backend (`CopilotClient`, `create_session`, `PermissionHandler`, `JsonRpcError`) | Fixed project decision; the sole SDK behind the seam. [VERIFIED: installed dist metadata + pyproject.toml:33] |
| GitHub Copilot CLI | 1.0.64-0 | Runtime the SDK drives over JSON-RPC | Bundled/pinned; live model strings + `-32603` signature were probed against it (2026-06-20). [CITED: live-copilot-path-findings] |
| Typer | latest | CLI framework; `--model` option | Already the CLI framework; mirror the existing `--provider` option. [VERIFIED: cli/main.py:35] |
| pytest + pytest-asyncio | latest | Async unit tests against the fake SDK | Already the test toolchain; `_StubClient` pattern established. [VERIFIED: tests/test_copilot_backend_unavailable.py] |

### Verified SDK API surface (the exact shapes this phase uses)

```text
# copilot.session  (PUBLIC — re-exported in copilot.__all__)
PermissionHandler.approve_all(request: PermissionRequest, invocation: dict[str, str])
    -> PermissionRequestResult          # returns PermissionDecisionApproveOnce()   [session.py:350]
ReasoningEffort = Literal["low", "medium", "high", "xhigh"]                          # [session.py:156]
SystemMessageAppendConfig                # already imported & working in provider.py:49

# copilot.CopilotClient.create_session(...)  — keyword-only; the kwargs this phase sets:
#   model: str | None = None
#   reasoning_effort: ReasoningEffort | None = None
#   on_permission_request: _PermissionHandlerFn | None = None
#   available_tools: list[str] | ToolSet | None = None
#   excluded_tools:  list[str] | ToolSet | None = None
#   working_directory: str | None = None
#   system_message: SystemMessageConfig | None = None
# -> CopilotSession (an async context manager)                                       [client.py:1612]

# copilot._jsonrpc  (PRIVATE — NOT in copilot.__all__)
class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None): ...
    # attributes: .code (int), .message (str), .data                                 [_jsonrpc.py:23]
class ProcessExitedError(Exception): ...   # raised when the CLI process exits        [_jsonrpc.py:33]
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hardcoded `gpt-5` family heuristic (D-05) | `client.list_models() -> list[ModelInfo]` with `ModelInfo.capabilities.supports.reasoning_effort: bool` and `ModelInfo.supported_reasoning_efforts: list[str] \| None` | The authoritative capability source (`client.py:2748`, `558`, `654`). **Recorded for the future, NOT adopted in v1.1:** it adds a network round-trip, brushes the out-of-scope "model discovery" line, and is not forward-safe in the way the omit-on-doubt heuristic is. The heuristic matches the ROADMAP framing exactly. |
| `from copilot._jsonrpc import JsonRpcError` (private) inside the adapter | Duck-typing on a broad `except Exception` carrying `.code`/`.message` | Recommended: the explicit import (option a). The duck-typing alternative would catch unrelated exceptions that happen to have a `.code`, weakening the ERR-01/ERR-02 split and the seam intent; the private import is sanctioned inside `adapters/copilot/` and is precise. See Pitfall 2 for the regression-test guardrail. |

**Installation:** none — `uv sync` already provides `github-copilot-sdk==1.0.2`.

## Package Legitimacy Audit

> This phase installs **no new packages**. The only external dependency consumed is the already-pinned, already-installed `github-copilot-sdk==1.0.2`, a fixed project decision verified against the installed distribution.

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| github-copilot-sdk | PyPI | GA 2026-06-02; 1.0.2 published 2026-06-18 | n/a (org-published) | github.com/github (Copilot SDK) | OK | Already pinned & installed; no change |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```text
  dogen draft <unit> --provider copilot --model gpt-5-mini
         │
         ▼
  cli/main.py: draft()                         [add --model option; keep except-RuntimeError classifier]
         │  provider, model
         ▼
  mock_provider.select_provider(name, *, model=None, effort=None)   [D-03: extend signature]
         │                                  └── "mock"  → MockDraftingProvider()      (ignores model/effort, no SDK)
         │ "copilot"
         ▼
  adapters/copilot/provider.CopilotDraftingProvider(model=…)        [D-01 default gpt-5-mini]
         │  draft_unit(intent, audience, steering, sources)
         ▼
  _run_draft():
     reasoning_effort = self._effort.value if _is_gpt5_family(self._model) else None   [D-05]
     create_session(
        model=self._model,
        reasoning_effort=reasoning_effort,           # SDK omits it from wire when None
        on_permission_request=PermissionHandler.approve_all,    [D-04]
        available_tools=READONLY, excluded_tools=DENY,          (unchanged security boundary)
        working_directory=<abs>, system_message=<steer>)
         │
         ▼  send_and_wait(prompt)
  ┌──────────────── try / except (the ERR-01/ERR-02 mapping site) ───────────────┐
  │  except JsonRpcError as e:                                                    │
  │     if e.code == -32603 and _is_model_not_available(e.message):              │
  │         raise ModelRejectedError(self._model, e.message)   → ERR-01          │
  │     raise BackendUnavailableError(...)                     → ERR-02          │
  │  except StopError / ConnectionError / OSError / TimeoutError / ProcessExited │
  │     raise BackendUnavailableError(...)                     → ERR-02 (existing)│
  └──────────────────────────────────────────────────────────────────────────────┘
         │ raises RuntimeError subclass
         ▼
  cli/main.py: except RuntimeError → classify by type(exc).__name__ → typer.Exit(code=1)
```

### Recommended Project Structure (unchanged — files edited in place)
```
src/dogen/
├── adapters/
│   ├── copilot/
│   │   ├── provider.py     # _DEFAULT_MODEL→gpt-5-mini; _is_gpt5_family; permission handler;
│   │   │                   #   conditional effort; ModelRejectedError; JsonRpcError catch
│   │   ├── tools.py        # UNCHANGED (READONLY/DENY — the security boundary D-04 leans on)
│   │   ├── mapping.py      # UNCHANGED (PROV-01/02 is Phase 4)
│   │   └── __init__.py     # export the new ModelRejectedError alongside BackendUnavailableError
│   └── mock_provider.py    # select_provider signature + both factories accept *, model, effort
├── cli/main.py             # draft(): add --model; classifier already handles by-name dispatch
└── core/                   # UNCHANGED (ports/orchestrator/models stay in shape)
```

### Pattern 1: SDK omits the param for you — compute, don't branch the kwargs
**What:** D-05's family gate is implemented by computing `reasoning_effort` to `None` for non-GPT-5 models and passing it unconditionally; the SDK drops `None` from the wire payload.
**When to use:** the LIVE-03 fix in `_run_draft`.
**Example:**
```python
# Source: verified against copilot/client.py:1843 — `if reasoning_effort: payload["reasoningEffort"] = ...`
# self._effort.value is a str in {"low","medium","high","xhigh"} — matches ReasoningEffort literal.
reasoning_effort = self._effort.value if _is_gpt5_family(self._model) else None
session_cm = await client.create_session(
    model=self._model,
    reasoning_effort=reasoning_effort,                      # None → SDK omits it (Claude-safe)
    on_permission_request=PermissionHandler.approve_all,    # D-04
    available_tools=READONLY,
    excluded_tools=DENY,
    working_directory=self._working_directory,
    system_message=SystemMessageAppendConfig(mode="append", content=steer),
)
```
This avoids a "build a kwargs dict and conditionally insert" idiom (which `ruff` would not love anyway). Note `self._effort.value` is the plain `StrEnum` value (`core/models.py:70`) — no SDK type crosses the constructor.

### Pattern 2: Private-symbol catch inside the sanctioned subtree
**What:** Catch the SDK's private `JsonRpcError` only inside `adapters/copilot/provider.py`, classify it, and re-raise a domain `RuntimeError` subclass.
**When to use:** the ERR-01/ERR-02 mapping.
**Example:**
```python
# Source: verified against copilot/_jsonrpc.py:23 (JsonRpcError) and copilot/_jsonrpc.py:33 (ProcessExitedError).
# This import is OK: both seam guardrails forbid `copilot` only OUTSIDE adapters/copilot/.
from copilot._jsonrpc import JsonRpcError, ProcessExitedError

_MODEL_NOT_AVAILABLE_CODE = -32603  # JSON-RPC internal-error code the backend returns for a rejected model

def _is_model_not_available(message: str) -> bool:
    # D-07: detect by signature, but DO NOT parse the model out — we report self._model.
    return "is not available" in message.lower()

# in the except block:
except JsonRpcError as exc:
    if exc.code == _MODEL_NOT_AVAILABLE_CODE and _is_model_not_available(exc.message):
        raise ModelRejectedError(
            f"Model {self._model!r} was rejected by the backend: {exc.message}"
        ) from exc
    raise BackendUnavailableError(
        f"Copilot backend error (JSON-RPC {exc.code}): {exc.message}"
    ) from exc
except ProcessExitedError as exc:
    raise BackendUnavailableError(f"Copilot CLI process exited: {exc}") from exc
```

### Pattern 3: New error type plugs into the existing name-classifier
**What:** `ModelRejectedError(RuntimeError)` is classified in the CLI's existing `except RuntimeError` block by `type(exc).__name__`, so the mock path never imports `adapters/copilot/`.
**Example:**
```python
# Source: verified against cli/main.py:227-236 (the existing classifier).
except RuntimeError as exc:
    name = type(exc).__name__
    if name == "ModelRejectedError":
        typer.echo(f"{exc}", err=True)
        raise typer.Exit(code=1) from exc
    if name == "BackendUnavailableError":
        typer.echo(f"Copilot backend unavailable: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    raise
```
The classifier matches by string name precisely so it does not need to import the adapter (D-25). The planner may keep the dict-dispatch style the coding guide §2 prefers over an if/elif ladder.

### Anti-Patterns to Avoid
- **Re-exporting `JsonRpcError` from `core/` or the CLI** to "catch it there" — that would import `copilot` outside the adapter and fail both guardrails. The catch MUST be in `provider.py`.
- **Parsing the model name out of the backend message** (D-07 forbids it) — report `self._model`; only the *detail* comes from `exc.message`.
- **A custom allowlist-checking permission handler** — `approve_all` is safe by construction because `READONLY`/`DENY` already constrain the tools; a custom handler re-implements a guarantee the toolset enforces (D-04).
- **Calling `client.list_models()` to decide effort** — out of scope (model discovery) and adds a round-trip; use the prefix heuristic (D-05).
- **Branching `available_tools` / `excluded_tools`** — leave `tools.py` and the `READONLY`/`DENY` wiring exactly as-is.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Omitting `reasoning_effort` for Claude | A conditional kwargs dict assembled before `create_session` | Pass `reasoning_effort=None`; the SDK omits it (`client.py:1843`) | Less code, no `ruff` SIM/complexity smell; the SDK already does the right thing. |
| Permission auto-approval | A handler that inspects each request against an allowlist | `PermissionHandler.approve_all` | The `READONLY`/`DENY` ToolSets are the real boundary; a custom handler duplicates it (D-04). |
| Model capability detection | A live `list_models()` lookup + capability map | The `model.startswith("gpt-5")` heuristic, omit-on-doubt | Discovery is out of scope; the heuristic is forward-safe and round-trip-free (D-05). |
| JSON-RPC parsing | A regex over the backend error string to extract the model | `self._model` + the `-32603` + signature check | Robust to backend message-format drift (D-07). |

**Key insight:** Almost every gap here is closed by *passing the right argument the SDK already supports*, not by writing new machinery. The phase's risk is in the **error-classification edge** (`-32603` overload — see Pitfall 1), not in the happy-path wiring.

## Runtime State Inventory

This is a code-only hardening phase — no rename, no migration, no stored runtime state to reconcile.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastore keys, collection names, or IDs change | none |
| Live service config | None — no external service config embeds a changed string (the Copilot account/CLI are unchanged; only the *default model requested* changes, which is a code constant) | none |
| OS-registered state | None — no OS-level registrations involved | none |
| Secrets/env vars | None — no secret or env-var name changes (the Copilot auth path is unchanged) | none |
| Build artifacts | None — no package rename; `_DEFAULT_MODEL` constant change does not affect installed artifacts | none |

**Nothing found in any category:** verified by reading the full implementation surface — the only persistent change is the value of two source constants (`_DEFAULT_MODEL`) and new code paths.

## Common Pitfalls

### Pitfall 1: `-32603` is overloaded — model-rejection AND the SDK's generic internal-error code
**What goes wrong:** Treating *any* `JsonRpcError(code=-32603)` as "model rejected" (ERR-01) would mislabel unrelated backend internal errors, and a real model rejection that the backend phrases differently could be missed.
**Why it happens:** `-32603` is the JSON-RPC "Internal error" code. The backend returns it for `Model "X" is not available` (live-confirmed), **but the SDK itself also emits `-32603` as the catch-all for any handler exception** (`_jsonrpc.py:456`: `await self._send_error_response(message["id"], -32603, str(exc), None)`). The known working-directory bug already documented in `provider.py:37` is *also* a `-32603` (`"Directory path must be absolute"`).
**How to avoid:** Require **both** `code == -32603` **and** a message signature (e.g. `"is not available" in message.lower()`) for ERR-01; everything else with `-32603` falls through to ERR-02 (`BackendUnavailableError`). Add a unit test that raises `JsonRpcError(-32603, "Directory path must be absolute")` and asserts it maps to ERR-02, **not** ERR-01.
**Warning signs:** A test that asserts ERR-01 purely on the code, or a directory/permission `-32603` rendering as a "model rejected" message.

### Pitfall 2: The private `copilot._jsonrpc` import can break silently on an SDK bump
**What goes wrong:** `JsonRpcError` is not in `copilot.__all__` (verified — it is a private module symbol). A future SDK patch could move or rename it, and `from copilot._jsonrpc import JsonRpcError` would then `ImportError` at adapter import time — taking down the whole copilot path.
**Why it happens:** Importing a private symbol is an unsanctioned coupling that no public-API contract protects.
**How to avoid:** Per D-08, add a **regression test** that imports `JsonRpcError` from `copilot._jsonrpc` and asserts it is the class the adapter catches (instantiate `JsonRpcError(-32603, "x")`, assert `.code`/`.message`). This converts a silent future breakage into a loud, early CI failure and documents the coupling. Pin the SDK (already done) and gate upgrades behind this test (matches the project's "pin both; gate upgrades behind a smoke test" stance).
**Warning signs:** An `ImportError` mentioning `_jsonrpc` after a `uv sync` that bumped the SDK.

### Pitfall 3: `working_directory` must be absolute (already handled — don't regress it)
**What goes wrong:** A relative `working_directory` (e.g. `"."`) is rejected by the backend with `-32603 "Directory path must be absolute"`.
**Why it happens:** Backend constraint, documented at `provider.py:37`.
**How to avoid:** The provider already resolves to `os.path.abspath(...)` in `__init__` (`provider.py:100`). Keep it; do not let a refactor of the constructor drop it. This is also why Pitfall 1's both-conditions check matters: this error is a `-32603` that must map to ERR-02.

### Pitfall 4: Threading `model`/`effort` must not make the mock import the SDK (D-25)
**What goes wrong:** Adding `model`/`effort` kwargs to `select_provider` and eagerly constructing the copilot provider, or letting the mock factory touch SDK types, would defeat the lazy-import seam and break CI (no token/network).
**Why it happens:** Over-eager refactoring of the dict-dispatch.
**How to avoid:** Keep `_make_copilot_provider` a lazy-import factory; give both factories a uniform `(*, model=None, effort=None)` signature; the mock factory simply ignores them. Add a test asserting `select_provider("mock", model="gpt-5-mini")` returns a working mock and that `sys.modules` gains no `copilot` entry on the mock path (extend the existing seam tests).

### Pitfall 5: `PermissionHandler.approve_all` is a bare staticmethod — pass it, don't call it
**What goes wrong:** Passing `PermissionHandler.approve_all()` (called) instead of `PermissionHandler.approve_all` (the callable) would pass the *result* (a `PermissionDecisionApproveOnce`) rather than the handler, and the SDK validates `callable(on_permission_request)` (`client.py:1792`), raising `ValueError`.
**How to avoid:** Pass the unbound staticmethod reference: `on_permission_request=PermissionHandler.approve_all`. Verified signature: `approve_all(request, invocation) -> PermissionRequestResult` (`session.py:350-354`).

## Code Examples

### Family predicate (D-05) — Claude's discretion on prefix vs allowlist
```python
# Source: live-confirmed model strings gpt-5, gpt-5-mini (GPT-5 family);
#         claude-sonnet-4.5, claude-haiku-4.5 (reject reasoning_effort).
# Prefix is forward-safe: a future gpt-5-* variant is covered; an unknown model omits the param.
def _is_gpt5_family(model: str) -> bool:
    """Return whether the model accepts ``reasoning_effort`` (GPT-5 family only)."""
    return model.startswith("gpt-5")
```
Recommendation: **prefix `gpt-5`** over an allowlist — it covers unseen `gpt-5-*` variants while still omitting the param for anything non-GPT-5 (omit-on-doubt, D-05). An allowlist would silently drop a new `gpt-5-nano` from the effort path.

### New error type + adapter export
```python
# Source: mirrors the existing BackendUnavailableError (provider.py:68) and its __init__ export.
class ModelRejectedError(RuntimeError):
    """The backend rejected the requested model (e.g. JSON-RPC -32603 'not available').

    Carries a message naming the *requested* model (self._model), not a parsed
    backend string (D-07). The CLI classifies it by name to a nonzero exit (ERR-01).
    """
# adapters/copilot/__init__.py:
# __all__ = ["BackendUnavailableError", "CopilotDraftingProvider", "ModelRejectedError"]
```

### Extended `select_provider` (D-03)
```python
# Source: extends mock_provider.py:154-184. Factories take uniform kwargs; mock ignores them.
def _make_mock_provider(*, model: str | None = None, effort: Effort | None = None) -> DraftingProvider:
    return MockDraftingProvider()  # deterministic; model/effort intentionally ignored (D-23/D-25)

def _make_copilot_provider(*, model: str | None = None, effort: Effort | None = None) -> DraftingProvider:
    from dogen.adapters.copilot import CopilotDraftingProvider  # noqa: PLC0415  (lazy, D-25)
    kwargs: dict[str, object] = {}
    if model is not None:
        kwargs["model"] = model
    if effort is not None:
        kwargs["effort"] = effort
    return CopilotDraftingProvider(**kwargs)  # falls back to gpt-5-mini default when model is None

def select_provider(
    name: str = _DEFAULT_PROVIDER, *, model: str | None = None, effort: Effort | None = None
) -> DraftingProvider:
    try:
        factory = _PROVIDER_FACTORIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDER_FACTORIES))
        raise ValueError(f"unknown provider {name!r}; choose one of: {known}") from exc
    return factory(model=model, effort=effort)
```
Note: `Effort` is already importable in `mock_provider` from `core.models` without any SDK coupling (it is a plain `StrEnum`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded `_DEFAULT_MODEL = "gpt-5"` | Operator-selectable `--model`, default `gpt-5-mini` | This phase (LIVE-01) | Bare command works out of the box on a standard account. |
| No permission handler (reads denied non-interactively) | `on_permission_request=PermissionHandler.approve_all` | This phase (LIVE-02) | Source reads actually happen; the agent grounds the draft instead of asking for a paste. |
| Unconditional `reasoning_effort` | Family-gated (`None` for non-GPT-5) | This phase (LIVE-03) | Claude-family models draft instead of erroring on the parameter. |
| `JsonRpcError` escapes as a raw traceback | Caught in-adapter, mapped to `ModelRejectedError`/`BackendUnavailableError` | This phase (ERR-01/02) | Clean message + nonzero exit; closes accepted debt #4. |

**Deprecated/outdated:** none — this is forward hardening of v1.0 code; no API in use is deprecated.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `-32603` model-not-available message contains the phrase `"is not available"` (case-insensitive) reliably enough to key ERR-01 off it | Pitfall 1 / Pattern 2 | LOW — verified against the one live observation (`Model "X" is not available`). If the backend rephrases, a model rejection would fall through to ERR-02 (still a clean handled error + nonzero exit, just the generic message rather than the model-named one). The model name in the user message comes from `self._model` regardless (D-07), so the actionable part is robust; only the ERR-01-vs-ERR-02 *routing* depends on the signature. Mitigation: keep the signature check broad (substring, lowercased) and add a test fixture mirroring the live string. |
| A2 | `gpt-5-mini` remains available on a standard Copilot account at execution time | LIVE-01 / D-01 | LOW — confirmed available on 2026-06-20 (`live-copilot-path-findings`). If retired by the backend later, the bare-command default would itself trigger ERR-01 — which is exactly the clean handled failure this phase delivers, so the failure mode is graceful, not a crash. Verification is a manual live run (D-24). |

**Note:** Both assumptions are LOW risk and degrade gracefully (worse case = a clean ERR-02 message instead of a clean ERR-01 message, or a clean ERR-01 on a retired default). Neither can produce an uncaught traceback, which is the property the phase guarantees.

## Open Questions (RESOLVED)

1. **Should the `effort` kwarg be wired through `select_provider` now, or deferred?**
   - What we know: CONTEXT.md D-05/Discretion says model is the LIVE-01 requirement; effort threading is optional scaffolding (the `Effort` enum + per-pass default already exist, and there is no `--effort` flag in v1.1 scope).
   - What's unclear: whether the planner wants the seam ready for a future `--effort` or kept minimal.
   - Recommendation: wire the `effort` *kwarg* through `select_provider` (cheap, symmetric with `model`, ignored by the mock) but do **not** add a `--effort` CLI option (deferred). This keeps the seam future-ready without scope creep.
   - **RESOLVED:** wired now — plan `03-02` Task 2 extends `select_provider(name, *, model=None, effort=None)` and forwards `effort`; no `--effort` CLI option is added (deferred per CONTEXT.md Discretion).

2. **Dict-dispatch vs. inline `if` for the CLI error classifier.**
   - What we know: the existing classifier (`cli/main.py:233`) uses an inline `if type(exc).__name__ == ...`; coding-guide §2 prefers dict dispatch over if/elif ladders for assigning one value.
   - What's unclear: whether two error types justify converting to a dict-dispatch `{name: (message_template, code)}`.
   - Recommendation: two cases is the borderline "rule of three" case — either is defensible. A small `{name: render_fn}` map reads cleanly and pre-empts a third error type; the planner/executor chooses (Discretion).
   - **RESOLVED:** left to executor discretion (plan `03-02` Task 2) — both an inline `if` chain and a small `{name: render_fn}` map are accepted for two error types; neither is mandated.

## Environment Availability

> The **live** path is manual-only (D-24) — CI has no token or network. Unit tests run against a fake/stub SDK and need no live backend. This table reflects what the *manual live verification* (success criteria 1-3) requires; CI requires none of it.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| github-copilot-sdk | Adapter import (all tests + live) | ✓ | 1.0.2 | — (pinned, installed) |
| Copilot CLI runtime | Manual live draft only | ✓ (dev machine) | 1.0.64-0 | Unit tests against `_StubClient` cover CI; live run is manual |
| Copilot account/token | Manual live draft only | manual | n/a | Not in CI by design (D-24); fake SDK substitutes |
| pytest + pytest-asyncio | All unit tests | ✓ | installed | — |

**Missing dependencies with no fallback:** none for CI (the whole phase is CI-testable against the fake SDK).
**Missing dependencies with fallback:** the live token/account is intentionally absent from CI; the `_StubClient` fake SDK is the fallback for every automated assertion. Success criteria 1-3 (a real written draft) require a manual live run on the dev machine.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_copilot_backend_unavailable.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
All tests extend the established `_StubClient` + `monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", factory)` pattern — **no network, no live SDK**. The stub's `create_session` is scripted to **record the kwargs it receives** (so tests assert presence/absence) and/or **raise a fake `JsonRpcError`** (so tests assert the ERR mapping).

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIVE-01 | `CopilotDraftingProvider()` default model is `gpt-5-mini`; `select_provider("copilot", model="x")` forwards `model` | unit | `uv run pytest tests/test_copilot_model_selection.py -x` | ❌ Wave 0 |
| LIVE-01 | `select_provider("mock", model="x")` ignores model, imports no SDK | unit | `uv run pytest tests/test_seam.py tests/test_copilot_model_selection.py -x` | ⚠️ extend seam test |
| LIVE-02 | `create_session` is called with `on_permission_request=PermissionHandler.approve_all` | unit (assert kwarg) | `uv run pytest tests/test_copilot_session_kwargs.py -x` | ❌ Wave 0 |
| LIVE-03 | GPT-5 model → `reasoning_effort` present in `create_session` kwargs; Claude model → `reasoning_effort` is `None`/absent | unit (parametrized, assert kwarg present/absent) | `uv run pytest tests/test_copilot_session_kwargs.py -x` | ❌ Wave 0 |
| ERR-01 | A fake `JsonRpcError(-32603, 'Model "x" is not available')` → `ModelRejectedError` naming `self._model` | unit | `uv run pytest tests/test_copilot_error_mapping.py -x` | ❌ Wave 0 |
| ERR-02 | A fake `JsonRpcError(-32603, 'Directory path must be absolute')` and a non-`-32603` `JsonRpcError` → `BackendUnavailableError` (NOT `ModelRejectedError`) | unit (parametrized) | `uv run pytest tests/test_copilot_error_mapping.py -x` | ❌ Wave 0 |
| ERR-01/02 | CLI renders `ModelRejectedError`/`BackendUnavailableError` as exit-1 clean messages (CliRunner, mock provider that raises) | unit | `uv run pytest tests/test_cli_draft_errors.py -x` | ❌ Wave 0 |
| D-08 | Regression: `from copilot._jsonrpc import JsonRpcError` succeeds and is the class the adapter catches | unit | `uv run pytest tests/test_copilot_jsonrpc_import.py -x` | ❌ Wave 0 |

**Test-design note (assert kwargs):** to assert LIVE-02/LIVE-03 the stub's `create_session` must capture its call kwargs. Extend `_StubClient` with a `create_session(self, **kwargs)` that stores `self.session_kwargs = kwargs` and returns a stub session context manager whose `send_and_wait` returns a scripted `assistant.message` event (so the happy path completes). Then assert on `stub.session_kwargs["on_permission_request"]` and `stub.session_kwargs.get("reasoning_effort")`.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_copilot_*.py -x` (the adapter test cluster)
- **Per wave merge:** `uv run pytest` (full suite — includes seam guardrails + import-linter test)
- **Phase gate:** Full suite green, `uv run lint-imports` (import-linter), and `python scripts/seam_check.py` clean before `/gsd-verify-work`; plus the **manual live runs** for success criteria 1-3 (D-24, off-CI).

### Wave 0 Gaps
- [ ] `tests/test_copilot_session_kwargs.py` — covers LIVE-02, LIVE-03 (requires the kwargs-capturing `_StubClient` extension)
- [ ] `tests/test_copilot_error_mapping.py` — covers ERR-01, ERR-02 (fake `JsonRpcError` injection)
- [ ] `tests/test_copilot_model_selection.py` — covers LIVE-01 (default + threading)
- [ ] `tests/test_cli_draft_errors.py` — covers the CLI exit-code rendering (Typer `CliRunner`)
- [ ] `tests/test_copilot_jsonrpc_import.py` — covers D-08 regression (private-import guardrail)
- [ ] Extend `_StubClient` in `tests/test_copilot_backend_unavailable.py` (or a shared `conftest.py` fixture) to capture `create_session` kwargs and return a scripted session — the shared harness all new tests build on.

## Security Domain

> `security_enforcement` is not explicitly disabled in config, so this section is included. The phase's security surface is narrow but real: it *widens* what the agent is permitted to do (auto-approving tool calls), so the threat model must confirm the boundary holds.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | The provider seam (ports + AST guardrail + import-linter) keeps SDK/error types out of `core/`; unchanged by this phase. |
| V4 Access Control | yes | `READONLY` allowlist + `DENY` denylist (`tools.py`) — the boundary that makes `approve_all` safe. **Must not be broadened** (out of scope, REQUIREMENTS.md). |
| V5 Input Validation | yes | Source content the agent reads is untrusted (prompt-injection vector T-02.3-01/02); the read-only toolset is the mitigation, not input sanitization. |
| V7 Error Handling | yes | ERR-01/ERR-02 ensure backend errors become handled failures with clean messages, never raw tracebacks that could leak internals or crash (SKEL-05/D-27). |
| V2 Auth / V3 Session / V6 Crypto | no | No auth, session, or crypto code is introduced; Copilot auth is the SDK's concern, unchanged. |

### Known Threat Patterns for the Copilot adapter

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Injected instructions in read source content try to make the agent write/exec/reach the network | Elevation of Privilege / Tampering (T-02.3-01/02) | `approve_all` can only ever approve a tool that is *available*, and only `grep`/`glob`/`view` are available; every mutating tool is both unavailable AND on `DENY`. Auto-approval is therefore safe **by construction** — the security guarantee is in the ToolSet, not the handler (D-04). |
| Over-broad permission handler approves a future write tool | Elevation of Privilege | Keep the toolset read-only (do not broaden — explicitly out of scope). If a tool is ever added, the handler decision must be revisited; a test asserting `READONLY == {grep, glob, view}` guards this. |
| Raw `JsonRpcError`/stack trace leaks backend internals or crashes the loop | Information Disclosure / DoS | ERR-01/ERR-02 convert every draft-path JSON-RPC/backend error into a handled `RuntimeError` subclass with a curated message and nonzero exit. |
| Private-symbol import (`copilot._jsonrpc`) breaks on SDK bump, disabling error handling | DoS (availability of the feature) | The D-08 regression test fails loudly on an SDK change rather than silently dropping the JsonRpcError catch (Pitfall 2). |

**Net security posture:** the phase *adds* auto-approval but does not widen the blast radius, because the tool allowlist — the actual control — is unchanged. The one new coupling (private import) is guarded by a regression test. Recommend the planner add an explicit assertion that `tools.py`'s `READONLY`/`DENY` names are unchanged, so a future edit cannot quietly broaden what `approve_all` can approve.

## Project Constraints (from CLAUDE.md / coding-guide.md)

The planner MUST verify plans honor these (treated with the authority of locked decisions):

- **Seam (coding-guide §6, SEAM-01/02):** `copilot`/`github_copilot_sdk` may be imported **only** under `adapters/copilot/`. The new `from copilot._jsonrpc import JsonRpcError` and `from copilot.session import PermissionHandler` MUST live in `provider.py`, never in `core/` or `cli/`. Enforced by `scripts/seam_check.py` (AST) + import-linter (`pyproject.toml:100`); both forbid the top-level `copilot` package outside the adapter — verified that the private submodule import passes inside the adapter.
- **No SDK type crosses into `core/`:** the new `ModelRejectedError` is a plain `RuntimeError` subclass (no SDK type in its signature); `Effort` threaded through `select_provider` is a plain `StrEnum`. The CLI classifies by `type(exc).__name__` (string), never by importing the SDK (D-25).
- **REUSE/SPDX headers (coding-guide §7):** every new source file (the new test files, any new module) MUST carry the full GPL-3.0-only notice block shown in the guide — not a bare SPDX line. `reuse lint` gates CI.
- **Toolchain:** `ruff` (lint+format) + `ty` (type checker), `uv` for env/lock. Target Python 3.12. Precise types; `typing.Any` banned in signatures; full annotations + NumPy-style docstrings (params/returns/raises) on every public function.
- **Functions ≤ 60 lines; no if/elif ladder to assign one value** (use dict dispatch / ternary / match) — relevant to the CLI error classifier and `_run_draft`'s growing body (consider extracting the kwargs build + the except mapping into small helpers).
- **Don't over-mock (coding-guide §4):** mock only at the true boundary — the SDK `CopilotClient`. Use the real `CopilotDraftingProvider`, real `select_provider`, real CLI; inject the fake SDK at `provider.CopilotClient` exactly as the existing test does.
- **Determinism:** tests pass with fresh context, no network, any order (D-24). No live calls in CI.
- **GitHub via `gh` (global CLAUDE.md):** any PR/issue work uses `gh`. **No `Co-Authored-By: Claude` trailer** on commits/PRs.
- **GSD workflow:** edits go through a GSD command (this is the research step; implementation is `/gsd-execute-phase`).

## Sources

### Primary (HIGH confidence — read directly this session)
- `.venv/lib/python3.12/site-packages/copilot/_jsonrpc.py` — `JsonRpcError(code, message, data)` definition (line 23), `.code`/`.message`/`.data` attributes, `ProcessExitedError` (line 33), the SDK's own `-32603` catch-all emission (line 456), and confirmation `JsonRpcError` is NOT in any `__all__`.
- `.venv/lib/python3.12/site-packages/copilot/__init__.py` — the public `__all__` (298 lines); confirms `PermissionHandler`, `ReasoningEffort`-bearing types, `ModelInfo`/`ModelSupports` are public but `JsonRpcError` is not.
- `.venv/lib/python3.12/site-packages/copilot/session.py` — `PermissionHandler.approve_all` staticmethod (350-354), `ReasoningEffort = Literal[...]` (156), `PermissionDecisionApproveOnce`.
- `.venv/lib/python3.12/site-packages/copilot/client.py` — full `create_session` signature (1612-1676), the `if reasoning_effort:` conditional wire-payload omission (1843), `requestPermission = bool(on_permission_request)` gating (1865), `callable()` validation (1792), `list_models() -> list[ModelInfo]` (2748), `ModelInfo`/`ModelSupports`/`ModelCapabilities` dataclasses (558/579/654).
- Project source: `provider.py`, `tools.py`, `mock_provider.py`, `cli/main.py`, `core/orchestrator.py`, `core/ports.py`, `adapters/copilot/__init__.py`, `tests/test_copilot_backend_unavailable.py`, `tests/test_seam.py`, `scripts/seam_check.py`, `pyproject.toml` (import-linter contract), `.planning/refs/coding-guide.md`.

### Secondary (HIGH confidence — empirical)
- Memory `live-copilot-path-findings` (2026-06-20 live run, account `akcano`, CLI `1.0.64-0`, SDK `1.0.2`) — the four gaps, the probed available model set (`gpt-5-mini`, `claude-sonnet-4.5`, `claude-haiku-4.5`), the `-32603 Model "X" is not available` signature, the `reasoning_effort` rejection on Claude, and the working `gpt-5-mini` source-grounded draft after wiring `approve_all`.

### Tertiary (LOW confidence)
- none — every load-bearing claim was verified against installed SDK source or project code this session.

## Metadata

**Confidence breakdown:**
- Standard stack / API surface: HIGH — every kwarg, type, and attribute read from the installed 1.0.2 source.
- Architecture / seam: HIGH — both guardrails (AST + import-linter) read; the private-import-inside-adapter conclusion follows directly from their exempt-subtree logic.
- Pitfalls: HIGH — the `-32603` overload is verified in SDK source (line 456) and project docs (`provider.py:37`); the private-symbol fragility is verified against `__all__`.
- Error-signature detection (ERR-01 vs ERR-02): MEDIUM — keyed to one live observation of the message string (logged as Assumption A1, LOW risk, degrades gracefully).

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stable; re-verify the model availability and `-32603` signature on the next live run or any `github-copilot-sdk` bump — both are pin-gated).
