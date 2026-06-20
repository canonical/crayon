---
phase: 02-walking-skeleton-planning-schema-provable-hitl-observability
plan: 01
subsystem: api
tags: [pydantic, typer, import-linter, pyyaml, opentelemetry, logfire, copilot-sdk, sphinx, myst, hexagonal, schema]

# Dependency graph
requires:
  - phase: 01-compliant-scaffold-provider-seam-boundary
    provides: hexagonal core/adapters/cli stubs, AST seam guardrail (scripts/seam_check.py), REUSE-compliant pyproject + CI + pre-commit, uv+hatchling layout
provides:
  - F1 planning-directory schema v0 as pure Pydantic v2 models (Unit, SourceRef, Steering, Generation, ReviewerEdit, VerificationStep, Verification, Provenance, ProgressEntry, Progress, DraftResult) with schema_version=0 and reserved-empty verification fields
  - DraftingProvider / SourceLookup / PlanningStore Protocol ports shaped by domain verbs (async drafting)
  - FilesystemPlanningStore over .dogen/units/<id>/ + docs/ with a tested front-matter splitter and a .planning/ write-guard
  - git-identity adapter (read_git_identity) behind an allowlisted, injectable git-config runner
  - thin Typer CLI with `dogen unit new <id>` and the `dogen` console entrypoint
  - declarative import-linter provider-seam contract (banning copilot/github_copilot_sdk/logfire/opentelemetry.sdk/adapters from core), wired into CI + pre-commit + a test, alongside the retained AST check
  - pinned runtime/docs/dev dependencies recorded in uv.lock
affects: [02-02 drafting loop, orchestrator, copilot adapter, mock provider, observability, steer/draft/review subcommands, sphinx docs build]

# Tech tracking
tech-stack:
  added: [github-copilot-sdk==1.0.2, typer 0.26.7, pydantic 2.13.4, opentelemetry-api 1.42.1, logfire 4.37.0, sphinx 9.1.0, myst-parser 5.1.0, furo 2025.12.19, import-linter 2.11, PyYAML 6.0.3]
  patterns: [Pydantic v2 schema with schema_version envelope, domain-verb Protocol ports, hexagonal zero-vendor-imports core, declarative import-linter seam contract belt-and-braces with AST check, allowlisted+injectable shell adapter, path-containment write guard, tested non-regex front-matter splitter]

key-files:
  created: [src/dogen/core/models.py, src/dogen/core/ports.py, src/dogen/adapters/planning_fs.py, src/dogen/adapters/git_identity.py, src/dogen/cli/main.py, tests/test_models.py, tests/test_planning_fs.py, tests/test_cli_unit_new.py, tests/test_seam_importlinter.py]
  modified: [pyproject.toml, uv.lock, .github/workflows/ci.yml, .pre-commit-config.yaml]

key-decisions:
  - "A4: dogen only creates unit.md (never rewrites operator-edited front-matter) this plan, so PyYAML is sufficient and ruamel.yaml was NOT added — revisit only if a later command rewrites unit.md"
  - "D-29 keep-both confirmed: import-linter is the primary declarative seam gate; scripts/seam_check.py AST check retained as belt-and-braces (RESEARCH Pitfall 4) — both run in CI + pre-commit and stay green"
  - "import-linter contract graphs `opentelemetry` as a second root_package so the forbidden set can name the `opentelemetry.sdk` subpackage specifically (import-linter forbids external subpackages only when their top-level is a graphed root); core may still use the OTel API"
  - "Effort/Intent/ProgressState modeled as enum.StrEnum (Python 3.12 floor) per ruff UP042"
  - "dogen unit new refuses to clobber an edited unit.md (UnitExistsError) unless --force; unit_id must be a single safe path segment (T-02.1-01)"

patterns-established:
  - "Schema envelope: every machine-readable model carries schema_version: int = 0 (D-34); reserved-but-empty fields (verification.steps, reviewer_edits) cost nothing now and avoid breaking migrations later (PLAN-07)"
  - "Distinct audit fields: Unit.sources (human-pointed) vs Generation.context_origins (agent-read) never collapse (D-37)"
  - "Seam gate single-sourced four ways: pyproject contract ↔ CI step ↔ pre-commit hook ↔ pytest subprocess test, mirroring the Phase-1 seam_check pattern"
  - "Host I/O adapters take an injectable runner so tests stub the boundary deterministically (no real git/network in tests)"

requirements-completed: [SKEL-01, PLAN-01, PLAN-02, PLAN-03, PLAN-07, SEAM-04]

