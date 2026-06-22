# Phase 3: Live Copilot path runs out of the box - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 10 (4 modified in place, 6 new test files)
**Analogs found:** 10 / 10

This is a **brownfield** phase. The four modified files have their analog *inside themselves* — the convention to match is the file's own existing idiom (the `BackendUnavailableError` class, the existing `except` block, the dict-dispatch factory, the CLI name-classifier). The six new test files all descend from one harness: `_StubClient` in `tests/test_copilot_backend_unavailable.py`.

## File Classification

| File | New/Mod | Role | Data Flow | Closest Analog | Match Quality |
|------|---------|------|-----------|----------------|---------------|
| `src/dogen/adapters/copilot/provider.py` | modified | adapter/provider | request-response | self (existing `BackendUnavailableError`, `_run_draft`, `except` block) | in-file |
| `src/dogen/adapters/copilot/__init__.py` | modified | seam/barrel | — | self (existing `BackendUnavailableError` export) | in-file |
| `src/dogen/adapters/mock_provider.py` | modified | provider seam/factory | dispatch | self (existing `_PROVIDER_FACTORIES` dict-dispatch + `select_provider`) | in-file |
| `src/dogen/cli/main.py` | modified | CLI controller | request-response | self (`draft()` `--provider` option + `except RuntimeError` classifier) | in-file |
| `tests/test_copilot_model_selection.py` | new | unit test | — | `tests/test_copilot_backend_unavailable.py` (`_StubClient`) | exact-role |
| `tests/test_copilot_session_kwargs.py` | new | unit test (assert kwargs) | — | `tests/test_copilot_backend_unavailable.py` (extended `_StubClient`) | exact-role |
| `tests/test_copilot_error_mapping.py` | new | unit test (inject error) | — | `tests/test_copilot_backend_unavailable.py` (`_StubClient` + scripted raise) | exact-role |
| `tests/test_cli_draft_errors.py` | new | unit test (CliRunner) | — | `tests/test_cli_unit_new.py` (Typer `CliRunner`) | exact-role |
| `tests/test_copilot_jsonrpc_import.py` | new | unit test (import regression) | — | `tests/test_copilot_mapping.py` (plain import-level asserts) | role-match |
| `tests/test_copilot_toolset_boundary.py` | new | unit test (V4 boundary) | — | `tests/test_copilot_mapping.py::test_toolsets_are_source_qualified_builtins` | exact |

---

## Pattern Assignments — Modified Files

### `src/dogen/adapters/copilot/provider.py` (adapter, request-response)

**Analog:** self. Match the file's own conventions exactly.

**1. New default model (D-01)** — change the constant at `provider.py:62`:
```python
# CURRENT (provider.py:62)
_DEFAULT_MODEL = "gpt-5"
# CHANGE TO
_DEFAULT_MODEL = "gpt-5-mini"
```
Note: the docstring on `CopilotDraftingProvider.__init__` (`provider.py:82`) says `defaults to the skeleton's ``gpt-5```; update it to match.

**2. New error type (D-06)** — mirror the existing `BackendUnavailableError` class at `provider.py:68-73` exactly (same shape, NumPy-style class docstring, `RuntimeError` base, no SDK type in signature):
```python
class BackendUnavailableError(RuntimeError):
    """The Copilot backend is down, unauthenticated, or its transport broke.

    Raised instead of letting a raw SDK/connection failure crash the loop, so
    the CLI can surface a clear message and a nonzero exit (SKEL-05/D-27).
    """
```
Add a sibling `ModelRejectedError(RuntimeError)` next to it with the same docstring style. Per D-07 its message names `self._model`, not a parsed backend string.

**3. SDK imports (D-04, D-08)** — extend the two existing import blocks at `provider.py:43-49`. `PermissionHandler` joins the public `copilot.session` import; `JsonRpcError`/`ProcessExitedError` come from the *private* `copilot._jsonrpc` (sanctioned only inside this subtree):
```python
# CURRENT
from copilot import CopilotClient, SessionEvent, SessionEventType, StopError
from copilot.session import SystemMessageAppendConfig
# ADD
from copilot._jsonrpc import JsonRpcError, ProcessExitedError  # private; OK inside adapter only
from copilot.session import PermissionHandler, SystemMessageAppendConfig
```

