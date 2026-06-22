---
phase: 03-live-copilot-path-runs-out-of-the-box
reviewed: 2026-06-22T00:00:00Z
depth: deep
files_reviewed: 11
files_reviewed_list:
  - src/dogen/adapters/copilot/provider.py
  - src/dogen/adapters/copilot/__init__.py
  - src/dogen/adapters/mock_provider.py
  - src/dogen/cli/main.py
  - tests/conftest.py
  - tests/test_copilot_session_kwargs.py
  - tests/test_copilot_error_mapping.py
  - tests/test_copilot_model_selection.py
  - tests/test_cli_draft_errors.py
  - tests/test_copilot_jsonrpc_import.py
  - tests/test_copilot_toolset_boundary.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-06-22
**Depth:** deep
**Files Reviewed:** 11
**Status:** issues_found

## Summary

This phase correctly implements the five LIVE/ERR requirements in `provider.py`
and wires them through the seam and CLI. The architecture is sound: the
`PermissionHandler.approve_all` is passed as a callable reference (Pitfall 5 is
clean), the `-32603` overload is guarded by the dual-condition check (Pitfall 1
is handled), the `gpt-5` prefix predicate is forward-safe (D-05 is correct), SDK
types stay behind the seam (SEAM-01 is intact), and the `READONLY`/`DENY`
toolset is unchanged and pinned by a new regression test.

One critical bug was found: `_require_available_backend` does not catch
`JsonRpcError` or `ProcessExitedError` from the SDK's `get_status()` /
`get_auth_status()` calls. These exceptions escape into `draft_unit`'s outer
`except JsonRpcError` handler, where `_map_jsonrpc_error` applies the same
ERR-01 vs ERR-02 classification it uses for session/send errors. A status-path
`JsonRpcError` whose code is `-32603` and whose message happens to contain `"is
not available"` (plausible for an auth-rejection or quota message) would be
misclassified and reported to the operator as a `ModelRejectedError`, naming the
requested model when the real cause has nothing to do with the model. The gap
also means the function's documented contract (`Raises: BackendUnavailableError`)
is false: it can propagate uncaught `JsonRpcError` / `ProcessExitedError` in
production.

Three warnings are also present: the D-08 regression guard covers only
`JsonRpcError` and not `ProcessExitedError` (also a private symbol subject to
the same SDK-bump risk), the module-level SDK import in `conftest.py` defeats
any runtime assertion about mock-path isolation, and a docstring in
`test_copilot_model_selection.py` claims a `sys.modules` check that is never
executed.

## Structural Findings (fallow)

No structural pre-pass was provided for this review.

## Narrative Findings (AI reviewer)

---

## Critical Issues

### CR-01: `_require_available_backend` does not catch `JsonRpcError`/`ProcessExitedError` — status-path error can be misclassified as `ModelRejectedError`

**File:** `src/dogen/adapters/copilot/provider.py:286-307`

**Issue:** `_require_available_backend` calls `get_status()` and `get_auth_status()`,
both of which perform a JSON-RPC request internally. The `_jsonrpc.py` request
handler raises `JsonRpcError` whenever the backend returns an error response (and
`ProcessExitedError` when the CLI exits). The current `try/except` in
`_require_available_backend` only catches `StopError` and
`(ConnectionError, OSError, TimeoutError)`, so a `JsonRpcError` or
`ProcessExitedError` from the status-check phase escapes the function.

