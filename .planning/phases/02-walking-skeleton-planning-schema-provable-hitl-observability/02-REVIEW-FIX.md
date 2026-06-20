---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
fixed_at: 2026-06-20T00:00:00Z
review_path: .planning/phases/02-walking-skeleton-planning-schema-provable-hitl-observability/02-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-06-20T00:00:00Z
**Source review:** .planning/phases/02-walking-skeleton-planning-schema-provable-hitl-observability/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (BLOCKER CR-01 + WARNINGS WR-01..WR-05; the 4 Info items were out of scope)
- Fixed: 6
- Skipped: 0

All in-scope findings were applied within the established hexagonal +
security patterns (full Canonical REUSE headers unchanged, numpy docstrings,
functions <=60 lines, no `typing.Any`, zero vendor imports in `core/`). The
full gate suite is green after every fix:

- `uv run pytest -q` -> 75 passed, 1 skipped
- `uv run lint-imports` -> 1 contract kept, 0 broken (core stays vendor/adapter-free)
- `uv run ruff check .` -> all checks passed
- `uv run ruff format --check .` -> all 35 files formatted
- `uv run ty check` -> all checks passed
- REUSE (`uvx reuse@6.2.0 lint`) -> Bad licenses: 0, Missing licenses: 0; exit 0.
  Pre-existing `.planning/*.md` SPDX-in-prose recommendations are unrelated to
  the changed source files.

## Fixed Issues

### CR-01 + WR-01: `write_draft` does not contain `sphinx_target`; `.planning/`-only guard leaves writes uncontained

**Files modified:** `src/dogen/adapters/planning_fs.py`, `src/dogen/core/models.py`, `tests/test_planning_fs.py`
**Commit:** 7b50702
**Applied fix:** These two findings share the same security boundary and the
same files, so they were applied as one atomic commit (documented here as the
combined fix). The fix:
- Resolves the draft target under a resolved `docs/` root and asserts positive
  containment — the target must be `docs/` itself or live beneath it — rejecting
  (not writing) any `sphinx_target` that escapes `docs/`, mirroring the
  `_reject_unsafe_unit_id` discipline (CR-01).
- Adds a `_assert_within_root` positive-containment helper and calls it from
  every write method (`scaffold_unit`, `write_draft`, `_write_yaml`), so the
  `.planning/` denylist is now defense-in-depth rather than the primary control
  (WR-01).
- Enforces the invariant once more at the schema boundary: a `Unit`
  `model_validator` rejects an empty, absolute, or `..`-bearing `sphinx_target`,
  consistent with how `SourceRef` validates its shape.
- Adds tests proving `../../../tmp/evil.md` is rejected at the write boundary,
  that a safe target writes under `docs/`, and that the schema rejects
  traversing targets (T-02.1-01).

### WR-02: `load_unit` ignores the directory `unit_id`, accepting a mismatched front-matter id

**Files modified:** `src/dogen/adapters/planning_fs.py`, `tests/test_planning_fs.py`
**Commit:** c24af29
**Applied fix:** `load_unit` now raises `ValueError` when the parsed
front-matter `unit_id` disagrees with the directory it was loaded from,
preventing a silently inconsistent audit record after a directory rename or a
hand-edited id (D-36/AC5). Added tests for both the mismatch (raises) and the
matching (accepts) cases.

### WR-03: `model_version` is populated with the model *name*, not a version

**Files modified:** `src/dogen/core/models.py`, `src/dogen/core/orchestrator.py`, `src/dogen/adapters/mock_provider.py`, `src/dogen/adapters/copilot/mapping.py`, `tests/test_copilot_mapping.py`, `tests/test_loop_mock_e2e.py`
**Commit:** 7238661
**Applied fix:** Added a distinct `model_version` field to `DraftResult`
(default sentinel `"unknown"`). It is mapped from the SDK event at the Copilot
seam (falling back to `"unknown"` when absent, kept distinct from the model
name) and from the fixed mock constant `_MOCK_MODEL_VERSION = "mock-1"` (which
already existed but was unused). The orchestrator now records
`result.model_version` instead of duplicating `result.model`, so the provenance
record no longer misrepresents a model name as a version. Tests assert the seam
maps a real version, records `"unknown"` when absent, and that the mock e2e
generation carries `model="mock-model"` with `model_version="mock-1"`.

### WR-04: `_advance_progress` re-stamps `drafted` history on every re-draft

**Files modified:** `src/dogen/core/orchestrator.py`, `tests/test_orchestrator_hitl.py`
**Commit:** bafdf3a
**Status:** fixed: requires human verification (lifecycle-ordering logic change)
**Applied fix:** Introduced a `_PROGRESS_ORDER` lifecycle tuple and drove
`_advance_progress` off it: only states strictly later than the current state
are stamped. A re-draft of an already-`drafted` unit no longer regresses
`drafted -> sourced -> drafted` nor appends spurious history entries (monotonic,
idempotent; D-38). Added a re-draft test asserting state stays `drafted` and no
extra transitions (and no backward `sourced`) are appended on the second draft.

### WR-05: `review` advances to `reviewed` and appends history unconditionally

**Files modified:** `src/dogen/cli/main.py`, `tests/test_loop_mock_e2e.py`
**Commit:** 3810096
**Status:** fixed: requires human verification (lifecycle-transition logic change)
**Applied fix:** The per-invocation `ReviewerEdit` append is retained (each
review note is a distinct, audit-relevant act), but the progress transition is
now idempotent: the `reviewed` state and history entry are stamped only when the
unit is not already `reviewed`, and `write_progress` is skipped otherwise.
Repeated `review` runs no longer dilute the lifecycle history with duplicate
`reviewed` transitions (D-38). Added a test asserting two `review` runs record
two reviewer edits but exactly one `reviewed` history entry.

## Skipped Issues

None — all in-scope findings were fixed.

The 4 Info findings (IN-01 `getattr`-with-defaults in mapping; IN-02 unnamespaced
`sphinx_target` default; IN-03 `git_identity` exit-code conflation; IN-04 OTel
private-state test hack) were out of scope (`fix_scope = critical_warning`) and
were intentionally not modified.

---

_Fixed: 2026-06-20T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
