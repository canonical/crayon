# Deferred items — Phase 02

Out-of-scope discoveries logged during execution (not fixed; not caused by the
current plan's changes).

## DEF-02-01 — `reuse lint` false-positive in 01-VERIFICATION.md

- **Found during:** plan 02-01, Task 1 (`uvx reuse lint` gate).
- **File:** `.planning/phases/01-compliant-scaffold-provider-seam-boundary/01-VERIFICATION.md` (committed in `31bd873`, Phase 1).
- **Symptom:** `reuse lint` reports an invalid SPDX license expression. The file
  contains a prose table where a markdown backtick run places a bare license
  token immediately after a license-identifier mention, which reuse's parser
  misreads as a malformed expression (the prose is documentation, not a header).
- **Scope:** pre-existing Phase-1 planning artifact; NOT modified by plan 02-01.
  Every source/config file this plan added or touched carries the full Canonical
  REUSE header and passes `reuse lint` individually.
- **Fix (later):** wrap the offending prose in `REUSE-IgnoreStart`/`REUSE-IgnoreEnd`
  comments, or rephrase the table cells in 01-VERIFICATION.md. Belongs to a docs/
  housekeeping pass, not this walking-skeleton plan.