**4. `create_session` kwargs (D-04, D-05)** — the call lives at `provider.py:169-176`. Currently passes `reasoning_effort=self._effort.value` unconditionally and no permission handler:
```python
# CURRENT (provider.py:169-176)
session_cm = await client.create_session(
    model=self._model,
    reasoning_effort=self._effort.value,
    available_tools=READONLY,
    excluded_tools=DENY,
    working_directory=self._working_directory,
    system_message=SystemMessageAppendConfig(mode="append", content=steer),
)
```
Compute effort to `None` for non-GPT-5 (SDK drops `None` from the wire — RESEARCH Pattern 1), add `on_permission_request`. Leave `available_tools=READONLY` / `excluded_tools=DENY` untouched:
```python
reasoning_effort = self._effort.value if _is_gpt5_family(self._model) else None
session_cm = await client.create_session(
    model=self._model,
    reasoning_effort=reasoning_effort,
    on_permission_request=PermissionHandler.approve_all,  # D-04: pass, don't call
    available_tools=READONLY,
    excluded_tools=DENY,
    working_directory=self._working_directory,
    system_message=SystemMessageAppendConfig(mode="append", content=steer),
)
```
Add a module-level `_is_gpt5_family(model: str) -> bool` helper near the other module functions (`provider.py:185+`), with a NumPy-style docstring like the existing `_require_available_backend`.

**5. Broaden the `except` (ERR-01/ERR-02, D-06/D-07/D-08)** — the current `try/except` is at `provider.py:136-145` and notably **omits `JsonRpcError`**:
```python
# CURRENT (provider.py:136-145)
try:
    return await self._run_draft(prompt, steer)
except StopError as exc:
    raise BackendUnavailableError(f"Copilot backend stopped unexpectedly: {exc}") from exc
except (ConnectionError, OSError, TimeoutError) as exc:
    raise BackendUnavailableError(f"Copilot backend is unavailable: {exc}") from exc
```
Add a `JsonRpcError` handler that splits on **both** `code == -32603` AND a message signature (RESEARCH Pitfall 1 — `-32603` is overloaded), plus a `ProcessExitedError` handler. Keep the existing handlers. Use a module constant `_MODEL_NOT_AVAILABLE_CODE = -32603` and a `_is_model_not_available(message)` helper. Function-length budget is 60 lines (coding-guide); if `draft_unit` grows past it, extract the except-mapping into a small helper. The `from exc` chaining and the `BackendUnavailableError(f"...: {exc}")` message shape are the in-file convention to keep.

---

### `src/dogen/adapters/copilot/__init__.py` (seam barrel)

**Analog:** self. The existing export block is `__init__.py:33-38`:
```python
from dogen.adapters.copilot.provider import (
    BackendUnavailableError,
    CopilotDraftingProvider,
)

__all__ = ["BackendUnavailableError", "CopilotDraftingProvider"]
```
Add `ModelRejectedError` to both the import tuple and `__all__` (keep `__all__` alphabetized — current order is already sorted).

---

### `src/dogen/adapters/mock_provider.py` (provider seam / factory)

**Analog:** self. The existing factories + dispatch + `select_provider` are `mock_provider.py:122-184`. Extend signatures to `(*, model=None, effort=None)`; the **mock factory ignores both** (stays SDK-free); the copilot factory forwards them lazily. The dict-dispatch (`_PROVIDER_FACTORIES`, `mock_provider.py:154-157`) and the lazy import inside `_make_copilot_provider` (`mock_provider.py:147`, `# noqa: PLC0415`) MUST be preserved (D-25).

