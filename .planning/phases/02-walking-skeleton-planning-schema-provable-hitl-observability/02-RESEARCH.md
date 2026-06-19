# Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability - Research

**Researched:** 2026-06-19
**Domain:** Agentic doc-drafting walking skeleton — `github-copilot-sdk` adapter, OTel/Logfire observability, F1 on-disk schema (Pydantic+YAML), Sphinx/MyST publish proof, import-linter seam enforcement
**Confidence:** HIGH for the SDK API (verified against the unpacked 1.0.2 wheel), HIGH for the docs/observability stack (PyPI-verified), MEDIUM for the exact built-in read-only tool names (filter mechanism verified; canonical names need one runtime confirmation)

## Summary

This phase wires the first real end-to-end loop on top of the Phase-1 hexagonal scaffold. The single highest-value finding: **I downloaded and unpacked the real `github-copilot-sdk==1.0.2` wheel and read its actual source**, so the API names in CONTEXT.md and ARCHITECTURE.md can now be corrected from illustration to verified fact. The SDK is **async-first**, `create_session` is a coroutine, tool allowlisting uses **source-qualified filter strings** (`builtin:grep`, not bare `"grep"`), `reasoning_effort` is `Literal["low","medium","high","xhigh"]`, and the draft text arrives as `AssistantMessageData.content` (carrying `.model` and `.output_tokens` — direct provenance inputs). The SDK is **not installed** in this repo's venv; the planner must add an `uv add github-copilot-sdk==1.0.2` task plus the Copilot-CLI pin (D-27).

The observability path (D-20/21/22) is clean: instrument `core/` against the **OpenTelemetry API** (`opentelemetry-api==1.42.1`), and configure **Logfire 4.37.0** with `send_to_logfire=False` as the local OTel backend. The SDK already propagates W3C trace context (`copilot._telemetry.get_trace_context` → `traceparent`), so minting the `run_id` from the active OTel trace id and stamping it into `provenance.yaml.generations[].run_id` is the natural OBS-03 correlation. The docs proof (D-43) is unblocked: **myst-parser 5.1.0 requires `sphinx<10,>=8`**, so Sphinx 9.1.0 is in range; Python floor is 3.12 (matches the project).

**Primary recommendation:** Build the loop mock-first (the mock provider is the CI-runnable proof and the second-provider swap evidence), confine every SDK symbol to `adapters/copilot/`, enforce the seam with `import-linter` layered contracts, and treat the real SDK run as a manual local smoke test that never enters CI (D-24). Correct ARCHITECTURE.md's illustrative API names against the verified surface in this document.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Observability (OBS-01/02/03)**
- **D-20** — Instrument core via the OTel API, not the SDK's telemetry; provider-independent layer lives in `core/`, layered on top of what the SDK emits.
- **D-21** — Concrete local backend = Logfire in local mode (`send_to_logfire=False`); chosen over pure OTel-SDK+ConsoleSpanExporter for DX; OTel API abstraction keeps the exporter swappable.
- **D-22** — Run↔provenance correlation via a shared `run_id` (the OTel trace id, or derived) stamped into the matching `provenance.yaml` `generations[]` entry.

**Provider seam, mock & SDK pin (SEAM-03/04, SKEL-04/05)**
- **D-23** — Ship the real Copilot adapter AND a deterministic `MockDraftingProvider` (canned deterministic `DraftResult` + synthetic provenance) so the port and full loop run in CI without the SDK.
- **D-24** — Acceptance proof = mock in CI + real local smoke. Real SDK run is a manual local smoke test (SKEL-05), demonstrated once (capture as evidence), kept OUT of CI; it gates SDK/CLI version bumps.
- **D-25** — Provider selection by explicit choice, defaulting to Copilot. CLI flag `--provider copilot|mock` + env/config fallback; CI/tests use `mock`. No runtime plugin discovery.
- **D-26** — SEAM-04 = design-only. Port documented Copilot-agnostic (domain verbs, no SDK shapes leaking). The mock IS the second provider that proves swappability. OpenCode SDK / Pydantic AI named, not built.
- **D-27** — Pin both `github-copilot-sdk==1.0.2` and a compatible Copilot CLI; handle "backend unavailable" as a handled, non-crashing state (clear message, nonzero exit) — SKEL-05.
- **D-28** — Bounded read-only toolset = `grep` / `glob` / `view` only (SKEL-04). No write/exec/network; enforced via the SDK's per-agent `tools` allowlist + session `excludedTools`.
- **D-29** — Upgrade seam enforcement to `import-linter` now the SDK is a real dependency. *(Confirm at planning whether to keep the AST check as belt-and-braces.)*

**Dogfood target & output layout (PLAN-01, SKEL-01/02)**
- **D-30** — Dogfood THIS repo. `.planning/` is excluded from source-lookup and NEVER written to. Agent sources = `src/dogen/**`, `README.md`, `AGENTS.md`, `pyproject.toml`.
- **D-31** — Output layout: audit surface in `.dogen/units/<unit-id>/`, drafted MyST `.md` under `docs/` (the Sphinx root).
- **D-32** — First unit = a reference/explanation page about dogen (e.g. CLI usage or the provider seam). Exact unit/title is a planning detail.

**F1 schema v0 (PLAN-01..07)**
- **D-33** — Per-unit directory `.dogen/units/<unit-id>/` with `unit.md` + `provenance.yaml` + `progress.yaml`. YAML front-matter + Markdown body; git-diffable.
- **D-34** — `schema_version` integer (`0`) at the top level of each machine-readable file.
- **D-35** — `unit.md` front-matter = editable steering+plan artifact: `unit_id`, `intent` (reference|tutorial|how-to|explanation — DIRECTION), `audience`, `title`, `sources` (human-pointed, list of `{path|ref}`), `sphinx_target`, `steering_notes`, `status`. Operator authors by hand.
- **D-36** — `provenance.yaml` = consolidated audit record. Blocks: `steering:` `{author, at, intent, audience}` (stamped by `dogen steer`); `generations[]` `{model, model_version, effort, tooling_version, sdk, context_origins, tools_used, run_id, at, action}`; `reviewer_edits[]` `{at, reviewer, summary}`; `verification:` reserved/empty (`steps: []`, each `{id, state: unverified, evidence: null, env_fingerprint: null}`).
- **D-37** — `sources` (human-pointed, in `unit.md`) and `context_origins` (agent-actually-read, in `provenance.yaml`) are two distinct fields. Never collapse them.
- **D-38** — `progress.yaml` lifecycle = `pending → sourced → drafted → reviewed → committed`, with `schema_version`, `unit_id`, `state`, `history[]` of `{at, state}`. Loop auto-advances `pending→sourced→drafted`; `dogen review` sets `reviewed`; the tool NEVER sets `committed`.