These exceptions then propagate uncaught through `_run_draft` (which has no
`try/except` of its own) and are caught by `draft_unit`'s outer `except
JsonRpcError` handler at line 202. That handler calls `self._map_jsonrpc_error`,
which routes `code == -32603 AND "is not available" in message` to
`ModelRejectedError`. A status-phase backend response that uses `-32603` with a
message like `"gpt-5-mini is not available on this plan"` (hypothetical but
plausible for an account-access or quota error during the status call) would
surface to the operator as a model-rejection error naming `self._model`, when
the real failure has nothing to do with the model parameter.

Additionally, the function's documented `Raises` section says only
`BackendUnavailableError`, which is factually incorrect: `JsonRpcError` and
`ProcessExitedError` can propagate out of it in production, breaking callers'
ability to reason about its contract.

**Fix:** Extend `_require_available_backend`'s `except` list to catch `JsonRpcError`
and `ProcessExitedError` and convert them to `BackendUnavailableError` (same as
the session-path handlers in `draft_unit`). This also makes the docstring
accurate.

```python
async def _require_available_backend(client: CopilotClient) -> None:
    """Fail fast with a handled error if the backend is not ready.

    ...

    Raises
    ------
    BackendUnavailableError
        If status or auth-status reports the backend cannot serve a draft,
        including any JSON-RPC or process-exit error during the status probe.
    """
    try:
        await client.get_status()
        await client.get_auth_status()
    except StopError as exc:
        raise BackendUnavailableError(
            f"Copilot backend status check failed: {exc}"
        ) from exc
    except JsonRpcError as exc:
        raise BackendUnavailableError(
            f"Copilot backend status check error (JSON-RPC {exc.code}): {exc.message}"
        ) from exc
    except ProcessExitedError as exc:
        raise BackendUnavailableError(
            f"Copilot backend process exited during status check: {exc}"
        ) from exc
    except (ConnectionError, OSError, TimeoutError) as exc:
        raise BackendUnavailableError(f"Copilot backend is unreachable: {exc}") from exc
```

A corresponding unit test should exercise `status_error=JsonRpcError(-32603,
"some status error")` and assert `BackendUnavailableError` is raised (not
`ModelRejectedError`). The `install_stub_client` fixture in `conftest.py`
already threads `status_error` through `_StubClient.get_status`, so no new
harness is needed.

---

## Warnings

### WR-01: D-08 regression guard covers only `JsonRpcError`, not `ProcessExitedError`

**File:** `tests/test_copilot_jsonrpc_import.py:32-44`

**Issue:** The file's module-level `from copilot._jsonrpc import JsonRpcError`
and the `test_jsonrpc_error_is_importable_and_shaped` test pin the private
symbol that the adapter catches for ERR-01/ERR-02. However, `provider.py` also
imports and catches `ProcessExitedError` from the same private module
(`from copilot._jsonrpc import JsonRpcError, ProcessExitedError` at line 54),
and that symbol is equally private — not in `copilot.__all__`. The D-08
regression design was explicit: "converts a silent future breakage into a loud,
early CI failure." A future SDK bump that moves or renames `ProcessExitedError`
would silently drop its `except` handler in `provider.py` without any CI signal,
because `ProcessExitedError` is not imported anywhere in the test suite. The
`test_copilot_jsonrpc_import.py` file is the natural home for this guard.

**Fix:**

```python
from copilot._jsonrpc import JsonRpcError, ProcessExitedError

def test_process_exited_error_is_importable() -> None:
    """Pin the private ``ProcessExitedError`` shape the adapter catches (D-08).

    Constructs the error and asserts it is an ``Exception`` subclass so the
    adapter's ``except ProcessExitedError`` handler is guarded against an SDK
    bump that moves or renames the class.
    """
    exc = ProcessExitedError("cli exited")
    assert isinstance(exc, Exception)
```

The module-level import is itself the loud signal: if the private path goes away,
collection of this module fails in CI before any test runs.

### WR-02: `conftest.py` module-level SDK import silently defeats runtime mock-path isolation assertions

**File:** `tests/conftest.py:50`

**Issue:** `conftest.py` imports `from copilot import SessionEvent, SessionEventType`
at module level. pytest collects `conftest.py` before every test module, meaning
`copilot` is always in `sys.modules` for the entire test session — including
tests that run on the mock path only (`select_provider("mock", ...)`). The RESEARCH
Pitfall 4 guard explicitly called for a test asserting "that `sys.modules` gains
no `copilot` entry on the mock path." That runtime check would be a vacuous pass
in any test session that collects `conftest.py`, because the SDK is already
imported regardless of which provider is selected.

The `test_mock_provider_ignores_model_and_stays_sdk_free` test (WR-03 below)
only calls the static AST guardrail, which is a source-code check and cannot
catch a runtime import that conftest triggers through a different path.

**Fix:** Move the SDK imports out of the top-level `conftest.py` and into the
test files or fixtures that actually require them
(`test_copilot_session_kwargs.py`, `test_copilot_error_mapping.py`). The
`_assistant_event`, `_StubSession`, and `_StubClient` helpers need `SessionEvent`
and `SessionEventType`, but they are only used in the copilot adapter tests, not
in the mock-path tests. Separating them keeps the mock-path test environment
genuinely SDK-free during collection:

```python
# conftest.py — remove the top-level SDK import:
# from copilot import SessionEvent, SessionEventType  <- DELETE

