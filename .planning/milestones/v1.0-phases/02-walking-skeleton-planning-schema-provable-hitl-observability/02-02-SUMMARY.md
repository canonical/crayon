---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
plan: 02
subsystem: orchestration
tags: [opentelemetry, logfire, otel-api, mock-provider, hitl, typer, asyncio, hexagonal, provenance, observability]

# Dependency graph
requires:
  - phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
    plan: 01
    provides: F1 Pydantic schema (core.models), domain-verb ports (core.ports), FilesystemPlanningStore, git-identity adapter, `dogen unit new`, import-linter seam contract
provides:
  - core/observability.py — OTel API tracer + draft_span/run_id helpers + non-sensitive span attributes (no logfire/opentelemetry.sdk import)
  - core/orchestrator.py — the one async drafting use-case (DraftRequest-injected), provable-HITL gate (SteeringRequiredError), run_id correlation, pending→sourced→drafted auto-advance, never committed
  - adapters/mock_provider.py — deterministic SDK-free MockDraftingProvider + dict-dispatch select_provider (default copilot, lazy copilot factory)
  - obs/logfire_backend.py — sole logfire import, idempotent configure(send_to_logfire=False) composition root
  - cli/main.py — steer/draft/review thin Typer subcommands behind one asyncio.run boundary
affects: [02-03 copilot adapter + real-SDK smoke, 02-04 sphinx docs build, future review/verification phases]

# Tech tracking
tech-stack:
  added: []
  patterns: [OTel-API-in-core/Logfire-at-edge, deterministic SDK-free provider double, dict-dispatch provider selection with lazy adapter import, DraftRequest dependency bundle for inward-only injection, HITL gate as a domain invariant, in-memory OTel SDK exporter for test-only span assertions, missing-provenance treated as the HITL refusal]

key-files:
  created: [src/dogen/core/observability.py, src/dogen/core/orchestrator.py, src/dogen/adapters/mock_provider.py, src/dogen/obs/__init__.py, src/dogen/obs/logfire_backend.py, tests/test_observability_correlation.py, tests/test_orchestrator_hitl.py, tests/test_loop_mock_e2e.py]
  modified: [src/dogen/cli/main.py, .planning/phases/02-walking-skeleton-planning-schema-provable-hitl-observability/deferred-items.md]

key-decisions:
  - "DraftRequest frozen dataclass bundles the injected collaborators (provider/store/clock/effort) so the use-case keeps inward-only DI without tripping PLR0913 (>5 args) and every function stays ≤60 lines"
  - "A wholly missing provenance.yaml is surfaced as the HITL refusal (SteeringRequiredError), not a FileNotFoundError — 'no steer ever ran' and 'present-but-unsteered' are the same audit outcome (HITL-01/D-40)"
  - "The orchestrator auto-initialises a pending Progress when a freshly-scaffolded unit has no progress.yaml, keeping the lifecycle a domain concern (the PlanningStore port has no exists() verb)"
  - "OBS-03 correlation is asserted with a test-only in-memory OTel SDK exporter (TracerProvider + SimpleSpanProcessor + InMemorySpanExporter); core/ stays API-only and the import-linter seam confirms it"
  - "Test fixtures reset OTel's _TRACER_PROVIDER_SET_ONCE guard so installing the in-memory exporter is order-independent (OTel forbids replacing an already-set global provider)"
  - "The E2E loop drives a real tmp `git init` + `git config` so the git-identity adapter is exercised at its true boundary deterministically (no stub, no network)"

patterns-established:
  - "Span attributes restricted to non-sensitive domain fields (unit_id, intent, provider, run_id) — no token/secret can leak into a trace (threat T-02.2-03)"
  - "Provider dispatch is a dict of factories, not an if/elif ladder (coding-guide §2); the copilot branch stays a lazy import so the mock path never loads adapters/copilot/ (D-25)"
  - "A no-committed AST scan test walks the orchestrator and fails if ProgressState.committed is ever referenced (SKEL-03/Pitfall 9)"