Current `select_provider` signature/body (`mock_provider.py:160-184`):
```python
def select_provider(name: str = _DEFAULT_PROVIDER) -> DraftingProvider:
    try:
        factory = _PROVIDER_FACTORIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(_PROVIDER_FACTORIES))
        raise ValueError(f"unknown provider {name!r}; choose one of: {known}") from exc
    return factory()
```
Extend per RESEARCH "Code Examples → Extended select_provider": add `*, model=None, effort=None` to `select_provider` and to both factory signatures; call `factory(model=model, effort=effort)`. `Effort` imports from `dogen.core.models` (plain `StrEnum`, no SDK coupling) — add it to the existing `from dogen.core.models import ...` block at `mock_provider.py:34`. The `Callable[[], DraftingProvider]` type on `_PROVIDER_FACTORIES` (`mock_provider.py:154`) must widen to accept the kwargs (e.g. `Callable[..., DraftingProvider]` or a `Protocol`).

---

### `src/dogen/cli/main.py` (CLI controller, request-response)

**Analog:** self.

**`--model` option (D-02)** — mirror the existing `--provider` Typer option on `draft()` (`main.py:184-191`):
```python
# CURRENT
provider: Annotated[
    str,
    typer.Option(help="Drafting provider: copilot or mock."),
] = "copilot",
```
Add a sibling `model: Annotated[str | None, typer.Option(help="...")] = None` and thread it into the `select_provider(provider)` call at `main.py:215` → `select_provider(provider, model=model)`. Update the `draft` docstring Parameters block (NumPy-style, `main.py:198-204`) to document `model`.

**Error classifier (D-06)** — the existing `except RuntimeError` name-classifier is `main.py:227-236`:
```python
except RuntimeError as exc:
    if type(exc).__name__ == "BackendUnavailableError":
        typer.echo(f"Copilot backend unavailable: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    raise
```
Add a `ModelRejectedError` branch (classified by `type(exc).__name__` string — never import the adapter, D-25), echo to `err=True`, `typer.Exit(code=1)`. RESEARCH Open Question 2 / coding-guide §2: two cases is borderline — a `{name: render_fn}` dict-dispatch is acceptable but an inline `if` is also fine. For `ModelRejectedError` the message is already self-describing (it names the model), so echo `exc` directly: `typer.echo(f"{exc}", err=True)`.

---

## Pattern Assignments — New Test Files

**Shared SPDX header (every source file).** Every new file MUST open with the full 16-line GPL-3.0-only block, copied verbatim from any existing file (e.g. `provider.py:1-16`) — a bare `# SPDX-License-Identifier:` line is NOT sufficient (`reuse lint` gates CI):
```python
# This file is part of dogen, an agentic documentation-drafting framework.
#
# SPDX-FileCopyrightText: 2026 Canonical Ltd.
# SPDX-License-Identifier: GPL-3.0-only
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
```

---

### `tests/test_copilot_model_selection.py` (LIVE-01)

**Analog:** `tests/test_copilot_backend_unavailable.py`.

Default-model assertion needs no stub — construct the real provider and read `_model` (mirrors the existing `test_effort_maps_to_sdk_literal`, `test_copilot_backend_unavailable.py:134-138`):
```python
def test_default_model_is_gpt_5_mini() -> None:
    provider = CopilotDraftingProvider()
    assert provider._model == "gpt-5-mini"
```
Threading assertion uses the real `select_provider("copilot", model=...)` and a stub to avoid an SDK call, OR asserts the constructed provider's `_model`. For the **mock-path-imports-no-SDK** assertion (LIVE-01 seam row), follow `tests/test_seam.py` — assert `select_provider("mock", model="x")` returns a working provider and `"copilot"` is absent from `sys.modules`.

---

### `tests/test_copilot_session_kwargs.py` (LIVE-02 + LIVE-03)

