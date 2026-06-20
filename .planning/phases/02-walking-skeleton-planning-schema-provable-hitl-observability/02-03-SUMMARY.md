---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
plan: 03
subsystem: copilot-adapter
tags: [copilot-sdk, provider-seam, bounded-toolset, anti-corruption, backend-unavailable, smoke-test, seam-doc, hexagonal]

# Dependency graph
requires:
  - phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
    plan: 02
    provides: DraftingProvider port, MockDraftingProvider, select_provider dispatch, orchestrator + HITL gate + observability, steer/draft/review CLI
provides:
  - adapters/copilot/tools.py — bounded read-only ToolSet allowlist (grep/glob/view) + write/exec/network denylist, source-qualified via add_builtin (D-28/SKEL-04)
  - adapters/copilot/mapping.py — to_draft_result anti-corruption (assistant.message event -> DraftResult), no SDK type reaches core/
  - adapters/copilot/provider.py — CopilotDraftingProvider (sole SDK importer) + BackendUnavailableError; awaits create_session coroutine; absolute working_directory; get_status/get_auth_status pre-flight
  - scripts/smoke_draft.py — manual local real-SDK smoke harness (SKEL-05 evidence + CLI bump gate, out of CI)
  - docs/seam.md — SEAM-04 design doc (Copilot-agnostic port; mock = swappability proof; OpenCode SDK + Pydantic AI named alternates)
affects: [02-04 sphinx docs build (owns wiring docs/seam.md into the toctree + any published-content license swap)]

# Tech tracking
tech-stack:
  added: []
  patterns: [adapter-as-sole-SDK-importer, anti-corruption-mapping-at-the-seam, bounded-read-only-toolset-via-ToolSet.add_builtin, backend-unavailable-as-handled-state, live-SDK-path-gated-behind-explicit-opt-in, mock-is-the-second-provider-proving-swappability]

key-files:
  created: [src/dogen/adapters/copilot/tools.py, src/dogen/adapters/copilot/mapping.py, src/dogen/adapters/copilot/provider.py, scripts/smoke_draft.py, docs/seam.md, tests/test_copilot_mapping.py, tests/test_copilot_backend_unavailable.py, tests/test_smoke_harness.py]
  modified: [src/dogen/adapters/copilot/__init__.py, src/dogen/adapters/mock_provider.py, src/dogen/cli/main.py, tests/test_observability_correlation.py]

key-decisions:
  - "The blocking A1 checkpoint (exact built-in tool names) was resolved by the human operator via a live probe against the authenticated Copilot CLI; the allowlist is locked to the CONFIRMED strings, no re-prompt"
  - "BackendUnavailableError lives in adapters/copilot/ (not core/) and the orchestrator simply lets it bubble; the CLI catches it via a lazy import so the mock path never loads the SDK adapter (D-25 preserved)"
  - "to_draft_result reads content/model/output_tokens defensively via getattr because evt.data is a union over ~90 event payloads; None model/tokens are coerced (unknown / 0) so the union and any None never reach the domain DraftResult"
  - "system_message is passed as SystemMessageAppendConfig(mode='append', content=...) — the real TypedDict key is content, not the plan-assumed append"
  - "the smoke harness's live path is gated behind --live / DOGEN_SMOKE_LIVE=1 so its argument-handling and backend-unavailable branches are unit-tested in CI with zero SDK/network calls; the captured real run stays a manual operator step (D-24)"
  - "docs/seam.md carries an inline HTML-comment GPL-3.0-only REUSE header (invisible when rendered, valid REUSE comment) rather than a .license sidecar, so plan 04 still owns the published-content licensing decision without this wave pre-empting it"

requirements-completed: [SKEL-04, SKEL-05, SEAM-04, PLAN-04]

# Metrics
duration: ~50min
completed: 2026-06-20
status: complete
---

# Phase 2 Plan 03: Real Copilot Adapter, Bounded Toolset & SEAM-04 Summary

**The production drafting path swapped in behind the very port the mock proved: `CopilotDraftingProvider` on the pinned `github-copilot-sdk==1.0.2`, confined entirely to `adapters/copilot/`, driving a bounded read-only session (grep/glob/view allowlist + write/exec/network denylist), translating the SDK's `assistant.message` event into a domain `DraftResult` so no vendor type reaches `core/`, and converting a down/unauthenticated/transport-broken backend into a handled `BackendUnavailableError` — with a manual local smoke harness as the SKEL-05 evidence/bump-gate and a SEAM-04 doc naming OpenCode SDK + Pydantic AI as the un-built alternates.**

