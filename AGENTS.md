# AGENTS.md — operating contract for coding agents

This is the harness-neutral operating contract for any AI coding agent working in this
repository (read by Copilot, Codex, Cursor, and others; Claude Code reads it too). Read it
before you touch anything.

**Non-negotiables**

- **The provider seam is sacred.** `dogen.core` never imports `copilot`,
  `github_copilot_sdk`, `logfire`, or `opentelemetry.sdk`. The Copilot SDK lives only in
  `src/dogen/adapters/copilot/`; the concrete telemetry backend only in `dogen.adapters`.
  Two hard gates enforce this — `scripts/seam_check.py` (AST) and `import-linter` — and both
  must stay green. It is the single most valuable property in the codebase: it keeps a later
  backend swap cheap.
- **The HITL gate is load-bearing.** No substantial draft is produced without recorded human
  steering and a signoff. The gate lives in deterministic `core` code, not in skill prose —
  never move it into the model's discretion.
- **dogen drafts and stops.** It writes a single traceable local commit and never pushes,
  opens or reviews PRs, builds, or publishes. The reviewer/merger owns the shipped output.
- **`main` stays green.** Every gate passes before a commit lands: `ruff check` +
  `ruff format --check`, `ty check`, `scripts/seam_check.py`, `scripts/skill_lint.py`,
  `lint-imports`, `pytest`.
- **Skills are the surface; the CLI is the tool layer.** Technical Authors drive the
  `dogen-plan` / `dogen-write` / `dogen-review` skills; the thin Typer CLI exposes the
  deterministic verbs those skills call. Keep the CLI thin.

The rest of this file is the project brief and the stack rationale.

---

## Project

**dogen — skills-first documentation-drafting framework**

dogen is a platform-agnostic, agentic **documentation-drafting** framework for Technical Authors (TAs). It drafts Sphinx-publishable (MyST Markdown, Diátaxis-structured) documentation from human-pointed sources, human-in-the-loop, and deliberately stops at the boundary of a single traceable local commit — no pushing, PR review, building, or publishing.

This iteration is a **skills-first rebuild**: portable Agent Skills (`SKILL.md`) are the surface a TA actually drives, layered over a reused deterministic Python core. It supersedes an earlier monolithic-CLI prototype — this repository's own history up to the tag `archive/mvp-1-prototype` — while lifting that prototype's proven, battle-tested machinery.

**Core Value:** A Technical Author can point dogen at sources for one documentation unit, steer it on intent and audience, and get a **review-ready, Sphinx-publishable draft** — produced through a *provable* human-in-the-loop loop, with steering and provenance recorded on disk. If everything else fails, this loop (declare → steer → draft → review, no substantial draft without recorded human steering) must work.

### Constraints

- **Tech stack**: Python 3.12 — keep the drafting layer thin over the SDK so a later swap is cheap.
- **Agent backend**: GitHub Copilot SDK (MIT; team decision, Jun 22) as the *driver* provider — corporate subscription, bring-your-own-key via Open Router, actively maintained. A *host-harness passenger* provider sits behind the same `DraftingProvider` port as a zero-setup fallback, auto-selected when Copilot is unavailable. LangGraph / Pydantic AI parked for later revisit.
- **Surface**: portable Agent Skills (`SKILL.md`) as the primary interface, authored to the **agentskills.io** spec and split into `dogen-plan` / `dogen-write` / `dogen-review`; validated on Claude Code and Copilot CLI.
- **Licensing**: core **LGPL-3.0-only**, expressed minimally (single root `LICENSE`, no per-file SPDX/REUSE machinery); skills licensed to match `skills-playground` (working default Apache-2.0, pending confirmation); the Copilot SDK dependency is MIT.
- **Budget**: prefer cheaper/open models (Sonnet-tier or top open-weight) via Open Router; avoid frontier/closed-model token burn.
- **Agnosticism**: platform-agnostic is a design property of the *core*; prove it on one stack (GitHub + RTD + Sphinx) this cycle.
- **Output**: Sphinx-publishable MyST Markdown, Diátaxis-structured; draft only.
- **HITL / provenance**: no substantial draft without recorded steering; provenance is for internal observability, NOT a published "AI-generated" disclaimer — the reviewer/merger owns the output.
- **UX**: good design is a primary requirement — "if it's easier to circumvent than to use, it will be circumvented."
- **Timeline**: 26.10 cycle; ~70% of goals by September, operational by mid-August. A mid-cycle company-wide holiday is the top schedule risk.
- **Privacy / AI policy**: Copilot's NDA arrangement covers confidential repos; respect Canonical's AI policy.