**Analog:** `tests/test_copilot_backend_unavailable.py` — but the `_StubClient` (`test_copilot_backend_unavailable.py:60-96`) must be **extended to capture `create_session` kwargs** and return a scripted session that completes the happy path. The existing stub only scripts `__aenter__`/`get_status`/`get_auth_status`; it has no `create_session`. Add:
```python
class _StubClient:
    def __init__(self, ...) -> None:
        self.session_kwargs: dict[str, object] | None = None
        ...
    async def create_session(self, **kwargs: object) -> "_StubSession":
        self.session_kwargs = kwargs
        return _StubSession()   # async-CM whose send_and_wait returns a scripted
                                # assistant.message SessionEvent (so _require_assistant_message passes)
```
Injection pattern (verbatim from the analog, `test_copilot_backend_unavailable.py:96`):
```python
monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", _factory)
```
Drive a draft (reuse the `_steering()` / `_draft()` helpers at `test_copilot_backend_unavailable.py:42-57`), then assert:
- LIVE-02: `stub.session_kwargs["on_permission_request"] is PermissionHandler.approve_all`
- LIVE-03: parametrized — `model="gpt-5-mini"` → `stub.session_kwargs.get("reasoning_effort") == "medium"`; `model="claude-sonnet-4.5"` → `stub.session_kwargs.get("reasoning_effort") is None`.

Async tests carry `@pytest.mark.asyncio` explicitly (the established convention — see `test_copilot_backend_unavailable.py:106`; `asyncio_mode` is not auto in pyproject).

Consider hoisting the extended `_StubClient` into a shared `tests/conftest.py` fixture (none exists yet) since `test_copilot_error_mapping.py` reuses it — RESEARCH Wave 0 note. Either a shared fixture or duplication is acceptable.

---

### `tests/test_copilot_error_mapping.py` (ERR-01 + ERR-02)

**Analog:** `tests/test_copilot_backend_unavailable.py` (the `pytest.raises(BackendUnavailableError)` + scripted-error idiom at `test_copilot_backend_unavailable.py:106-131`).

The stub's `create_session` (or `send_and_wait`) raises a fake `JsonRpcError`. Import it the same sanctioned way the adapter does:
```python
from copilot._jsonrpc import JsonRpcError
```
Parametrized cases (RESEARCH Validation map + Pitfall 1):
- `JsonRpcError(-32603, 'Model "gpt-5" is not available')` → `ModelRejectedError`, message contains `self._model`.
- `JsonRpcError(-32603, "Directory path must be absolute")` → `BackendUnavailableError` (NOT `ModelRejectedError`) — the both-conditions guard.
- a non-`-32603` `JsonRpcError` → `BackendUnavailableError`.

Assertion idiom mirrors the analog: `with pytest.raises(ModelRejectedError) as excinfo: ...; assert "gpt-5" in str(excinfo.value)`.

---

### `tests/test_cli_draft_errors.py` (CLI exit codes)

