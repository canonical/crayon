---
phase: 03-live-copilot-path-runs-out-of-the-box
plan: 02
subsystem: api
tags: [github-copilot-sdk, jsonrpc, typer, error-mapping, provider-seam, reasoning-effort]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Shared fake-SDK harness (tests/conftest.py): kwargs-capturing _StubClient, scripted _StubSession, install_stub_client fixture, _steering/_draft helpers"
provides:
  - "CopilotDraftingProvider defaults to gpt-5-mini (retired gpt-5 removed) — LIVE-01"
  - "create_session wired with on_permission_request=PermissionHandler.approve_all — LIVE-02"
  - "Family-gated reasoning_effort (value for gpt-5*, None for Claude/unknown) — LIVE-03"
  - "ModelRejectedError(RuntimeError) with the -32603 both-conditions guard — ERR-01"
  - "Other JsonRpcError/ProcessExitedError -> BackendUnavailableError — ERR-02"
  - "--model CLI option threaded through select_provider(name, *, model, effort) to the adapter (mock stays SDK-free)"
affects: [live-copilot-verification, future-provider-adapters, cli-error-rendering]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Private SDK symbol (copilot._jsonrpc.JsonRpcError/ProcessExitedError) imported ONLY inside adapters/copilot/ (SEAM-01)"
    - "Family-gate by computing reasoning_effort to None and passing unconditionally — SDK omits falsy from the wire (RESEARCH Pattern 1)"
    - "Overloaded -32603 disambiguated by BOTH code AND message signature (Pitfall 1)"
    - "Domain error classified at the CLI by type(exc).__name__ — no adapter/SDK import on the mock path (D-25)"
    - "TypedDict(total=False) to forward only set kwargs with precise types across the lazy seam"

key-files:
  created:
    - tests/test_copilot_session_kwargs.py
    - tests/test_copilot_error_mapping.py
    - tests/test_copilot_model_selection.py
    - tests/test_cli_draft_errors.py
  modified:
    - src/dogen/adapters/copilot/provider.py
    - src/dogen/adapters/copilot/__init__.py
    - src/dogen/adapters/mock_provider.py
    - src/dogen/cli/main.py
    - tests/conftest.py

key-decisions:
  - "Extracted _map_jsonrpc_error helper to keep draft_unit within the 60-line budget and avoid an if/elif value-assignment ladder"
  - "_CopilotKwargs TypedDict(total=False) used to forward model/effort with precise types so ty stays green across the lazy import seam"
  - "CLI classifier uses a two-arm if-chain (ModelRejectedError before BackendUnavailableError) — clean and avoids a one-value if/elif ladder"

patterns-established:
  - "Pattern 1: family-gate optional SDK params by computing value-or-None and passing unconditionally (SDK drops falsy)"
  - "Pattern 2: split an overloaded JSON-RPC code by requiring code AND a message signature, falling through to the generic handler otherwise"

requirements-completed: [LIVE-01, LIVE-02, LIVE-03, ERR-01, ERR-02]

# Metrics
duration: 8min
completed: 2026-06-22
status: awaiting-checkpoint
---

# Phase 3 Plan 2: Close the five live-Copilot gaps in the adapter Summary

**gpt-5-mini default + --model threading, approve_all read-only permission handler, family-gated reasoning_effort, and a -32603 model-rejection vs generic-backend error split — all unit-proven against the Wave-0 fake-SDK harness; the live end-to-end runs remain a blocking human-verify checkpoint (D-24).**

## Performance

- **Duration:** ~8 min (autonomous Tasks 1-2)
- **Started:** 2026-06-22T09:38:47Z
- **Completed (autonomous work):** 2026-06-22T09:46:45Z
- **Tasks:** 2 of 3 executed autonomously; Task 3 is a blocking human-verify checkpoint (not auto-completed)
- **Files modified:** 9 (4 production, 4 new tests, 1 harness docstring wrap)

