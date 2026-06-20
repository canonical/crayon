# The provider seam (SEAM-04)

`dogen` rides on an agent SDK but stays genuinely provider-agnostic. The whole
point of the seam is that the agentic-logic backend can be swapped cheaply —
agnosticism is a core design property, not an afterthought. This document records
**why the seam is real** and **how a second backend would slot in unchanged**.

## The port is shaped by domain verbs, not by an SDK

The single contract between `core/` and any backend is the
`DraftingProvider` port (`src/dogen/core/ports.py`):

```python
async def draft_unit(
    self,
    *,
    intent: Intent,
    audience: str,
    steering: Steering,
    sources: list[SourceRef],
) -> DraftResult: ...
```

Every name in that signature is a **domain** term — `intent`, `audience`,
`steering`, `sources`, `DraftResult`. None of them is a Copilot (or any vendor)
shape. A port that mirrored an SDK method — `create_session(...)`,
`AssistantMessageData`, `ToolSet` — would have *already* failed the design
(ARCHITECTURE Anti-Pattern 2): it would make the "swap" fictional because the
core would be coupled to one vendor's object model.

Two invariants keep the seam honest, and both are enforced in CI:

- **`core/` carries zero vendor imports.** It depends only on the `Protocol`
  ports it defines. The `import-linter` forbidden contract and the static AST
  guardrail (`scripts/seam_check.py`) both fail the build if `copilot`,
  `github_copilot_sdk`, `logfire`, or `opentelemetry.sdk` is imported anywhere
  under `dogen.core`.
- **`adapters/copilot/` is the single place the Copilot SDK may be imported.**
  The anti-corruption mapping (`adapters/copilot/mapping.py`) translates the
  SDK's `assistant.message` event into the pure-domain `DraftResult` at the
  boundary, so no `AssistantMessageData` / `SessionEvent` ever crosses inward.

## The mock *is* the second provider — swappability is proven, not asserted

Swappability is not a promise on a slide; it is demonstrated from **both sides**
of the port:

- `adapters/mock_provider.py` — `MockDraftingProvider` implements the exact same
  `DraftingProvider` port, deterministically, with **no SDK import and no
  network**. The full `steer → draft → review` loop runs against it in CI with
  no Copilot token (SEAM-03 / D-24/D-26).
- `adapters/copilot/provider.py` — `CopilotDraftingProvider` implements the same
  port on the real `github-copilot-sdk`.

Because both satisfy one port, the orchestrator drives either by name
(`select_provider("mock" | "copilot")`, D-25) with **no change to `core/` or the
CLI**. The mock is the living proof that a second backend needs nothing more than
a new adapter behind the unchanged port.

## Viable alternate backends (named, not built this phase)

The seam is designed so each of the following would be a **single new adapter**
behind the unchanged `DraftingProvider` port — no change to `core/`, the
orchestrator, the CLI, or the F1 schema. None is built this phase (D-26, this is
SEAM-04 design-only):

- **OpenCode SDK** — a provider-agnostic agent SDK, explicitly a drop-in
  replacement for the `claude_agent_sdk` shape (sessions, tools, MCP, skills).
  Its session/tool model maps cleanly onto the same `draft_unit` contract.
- **A homegrown Pydantic AI agent** — a thin, self-owned agent loop built on
  Pydantic AI, for when an external SDK's cost, availability, or policy is not
  acceptable. The port already speaks Pydantic-friendly domain models, so the
  adapter would translate them to whatever client it drives.

Either would be adopted by writing one `adapters/<backend>/` package implementing
`draft_unit` and adding it to the `select_provider` dispatch — exactly the shape
the mock already exercises.

## Where the line is drawn

The adapter is allowed to know about the SDK; nothing else is. Concretely:

| Layer | May import the SDK? | Responsibility |
|-------|--------------------|----------------|
| `core/` | **No** (CI-enforced) | Domain models, ports, the orchestrator, the HITL gate |
| `adapters/copilot/` | **Yes** (the sole site) | Drive the real SDK; bounded read-only toolset; anti-corruption mapping; backend-unavailable handling |
| `adapters/mock_provider.py` | **No** | Deterministic second provider that proves the seam |
| `scripts/smoke_draft.py` | Yes (not `core/`) | Manual local smoke run of the real SDK (out of CI) |

That single, narrow, CI-enforced border is what keeps adopting OpenCode or a
Pydantic AI agent a *one-adapter* change rather than a rewrite.
