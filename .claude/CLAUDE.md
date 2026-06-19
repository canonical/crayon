<!-- GSD:project-start source:PROJECT.md -->

## Project

**Agentic Documentation Drafting Framework**

A reusable, distributable Python package that helps a person in a Technical Author (TA) role draft complete documentation sets iteratively. It rides on an adopted agent SDK and adds a doc-drafting layer on top — it does exactly one thing: draft documentation in a Sphinx-publishable format. It is steered by human intent and product expertise, layers org-wide guidance + per-repo knowledge + writer preferences, and stays deliberately "dumb" outside drafting: no committing-at-scale, pushing, PR review, building, or auto-publishing. The hard border is singular, traceable local commits.

**Core Value:** A TA (or anyone acting in that capacity) can reliably draft review-ready documentation faster than starting from scratch, with a human owning intent and review at every step — "quality at speed," without AI slop.

### Constraints

- **Tech stack**: Python package; rides on the **Copilot SDK behind a thin, genuinely multi-provider abstraction seam** (alternate targets: OpenCode SDK, or a homegrown Pydantic AI agent) so the agentic-logic provider can be swapped cheaply — Why: pragmatic-first per the epic, with agnosticism kept as a core design property
- **Output**: must be Sphinx-publishable — Why: primary docs-as-code stack this cycle is GitHub + RTD + Sphinx
- **Scope border**: drafting only; stop at singular traceable local commits — Why: framework stays dumb outside drafting; reviewer/merger owns output
- **Process**: human-in-the-loop is mandatory and must be *provable* (recorded steering on intent + audience) — Why: accountability and the AC5 audit
- **Decoupling**: the reusable core stays distinct from the guidance it consumes (defined company-wide once and maintained, or scraped per repo) — Why: portfolio updates benefit everyone instead of fragmenting
- **Provenance**: internal observability only, about the harness/tooling — not a published content disclaimer — Why: humans own and stand behind shipped output
- **Observability**: instrumented independently of the agentic SDK (provider-independent layer; Logfire / OpenTelemetry the leading candidate) — Why: observability must survive an SDK swap and not depend on the SDK's own telemetry
- **Licensing**: REUSE-compliant from commit 1 (SPDX headers, `reuse lint` in CI); specific OSS license TBD via discussion — Why: clean, auditable licensing/provenance of own and third-party code
- **Delivery cadence**: agile; plan one pulse in advance; epic breakdown is a reference frame, not a fixed task list — Why: holiday/critical-path risk plus the "pour concrete in stages" philosophy
- **UX**: good design is a primary requirement — Why: if it's easier to circumvent than to use, it will be circumvented

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Critical context: there is a real Copilot SDK, not just a CLI [HIGH]

- **Python package:** `github-copilot-sdk` — **v1.0.2, released 2026-06-18**, requires **Python ≥ 3.11**. Import surface is `from copilot import CopilotClient` and `from copilot.session import PermissionHandler`. (Verified on PyPI + GitHub Docs.)
- **How it works:** the SDK talks to the Copilot CLI runtime over **JSON-RPC**. By default the SDK auto-manages the CLI process lifecycle (bundled binary, stdio). You can also run the CLI in server mode (`copilot --headless --port 4321`) and connect via `RuntimeConnection.for_uri(...)` / `for_tcp(...)` / `for_stdio(...)`.
- **Async-first:** context-manager + `async`/`await` API. Core flow:

### Copilot SDK — MCP support [HIGH]

### Copilot SDK / CLI — custom tools support [HIGH]

### Copilot — Agent Skills support [HIGH]

### Copilot CLI — programmatic/headless surface (fallback seam) [HIGH]

