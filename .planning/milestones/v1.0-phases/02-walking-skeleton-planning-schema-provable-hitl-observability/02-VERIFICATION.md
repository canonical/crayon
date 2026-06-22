---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
verified: 2026-06-20T14:00:00Z
status: passed
score: 19/19
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 18/19
  gaps_closed:
    - "_advance_progress resets a reviewed unit cleanly to drafted on re-draft (one transition, no backward sourced walk) — WR-04 follow-up (commit 78c154f)"
    - "`dogen review` before any draft gives a plain 'has not been drafted yet — run dogen draft first' message at exit 2 instead of a generic read error — WR-05 UX (commit 668f4f8)"
  gaps_remaining: []
  regressions: []
---

# Phase 02: Walking Skeleton — Verification Report

**Phase Goal:** The agent drafts one operator-defined documentation unit end-to-end — from human-pointed sources into Sphinx-publishable MyST output — stopping before any commit, while writing the F1 planning directory (steering, provenance, progress), refusing to draft without recorded steering, and emitting SDK-independent observability that correlates with the provenance record.
**Verified:** 2026-06-20T14:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (previous: human_needed, 18/19)

---

## Gate Results (Run Fresh This Verification)

| Gate | Command | Result | Status |
|------|---------|--------|--------|
| Full test suite | `uv run pytest -q` | 78 passed | PASS |
| Import-linter seam contract | `uv run lint-imports` | 1 kept, 0 broken | PASS |
| Sphinx build (warnings-as-errors) | `uv run --extra docs sphinx-build -W -b html docs docs/_build` | build succeeded | PASS |

---

## Goal Achievement

### Observable Truths