# Instead, add a local import inside the affected helpers, or split the
# shared conftest into a copilot-specific conftest under tests/copilot/.
```

This is the only way to make a future runtime `sys.modules` check on the mock
path meaningful.

### WR-03: `test_mock_provider_ignores_model_and_stays_sdk_free` docstring claims `sys.modules` assertion that is never performed

**File:** `tests/test_copilot_model_selection.py:59-65`

**Issue:** The test's module docstring and the function docstring both state that
the test verifies "resolving the mock provider does not pull
`dogen.adapters.copilot` onto `sys.modules`." The test body only calls
`seam_check.main() == 0`, which is a static AST walk of `src/dogen` source files.
It does not inspect `sys.modules` at runtime. The claim in the docstring is false:
no runtime isolation check exists.

This is a documentation accuracy issue in a test, but it matters here because
the seam isolation on the mock path is a named design property (D-25, Pitfall 4)
and both the RESEARCH and CONTEXT documents reference it. Readers of this test
would reasonably conclude the runtime property is verified when it is not.

Additionally, even if a `sys.modules` assertion were added, it would fail to
detect isolation problems because `conftest.py` already imports `copilot` at
collection time (WR-02 above). The fix for WR-02 is a prerequisite.

**Fix:** Either update the docstring to accurately describe what the test actually
checks ("the static AST seam guardrail still passes on the mock path"), or — after
fixing WR-02 — add the missing runtime assertion:

```python
def test_mock_provider_ignores_model_and_stays_sdk_free() -> None:
    """LIVE-01/D-25: the mock path honours the signature but imports no SDK.

    Asserts both the static AST guardrail (same check CI/pre-commit run) and
    that resolving the mock provider does not pull ``copilot`` onto sys.modules
    at runtime.
    """
    # Remove copilot from modules if conftest didn't already import it:
    sys.modules.pop("copilot", None)
    sys.modules.pop("dogen.adapters.copilot", None)

    provider = select_provider("mock", model="gpt-5-mini")
    assert isinstance(provider, MockDraftingProvider)
    assert "dogen.adapters.copilot" not in sys.modules, (
        "mock path should not import the copilot adapter"
    )
    assert seam_check.main() == 0
```

Note: this is only meaningful after WR-02 is resolved.

---

## Info

### IN-01: Tests directly access `_model` private attribute on `CopilotDraftingProvider`

**File:** `tests/test_copilot_model_selection.py:42,49,56`

**Issue:** Three test assertions read `provider._model` directly. This works
today because the attribute name is a stable implementation detail, but the
Python convention is that `_`-prefixed attributes are subject to change without
notice. If the attribute is ever renamed (e.g., to support a property), these
tests would fail with a silent `AttributeError` rather than a type-safe compile
error. The tests are also black-box testing at a level below the port interface.

**Fix:** Consider exposing the selected model through a property or through an
observable side-effect such as the `session_kwargs["model"]` already captured by
the stub harness. Either approach removes the dependency on the internal name
without reducing coverage. This is a low-priority stylistic concern; the current
approach is pragmatic and common in small codebases.

### IN-02: `conftest.py` `_draft` and `_steering` are not prefixed with `_` consistently

**File:** `tests/conftest.py:300-334`

**Issue:** `conftest.py` exports `_draft` and `_steering` as module-level
helpers (with a leading underscore, signalling "test-internal"). However,
`test_copilot_session_kwargs.py` and `test_copilot_error_mapping.py` import them
explicitly with `from tests.conftest import _draft`, which is an unusual pattern
(most conftest helpers are consumed via fixtures, not direct imports). This works
but it couples the test files to `conftest`'s internal naming in a way that
`conftest`-scoped fixtures would not. It is not a bug, but it means renaming
`_draft` or `_steering` requires updating multiple test files manually.

**Fix:** Consider promoting `_draft` and `_steering` to `pytest` fixtures in
`conftest.py` (fixture functions can also be `async`) so pytest injects them
automatically. This is a low-priority style matter with no functional impact.

---

_Reviewed: 2026-06-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