**Analog:** `tests/test_cli_unit_new.py` — the Typer `CliRunner` pattern (`test_cli_unit_new.py:22-69`):
```python
from typer.testing import CliRunner
from dogen.cli.main import app
runner = CliRunner()

def test_...(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["draft", "my-unit", "--provider", "mock"])
    assert result.exit_code != 0, result.output
```
To exercise the classifier without the SDK: `monkeypatch` `select_provider` (or the provider's `draft_unit`) to raise a `RuntimeError` subclass whose `type(exc).__name__` is `"ModelRejectedError"` / `"BackendUnavailableError"`. Assert `result.exit_code == 1` and the message text. Do NOT import `adapters/copilot/` in this test (preserve D-25) — construct the error by name or via a local `RuntimeError` subclass with the matching `__name__`. The `assert result.exit_code == ..., result.output` form is the file's convention.

---

### `tests/test_copilot_jsonrpc_import.py` (D-08 regression)

**Analog:** `tests/test_copilot_mapping.py` (a plain module-level import + assert test, no async, no stub).

Guards the private-symbol coupling (RESEARCH Pitfall 2). Import the private symbol and assert it is the class the adapter actually catches:
```python
from copilot._jsonrpc import JsonRpcError

def test_jsonrpc_error_is_importable_and_shaped() -> None:
    exc = JsonRpcError(-32603, "x")
    assert exc.code == -32603
    assert exc.message == "x"
```
Turns a future SDK-bump rename into a loud CI failure instead of a silent loss of the `JsonRpcError` catch.

---

### `tests/test_copilot_toolset_boundary.py` (V4 — READONLY/DENY unchanged)

**Analog:** `tests/test_copilot_mapping.py::test_toolsets_are_source_qualified_builtins` (`test_copilot_mapping.py:104-130`) — copy this exact pattern. It already asserts the full names against `to_list()` / `builtin:<name>`:
```python
@pytest.mark.parametrize(
    ("constant", "expected"),
    [
        (READONLY, {"grep", "glob", "view"}),
        (DENY, {"bash", "edit", "create", "stop_bash", "sql", "task", "skill", "web_fetch"}),
    ],
)
def test_toolsets_are_source_qualified_builtins(constant: ToolSet, expected: set[str]) -> None:
    assert isinstance(constant, ToolSet)
    filters = set(constant.to_list())
    assert filters == {f"builtin:{name}" for name in expected}
```
The new test locks the boundary as a security regression guard for Phase 3 (V4 — `approve_all` is only safe while this set is unchanged). It may simply re-assert these exact sets with a name signaling intent (e.g. `test_readonly_set_unchanged` / `test_deny_set_unchanged`). Note: `tools.py` itself is NOT modified this phase — this test pins it.

---

## Shared Patterns

### SPDX / REUSE header
**Source:** any file, `provider.py:1-16`. **Apply to:** all 6 new test files. Full 16-line GPL-3.0-only block, verbatim. `reuse lint` gates CI.

### Fake-SDK injection (no network)
**Source:** `tests/test_copilot_backend_unavailable.py:85-96`. **Apply to:** `test_copilot_model_selection.py`, `test_copilot_session_kwargs.py`, `test_copilot_error_mapping.py`.
```python
monkeypatch.setattr("dogen.adapters.copilot.provider.CopilotClient", _factory)
```
Mock only at the true boundary — the SDK `CopilotClient` (coding-guide §4). Use the real provider, real `select_provider`, real CLI.

### RuntimeError-subclass → CLI name-classifier
**Source:** `cli/main.py:227-236` + `provider.py:68` (`BackendUnavailableError`). **Apply to:** the new `ModelRejectedError` and the CLI branch. Domain raises a `RuntimeError` subclass; the CLI maps by `type(exc).__name__` (string, no adapter import — D-25) to `typer.Exit(code=1)`.

### Seam discipline (SEAM-01)
**Source:** `provider.py` (sole `copilot` importer) + `__init__.py:18-31`. **Apply to:** all new SDK symbols (`PermissionHandler`, `JsonRpcError`, `ProcessExitedError`) live ONLY in `provider.py`. Tests importing `copilot._jsonrpc` are exempt (tests are not under `core/`/`cli/`); the AST seam-check + import-linter forbid the top-level `copilot` package only *outside* the adapter/tests. Phase gate runs `uv run lint-imports` + `python scripts/seam_check.py`.

### NumPy-style docstrings + function-length budget
**Source:** every public function in `provider.py` / `mock_provider.py` / `cli/main.py`. **Apply to:** new helpers (`_is_gpt5_family`, `_is_model_not_available`) and the `ModelRejectedError` class. Params/Returns/Raises sections; functions ≤ 60 lines; no if/elif ladder to assign one value (dict dispatch / ternary / match).

## No Analog Found

None. Every file has a strong in-codebase analog.

## Metadata

**Analog search scope:** `src/dogen/adapters/copilot/`, `src/dogen/adapters/`, `src/dogen/cli/`, `tests/`.
**Files scanned:** `provider.py`, `__init__.py`, `mock_provider.py`, `cli/main.py`, `tools.py`, `tests/test_copilot_backend_unavailable.py`, `tests/test_cli_unit_new.py`, `tests/test_copilot_mapping.py`, `pyproject.toml`.
**Pattern extraction date:** 2026-06-22
