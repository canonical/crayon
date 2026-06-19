# Phase 1: Compliant Scaffold & Provider-Seam Boundary - Research

**Researched:** 2026-06-19
**Domain:** Python package scaffolding · REUSE/SPDX licensing · provider-seam (hexagonal) boundary enforcement · uv/hatchling packaging · ruff/ty/pytest quality gates · GitHub Actions + pre-commit CI
**Confidence:** HIGH (all five planning-blocking mechanics empirically verified against the installed tools in this session: `reuse 6.2.0`, `uv 0.11.21`, `ruff 0.15.17`, `ty 0.0.51`, `hatchling`, `pre-commit 4.5.1`)

## Summary

Every Phase-1 deliverable is mechanically provable today, and I proved the load-bearing ones live in this session rather than relying on training knowledge:

1. **REUSE compliance is fully achievable with the exact coding-guide §7 header.** `reuse 6.2.0` (REUSE spec 3.3) passes lint when a top-level `LICENSE` sits alongside `LICENSES/GPL-3.0-only.txt` — the top-level `LICENSE` is treated specially and does **not** need its own SPDX header (D-05 confirmed, empirically). The exact Canonical notice block (D-04 / coding-guide §7, including `SPDX-FileCopyrightText: 2026 Canonical Ltd.` with no "Copyright" word) is produced byte-for-byte by `reuse annotate --copyright-prefix spdx --template canonical` with a custom Jinja2 template — and that header passes lint. Files that can't carry comments (lockfiles, binaries, license text) get `.license` sidecars via `--force-dot-license`/`--fallback-dot-license`, keeping the per-file (not `REUSE.toml`-bulk) policy intact.

2. **The AST seam guardrail works and resists evasion.** A ~40-line `ast`-based check walking `src/dogen/` (excluding `adapters/copilot/`) catches `import copilot`, `import copilot as c`, `import github_copilot_sdk`, `from copilot import …`, `from copilot.session import …`, and `importlib.import_module("copilot")` — all six forms, verified live, exit 0 clean / exit 1 on violation. No SDK install needed (D-08/D-09 hold).

3. **PEP 639 SPDX metadata is real in the installed toolchain.** `license = "GPL-3.0-only"` + `license-files = ["LICENSE", "LICENSES/*.txt"]` in `pyproject.toml` makes hatchling/uv emit `Metadata-Version: 2.4`, `License-Expression: GPL-3.0-only`, and `License-File:` entries in the built wheel METADATA — satisfying LIC-02 / SC2 directly (verified by building and unzipping the wheel).

4. **`ty` is beta, not GA.** `ty 0.0.51` runs and is the Handbook-mandated checker (D-14), but Astral's own guidance is "don't remove your other type checker from CI until ty's stable release" (targeted 2026). This is the one finding that tensions a locked decision — surfaced below, with a recommended `--exit-zero`-free hard-gate posture plus a documented fallback.