**Provable HITL gate (HITL-01/02)**
- **D-39** — "Recorded steering" = explicit `dogen steer` event; stamps `{author, at}` + steered intent/audience into `provenance.yaml.steering`.
- **D-40** — `dogen draft` hard-refuses without a recorded steering event (HITL-01): clear message + nonzero exit, no draft.
- **D-41** — Author + timestamp captured from git config (`user.name`/`user.email`) at `dogen steer` / `dogen review` time.

**CLI command surface (SKEL-01, UX)**
- **D-42** — Four thin Typer subcommands: `dogen unit new <id>` → `dogen steer <id>` → `dogen draft <id>` → `dogen review <id> --note "..."`. PLAN-05/06 exercised end-to-end. CLI stays thin.

**Sphinx-publishable proof & docs toolchain (SKEL-02; resolves D-17)**
- **D-43** — Prove publishability with a real, minimal Sphinx build in CI. `docs/conf.py` + `.readthedocs.yaml` configured for MyST + `colon_fence` (Sphinx 9.1.0 / myst-parser 5.1.0, Python 3.12); CI job actually builds the drafted page.

**Licensing follow-on**
- **D-44** — A docs/content license decision goes live. Drafted `.md` under `docs/` needs SPDX headers for `reuse lint`. Lean `CC-BY-SA-4.0` — but first reconcile the policy's own `CC-BY-NC-SA-4.0` inconsistency. Resolve at planning.

### Claude's Discretion
- Exact OTel span names/attributes and Logfire configuration details.
- The mock provider's canned draft content/shape (must be deterministic).
- Provider-selection precedence (flag vs env vs config).
- Exact wording/fields of the `unit.md` scaffold template.
- Progress/streaming UX during a draft run.
- The smoke-test harness layout and how it gates SDK/CLI bumps.
- Whether to keep the Phase-1 AST seam check alongside `import-linter` (D-29).
- Precise sub-module layout inside `core/` and `adapters/`.

### Deferred Ideas (OUT OF SCOPE)
- Steering layering org→repo→writer (STEER-01) — `steering/resolver.py` merge; v2.
- Type-aware breadth across all four intents — skeleton drives ONE intent path via prompting.
- SDLC connectors (CONN-01) — `sources[].ref` reserved only.
- DOCPR-2822 `QaHook` extension point (CONN-03).
- Singular-traceable-local-commit border (STEER-03) — `progress` reserves `committed` but the tool never sets it.
- Actionable-content verification execution (VERIFY-01/02) — fields reserved, empty.
- RAG / context-augmentation — spike-gated; do-not-build.
- Real second provider adapter — design-only (D-26).
- Dependency-update bot (Renovate/Dependabot) — confirm at planning whether it lands this phase or next.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SKEL-01 | Operator defines a unit + points at sources | `dogen unit new` scaffolds `unit.md`; `sources[]` front-matter (D-35). Typer 0.26.7 verified. |
| SKEL-02 | Agent drafts into Sphinx-publishable MyST via CLI→orchestrator→adapter | SDK `create_session`/`send_and_wait` verified; MyST+Sphinx build verified compatible. |
| SKEL-03 | Output only, stop before any commit | `progress.yaml` has no commit/push/build states (D-38); no git-write code in the loop. |
| SKEL-04 | Bounded read-only toolset (grep/glob/view) | `available_tools`/`excluded_tools` filter verified; source-qualified `builtin:` names (see Pitfall 1). |
| SKEL-05 | Pinned SDK + CLI; backend-unavailable handled | `CopilotClient.get_status()`/`get_auth_status()` + `StopError` verified for graceful handling. |
| SEAM-03 | `DraftingProvider` port shaped by domain verbs; mock proves swap | Port = domain verbs; `MockDraftingProvider` returns canned `DraftResult` (D-23). |
| SEAM-04 | Multi-provider by design; alternates named | Design-only doc; mock is the proof (D-26). |
| PLAN-01 | Per-unit planning directory on disk | `adapters/planning_fs.py` over `.dogen/units/` (D-31/33). |
| PLAN-02 | `schema_version` field | Integer `0` at top level of each file (D-34). |
| PLAN-03 | `unit.md` records intent+audience+steering+sources | Pydantic model + YAML front-matter (D-35). |
| PLAN-04 | `provenance.yaml` per-generation record | `AssistantMessageData.content/.model/.output_tokens` + SDK `__version__` feed it (D-36). |
| PLAN-05 | `provenance.yaml` reviewer edits | `dogen review --note` appends `reviewer_edits[]` (D-36/42). |
| PLAN-06 | `progress.yaml` lifecycle, stops at committed | State machine in `core/models.py` (D-38). |
| PLAN-07 | Reserve verification evidence fields | `verification.steps[]` reserved empty (D-36). |
| HITL-01 | Refuse to draft without recorded steering | `dogen draft` checks `provenance.yaml.steering` exists; nonzero exit (D-40). |
| HITL-02 | Recorded steering captures author + timestamp | git-config author + UTC timestamp at `dogen steer` (D-41). |
| OBS-01 | Provider-independent instrumentation in core | OTel API spans in `core/orchestrator.py` (D-20). |
| OBS-02 | Concrete backend wired locally | Logfire `configure(send_to_logfire=False)` (D-21). |
| OBS-03 | Run correlates with provenance generation entry | OTel trace id → `run_id` → `generations[].run_id` (D-22). |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parse/validate `unit.md` front-matter | `core/` models (Pydantic) | `adapters/planning_fs.py` (YAML I/O) | Domain schema is pure; file read/write is an adapter concern (PlanningStore port). |
| Drive ONE draft pass | `core/orchestrator.py` | `adapters/copilot/provider.py` | Orchestration is domain logic; SDK calls live behind the DraftingProvider port. |
| Talk to Copilot SDK/CLI | `adapters/copilot/` | — | Single SDK isolation point (SEAM-01/02 invariant; import-linter enforced). |
| Bounded read-only tools | `adapters/copilot/tools.py` | — | Tool allowlist is SDK-shaped; `core/` only names the *capability*, not tool strings. |
| Emit traces/spans/metrics | `core/` (OTel API) | Logfire backend wiring (composition root) | OBS-01 mandates instrumentation independent of the SDK; backend is swappable. |
| Mint `run_id`, stamp provenance | `core/orchestrator.py` | `adapters/planning_fs.py` (write) | run_id is derived from the OTel trace the core owns (OBS-03). |
| HITL steering gate | `core/orchestrator.py` (refuse logic) | `cli/` (surface message/exit) | Gate is a domain invariant; CLI only reports it. |
| git-config author capture | `adapters/` (e.g. `git_identity.py`) | `cli/` | Shelling to `git config` is host I/O — not a `core/` concern; keep behind a tiny adapter. |
| Sphinx build | CI / docs toolchain | `.readthedocs.yaml` | Build is external to the package; the framework only emits the `.md`. |

