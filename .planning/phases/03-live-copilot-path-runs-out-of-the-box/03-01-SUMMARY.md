---
phase: 03-live-copilot-path-runs-out-of-the-box
plan: 01
subsystem: testing
tags: [test-harness, regression-guard, copilot-adapter, seam, security]
status: complete
requires:
  - "src/dogen/adapters/copilot/provider.py (CopilotClient boundary, _run_draft lifecycle)"
  - "src/dogen/adapters/copilot/mapping.py (to_draft_result event shape)"
  - "src/dogen/adapters/copilot/tools.py (READONLY/DENY ToolSets)"
  - "copilot._jsonrpc.JsonRpcError (private SDK symbol)"
provides:
  - "tests/conftest.py — shared kwargs-capturing _StubClient + scripted _StubSession + install_stub_client fixture + _steering/_draft helpers"
  - "tests/test_copilot_jsonrpc_import.py — D-08 private-import regression guard"
  - "tests/test_copilot_toolset_boundary.py — V4 READONLY/DENY-unchanged guard"
affects:
  - "Wave-1 (03-02) tests: test_copilot_session_kwargs.py, test_copilot_model_selection.py, test_copilot_error_mapping.py build on the conftest harness"
tech-stack:
  added: []
  patterns:
    - "Structural SessionEvent fake via cast() (idiom from test_copilot_mapping.py) — no full SDK event constructed"
    - "Fake-SDK injection at the true boundary: monkeypatch.setattr('dogen.adapters.copilot.provider.CopilotClient', factory)"
    - "Explicit @pytest.mark.asyncio (asyncio_mode is not auto)"
key-files:
  created:
    - "tests/conftest.py"
    - "tests/test_copilot_jsonrpc_import.py"
    - "tests/test_copilot_toolset_boundary.py"
  modified: []
decisions:
  - "Scripted assistant.message event modelled as a structural dataclass fake cast to SessionEvent (matching test_copilot_mapping.py), not a real SDK SessionEvent — the SDK constructor requires id/timestamp/data and the provider only reads .type/.data."
  - "install_stub_client returns the stub instance (not just installs it) so 03-02 tests can read session_kwargs after driving a draft."
  - "_StubClient carries three independent error hooks (status_error / session_error / send_error) so 03-02 can inject a JsonRpcError at create_session OR at send_and_wait, plus simulate an unhealthy backend."
metrics:
  duration: "~6 min"
  completed: "2026-06-22"
  tasks: 2
  files: 3
---

# Phase 3 Plan 01: Wave-0 Test Scaffolding + Regression Guards Summary

Shipped the shared fake-SDK harness (`tests/conftest.py`) the Wave-1 implementation tests build on, plus two standalone regression guards that lock the phase's fragile couplings — the private `copilot._jsonrpc.JsonRpcError` import (D-08) and the `READONLY`/`DENY` toolset boundary (V4). No production code touched.

## What Was Built

### Task 1 — `tests/conftest.py` fake-SDK harness (commit `cc0cbca`)

- **`_StubClient`** — a kwargs-capturing stand-in for `CopilotClient`. `create_session(**kwargs)` records `self.session_kwargs` and returns a scripted `_StubSession`. Three independent error hooks (`status_error`, `session_error`, `send_error`) let 03-02 simulate an unhealthy backend, a create-time `JsonRpcError`, or a mid-draft `send_and_wait` failure.
- **`_StubSession`** — async context manager whose `send_and_wait` returns a scripted `assistant.message` `SessionEvent` (so `_require_assistant_message` passes and `to_draft_result` maps it) or raises a scripted exception.
- **`install_stub_client`** fixture — builds a stub from a keyword recipe, monkeypatches `dogen.adapters.copilot.provider.CopilotClient` to a factory yielding it, and **returns the stub instance** so a test can assert `session_kwargs` after driving a draft.
- **`_steering()` / `_draft(provider)`** helpers — hoisted from `test_copilot_backend_unavailable.py` so 03-02 tests drive a draft without redefining them.