## Technology Stack

## TL;DR — be prescriptive

- **Keep every dependency and version** from mvp-1's `pyproject.toml`. Do not re-litigate the seam.
- **Reposition the Typer CLI** from "the product" to "the deterministic tool surface that Skills drive." Portable `SKILL.md` files become the primary human-facing interface; the CLI verbs become the callable, side-effecting actions a skill invokes via `Bash`.
- **Preserve the `import-linter` provider-seam contract verbatim** — it is the single most valuable artifact to lift, because it is what keeps a later backend swap (els-style / open SDK) cheap.

## Lift-from-mvp-1 list (exact, cite-grounded)

| Item | Declared spec (pyproject) | Resolved (uv.lock) | Action | Confidence |
|------|---------------------------|--------------------|--------|------------|
| Python floor | `requires-python = ">=3.12"` | 3.12 | LIFT as-is | HIGH |
| `github-copilot-sdk` | `==1.0.2` (exact pin) | 1.0.2 | LIFT — keep exact pin | HIGH |
| `logfire` | `>=4.37.0` | 4.37.0 | LIFT | HIGH |
| `opentelemetry-api` | `>=1.42.1` | 1.42.1 | LIFT (API only — see seam note) | HIGH |
| `pydantic` | `>=2` | 2.13.4 | LIFT | HIGH |
| `typer` | `>=0.26.7` | 0.26.7 | LIFT — but reposition (see CLI decision) | HIGH |
| `sphinx` (docs extra) | `==9.1.0` | 9.1.0 | LIFT | HIGH |
| `myst-parser` (docs extra) | `==5.1.0` | 5.1.0 | LIFT | HIGH |
| `furo` (docs extra) | `>=2025.12.19` | 2025.12.19 | LIFT | HIGH |
| `ruff` (dev) | unpinned | 0.15.18 | LIFT; consider pinning | HIGH |
| `ty` (dev) | unpinned | 0.0.51 | LIFT; pin (pre-1.0, churny) | MEDIUM |
| `pytest` (dev) | unpinned | 9.1.1 | LIFT (eval deferred, but keep installed) | HIGH |
| `pytest-asyncio` (dev) | unpinned | 1.4.0 | LIFT | HIGH |
| `pre-commit` (dev) | unpinned | 4.6.0 | LIFT | HIGH |
| `import-linter` (dev) | `>=2.11` | 2.11 | LIFT — **plus the contract block** | HIGH |
| Build backend | `hatchling` | — | LIFT | HIGH |
| Project/lock/build driver | `uv` (+ `uv.lock`) | — | LIFT | HIGH |
| License | mvp-1 was `GPL-3.0-only` + PEP 639 `license-files` | — | **CHANGED** — core is now **LGPL-3.0-only** via a single root `LICENSE`; skills Apache-2.0 (`skills/LICENSE`) | HIGH |
| REUSE/SPDX | mvp-1 used `REUSE.toml` + per-file headers + `reuse` pre-commit | — | **DROPPED** — licensing is expressed minimally; no REUSE machinery (see Constraints) | HIGH |
| CI | `.github/workflows/ci.yml` | — | LIFT, adapted for skills | HIGH |
| Provider-seam guard | `scripts/seam_check.py` (AST) + `import-linter` forbidden contract | — | **LIFT verbatim** | HIGH |
| Pre-commit hooks | `ruff`, `ruff-format`, `seam-check`, `skill-lint`, `import-linter`, `ty` | — | LIFT (no `reuse` hook; `skill-lint` added) | HIGH |

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | **3.12** (`>=3.12`) | Implementation language | Floor is set by the docs toolchain: `sphinx==9.1.0` needs 3.12+. The Copilot SDK floor is only 3.11, so 3.12 covers both. Lift mvp-1's floor unchanged. [HIGH] |
| **github-copilot-sdk** | **1.0.2** (pin exactly) | Adopted agent backend; drives drafting via JSON-RPC to the Copilot CLI runtime | Team decision (Jun 22). GA, typed, async, in-process tools (Pydantic), per-session MCP, BYO-key via Open Router. Pin exactly — the SDK↔CLI runtime protocol is version-coupled (see Version Compatibility). [HIGH] |
| **Agent Skills (`SKILL.md`)** | spec: `name` + `description` required; `allowed-tools` optional | **Primary human-facing surface** — portable, harness-agnostic skill files orchestrating the loop | The deliberate pivot for this milestone. Cross-agent open standard supported by Copilot, Claude Code, Codex, Gemini CLI, Cursor, OpenCode. The `ng` docs-skills family is the authoritative pattern source (family contract, section skeleton, `references/`, self-healing block). [HIGH] |
| **Typer** | **0.26.7** (`>=0.26.7`) | Thin deterministic CLI — the **tool surface skills invoke**, not the product UX | Type-hint-driven, minimal boilerplate. Repositioned (see CLI decision): exposes deterministic verbs (scaffold planning dir, record steering, emit provenance, render review surface) that `SKILL.md` workflows call via `Bash`. Stays thin per the lifted D-42 constraint. [HIGH] |
| **Pydantic** | **v2** (resolved 2.13.4) | Schemas for planning-dir (steering/unit-plan/provenance) **and** Copilot SDK `@define_tool` params | One validation model spans on-disk schema v0 and SDK tool params. Already the SDK's schema layer — reuse it; do not add a second validator. [HIGH] |
| **uv** | latest (Astral) | Project, dependency, lockfile, build, publish driver | 2026 golden path; reproducible `uv.lock` lifted from mvp-1. One fast tool for venv + resolve + build. [HIGH] |
| **hatchling** | latest | PEP 517 build backend | mvp-1's `[build-system]`. Lightweight, src-layout friendly, plays clean with uv. [HIGH] |