## Checkpoint resolution (A1 — confirmed tool names)

The plan's first task was a blocking human checkpoint to confirm the exact runtime-registered built-in tool names before locking the allowlist (RESEARCH Open Question 1 / Pitfall 1). The human operator resolved it via a live probe against the authenticated Copilot CLI, so it was treated as DONE and the allowlist locked to the **confirmed** strings (no re-prompt):

- **READONLY allowlist (`available_tools`):** `grep`, `glob`, `view` — exactly these three, confirmed registered. Deliberately minimal per D-28 (source/repo read tools only). `web_fetch` was deliberately excluded (it is network access, denied by D-28); agent/session tools (`read_agent`/`list_agents`) were not added.
- **DENY denylist (`excluded_tools`):** `bash`, `edit`, `create`, `stop_bash`, `sql`, `task`, `skill`, `web_fetch` — the confirmed write/exec/network tools.
- **Plan-text correction:** the plan assumed the file-edit tool is `str_replace_editor`; the live probe shows the real registered name is **`edit`**. The denylist uses `edit`, not `str_replace_editor` (which is not a registered tool name on this runtime).
- Names are source-qualified via `ToolSet().add_builtin([...])` (emits `builtin:<name>`); bare strings raise (Pitfall 1) — verified against the installed wheel. The allowlist is the primary control; the denylist is belt-and-braces.

## Recorded runtime facts (the A2 pin / bump-gate reference)

- **Copilot CLI runtime version: `1.0.64-0`** (protocol_version 3) — this is the A2 pin and the SKEL-05 SDK/CLI bump-gate reference. The smoke harness reads it live from `client.get_status().version`.
- SDK: `github-copilot-sdk==1.0.2` (pinned in `pyproject.toml`); auth via `gh-cli`.
- **Absolute-working-directory pitfall:** `client.create_session(...)` rejects a relative `working_directory` with JSON-RPC `-32603` ("Directory path must be absolute: ."). The provider and the smoke harness always pass an **absolute** repo-root path (`os.path.abspath(... or os.getcwd())`), never `"."`.
- `create_session` is a coroutine (must `await`), and its result is itself an async context manager (`async with await client.create_session(...) as session:`). Verified-real surface used: `get_status()`, `get_auth_status()`, `ToolSet().add_builtin`, `session.send_and_wait`, `SystemMessageAppendConfig(mode="append", content=...)`.

## Accomplishments

- **`adapters/copilot/tools.py`** — `READONLY` and `DENY` `ToolSet` constants built via `add_builtin` (source-qualified). The allowlist (`grep`/`glob`/`view`) is the primary SKEL-04 security boundary; the denylist (the eight confirmed write/exec/network tools) is defense-in-depth.
- **`adapters/copilot/mapping.py`** — `to_draft_result(evt, run_id) -> DraftResult`, the anti-corruption layer: reads `content`/`model`/`output_tokens` from the event payload defensively (the payload is a union over ~90 SDK event types) and coerces a missing model/tokens to `unknown`/`0`, so neither the union nor `None` ever reaches the domain model.
- **`adapters/copilot/provider.py`** — `CopilotDraftingProvider` implements the shared `DraftingProvider` port. It opens `async with CopilotClient()`, runs a `get_status`/`get_auth_status` pre-flight, awaits `create_session(...)` with the bounded toolsets + absolute working dir + steering system message, `send_and_wait`s the composed prompt, and maps the `assistant.message` event to a `DraftResult`. `StopError`, connection/OS/timeout failures, status-check failures, and a missing assistant message are all converted into a handled `BackendUnavailableError` (clear message), never a crash (SKEL-05/D-27).
- **Wiring** — `select_provider("copilot")` now lazily constructs the real adapter (D-25 laziness preserved with a justified `# noqa: PLC0415`); the `draft` CLI catches `BackendUnavailableError` via a deferred import and maps it to a clear message + exit 1; `adapters/copilot/__init__.py` re-exports the two public symbols and its docstring now reflects the landed adapter.
- **`scripts/smoke_draft.py`** — the manual local smoke harness. The live SDK path is gated behind `--live` / `DOGEN_SMOKE_LIVE=1`; the default non-live run makes **no** SDK call and prints how to opt in. The live path prints the bundled CLI version (the A2 pin) from `get_status()`, runs one real draft, and degrades gracefully on `BackendUnavailableError` (exit 1). Not wired into CI (D-24).
- **`docs/seam.md`** — the SEAM-04 design doc: the port is shaped by domain verbs (Anti-Pattern 2 avoided), the deterministic mock IS the second provider proving swappability (SEAM-03), and **OpenCode SDK** + a **homegrown Pydantic AI agent** are named as viable un-built alternates that would each be a single new adapter behind the unchanged port.