## Standard Stack

### Core (new dependencies this phase)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| github-copilot-sdk | 1.0.2 (pin exact) | The drafting backend; confined to `adapters/copilot/` | Fixed decision; GA, Python-native, async, typed events, in-process tools. `[VERIFIED: PyPI + unpacked wheel]` |
| typer | 0.26.7 | CLI framework (four thin subcommands) | Type-hint CLI, best DX; fixed in STACK.md. `[VERIFIED: PyPI]` |
| pydantic | 2.13.4 (`>=2`) | F1 schema models + SDK `@define_tool` param schemas | One validation layer for tool params and on-disk schema. `[VERIFIED: PyPI]` |
| opentelemetry-api | 1.42.1 | Provider-independent instrumentation in `core/` (D-20) | The vendor-neutral instrumentation API; keeps OBS-01 true. `[VERIFIED: PyPI]` |
| logfire | 4.37.0 | Local OTel backend (D-21), `send_to_logfire=False` | Pydantic-native OTel backend; bundles `opentelemetry-sdk 1.39–1.42`. `[VERIFIED: PyPI]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sphinx | 9.1.0 | Docs build engine (D-43) | `docs` optional-dependency group; CI build job. `[VERIFIED: PyPI, py>=3.12]` |
| myst-parser | 5.1.0 | MyST Markdown parsing + `colon_fence` | `docs` group; requires `sphinx<10,>=8` → 9.1.0 OK. `[VERIFIED: PyPI requires_dist]` |
| furo | 2025.12.19 | Sphinx HTML theme (optional, local HTML review) | Only if rendering HTML locally; RTD can theme. `[VERIFIED: PyPI]` |
| import-linter | 2.11 | Layered/forbidden-import contracts for the seam (D-29) | `dev` group; new CI gate. `[VERIFIED: PyPI]` |
| PyYAML | 6.0.3 (installed) | Read/write `provenance.yaml` / `progress.yaml` (machine-written) | Already in the venv; fine for tool-written files. `[VERIFIED: venv]` |
| ruamel.yaml | 0.19.1 | Round-trip-preserving YAML for human-edited `unit.md` front-matter | See "Don't Hand-Roll" — only if comment/order preservation on hand-edited files matters. `[VERIFIED: PyPI]` |
| opentelemetry-sdk | 1.42.1 | Pulled transitively by logfire (1.39–<1.43 range) | Do not pin separately unless you wire a raw exporter; logfire owns the SDK. `[VERIFIED: PyPI]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| logfire (D-21) | `opentelemetry-sdk` + `ConsoleSpanExporter` | Pure-OTel, one fewer dep, but worse DX; D-21 chose Logfire deliberately. The OTel API abstraction means swapping later is a composition-root change only. |
| ruamel.yaml for `unit.md` | PyYAML everywhere | PyYAML drops comments/key order on round-trip. Since the operator hand-authors `unit.md`, ruamel preserves their formatting on machine `status` updates. If the tool only ever *reads* `unit.md` front-matter (never rewrites it), PyYAML suffices and ruamel is unnecessary. **Decide based on whether `dogen` rewrites `unit.md`.** |
| Typer | Click / argparse | Fixed by STACK.md; Typer's type-hint model fits the thin-CLI + "good UX" requirement. |

**Installation:**
```bash
uv add github-copilot-sdk==1.0.2 typer 'pydantic>=2' opentelemetry-api logfire
uv add --optional docs sphinx==9.1.0 myst-parser==5.1.0 furo
uv add --dev import-linter
# ruamel.yaml only if dogen rewrites unit.md front-matter:
# uv add ruamel.yaml
```

**Version verification (this session):** all versions above fetched live from the PyPI JSON API on 2026-06-19. `github-copilot-sdk` 1.0.2 wheel was downloaded and unpacked to read the real API. The repo venv currently contains **none** of these runtime deps — only dev tooling (ruff, ty, pytest, pytest-asyncio, pre-commit) and PyYAML.

## Package Legitimacy Audit

| Package | Registry | Latest / Pinned | Source Repo | Verdict | Disposition |
|---------|----------|-----------------|-------------|---------|-------------|
| github-copilot-sdk | PyPI | 1.0.2 | github.com/github/copilot-sdk | OK* | Approved (fixed decision; wheel inspected) |
| logfire | PyPI | 4.37.0 | github.com/pydantic/logfire | OK* | Approved |
| sphinx | PyPI | 9.1.0 | sphinx-doc.org | OK | Approved |
| myst-parser | PyPI | 5.1.0 | github.com/executablebooks/MyST-Parser | OK | Approved |
| opentelemetry-api | PyPI | 1.42.1 | github.com/open-telemetry/opentelemetry-python | OK | Approved |
| opentelemetry-sdk | PyPI | 1.42.1 | github.com/open-telemetry/opentelemetry-python | OK | Approved (transitive via logfire) |
| import-linter | PyPI | 2.11 | github.com/seddonym/import-linter | OK | Approved |
| typer | PyPI | 0.26.7 | github.com/fastapi/typer | OK | Approved |
| pydantic | PyPI | 2.13.4 | github.com/pydantic/pydantic | OK | Approved |
| ruamel.yaml | PyPI | 0.19.1 | sourceforge.net/projects/ruamel-yaml | OK | Approved (conditional — see ruamel note) |
| furo | PyPI | 2025.12.19 | github.com/pradyunsg/furo | OK | Approved (optional) |

\* The `gsd-tools package-legitimacy` seam flagged `github-copilot-sdk` and `logfire` as `SUS` for reasons **`too-new` / `unknown-downloads`**. These are artifacts of the registry returning the *latest release date* and null weekly-download counts, **not** genuine slop signals: both have authentic first-party source repos (github/copilot-sdk, pydantic/logfire), both are named in the project's own fixed-decision STACK.md, and the SDK wheel was downloaded and its source read in this session. **No package removed; no checkpoint required.** All package names here originate from the project's verified STACK.md / official docs, not from WebSearch guesses.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none requiring action (the two seam flags are registry-metadata artifacts, dispositioned above)

## VERIFIED Copilot SDK API (`github-copilot-sdk==1.0.2`)

> **Source: the unpacked 1.0.2 wheel** (`copilot/__init__.py`, `client.py`, `session.py`, `tools.py`, `_mode.py`, `generated/session_events.py`, `_telemetry.py`). This **supersedes ARCHITECTURE.md's illustrative names**, which were explicitly flagged as unverified. `[VERIFIED: unpacked wheel github_copilot_sdk-1.0.2]`