All 19 truths are verified by code presence, wiring, and passing behavioral tests.
The two previously PRESENT_BEHAVIOR_UNVERIFIED / human-needed items are now VERIFIED by newly added tests that both pass.

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Operator can run `dogen unit new <id>` and a per-unit directory `.dogen/units/<id>/` with an editable `unit.md` template is created on disk | VERIFIED | `cli/main.py unit_new` delegates to `FilesystemPlanningStore.scaffold_unit`; test_cli_unit_new.py passes; 78/78 tests pass |
| 2 | Every machine-readable F1 file carries `schema_version: 0` so future migrations are explicit and detectable | VERIFIED | `Unit`, `Provenance`, `Progress` each have `schema_version: int = 0` in `core/models.py`; test_models.py verifies round-trips and defaults |
| 3 | The F1 Pydantic models reserve verification-evidence fields (step state, evidence pointer, environment fingerprint) present-but-empty at v0 | VERIFIED | `VerificationStep` has `state="unverified"`, `evidence=None`, `env_fingerprint=None`; `Verification.steps=[]` and `Provenance.reviewer_edits=[]` by default; test_models.py exercises these |
| 4 | `unit.md` front-matter records intent, audience, title, human-pointed sources, sphinx_target, and steering_notes as distinct fields | VERIFIED | `Unit` model in `core/models.py` defines all these fields; `sphinx_target` has a `model_validator` rejecting absolute/`..`-bearing values (CR-01 fix); dogfood `.dogen/units/cli-reference/unit.md` exists on disk |
| 5 | `import-linter` fails the build if `core/` imports `copilot`, `github_copilot_sdk`, `logfire`, `opentelemetry.sdk`, or `adapters.*` | VERIFIED | `pyproject.toml` `[tool.importlinter]` contract present; `uv run lint-imports` outputs "1 kept, 0 broken" (confirmed this run) |
| 6 | The full loop `unit new → steer → draft → review` runs end-to-end in CI on the deterministic mock provider with no github-copilot-sdk import and no network | VERIFIED | test_loop_mock_e2e.py: 7 tests pass including `test_full_loop_reaches_reviewed` and `test_e2e_imports_no_sdk`; CI `gates` job runs pytest on Python 3.12 + 3.13 |
| 7 | `dogen draft` hard-refuses (clear message, nonzero exit, no draft written) when no steering event has been recorded | VERIFIED | `orchestrator._read_steered_provenance` raises `SteeringRequiredError` on missing provenance.yaml (FileNotFoundError mapped); CLI maps it to exit 1 + "no recorded steering" message; `test_draft_refuses_without_steer` passes |
| 8 | `dogen steer` records the HITL event with author + timestamp (from git config) into `provenance.yaml.steering` as a discrete act that provably precedes drafting | VERIFIED | `cli/main.py steer()` calls `read_git_identity()` + `_utc_now()` and writes `Steering(author, at, intent, audience)` via `write_provenance`; dogfood provenance.yaml shows `steering.author: Artem Konev`; `test_steer_records_author_and_precedes_draft` passes |
| 9 | Each draft run mints a `run_id` from the OTel trace id and stamps it into the matching `provenance.yaml` generations[] entry, so the trace and the on-disk audit surface line up | VERIFIED | `observability.draft_span()` yields `(span, run_id)` where `run_id = format(trace_id, "032x")`; orchestrator stamps `run_id` on `Generation`; OBS-03 correlation asserted by in-memory OTel SDK exporter in test_observability_correlation.py |
| 10 | `dogen review --note` appends a `reviewer_edits[]` entry and advances progress to `reviewed`; no code path ever sets `committed` | VERIFIED | `cli/main.py review()` appends `ReviewerEdit` and sets `ProgressState.reviewed` (idempotent per WR-05 fix); `test_orchestrator_never_writes_committed` AST-scans orchestrator and confirms no `ProgressState.committed` reference; dogfood `progress.yaml` shows `state: reviewed` |
| 11 | `_advance_progress` is monotonic/idempotent when the unit is in `reviewed` state and `dogen draft` is re-run | VERIFIED | `_PROGRESS_ORDER` now includes `reviewed` (index 3); `current > drafted_rank` branch fires for a reviewed unit, emitting exactly one `drafted` transition with no backward `sourced` re-stamp; `test_redraft_of_reviewed_resets_to_drafted` passes and asserts state=drafted, exactly one new `drafted` entry, sourced appears only once (commit 78c154f) |
| 12 | The real Copilot adapter implements the same `DraftingProvider` port the mock does | VERIFIED | `CopilotDraftingProvider` in `adapters/copilot/provider.py` implements `async def draft_unit(...)` matching the port; `test_copilot_backend_unavailable.py::test_copilot_provider_is_drafting_provider` passes |
| 13 | The agent operates with a bounded read-only toolset (grep/glob/view), with write/exec/network tools denied | VERIFIED | `adapters/copilot/tools.py` defines `READONLY = ToolSet().add_builtin(["grep","glob","view"])` and `DENY = ToolSet().add_builtin([...8 tools...])` via source-qualified `add_builtin`; test_copilot_mapping.py asserts `ToolSet` instances with `builtin:<name>` filters |
| 14 | Backend unavailable is a handled state (clear message, nonzero exit, never a crash) | VERIFIED | `CopilotDraftingProvider.draft_unit` wraps `StopError`, connection errors, and status failures into `BackendUnavailableError`; CLI maps it to exit 1; 4/4 backend-unavailable tests pass |
| 15 | SEAM-04 is documented: the port is Copilot-agnostic with OpenCode SDK / Pydantic AI named as viable alternates | VERIFIED | `docs/seam.md` exists and states DraftingProvider uses domain verbs; names "OpenCode SDK" and "homegrown Pydantic AI agent" as un-built alternates; wired into Sphinx toctree |
| 16 | A real Sphinx build succeeds in CI with -W (warnings-as-errors), proving Sphinx-publishable | VERIFIED | `sphinx-build -W -b html docs docs/_build` ran this verification and returned "build succeeded"; CI `docs` job does same on Python 3.12 |
| 17 | The Sphinx config parses MyST with colon_fence enabled; the drafted page is referenced from a toctree | VERIFIED | `docs/conf.py` has `extensions=["myst_parser"]` and `myst_enable_extensions=["colon_fence"]`; `docs/index.md` toctree references `cli-reference` and `seam` |
| 18 | The docs/content license is decided (CC-BY-SA-4.0), licensing.md contradiction reconciled, and reuse lint passes for the drafted page | VERIFIED | `LICENSES/CC-BY-SA-4.0.txt` present; `docs/cli-reference.md.license` and `docs/seam.md.license` carry CC-BY-SA-4.0; `licensing.md` §1/§2/§3.5 all agree; `uvx reuse lint` exits 0 on all source/docs files (4 `.planning/` prose false-positives pre-exist and are known deferred DEF-02-01/02) |
| 19 | The committed `.dogen/units/<id>/` audit surface is REUSE-compliant via a REUSE.toml `.dogen/**` glob | VERIFIED | `REUSE.toml` has `.dogen/**` `[[annotations]]` block with `GPL-3.0-only`; `.dogen/units/cli-reference/{unit.md,provenance.yaml,progress.yaml}` committed; `uvx reuse lint` counts 117/117 files covered |