## Accomplishments
- **LIVE-01:** `_DEFAULT_MODEL` changed `gpt-5` → `gpt-5-mini`; `--model` Typer option added to `dogen draft` and threaded via `select_provider(name, *, model=None, effort=None)` to the Copilot adapter. The mock factory honours the uniform signature but ignores both and stays SDK-free (seam_check still green).
- **LIVE-02:** `create_session` now receives `on_permission_request=PermissionHandler.approve_all` (the staticmethod reference, not called), so non-interactive read-only source lookups are auto-approved — safe by construction (only grep/glob/view available; write/exec/network unavailable AND on DENY).
- **LIVE-03:** `reasoning_effort` is computed family-gated (`self._effort.value` for `gpt-5*`, `None` otherwise) and passed unconditionally; the SDK omits a falsy value, so Claude drafts no longer error on the parameter.
- **ERR-01:** New `ModelRejectedError(RuntimeError)`; a `-32603` whose message carries the "is not available" signature raises it naming the *requested* model (`self._model`, D-07). Exported from `adapters/copilot/__init__` and classified by name at the CLI into a clean exit-1 message (no adapter import, D-25).
- **ERR-02:** Every other `JsonRpcError` (incl. the overloaded `-32603` "Directory path must be absolute" and any non-`-32603` code) plus `ProcessExitedError` maps to `BackendUnavailableError` and a nonzero exit — never an uncaught traceback. The overload is disambiguated by the both-conditions guard.

## Task Commits

1. **Task 1 (RED):** add failing session-kwargs + error-mapping tests — `105fd94` (test)
2. **Task 1 (GREEN):** family-gated effort, approve_all handler, JsonRpcError mapping — `786faf5` (feat)
3. **Task 2:** thread --model through CLI/select_provider, export ModelRejectedError — `0552dee` (feat)

No separate REFACTOR commit was needed: the `_map_jsonrpc_error` helper was extracted in the GREEN step, keeping every function within the length budget the first time.

**Plan metadata:** committed alongside this SUMMARY (docs).

## Files Created/Modified
- `src/dogen/adapters/copilot/provider.py` — `gpt-5-mini` default; `_MODEL_NOT_AVAILABLE_CODE`, `_is_gpt5_family`, `_is_model_not_available`, `ModelRejectedError`; family-gated `reasoning_effort` + `approve_all` on `create_session`; `_map_jsonrpc_error` and the `JsonRpcError`/`ProcessExitedError` except arms; private `copilot._jsonrpc` import.
- `src/dogen/adapters/copilot/__init__.py` — export `ModelRejectedError` (alphabetized `__all__`).
- `src/dogen/adapters/mock_provider.py` — uniform `(*, model, effort)` factories; mock ignores both; copilot forwards set values via `_CopilotKwargs` TypedDict; `select_provider` extended signature; `Effort` import.
- `src/dogen/cli/main.py` — `--model` option, `select_provider(provider, model=model)`, `ModelRejectedError` branch in the by-name classifier.
- `tests/test_copilot_session_kwargs.py` — approve_all + parametrized family-gate assertions.
- `tests/test_copilot_error_mapping.py` — ERR-01 model-rejection naming + the parametrized ERR-02 / Pitfall-1 guard.
- `tests/test_copilot_model_selection.py` — default model, copilot threading, mock-stays-SDK-free (seam_check.main() == 0).
- `tests/test_cli_draft_errors.py` — CliRunner exit-1 rendering for both error classes by name, without importing the adapter.
- `tests/conftest.py` — two over-length docstring lines wrapped (deviation, see below).