### Stability gotcha you must design around [HIGH — verified, unresolved]

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | **3.11+** (target 3.12) | Implementation language of the framework | Fixed by PROJECT.md; floor is dictated by `github-copilot-sdk` (≥3.11). Sphinx 9.x needs 3.12+, so the *docs toolchain* env wants 3.12 — target 3.12 to cover both. [HIGH] |
| **github-copilot-sdk** | **1.0.2** (pin exactly) | The adopted agent backend — drives drafting, tools, MCP, skills via JSON-RPC to the Copilot CLI runtime | Fixed decision. GA, official, Python-native, async, typed events, in-process tools (Pydantic), per-session MCP, Agent Skills. Avoids fragile stdout scraping. **Pin; auto-update of the underlying CLI is a known breakage vector.** [HIGH] |
| **GitHub Copilot CLI** | pin the SDK-compatible version | Runtime the SDK launches/connects to; secondary fallback integration surface | Bundled with the SDK; you mostly never touch it directly, but its version must be pinned because of issue #1606. [HIGH] |
| **uv** | latest (Astral) | Project, dependency, lockfile, build, and publish driver | 2026 "golden path" — one fast tool for venv + resolve + build + publish; reproducible `uv.lock`; first-class `pyproject.toml`. [HIGH] |
| **hatchling** | latest | Build backend (`[build-system]`) | 2026 default backend: lightweight, PEP-compliant, plays cleanly with uv and src/ layout. [HIGH] |
| **Typer** | latest | CLI framework for the installed console command | Type-hint-driven (built on Click, by the FastAPI author); function signatures become the CLI; auto help/completion. Best DX-per-line for a new CLI, and "good UX is a primary requirement" per PROJECT.md. [HIGH] |
| **Pydantic** | v2.x | Schemas for the planning-directory (F1) and for Copilot SDK `@define_tool` parameter schemas | Already the schema layer the Copilot SDK uses for tools; reusing it keeps one validation model for tool params *and* the on-disk planning/provenance schema. [HIGH] |

### Documentation output toolchain (the "Sphinx-publishable" target)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Sphinx** | **9.1.0** (Python 3.12+) | The publish engine for Read the Docs | The fixed docs-as-code stack. v9.1.0 released 2025-12-31. [HIGH] |
| **myst-parser** | **5.1.0** | Parse **MyST Markdown** in Sphinx | MyST is the 2026 recommendation: CommonMark ergonomics + full rST power (roles/directives via `colon_fence`). Models emit clean Markdown far more reliably than rST's whitespace-strict syntax — directly lowers AI "slop"/malformed-output risk. Sphinx happily mixes `.md` and `.rst`. [HIGH] |
| **Diátaxis** | (methodology, not a package) | Structure the drafted doc set: tutorial / how-to / reference / explanation | Officially endorsed by Read the Docs; aligns with PROJECT.md's "type-aware generation steered by intent." Encode the four types as *direction* the operator picks; one Diátaxis category per page/navigation path. [HIGH] |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **github-copilot-sdk[telemetry]** (OpenTelemetry extra) | matches SDK 1.0.2 | Built-in OTel hooks for the agent runtime | Use for the **provenance/observability** requirement — capture model/version/effort and tool calls from the SDK's own telemetry instead of hand-rolling. [MEDIUM — extra confirmed on PyPI; exact emitted fields unverified, validate at build time] |
| **furo** | 2025.12.19 (calver) | Sphinx HTML theme | If you render HTML locally for review; clean, responsive, light/dark. Optional — RTD can theme. [HIGH] |
| **sphinx-design** | 2026-01 release | Cards/grids/tabs components in MyST | Only if drafted docs use rich components; enable with MyST `colon_fence`. [MEDIUM] |
| **tomllib** (stdlib, 3.11+) / **tomli-w** | stdlib / latest | Read/write the on-disk planning + provenance files (F1) if TOML-based | `tomllib` is read-only stdlib; add `tomli-w` only if you must *write* TOML. (Prefer Pydantic-validated YAML/JSON if humans hand-edit steering files.) [HIGH] |
| **PyYAML** / **ruamel.yaml** | latest | Read/write planning-dir steering + agent/skill profiles (YAML frontmatter) | Copilot agent profiles and SKILL.md use YAML frontmatter; `ruamel.yaml` if you must round-trip-preserve human edits. [MEDIUM] |
| **httpx** | latest | Fetch org-wide guidance from remote URLs/repos (the "called externally" customization layer, pre-MCP) | The "pull guidance from remote URLs now, evolve to MCP later" requirement. Async, matches the SDK's async model. [HIGH] |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Env, lock, build, publish | `uv init --lib`, `uv build`, `uv publish`. Single source of truth. |
| **ruff** | Lint + format | 2026 default; replaces black+isort+flake8; configure in `pyproject.toml`. |
| **pytest** + **pytest-asyncio** | Tests (SDK is async) | `pytest-asyncio` required to test the async drafting loop. |
| **mypy** or **pyright** | Type checking | Typer + Pydantic give strong types; enforce them. |
| **Workshop SDK (sdkcraft)** | Optional packaging-as-Workshop-SDK + repeatable deploy/doc-test container | PROJECT.md adopts Workshop to "contain documentation tests and define the repeatable deployment model." Treat as a *delivery wrapper* around the pip-installable package, not a replacement for it. [MEDIUM — org-specific tooling] |

