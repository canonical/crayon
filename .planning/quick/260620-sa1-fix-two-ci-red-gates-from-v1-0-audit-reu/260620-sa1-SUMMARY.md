---
quick_id: 260620-sa1
description: "Fix two CI-red gates from v1.0 audit: REUSE-lint prose false-positives and ty test-double diagnostic"
date: 2026-06-20
status: complete
---

# Quick Task 260620-sa1 — Summary

Resolved the CI-red gates surfaced by the v1.0 milestone re-audit, plus a third
pre-existing red gate discovered while running the full gate suite.

## What changed

### Task 1 — REUSE-lint prose false-positives (docs housekeeping)
Wrapped the SPDX license-identifier tokens quoted in planning prose with inline
`REUSE-Ignore` HTML comments so the REUSE parser no longer misreads them as real
declarations. Files fixed:
- `01-VERIFICATION.md` (2 table cells — kept `|` delimiters outside the comments)
- `02-01-SUMMARY.md`, `02-02-SUMMARY.md`, `deferred-items.md` (inline span wraps)

While verifying, two **newly added** files (`01-LEARNINGS.md` from the same batch,
and this task's own `PLAN.md`) re-introduced the trigger — the Phase-1 learnings
doc had unbalanced ignore markers because it *documents* the technique with literal
marker strings, which corrupts marker pairing. Fixed by rewording the documenting
prose so the file's real body-wrap markers pair cleanly, and by dropping the literal
tag form from the PLAN prose.

Result: `uvx reuse lint` → compliant, **129/129 files**, 0 invalid expressions.

### Task 2 — `ty` test-double diagnostic
Redefined `_FailingDraftStore` in `tests/test_orchestrator_hitl.py` as a subclass of
the (stateless) `FilesystemPlanningStore`, overriding only `write_draft` to raise
`OSError("disk full")`. This makes it a genuine `PlanningStore`, so the
`# type: ignore[arg-type]` on `store=failing` was removed. Behaviour is identical
(all other store calls hit the real implementation against the same `tmp_path`).

Result: `uv run ty check` → All checks passed.

### Task 3 — ruff format (pre-existing, discovered this task)
Running the full CI gate suite revealed `ruff format --check` was already failing on
`tests/test_loop_mock_e2e.py` (a line-length reflow, unrelated to this task and
missed by both the prior audit and the re-audit, which only checked reuse + ty exit
codes). Applied `ruff format` to that one file.

## Verification — full CI gate suite, 8/8 green
`uvx reuse lint` · `ruff check` · `ruff format --check` · `ty check` ·
`scripts/seam_check.py` · `lint-imports` · `pytest` (97 passed) · `uv build` — all exit 0.

## Also committed in this batch (pre-existing working-tree artifacts)
- `.planning/v1.0-MILESTONE-AUDIT.md` — the milestone re-audit (with a post-audit
  update noting these gates are now green)
- `01-LEARNINGS.md`, `02-LEARNINGS.md` — extracted phase learnings
- `.planning/config.json` — prior working-tree change

## Notes / remaining debt (non-blocking, not CI-red)
- SKEL-02 is recorded only in `02-04-SUMMARY.md` tags, not a machine-readable
  requirements key (requirement itself is verified satisfied).
- Live-backend `JsonRpcError` mapping breadth on the manual-only Copilot path.