## Decisions Made
- Extracted `_map_jsonrpc_error` to keep `draft_unit` clean and avoid a one-value if/elif ladder.
- Used a `_CopilotKwargs` `TypedDict(total=False)` so the lazy copilot factory forwards `model`/`effort` with precise types (keeps `ty` green; the adapter declares non-optional `model: str` / `effort: Effort`).
- CLI classifier kept as a small two-arm `if` chain (ModelRejectedError before BackendUnavailableError); both echo and `raise typer.Exit(code=1) from exc`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wrapped two over-length docstring lines in tests/conftest.py**
- **Found during:** Task 1 (after GREEN, running the `uv run ruff check src tests` gate)
- **Issue:** `tests/conftest.py` (created in plan 03-01, unchanged by 03-02) carried two `E501` line-too-long violations (lines 22 and 272). These blocked the required `ruff check src tests` exit-0 gate that both Task 1 and Task 2 acceptance criteria depend on.
- **Fix:** Wrapped the two long docstring lines (a `:class:` cross-reference and the fixture's Returns signature) without changing any harness behaviour.
- **Files modified:** tests/conftest.py
- **Verification:** `uv run ruff check src tests` → All checks passed; full suite still 117 passed.
- **Committed in:** `786faf5` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking). No scope creep — a docstring re-wrap to clear the mandated lint gate.
**Impact on plan:** None on shipped behaviour.

## Issues Encountered
- **`ty` type error on the kwargs-forwarding dict.** The first implementation forwarded `model`/`effort` through a `dict[str, object]`, which widened the values to `object` and tripped three `invalid-argument-type` diagnostics against `CopilotDraftingProvider.__init__`. Resolved by introducing the `_CopilotKwargs` `TypedDict(total=False)`, preserving each argument's precise type. All gates green afterward.
- **Repo-wide `reuse lint` is non-compliant on out-of-scope files** (the untracked `temp/` scratch dir and a prior plan's `03-01-SUMMARY.md` SPDX expression). Every file this plan creates/changes is individually `uvx reuse lint-file`-clean. Logged to `deferred-items.md`; not fixed (Scope Boundary).

## Automated Gates (all green)
- `uv run pytest` — 117 passed (incl. the 03-01 seam/import/jsonrpc regression guards).
- `uv run ruff check src tests` — clean.
- `uv run ty check src` — clean.
- `python scripts/seam_check.py` — exit 0 (no SDK import outside adapters/copilot/).
- `uv run lint-imports` — 1 contract kept, 0 broken.
- `uvx reuse lint-file` on all plan files — exit 0.

## User Setup Required
**Manual live verification is required and is by design off-CI (D-24).** This plan's Task 3 is a blocking `checkpoint:human-verify`: the real `dogen draft --provider copilot` end-to-end runs need an authenticated Copilot CLI (1.0.64-0) with a live token/network on the dev machine, which the CI/sandbox environment does not have. See the plan's Task 3 `<how-to-verify>` for the exact numbered steps (bare draft on the new default, a Claude-model draft, and a retired-`gpt-5` rejection check).

## Live Verification (D-24) — APPROVED by operator
- **Task 3 human-verify checkpoint: the operator replied "approved" on 2026-06-22.**
- Per that checkpoint's `<done>`/`<resume-signal>` contract, "approved" is the operator's attestation that the off-CI live runs met all stated criteria: written drafts on the bare `gpt-5-mini` default and on `--model claude-sonnet-4.5`, grounded in auto-approved source reads (criteria 1-3 → LIVE-01/02/03), and a clear named model-rejection error with a nonzero exit on the retired `--model gpt-5` (criterion 5 → ERR-01).
- The individual per-criterion command outputs were not separately reported to the framework and were not observed in this environment (no live token/network — D-24); this record reflects the operator's approval, not an automated observation. Combined with the green fake-SDK suite, it closes the phase's manual-verification gate.

## Next Phase Readiness
- All autonomous wiring is complete and unit-proven; the live runs are operator-approved (above). The adapter, mock seam, and CLI are ready.
- Phase 4 (PROV-01/02) can now build on a working live draft to observe and record tool-call events.

## Self-Check: PASSED

- Created files all exist: `tests/test_copilot_session_kwargs.py`, `tests/test_copilot_error_mapping.py`, `tests/test_copilot_model_selection.py`, `tests/test_cli_draft_errors.py`.
- Task commits all present: `105fd94` (RED), `786faf5` (GREEN), `0552dee` (Task 2).

---
*Phase: 03-live-copilot-path-runs-out-of-the-box*
*Completed (autonomous Tasks 1-2): 2026-06-22 — Task 3 awaiting human-verify checkpoint*