### Documentation output toolchain (the "Sphinx-publishable" target)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Sphinx** | **9.1.0** (pin) | Publish engine for Read the Docs | Fixed docs-as-code stack (GitHub + RTD + Sphinx). Drives the 3.12 floor. [HIGH] |
| **myst-parser** | **5.1.0** (pin) | Parse MyST Markdown in Sphinx | MyST = CommonMark ergonomics + full rST power via `colon_fence`. Models emit clean Markdown far more reliably than whitespace-strict rST — directly lowers malformed-output/"slop" risk. [HIGH] |
| **furo** | **2025.12.19** (calver) | Sphinx HTML theme for local review rendering | Clean, responsive, light/dark. Optional at publish (RTD can theme); useful for the local review surface. [HIGH] |
| **Diátaxis** | methodology (no package) | Structure drafted units: tutorial / how-to / reference / explanation | RTD-endorsed; aligns with type-aware, intent-steered generation. Encode the four types as operator-picked *direction*; one category per page. [HIGH] |

### Observability (provider-independent, survives an SDK swap)

| Library | Version | Purpose | Why / When |
|---------|---------|---------|------------|
| **logfire** | **4.37.0** (`>=4.37.0`) | Concrete observability backend for provenance + run telemetry | Captures model/version/effort, tooling version, context origins (provenance requirement). Lives **only in `dogen.adapters`** — `core/` is import-linter-forbidden from importing it. [HIGH] |
| **opentelemetry-api** | **1.42.1** (`>=1.42.1`) | Vendor-neutral telemetry API for `core/` | `core/` may use the OTel **API** but never `opentelemetry.sdk` (forbidden by contract). This is the seam that lets the backend swap without touching core. [HIGH] |

