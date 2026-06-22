---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
plan: 04
subsystem: docs-toolchain-and-licensing
tags: [sphinx, myst, reuse, licensing, dogfood, ci, skel-02]
requires:
  - "02-02: the dogen CLI (unit new/steer/draft/review) + mock provider that produced the dogfood run"
  - "02-03: docs/seam.md (the design doc wired into the published toctree this plan)"
provides:
  - "Sphinx/MyST docs toolchain (docs/conf.py, docs/index.md, .readthedocs.yaml) proven by a real -W CI build"
  - "Resolved docs/content license (CC-BY-SA-4.0) + reconciled licensing.md system-of-record"
  - "First committed dogfood drafted page (docs/cli-reference.md) + its AC5 audit surface"
  - ".dogen/** REUSE.toml glob so the committed audit surface is reuse-lint-clean"
affects:
  - ".github/workflows/ci.yml (new Python-3.12-only docs job)"
  - ".planning/refs/licensing.md (docs license resolved across §1/§2/§3.5)"
  - "docs/seam.md (relicensed to CC-BY-SA-4.0 as published content)"
tech_stack_added:
  - "sphinx==9.1.0, myst-parser==5.1.0, furo (docs extra; already in pyproject)"
key_files_created:
  - docs/conf.py
  - docs/index.md
  - docs/index.md.license
  - docs/cli-reference.md
  - docs/cli-reference.md.license
  - docs/seam.md.license
  - .readthedocs.yaml
  - LICENSES/CC-BY-SA-4.0.txt
  - tests/test_docs_build.py
  - .dogen/units/cli-reference/unit.md
  - .dogen/units/cli-reference/provenance.yaml
  - .dogen/units/cli-reference/progress.yaml
key_files_modified:
  - .github/workflows/ci.yml
  - .planning/refs/licensing.md
  - REUSE.toml
  - .gitignore
  - docs/seam.md
decisions:
  - "D-44 resolved: drafted docs/content license = CC-BY-SA-4.0 (developer-selected)"
  - "docs/seam.md treatment: published content → CC-BY-SA-4.0 .license sidecar, inline GPL header stripped"
  - ".dogen/ git policy: committed (not gitignored) + REUSE.toml .dogen/** glob under GPL-3.0-only"
metrics:
  duration_min: 25
  tasks: 2
  files: 16
  completed: 2026-06-20
status: complete
---

# Phase 02 Plan 04: Sphinx/MyST Docs Toolchain, Docs License, and First Dogfood Draft Summary

Stood up the deferred (D-17) Sphinx/MyST documentation toolchain and proved
"Sphinx-publishable" (SKEL-02) with a real warnings-as-errors (`-W`) build wired
into CI — not asserted — then resolved the live D-44 docs/content-license
decision (CC-BY-SA-4.0), reconciled the `licensing.md` self-contradiction, and
committed the first dogfood drafted page about dogen's CLI together with its AC5
audit surface, all kept `reuse lint`-clean.

## What was built

### Task 1 — Sphinx/MyST toolchain, docs-build CI job, docs-license decision (commit `0d90d72`)

- **`docs/conf.py`** — `extensions = ["myst_parser"]` (Pitfall 6: without it the
  `.md` pages are not parsed as MyST and a `-W` build proves nothing),
  `myst_enable_extensions = ["colon_fence"]`, `source_suffix` for `.md`/`.rst`,
  `project = "dogen"`, `html_theme = "furo"`, `exclude_patterns = ["_build"]`.
  Full Canonical GPL header in `#` form.
- **`docs/index.md`** (+ `docs/index.md.license`, CC-BY-SA-4.0) — the docs root
  with a `:::{toctree}` (colon-fence) referencing the published pages so `-W`
  does not fail on an orphan.
- **`.readthedocs.yaml`** — `version: 2`, `build.os: ubuntu-24.04`,
  `tools.python: "3.12"`, install `.[docs]`, `sphinx.configuration: docs/conf.py`,
  `sphinx.fail_on_warning: true` (mirrors the CI `-W` gate).
- **`.github/workflows/ci.yml`** — added a **separate `docs` job**, Python **3.12
  only** (Sphinx 9.1 floor), checkout + `setup-uv` (both still SHA-pinned),
  `uv sync --frozen`, then `uv run --extra docs sphinx-build -W -b html docs
  docs/_build`. The existing `gates` job, its `["3.12","3.13"]` matrix, the
  SHA-pinned actions, and `permissions: contents: read` are **unchanged**.
- **`LICENSES/CC-BY-SA-4.0.txt`** — generated via `uvx reuse download
  CC-BY-SA-4.0` so the filename/content match REUSE's expectation.
- **`tests/test_docs_build.py`** — the publishability proof as a test: asserts
  `conf.py` has `myst_parser` + `colon_fence`, the index has a toctree, and runs
  a real `sphinx-build -W` (skipped only when `sphinx-build` is absent; CI runs
  it with `--extra docs`).
- **`.gitignore`** — added `docs/_build/` (generated HTML, not source); `.dogen/`
  is deliberately NOT ignored.

### Task 2 — First dogfood drafted page + AC5 audit surface (commit `2858671`)

