# Stack Research

**Domain:** Platform-thin agentic documentation-drafting framework — a distributable Python package that rides on the GitHub Copilot SDK (behind a thin abstraction seam) and outputs Sphinx-publishable content for GitHub + Read the Docs.
**Researched:** 2026-06-19
**Confidence:** MEDIUM-HIGH (Copilot SDK surface verified against official GitHub Docs + PyPI + changelog; Sphinx/packaging stack HIGH; versions of a fast-moving SDK flagged where they may drift)

> **How to read this file.** Every recommendation carries a confidence tag and a "Why / Why not" rationale. The Copilot SDK is a *fixed* decision (see PROJECT.md Key Decisions) — this file does NOT re-litigate it; it documents the SDK's real programmatic surface, its gotchas, and the seam that keeps a swap cheap. Versions of GitHub's Copilot SDK/CLI move weekly; pin and re-verify at implementation time (see "Version Compatibility" and PITFALLS).

---

## Critical context: there is a real Copilot SDK, not just a CLI [HIGH]

The whole drafting layer rides on this, so it is addressed first and explicitly.

**GitHub Copilot SDK is GA (general availability) as of 2026-06-02.** It is a multi-language SDK — TypeScript/Node, **Python**, Go, Rust, Java, and .NET (C#) — that exposes *the same agent runtime that powers Copilot CLI*, as an importable library. You do **not** have to shell out to the `copilot` binary and scrape stdout.

- **Python package:** `github-copilot-sdk` — **v1.0.2, released 2026-06-18**, requires **Python ≥ 3.11**. Import surface is `from copilot import CopilotClient` and `from copilot.session import PermissionHandler`. (Verified on PyPI + GitHub Docs.)
- **How it works:** the SDK talks to the Copilot CLI runtime over **JSON-RPC**. By default the SDK auto-manages the CLI process lifecycle (bundled binary, stdio). You can also run the CLI in server mode (`copilot --headless --port 4321`) and connect via `RuntimeConnection.for_uri(...)` / `for_tcp(...)` / `for_stdio(...)`.
- **Async-first:** context-manager + `async`/`await` API. Core flow:
  ```python
  async with CopilotClient() as client:
      async with await client.create_session(
          on_permission_request=PermissionHandler.approve_all,  # <-- our HITL gate hooks here
          model="gpt-5",
      ) as session:
          await session.send("Draft a how-to for feature X from these sources…")
  ```

### Copilot SDK — MCP support [HIGH]
MCP is first-class. MCP servers are configured **per session** via the `mcpServers` field on `SessionConfig` / `create_session(...)` (typed entries: `type: "http" | "stdio" | "sse"`, `url`/`command`). They can also be scoped per **custom agent** (`mcp-servers` in an agent profile) and at the repo level (`~/.copilot/mcp-config.json`). This directly supports the project's "evolve org guidance toward MCP-served guidance later" requirement — guidance becomes an MCP server the session mounts.

### Copilot SDK / CLI — custom tools support [HIGH]
The SDK registers **in-process custom tools** with the `@define_tool` decorator (Python); parameters use **Pydantic** schema generation. This is how the drafting layer exposes bounded, safe tools (e.g. `read_source_file`, `list_repo_paths`) without giving the agent unrestricted shell — matching the "stays dumb outside drafting" border.

### Copilot — Agent Skills support [HIGH]
Copilot supports **Agent Skills (SKILL.md)** — announced 2025-12-18, with skills usable across Copilot in VS Code, **Copilot CLI**, and the cloud agent. **Agent Skills is an open, cross-agent standard:** skills live in `.github/skills`, `.claude/skills`, or `.agents/skills` (project) and `~/.copilot/skills` or `~/.agents/skills` (personal); the relevant `SKILL.md` is injected into context when its description matches. **This is strategically important:** the same SKILL.md works for Copilot today and the Claude Agent SDK later, so the org's drafting skills (and the `skills-playground` / `AI-resources-for-docs` resources the project commits back to) are **portable across the abstraction seam** rather than locked to one vendor.

### Copilot CLI — programmatic/headless surface (fallback seam) [HIGH]
If/when the SDK path is unavailable, the CLI itself is scriptable: `copilot -p/--prompt "…"` (single-shot, exits when done), `-s` (silent — clean text for piping), `--no-ask-user`, `--model`, `--agent`, allow/deny controls (`--allow-tool`, `--deny-tool`, `--allow-url`, `--add-dir`, `--allow-all`/`--yolo`), `--secret-env-vars` (redaction), `--share`/`--share-gist` (transcript export — a free provenance artifact). Auth via `COPILOT_GITHUB_TOKEN` > `GH_TOKEN` > `GITHUB_TOKEN`. **No documented structured/JSON output** — another reason to prefer the SDK (typed events) over CLI-stdout scraping.

### Stability gotcha you must design around [HIGH — verified, unresolved]
GitHub Copilot CLI **removed `--headless --stdio` without deprecation** (~CLI v0.0.410+), breaking older `@github/copilot-sdk` (0.1.x preview) downstream; the issue (`github/copilot-cli#1606`) was closed "not planned." The replacement is the ACP protocol. **Takeaway:** the CLI auto-updates and can break the SDK's transport with no notice. Mitigations: (1) **pin the CLI version** the SDK drives, (2) keep the abstraction seam thin (this whole project's premise), (3) treat "Copilot drafting backend unavailable" as an expected, handled state. This is the single biggest stack risk — flagged for PITFALLS.

