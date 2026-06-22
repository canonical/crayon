---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
fixed_at: 2026-06-20T00:00:00Z
review_path: .planning/phases/02-walking-skeleton-planning-schema-provable-hitl-observability/02-REVIEW.md
iteration: 1
findings_in_scope: 11
fixed: 11
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-06-20T00:00:00Z
**Source review:** .planning/phases/02-walking-skeleton-planning-schema-provable-hitl-observability/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (fix scope: all)
- Fixed: 11
- Skipped: 0

All findings were fixed. Each fix carries a regression test where one was
missing (the review explicitly called out untested error paths for WR-01 and
honest-provenance for BL-01). The full suite grew from 77 to 88 passing tests
(1 skipped unchanged); `ruff check .`, `scripts/seam_check.py`, and the
import-linter seam contract (`tests/test_seam_importlinter.py`) all stay green,
and `core/` still carries zero vendor SDK imports.

Three findings touch domain logic (BL-01 provenance honesty, WR-03 side-effect
ordering, WR-04 / IN-03 lifecycle and effort semantics). Their behaviour is
pinned by new tests, but they are flagged below as `fixed: requires human
verification` so a developer confirms the semantics match intent before the
phase proceeds.

## Fixed Issues

### BL-01: `Generation.context_origins` / `tools_used` are fabricated, violating D-37

**Files modified:** `src/dogen/core/models.py`, `src/dogen/core/orchestrator.py`, `tests/test_orchestrator_hitl.py`
**Commit:** f3a1dba
**Status:** fixed: requires human verification (provenance-truth semantics)
**Applied fix:** Added `context_origins` and `tools_used` to `DraftResult`
(provider seam preserved — both default to empty, no vendor import added).
`_record_generation` now reads these from `result` instead of copying
`unit.sources`, and the unused `unit` parameter was dropped from that helper.
Until a provider can observe and report reads/tools, both record an honest
empty list rather than fabricated read context. Added two regression tests: one
asserting `context_origins`/`tools_used` stay empty for the mock even when the
unit declares a source (D-37), and one asserting a provider that *does* report
them is recorded verbatim.

### WR-01: `draft` CLI imports the Copilot SDK adapter on the mock error path (seam leak)

**Files modified:** `src/dogen/cli/main.py`, `tests/test_loop_mock_e2e.py`
**Commit:** 4197a54
**Status:** fixed
**Applied fix:** Removed the `except _backend_unavailable_error()` clause (whose
lazy import ran on every non-steering error) and the now-unused
`_backend_unavailable_error()` helper. Replaced with `except RuntimeError` that
classifies by `type(exc).__name__ == "BackendUnavailableError"` and re-raises
anything else — so the `--provider mock` path never imports `adapters/copilot/`.
Added a regression test driving a `ValueError` on the mock path and asserting
`dogen.adapters.copilot` / `...provider` are absent from `sys.modules` and the
exit code is the intended clean `2`.

### WR-02: `Unit.status` is documented as a progress mirror but is never updated

**Files modified:** `src/dogen/core/models.py`
**Commit:** 730dd54
**Status:** fixed
**Applied fix:** Took the reviewer's option (c), the lowest-risk path: changed
the `Unit` class docstring and the `status` field docstring to state the field
is "reserved; not yet maintained" and that `progress.yaml` is the sole source of
truth, so the schema no longer advertises a live-mirror guarantee it does not
keep. No data migration and no behavioural change.

### WR-03: Drafting writes draft + provenance + progress with no partial-failure handling

**Files modified:** `src/dogen/core/orchestrator.py`, `src/dogen/adapters/planning_fs.py`, `tests/test_orchestrator_hitl.py`
**Commit:** e37a828
**Status:** fixed: requires human verification (side-effect ordering)
**Applied fix:** Reordered `_run_draft` so the audit record is durable before
the draft is observable: `_record_generation` → `write_provenance` →
`_advance_progress` → `write_draft` (draft last). Added an
`_atomic_write_text` helper (temp-then-rename with `flush`/`fsync`/`os.replace`)
to `FilesystemPlanningStore` and routed both `_write_yaml` and `write_draft`
through it, so a torn write never leaves a half-serialized audit file. A crash
can now only leave an audit row with no draft (re-runnable), never a drafted
output with no recorded generation. Added a regression test that makes
`write_draft` raise and asserts provenance + progress are already on disk while
no `docs/u.md` exists.

### WR-04: `steer` can silently overwrite a prior steering event and invert the audit ordering

