---
phase: 03-live-copilot-path-runs-out-of-the-box
verified: 2026-06-22T12:00:00Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 3: Live Copilot Path Runs Out of the Box — Verification Report

**Phase Goal:** A TA can run `dogen draft --provider copilot` out of the box and either get a written draft on an available model of any family, or a clear actionable failure — never a hardcoded-unavailable default, a denied source read, a parameter rejection, or a raw traceback.
**Verified:** 2026-06-22
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running a bare `dogen draft --provider copilot` requests `gpt-5-mini`, not the retired `gpt-5` (LIVE-01) | VERIFIED | `_DEFAULT_MODEL = "gpt-5-mini"` at `provider.py:68`; test `test_copilot_default_model_is_gpt_5_mini` passes; no `gpt-5"` string remains as a default |
| 2 | An operator can pass `--model <name>` and that model is threaded to the Copilot session (LIVE-01) | VERIFIED | `model: Annotated[str \| None, typer.Option(...)]` at `cli/main.py:191-197`; `select_provider(provider, model=model)` at line 225; `select_provider(name, *, model=None, effort=None)` at `mock_provider.py:206-211`; `_make_copilot_provider` forwards via `_CopilotKwargs`; test `test_select_provider_threads_model_to_copilot_adapter` passes |
| 3 | `create_session` is called with `on_permission_request=PermissionHandler.approve_all` so non-interactive read-only source lookups are auto-approved (LIVE-02) | VERIFIED | `on_permission_request=PermissionHandler.approve_all` at `provider.py:272`; passed as staticmethod reference (no trailing `()`); test `test_create_session_wires_approve_all_permission_handler` asserts `stub.session_kwargs["on_permission_request"] is PermissionHandler.approve_all` — passes |
| 4 | `reasoning_effort` is sent only for GPT-5-family models and omitted (`None`) for Claude-family models so Claude drafts no longer error on the parameter (LIVE-03) | VERIFIED | `reasoning_effort = self._effort.value if _is_gpt5_family(self._model) else None` at `provider.py:262`, passed unconditionally at line 267; `_is_gpt5_family` returns `model.startswith("gpt-5")`; parametrized test `test_reasoning_effort_is_family_gated` covers gpt-5-mini/gpt-5 (medium) and claude-sonnet-4.5/claude-haiku-4.5 (None) — all 4 variants pass |
| 5 | A backend model rejection (`-32603` "is not available") raises `ModelRejectedError` naming the requested model; CLI exits nonzero with a clean message, never a raw traceback (ERR-01) | VERIFIED | `ModelRejectedError(RuntimeError)` at `provider.py:86`; `_map_jsonrpc_error` at line 229 requires BOTH `exc.code == _MODEL_NOT_AVAILABLE_CODE` AND `_is_model_not_available(exc.message)`; message uses `self._model` (the requested, not parsed, model); CLI classifies by `type(exc).__name__ == "ModelRejectedError"` at `cli/main.py:245`; exported from `adapters/copilot/__init__.py:36`; tests `test_model_not_available_raises_model_rejected_naming_requested_model`, `test_model_rejection_reports_requested_not_backend_model`, and `test_model_rejected_renders_exit_1_clean_message` all pass |
| 6 | Any other `JsonRpcError`/`ProcessExitedError` (including a `-32603` with a non-model-rejection message, and status-path errors) becomes a handled `BackendUnavailableError` with a nonzero exit, never an uncaught crash (ERR-02) | VERIFIED | Draft-path: `except JsonRpcError` at `provider.py:202` routes non-model-rejection to `BackendUnavailableError` via `_map_jsonrpc_error`; `except ProcessExitedError` at line 204 raises `BackendUnavailableError`. Status-path (CR-01 fix, commit `7f85ac0`): `_require_available_backend` at lines 310-318 catches `JsonRpcError` and `ProcessExitedError` before they can reach the draft-path classifier. CLI `BackendUnavailableError` branch at `cli/main.py:250`. Tests: parametrized `test_other_backend_errors_map_to_backend_unavailable` (3 variants), `test_status_path_errors_map_to_backend_unavailable_not_model_rejected` (3 variants), and `test_backend_unavailable_renders_exit_1_with_prefix` all pass. |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/dogen/adapters/copilot/provider.py` | gpt-5-mini default, `_is_gpt5_family` predicate, `approve_all` permission handler, family-gated `reasoning_effort`, `ModelRejectedError`, `JsonRpcError`/`ProcessExitedError` catch | VERIFIED | All six elements confirmed at lines 54, 68, 86, 97, 112, 262, 267, 272, 202-211, 310-318 |
| `src/dogen/adapters/copilot/__init__.py` | Exports `ModelRejectedError` alongside `BackendUnavailableError` | VERIFIED | `ModelRejectedError` in import tuple at line 36 and in `__all__` at line 42 (alphabetized) |
| `src/dogen/adapters/mock_provider.py` | `select_provider(name, *, model=None, effort=None)` threading; mock factory ignores both | VERIFIED | Uniform `(*, model: str \| None = None, effort: Effort \| None = None)` signature on `_make_mock_provider`, `_make_copilot_provider`, and `select_provider` at lines 137, 160, 206; lazy import with `# noqa: PLC0415` preserved at line 183 |
| `src/dogen/cli/main.py` | `--model` Typer option; `ModelRejectedError` branch in the by-name classifier; no direct copilot adapter import | VERIFIED | `model: Annotated[str \| None, typer.Option(...)]` at lines 191-197; `select_provider(provider, model=model)` at line 225; classifier at lines 244-252; `grep "from dogen.adapters.copilot" src/dogen/cli/main.py` returns nothing (seam intact) |
| `tests/conftest.py` | Shared kwargs-capturing `_StubClient`, `_StubSession`, `install_stub_client` fixture, `_steering`/`_draft` helpers | VERIFIED | All four elements present; `session_kwargs` captured in `_StubClient.create_session` at line 265; SDK imports deferred behind `TYPE_CHECKING` guard (WR-02 fixed) |
| `tests/test_copilot_jsonrpc_import.py` | D-08 private-import regression guard for both `JsonRpcError` and `ProcessExitedError` | VERIFIED | Module-level `from copilot._jsonrpc import JsonRpcError, ProcessExitedError` at line 32; two tests pin shapes; WR-01 fix (ProcessExitedError guard) included in commit `3acf0a0` |
| `tests/test_copilot_toolset_boundary.py` | V4 READONLY/DENY unchanged guard | VERIFIED | `test_readonly_set_unchanged` pins `{builtin:grep, builtin:glob, builtin:view}`; `test_deny_set_unchanged` pins all 8 deny names — both pass |
| `tests/test_copilot_session_kwargs.py` | LIVE-02 approve_all + LIVE-03 parametrized family-gate | VERIFIED | 5 tests, all pass |
| `tests/test_copilot_error_mapping.py` | ERR-01 model-rejection naming + ERR-02 Pitfall-1 guard + CR-01 status-path guard | VERIFIED | 8 tests including the 3-variant status-path parametrize from CR-01 fix — all pass |
| `tests/test_copilot_model_selection.py` | Default model, copilot threading, mock-stays-SDK-free (seam_check) | VERIFIED | 4 tests, all pass |
| `tests/test_cli_draft_errors.py` | CliRunner exit-1 rendering for both error classes by name, without importing the adapter | VERIFIED | 3 tests, all pass; no `from dogen.adapters.copilot` in the file |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/dogen/cli/main.py` | `src/dogen/adapters/mock_provider.py` | `select_provider(provider, model=model)` at line 225 | WIRED | `grep -n 'select_provider.*model=' src/dogen/cli/main.py` confirms line 225 |
| `src/dogen/adapters/mock_provider.py` | `src/dogen/adapters/copilot/provider.py` | `_make_copilot_provider` builds `_CopilotKwargs` and calls `CopilotDraftingProvider(**kwargs)` | WIRED | Lazy import at line 183; `_CopilotKwargs` TypedDict at line 39; factory at lines 159-193 |
| `src/dogen/adapters/copilot/provider.py` | `copilot.session` | `create_session(on_permission_request=PermissionHandler.approve_all, reasoning_effort=<value-or-None>, ...)` | WIRED | `grep -n 'on_permission_request=PermissionHandler.approve_all' provider.py` confirms line 272; `reasoning_effort` computed and passed at lines 262/267 |
| `src/dogen/cli/main.py` | `src/dogen/adapters/copilot/provider.py` | `except RuntimeError` classifies `ModelRejectedError` by `type(exc).__name__` (no SDK import, D-25) | WIRED | Lines 244-252; CLI does NOT import the adapter (`grep "from dogen.adapters.copilot" src/dogen/cli/main.py` is empty); seam_check exits 0 |

---

### Data-Flow Trace (Level 4)

Not applicable. This phase delivers an error-handling hardening path, not a data-rendering component. The key data flows are:
- `_DEFAULT_MODEL` literal → `CopilotDraftingProvider._model` → `create_session(model=...)` — directly traced via `session_kwargs` in stub tests.
- `_is_gpt5_family(self._model)` → `reasoning_effort` → `create_session(reasoning_effort=...)` — directly traced via `session_kwargs` in stub tests.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase test cluster: 24 tests (session kwargs, error mapping, model selection, CLI exit codes, import guards, toolset boundary) | `uv run pytest tests/test_copilot_session_kwargs.py tests/test_copilot_error_mapping.py tests/test_copilot_model_selection.py tests/test_cli_draft_errors.py tests/test_copilot_jsonrpc_import.py tests/test_copilot_toolset_boundary.py -v` | 24 passed in 0.05s | PASS |
| Full suite regression (121 tests) | `uv run pytest -x -q` | 121 passed in 1.55s | PASS |
| Lint gate | `uv run ruff check src tests` | "All checks passed!" | PASS |
| Seam guard | `uv run python scripts/seam_check.py` | "OK — 14 files, no vendor imports outside adapters/copilot/" | PASS |
| Import linter | `uv run lint-imports` | 1 kept, 0 broken | PASS |

---

### Probe Execution

No declared probes for this phase. Phase uses pytest-based test gates only.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LIVE-01 | 03-02 | Operator can choose the drafting model; hardcoded unavailable `gpt-5` default is retired | SATISFIED | `_DEFAULT_MODEL = "gpt-5-mini"` at provider.py:68; `--model` Typer option at cli/main.py:191; threaded through `select_provider`; tests pass |
| LIVE-02 | 03-02 | Non-interactive agent can auto-approve read-only source lookups via permission handler | SATISFIED | `on_permission_request=PermissionHandler.approve_all` at provider.py:272; test asserts `stub.session_kwargs["on_permission_request"] is PermissionHandler.approve_all` |
| LIVE-03 | 03-02 | Drafting succeeds on any model family; `reasoning_effort` omitted for Claude-family models | SATISFIED | Family-gated at provider.py:262; parametrized test covers 4 model variants |
| ERR-01 | 03-02 | Model rejection (-32603 "is not available") → clean message naming the model + nonzero exit, never traceback | SATISFIED | `ModelRejectedError` raised by `_map_jsonrpc_error`; CLI classifies by name; tests confirm no traceback, exit code 1 |
| ERR-02 | 03-02 | Other draft-path JSON-RPC errors → handled `BackendUnavailableError` + nonzero exit; status-path errors also covered (CR-01 fix) | SATISFIED | Both draft-path and status-path `except` blocks present; 6 parametrized test variants pass |

**Coverage note:** REQUIREMENTS.md traceability table marks all five as "Complete" for Phase 3. PROV-01/PROV-02 are correctly deferred to Phase 4 and are not in scope here. No orphaned requirements.

---

### CR-01 Critical Fix Verification

The code review found a critical bug: `_require_available_backend` did not catch `JsonRpcError`/`ProcessExitedError` from `get_status()`/`get_auth_status()`, allowing a status-phase `-32603` to be misclassified as `ModelRejectedError`.

**Fix verified in commit `7f85ac0`:**
- `_require_available_backend` at provider.py lines 303-318 now has explicit `except JsonRpcError` and `except ProcessExitedError` blocks that raise `BackendUnavailableError`.
- A parametrized regression test `test_status_path_errors_map_to_backend_unavailable_not_model_rejected` (3 variants) covers the status-path classification — all pass.
- Docstring updated to accurately state `Raises: BackendUnavailableError` for status-path errors.

---

### Warnings From Code Review (WR-01, WR-02, WR-03) — Status

| Warning | Disposition | Commit |
|---------|-------------|--------|
| WR-01: D-08 guard covered only `JsonRpcError`, not `ProcessExitedError` | FIXED — `test_copilot_jsonrpc_import.py` now imports and tests both; `ProcessExitedError` guard added | `3acf0a0` |
| WR-02: `conftest.py` module-level SDK import defeated mock-path isolation | FIXED — SDK imports moved behind `TYPE_CHECKING` guard; `_assistant_event` uses function-local import | `176e3a3` |
| WR-03: docstring in `test_copilot_model_selection.py` claimed an unperformed `sys.modules` check | FIXED — docstring updated to accurately describe the static AST check actually performed | `5b0679b` |

All three warnings addressed before verification. No unresolved warnings remain as blockers.

Info findings IN-01/IN-02 are documentation/style concerns with no functional impact; not blocking.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TBD/FIXME/XXX markers, no empty stubs, no placeholder returns in phase files | — | — |

Scanned all 11 files listed in 03-REVIEW.md. No debt markers found in phase-modified production or test files. The `temp/` directory noted in 03-02-SUMMARY.md is untracked and out of scope.

---

### Live Verification (D-24 Manual Path)

ROADMAP success criteria 1-3 (written drafts: bare `gpt-5-mini` default, `--model claude-sonnet-4.5`, auto-approved source reads) and criterion 5 (clean named model-rejection error, nonzero exit on `--model gpt-5`) require a live Copilot token/network on the dev machine and are by design off-CI (D-24).

**These criteria are satisfied by the recorded operator attestation in 03-02-SUMMARY.md:** "Task 3 human-verify checkpoint: the operator replied 'approved' on 2026-06-22." The supporting implementing code — `_DEFAULT_MODEL = "gpt-5-mini"`, `--model` threading, `PermissionHandler.approve_all`, family-gated `reasoning_effort`, `ModelRejectedError` + `BackendUnavailableError` classification — is verified in the codebase as documented above.

No re-run of the live criteria in CI or a sandbox is required; that would contradict D-24.

---

### Human Verification Required

None. All automated must-haves are code-verified and pass. The D-24 live criteria are covered by the recorded operator approval (03-02-SUMMARY.md) plus the implementing code confirmed present and wired.

---

## Gaps Summary

No gaps. All six must-have truths are VERIFIED, all 11 artifacts are substantive and wired, all four key links are confirmed, the CR-01 critical fix is in place and tested, all three code-review warnings are resolved, the full 121-test suite is green, and all lint/seam/import gates pass.

---

_Verified: 2026-06-22_
_Verifier: Claude (gsd-verifier)_