## How the seam stays green

- `core/` imports zero vendor symbols; the only `from copilot import ...` sites are under `adapters/copilot/` (plus `scripts/smoke_draft.py`, which is not `core/`). `uv run lint-imports` reports **1 kept / 0 broken**, and the AST guardrail `scripts/seam_check.py` reports OK (14 files).
- `BackendUnavailableError` is defined in the adapter, not `core/`; the orchestrator never names it — it simply propagates, and the CLI classifies it via a lazy import so the mock path never loads the SDK adapter.

## Tests added (no live SDK in CI)

- `tests/test_copilot_mapping.py` — maps `content/model/output_tokens` with lightweight fake events (proving no SDK type in `core/`), coerces missing model/tokens, and asserts both toolset constants are `ToolSet`s whose `to_list()` yields exactly the source-qualified `builtin:<name>` filters.
- `tests/test_copilot_backend_unavailable.py` — structural port check (`isinstance(provider, DraftingProvider)`); a stubbed `CopilotClient` raising `StopError` from `get_status` and a `ConnectionError` from `__aenter__` both become a handled `BackendUnavailableError`; `Effort.xhigh` maps to the SDK reasoning-effort literal.
- `tests/test_smoke_harness.py` — non-live default makes no SDK call (exit 0 + opt-in hint), env/flag opt-in parsing, and a stubbed backend-unavailable run returns exit 1.

## Task Commits

1. **Task 1: real Copilot adapter (provider, bounded tools, anti-corruption mapping)** — `b26e71e` (feat)
2. **Task 2: local smoke harness (SKEL-05 evidence + bump gate) and SEAM-04 design doc** — `7e73a8e` (feat)

_TDD note: each task was authored test-first (behaviour tests + minimal implementation), landing as one `feat` commit per task — the convention plans 01/02 recorded._

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Stale plan-02 placeholder test asserted the copilot provider raises `NotImplementedError`**
- **Found during:** Task 1 (full suite run after wiring `select_provider`).
- **Issue:** `tests/test_observability_correlation.py::test_select_provider_copilot_dispatches_lazily` asserted `select_provider("copilot")` raises `NotImplementedError` — the plan-02 stub behaviour, now obsolete because the real adapter lands here.
- **Fix:** renamed to `test_select_provider_copilot_resolves_real_adapter`, asserting it returns a `CopilotDraftingProvider` (lazy import preserved; the sibling mock-path no-import test still guards D-25 laziness).
- **Files modified:** tests/test_observability_correlation.py
- **Committed in:** b26e71e

**2. [Rule 1 - Bug] `SystemMessageAppendConfig` constructed with the wrong key**
- **Found during:** Task 1 (`ty check`).
- **Issue:** the plan/early probe assumed the TypedDict key was `append`; `ty` flagged it as unknown. The real TypedDict keys are `mode` (`Literal['append']`) and `content`.
- **Fix:** pass `SystemMessageAppendConfig(mode="append", content=steer)`.
- **Files modified:** src/dogen/adapters/copilot/provider.py
- **Committed in:** b26e71e

**3. [Rule 1 - Bug] `to_draft_result` typed against the event-data union**
- **Found during:** Task 1 (`ty check`).
- **Issue:** `evt.data` is a union over ~90 event payload types, so static `.content` access failed type-checking; and the SDK reports `model`/`output_tokens` as nullable, which the non-null domain `DraftResult` rejects.
- **Fix:** read all three fields via `getattr` (the mapping is the anti-corruption boundary) and coerce missing model/tokens to `unknown`/`0`.
- **Files modified:** src/dogen/adapters/copilot/mapping.py
- **Committed in:** b26e71e

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs). **Impact:** all necessary for the adapter to compile, type-check, and not regress the suite; no scope change.

