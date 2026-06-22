---
status: complete
phase: 04-honest-observed-provenance
source: [04-VERIFICATION.md]
started: 2026-06-22T12:08:34Z
updated: 2026-06-22T13:20:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Live draft populates honest provenance (PROV-01 / PROV-02)
expected: After a successful `dogen draft --provider copilot` live run, the unit's `provenance.yaml` latest `generations[]` entry has non-empty `context_origins` (the `view`-read file paths, distinct from `sources`) and non-empty `tools_used` (`builtin:<name>` identifiers) — derived from observed `TOOL_EXECUTION_START` events, not fabricated. Confirms the live CLI emits `arguments["path"]` as the bundled-schema probe indicated (RESEARCH open question A1).
result: pass

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