### Import surface
```python
from copilot import (
    CopilotClient, CopilotSession,
    PermissionHandler, Tool, ToolResult, define_tool,
    ToolSet, BUILTIN_TOOLS_ISOLATED,
    StopError, TelemetryConfig,
    MCPServerConfig, MCPHTTPServerConfig, MCPStdioServerConfig,
    SystemMessageConfig, SessionEvent, SessionEventType,
)
```
(`CopilotClient`, `create_session`, `send_and_wait`, `define_tool` all confirmed exported. Note: it is `from copilot import ...`, package distribution name `github-copilot-sdk`.)

### Client + session lifecycle (async-first)
- `CopilotClient(...)` is an **async context manager** (`async def __aenter__`). It manages the bundled CLI process.
- **`create_session` is a coroutine**: `async def create_session(self, *, ...) -> CopilotSession`. ARCHITECTURE.md's synchronous `self._client.create_session(...)` is **wrong** — it must be `await`ed.
- `CopilotSession` is also an async context manager (`__aenter__`/`__aexit__`).

```python
async with CopilotClient() as client:
    async with await client.create_session(
        model="gpt-5",
        reasoning_effort="medium",                 # Literal["low","medium","high","xhigh"]
        on_permission_request=PermissionHandler.approve_all,  # HITL hook (see note)
        excluded_tools=ToolSet().add_builtin(["bash", "str_replace_editor"]),  # source-qualified
        available_tools=ToolSet().add_builtin(["grep", "glob", "view"]),       # see Pitfall 1
        tools=[my_custom_tool],                    # list[Tool] from @define_tool
        working_directory="/path/to/repo",
    ) as session:
        final = await session.send_and_wait("Draft ...", timeout=60.0)  # -> SessionEvent | None
```

### Verified `create_session` keyword parameters (relevant subset)
| Param | Type | Maps to |
|-------|------|---------|
| `model` | `str | None` | model selection (provenance `model`) |
| `reasoning_effort` | `Literal["low","medium","high","xhigh"] | None` | effort (provenance `effort`) — **D-36 `effort` enum: include `xhigh`** |
| `reasoning_summary` | `Literal["none","concise","detailed"]` | reasoning verbosity |
| `tools` | `list[Tool] | None` | custom in-process tools from `@define_tool` |
| `available_tools` | `list[str] | ToolSet | None` | **allowlist** (D-28) — source-qualified strings |
| `excluded_tools` | `list[str] | ToolSet | None` | **denylist** (D-28) |
| `on_permission_request` | handler | the HITL permission hook |
| `system_message` | `SystemMessageConfig | None` | system prompt / intent steering |
| `mcp_servers` | `dict[str, MCPServerConfig] | None` | future MCP guidance (v2) |
| `working_directory` | `str | None` | the repo root to look up sources in |
| `streaming` | `bool | None` | enable streaming deltas |
| `enable_session_telemetry` | `bool | None` | SDK-side telemetry toggle (D-20 uses our own OTel regardless) |