---

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

```toml
# pyproject.toml (excerpt)
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "doc-drafter"            # working name
requires-python = ">=3.12"      # 3.12 to satisfy Sphinx 9.x; SDK floor is 3.11
dependencies = [
  "github-copilot-sdk==1.0.2",  # PIN — underlying CLI auto-updates can break transport
  "typer",
  "pydantic>=2",
  "httpx",
]

[project.optional-dependencies]
docs = ["sphinx==9.1.0", "myst-parser==5.1.0", "furo", "sphinx-design"]
telemetry = ["github-copilot-sdk[telemetry]"]
dev = ["pytest", "pytest-asyncio", "ruff", "pyright"]

[project.scripts]
doc-drafter = "doc_drafter.cli:app"   # Typer app -> console command on PATH
```

```bash
# Dev setup (uv golden path)
uv init --lib
uv add github-copilot-sdk==1.0.2 typer pydantic httpx
uv add --optional docs sphinx==9.1.0 myst-parser==5.1.0 furo sphinx-design
uv add --dev pytest pytest-asyncio ruff pyright
uv build        # produces wheel + sdist
# uv publish    # when distributing
```

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

**If org guidance is consumed remotely (now, pre-MCP):**
- Use `httpx` to fetch org-wide guidance from a URL/repo and layer it into the system message / a SKILL.md injected per session.
- Because PROJECT.md keeps the reusable core *decoupled* from the guidance it consumes.

**If org guidance evolves to MCP-served (later):**
- Mount it as an MCP server via `create_session(mcpServers={...})` — no change to the drafting layer's shape.
- Because the Copilot SDK already supports per-session MCP; the migration is config, not code.

**If you must run in CI / fully headless:**
- Prefer the SDK with the CLI in managed/stdio mode; if blocked, fall back to `copilot -p "…" -s --no-ask-user --deny-tool ...` behind the same port interface.
- Because the seam should hide whether the backend is the SDK or the CLI binary.

**If packaging as a Workshop SDK for repeatable deployment:**
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
  - https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically
  - https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference
- GitHub Docs — *Custom agents configuration* (agent profiles, `mcp-servers`, `tools` fields) — [HIGH]
  - https://docs.github.com/en/copilot/reference/custom-agents-configuration
- GitHub Docs — *Adding agent skills for Copilot CLI* / *About agent skills* + GitHub Changelog (2025-12-18 Agent Skills) — open cross-agent SKILL.md standard — [HIGH]
  - https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
  - https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/
- GitHub Docs — *Copilot SDK getting started* + Changelog *Copilot SDK GA 2026-06-02* — languages, JSON-RPC, `CopilotClient`, `@define_tool`, MCP, BYOK — [HIGH]
  - https://docs.github.com/en/copilot/how-tos/copilot-sdk/getting-started
  - https://github.blog/changelog/2026-06-02-copilot-sdk-is-now-generally-available/
- PyPI — `github-copilot-sdk` **1.0.2** (2026-06-18, Python ≥3.11, `[telemetry]` OTel extra) — [HIGH]
  - https://pypi.org/project/github-copilot-sdk/
- GitHub issue `github/copilot-cli#1606` — `--headless --stdio` removed, breaks SDK, closed "not planned" — stability risk — [HIGH, verified/unresolved]
  - https://github.com/github/copilot-cli/issues/1606
- Claude Agent SDK (Python) — `@tool` + `create_sdk_mcp_server`, Agent Skills — seam adapter reference — [MEDIUM]
  - https://platform.claude.com/docs/en/agent-sdk/python
- `opencode-agent-sdk` (PyPI) — provider-agnostic, drop-in for `claude_agent_sdk` — seam adapter reference — [MEDIUM]
  - https://pypi.org/project/opencode-agent-sdk/
- PyPI / official — Sphinx **9.1.0**, myst-parser **5.1.0**, furo **2025.12.19**, sphinx-design (2026-01) — [HIGH]
  - https://pypi.org/project/sphinx/ , https://pypi.org/project/myst-parser/
- Read the Docs — MyST vs rST migration guidance & Diátaxis endorsement; diataxis.fr — [HIGH]
  - https://docs.readthedocs.com/platform/stable/guides/migrate-rest-myst.html , https://diataxis.fr/start-here/
- uv docs (build backend, project init) + 2026 packaging guides — uv+hatchling+src layout golden path — [HIGH]
  - https://docs.astral.sh/uv/concepts/build-backend/
- Typer (fastapi/typer) + 2026 CLI comparison — type-hint CLI recommendation — [HIGH]
  - https://github.com/fastapi/typer

---
*Stack research for: platform-thin agentic doc-drafting framework on the GitHub Copilot SDK → Sphinx/RTD output, distributed as a Python package*
*Researched: 2026-06-19*