### Supporting libraries (add only when the requirement lands)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **tomllib** (stdlib) / **tomli-w** | stdlib / latest | Read/write planning-dir + provenance if TOML-based | `tomllib` read-only is free. Prefer Pydantic-validated YAML/JSON for human-edited steering files; add `tomli-w` only if you must *write* TOML. [HIGH] |
| **PyYAML** / **ruamel.yaml** | latest | YAML frontmatter for steering + `SKILL.md` profiles | `SKILL.md` and agent profiles use YAML frontmatter; `ruamel.yaml` only if you must round-trip-preserve human edits. [MEDIUM] |
| **httpx** | latest | Fetch org-wide guidance from remote URLs (pre-MCP customization layer) | Deferred-milestone need ("remote URLs now → MCP later"). Async, matches the SDK. Do **not** add until that layer is in scope. [HIGH] |

### Development Tools (lift mvp-1's exact set)

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| **uv** | latest | Env, lock, build, publish | Single source of truth; `uv.lock` lifted. |
| **ruff** | 0.15.18 | Lint + format | mvp-1 `select = ["E","F","I","UP","B","SIM","C901","PL","ANN","D"]`, numpy docstring convention. Consider pinning. |
| **ty** | 0.0.51 | Static type checker (Astral) | Pre-1.0 and churny — **pin this one**. mvp-1 uses `extra-paths = ["scripts"]` so the seam guard resolves. |
| **import-linter** | 2.11 (`>=2.11`) | Declarative provider-seam enforcement | Primary seam gate; runs with the AST `seam_check.py` as belt-and-braces. **Lift the contract block.** |
| **pytest** + **pytest-asyncio** | 9.1.1 / 1.4.0 | Async test harness | Eval is *deferred* this milestone — keep installed and green, don't build the harness yet. |
| **pre-commit** | 4.6.0 | Hook runner | Hooks: `ruff`, `ruff-format`, `seam-check`, `skill-lint`, `import-linter`, `ty` (see `.pre-commit-config.yaml`). No `reuse` hook — licensing is minimal. |
| **skill-lint** | `scripts/skill_lint.py` | `SKILL.md` frontmatter + tool-surface gate | Asserts each skill's frontmatter and the Write/Edit tool-surface isolation; a hard CI + pre-commit gate. |
| **GitHub Actions** | `ci.yml` | CI | Runs the same gate order as pre-commit + `pytest`; lints skills (`SKILL.md`) alongside Python. |

## Installation

See `README.md` for the install-and-use quickstart (install into a docs repo, install the
skills, land context files) and the dev-setup commands (`uv sync` + the gate suite).

## CLI-vs-Skills surface decision (RECOMMENDED)

- The milestone requirement is explicit: "the loop is driven through portable Agent Skills (`SKILL.md`) over the lifted deterministic core." The TA drives skills, not a CLI.
- The `ng` family (authoritative prior-art) proves the shape: skills are *conversational LLM prompts with no flags* that call repo tools (`tools/*.py`) via `Bash` for the deterministic, side-effecting work (scaffolding, staging, build validation). dogen mirrors this — Typer verbs are dogen's `tools/`.
- This split is exactly what keeps the drafting layer thin and the core swappable: the **provable HITL gate, planning-dir schema v0 writes, and provenance capture must be deterministic Python** (testable, not LLM-discretionary), while *intent/judgment* lives in the skill prompt. A skill that "refuses to draft without recorded steering" should call a CLI verb that enforces the gate in code, not rely on the model to remember.
- `SKILL.md` (e.g. a `dogen-plan` / `dogen-draft` / `dogen-review` family modeled on `ng-plan-docs` → `ng-write-docs` → `ng-review-docs`) = the human-facing surface, harness-portable.
- Typer verbs (`dogen declare`, `dogen record-steering`, `dogen draft`, `dogen provenance`, `dogen review`) = deterministic actions the skills invoke. Keep the CLI module thin (lifted D-42); the Typer `app` object stays the console entrypoint for power users and CI, but it is not the TA's primary path.
- **`allowed-tools` in each `SKILL.md`** gates the tool surface (the `ng` family excludes `Write`/`Edit` from the graft skill to force delegation — use the same technique to force drafting through the gate).

