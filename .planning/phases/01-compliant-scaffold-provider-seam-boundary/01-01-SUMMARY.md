---
phase: 01-compliant-scaffold-provider-seam-boundary
plan: 01
subsystem: licensing
status: complete
tags: [reuse, spdx, licensing, gpl-3.0-only, jinja2-template]
dependency_graph:
  requires: []
  provides:
    - "canonical REUSE annotation template (.reuse/templates/canonical.jinja2)"
    - "GPL-3.0-only license text (LICENSES/GPL-3.0-only.txt)"
    - "top-level LICENSE (Canonical policy D-05)"
  affects:
    - "plans 02-04 (every file they create is annotated with this template)"
tech_stack:
  added:
    - "reuse 6.2.0 (run via uvx, not a project dependency)"
  patterns:
    - "Per-file REUSE header via committed Jinja2 template (RESEARCH Pattern 1)"
    - "spdx copyright-prefix -> SPDX-FileCopyrightText form (no literal 'Copyright')"
    - ".license sidecar for the template file itself (avoids Jinja2 self-interpretation)"
key_files:
  created:
    - LICENSES/GPL-3.0-only.txt
    - LICENSE
    - .reuse/templates/canonical.jinja2
    - .reuse/templates/canonical.jinja2.license
  modified: []
decisions:
  - "License text fetched via reuse download (not hand-pasted) — canonical SPDX source"
  - "Template renders coding-guide section 7 byte-for-byte; verified via spdx-prefix smoke check"
  - "No REUSE.toml — per-file annotation policy (D-04) intact"
metrics:
  duration_min: 2
  completed_date: 2026-06-19
requirements: [LIC-01, LIC-02]
---
<!-- REUSE-IgnoreStart -->


# Phase 1 Plan 01: Licensing Foundation Summary

Established the REUSE annotation machinery for Phase 1: the canonical Jinja2 template that emits the full Canonical notice block (coding-guide section 7) byte-for-byte, the canonical SPDX GPL-3.0-only license text in LICENSES/, and the top-level LICENSE copy — the licensing foundation every subsequent Phase-1 file is born with.

## What Was Built

**Task 1 — License provisioning (commit 417fd33)**
- `LICENSES/GPL-3.0-only.txt` fetched via `uvx reuse download GPL-3.0-only` (canonical SPDX text, not hand-pasted — per RESEARCH "Don't Hand-Roll").
- Top-level `LICENSE` created as a copy of that text (Canonical policy D-05).
- Both are REUSE-special files: the license text and the top-level LICENSE do not require their own SPDX headers, so neither was annotated.
- No `REUSE.toml` created — per-file annotation policy (D-04) preserved.

**Task 2 — Canonical template (commit 8b03ea7)**
- `.reuse/templates/canonical.jinja2` reproduces coding-guide section 7 / licensing.md section 3.1: the "This file is part of dogen" identity line, the `copyright_lines` iteration, the `spdx_expressions` iteration emitting `SPDX-License-Identifier: GPL-3.0-only`, and the full three-paragraph GPL warranty-disclaimer block.
- `.reuse/templates/canonical.jinja2.license` sidecar annotates the template file itself, carrying `SPDX-FileCopyrightText: 2026 Canonical Ltd.` and `SPDX-License-Identifier: GPL-3.0-only` (sidecar avoids Jinja2 interpreting a header inside its own body).

## Verification Evidence

- Task 1 automated check passed: `LICENSES/GPL-3.0-only.txt` and `LICENSE` both non-empty; "GNU GENERAL PUBLIC LICENSE" and "Version 3" present; `test ! -e REUSE.toml` exits 0.
- Task 2 automated grep checks all passed (identity line, `copyright_lines`, `spdx_expressions`, warranty paragraph, both sidecar SPDX tags).
- **Render smoke check (Pitfall 1 defense):** annotating a throwaway temp `.py` with `--template canonical --copyright-prefix spdx` produced the full block — identity line + warranty paragraph — NOT the degraded two-line SPDX form.
- **Byte-for-byte:** `diff` of the rendered `#`-comment header against coding-guide section 7 (lines 103-118) showed zero differences.
- **Pitfall 2 defense:** rendered copyright tag is `SPDX-FileCopyrightText: 2026 Canonical Ltd.` with no literal "Copyright" word.
- **Lint gate:** with the annotated temp file present, `uvx reuse lint` reported `Bad licenses: 0`, `Deprecated licenses: 0`, and `Used licenses: GPL-3.0-only` — the LICENSES/ entry is recognized and "used" (Pitfall 5 cleared). The temp file was removed afterward.

> Note: the overall `reuse lint` run reports the repo as not-yet-compliant because `.planning/` and other pre-existing files have no headers — that annotation is the explicit scope of plans 02-04, not this plan. This plan's deliverable (the machinery + the bad-license/used-license gate for GPL-3.0-only) passes.

## Deviations from Plan

None — plan executed exactly as written. No bugs, missing functionality, or blocking issues encountered; no architectural decisions required.

## Threat Surface

No new security-relevant surface beyond the plan's threat model. The single trust boundary (upstream SPDX -> local repo via reuse) was crossed exactly once via `uvx reuse download`; content is public license text, verified by the grep assertion and the lint gate. No secrets, no executed fetched content.

## Requirements Satisfied

- **LIC-01** (partial — license-text portion): `LICENSES/` populated with the canonical GPL-3.0-only text; the annotation template that lets every file carry the SPDX header is in place. Full `reuse lint` CI pass is completed across plans 02-04.
- **LIC-02** (SPDX-identifier source): the `GPL-3.0-only` identifier is the single source the template and (plan 02) `pyproject.toml` metadata consume.

## Handoff to Next Plans

Plans 02 and 03 can now stamp every file they create with:
```
uvx reuse annotate --copyright "Canonical Ltd." --year 2026 \
  --license GPL-3.0-only --copyright-prefix spdx --template canonical <file>
```

## Self-Check: PASSED

- Files: all 4 present (LICENSES/GPL-3.0-only.txt, LICENSE, .reuse/templates/canonical.jinja2, .reuse/templates/canonical.jinja2.license).
- Commits: 417fd33 (Task 1), 8b03ea7 (Task 2) both present in git log.
<!-- REUSE-IgnoreEnd -->