requirements-completed: [SEAM-03, PLAN-04, PLAN-05, PLAN-06, HITL-01, HITL-02, OBS-01, OBS-02, OBS-03, SKEL-03]

# Metrics
duration: ~45min
completed: 2026-06-20
status: complete
---

# Phase 2 Plan 02: Walking-Skeleton Loop, Provable HITL & Observability Summary

**The inseparable A2 drafting loop on top of the F1 schema: an OTel-API observability layer, a deterministic SDK-free `MockDraftingProvider`, the one async `core/orchestrator.py` use-case enforcing the provable-HITL gate and correlating each run to provenance via `run_id`, and the `steer`/`draft`/`review` CLI — exercised end-to-end on `--provider mock` in CI with no Copilot SDK or token, stopping before any commit.**

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-06-20
- **Tasks:** 3 (each TDD: tests + implementation landed together, run RED→GREEN)
- **Files:** 10 (8 created, 2 modified)
- **Final suite:** 53 tests passing (21 new this plan)

## Accomplishments

- **`core/observability.py`** — vendor-neutral OTel **API** helpers: `get_tracer()`, a `draft_span()` context manager that opens `dogen.draft` and yields `(span, run_id)` with `run_id = format(trace_id, "032x")`, and `set_draft_attributes()` restricted to non-sensitive domain fields. Imports neither `logfire` nor `opentelemetry.sdk` (OBS-01/D-20), asserted both by a test and by the import-linter contract.
- **`adapters/mock_provider.py`** — `MockDraftingProvider` implementing `DraftingProvider.draft_unit` with a deterministic MyST snippet derived only from the inputs (no wall-clock, no randomness, no SDK; D-23), plus `select_provider(name="copilot")` as a dict dispatch of factories, the `copilot` factory lazily importable (D-25).
- **`obs/logfire_backend.py`** — the single `logfire` import site; `configure_observability()` runs `logfire.configure(send_to_logfire=False)` once (idempotent), wired only at the CLI composition root (OBS-02/D-21).
- **`core/orchestrator.py`** — the one async `draft(DraftRequest)` use-case, decomposed into ≤60-line functions: load unit + provenance, enforce the HITL gate, open the span, mint `run_id`, drive the injected provider, write the draft, append a `generations[]` entry stamped with the correlated `run_id`, and auto-advance `pending→sourced→drafted`. No path writes `committed` (SKEL-03).
- **`cli/main.py`** — three thin subcommands: `steer` (capture git author + clock → stamp `provenance.steering`, D-39), `draft` (configure observability once, select provider by name, run the orchestrator under a single `asyncio.run`, map `SteeringRequiredError` → clear message + nonzero exit, D-40), `review` (append one `reviewer_edits[]` entry, advance to `reviewed`, D-38).

## Orchestrator function decomposition

The use-case is split so every function is ≤60 lines and the injected collaborators flow through one frozen `DraftRequest`:

| Function | Responsibility |
|----------|----------------|
| `draft(request)` | Public entry: load unit, get steered provenance, delegate to `_run_draft`. |
| `_read_steered_provenance(request)` | Read provenance; a missing file **is** the HITL refusal; then `_require_steering`. |
| `_require_steering(provenance)` | The domain invariant: raise `SteeringRequiredError` if `steering is None`. |
| `_run_draft(request, unit, provenance)` | Open the span, set attributes, call the provider, write draft, record generation, write provenance, advance progress. |
| `_record_generation(provenance, request, unit, result, run_id)` | Append the `generations[]` entry (model/effort/tooling_version/sdk/context_origins/run_id/at/action). |
| `_advance_progress(request)` | Walk the `pending→sourced→drafted` ladder; write history; never `committed`. |
| `_read_or_init_progress(request)` | Initialise a `pending` Progress when a scaffolded unit has none. |

## How run_id correlation is tested (OBS-03)

