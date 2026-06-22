# Deferred items — phase 03 (logged during 03-02 execution)

Out-of-scope discoveries logged per the execute-plan Scope Boundary rule. NOT fixed
by this plan.

## reuse lint (repo-wide) is non-compliant on out-of-scope files

`uvx reuse lint` (repo-wide) currently exits non-zero, but ONLY on files outside
this plan's surface. `uvx reuse lint-file` on every file 03-02 creates/changes
exits 0 (all carry the full GPL-3.0-only SPDX header).

Offending files (all pre-existing or scratch, none owned by 03-02):

- `temp/**` — untracked local scratch directory (`?? temp/`, 0 files tracked by
  git); missing SPDX headers. Not part of the package; should be removed or
  `.gitignore`d by the operator.
- `.planning/phases/03-live-copilot-path-runs-out-of-the-box/03-01-SUMMARY.md`
  — an "Invalid SPDX License Expression" reported against a prior plan's summary
  (CC-BY-SA-4.0 expression). Pre-existing artifact from plan 03-01.

Recommendation: gitignore `temp/`, and have the 03-01 summary's SPDX expression
corrected if `.planning/` is meant to be REUSE-clean. Neither blocks 03-02's
code, whose files are individually `reuse lint-file`-clean.