# Metrics
duration: ~40min
completed: 2026-06-20
status: complete
---

# Phase 2 Plan 01: Walking-Skeleton Schema, Ports & Seam Upgrade Summary

**F1 planning-directory schema v0 (Pydantic v2 with schema_version + reserved verification fields), domain-verb ports, a filesystem PlanningStore behind `dogen unit new`, and the provider seam upgraded from the AST check to a declarative import-linter contract banning copilot/logfire/opentelemetry.sdk from core.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-06-20
- **Completed:** 2026-06-20
- **Tasks:** 3
- **Files modified:** 13 (9 created, 4 modified)

## Accomplishments
- F1 schema v0 as pure `core/` Pydantic v2 models: `schema_version: 0` on every machine model, reserved-empty `verification.steps`/`reviewer_edits`, distinct `sources`/`context_origins`, `Intent` = exactly the four Diátaxis directions, `Effort` includes `xhigh`, `committed` in the enum with no setter helper.
- Three domain-verb Protocol ports (`DraftingProvider` async, `SourceLookup`, `PlanningStore`) with zero vendor imports — the SEAM-04 design-only foundation.
- `FilesystemPlanningStore` over `.dogen/units/<id>/` + `docs/`, with a tested non-regex front-matter splitter (CRLF, embedded `---`, empty body) and an explicit guard refusing any write under `.planning/` (D-30).
- `git_identity.read_git_identity` behind an allowlisted, injectable git-config runner (D-41, coding-guide §5).
- Thin Typer CLI: `dogen unit new <id>` (with `--intent`/`--audience`/`--force`) and the `dogen` console entrypoint, verified end-to-end producing a `unit.md` that parses back into a `Unit`.
- Declarative `import-linter` seam contract wired into CI + pre-commit + a test, retaining the Phase-1 AST check as belt-and-braces (D-29 keep-both).

## Resolved dependency versions (uv.lock)

| Package | Resolved | Pin policy |
|---------|----------|------------|
| github-copilot-sdk | 1.0.2 | exact (coding-guide §2) |
| sphinx | 9.1.0 | exact |
| myst-parser | 5.1.0 | exact |
| typer | 0.26.7 | floor `>=0.26.7` |
| pydantic | 2.13.4 | floor `>=2` |
| opentelemetry-api | 1.42.1 | floor `>=1.42.1` |
| logfire | 4.37.0 | floor `>=4.37.0` |
| furo | 2025.12.19 | floor (docs extra) |
| import-linter | 2.11 | floor (dev) |
| PyYAML | 6.0.3 | transitive/installed |

All resolved versions match the RESEARCH-verified live PyPI pins. `uv sync --frozen` installs the committed lockfile cleanly.

## import-linter contract shape

```toml
[tool.importlinter]
root_packages = ["dogen", "opentelemetry"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "core stays vendor- and adapter-free (provider seam)"
type = "forbidden"
source_modules = ["dogen.core"]
forbidden_modules = ["copilot", "github_copilot_sdk", "logfire", "opentelemetry.sdk", "dogen.adapters"]
```

Injecting `import logfire`, `from opentelemetry import sdk`, `import copilot`, or `import dogen.adapters` into any `core/` module makes `lint-imports` exit nonzero (verified, then reverted).

## D-29 keep-both decision (visible record)

**KEEP BOTH** the declarative `import-linter` contract AND the Phase-1 AST `scripts/seam_check.py`. import-linter is the primary declarative gate; the AST check catches dynamic forms (`importlib.import_module` by string constant) that import-linter's static graph can miss, and the two are cheap to run together (RESEARCH Pitfall 4). `scripts/seam_check.py` and its three wirings (CI step, pre-commit hook, `tests/test_seam.py`) are **unchanged** — `seam_check: OK - 9 files` and its test stay green.

## A4 ruamel-vs-PyYAML decision (visible record)

This plan's `dogen unit new` only **creates** `unit.md`; no command rewrites operator-edited front-matter yet. Therefore **PyYAML is used and ruamel.yaml was not added** — comment/key-order preservation only matters when the tool round-trips a human-edited file. Revisit if a later command (e.g. a `status` updater that rewrites `unit.md`) is introduced.

## Task Commits

1. **Task 1: deps + import-linter seam upgrade** - `8953bce` (feat)
2. **Task 2: F1 v0 schema + domain ports** - `18483b3` (feat)
3. **Task 3: PlanningStore + git-identity + `dogen unit new`** - `1598075` (feat)

_TDD note: all three tasks were authored test-first (tests written alongside the implementation and run RED→GREEN); they landed as single feat commits per task since each behavior set and its implementation are inseparable for this skeleton._