The scripted event is a structural dataclass fake `cast` to `SessionEvent` (matching the established `test_copilot_mapping.py` idiom) — the real SDK `SessionEvent` constructor requires `id`/`timestamp`/`data`, while the provider only reads `.type`/`.data`.

### Task 2 — two regression guards (commit `9dfef0e`)

- **`tests/test_copilot_jsonrpc_import.py`** (D-08) — `from copilot._jsonrpc import JsonRpcError` at module level (a top-level import failure is the loud CI signal) + `test_jsonrpc_error_is_importable_and_shaped` constructing `JsonRpcError(-32603, "x")` and asserting `.code == -32603` / `.message == "x"`. Turns a future SDK-bump rename of the private symbol into a loud CI failure instead of a silently dropped error catch (RESEARCH Pitfall 2).
- **`tests/test_copilot_toolset_boundary.py`** (V4) — `test_readonly_set_unchanged` pins `READONLY == {builtin:grep, builtin:glob, builtin:view}` and `test_deny_set_unchanged` pins `DENY` to its exact eight `builtin:` names. Locks the boundary `approve_all` (wired in 03-02) leans on so a future `tools.py` edit cannot quietly broaden what auto-approval permits.

## Verification

All gates green (run via the project's actual toolchain — `reuse` via `uvx`, scripts via `uv run`):

| Gate | Result |
|------|--------|
| `uv run pytest tests/ -q` | 100 passed (97 pre-existing + 3 new) |
| `uv run lint-imports` | 1 kept, 0 broken |
| `uv run python scripts/seam_check.py` | OK — 14 files, no vendor imports outside adapters/copilot/ |
| `uvx reuse lint` (new files only) | clean — all 3 new files carry the full GPL-3.0-only block; 0 hits |

The harness was additionally proven end-to-end with a throwaway test: `install_stub_client()` injects the stub, `_draft(CopilotDraftingProvider())` completes via the scripted assistant event, and `session_kwargs` is captured (then the throwaway file was removed — not committed).

## Deviations from Plan

None affecting code — the harness, import guard, and boundary assertions all hold against current production code without any production change (as expected for test-only scaffolding).

**State-bookkeeping note:** The plan frontmatter lists `requirements: [ERR-01, ERR-02, LIVE-02, LIVE-03]`, but those four requirements are also claimed by **03-02**, which ships the production code that actually satisfies them (the permission handler, family-aware effort, and `JsonRpcError` → `ModelRejectedError` mapping). 03-01 is test scaffolding only, so the requirements were intentionally **left `Pending`** in `REQUIREMENTS.md` — marking them complete here would misrepresent state to the verifier before the implementing code exists. They will be marked complete after 03-02.

## Threat Mitigations Applied

Both `mitigate`-disposition threats from the plan's STRIDE register are now covered by passing tests:

- **T-03-01 (DoS — private `copilot._jsonrpc` import)** → `test_copilot_jsonrpc_import.py` (module-level import + shape assertion).
- **T-03-02 (Elevation of Privilege — toolset boundary)** → `test_copilot_toolset_boundary.py` (exact allowlist/denylist pin).

T-03-SC (supply-chain) needed no action: no packages were installed — only the already-pinned `github-copilot-sdk==1.0.2` is consumed.

## Known Stubs

None. The conftest "stubs" are the intended test harness (a fake SDK boundary), not placeholder production data.

## Out-of-Scope Note (pre-existing, not introduced here)

`uvx reuse lint` reports one failure on `.planning/phases/03-live-copilot-path-runs-out-of-the-box/03-PATTERNS.md` — a prose false-positive: the file's prose quotes a bare `SPDX-License-Identifier:` token inside a code block, which `reuse` misparses as an invalid license expression. This file was committed in `4571692 docs(03): add pattern map` (the planning pass), **predates this plan, and is not a tracked source/test file** in scope. Per the executor SCOPE BOUNDARY rule it was logged, not fixed. All three files this plan created are reuse-clean.

## Self-Check: PASSED

- `tests/conftest.py` — FOUND
- `tests/test_copilot_jsonrpc_import.py` — FOUND
- `tests/test_copilot_toolset_boundary.py` — FOUND
- commit `cc0cbca` — FOUND
- commit `9dfef0e` — FOUND