**Primary recommendation:** Scaffold src-layout `dogen` with uv+hatchling, provision REUSE via a committed `.reuse/templates/canonical.jinja2` + `reuse download GPL-3.0-only`, enforce the seam with a pure-stdlib `ast` check wired as both a pytest test and a CI/pre-commit step, and run all commit-1 gates (`reuse lint` → `ruff check`+`format --check` → `ty check` → seam check → `pytest`) on a 3.12+3.13 matrix via `astral-sh/setup-uv`. Treat `ty` as a hard gate but pin its version and keep the upgrade behind a smoke test.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Licensing & REUSE**
- **D-01** — OSS license = `GPL-3.0-only` (the `-only` SPDX variant, per Canonical policy "not 'v3 or later'"; `dogen` is a tool/app → policy's "everything else" → GPLv3). Non-default would need CEO approval.
- **D-02** — Copyright = `Canonical Ltd.`; year = year of first publication = `2026`.
- **D-03** — License granularity = single license now. No separate content/docs license at Phase 1 (deferred to when real prose/docs land; policy default CC-BY-SA-4.0, confirm against the policy's CC-BY-NC-SA-4.0 inconsistency first).
- **D-04** — REUSE annotation = per-file **full Canonical notice block** (program name + one-line description, copyright, `SPDX-License-Identifier: GPL-3.0-only`, GPL warranty-disclaimer paragraph) — **not** `REUSE.toml` bulk mapping. Use `SPDX-FileCopyrightText: 2026 Canonical Ltd.` (not a bare `Copyright` line). Exact header is coding-guide §7.
- **D-05** — License text in `LICENSES/GPL-3.0-only.txt` (REUSE requirement) **plus** a top-level `LICENSE` (policy). `reuse lint` gates CI (LIC-01); SPDX identifier in package metadata satisfies LIC-02 / SC2.
- **D-06** — CONTRIBUTING references the Canonical CLA; CLA-contributed files use the "License granted by Canonical Limited" notice variant (relevant for future external contributions, not commit-1 code).

**Provider seam & enforcement**
- **D-07** — Hot-swap = design property, not runtime machinery. Clean inward-only boundary + a single Copilot adapter. No runtime/config provider-selection in Phase 1. `DraftingProvider` port + mock-provider proof are Phase 2 (SEAM-03/04). Plugin discovery = v2.
- **D-08** — Phase-1 adapter depth = **empty boundary**. `adapters/copilot/` exists as the designated sole-importer shape but takes **no `github-copilot-sdk` dependency yet**. Keeps CI fast and free of issue #1606 fragility. Real SDK lands in Phase 2 (SKEL-05).
- **D-09** — Seam enforcement = **static AST-based check** (no SDK install needed) flagging any `copilot` / `github_copilot_sdk` import outside `adapters/copilot/`. AST (not regex) to resist aliasing/evasion. Runs on every CI build (SEAM-02 / SC4). `import-linter` is the named Phase-2 upgrade.
- **D-10** — Guardrail proof (SC4) = **one-time manual demo**: deliberately misplace an import, observe the check fail, capture the log as AC evidence. The AST check is the standing CI protection. *Trade-off accepted:* no committed negative-test fixture.

**Packaging & project identity**
- **D-11** — Package name = `dogen` (distribution + import name; `src/dogen/` layout). Verify PyPI-name availability before first publish (publishing is well out of v1 scope).
- **D-12** — Toolchain = uv + hatchling + src layout. `requires-python = ">=3.12"`. CI matrix on 3.12 + 3.13 (cheap forward-compat insurance).

**CI & quality gates**
- **D-13** — CI = GitHub Actions. Commit-1 gates run together: `reuse lint` + `ruff` (lint + format) + `ty` (type) + seam AST check + `pytest` (smoke/import). A `pre-commit` config mirrors the gates for local DX.
- **D-14** — Type checker = `ty` (Astral), per the Handbook's mandated Python toolchain (refines the earlier mypy/pyright assumption).
- **D-15** — Coding standards = follow `.planning/refs/coding-guide.md` (binding). `AGENTS.md` is the agent operating contract; synthetic code carries provenance per `.planning/refs/synthetic-code-provenance.md`.

**Repo hygiene**
- **D-16** — Standard OSS file set at commit 1, Canonical conventions: README, CONTRIBUTING (with CLA), SECURITY.md, CODE_OF_CONDUCT, `.editorconfig`, `.gitignore`. `AGENTS.md` already created.

**Docs toolchain**
- **D-17** — Sphinx/MyST + RTD toolchain deferred **entirely** to Phase 2. Do not stand up `conf.py`/`.readthedocs.yaml` now.

**Dependency management**
- **D-18** — Commit `uv.lock` from commit 1. Dependency-update bot (Renovate/Dependabot) deferred to Phase 2.

**Process**
- **D-19** — Trunk-based development. `main` default + stable. Feature branches ~one pulse, `docpr-<ticket>-<objective>` (kebab-case). Squash-merge, delete on merge, small PRs. Two maintainer reviews; reviewers run the change locally.

### Claude's Discretion
- Exact `ruff` ruleset selection and `ty` strictness flags (within coding-guide constraints).
- The `pytest`/`tests/` layout.
- The sub-layout inside `src/dogen/` (`core/`, `adapters/copilot/`, `cli/`) per ARCHITECTURE.md.
- Exact wording/structure of README, SECURITY.md, CODE_OF_CONDUCT (follow Canonical conventions).

### Deferred Ideas (OUT OF SCOPE)
- Runtime/config provider selection + `DraftingProvider` port + mock-provider swap proof → Phase 2 (SEAM-03/04).
- Real `github-copilot-sdk` dependency + pinned Copilot CLI + drafting-loop smoke test → Phase 2 (SKEL-05).
- `import-linter` upgrade for seam enforcement → Phase 2.
- Committed negative-test fixture for the seam guardrail → optional future hardening.
- Docs/content license (CC-BY-SA-4.0 candidate) → when first docs land (Phase 2).
- Sphinx/MyST + RTD docs toolchain → Phase 2.
- Dependency-update bot (Renovate/Dependabot) → Phase 2.
- Third-party plugin/entry-point provider discovery → v2 / non-goal.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **SEAM-01** | The GitHub Copilot SDK is imported in exactly one adapter module; the domain core has zero vendor imports | Hexagonal src-layout (`src/dogen/{core,adapters/copilot,cli}`) from ARCHITECTURE.md. `adapters/copilot/` is the designated sole importer but stays **empty** of the real SDK in Phase 1 (D-08). The "Architecture Patterns" section gives the layout + the standing invariant from coding-guide §6. |
| **SEAM-02** | A CI guardrail fails the build if any Copilot SDK import appears outside the adapter module | Verified `ast`-based check (see "Pattern 2" + "Code Examples"). Catches all six import/evasion forms live; exit 1 on violation. Wired as pytest test + CI step + pre-commit hook. SC4 proof = one-time manual demo (D-10). |
| **LIC-01** | REUSE-compliant — every file carries SPDX license + copyright, `LICENSES/` populated, `reuse lint` passes in CI | `reuse 6.2.0` verified: `reuse download GPL-3.0-only`, the `.reuse/templates/canonical.jinja2` template reproduces coding-guide §7 exactly and passes lint, `.license` sidecars for non-commentable files, top-level `LICENSE` + `LICENSES/` both pass. Full per-file-type enumeration in "Don't Hand-Roll" + "Code Examples". |
| **LIC-02** | A license for the distributable core is chosen, applied, recorded as an SPDX identifier | `GPL-3.0-only` (D-01). PEP 639 `license = "GPL-3.0-only"` + `license-files` verified to emit `License-Expression: GPL-3.0-only` in the built wheel METADATA (Metadata-Version 2.4). See "Packaging + SPDX Metadata". |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives carry the same authority as locked decisions; the planner must not contradict them:

- **GitHub work via `gh` CLI** — any PR/issue/CI/release/repo-metadata task uses `gh` (with `--json` when parsing), never git remotes, web UI, or curl. (User global instruction + project convention.) Relevant to the GitHub Actions/CI tasks and any future PR steps.
- **Never add `Co-Authored-By: Claude` trailers** — strip any auto-suggested attribution trailer from commits, PR bodies, and all git artifacts. The user authors these commits.
- **GSD workflow enforcement** — file-changing work routes through a GSD command (this phase's execution is `/gsd-execute-phase`). Not a code constraint, but governs how plans run.
- The project `CLAUDE.md` "Technology Stack" section documents the Copilot SDK / Sphinx stack at length — **note that almost all of it is Phase-2 scope** (D-08, D-17). Phase 1 touches only: Python 3.12+, uv, hatchling, ruff, ty, pytest, pre-commit, reuse. Do not let the CLAUDE.md stack table pull SDK/Sphinx work into Phase 1.

## Architectural Responsibility Map

`dogen` is a **CLI library** — there is no web/server/browser/CDN/DB tier (explicitly stated in scope guardrails). Tiers below are reframed to the package's internal hexagonal layers, which is what "tier ownership" means here.

| Capability | Primary Layer | Secondary Layer | Rationale |
|------------|---------------|-----------------|-----------|
| Domain models / orchestration logic (future) | `src/dogen/core/` (pure) | — | Zero vendor imports; depends only on `Protocol` ports it defines (coding-guide §6). Phase 1 may leave this near-empty (a package marker + maybe a `__about__`/version). |
| Copilot SDK integration (future) | `src/dogen/adapters/copilot/` | — | The single sanctioned vendor-import site (SEAM-01). **Empty boundary in Phase 1** (D-08) — exists as the shape, no SDK dep. |
| CLI entrypoint (future) | `src/dogen/cli/` | core | Thin driving adapter; Typer is the Phase-2 choice. Phase 1 may stub a console-script target or omit it (Claude's discretion). |
| Seam enforcement | repo-level tooling (`scripts/` or `tests/`) | CI + pre-commit | A build/test concern, not domain code. Pure stdlib `ast`; no runtime coupling to the package. |
| Licensing/SPDX headers | every file + `.reuse/`, `LICENSES/`, `LICENSE` | CI (`reuse lint`) | Cross-cutting; a per-file obligation plus repo-root license artifacts. |
| Packaging / metadata | `pyproject.toml` (hatchling) | uv (`uv.lock`, build) | Declares the SPDX expression (LIC-02) and the src-layout. |
| Quality gates | `pyproject.toml` tool config + CI workflow + `.pre-commit-config.yaml` | — | ruff/ty/pytest config co-located in `pyproject.toml`; orchestrated by GitHub Actions and pre-commit. |

**Why this matters:** the one assignment that must not slip is the seam — the AST check and the `adapters/copilot/` boundary are the entire point of the phase. Everything else is conventional Python packaging. There is no risk of mis-tiering auth/data/rendering because none of those tiers exist.

## Standard Stack

All versions below were verified live in this session (`--version` on the installed binary and/or the PyPI JSON API on 2026-06-19).

### Core
| Tool | Version (verified) | Purpose | Why Standard |
|------|--------------------|---------|--------------|
| **Python** | 3.12.3 installed; target `>=3.12` | Implementation language | D-12; floor set by future Sphinx 9.x (Phase 2) and is non-breaking to tighten later only if no users — so set 3.12 now. `[VERIFIED: python3 --version]` |
| **uv** | 0.11.21 | Env, dependency resolution, lockfile, build, publish driver | 2026 golden path; one tool for venv+resolve+build+publish; reproducible `uv.lock`. `[VERIFIED: uv --version]` |
| **hatchling** | latest (build backend) | `[build-system]` backend | 2026 default; PEP 621/639-compliant; clean with uv + src-layout. PEP 639 `License-Expression` emission verified. `[VERIFIED: uv build of a sample package]` |
| **reuse** | 6.2.0 (REUSE spec 3.3) | SPDX/REUSE compliance: `download`, `annotate`, `lint` | The REUSE reference implementation (FSFE). `[VERIFIED: uvx reuse --version; PyPI JSON]` |
| **ruff** | 0.15.17 local / 0.15.18 latest | Lint + format | 2026 default; replaces black+isort+flake8. `[VERIFIED: ruff --version; PyPI JSON]` |
| **ty** | 0.0.51 | Type checker (Astral) | Handbook-mandated (D-14). **BETA — see caveat in State of the Art / Open Questions.** `[VERIFIED: ty --version; PyPI JSON; WebSearch on release status]` |
| **pytest** (+ pytest-asyncio) | latest | Test harness (smoke/import + seam test) | Stand up from commit 1 (coding-guide §4). `pytest-asyncio` is for the Phase-2 async loop — optional in Phase 1. `[VERIFIED: PyPI JSON]` |
| **pre-commit** | 4.5.1 | Local gate mirror | Mirrors CI gates for DX (D-13). `[VERIFIED: pre-commit --version]` |

### Supporting
| Tool / Action | Version | Purpose | When to Use |
|---------------|---------|---------|-------------|
| **`astral-sh/setup-uv`** (GitHub Action) | latest (`@v6` family; pin a tag) | Install uv + Python in CI, with caching | The CI install step (D-13). `[VERIFIED: repo exists, HTTP 200]` |
| **`fsfe/reuse-tool`** pre-commit hook | `rev: v6.2.0`, `id: reuse` (or `reuse-lint-file`) | Run `reuse lint` on commit | The pre-commit REUSE gate. `[CITED: github.com/fsfe/reuse-tool/.pre-commit-hooks.yaml]` |
| **uvx** | 0.11.21 (bundled with uv) | Run `reuse` without adding it as a project dep | Keeps `reuse` out of `dogen`'s runtime/dev deps; CI runs `uvx reuse lint`. `[VERIFIED: uvx --version]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `uvx reuse lint` (CI) | `fsfe/reuse-action` GitHub Action | The action is one fewer moving part in the YAML, but it pins REUSE separately from local dev (drift risk) and adds a Docker pull. **Recommend `uvx reuse lint`** so CI and local dev run the *same* `reuse` version resolved the same way, and pre-commit uses the matching `rev`. Keeps a single source of truth for the REUSE version. |
| `ty` (beta) | mypy or pyright (mature) | Handbook **mandates** `ty` (D-14), so it is the gate. But because `ty` is beta, the planner should pin `ty`'s exact version and gate upgrades behind the smoke suite. Do **not** silently swap to mypy — that contradicts D-14. See Open Questions for the documented fallback posture. |
| Custom AST script | `import-linter` | `import-linter` needs the SDK to be an installable dependency to express a "forbidden" contract cleanly, and Phase 1 deliberately has **no SDK dep** (D-08). The custom AST check needs zero dependencies. `import-linter` is the named Phase-2 upgrade (D-09). |
| src-layout | flat layout | src-layout prevents accidental imports of the un-built package and is the uv/hatchling 2026 default; D-12 fixes it. |

**Installation (scaffold bootstrap):**
```bash
# uv drives everything; reuse runs via uvx (not a project dep)
uv init --lib --package dogen          # creates src/dogen/ + pyproject.toml (then edit to taste)
uv add --dev ruff ty pytest pytest-asyncio pre-commit
uvx reuse download GPL-3.0-only        # populates LICENSES/GPL-3.0-only.txt
uv lock                                 # commit uv.lock (D-18)
```

**Version verification (run at execution time — versions move):**
```bash
uv --version           # expect >= 0.11.21
ruff --version         # expect >= 0.15.17
ty --version           # expect >= 0.0.51 (BETA)
uvx reuse --version    # expect 6.2.0 (REUSE spec 3.3)
pre-commit --version   # expect >= 4.5.1
```

## Package Legitimacy Audit

Ran `gsd-tools query package-legitimacy check --ecosystem pypi reuse ruff ty pytest pytest-asyncio hatchling pre-commit`. **Every package returned `SUS`, but every verdict is a false positive** driven solely by `unknown-downloads` (the seam's download-count source returned null) and `too-new` (these tools republish frequently; e.g. ruff/pytest were re-published within the last day). I independently verified each against PyPI's JSON API and its official source repo, and ran `uv`, `ruff`, `ty`, `reuse`, and `pre-commit` live. These are among the most-downloaded packages in the Python ecosystem.

| Package | Registry | Published (verified) | Source Repo | Seam Verdict | Disposition |
|---------|----------|----------------------|-------------|--------------|-------------|
| `reuse` | PyPI | 2025-10-27 (6.2.0) | reuse.software / codeberg.org/fsfe/reuse-tool | SUS (unknown-downloads) | **Approved** — FSFE reference tool, ran live |
| `ruff` | PyPI | 2026-06-18 (0.15.18) | docs.astral.sh/ruff (astral-sh) | SUS (too-new, unknown-downloads) | **Approved** — Astral, ran live |
| `ty` | PyPI | 2026-06-19 (0.0.51) | github.com/astral-sh/ty | SUS (too-new, unknown-downloads) | **Approved** — Astral, ran live; **beta maturity flagged separately (not a legitimacy issue)** |
| `pytest` | PyPI | 2026-06-19 | github.com/pytest-dev/pytest | SUS (too-new, unknown-downloads) | **Approved** — pytest-dev |
| `pytest-asyncio` | PyPI | 2026-05-26 | github.com/pytest-dev/pytest-asyncio | SUS (unknown-downloads) | **Approved** — pytest-dev |
| `hatchling` | PyPI | — | github.com/pypa/hatch | SUS | **Approved** — PyPA; ran a real build with it |
| `pre-commit` | PyPI | — | github.com/pre-commit/pre-commit | SUS | **Approved** — ran live |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS] requiring a human-verify checkpoint:** none — all SUS verdicts are download-count/recency false positives on canonical tooling, each independently verified against its official source and executed live. No `checkpoint:human-verify` task is warranted for these.

> Note: no `github-copilot-sdk` legitimacy check is needed in Phase 1 — D-08 takes **no** SDK dependency. That audit belongs to Phase 2 (SKEL-05).

## Architecture Patterns

### System Architecture (Phase-1 scope)

This phase pours structure, not behaviour. The "data flow" is the **build/CI gate flow**, plus the static package boundary the seam check protects.

```
  Developer edit / git commit
        │
        ▼
  ┌─────────────────────── pre-commit (local) ───────────────────────┐
  │  reuse lint → ruff check → ruff format --check → ty check →       │
  │  seam-check (ast) → pytest -q                                     │
  └──────────────────────────────────────────────────────────────────┘
        │ push / PR
        ▼
  ┌──────────────── GitHub Actions (astral-sh/setup-uv) ─────────────┐
  │  matrix: python 3.12, 3.13                                        │
  │   1. uvx reuse lint           ── LIC-01 gate                      │
  │   2. ruff check .                                                 │
  │   3. ruff format --check .                                        │
  │   4. ty check                 ── D-14 (beta, hard gate)           │
  │   5. python -m seam_check     ── SEAM-02 gate (exit 1 = fail)     │
  │   6. pytest -q                ── smoke/import + seam test         │
  │   7. uv build                 ── proves wheel metadata (LIC-02)   │
  └──────────────────────────────────────────────────────────────────┘

  Static package boundary the seam check enforces:

    src/dogen/
      core/        ──┐  zero vendor imports (Protocol ports only)
      cli/         ──┤  may import core; never copilot
                     │  ▲  seam-check walks these, flags `copilot`/
                     │  │  `github_copilot_sdk` imports → BUILD FAIL
      adapters/      │  │
        copilot/   ◄─┘  the ONLY sanctioned import site
                        (EMPTY in Phase 1 — D-08, no SDK dep)
```

### Recommended Project Structure

Per ARCHITECTURE.md (hexagonal) and D-11/D-12 (src-layout, name `dogen`). Sub-layout is Claude's discretion; this is the recommended shape:

```
dogen/                              # repo root
├── .github/workflows/ci.yml        # GitHub Actions (D-13)
├── .reuse/
│   └── templates/
│       └── canonical.jinja2        # the full Canonical notice block (drives `reuse annotate`)
├── LICENSES/
│   └── GPL-3.0-only.txt            # from `reuse download` (REUSE requirement, D-05)
├── LICENSE                          # top-level copy (Canonical policy, D-05) — no SPDX header needed
├── src/
│   └── dogen/
│       ├── __init__.py             # package marker (+ maybe __version__); full header
│       ├── core/
│       │   └── __init__.py         # pure domain home — near-empty in Phase 1
│       ├── adapters/
│       │   └── copilot/
│       │       └── __init__.py     # the seam boundary — EMPTY of SDK (D-08)
│       └── cli/
│           └── __init__.py         # thin CLI home — stub or omit (discretion)
├── tests/
│   ├── __init__.py
│   ├── test_smoke.py               # imports dogen, asserts package importable
│   └── test_seam.py                # invokes the AST seam check; fails on violation
├── scripts/
│   └── seam_check.py               # the runnable AST guardrail (stdlib only)
├── pyproject.toml                  # hatchling + PEP 639 license + ruff/ty/pytest config
├── uv.lock                         # committed from commit 1 (D-18)
├── .pre-commit-config.yaml         # mirrors CI gates (D-13)
├── .editorconfig                   # (D-16) — .license sidecar (can't carry a comment cleanly → use .license)
├── .gitignore                      # (D-16) — needs a .license sidecar OR an editorconfig-style comment
├── README.md                       # (D-16)
├── CONTRIBUTING.md                 # (D-16) — references Canonical CLA (D-06)
├── SECURITY.md                     # (D-16)
├── CODE_OF_CONDUCT.md              # (D-16)
└── AGENTS.md                       # already exists
```

> **Single-source-the seam check:** put the real logic in `scripts/seam_check.py` and have `tests/test_seam.py` import and call it, so CI/pre-commit and the test suite run the *same* code (no drift between "the test" and "the CI step"). This is the recommended resolution of the D-13 "both a pytest test and a CI step" requirement.

### Pattern 1: Per-file REUSE header via a committed Jinja2 template

**What:** A custom `reuse` template at `.reuse/templates/canonical.jinja2` reproduces the coding-guide §7 block exactly. `reuse annotate --template canonical --copyright-prefix spdx` applies it.
**When to use:** Every new commentable source file (`.py`, `.toml`, `.yaml`, `.cfg`, `.editorconfig`).
**Why a template:** the default `reuse annotate` emits only the two-line SPDX tags; the Canonical policy (D-04) requires the full notice block (program description + GPL warranty paragraph). The template is the only way to get that block *and* pass lint. **Verified:** template output matched coding-guide §7 byte-for-byte and `reuse lint` passed.

### Pattern 2: Pure-stdlib AST seam guardrail

**What:** `ast.walk` over every `*.py` under `src/dogen/` except `adapters/copilot/`, flagging `Import`, `ImportFrom`, and `importlib.import_module(...)` nodes whose root module is `copilot` or `github_copilot_sdk`.
**When to use:** SEAM-02 enforcement — every CI build + pre-commit + pytest.
**Why AST not grep:** resists aliasing (`import copilot as c`), submodule imports (`from copilot.session import …`), and dynamic imports — all of which a naive `grep "import copilot"` would miss or mis-handle. **Verified live:** all six forms caught, exit codes correct.
**Trade-offs:** + zero dependencies, fast, evasion-resistant. − does not catch truly dynamic string construction (`import_module("cop"+"ilot")`) — acceptable, and `import-linter` (Phase 2) is the stronger successor once the SDK is a real dep.

### Pattern 3: PEP 639 SPDX license expression in packaging metadata

**What:** `license = "GPL-3.0-only"` (a string SPDX expression, **not** the deprecated `{text=...}`/`{file=...}` table) + `license-files = ["LICENSE", "LICENSES/*.txt"]` in `[project]`.
**When to use:** LIC-02 — recording the SPDX identifier in distributable metadata.
**Why:** verified to produce `Metadata-Version: 2.4` + `License-Expression: GPL-3.0-only` + `License-File:` lines in the wheel. This is the modern (PEP 639) replacement for the old `License ::` trove classifier; **do not** also add a `License :: OSI Approved ::` classifier — PEP 639 tooling treats that as a conflict/duplication.

### Anti-Patterns to Avoid
- **`REUSE.toml` bulk mapping for source files** — violates D-04 (per-file full notice mandated). `REUSE.toml` is acceptable *only* if a future need arises for files that genuinely cannot be annotated; Phase 1 uses per-file headers + `.license` sidecars.
- **A bare `Copyright 2026 Canonical Ltd.` line** — coding-guide §7 mandates `SPDX-FileCopyrightText: 2026 Canonical Ltd.`. Use `--copyright-prefix spdx` (verified to omit the word "Copyright"); `spdx-string`/`string` prefixes wrongly inject "Copyright".
- **Regex/grep seam check** — fails on aliasing and dynamic imports; D-09 explicitly chose AST.
- **Installing the Copilot SDK in Phase 1** — D-08 forbids it; pulls in issue-#1606 CLI fragility for zero Phase-1 benefit.
- **A committed permanently-failing seam fixture** — D-10 chose a one-time manual demo, not a committed negative test (would keep CI red).
- **`ty`'s `--exit-zero`** in CI — that flag forces exit 0 even on errors, defeating the gate. Use plain `ty check` so type errors fail the build.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Inserting/maintaining SPDX headers | A sed/python header-stamping script | `reuse annotate --template canonical` | Handles every comment style, idempotency (`--skip-existing`), `.license` fallback, and stays spec-3.3-correct. |
| Checking REUSE compliance | A custom "does every file have a header" walker | `reuse lint` | Canonical reference implementation; checks bad/deprecated/unused licenses, missing license files, read errors — far beyond "has a header". |
| Obtaining the GPL-3.0-only text | Pasting the license text by hand | `reuse download GPL-3.0-only` | Fetches the canonical SPDX text into `LICENSES/` with the exact filename `reuse lint` expects. |
| Env/lock/build/publish | Poetry/pip/twine combo | `uv` + `hatchling` | D-12; single fast tool, reproducible `uv.lock`. |
| SPDX metadata in the wheel | Hand-writing classifiers | PEP 639 `license` string + `license-files` | hatchling emits `License-Expression` automatically (verified). |
| Aliasing-proof import detection | `grep`/regex over source | stdlib `ast` | D-09; AST resists evasion. (`import-linter` is the Phase-2 upgrade — not now, no SDK dep.) |

**Key insight:** Phase 1 is almost entirely "wire up the standard 2026 Python toolchain correctly"; the only genuinely bespoke code is the ~40-line AST seam check (which *must* be hand-written because `import-linter` can't be used without an installable SDK dep yet). Everything else is configuration of `reuse`, `uv`, `hatchling`, `ruff`, `ty`, `pytest`, and `pre-commit`.

### Per-file-type header enumeration (LIC-01)

How each file in the scaffold gets its REUSE info. **Commentable** = inline full Canonical header via the template; **sidecar** = a `.license` file next to it (for files where an inline comment is impossible or undesirable); **special** = REUSE treats it specially.

| File type | How annotated | Notes |
|-----------|---------------|-------|
| `.py` (all source + tests + `scripts/seam_check.py`) | Inline, full Canonical block (`reuse annotate --template canonical --copyright-prefix spdx -s python`) | `#` comments. Verified. |
| `pyproject.toml` | Inline `#` header (full block) | TOML supports `#`. |
| `.yaml` / `.yml` (CI, pre-commit) | Inline `#` header | YAML supports `#`. |
| `.editorconfig` | Inline `#` header | INI-style `#`/`;` comments OK. |
| `.gitignore` | **Sidecar** `.gitignore.license` (recommended) **or** an inline `#` comment | A `#` line in `.gitignore` is a valid comment, but a `.license` sidecar keeps the ignore file clean — either passes lint. Pick one (discretion). |
| `.md` (README, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT) | Inline header — HTML comment `<!-- ... -->` **or** a short SPDX block; `reuse` supports an `html`/markdown style | Markdown can carry the header in an HTML comment at top. Alternatively `.md.license` sidecar. Verified `.license` path works for any file. |
| `LICENSE` (top-level) | **Special — no header needed** | **Verified:** `reuse lint` does not require the top-level `LICENSE` to carry its own SPDX header; it counted only the real source file (1/1). D-05 satisfied. |
| `LICENSES/GPL-3.0-only.txt` | **Special — no header needed** | Recognized as the license text itself by REUSE; not a file that needs annotation. |
| `uv.lock` | **Sidecar** `uv.lock.license` (`--force-dot-license`) | Generated/large; do not hand-edit a header into it. Verified `.license` sidecar passes lint. |
| Binary/asset files (none in Phase 1, but for completeness) | **Sidecar** `<file>.license` via `--force-dot-license` / `--fallback-dot-license` | Verified with a `.png`. |
| `.reuse/templates/canonical.jinja2` | Inline header (the template file itself) **or** sidecar | It's a text file; give it the header too, or a `.license`. |

## Runtime State Inventory

> Greenfield scaffold — but D-11 (`dogen` PyPI name) surfaced a real external-state finding worth recording.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — greenfield repo, no datastores. | None. |
| Live service config | None — no external services configured in Phase 1 (D-08: no SDK, no CLI). | None. |
| OS-registered state | None. | None. |
| Secrets/env vars | None required for Phase 1 gates (`reuse`/`ruff`/`ty`/`pytest`/`uv` need no secrets; GitHub Actions uses the default `GITHUB_TOKEN` only if a step needs it — the listed gates don't). | None. |
| Build artifacts | None stale yet (greenfield). After scaffold, `uv build` produces `dist/` — gitignore it. | Add `dist/`, `*.egg-info/`, `.venv/`, `__pycache__/` to `.gitignore`. |
| **External registry name** | **`dogen` is ALREADY TAKEN on PyPI** (a Red Hat "Dockerfile from YAML templates" tool, present for years). `[VERIFIED: pypi.org/pypi/dogen/json → HTTP 200]` | **No Phase-1 action** (publishing is out of v1 scope per D-11), but the planner/STATE must record that the **distribution** name needs reconsideration before any publish. The **import name** `dogen` and local dev are unaffected. |

## Common Pitfalls

### Pitfall 1: The full Canonical header silently degrades to two SPDX lines
**What goes wrong:** `reuse annotate` without `--template` writes only `SPDX-FileCopyrightText` + `SPDX-License-Identifier`, dropping the program-description line and the GPL warranty paragraph that D-04/§7 mandate. Lint still passes, so it's invisible until a licensing review.
**Why it happens:** the full block is policy, not a REUSE requirement — the tool's default is the minimal compliant form.
**How to avoid:** commit `.reuse/templates/canonical.jinja2` and always pass `--template canonical --copyright-prefix spdx`. Add a check (review or a tiny test) that a sample file contains the warranty paragraph.
**Warning signs:** headers that are only 2–3 lines; missing "This program is free software…".

### Pitfall 2: Wrong copyright prefix injects the word "Copyright"
**What goes wrong:** `--copyright-prefix spdx-string` (or `string`) emits `SPDX-FileCopyrightText: Copyright 2026 Canonical Ltd.`, which contradicts §7's `SPDX-FileCopyrightText: 2026 Canonical Ltd.`
**How to avoid:** use `--copyright-prefix spdx` (verified to omit "Copyright"). Codify the exact `reuse annotate` invocation in a script so it isn't retyped wrong.

### Pitfall 3: `ty` beta breaks or changes behaviour on upgrade
**What goes wrong:** `ty` is 0.0.x beta with frequent releases; a `ty` auto-upgrade could introduce new diagnostics (red CI) or change exit semantics.
**Why it happens:** Astral explicitly warns of bugs/missing features pre-1.0.
**How to avoid:** pin `ty`'s exact version in `uv.lock`/dev-deps; treat a `ty` bump like the SDK bump — gate behind the smoke suite (the same discipline #1606 teaches for Phase 2). Do **not** add `--exit-zero` to hide failures (that defeats D-14's gate).
**Warning signs:** CI red only after a dev-dep bump touching `ty`.

### Pitfall 4: Seam check passes locally but misses files in CI (path assumptions)
**What goes wrong:** the AST check hard-codes a relative `src/dogen` and is run from a different cwd in CI, scanning nothing and passing vacuously.
**How to avoid:** resolve the scan root relative to the script's own location (`Path(__file__).resolve().parents[1] / "src" / "dogen"`), and have `test_seam.py` assert it actually found ≥1 file. Add the manual D-10 demo to confirm it *can* fail.

### Pitfall 5: `LICENSE` vs `LICENSES/` confusion causes "unused license" lint noise
**What goes wrong:** assuming `reuse lint` will complain about the duplicate top-level `LICENSE`, or that `LICENSES/GPL-3.0-only.txt` is "unused" if no file references it yet.
**Why it happens:** `reuse lint` flags licenses in `LICENSES/` that no file references. In a near-empty scaffold, if the only annotated files all reference `GPL-3.0-only`, it's "used" and fine — **verified, lint passed**. But a scaffold with *zero* annotated source files would flag `GPL-3.0-only` as unused.
**How to avoid:** ensure at least one annotated source file (e.g. `src/dogen/__init__.py`) references `GPL-3.0-only` before running lint — which is always true once headers are applied.

## Code Examples

Verified patterns from this session.

### `.reuse/templates/canonical.jinja2` (the full Canonical block)
```jinja2
{# Source: verified to reproduce coding-guide.md §7 byte-for-byte and pass `reuse lint`. #}
This file is part of dogen, an agentic documentation-drafting framework.

{% for copyright_line in copyright_lines %}
{{ copyright_line }}
{% endfor %}
{% for expression in spdx_expressions %}
SPDX-License-Identifier: {{ expression }}
{% endfor %}

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License version 3, as published
by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program. If not, see <http://www.gnu.org/licenses/>.
```

### Applying the header + provisioning licenses (verified commands)
```bash
# one-time: get the license text into LICENSES/
uvx reuse download GPL-3.0-only

# top-level LICENSE copy (Canonical policy, D-05) — needs no SPDX header
cp LICENSES/GPL-3.0-only.txt LICENSE

# annotate a source file with the FULL Canonical block (template + spdx prefix)
uvx reuse annotate \
  --copyright "Canonical Ltd." --year 2026 \
  --license GPL-3.0-only \
  --copyright-prefix spdx \
  --template canonical \
  src/dogen/__init__.py

# annotate a file that should use a sidecar (e.g. the lockfile)
uvx reuse annotate \
  --copyright "Canonical Ltd." --year 2026 --license GPL-3.0-only \
  --copyright-prefix spdx --force-dot-license uv.lock

# gate
uvx reuse lint     # exit 0 + "compliant with version 3.3" when clean
```

### `scripts/seam_check.py` (verified AST guardrail — all six forms caught)
```python
# Source: prototype run live this session; exit 0 clean / exit 1 on any violation.
"""Static AST guardrail: no Copilot SDK imports outside adapters/copilot/."""
import ast
import sys
from pathlib import Path

BANNED_ROOTS = {"copilot", "github_copilot_sdk"}
PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "dogen"
ADAPTER_DIR = PKG_ROOT / "adapters" / "copilot"


def _is_banned(module: str) -> bool:
    """Return True if the module's top-level package is banned."""
    return module.split(".")[0] in BANNED_ROOTS


def find_violations(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, description) for each banned import in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [(node.lineno, f"import {a.name}") for a in node.names if _is_banned(a.name)]
        elif isinstance(node, ast.ImportFrom) and node.module and _is_banned(node.module):
            hits.append((node.lineno, f"from {node.module} import ..."))
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name == "import_module" and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and _is_banned(arg.value):
                    hits.append((node.lineno, f"import_module({arg.value!r})"))
    return hits


def main() -> int:
    """Scan src/dogen (excluding the adapter) and fail on any violation."""
    scanned = 0
    bad: list[str] = []
    for py in PKG_ROOT.rglob("*.py"):
        if ADAPTER_DIR in py.parents:
            continue
        scanned += 1
        bad += [f"{py}:{ln}: {what}" for ln, what in find_violations(py)]
    if scanned == 0:
        print("seam-check: ERROR — scanned 0 files (path misconfigured)", file=sys.stderr)
        return 2
    if bad:
        print("seam-check: VIOLATION(S):", *bad, sep="\n  ", file=sys.stderr)
        return 1
    print(f"seam-check: OK — {scanned} files, no vendor imports outside adapters/copilot/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### `tests/test_seam.py` (reuses the same code — no drift)
```python
# Source: pattern; calls the same function CI/pre-commit run.
"""Seam guardrail as a pytest test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seam_check  # noqa: E402


def test_no_vendor_imports_outside_adapter() -> None:
    """The core/cli must contain no Copilot SDK imports."""
    assert seam_check.main() == 0
```

### `pyproject.toml` (verified to build with PEP 639 metadata)
```toml
# Source: built live; wheel METADATA showed License-Expression: GPL-3.0-only.
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dogen"
version = "0.0.0"
description = "Agentic documentation-drafting framework"
requires-python = ">=3.12"
license = "GPL-3.0-only"                       # PEP 639 SPDX expression → License-Expression
license-files = ["LICENSE", "LICENSES/*.txt"]  # → License-File entries
# NOTE: do NOT also add a `License :: OSI Approved ::` classifier (PEP 639 conflict)

[dependency-groups]
dev = ["ruff", "ty", "pytest", "pytest-asyncio", "pre-commit"]

[tool.ruff.lint]
# selection is Claude's discretion; align with coding-guide §2 weaknesses, e.g.:
select = ["E", "F", "I", "UP", "B", "SIM", "C901", "PL", "ANN", "D"]
[tool.ruff.lint.pydocstyle]
convention = "numpy"

[tool.ty.environment]
python-version = "3.12"
```

### `.github/workflows/ci.yml` (gate order per D-13)
```yaml
# Source: pattern using astral-sh/setup-uv (repo verified to exist).
name: ci
on: [push, pull_request]
jobs:
  gates:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]   # D-12
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync --frozen            # uses committed uv.lock (D-18)
      - run: uvx reuse lint              # LIC-01
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run ty check             # D-14 (beta hard gate; no --exit-zero)
      - run: uv run python scripts/seam_check.py   # SEAM-02
      - run: uv run pytest -q
      - run: uv build                    # proves PEP 639 metadata (LIC-02)
```

### `.pre-commit-config.yaml` (mirrors the gates, D-13)
```yaml
# Source: reuse hook id/rev verified via fsfe/reuse-tool .pre-commit-hooks.yaml.
repos:
  - repo: https://github.com/fsfe/reuse-tool
    rev: v6.2.0
    hooks:
      - id: reuse
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.18           # pin to match the dev-dep ruff
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: local
    hooks:
      - id: seam-check
        name: seam-check (no vendor imports outside adapters/copilot)
        entry: python scripts/seam_check.py
        language: system
        pass_filenames: false
      - id: ty
        name: ty type check
        entry: uv run ty check
        language: system
        pass_filenames: false
# Note: ty has no stable official pre-commit hook yet (beta) — run via `uv run ty check`
# as a local hook. Re-evaluate when ty ships a published pre-commit hook at 1.0.
```

## State of the Art

| Old Approach | Current Approach (2026) | When Changed | Impact |
|--------------|--------------------------|--------------|--------|
| `setup.py` / setuptools + `License ::` trove classifier | `pyproject.toml` + PEP 639 `license = "<SPDX>"` string + `license-files` | PEP 639 finalized; hatchling/uv support verified | Single SPDX expression in metadata; classifiers for license are discouraged. |
| Poetry/pip/twine | `uv` (one tool: venv+lock+build+publish) | uv maturity through 2025–26 | D-12; faster, reproducible `uv.lock`. |
| mypy / pyright | `ty` (Astral) — **but still beta** | ty entered beta 2026; 1.0 targeted 2026 | D-14 mandates `ty`; treat as a pinned, smoke-gated gate, not a "set and forget". |
| `.reuse/dep5` (Debian copyright format) | `REUSE.toml` (REUSE spec 3.x) | REUSE spec 3.0+ | We use **per-file headers** (D-04), not `REUSE.toml`, so this mostly doesn't apply — but if a bulk file is ever needed, it's `REUSE.toml`, not `dep5`. `reuse` even ships `convert-dep5`. |
| black + isort + flake8 | `ruff` (lint + format) | 2024–25 consolidation | Single fast tool; one config block. |

**Deprecated/outdated (do not use):**
- `license = {text = "..."}` or `{file = "..."}` table form in `[project]` — superseded by the PEP 639 SPDX string.
- `License :: OSI Approved :: GNU General Public License v3 only` classifier alongside a PEP 639 expression — conflicts.
- `.reuse/dep5` — replaced by `REUSE.toml`.
- `ty --exit-zero` in a CI gate — silences the gate.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `astral-sh/setup-uv@v6` is the current major tag for the action | CI example | Low — repo verified to exist (HTTP 200); the planner pins an exact tag at execution time (`gh api` or the repo's releases). If `@v6` has moved, the YAML uses the then-current major. |
| A2 | `ruff-pre-commit` `rev: v0.15.18` matches the dev-dep ruff at execution time | pre-commit example | Low — cosmetic version drift; pin to whatever ruff is locked. Mismatch only causes a version-skew warning, not a wrong result. |
| A3 | `ty` has no published official pre-commit hook yet (so it's run as a `local`/`system` hook) | pre-commit example | Low — if Astral has since published one, swap to it; the `uv run ty check` local hook works regardless. |
| A4 | Markdown files (`README` etc.) can carry the SPDX header in an HTML comment and pass lint | per-file enumeration | Low — the `.license` sidecar path is verified and is the safe fallback for any file type; the inline-HTML-comment path is the only un-verified variant. Planner can default all `.md` to `.md.license` sidecars to be certain. |

**Everything else in this research was verified live or cited from the installed tool's own `--help`/output.** The four assumptions above are all version-pinning or cosmetic, with verified fallbacks.

## Open Questions

1. **`ty` is beta — does the Handbook mandate (D-14) override "don't gate CI on a beta type checker"?**
   - What we know: Astral explicitly says don't remove your other checker from CI until ty's stable (2026). The Handbook nonetheless mandates `ty` (D-14, binding).
   - What's unclear: whether the team wants `ty` as a *hard* gate (build fails on ty error) now, or a *soft* gate (report-only) until 1.0.
   - **Recommendation:** keep `ty` as a **hard gate** (honors D-14) but (a) pin its exact version, (b) gate version bumps behind the smoke suite, (c) do **not** use `--exit-zero`. If `ty` beta instability blocks delivery, the documented fallback is to temporarily make the `ty` step `continue-on-error: true` in CI with a tracked issue — **not** to swap to mypy (which would contradict D-14). Flag this to the user at planning.

2. **`.md` header style: inline HTML comment vs `.license` sidecar?**
   - What we know: `.license` sidecars are verified to work for any file; inline HTML-comment headers in Markdown are supported by `reuse` but I didn't verify them live.
   - **Recommendation:** default all four `.md` hygiene files to `<file>.md.license` sidecars for certainty, OR verify one inline at execution time. Pure discretion; either passes lint.

3. **Does `dogen` need a console-script entrypoint in Phase 1?**
   - What we know: Typer/CLI is Phase-2 (drafting loop). Phase 1's `cli/` can be an empty package.
   - **Recommendation:** stub `cli/` as an empty package (no `[project.scripts]` yet) to avoid declaring a Typer dep prematurely. Discretion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | env/lock/build (D-12, D-18) | ✓ | 0.11.21 | — |
| `uvx` | running `reuse` without a project dep | ✓ | 0.11.21 | `uv tool run reuse` |
| `python3` | runtime / target 3.12 | ✓ | 3.12.3 | — |
| `ruff` | lint+format gate (D-13) | ✓ | 0.15.17 | — |
| `ty` | type gate (D-14) | ✓ | 0.0.51 (beta) | mypy/pyright would contradict D-14 — see Open Q1 |
| `reuse` | LIC-01 gate | ✓ (via uvx) | 6.2.0 | `fsfe/reuse-action` in CI |
| `pre-commit` | local gate mirror (D-13) | ✓ | 4.5.1 | — |
| `pytest` | smoke + seam test | ✓ (resolvable) | latest | — |
| `git` | VCS / trunk-based (D-19) | ✓ | 2.43.0 | — |
| `gh` | GitHub ops (CLAUDE.md mandate) | not probed | — | required by CLAUDE.md for any GitHub task; planner assumes present |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `ty` (beta) — fallback is *not* a tool swap (D-14) but a CI posture (Open Q1).

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` in config. Phase 1 is a CLI-library scaffold with **no** auth, sessions, network endpoints, user input handling, or data storage — most ASVS categories are N/A. The live security concerns are supply-chain and CI integrity.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in Phase 1. |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | No access-controlled resources. |
| V5 Input Validation | no (deferred) | No user input until the CLI/drafting loop (Phase 2). |
| V6 Cryptography | no | No crypto in scope. |
| V14 Configuration / Dependencies | **yes** | Pin dependencies in `uv.lock` (D-18); verify package legitimacy (done above); PEP 639 license hygiene; minimal dev-dep surface. |

### Known Threat Patterns for the Phase-1 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Dependency confusion / slopsquatting in dev-deps | Tampering / Spoofing | Pin exact versions in `uv.lock` (D-18); ran the legitimacy gate (all canonical tools, verified). |
| Malicious GitHub Action (untrusted `uses:`) | Tampering / EoP | Pin actions to a tag/SHA; use only `actions/checkout` + `astral-sh/setup-uv` (first-party). Consider SHA-pinning for supply-chain hardening. |
| `postinstall`/build-time code execution | Tampering | None of the Phase-1 tools have postinstall scripts (verified: `postinstall: null` for all in the legitimacy check). |
| Secret leakage in CI logs | Info Disclosure | Phase-1 gates need no secrets; don't add any. Default `GITHUB_TOKEN` only, least-privilege. |
| Seam check bypass (hiding a vendor import) | Tampering (of the architecture invariant) | The AST check resists aliasing/dynamic-by-constant; the D-10 manual demo proves it catches a real misplacement. |

**SECURITY.md (D-16):** follow Canonical conventions — a brief vulnerability-reporting policy. The Handbook's "Security policy / Vulnerability response" sections are stubs (engineering-handbook §11), so use a standard Canonical SECURITY.md template; exact wording is Claude's discretion (per CONTEXT).

## Sources

### Primary (HIGH confidence — verified live this session)
- Installed binaries: `uv 0.11.21`, `ruff 0.15.17`, `ty 0.0.51`, `reuse 6.2.0` (REUSE spec 3.3), `pre-commit 4.5.1`, `python 3.12.3` — `--version` / `--help` output.
- Live `reuse` experiments: `reuse download GPL-3.0-only`; `reuse lint` PASS with top-level `LICENSE` + `LICENSES/`; custom Jinja2 template reproducing coding-guide §7 byte-for-byte and passing lint; `.license` sidecar via `--force-dot-license` passing lint; `--copyright-prefix spdx` omitting the word "Copyright".
- Live `hatchling`/`uv build`: wheel METADATA showed `Metadata-Version: 2.4`, `License-Expression: GPL-3.0-only`, `License-File:` (PEP 639).
- Live AST seam prototype: all six import/evasion forms caught; exit 0 clean / exit 1 on violation.
- PyPI JSON API: `reuse 6.2.0` (req-python ≥3.10), `ruff 0.15.18`, `ty 0.0.51`; `dogen` name TAKEN (HTTP 200, Red Hat tool).
- `astral-sh/setup-uv` repo exists (HTTP 200).

### Secondary (MEDIUM confidence — official docs / web, cross-checked)
- `fsfe/reuse-tool` `.pre-commit-hooks.yaml` (hook ids `reuse` / `reuse-lint-file`, `rev: v6.2.0`) — github.com/fsfe/reuse-tool.
- `ty` release status (beta; 1.0 targeted 2026; "don't remove mypy until stable") — InfoWorld / pydevtools / Astral docs (WebSearch 2026-06-19).

### Binding in-repo references (authoritative for this project)
- `.planning/refs/coding-guide.md` §2 (toolchain), §6 (architecture invariants), §7 (exact header).
- `.planning/refs/licensing.md` (system of record: GPL-3.0-only, 2026, per-file headers, header variants, CLA).
- `.planning/refs/engineering-handbook.md` §7 (ruff+ty mandate), §3/§8 (trunk-based, review).
- `AGENTS.md` (seam invariant, branching).
- `.planning/research/ARCHITECTURE.md` (hexagonal layout, Pattern 1, Anti-Pattern 1/2), `STACK.md`, `PITFALLS.md` (Pitfall 4 seam leak, Pitfall 9 scope border).

## Metadata

**Confidence breakdown:**
- REUSE mechanics (LIC-01): **HIGH** — every claim (LICENSE+LICENSES/ lint pass, exact template header, `.license` sidecars, copyright prefix) verified live.
- SPDX metadata (LIC-02): **HIGH** — built a wheel and inspected METADATA; PEP 639 emission confirmed.
- Seam guardrail (SEAM-01/02): **HIGH** — AST prototype ran live, all evasion forms caught.
- Packaging/toolchain: **HIGH** — uv/hatchling/ruff/pre-commit versions verified; build succeeded.
- `ty` posture: **MEDIUM** — tool runs (verified), but beta status and the D-14-vs-beta tension is a planning decision (Open Q1).
- CI/pre-commit YAML: **MEDIUM** — action/hook names verified to exist; exact pinned tags are execution-time details (assumptions A1–A3).

**Research date:** 2026-06-19
**Valid until:** ~2026-07-19 for `reuse`/`uv`/`hatchling`/PEP 639 mechanics (stable); ~2026-06-26 for `ty`/`ruff` exact versions (Astral releases weekly — re-verify pins at execution time).