## Installation

# pyproject.toml (excerpt)

# Dev setup (uv golden path)

# uv publish    # when distributing

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| github-copilot-sdk (Python lib, JSON-RPC) | Shelling out to `copilot -p … -s` and parsing stdout | Only as a *fallback* if the SDK transport is broken (issue #1606) or in a constrained CI where the SDK can't manage the CLI. The seam should make either path swappable. [HIGH] |
| Copilot SDK as the backend | Claude Agent SDK (`claude-agent-sdk`) / `opencode-agent-sdk` | These are the **seam's future adapters**. `opencode-agent-sdk` is explicitly a *drop-in replacement for `claude_agent_sdk`* and is provider-agnostic — strong evidence the port should mirror that shape (sessions, tools, MCP, skills). Swap to them if Copilot cost/availability/policy changes. [MEDIUM] |
| MyST Markdown | reStructuredText (rST) | Use rST when a project's existing docs are already rST, or for the few constructs where rST is terser. Sphinx reads both, so mixing is fine; default new drafted pages to MyST. [HIGH] |
| uv + hatchling | PDM, Poetry, setuptools | Use Poetry/PDM only if the org already standardizes on them. setuptools only for legacy. None offer uv's speed + unified flow in 2026. [HIGH] |
| Typer | Click, argparse | Click if you need its plugin ecosystem or dislike the type-hint magic; argparse only to avoid any dependency. Typer wins on DX for a new tool. [HIGH] |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Scraping `copilot` CLI stdout as the *primary* integration | No documented JSON/structured output; brittle to formatting changes; `--headless --stdio` was removed once already | The `github-copilot-sdk` typed JSON-RPC client |
| Floating/unpinned `github-copilot-sdk` **and** an unpinned Copilot CLI | The CLI auto-updates and has silently broken SDK transport (issue #1606, closed "not planned") | Pin both; gate upgrades behind a smoke test of the drafting loop |
| Building your own agent loop / tool-dispatch / provider client | PROJECT.md: "build the drafting layer, not agent machinery"; duplicates the SDK and bloats the thin core | The SDK's session + `@define_tool` + MCP primitives |
| Leaking Copilot types (CopilotClient, SessionConfig) across the whole codebase | Defeats the cheap-swap premise; makes Claude/opencode adoption a rewrite | A narrow port interface (e.g. `DraftingBackend`) with a single Copilot adapter |
| Poetry/Pipenv for a new distributable lib in 2026 | Slower, divergent from the uv/pyproject golden path | uv + hatchling |
| Persistent agent memory (Cognee/mem0), RAG index build | Explicitly out of scope / spike-gated in PROJECT.md (Mode-B-facing) | Steering-first; remote-URL guidance via httpx now, MCP-served guidance later |
| Heavy rST-first authoring for AI-emitted content | Whitespace-strict rST raises malformed-output rate from a model | MyST Markdown with `colon_fence` |

## Stack Patterns by Variant

- Use `httpx` to fetch org-wide guidance from a URL/repo and layer it into the system message / a SKILL.md injected per session.
- Because PROJECT.md keeps the reusable core *decoupled* from the guidance it consumes.
- Mount it as an MCP server via `create_session(mcpServers={...})` — no change to the drafting layer's shape.
- Because the Copilot SDK already supports per-session MCP; the migration is config, not code.
- Prefer the SDK with the CLI in managed/stdio mode; if blocked, fall back to `copilot -p "…" -s --no-ask-user --deny-tool ...` behind the same port interface.
- Because the seam should hide whether the backend is the SDK or the CLI binary.
- Keep the pip-installable package as the artifact of record; wrap it with sdkcraft for the doc-test container / deployment model.
- Because Workshop is adopted for "documentation tests and the repeatable deployment model," not as the distribution primitive.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `github-copilot-sdk==1.0.2` | a **specific** Copilot CLI version | The SDK drives the CLI runtime over JSON-RPC; CLI auto-updates have broken transport (#1606). **Pin the CLI**; re-verify on every SDK bump. [HIGH] |
| `github-copilot-sdk` | Python ≥ 3.11 | SDK floor. [HIGH] |
| `sphinx==9.1.0` | Python ≥ 3.12 | Docs toolchain floor — drives the project target to 3.12. [HIGH] |
| `myst-parser==5.1.0` | Sphinx 9.x | Confirm exact Sphinx range in MyST changelog at build time (MyST tracks Sphinx majors closely). [MEDIUM] |
| `sphinx-design` (2026-01) | MyST + `colon_fence` enabled | Needs `myst_enable_extensions = ["colon_fence"]`. [MEDIUM] |

## Sources

- GitHub Docs — *Running Copilot CLI programmatically* & *CLI programmatic reference* (flags, env vars, no JSON output) — [HIGH]
- GitHub Docs — *Custom agents configuration* (agent profiles, `mcp-servers`, `tools` fields) — [HIGH]
- GitHub Docs — *Adding agent skills for Copilot CLI* / *About agent skills* + GitHub Changelog (2025-12-18 Agent Skills) — open cross-agent SKILL.md standard — [HIGH]
- GitHub Docs — *Copilot SDK getting started* + Changelog *Copilot SDK GA 2026-06-02* — languages, JSON-RPC, `CopilotClient`, `@define_tool`, MCP, BYOK — [HIGH]
- PyPI — `github-copilot-sdk` **1.0.2** (2026-06-18, Python ≥3.11, `[telemetry]` OTel extra) — [HIGH]
- GitHub issue `github/copilot-cli#1606` — `--headless --stdio` removed, breaks SDK, closed "not planned" — stability risk — [HIGH, verified/unresolved]
- Claude Agent SDK (Python) — `@tool` + `create_sdk_mcp_server`, Agent Skills — seam adapter reference — [MEDIUM]
- `opencode-agent-sdk` (PyPI) — provider-agnostic, drop-in for `claude_agent_sdk` — seam adapter reference — [MEDIUM]
- PyPI / official — Sphinx **9.1.0**, myst-parser **5.1.0**, furo **2025.12.19**, sphinx-design (2026-01) — [HIGH]
- Read the Docs — MyST vs rST migration guidance & Diátaxis endorsement; diataxis.fr — [HIGH]
- uv docs (build backend, project init) + 2026 packaging guides — uv+hatchling+src layout golden path — [HIGH]
- Typer (fastapi/typer) + 2026 CLI comparison — type-hint CLI recommendation — [HIGH]

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