**Score:** 19/19 truths verified (0 present, behavior-unverified)

---

### Re-Verification Focus: Previously Flagged Items

#### WR-04 follow-up: re-draft of a reviewed unit (commit 78c154f)

**Fix:** `_PROGRESS_ORDER` was extended to include `ProgressState.reviewed` (at index 3, after `drafted` at index 2). `_advance_progress` now has three branches:

- `state is drafted` → no-op (unchanged)
- `current < drafted_rank` (pending/sourced) → walk forward ladder stamping each newly-reached state (unchanged)
- `current > drafted_rank` (reviewed, or any post-ladder state) → single clean reset: set `state = drafted`, append one `ProgressEntry(drafted)` — no backward `sourced` walk

The `len(_PROGRESS_ORDER)` fallback for states truly outside the ladder (only `committed`, which the orchestrator never writes per SKEL-03) still handles positional ranking correctly.

**Test:** `test_redraft_of_reviewed_resets_to_drafted` seeds a unit through the full loop to `reviewed`, then re-drafts. Asserts: `after.state is ProgressState.drafted`, `after_states == [*before_states, ProgressState.drafted]` (exactly one new entry), `after_states.count(ProgressState.sourced) == 1`. **Passes.**

**SKEL-03 guard still holds:** `ProgressState.committed` does not appear as a `ProgressState` attribute access in orchestrator.py (only in docstrings/comments). `test_orchestrator_never_writes_committed` AST-walks the source and confirms this. **Passes.**

#### WR-05 UX: review before draft (commit 668f4f8)

**Fix:** `review()` in `cli/main.py` now has a separate `except FileNotFoundError` handler for `store.read_progress(...)`, distinct from the provenance `(FileNotFoundError, ValueError)` handler. It emits: `"Cannot review {unit_id!r}: it has not been drafted yet — run dogen draft {unit_id} first."` at `typer.Exit(code=2)`.