### Sending + reading the draft
- `async def send(prompt, *, ...) -> str` (returns a message id; fire-and-forget + listen via `session.on(handler)`).
- `async def send_and_wait(prompt, *, timeout: float = 60.0, ...) -> SessionEvent | None` — **the simplest path for the skeleton**; returns the final event.
- Event subscription: `unsubscribe = session.on(handler)` where `handler: Callable[[SessionEvent], None]`.
- **The drafted text** is on the `assistant.message` event payload: `AssistantMessageData` with fields `content: str`, `message_id: str`, `model: str | None`, `output_tokens: int | None`. → `content` is the draft; `model`/`output_tokens` feed `provenance.yaml.generations[]` directly.
- Streaming deltas: `assistant.message_delta` → `AssistantMessageDeltaData.delta_content` (use for the progress UX in Claude's-discretion D).

### `SessionEventType` (the events the orchestrator may consume)
`session.start`, `session.error`, `session.idle`, `user.message`, `assistant.turn_start`, `assistant.message_start`, `assistant.message_delta`, **`assistant.message`**, `assistant.turn_end`, `assistant.usage`, `permission.completed`, … (full enum in `generated/session_events.py`).

### Custom tools — `define_tool`
```python
@define_tool(name="read_source_file", description="...", skip_permission=False)
def read_source_file(params: MyParams) -> ToolResult: ...
```
Signature: `define_tool(name=None, *, description=None, overrides_built_in_tool=False, skip_permission=False, defer=None)` and an overload taking `params_type: type[T]`. Returns a `Tool`. Params use Pydantic schema generation (matches the project's Pydantic-everywhere choice).

### Backend-unavailable handling (SKEL-05 / D-27)
- `async def get_status(self) -> GetStatusResponse` and `async def get_auth_status(self) -> GetAuthStatusResponse` exist on `CopilotClient` — call one before/around the draft to detect an unavailable/unauthenticated backend and return the clear-message-nonzero-exit state.
- `StopError` is exported — catch it (and connection failures from `__aenter__`) to convert a broken CLI transport (issue #1606) into the handled state rather than a crash.
- `async def list_models(self) -> list[ModelInfo]` is available if you want to validate the configured model before drafting.

### Telemetry interop (OBS-03 bonus)
`copilot._telemetry` exposes `get_trace_context() -> dict[str,str]` and `trace_context(traceparent, tracestate)` built on `opentelemetry.propagate`. **The SDK already speaks W3C trace context**, so a span the core opens (OTel API, D-20) can have its `traceparent` flow into the SDK call — meaning the `run_id` derived from the active OTel trace id genuinely spans both the core loop and the SDK's own emitted telemetry. This makes D-22/OBS-03 a first-class fit, not a bolt-on.

## Architecture Patterns

### System Architecture Diagram
```
  dogen unit new <id> ──► writes .dogen/units/<id>/unit.md  (operator then hand-edits)
                                   │
  dogen steer <id> ──────────────►│ reads unit.md front-matter (intent/audience/sources)
                                   │ git config user.{name,email} ──► stamps provenance.yaml.steering {author,at,intent,audience}
                                   ▼
  dogen draft <id> ──► [HITL GATE] provenance.yaml.steering present? ──no──► clear msg + exit≠0 (HITL-01)
                                   │ yes
                                   ▼
                          core/orchestrator (OTel span "draft", mints run_id from trace id)
                                   │  selects provider (D-25: copilot|mock)
            ┌──────────────────────┴───────────────────────┐
            ▼ provider=copilot                              ▼ provider=mock (CI)
   adapters/copilot/provider.py                     MockDraftingProvider
     await client.create_session(                     returns canned deterministic
        available_tools=builtin:grep/glob/view,         DraftResult + synthetic provenance
        excluded_tools=write/exec/net)
     await session.send_and_wait(prompt)
     AssistantMessageData.content/.model/.output_tokens
            └──────────────────────┬───────────────────────┘
                                   ▼  DraftResult (domain type — no SDK shapes)
                  PlanningStore (adapters/planning_fs.py) writes:
                    docs/<sphinx_target>.md   (the MyST draft)
                    .dogen/units/<id>/provenance.yaml  (generations[] += {run_id,...})
                    .dogen/units/<id>/progress.yaml    (pending→sourced→drafted)
                                   ▼
  dogen review <id> --note "..." ──► provenance.reviewer_edits[] += ; progress → reviewed  (STOP — never 'committed')
                                   ▼
  CI: sphinx-build docs/ (MyST+colon_fence, -W fail-on-warning)  proves SKEL-02
```

### Recommended Project Structure (fills the Phase-1 stubs)
```
src/dogen/
├── core/
│   ├── models.py         # Unit, Intent(enum), Audience, Steering, DraftResult, Provenance, Progress (Pydantic v2)
│   ├── ports.py          # DraftingProvider, SourceLookup, PlanningStore (Protocols)
│   ├── orchestrator.py   # the one drafting use-case; OTel spans; HITL gate; run_id
│   └── observability.py  # OTel API tracer/meter helpers (NO logfire import here — keep core backend-agnostic)
├── adapters/
│   ├── copilot/
│   │   ├── provider.py   # CopilotDraftingProvider (the ONLY SDK importer)
│   │   ├── tools.py      # bounded read-only toolset config (available/excluded)
│   │   └── mapping.py    # DraftResult ↔ AssistantMessageData (anti-corruption)
│   ├── mock_provider.py  # MockDraftingProvider (deterministic) — D-23
│   ├── planning_fs.py    # PlanningStore over .dogen/units/ + docs/
│   └── git_identity.py   # git config user.{name,email} (D-41) — host I/O kept out of core
├── obs/
│   └── logfire_backend.py# configure(send_to_logfire=False) — composition root wires it (D-21)
└── cli/
    └── main.py           # Typer app: unit/steer/draft/review — thin
docs/
├── conf.py               # MyST + colon_fence (D-43)
└── <sphinx_target>.md    # the drafted page lands here
.readthedocs.yaml
.dogen/units/<unit-id>/   # audit surface (runtime data, gitignore policy TBD at planning)
```
**Note on `.dogen/` vs `.planning/`:** ARCHITECTURE.md wrote the schema under `.planning/units/`; **CONTEXT.md D-31 overrides that to `.dogen/units/`** (because `.planning/` is GSD's and is excluded — D-30). Use `.dogen/`.

### Pattern 1: DraftingProvider port (domain verbs, not SDK shapes)
```python
# core/ports.py
from typing import Protocol
class DraftingProvider(Protocol):
    async def draft_unit(self, *, intent: "Intent", audience: "Audience",
                         steering: "Steering", sources: list["SourceRef"]) -> "DraftResult": ...
```
The port is **async** (the SDK is async; making the port sync would force `asyncio.run` inside the adapter and leak threading concerns). The mock implements the same async signature trivially.

### Pattern 2: Bounded read-only tools via source-qualified filters
```python
# adapters/copilot/tools.py — NOTE the builtin: prefix (verified requirement)
from copilot import ToolSet
READONLY = ToolSet().add_builtin(["grep", "glob", "view"])   # allowlist
DENY     = ToolSet().add_builtin(["bash", "str_replace_editor", "create"])  # belt-and-braces denylist
# create_session(available_tools=READONLY, excluded_tools=DENY)
```

### Pattern 3: OTel-in-core, Logfire-at-the-edge (keeps OBS-01 true)
```python
# core/observability.py — opentelemetry API ONLY, no backend import
from opentelemetry import trace
tracer = trace.get_tracer("dogen")
# orchestrator:
with tracer.start_as_current_span("dogen.draft") as span:
    run_id = format(span.get_span_context().trace_id, "032x")   # OBS-03 run_id
    span.set_attribute("dogen.unit_id", unit.unit_id)
    ...
# obs/logfire_backend.py — the ONLY logfire import; called from the composition root
import logfire
logfire.configure(send_to_logfire=False)   # local mode; Logfire installs an OTel SDK provider
```
This satisfies D-20 (core uses the OTel *API*) and D-21 (Logfire is the concrete backend) while keeping the backend swappable — `core/` never imports `logfire`.

### Anti-Patterns to Avoid
- **`create_session(...)` without `await`** — it is a coroutine; ARCHITECTURE.md's example is wrong.
- **Bare tool names** (`["grep"]`) in `available_tools` — they must be source-qualified (`builtin:grep`) or a `ToolSet`; passing a bare `str` raises `TypeError` by design.
- **Importing `logfire` in `core/`** — breaks OBS-01's "survives an SDK/backend swap"; import it only at the composition root.
- **Leaking `AssistantMessageData` / `SessionEvent` into `core/`** — translate to `DraftResult` in `adapters/copilot/mapping.py` (Anti-Pattern 1/2; Pitfall 4).
- **Letting `progress.yaml` gain a `committed`-setter** — the tool must never write `committed` (D-38, Pitfall 9).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Agent loop / tool dispatch / model calls | A custom JSON-RPC client or stdout scraper | `github-copilot-sdk` session API | The whole project premise; the SDK gives typed events + in-process tools. |
| Seam enforcement | A second bespoke AST walker | `import-linter` forbidden/layers contract (D-29) | Declarative, CI-native, catches `from copilot...` anywhere outside the adapter; the named D-09 upgrade. |
| Tracing/metrics plumbing | A custom logger with run-id threading | OTel API + Logfire backend | Standard, swappable, and the SDK already speaks W3C trace context. |
| YAML round-trip on human-edited `unit.md` | Manual front-matter splicing | ruamel.yaml (only if the tool rewrites `unit.md`) | Preserves operator comments/order; PyYAML silently drops them. |
| Front-matter + body split | A regex `---` parser | A small, tested front-matter splitter (or python-frontmatter if added) | Edge cases: CRLF, `---` inside body, empty front-matter. Keep it tiny and tested. |
| Schema validation | `dict.get(...)` everywhere | Pydantic v2 models with `schema_version` | One validation layer; D-34 migrations become explicit. |

**Key insight:** every line of agent machinery you write is a line the SDK already maintains and that the seam is supposed to hide. Build the *drafting layer and the F1 schema*, not the agent.

## Runtime State Inventory

> This is a greenfield feature phase (filling empty Phase-1 stubs), not a rename/refactor. Inventory included because the phase introduces new on-disk runtime state and a new external runtime (the Copilot CLI).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New `.dogen/units/<id>/` tree (unit.md, draft, provenance.yaml, progress.yaml) created at runtime. None pre-exists. | Decide gitignore policy for `.dogen/` at planning (the dogfood run will create real files in this repo). |
| Live service config | The pinned **Copilot CLI** runtime the SDK launches — version is host/CLI-managed and auto-updates (issue #1606). Not in git. | Pin the CLI version (D-27); the smoke test (D-24) re-verifies on bump. |
| OS-registered state | None — the SDK manages the CLI as a child process; no Task Scheduler/systemd/launchd registration. | None. |
| Secrets/env vars | Copilot auth via `COPILOT_GITHUB_TOKEN` > `GH_TOKEN` > `GITHUB_TOKEN` (read by the CLI). Not used in CI (D-24 keeps the real SDK out of CI). | Document for local smoke; ensure CI path uses `--provider mock` and never needs the token. |
| Build artifacts | `dist/_wheel/` exists from Phase-1 build; `src/dogen/**/__pycache__/`. New deps change `uv.lock`. | `uv add` updates `uv.lock` (D-18); CI uses `uv sync --frozen`. |

## Common Pitfalls

### Pitfall 1: Tool allowlist names are source-qualified, and the exact built-in names need one runtime confirmation
**What goes wrong:** Passing `available_tools=["grep", "glob", "view"]` (as ARCHITECTURE.md illustrates) either raises or silently fails to match, because the SDK expects **source-qualified** entries (`builtin:grep`) or a `ToolSet`. Worse, the *canonical built-in names* for read-only lookup are not fully enumerated in the wheel's Python source.
**Why it happens:** `_mode.py` only enumerates `BUILTIN_TOOLS_ISOLATED` (`ask_user`, `task`, `skill`, …) which does **not** include grep/glob/view; those are non-isolated built-ins registered by the CLI runtime. The wheel's `rpc.py` documents tool identifiers by example only: *"Tool identifier (e.g., `bash`, `grep`, `str_replace_editor`)"*.
**How to avoid:** Use `ToolSet().add_builtin([...])` (which emits `builtin:<name>`). During the **local smoke test**, run `await client.create_session(...)` then introspect the actual registered built-in tool names the runtime exposes (or check the pinned CLI's `--help`/tool list), and confirm the exact strings for grep/glob/view before locking D-28's allowlist. Belt-and-braces: also set `excluded_tools` to deny `bash`/`str_replace_editor`/`create`/write/network tools.
**Warning signs:** The agent reads nothing (over-restrictive allowlist) or can write/exec (under-restrictive). `[VERIFIED: wheel `_mode.py`/`rpc.py`; canonical names ASSUMED pending runtime confirmation]`

### Pitfall 2: `create_session` is async — the whole loop is async
**What goes wrong:** Treating the provider call as synchronous forces `asyncio.run()` deep in an adapter, which breaks if anything above is already in an event loop and complicates Typer (sync) → async orchestrator.
**How to avoid:** Make `DraftingProvider.draft_unit` async; run the loop once at the CLI boundary (`asyncio.run(orchestrator.draft(...))` in `cli/main.py`). `pytest-asyncio` is already installed for testing it. The mock provider's `draft_unit` is `async` too (just `return canned`).
**Warning signs:** `RuntimeError: asyncio.run() cannot be called from a running event loop`. `[VERIFIED: wheel]`

### Pitfall 3 (domain): HITL theatre — the gate must be consequential and recorded *before* drafting
**What goes wrong:** A confirmation prompt or a `steering` field written *by* the draft pass would be ceremonial, failing AC5.
**How to avoid:** D-39's explicit `dogen steer` event writes `provenance.yaml.steering {author, at, intent, audience}` as a discrete act; `dogen draft` reads it and refuses if absent (D-40). Steering provably precedes drafting. (PITFALLS Pitfall 5.)
**Warning signs:** `steering` is written in the same call as `generations[]`; no nonzero exit when steering is missing.

### Pitfall 4: Seam leak through `core/`
**What goes wrong:** `AssistantMessageData`, `SessionEvent`, `ToolSet`, or `logfire` types appear in `core/`, making the SDK/backend swap fictional.
**How to avoid:** `import-linter` forbidden contract: `core/*` may not import `copilot`, `logfire`, `opentelemetry.sdk`, or `adapters.*`. Keep the Phase-1 AST check too (cheap, single-sourced) unless planning decides import-linter fully subsumes it (D-29 open question). (PITFALLS Pitfall 4.)

### Pitfall 5: F1 schema designed too narrowly
**What goes wrong:** Modeling only what the skeleton writes today forces breaking migrations later.
**How to avoid:** Reserve `verification.steps[]` empty now (D-36/PLAN-07), keep `sources` vs `context_origins` distinct (D-37), put `schema_version: 0` on every machine file (D-34). An empty-but-present field costs nothing. (PITFALLS Pitfall 8.)

### Pitfall 6: Sphinx build silently "passes" without actually parsing MyST
**What goes wrong:** A `conf.py` missing `myst_parser` in `extensions` will treat `.md` as plain text or skip it; the build "succeeds" but never proved publishability.
**How to avoid:** `extensions = ["myst_parser"]`, `myst_enable_extensions = ["colon_fence"]`, and build with `sphinx-build -W -b html docs docs/_build` (`-W` turns warnings — including a `.md` not in any toctree — into errors). Ensure the drafted page is referenced from a `toctree`. `[CITED: myst-parser docs; VERIFIED: myst-parser 5.1.0 requires sphinx<10,>=8]`

## Code Examples

### Minimal `docs/conf.py` (MyST + colon_fence, D-43)
```python
# Source: myst-parser configuration docs (executablebooks)
project = "dogen"
extensions = ["myst_parser"]
myst_enable_extensions = ["colon_fence"]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
html_theme = "furo"  # optional; omit to use Sphinx default
```

### Minimal `.readthedocs.yaml` (D-43)
```yaml
# Source: Read the Docs config v2 reference
version: 2
build:
  os: ubuntu-24.04
  tools:
    python: "3.12"
sphinx:
  configuration: docs/conf.py
  fail_on_warning: true
python:
  install:
    - method: pip
      path: .
      extra_requirements: [docs]
```

### CI docs build step (extends the Phase-1 `ci.yml`, mock-only loop)
```yaml
# add to .github/workflows/ci.yml jobs (Python 3.12 only — Sphinx 9.1 floor)
- name: Docs build (proves Sphinx-publishable MyST — SKEL-02)
  run: uv run --extra docs sphinx-build -W -b html docs docs/_build
```

### Reading the draft + provenance from the SDK result (adapter, anti-corruption)
```python
# adapters/copilot/mapping.py  — verified field names
def to_draft_result(evt: "SessionEvent", run_id: str) -> "DraftResult":
    data = evt.data  # AssistantMessageData when evt.type == "assistant.message"
    return DraftResult(
        text=data.content,
        model=data.model,
        output_tokens=data.output_tokens,
        run_id=run_id,
    )
```

## State of the Art

| Old (ARCHITECTURE.md illustration) | Verified (1.0.2 wheel) | Impact |
|------------------------------------|------------------------|--------|
| `client.create_session(...)` (sync) | `await client.create_session(...)` (coroutine) | Loop must be async end-to-end. |
| `session.send_and_wait(...)` returns "reply" | returns `SessionEvent | None`; draft is `AssistantMessageData.content` | Adapter reads `.content/.model/.output_tokens`. |
| `tools=["grep","glob","view"]` | `available_tools=ToolSet().add_builtin([...])` → `builtin:grep` | Allowlist is source-qualified; bare str raises. |
| `excluded_tools=["shell","edit","create"]` | same mechanism; built-in names are e.g. `bash`, `str_replace_editor` | Confirm exact names at smoke time. |
| `custom_agents=[...]`, `effort` | `custom_agents` exists; effort is `reasoning_effort` Literal incl. `xhigh` | Add `xhigh` to the provenance `effort` enum. |
| Schema under `.planning/units/` | `.dogen/units/` (D-31) | `.planning/` is GSD's; never write there. |

**Deprecated/outdated:**
- The STACK.md note that observability *could* lean on `github-copilot-sdk[telemetry]` — superseded by D-20 (own OTel layer in core). The `[telemetry]` extra is still useful to *correlate* with (the SDK emits W3C trace context), but it is not the OBS-01 mechanism.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The canonical built-in tool names for read-only lookup are `grep` / `glob` / `view` | Pitfall 1, Pattern 2 | If the runtime registers different names, the D-28 allowlist must be adjusted. **Resolve at the local smoke test by introspecting registered tools** before locking the allowlist. (Filter *mechanism* is verified; only the exact strings are assumed.) |
| A2 | The compatible Copilot CLI version for SDK 1.0.2 is whatever the 1.0.2 wheel bundles | SKEL-05/D-27 | Pinning the wrong CLI re-triggers issue #1606. The wheel bundles a CLI binary; the smoke test must record the exact bundled/used CLI version as the pin. |
| A3 | macOS wheel's Python API == Linux/Windows wheels' Python API (only the bundled CLI binary differs per platform) | Whole SDK section | Very low risk — the `.py` source is platform-independent; only `copilot/bin/` differs. The repo will install the Linux wheel. |
| A4 | ruamel.yaml is needed only if `dogen` rewrites `unit.md` | Stack, Don't Hand-Roll | If the tool only reads `unit.md`, ruamel is an unnecessary dep — decide at planning whether `dogen` ever mutates `unit.md` (e.g. syncing `status`). |
| A5 | `send_and_wait` is sufficient for the skeleton (no streaming required) | SDK section | If the model truncates or multi-turns, the planner may need the `session.on(handler)` event path; both are verified-available. |

## Open Questions (RESOLVED)

All four open questions have a recorded disposition (covering task/checkpoint or explicit planning decision) as of the phase-2 plan revision. Each is annotated **RESOLVED** below.

1. **Exact built-in read-only tool names (A1).**
   - What we know: the filter mechanism (`ToolSet().add_builtin` → `builtin:<name>`), and that `grep`/`bash`/`str_replace_editor` are documented-by-example identifiers.
   - What's unclear: the precise names for "glob" and "view" (file read) as the runtime registers them.
   - Recommendation: a one-task smoke probe that lists registered tools, run before the allowlist is locked. Plan a `checkpoint:human-verify` here.
   - **RESOLVED:** Covered by the **blocking `checkpoint:human-verify` in plan 02-03** ("Confirm the exact built-in read-only tool names (A1) before locking the allowlist"). The human probes the pinned runtime and supplies/approves the exact `grep`/`glob`/`view` (and deny-side) names before `adapters/copilot/tools.py` is locked. No further research needed.

2. **Docs/content license (D-44) — CC-BY-SA-4.0 vs CC-BY-NC-SA-4.0.**
   - What we know: licensing.md §1 says the policy default is CC-BY-SA-4.0, but §3.5 (the per-file docs header example) says **CC BY-NC-SA 4.0** — a real, unresolved inconsistency in the system-of-record.
   - What's unclear: which the project adopts for drafted `.md` under `docs/`.
   - Recommendation: resolve at planning before the first drafted page is committed (it needs a correct SPDX header for `reuse lint`). This is a decision task, not research.
   - **RESOLVED:** Covered by the **blocking `checkpoint:decision` in plan 02-04** ("Decide the drafted docs/content license and reconcile licensing.md (D-44)"). The developer selects CC-BY-SA-4.0 (the D-44/§1/§2 lean) vs CC-BY-NC-SA-4.0 before the first drafted page is committed; the executor then adds `LICENSES/<chosen>.txt`, reconciles licensing.md §1/§2/§3.5, and applies the SPDX id via a `.license` sidecar.

3. **`.dogen/` gitignore policy.**
   - What we know: the dogfood run writes real audit files into this repo.
   - What's unclear: whether `.dogen/units/` is committed (audit trail in git history, per the schema's "git-diffable" intent) or ignored.
   - Recommendation: planning decision; the schema rationale ("the audit trail IS the git history") argues for committing it.
   - **RESOLVED (settled at planning, not a new checkpoint):** **Commit** the `.dogen/units/<id>/` audit surface as the AC5 evidence (per D-24 "demonstrated once, capture the run as evidence"; the schema's audit trail IS the git history) — do NOT gitignore it. To keep `reuse lint` green on these tool-generated files, **plan 02-04 Task 2 adds a `REUSE.toml` `.dogen/**` glob annotation** (`precedence = "aggregate"`, `GPL-3.0-only` — tool-generated project artifacts get the same license as the code that produced them, per licensing.md §1). `.planning/` stays excluded from both source-lookup and dogen output (D-30); its existing REUSE.toml `.planning/**` exclusion is untouched. `docs/_build` is gitignored as build output; `.dogen/` is not.

4. **Dependency-update bot (deferred-but-flagged).**
   - Recommendation: confirm at planning whether Renovate/Dependabot lands now (the SDK/CLI pin makes it relevant) or next phase — keep it out of scope unless explicitly added.
   - **RESOLVED — DEFERRED to a later phase.** A dependency-update bot (Renovate/Dependabot) is **not** in this phase's 19 requirements and is **not** added now; it is explicitly deferred, consistent with CONTEXT.md's deferred list. The pinned `github-copilot-sdk==1.0.2` + bundled-CLI pin are guarded this phase by the manual smoke-test bump gate (plan 02-03, D-24), so there is no correctness gap from deferring the bot. Disposition: out of scope for phase 2; revisit when automated dependency updates are explicitly scheduled.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.12.3 | — |
| uv | env/lock/build | ✓ | 0.11.21 | — |
| ruff | lint/format gate | ✓ | (venv) | — |
| ty | type gate | ✓ | (venv) | — |
| pytest + pytest-asyncio | tests (async loop) | ✓ | (venv) | — |
| PyYAML | YAML I/O | ✓ | 6.0.3 | — |
| github-copilot-sdk | real adapter (SKEL-02/05) | ✗ | needs 1.0.2 | **mock provider** runs the whole loop in CI (D-23) — real SDK is local-smoke only |
| Copilot CLI | SDK runtime | ✗ (unverified) | pin TBD | mock provider; backend-unavailable is a handled state (D-27) |
| logfire | OBS backend (D-21) | ✗ | needs 4.37.0 | OTel SDK ConsoleSpanExporter (but D-21 chose logfire) |
| opentelemetry-api | OBS instrumentation | ✗ | needs 1.42.1 | none — required for OBS-01 |
| sphinx + myst-parser | docs build (D-43) | ✗ | 9.1.0 / 5.1.0 | none — required for SKEL-02 proof |
| import-linter | seam gate (D-29) | ✗ | needs 2.11 | keep Phase-1 AST check as fallback |
| reuse | LIC-01 gate | ✗ on PATH (uvx in CI) | v6.2.0 | `uvx reuse` (as Phase-1 CI does) |

**Missing dependencies with no fallback (planner must add install tasks):** `opentelemetry-api`, `logfire`, `sphinx`, `myst-parser`, `import-linter`, and `github-copilot-sdk` (for the local smoke path). All are `uv add` tasks updating `uv.lock` (D-18).
**Missing dependencies with fallback:** the real Copilot SDK/CLI at *CI* time — the mock provider (D-23) is the CI-runnable substitute.

## Validation Architecture

> Nyquist validation is disabled for this phase (per the research brief). Included lightly because the mock-first acceptance model (D-24) is itself a validation-architecture decision the planner must encode.

- **CI loop proof = mock provider.** `pytest` drives `--provider mock` end-to-end: `unit new → steer → draft → review`, asserting the four files appear with correct schema, the HITL gate refuses without steering, and `progress.yaml` never reaches `committed`. Deterministic (no network, no SDK) per the coding-guide testing rules.
- **Seam gate.** `import-linter` contract in CI + pre-commit (and keep `scripts/seam_check.py` unless subsumed).
- **Docs gate.** `sphinx-build -W` builds the drafted MyST page (SKEL-02), Python 3.12 only.
- **Real-SDK smoke (manual, out of CI).** One captured run on the pinned SDK+CLI is the SKEL-05 evidence and the version-bump gate (D-24). Record the bundled CLI version as the pin (A2).
- **Mock at the true boundary only.** Per coding-guide §4: mock the provider port and host I/O (git config), use real objects in the core. Don't over-mock the orchestrator.

## Security Domain

> `security_enforcement` not explicitly disabled; included because bounded tools + drafted-command output touch real threat surface (PITFALLS security table).

### Applicable controls
| Concern | Applies | Standard control |
|---------|---------|------------------|
| Unbounded agent capability (write/exec/network) | yes | `available_tools`/`excluded_tools` allowlist (D-28); read-only `builtin:grep/glob/view`; deny `bash`/write/create. |
| Secrets in captured output landing in provenance | yes | Scrub/redact before persisting `context_origins`/any captured stdout; never store tokens. (PITFALLS security row 3.) |
| Auth tokens in CI | yes | CI uses `--provider mock`; never needs `COPILOT_GITHUB_TOKEN`/`GH_TOKEN` (D-24). |
| Provenance leaking into shipped docs | yes | Keep `.dogen/` provenance internal; never emit model/version/effort into the `docs/` `.md` (PROJECT.md: no public AI disclaimer). |
| Supply-chain (pinned deps) | yes | `uv.lock` frozen install in CI; pin SDK+CLI; legitimacy audit above. |
| Scope-border crossing (push/PR/build) | yes | No git-write/network-publish code; `progress` has no such states (D-38, Pitfall 9). |

## Sources

### Primary (HIGH confidence)
- **Unpacked `github-copilot-sdk==1.0.2` wheel** (downloaded from PyPI files this session): `copilot/__init__.py`, `client.py` (`create_session`, `get_status`, `list_models`), `session.py` (`send`, `send_and_wait`, `on`, `ReasoningEffort`), `tools.py` (`define_tool`), `_mode.py` (`ToolSet`, `BUILTIN_TOOLS_ISOLATED`), `generated/session_events.py` (`SessionEventType`, `AssistantMessageData`), `_telemetry.py` (W3C trace context). — the authoritative API source.
- **PyPI JSON API** (this session): verified versions + Python floors for all 12 packages; `myst-parser 5.1.0` `requires_dist` → `sphinx<10,>=8`; `logfire 4.37.0` → `opentelemetry-sdk 1.39–<1.43`.
- In-repo: ARCHITECTURE.md, STACK.md, PITFALLS.md, coding-guide.md, licensing.md, REQUIREMENTS.md, 02-CONTEXT.md, 01-CONTEXT.md, Phase-1 `ci.yml`/`.pre-commit-config.yaml`/`scripts/seam_check.py`/`pyproject.toml`/tests.

### Secondary (MEDIUM confidence)
- myst-parser configuration (`extensions`, `myst_enable_extensions = ["colon_fence"]`) and Read the Docs config v2 — patterns from official docs; exact `conf.py` to be confirmed against the installed 5.1.0 at build time.

### Tertiary (LOW confidence)
- Canonical built-in tool names `glob`/`view` — inferred from the wheel's by-example identifiers; confirm at smoke time (A1).

## Metadata

**Confidence breakdown:**
- Copilot SDK API: HIGH — read directly from the unpacked 1.0.2 wheel source.
- Stack versions/compatibility: HIGH — live PyPI metadata, including the myst↔sphinx pin.
- Observability wiring: HIGH for the API/package shape; MEDIUM for exact span attribute design (Claude's discretion).
- Bounded-tool exact names: MEDIUM — mechanism verified, canonical strings need one runtime check.
- F1 schema / HITL / Sphinx patterns: HIGH — fully specified by CONTEXT.md decisions + verified package capabilities.

**Research date:** 2026-06-19
**Valid until:** ~2026-07-19 for the stack; **shorter for the Copilot CLI** — its auto-update can break SDK transport at any time (issue #1606), so re-verify the CLI pin on every SDK touch.

## RESEARCH COMPLETE