`core/` only touches the OTel **API**, so a no-op tracer is in effect by default and spans aren't recorded. The tests install a **test-only** in-memory OTel **SDK** exporter (`TracerProvider` + `SimpleSpanProcessor` + `InMemorySpanExporter`) in a fixture, reset OTel's `_TRACER_PROVIDER_SET_ONCE` guard for order-independence, run the draft, and assert that `provenance.generations[0].run_id == format(finished_span.context.trace_id, "032x")`. The same exporter proves `draft_span()` yields a `run_id` matching the exported span. This keeps the seam clean (the SDK lives only in the test fixture) while proving the on-disk audit surface and the runtime trace line up.

## Mock loop runs in CI with no SDK / token (D-24)

`tests/test_loop_mock_e2e.py` drives `unit new → steer → draft --provider mock → review` through Typer's `CliRunner` against a tmp `git init` repo (real `git config` identity, no network). It asserts: all four F1 files + the `docs/<target>.md` draft appear schema-valid; `draft` before `steer` exits nonzero with "no recorded steering" and writes no draft (HITL-01); `provenance.steering.author/.at` are populated and the steering `at` precedes the first `generations[].at` (HITL-02/AC5); exactly one `reviewer_edits[]` entry; progress ends `reviewed` and never `committed`. A separate test parses the module's own imports (via AST, to avoid self-matching the banned token in the assertion text) and asserts no `copilot`/`github_copilot_sdk` import — so the loop is CI-runnable with no Copilot SDK or token. CI already runs `pytest` from Phase 1, so this loop is exercised on every push; the real-SDK smoke stays out of CI (that is plan 03).

## Task Commits

1. **Task 1: observability layer, mock provider, provider dispatch** — `a514fe0` (feat)
2. **Task 2: drafting orchestrator with provable-HITL gate** — `25334a4` (feat)
3. **Task 3: wire steer/draft/review CLI and the mock E2E loop** — `217cadc` (feat)

_TDD note: each task was authored test-first (RED tests + minimal implementation), landing as one `feat` commit per task because each behaviour set and its implementation are inseparable for this skeleton — the same convention plan 01 recorded._

## Files Created/Modified
- `src/dogen/core/observability.py` — OTel API tracer/span/run_id/attribute helpers
- `src/dogen/core/orchestrator.py` — the async drafting use-case + HITL gate + lifecycle
- `src/dogen/adapters/mock_provider.py` — deterministic mock + `select_provider`
- `src/dogen/obs/__init__.py`, `src/dogen/obs/logfire_backend.py` — Logfire composition root
- `tests/test_observability_correlation.py`, `tests/test_orchestrator_hitl.py`, `tests/test_loop_mock_e2e.py` — behaviour tests
- `src/dogen/cli/main.py` — added `steer`/`draft`/`review` thin subcommands
- `.planning/.../deferred-items.md` — logged DEF-02-02

## Decisions Made
See `key-decisions` frontmatter. The load-bearing ones: bundling injected collaborators into `DraftRequest` (keeps inward-only DI under the ≤5-arg / ≤60-line limits); treating a missing `provenance.yaml` as the HITL refusal rather than a file error; and asserting OBS-03 via a test-only in-memory OTel SDK exporter so `core/` stays API-only.

## Deviations from Plan

None affecting scope. Adjustments handled inline:

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `draft` without any prior `steer` raised `FileNotFoundError`, not the HITL refusal**
- **Found during:** Task 3 (E2E test `test_draft_refuses_without_steer`).
- **Issue:** `unit new` creates only `unit.md`; with no `steer`, `provenance.yaml` does not exist, so `read_provenance` raised `FileNotFoundError` before the HITL gate, producing exit code 2 + a file-path error instead of the "no recorded steering" refusal (HITL-01/D-40).
- **Fix:** added `_read_steered_provenance` in the orchestrator — a missing provenance is surfaced as `SteeringRequiredError` (the same outcome as a present-but-unsteered record). The CLI maps it to the clear message + exit 1.
- **Files modified:** src/dogen/core/orchestrator.py
- **Committed in:** 217cadc