**Test:** `test_review_before_draft_says_draft_first` invokes `dogen review u --note premature` after `dogen steer u` but before any draft. Asserts `exit_code == 2` and `"has not been drafted yet" in result.output`. **Passes.**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/dogen/core/models.py` | F1 schema v0: Unit, Steering, Generation, ReviewerEdit, VerificationStep, Verification, Provenance, Progress, DraftResult, enums | VERIFIED | All named classes present; `schema_version=0`; `xhigh` in Effort; model_version distinct from model |
| `src/dogen/core/ports.py` | DraftingProvider, SourceLookup, PlanningStore Protocol ports | VERIFIED | All three `@runtime_checkable` Protocols with domain-verb method names; zero vendor imports |
| `src/dogen/adapters/planning_fs.py` | FilesystemPlanningStore over .dogen/units/<id>/ and docs/ | VERIFIED | `FilesystemPlanningStore`, `split_front_matter`, `_assert_within_root`, `_assert_not_under_planning`; path-traversal fix present |
| `src/dogen/adapters/git_identity.py` | git config reader behind allowlisted subprocess | VERIFIED | `def read_git_identity` present; explicit allowlisted subprocess call |
| `src/dogen/cli/main.py` | Typer app with unit new + steer + draft + review commands | VERIFIED | `app = typer.Typer(...)`; 4 subcommands; WR-05 fix present at lines 241-251 |
| `src/dogen/core/orchestrator.py` | Drafting use-case: OTel span, run_id mint, HITL gate, provider dispatch, F1 writes, progress auto-advance | VERIFIED | `_PROGRESS_ORDER` includes `reviewed` at index 3; WR-04 fix present at lines 303-324; `committed` absent as executable reference |
| `src/dogen/core/observability.py` | OTel API tracer/span helpers (no logfire / opentelemetry.sdk import) | VERIFIED | `def get_tracer`, `def draft_span`, `run_id_from_span`; imports only `opentelemetry.trace` |
| `src/dogen/adapters/mock_provider.py` | Deterministic MockDraftingProvider with no SDK import | VERIFIED | `class MockDraftingProvider`; `select_provider` dict dispatch; `_MOCK_MODEL_VERSION = "mock-1"` |
| `src/dogen/obs/logfire_backend.py` | Sole logfire import site; configure(send_to_logfire=False) | VERIFIED | `import logfire`; `configure_observability()` idempotent |
| `src/dogen/adapters/copilot/provider.py` | CopilotDraftingProvider — sole SDK importer; backend-unavailable handling | VERIFIED | `class CopilotDraftingProvider`; `BackendUnavailableError`; `await create_session` |
| `src/dogen/adapters/copilot/tools.py` | Bounded read-only ToolSet allowlist + denylist | VERIFIED | `add_builtin(["grep","glob","view"])` for READONLY; 8-tool denylist |
| `src/dogen/adapters/copilot/mapping.py` | Anti-corruption: SDK event → DraftResult | VERIFIED | `def to_draft_result` present; uses `getattr` defensively |
| `scripts/smoke_draft.py` | Manual local smoke harness; backend-unavailable handled | VERIFIED | `get_status` call present; `--live` gate; CLI version 1.0.64-0 recorded |
| `docs/seam.md` | SEAM-04 design doc: port is Copilot-agnostic, alternates named | VERIFIED | States domain verbs; mock as second provider; OpenCode SDK + Pydantic AI named |
| `docs/conf.py` | Sphinx config: myst_parser extension, colon_fence, source_suffix | VERIFIED | `extensions = ["myst_parser"]`; `myst_enable_extensions = ["colon_fence"]` |
| `docs/index.md` | Docs root with toctree referencing the drafted page | VERIFIED | `:::{toctree}` references `cli-reference` and `seam` |
| `.readthedocs.yaml` | RTD config v2, Python 3.12, fail_on_warning, install .[docs] | VERIFIED | All required fields present; `sphinx.fail_on_warning: true` |
| `LICENSES/CC-BY-SA-4.0.txt` | Docs/content license text for REUSE | VERIFIED | File present in LICENSES/ directory |
| `REUSE.toml` | `.dogen/**` glob annotation, GPL-3.0-only | VERIFIED | `.dogen/**` block with `precedence = "aggregate"`, `GPL-3.0-only` |
| `.github/workflows/ci.yml` | CI gates job + docs job with sphinx-build -W | VERIFIED | `gates` job: pytest, lint-imports, ruff, ty check, seam check; `docs` job: sphinx-build -W |
| `.dogen/units/cli-reference/{unit.md,provenance.yaml,progress.yaml}` | Committed AC5 audit surface | VERIFIED | All three files present; provenance shows steering + generation + reviewer_edits; progress shows `state: reviewed` |
| `docs/cli-reference.md` (+ `.license`) | First dogfood drafted page | VERIFIED | MyST content documenting real CLI commands; CC-BY-SA-4.0 sidecar |
| `tests/test_orchestrator_hitl.py::test_redraft_of_reviewed_resets_to_drafted` | New test for WR-04 follow-up | VERIFIED | Added in commit 78c154f; passes |
| `tests/test_loop_mock_e2e.py::test_review_before_draft_says_draft_first` | New test for WR-05 UX | VERIFIED | Added in commit 668f4f8; passes |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli/main.py` | `adapters/planning_fs.py` | `scaffold_unit` call in `unit_new` | WIRED | Confirmed in source |
| `cli/main.py` | `core/orchestrator.py` | `asyncio.run(draft_use_case(request))` in `draft()` | WIRED | `from dogen.core.orchestrator import draft as draft_use_case` |
| `core/orchestrator.py` | `core/observability.py` | `observability.draft_span()` yields `(span, run_id)` | WIRED | `from dogen.core import observability` at top of orchestrator |
| `core/orchestrator.py` | `adapters/mock_provider.py` | `select_provider(provider)` resolves to `MockDraftingProvider` | WIRED | `DraftRequest.provider = select_provider(provider)` in CLI; factory dict dispatch |
| `adapters/copilot/provider.py` | `core/ports.py` | `CopilotDraftingProvider` implements `DraftingProvider` | WIRED | `isinstance(provider, DraftingProvider)` test passes |
| `adapters/copilot/provider.py` | `adapters/copilot/tools.py` | `available_tools=READONLY, excluded_tools=DENY` in `create_session` | WIRED | Confirmed; test_copilot_mapping.py confirms ToolSet constants |
| `adapters/copilot/provider.py` | `adapters/copilot/mapping.py` | `to_draft_result(evt, run_id)` call | WIRED | `from dogen.adapters.copilot.mapping import to_draft_result` |
| `obs/logfire_backend.py` | `opentelemetry` | `logfire.configure(send_to_logfire=False)` installs OTel SDK provider | WIRED | `import logfire` + `logfire.configure(send_to_logfire=False)` confirmed |
| `pyproject.toml` | `dogen.core` | `[tool.importlinter]` contract forbids vendor imports | WIRED | `lint-imports` outputs "1 kept, 0 broken" (confirmed this run) |
| `docs/index.md` | `docs/cli-reference.md` | toctree entry `cli-reference` | WIRED | `:::{toctree}` contains `cli-reference`; sphinx-build -W passes (confirmed this run) |
| `.github/workflows/ci.yml` | `docs/conf.py` | `sphinx-build -W -b html docs docs/_build` in docs job | WIRED | `docs` job in ci.yml confirmed |
| `cli/main.py review()` | `store.read_progress()` | Separate `FileNotFoundError` guard emitting "not drafted yet" | WIRED | Lines 241-251 of main.py; test_review_before_draft_says_draft_first passes |
| `orchestrator._advance_progress` | `_PROGRESS_ORDER` with `reviewed` | `current > drafted_rank` branch for clean re-draft reset | WIRED | Lines 303-324 of orchestrator.py; test_redraft_of_reviewed_resets_to_drafted passes |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite (78 tests) | `uv run pytest -q` | 78 passed | PASS |
| Import-linter seam contract | `uv run lint-imports` | 1 kept, 0 broken | PASS |
| Sphinx build (-W) | `uv run --extra docs sphinx-build -W -b html docs docs/_build` | build succeeded | PASS |
| WR-04 fix: re-draft of reviewed unit | `uv run pytest -q tests/test_orchestrator_hitl.py::test_redraft_of_reviewed_resets_to_drafted -v` | 1 passed | PASS |
| WR-05 fix: review before draft UX | `uv run pytest -q tests/test_loop_mock_e2e.py::test_review_before_draft_says_draft_first -v` | 1 passed | PASS |
| SKEL-03 guard: committed never written | `uv run pytest -q tests/test_orchestrator_hitl.py::test_orchestrator_never_writes_committed -v` | 1 passed | PASS |
| WR-04 original: re-draft of drafted unit | `uv run pytest -q tests/test_orchestrator_hitl.py::test_redraft_does_not_move_progress_backward` | 1 passed | PASS (no regression) |
| WR-05 original: review idempotency | `uv run pytest -q tests/test_loop_mock_e2e.py::test_review_twice_appends_single_reviewed_transition` | 1 passed | PASS (no regression) |
| E2E mock loop | `uv run pytest -q tests/test_loop_mock_e2e.py` | 7 passed | PASS |
| Orchestrator HITL suite | `uv run pytest -q tests/test_orchestrator_hitl.py` | 7 passed | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| SKEL-01 | 02-01 | Operator defines a unit and points agent at sources | SATISFIED | `dogen unit new` works end-to-end; unit.md with sources field |
| SKEL-02 | 02-04 | Agent drafts into Sphinx-publishable MyST | SATISFIED | `sphinx-build -W` passes (confirmed this run); docs/cli-reference.md committed |
| SKEL-03 | 02-02 | Loop stops before commit | SATISFIED | No code path writes `ProgressState.committed`; AST scan test passes; `committed` absent from _PROGRESS_ORDER |
| SKEL-04 | 02-03 | Bounded read-only toolset | SATISFIED | READONLY ToolSet with grep/glob/view; DENY with 8 write/exec/network tools |
| SKEL-05 | 02-03 | Pinned SDK; backend-unavailable handled | SATISFIED | `github-copilot-sdk==1.0.2` in pyproject; BackendUnavailableError tested; smoke harness with CLI version 1.0.64-0 |
| SEAM-03 | 02-02 | DraftingProvider port; mock proves swappability | SATISFIED | MockDraftingProvider + CopilotDraftingProvider both implement same port |
| SEAM-04 | 02-01, 02-03 | Multi-provider design; port documented; alternates named | SATISFIED | docs/seam.md; DraftingProvider shaped by domain verbs; OpenCode SDK + Pydantic AI named |
| PLAN-01 | 02-01 | Per-unit planning directory persisted | SATISFIED | unit.md, provenance.yaml, progress.yaml in .dogen/units/<id>/ |
| PLAN-02 | 02-01 | schema_version field | SATISFIED | Unit, Provenance, Progress each have `schema_version: int = 0` |
| PLAN-03 | 02-01 | unit.md front-matter fields | SATISFIED | intent, audience, title, sources, sphinx_target, steering_notes all present |
| PLAN-04 | 02-02 | provenance.yaml records per-generation fields | SATISFIED | Generation model with model/model_version/effort/tooling_version/sdk/context_origins/tools_used/run_id/at/action |
| PLAN-05 | 02-02 | provenance.yaml records reviewer_edits | SATISFIED | ReviewerEdit with at/reviewer/summary; dogfood provenance has one entry |
| PLAN-06 | 02-02 | progress.yaml tracks lifecycle | SATISFIED | ProgressState enum; pending→sourced→drafted→reviewed; never committed; re-draft of reviewed resets cleanly to drafted (WR-04 follow-up) |
| PLAN-07 | 02-01 | Schema reserves verification evidence fields | SATISFIED | VerificationStep with state/evidence/env_fingerprint; Verification.steps=[]; reviewer_edits=[] |
| HITL-01 | 02-02 | Refuses draft without recorded steering | SATISFIED | SteeringRequiredError; exit 1; test_draft_refuses_without_steer passes |
| HITL-02 | 02-02 | Steering captures author+timestamp | SATISFIED | Steering.author from git config; Steering.at precedes Generation.at; test asserts ordering |
| OBS-01 | 02-02 | Provider-independent instrumentation in core | SATISFIED | core/observability.py uses opentelemetry.trace API only; logfire/opentelemetry.sdk excluded; lint-imports passes |
| OBS-02 | 02-02 | Concrete backend wired; Logfire local | SATISFIED | obs/logfire_backend.py; configure_observability() at CLI root; send_to_logfire=False |
| OBS-03 | 02-02 | Run-level observability correlates with provenance | SATISFIED | run_id = format(trace_id, "032x") stamped into generations[]; test_observability_correlation.py proves equality |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.dogen/units/cli-reference/provenance.yaml` | — | `model_version: mock-model` equals `model` value | Info | Pre-fix artifact written before the WR-03 fix; the fix is correct in `mock_provider.py` (`_MOCK_MODEL_VERSION = "mock-1"`). New drafts will record `mock-1` as model_version. Not a code defect. |

No TBD/FIXME/XXX markers found in phase-modified source files. No stubs. No placeholder return values in production paths.

---

### Known Deferred Debt (Non-Blocking)

`uvx reuse lint` reports 4 invalid SPDX expressions in `.planning/` prose files (DEF-02-01/02). These are planning artifacts that quote SPDX tokens in narrative text, which the REUSE parser misreads. All 117/117 tracked files carry copyright and license information. No distributable or source file is affected. Documented deferred debt; does not constitute a phase gap.

---

### Human Verification Required

None. All previously flagged items are now resolved by code and passing tests.

---

### Gaps Summary

No gaps. All 19 must-have truths are verified by code evidence and passing behavioral tests (19/19 VERIFIED). The two items previously flagged as human-needed are both resolved:

1. WR-04 follow-up (re-draft of reviewed unit): `_PROGRESS_ORDER` now includes `reviewed`; `_advance_progress` correctly branches on `current > drafted_rank` to emit a single clean `drafted` reset with no backward `sourced` walk. Test `test_redraft_of_reviewed_resets_to_drafted` asserts the exact invariant and passes.

2. WR-05 UX (review before draft): `review()` in `cli/main.py` now catches `FileNotFoundError` from `read_progress` separately and emits a specific "has not been drafted yet — run `dogen draft <id>` first" message at exit 2. Test `test_review_before_draft_says_draft_first` asserts both the exit code and the message and passes.

The SKEL-03 guard (`committed` never referenced in orchestrator as a `ProgressState` attribute) holds after the WR-04 fix: `committed` appears only in docstrings and comments; `_PROGRESS_ORDER` stops at `reviewed`; `test_orchestrator_never_writes_committed` confirms via AST walk.

The full suite (78 tests), import-linter contract, and Sphinx build (-W) all pass in this verification run.

---

_Verified: 2026-06-20T14:00:00Z_
_Verifier: Claude (gsd-verifier) — re-verification after gap closure_