## Light current-practice / drift check

| Item | mvp-1 state | Current (Jun 2026) | Drift / flag |
|------|-------------|--------------------|--------------|
| `github-copilot-sdk` | pinned `==1.0.2` | 1.0.2 is current latest on PyPI | **No drift in the pin.** But the SDK↔CLI runtime is protocol-version-coupled (reports of `SDK expects protocol v2, server reports v3` mismatches between SDK and a newer CLI). Reinforces: pin the SDK *and* the runtime; fetch via `python -m copilot download-runtime`; gate any bump behind a drafting-loop smoke test. [HIGH] |
| Copilot runtime fetch | (managed by SDK) | `python -m copilot download-runtime` is the documented runtime step | Add it to setup + CI; do not rely on silent auto-update (the auto-update path is the known breakage vector — mvp-1's issue-#1606 note still stands). [HIGH] |
| Agent Skills `SKILL.md` | "open cross-agent standard (2025-12-18)" | Spec stable: `name`+`description` required, `allowed-tools`/`license`/`compatibility`/`metadata` optional; progressive disclosure + `references/` confirmed | **No breaking drift.** Copilot supports `SKILL.md` (via VS Code agent skills). The `ng` skeleton is a valid superset. [HIGH] |
| `sphinx` / `myst-parser` / `furo` | 9.1.0 / 5.1.0 / 2025.12.19 | Same generation; pins still valid | No action; re-verify the MyST↔Sphinx 9.x range only if you bump Sphinx. [HIGH] |
| `ty` | 0.0.51 (unpinned) | Pre-1.0, fast-moving | **Pin it** — unpinned 0.0.x can break the type gate on any release. [MEDIUM] |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `github-copilot-sdk` (typed JSON-RPC client) | Shelling out to `copilot -p … -s` and parsing stdout | Only as a *fallback* behind the same port if the SDK transport breaks (protocol mismatch / removed flags) or in constrained CI. The seam must make either path swappable. [HIGH] |
| Copilot SDK backend | Claude Agent SDK / `opencode-agent-sdk` | These are the seam's **future adapters**, not now. `opencode-agent-sdk` is a drop-in for `claude_agent_sdk` and provider-agnostic — mirror its shape (sessions/tools/MCP/skills). Swap if Copilot cost/policy/availability changes. [MEDIUM] |
| Skills-first surface | CLI-first / TUI-first | Only if a target harness lacks `SKILL.md` support — then the Typer CLI is already the fallback driver. Don't invert the default. [HIGH] |
| MyST Markdown | reStructuredText | Use rST when a project's existing docs are already rST. Sphinx reads both; default new drafted pages to MyST to reduce model malformation. [HIGH] |
| uv + hatchling | Poetry / PDM / setuptools | Only if the org standardizes elsewhere. None match uv's speed + unified flow in 2026. [HIGH] |
| Typer (as tool layer) | Click / argparse | Click for its plugin ecosystem; argparse to avoid a dependency. Typer wins DX for thin typed verbs. [HIGH] |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **RAG infra / vector DBs by default** (Chroma, FAISS, pgvector, LlamaIndex) | Explicitly spike-gated and out of scope this milestone; steering-first is the design. Adds infra, indexing, and a retrieval failure mode the loop doesn't need. | Human-pointed sources + remote-URL guidance via `httpx` later → MCP-served guidance when that layer lands. [HIGH] |
| **Heavyweight agent frameworks** (LangGraph, LangChain, CrewAI, AutoGen, Pydantic AI *as the loop*) | Duplicates the Copilot SDK's session/tool/MCP machinery, thickens the layer that must stay thin, and blocks the cheap backend swap. PROJECT.md: build the drafting layer, not agent machinery. | The SDK's `session` + `@define_tool` + per-session MCP. Pydantic AI stays *parked* (PROJECT.md) as a possible future adapter, not a dependency now. [HIGH] |
| **Anything that thickens the SDK adapter / leaks SDK types** (passing `CopilotClient`, `SessionConfig` across modules) | Defeats the cheap-swap premise; makes adopting Claude/OpenCode a rewrite; violates the lifted import-linter contract. | A narrow port (`DraftingBackend`) with one Copilot adapter in `dogen.adapters`; `core/` never imports `copilot`/`github_copilot_sdk`. [HIGH] |
| **Scraping `copilot` CLI stdout as the primary integration** | No documented structured output; brittle; `--headless --stdio` was removed once already. | The typed JSON-RPC SDK; keep stdout-parsing only as a guarded fallback behind the port. [HIGH] |
| **Floating/unpinned SDK + auto-updating CLI runtime** | The runtime auto-update silently breaks the SDK transport via protocol-version mismatch. | Pin `==1.0.2`, pin the downloaded runtime, gate bumps behind a drafting-loop smoke test. [HIGH] |
| **Persistent agent memory** (mem0, Cognee) | Mode-B-facing; out of scope for unit-scoped Mode A; adds state the provable loop doesn't need. | Steering recorded on disk (planning-dir schema v0); no memory layer. [HIGH] |
| **A concrete OTel SDK or `logfire` import inside `core/`** | Breaks OBS-01 (observability must survive a backend swap) and the import-linter contract. | `opentelemetry-api` only in `core/`; `logfire` + `opentelemetry.sdk` confined to `dogen.adapters`. [HIGH] |
| **Building your own agent loop / tool dispatcher / provider client** | Reinvents the SDK, bloats the thin core, and is explicitly anti-scope. | SDK primitives behind the port. [HIGH] |
| **Heavy rST-first authoring for AI-emitted content** | Whitespace-strict rST raises the model's malformed-output rate. | MyST Markdown with `colon_fence`. [HIGH] |
| **Poetry / Pipenv for a new distributable lib** | Slower; divergent from the uv/pyproject golden path already proven in mvp-1. | uv + hatchling. [HIGH] |

## Stack Patterns by Variant

- Ship the skill family as the primary surface; the TA never touches Typer directly.
- Because the milestone requires the loop driven through portable Agent Skills.
- Drive the same deterministic verbs through the Typer CLI directly.
- Because the CLI is the always-available fallback for the exact same core operations.
- Fetch via `httpx` and inject into the system message / a per-session `SKILL.md`; evolve to an MCP server via `create_session(mcpServers={...})`.
- Because the SDK already supports per-session MCP — the migration is config, not code, and the core stays decoupled from the guidance.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `github-copilot-sdk==1.0.2` | a **specific** Copilot CLI runtime | Protocol-version-coupled. A newer auto-updated runtime can report a protocol version the pinned SDK doesn't speak (observed `expects v2 / server v3` mismatches). **Pin both; fetch via `python -m copilot download-runtime`; smoke-test on any bump.** [HIGH] |
| `github-copilot-sdk` | Python ≥ 3.11 | SDK floor; not the binding constraint. [HIGH] |
| `sphinx==9.1.0` | Python ≥ 3.12 | Docs toolchain floor — drives the project's `>=3.12`. [HIGH] |
| `myst-parser==5.1.0` | Sphinx 9.x | Re-confirm the exact Sphinx range in the MyST changelog only if you bump Sphinx. [MEDIUM] |
| `opentelemetry-api>=1.42.1` | `logfire>=4.37.0` | API in `core/`, SDK+logfire in adapters; the split is enforced by import-linter, not just convention. [HIGH] |
| `ty==0.0.51` (recommend pinning) | Python 3.12, `extra-paths=["scripts"]` | Pre-1.0; pin to avoid a type-gate break on any release. [MEDIUM] |

## Sources

- The **mvp-1 prototype** — this repository's own ancestry, at tag `archive/mvp-1-prototype`:
  `pyproject.toml` (declared deps, docs extra, dev group, the `[tool.importlinter]`
  provider-seam contract, ruff/ty config), `uv.lock` (resolved versions — pydantic 2.13.4,
  ruff 0.15.18, ty 0.0.51, pytest 9.1.1, pytest-asyncio 1.4.0, pre-commit 4.6.0, typer 0.26.7,
  sphinx 9.1.0, myst-parser 5.1.0, furo 2025.12.19, logfire 4.37.0, opentelemetry-api 1.42.1,
  import-linter 2.11), `.pre-commit-config.yaml`, and `.github/workflows/ci.yml` — [HIGH, primary]
- The `ng-*` docs-skills prior-art family — family contract, `SKILL.md` section skeleton,
  `references/` pattern, canonical self-healing block, non-destructive default — [HIGH]
- PyPI / GitHub `github/copilot-sdk` — `github-copilot-sdk` 1.0.2; SDK↔CLI protocol-version
  mismatch reports; `python -m copilot download-runtime` — [HIGH, web]
- agentskills.io specification + 2026 SKILL.md references — required `name`/`description`,
  optional `allowed-tools`, cross-agent support incl. GitHub Copilot — [HIGH, web]

## Conventions

- **Markup:** new drafted pages default to MyST Markdown (`colon_fence`); use rST only when a
  page's siblings are already rST — the target extension *is* the format.
- **Docstrings:** numpy convention (ruff `select = ["E","F","I","UP","B","SIM","C901","PL","ANN","D"]`).
- **Decisions** are recorded as `D-NN` references in code and skill prose — keep that trail.

## Architecture

Hexagonal, organized around the provider seam:

- `src/dogen/core/` — vendor-free domain: the orchestrator (the declare → steer → draft →
  review loop and the HITL gate), Pydantic models, the ports, authoring rubrics, and the
  observability API surface. Imports no provider or concrete-telemetry package.
- `src/dogen/adapters/` — the outside world: `copilot/` (the GitHub Copilot SDK driver),
  `host_harness.py` (the zero-setup passenger provider), `planning_fs.py` (the on-disk
  planning directory), `git_repo.py` / `git_identity.py`, `skills_install.py`.
- `src/dogen/app/compose.py` — the composition root that wires ports to adapters.
- `src/dogen/cli/` — the thin Typer surface (`main.py` + `skills.py`) that skills invoke via Bash.
- `src/dogen/obs/` — the concrete logfire backend (the adapter side of the observability seam).

The seam (`core` ⇏ providers / concrete telemetry) is enforced by `scripts/seam_check.py` and
`import-linter`, not by convention — see the Non-negotiables at the top.

## Project skills

This repo ships the canonical `dogen-plan` → `dogen-write` → `dogen-review` skill family under
`skills/` (each a `SKILL.md` plus its `references/`). Install it into a target repo's harness
discovery root with `dogen skills install --harness <name>` (repeatable; omit to auto-detect
from the repo's directories) — `claude` → `.claude/skills`, `copilot` → `.github/skills`,
`opencode` → `.opencode/skills`; the install is recorded in `.dogen/skills-install.yaml` and
re-staged with `dogen skills update`. `skills/` is the single source of truth — never
hand-edit an installed copy.