## Files Created/Modified
- `src/dogen/core/models.py` - F1 v0 Pydantic schema + Intent/ProgressState/Effort StrEnums
- `src/dogen/core/ports.py` - DraftingProvider/SourceLookup/PlanningStore Protocols
- `src/dogen/adapters/planning_fs.py` - FilesystemPlanningStore + split_front_matter + .planning/ guard
- `src/dogen/adapters/git_identity.py` - allowlisted, injectable git-identity reader
- `src/dogen/cli/main.py` - thin Typer app, `unit new` subcommand
- `tests/test_models.py`, `tests/test_planning_fs.py`, `tests/test_cli_unit_new.py`, `tests/test_seam_importlinter.py` - behavior tests
- `pyproject.toml` - deps, `[project.scripts]`, `[tool.importlinter]`
- `uv.lock` - resolved/pinned deps
- `.github/workflows/ci.yml` - `uv run lint-imports` gate after the seam-check step
- `.pre-commit-config.yaml` - matching local `import-linter` hook

## Decisions Made
See `key-decisions` frontmatter. Notable runtime resolution: import-linter rejects forbidding an external subpackage (`opentelemetry.sdk`) unless its top-level package is graphed as a root, so `opentelemetry` was added to `root_packages` (this does not relax the seam — `core` may use the OTel *API* but the `.sdk` subpackage is forbidden).

## Deviations from Plan

None affecting scope. Two small, necessary adjustments handled inline:

### Auto-fixed Issues

**1. [Rule 3 - Blocking] import-linter config required `include_external_packages` and a second root package**
- **Found during:** Task 1
- **Issue:** `lint-imports` errored that external forbidden modules need `include_external_packages=True`, and separately that a subpackage of an external package (`opentelemetry.sdk`) cannot be forbidden unless its top-level is a graphed root.
- **Fix:** Added `include_external_packages = true` and `root_packages = ["dogen", "opentelemetry"]`. The contract now keeps and trips correctly on all four banned imports.
- **Files modified:** pyproject.toml
- **Verification:** `lint-imports` exits 0 clean; nonzero on each injected forbidden import.
- **Committed in:** 8953bce

**2. [Rule 1 - Bug] ty strictness on enum-typed constructor args in tests; ruff UP042 on `str, Enum`**
- **Found during:** Task 2
- **Issue:** `ty` flagged passing raw strings where `Intent`/`Effort`/`ProgressState` enums are statically expected (Pydantic coerces at runtime, but the type checker is strict); ruff UP042 preferred `StrEnum` over `str, Enum`.
- **Fix:** Switched the three enums to `enum.StrEnum` (3.12 floor) and passed enum members in the directly-constructed test cases (the `**dict` round-trip cases still exercise string coercion).
- **Files modified:** src/dogen/core/models.py, tests/test_models.py
- **Verification:** `ty check` and `ruff check` both pass.
- **Committed in:** 18483b3

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug/lint). **Impact:** both necessary for the gates to pass; no scope creep.

## Issues Encountered

- **`reuse lint` whole-repo false positive (out of scope, deferred).** `uvx reuse lint` reports one invalid SPDX expression in `.planning/phases/01-.../01-VERIFICATION.md` — a Phase-1 planning artifact whose prose places a bare license token after an <!-- REUSE-IgnoreStart -->`SPDX-License-Identifier:`<!-- REUSE-IgnoreEnd --> mention. This file was NOT touched by this plan. Every source/config file this plan created or modified passes `reuse lint-file`. Logged as DEF-02-01 in `deferred-items.md`. My own `deferred-items.md` was reworded to avoid introducing the same parser trigger, keeping the whole-repo count at the single pre-existing hit.

## User Setup Required
None - no external service configuration required. (The real Copilot SDK run is a later-plan manual smoke test, out of scope here.)

## Next Phase Readiness
- The on-disk F1 shape and the operator entry point exist, so plan 02 can run the full `steer → draft → review` loop against `.dogen/units/<id>/` and serialize provenance/progress through the same `PlanningStore`.
- The async `DraftingProvider` port is ready for both the real Copilot adapter and the deterministic mock.
- The seam is enforced declaratively; any vendor/backend import leaking into `core/` will fail CI and pre-commit.

## Self-Check: PASSED

All 9 created source/test files exist on disk; all 3 task commits (`8953bce`, `18483b3`, `1598075`) are present in git history.

---
*Phase: 02-walking-skeleton-planning-schema-provable-hitl-observability*
*Completed: 2026-06-20*