**2. [Rule 3 - Blocking] `draft` failed when a scaffolded unit had no `progress.yaml`**
- **Found during:** Task 3.
- **Issue:** the orchestrator's progress auto-advance read `progress.yaml`, which a freshly-scaffolded unit does not have, raising `FileNotFoundError`.
- **Fix:** added `_read_or_init_progress` — initialise a `pending` Progress when none exists, keeping the lifecycle a domain concern (the port has no `exists()` verb).
- **Files modified:** src/dogen/core/orchestrator.py
- **Committed in:** 217cadc

**3. [Rule 1 - Bug] self-defeating SDK-import assertion**
- **Found during:** Task 3.
- **Issue:** the first form of `test_e2e_imports_no_sdk` scanned the file's raw text for banned tokens, but the assertion lines themselves contain those tokens, so it always failed.
- **Fix:** parse the module's own `import`/`from` statements via AST and assert no `copilot`/`github_copilot_sdk` top-level module is imported.
- **Files modified:** tests/test_loop_mock_e2e.py
- **Committed in:** 217cadc

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug). **Impact:** all necessary for the loop and its gates; no scope creep.

## Issues Encountered

- **`reuse lint` whole-repo invalid-SPDX count is 2 (out of scope, deferred).** `uvx reuse lint` reports two invalid SPDX expressions, both in `.planning/` planning artifacts: `01-VERIFICATION.md` (DEF-02-01, pre-existing from Phase 1) and `02-01-SUMMARY.md` (DEF-02-02 — its own "Issues Encountered" prose quotes a bare license token after an <!-- REUSE-IgnoreStart -->`SPDX-License-Identifier:`<!-- REUSE-IgnoreEnd --> mention). Neither file was touched by this plan. Every source/test file this plan created passes `reuse lint-file` individually. Logged both as DEF-02-01/02 in `deferred-items.md`; the fix is a docs-housekeeping `REUSE-IgnoreStart/End` pass, not this walking-skeleton plan.
- **`reuse` is not a dev dependency**, so the REUSE gate runs via `uvx reuse lint` (matching plan 01 and the pre-commit `reuse` hook); `uv run reuse lint` is not available.

## Threat surface scan

No new security-relevant surface beyond the plan's `<threat_model>`. The mitigations are implemented and tested: the HITL gate is a domain invariant with no side effects on refusal (T-02.2-01); no path writes `committed`, asserted by an AST scan (T-02.2-02); span attributes are restricted to non-sensitive domain fields and Logfire runs `send_to_logfire=False` (T-02.2-03). No network egress anywhere in the mock loop.

## User Setup Required
None — the mock loop needs no external service or token. The real Copilot SDK run is a later-plan manual smoke test (plan 03), out of scope here.

## Next Phase Readiness
- The orchestrator drives `await provider.draft_unit(...)` behind the `DraftingProvider` port, so plan 03 can drop the real Copilot adapter in behind `select_provider("copilot")` with no change to `core/` or the CLI.
- The provenance now carries steering + generations[] (with run_id) + reviewer_edits[]; progress advances to `reviewed` and never `committed` — the audit surface plan 03's smoke test and the AC5 audit consume.
- The OTel API spans are ready for the real Logfire backend at the composition root; the SDK already propagates W3C trace context so the `run_id` will span both the core loop and the SDK's own telemetry.

## Self-Check: PASSED

All 8 created source/test files exist on disk; the modified `cli/main.py` exists; all 3 task commits (`a514fe0`, `25334a4`, `217cadc`) are present in git history. Final gates: `pytest -q` 53 passed; `ruff check .` clean; `ruff format --check .` clean; `ty check` clean; `lint-imports` 1 kept / 0 broken; `seam_check.py` OK (14 files).

---
*Phase: 02-walking-skeleton-planning-schema-provable-hitl-observability*
*Completed: 2026-06-20*
