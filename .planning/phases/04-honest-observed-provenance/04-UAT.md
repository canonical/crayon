---
status: testing
phase: 04-honest-observed-provenance
source: [04-VERIFICATION.md]
started: 2026-06-22T12:08:34Z
updated: 2026-06-22T12:08:34Z
---

## Current Test

number: 1
name: Live draft populates honest provenance (PROV-01 / PROV-02, D-24)
expected: |
  Run `dogen draft --provider copilot` against a real Copilot account on a unit
  with sources, then inspect the unit's generated `provenance.yaml`. In the latest
  `generations[]` entry: `context_origins` is non-empty and lists the file paths
  the agent actually read via the `view` tool; `tools_used` is non-empty and lists
  the `builtin:<name>` identifiers the agent invoked — both derived from observed
  live session events, kept distinct from the human-pointed `sources`.
awaiting: user response

## Tests

### 1. Live draft populates honest provenance (PROV-01 / PROV-02)
expected: After a successful `dogen draft --provider copilot` live run, the unit's `provenance.yaml` latest `generations[]` entry has non-empty `context_origins` (the `view`-read file paths, distinct from `sources`) and non-empty `tools_used` (`builtin:<name>` identifiers) — derived from observed `TOOL_EXECUTION_START` events, not fabricated. Confirms the live CLI emits `arguments["path"]` as the bundled-schema probe indicated (RESEARCH open question A1).
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