- Ran the **real dogen loop** (`unit new → steer → draft --provider mock →
  review`) to produce the `.dogen/units/cli-reference/` audit surface. The mock
  emitted a placeholder draft; per the plan ("may be authored directly by the
  executor as the committed dogfood artifact"), the committed **`docs/cli-reference.md`**
  is an author-written reference page for the **real** CLI (`unit new`/`steer`/
  `draft`/`review`), grounded in `src/dogen/cli/main.py` — no invented
  commands/flags.
- **`docs/cli-reference.md.license`** — CC-BY-SA-4.0 sidecar; the prose body
  carries **no** inline SPDX (S2/D-44).
- Wired `cli-reference` into the `docs/index.md` toctree; extended
  `tests/test_docs_build.py` to assert the page is in the toctree and licensed
  via its sidecar.
- Committed the **`.dogen/units/cli-reference/`** audit surface (`unit.md`,
  `provenance.yaml`, `progress.yaml`) as the AC5 evidence (D-24) — the audit
  trail lives in git history, not gitignored.
- **`REUSE.toml`** — added a `.dogen/**` `[[annotations]]` glob,
  `precedence = "aggregate"`, `GPL-3.0-only` (tool-generated artifacts, same
  license as the code per licensing.md §1). The existing `.planning/**` /
  `.claude/**` entries are untouched.

## Checkpoint resolution (D-44)

The plan's first task is a blocking decision checkpoint (drafted docs/content
license). It was **pre-resolved by the developer to CC-BY-SA-4.0** and treated as
DONE — no re-prompt. Resulting edits:

- `licensing.md` **§1** row "Docs/content license" changed from *Deferred* to
  **`CC-BY-SA-4.0`** with rationale.
- `licensing.md` **§3.5** rewritten: the CC-BY-**NC**-SA example was replaced with
  the **CC-BY-SA-4.0** form and a note that the SPDX id is applied via a `.license`
  sidecar (no inline SPDX in published prose). §1, §2, and §3.5 now **all agree**
  on CC-BY-SA-4.0 — the CC-BY-SA vs CC-BY-NC-SA contradiction is gone.
- License applied to drafted pages via `.license` sidecars only.

## docs/seam.md license treatment (recorded)

`docs/seam.md` (from plan 03) carried an **inline GPL-3.0-only** HTML-comment
header. Because this plan wires it into the **published** Sphinx toctree, it was
treated as **published content**: the inline GPL header was **stripped** and a
**`docs/seam.md.license` (CC-BY-SA-4.0) sidecar** was added. One consistent
treatment — never both an inline GPL header and a CC-BY-SA sidecar on the same
file. `reuse lint-file docs/seam.md` passes.

## Verification

All run green:

- `uv run --extra docs sphinx-build -W -b html docs docs/_build` → **build
  succeeded** (SKEL-02 proven, not asserted; both `cli-reference` and `seam`
  pages built, no orphan warning).
- `uv run pytest -q` → **69 passed** (4 in `tests/test_docs_build.py`).
- `uv run ruff check .` → All checks passed.
- `uv run ruff format --check .` → 35 files already formatted.
- `uv run ty check` → All checks passed.
- `uv run lint-imports` → 1 kept, 0 broken (seam contract intact).
- Every new/modified file passes `uvx reuse lint-file` (verified individually,
  exit 0).

### Whole-repo `reuse lint` result (exact)

`uvx reuse lint` reports **`Invalid SPDX License Expressions: 4`**, ALL
pre-existing `.planning/` planning prose (the documented DEF-02-01/02 class —
SUMMARY/VERIFICATION files that *quote* an SPDX token in narrative, which REUSE's
parser misreads):

- `.planning/phases/01-.../01-VERIFICATION.md`
- `.planning/phases/02-.../02-01-SUMMARY.md`
- `.planning/phases/02-.../02-02-SUMMARY.md`
- `.planning/phases/02-.../deferred-items.md`

This count is **unchanged from the pre-execution baseline** — this plan added
**zero** new whole-repo reuse errors. The new `LICENSES/CC-BY-SA-4.0.txt`, the
drafted page + sidecar, the `docs/seam.md` treatment, and the committed
`.dogen/**` audit surface (covered by the new glob) are all clean. The remaining
4 are deferred per `<known_reuse_debt>` (do not rewrite GSD planning artifacts).
This 02-04-SUMMARY.md may itself add to that `.planning/`-only count when it
quotes SPDX tokens — same accepted, deferred class; it does not affect any
distributable file.

## Deviations from Plan

None affecting scope. Notes:

- The mock-provider draft (`docs/cli-reference.md` as first emitted) was a
  deterministic placeholder; the committed page was author-written per the plan's
  explicit allowance, while the live run's audit surface is preserved as AC5
  evidence. This is the intended dogfood shape, not a deviation.
- `reuse`/`sphinx-build` are invoked via `uvx` / `uv run --extra docs`
  respectively (not `uv run reuse`), matching how the CI/pre-commit gates already
  resolve `reuse` and how the docs extra is installed.

## Known Stubs

None. The drafted page documents the real CLI surface; no placeholder/empty data
flows to any output.

## Self-Check: PASSED

- Created files verified present: `docs/conf.py`, `docs/index.md`(+`.license`),
  `docs/cli-reference.md`(+`.license`), `docs/seam.md.license`, `.readthedocs.yaml`,
  `LICENSES/CC-BY-SA-4.0.txt`, `tests/test_docs_build.py`,
  `.dogen/units/cli-reference/{unit.md,provenance.yaml,progress.yaml}`.
- Commits verified in `git log`: `0d90d72` (Task 1), `2858671` (Task 2).