## Issues Encountered

- **Whole-repo `reuse lint` reports 4 invalid SPDX expressions, all pre-existing `.planning/` prose (DEF-02-01/02).** The offending files are `01-VERIFICATION.md`, `02-01-SUMMARY.md`, `02-02-SUMMARY.md`, and `deferred-items.md` — each *quotes* a license token inside narrative text, which reuse's parser misreads. None is distributable source/docs and none was touched by this plan. Every source/test/docs file this plan created or modified passes `reuse lint-file` individually (105/105 files carry copyright + license info). The fix remains a `REUSE-IgnoreStart/End` docs-housekeeping pass, deferred as in plans 01/02. This SUMMARY is phrased to avoid adding a fifth trigger.
- **`reuse` runs via `uvx reuse lint`** (it is not a dev dependency), matching plans 01/02 and the pre-commit hook; `uv run reuse lint` is unavailable.
- **`# noqa: PLC0415` on the deferred adapter imports** (in `mock_provider.py`, `cli/main.py`, the smoke harness, and two tests) is load-bearing, not a style escape: a top-level import would load the SDK adapter on the mock/CI path and defeat the seam.

## docs/seam.md in the published tree (coordinate with plan 04)

`docs/seam.md` is **not yet wired into the Sphinx toctree** — `docs/` currently contains only this file and no `conf.py`. This wave gives it an inline HTML-comment GPL-3.0-only REUSE header so `reuse lint` is green now, deliberately **without** a `.license` sidecar. Plan 04 (Wave 4) owns: (a) wiring `docs/seam.md` into the Sphinx build, and (b) IF it converts the docs to published-content licensing, swapping the inline header for a `.license` sidecar under the chosen docs license. This plan does not pre-empt that decision.

## Threat surface scan

No new security-relevant surface beyond the plan's `<threat_model>`. The mitigations are implemented and tested: the bounded read-only allowlist + denylist constrain the agent (T-02.3-01); the toolset is read-only so injected source content cannot make the agent act outside drafting (T-02.3-02); `get_status`/`get_auth_status` + `StopError`/connection handling convert a broken transport into a handled `BackendUnavailableError` (T-02.3-03); the Copilot token is only used in the manual live smoke and is never written to provenance/spans/logs, and CI uses `--provider mock` (T-02.3-04); the SDK is pinned `==1.0.2` and the CLI `1.0.64-0` is recorded as the bump gate (T-02.3-SC). No network egress in any pytest path.

## User Setup Required

None for CI (the mock loop needs no token). To run the **manual** smoke (operator-only): authenticate the Copilot CLI (`gh-cli`/`COPILOT_GITHUB_TOKEN`), then `DOGEN_SMOKE_LIVE=1 uv run python scripts/smoke_draft.py --unit <id>`. This is out of CI by design (D-24).

## Next Phase Readiness

- The `--provider copilot` path now resolves a working real adapter; plan 04 can build the Sphinx docs and wire `docs/seam.md` into the toctree.
- The CLI/CI loop is unchanged on `--provider mock`; no Copilot token is required for any automated gate.
- The CLI pin `1.0.64-0` is recorded as the SDK/CLI bump gate: re-run `scripts/smoke_draft.py --live` and re-record `get_status().version` before trusting the loop after any SDK or CLI bump.

## Self-Check: PASSED

All 8 created files exist on disk (tools.py, mapping.py, provider.py, scripts/smoke_draft.py, docs/seam.md, test_copilot_mapping.py, test_copilot_backend_unavailable.py, test_smoke_harness.py); the 4 modified files exist. Both task commits (`b26e71e`, `7e73a8e`) are present in git history. Final gates: `pytest -q` 65 passed; `ruff check .` clean; `ruff format --check .` clean (33 files); `ty check` clean; `lint-imports` 1 kept / 0 broken; `seam_check.py` OK (14 files); every new/modified file passes `reuse lint-file`.

---
*Phase: 02-walking-skeleton-planning-schema-provable-hitl-observability*
*Completed: 2026-06-20*