**Files modified:** `src/dogen/cli/main.py`, `tests/test_loop_mock_e2e.py`
**Commit:** 234d6d2
**Status:** fixed: requires human verification (HITL audit-ordering semantics)
**Applied fix:** `steer` now refuses to overwrite an existing steering event
unless `--force` / `--re-steer` is passed (mirroring the `unit new` clobber
guard), exiting `1` with a clear message naming the prior author/timestamp. An
explicit re-steer of an already-drafted unit is honoured but warns that existing
generations predate the new steering act. Added three regression tests: refusal
without the flag (original act untouched), overwrite with `--re-steer`, and the
warning when re-steering a drafted unit.

### WR-05: `mapping.to_draft_result` lets a `None` content crash instead of degrading

**Files modified:** `src/dogen/adapters/copilot/mapping.py`, `tests/test_copilot_mapping.py`
**Commit:** 892efae
**Status:** fixed
**Applied fix:** Changed `text = getattr(data, "content", "")` to
`getattr(data, "content", None) or ""`, matching how `model` and
`output_tokens` already coerce — so an explicit `content=None` on a truncated
stream degrades to an empty string instead of raising a Pydantic
`ValidationError` on the `str`-typed `DraftResult.text`. Added a regression test
asserting `content=None` maps to `text == ""`.

### WR-06: Unknown `--provider` raises `ValueError` outside the `draft` try-block

**Files modified:** `src/dogen/cli/main.py`, `tests/test_loop_mock_e2e.py`
**Commit:** ee86206
**Status:** fixed
**Applied fix:** Moved the entire `DraftRequest` construction (including
`select_provider(provider)`, which raises `ValueError` on an unknown name)
inside the `try:` block, so the existing `except (FileNotFoundError, ValueError)`
handler renders the clean exit-2 "Cannot draft … unknown provider" message
instead of an uncaught traceback. Added a regression test for
`--provider banana` asserting exit code 2 and the message text.

### IN-01: Committed dogfood provenance records a stale `model_version`

**Files modified:** `.dogen/units/cli-reference/provenance.yaml`
**Commit:** 90fbf48
**Status:** fixed
**Applied fix:** Corrected the committed dogfood generation's
`model_version: mock-model` to `mock-1`, matching the current mock provider
(`_MOCK_MODEL_VERSION = "mock-1"`). Validated the file still round-trips through
the `Provenance` model. (The record already carried the post-BL-01 empty
`context_origins`/`tools_used`, so only the version line needed correcting.)

### IN-02: `git config` reads omit `--get`, risking surprising values

**Files modified:** `src/dogen/adapters/git_identity.py`, `tests/test_planning_fs.py`
**Commit:** 5ff604b
**Status:** fixed
**Applied fix:** Changed the two allowlisted read vectors to the explicit
`["git", "config", "--get", "user.name"]` / `--get user.email` form, so a
multi-valued key behaves predictably for a field that becomes an immutable audit
author. Updated the test that asserts the exact issued argument vectors.

### IN-03: SDK reasoning effort and recorded provenance effort are two independent values

**Files modified:** `src/dogen/core/models.py`, `src/dogen/core/orchestrator.py`, `src/dogen/adapters/copilot/provider.py`, `tests/test_orchestrator_hitl.py`
**Commit:** d343155
**Status:** fixed: requires human verification (provenance effort semantics)
**Applied fix:** Added an optional `effort_used: Effort | None` to `DraftResult`.
The Copilot provider now reports the effort it actually ran at via
`result.model_copy(update={"effort_used": self._effort})`; the orchestrator
records `result.effort_used or request.effort`, making the provider's actual
effort the single source of truth and falling back to the requested effort only
when the provider reports none (the mock case). Added two regression tests:
provider-reported effort is recorded over the requested value, and the requested
effort stands when the provider reports none.

### IN-04: Un-flagged `draft` defaults to `copilot`, amplifying WR-01

**Files modified:** (none — addressed by WR-01)
**Commit:** 4197a54 (the WR-01 commit)
**Status:** fixed
**Applied fix:** The review states "No independent fix required beyond WR-01."
IN-04 is the blast-radius observation that the common `dogen draft UNIT` (no
`--provider`) defaults to `copilot` and therefore eagerly resolves the real SDK
adapter. That default is intentional and unchanged. With WR-01 fixed (the mock
*error* path no longer pulls `adapters/copilot/`), the amplification IN-04
described — a common command turning a clean domain error into an `ImportError`
on a host without the SDK — is neutralized. No separate code change was needed.

---

_Fixed: 2026-06-20T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
