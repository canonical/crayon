# Architecture Research

**Domain:** Platform-thin agentic documentation-drafting framework (a thin Python drafting layer over an adopted agent SDK — GitHub Copilot SDK — with a provider-abstraction seam, an SDD-style planning directory, bounded agentic lookup, and an optional external-QA extension point)
**Researched:** 2026-06-19
**Confidence:** MEDIUM

> Confidence note: Findings draw on official GitHub Copilot SDK docs/repo and the github/spec-kit repo (cross-checked → MEDIUM), plus established hexagonal-architecture and coding-agent tooling practice. No HIGH-confidence curated-doc lookups (Context7) were available for the Copilot SDK; verify the exact Python API names against the installed SDK version before coding. The *shape* of the architecture is solid; specific method/field names in code examples are illustrative.

## Standard Architecture

The dominant pattern for "thin layer over an agent SDK" is **hexagonal / ports-and-adapters**: a pure drafting *core* that owns the domain concepts (unit, intent, steering, draft, provenance) and depends only on *ports* (interfaces). The vendor SDK lives behind an *adapter* that implements a port — it is the anti-corruption layer that keeps the Copilot SDK's vocabulary from leaking into the core. This is exactly the constraint in PROJECT.md ("Copilot SDK behind a thin abstraction seam so a later swap stays cheap").

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DRIVING SIDE (entry)                            │
│  ┌──────────────┐                                                      │
│  │   CLI / TA   │  human points at sources, sets intent + audience     │
│  └──────┬───────┘                                                      │
├─────────┼──────────────────────────────────────────────────────────────┤
│         ▼                  CORE  (pure Python, no SDK imports)          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  Orchestrator / Drafting Use-Case                                │   │
│  │   - loads STEERING (intent + audience)                           │   │
│  │   - reads/writes the PLANNING DIRECTORY                          │   │
│  │   - drives ONE type-aware draft of ONE unit                      │   │
│  │   - records PROVENANCE + PROGRESS                                │   │
│  └───┬──────────────┬──────────────────┬─────────────────┬─────────┘   │
│      │ port         │ port             │ port            │ port        │
│      ▼              ▼                  ▼                 ▼             │
│  ┌─────────┐  ┌────────────┐    ┌──────────────┐  ┌───────────────┐    │
│  │Drafting │  │  Lookup    │    │  Planning    │  │   QA Hook     │    │
│  │Provider │  │  (sources) │    │  Store       │  │  (optional)   │    │
│  │  PORT   │  │   PORT     │    │   PORT       │  │    PORT       │    │
│  └────┬────┘  └─────┬──────┘    └──────┬───────┘  └───────┬───────┘    │
├───────┼─────────────┼──────────────────┼──────────────────┼────────────┤
│       ▼             ▼      DRIVEN SIDE (adapters)         ▼            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Copilot  │  │ grep/glob/   │  │  filesystem  │  │ DOCPR-2822   │    │
│  │ SDK      │  │ file-read    │  │  .planning/  │  │ QA framework │    │
│  │ adapter  │  │ (SDK tools)  │  │  YAML/MD     │  │ (call-out)   │    │
│  └────┬─────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│       ▼                                                                │
│  GitHub Copilot CLI (server mode) via JSON-RPC                         │
├────────────────────────────────────────────────────────────────────────┤
│                          OUTPUT                                        │
│   Sphinx-publishable .rst / .md  +  .planning/ provenance + progress   │
│   (STOP: no commit/push/PR/build — singular traceable local commit max)│
└────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **CLI (driving adapter)** | Capture human intent, audience, source pointers; invoke the drafting use-case; surface progress | `click`/`typer` thin command surface; no business logic |
| **Orchestrator / Drafting use-case** | The one capability: draft one unit, type-aware, steered by intent. Reads steering, calls Drafting Provider, persists draft + provenance + progress | Pure Python; depends only on ports |
| **Drafting Provider port + Copilot adapter** | The SDK seam. Port exposes domain-shaped methods (`draft_unit(prompt, sources, constraints) -> DraftResult`); adapter translates to Copilot SDK `create_session`/`send_and_wait` and registers tools | Adapter is the *only* module that imports the Copilot SDK |
| **Lookup port + tools** | Bounded, read-only, well-known source access: grep/glob/file-read/traversal. Future connectors (PRs, bugs, commits) added as new bounded tools | SDK-native read-only tools (`grep`, `glob`, `view`) registered on the session; future = MCP servers |
| **Planning Store port + filesystem adapter** | Read/write the planning directory: steering, unit plan, provenance, progress | Plain file I/O over `.planning/` (YAML front-matter + Markdown) |
| **QA Hook port (optional)** | Optional call-out to DOCPR-2822 QA framework without a hard dependency | No-op default adapter; real adapter added later |
| **Steering / Guidance layer** | Layered customization: org-wide guidance → per-repo knowledge → writer preferences, fed to the drafting prompt | Resolved config merge; org guidance referenced externally (decoupled from core) |

The hard architectural rule (from the source research): **dependencies point inward only**. The Copilot adapter knows about the core's ports; the core knows nothing about Copilot. Swapping SDKs later means writing one new adapter, not touching the core.

## Recommended Project Structure

```
docdraft/                       # the distributable Python package
├── core/                       # PURE domain — no SDK, no I/O specifics
│   ├── models.py               # Unit, Intent, Audience, Steering, DraftResult, Provenance
│   ├── orchestrator.py         # the single drafting use-case (type-aware, intent-steered)
│   └── ports.py                # DraftingProvider, SourceLookup, PlanningStore, QaHook (Protocols/ABCs)
├── adapters/                   # DRIVEN side — the only place vendors are imported
│   ├── copilot/                # ← THE SEAM. Copilot SDK lives ONLY here
│   │   ├── provider.py         # implements DraftingProvider via create_session/send_and_wait
│   │   ├── tools.py            # registers the bounded read-only toolset (grep/glob/view)
│   │   └── mapping.py          # translate domain types ↔ SDK session config (anti-corruption)
│   ├── planning_fs.py          # implements PlanningStore over .planning/ files
│   └── qa_noop.py              # default QaHook (does nothing); DOCPR-2822 adapter added later
├── steering/                   # layered guidance resolution (org → repo → writer)
│   └── resolver.py
├── cli/                        # DRIVING adapter
│   └── main.py                 # typer/click commands; thin
└── pyproject.toml

# Produced/consumed at runtime in the target docs repo:
.planning/                      # the F1 planning directory (audit + provenance surface)
└── units/<unit-id>/...         # see schema sketch below
```

### Structure Rationale

- **`core/` has zero vendor imports** — this is what makes the seam real and a future SDK swap cheap. If `core/` ever `import`s the Copilot SDK, the seam has failed.
- **`adapters/copilot/` is the single isolation point** — all SDK-specific calls (session creation, tool registration, model/effort selection, event handling) live here. `mapping.py` is the explicit anti-corruption translation so the SDK's data shapes never reach the core.
- **`ports.py` defines interfaces shaped by what the domain needs**, not by mirroring the SDK API — the documented over-abstraction pitfall is to let the port become a 1:1 proxy of the vendor surface.
- **`.planning/` is data, not code** — it is the F1 deliverable, the future HITL audit surface, and the provenance store. Keeping it filesystem-native (Markdown + YAML) makes it git-diffable, reviewable, and tool-agnostic.

## Architectural Patterns

### Pattern 1: Provider Port + Adapter (the SDK seam)

**What:** The core calls a narrow `DraftingProvider` interface; the Copilot SDK is wrapped in an adapter that implements it.
**When to use:** Any time the vendor (SDK/LLM provider) is expected to change — exactly the PROJECT.md constraint.
**Trade-offs:** + Swap cost is one new adapter; core and tests stay stable. − Slight indirection; risk of over-abstracting if the port mirrors the SDK instead of the domain.

**Example:**
```python
# core/ports.py — shaped by the domain, NOT by Copilot's API
from typing import Protocol

class DraftingProvider(Protocol):
    def draft_unit(
        self, *, intent: "Intent", audience: "Audience",
        steering: "Steering", sources: list["SourceRef"],
    ) -> "DraftResult": ...

# adapters/copilot/provider.py — the ONLY module importing the SDK
class CopilotDraftingProvider:                      # implements DraftingProvider
    def __init__(self, client): self._client = client
    def draft_unit(self, *, intent, audience, steering, sources):
        session = self._client.create_session(
            custom_agents=[_drafting_agent(intent, audience, steering)],
            tools=BOUNDED_READONLY_TOOLS,            # grep / glob / view only
        )
        reply = session.send_and_wait(_compose_prompt(intent, audience, steering, sources))
        return _to_draft_result(reply)              # anti-corruption translation
```

### Pattern 2: One capability, steered by intent (not four flows)

**What:** Reference / tutorial / how-to / explanation are *directions* passed as `intent`, not separate code paths. The orchestrator builds the prompt/agent differently based on `intent` but runs one flow.
**When to use:** Type-aware generation where the variation is in prompting/steering, not in control flow.
**Trade-offs:** + No code duplication; new doc types = new prompt/template, not new pipeline. − Requires disciplined prompt assembly so intent meaningfully changes output.

**Example:**
```python
def draft(self, unit, intent, audience):
    steering = self._steering.resolve(unit.repo, intent, audience)  # org→repo→writer
    sources  = self._lookup.gather(unit.source_pointers)
    result   = self._provider.draft_unit(
        intent=intent, audience=audience, steering=steering, sources=sources)
    self._store.write_draft(unit, result)
    self._store.record_provenance(unit, result.provenance)   # F1 surface
    self._store.advance_progress(unit, "drafted")
    return result
```

### Pattern 3: Bounded, read-only, well-known toolset

**What:** Expose a small, explicitly enumerated set of read-only lookup tools (grep/glob/file-read/traversal). The Copilot SDK supports this directly via per-agent `tools` allowlists plus session-level `availableTools`/`excludedTools`.
**When to use:** Agentic source lookup where controllability and auditability matter (and to keep token cost down — clean upstream search dominates cost).
**Trade-offs:** + Safe, predictable, cheap, auditable; matches how coding agents (aider etc.) use `ripgrep`. − Less "magic" than letting the agent do anything; future SDLC connectors (PRs/bugs) must be added deliberately as new bounded tools/MCP servers.

```python
BOUNDED_READONLY_TOOLS = ["grep", "glob", "view"]   # no write/exec/network tools
# session = client.create_session(tools=BOUNDED_READONLY_TOOLS,
#                                 excluded_tools=["shell", "edit", "create"])
```

## Proposed Planning-Directory / Provenance Schema (F1)

Borrows the **spec-kit SDD layout** (steering = constitution/spec analogue; unit plan = plan/tasks; progress tracking via checklists) and the **C2PA provenance model** (assertions about origin, actions, ingredients, AI-use — recorded as plain structured fields, *internal-only*, no published disclaimer per PROJECT.md).

Layout — per unit, git-diffable, reviewable:

```
.planning/
├── steering.yaml               # GLOBAL steering for this docs project
│   #   audience defaults, doc-set intent, layered-guidance references
│   #   (org-guidance ref → external; per-repo knowledge; writer preferences)
└── units/
    └── <unit-id>/              # one drafted unit
        ├── unit.md             # the unit PLAN + STEERING (front-matter + body)
        ├── draft.rst           # the Sphinx-publishable output (or .md)
        ├── provenance.yaml     # the audit/provenance record
        └── progress.yaml       # state machine for this unit
```

**`units/<unit-id>/unit.md`** — steering + plan (front-matter is the machine-readable contract):
```yaml
---
unit_id: install-on-lxd
intent: how-to               # reference | tutorial | how-to | explanation (DIRECTION)
audience: "ops engineer, first-time LXD user"
title: "Install the agent on LXD"
sources:                     # human-pointed source pointers (HITL steering, recorded)
  - path: src/installer/lxd.py
  - path: docs/concepts/lxd.rst
  - ref: "PR #412"           # future connector; recorded even before supported
sphinx_target: how-to/install-lxd.rst
steering_notes: "Lead with prerequisites; assume no prior Juju knowledge."
status: drafted              # mirrors progress.yaml for quick scan
---
## Intent & scope
<!-- human-authored framing; the provable HITL steering surface -->
## Outline / acceptance
- [ ] prerequisites covered
- [ ] commands verified runnable
```

**`units/<unit-id>/provenance.yaml`** — internal observability (C2PA-style assertions, no crypto/no public disclaimer):
```yaml
unit_id: install-on-lxd
generations:                 # action history — one entry per draft pass
  - at: 2026-06-19T14:02:11Z
    action: drafted
    model: <model-id>
    model_version: <version>
    effort: <low|medium|high>     # reasoning/effort setting
    tooling_version: docdraft 0.1.0
    sdk: copilot-sdk <version>
    context_origins:               # "ingredients" — what the agent actually read
      - src/installer/lxd.py
      - docs/concepts/lxd.rst
    tools_used: [grep, view]
reviewer_edits:                    # human edits after generation
  - at: 2026-06-19T15:40:00Z
    reviewer: konev.artem
    summary: "Reworded prerequisites; removed hallucinated flag --auto."
```

**`units/<unit-id>/progress.yaml`** — explicit lifecycle state:
```yaml
unit_id: install-on-lxd
state: drafted               # pending → sourced → drafted → reviewed → committed
history:
  - { at: 2026-06-19T14:00:00Z, state: pending }
  - { at: 2026-06-19T14:02:11Z, state: drafted }
```

**`.planning/steering.yaml`** — project-level steering and the decoupled-guidance references:
```yaml
doc_set_intent: "Operator-facing docs for the agent platform"
default_audience: "experienced Linux operator"
guidance:
  org_ref: "https://.../canonical-doc-guidance"   # external, referenced not copied
  repo_knowledge: .planning/repo-knowledge.md      # per-repo, may be scraped later
  writer_preferences: .planning/writer-prefs.yaml
sphinx_root: docs/
```

Design choices and why:
- **YAML front-matter + Markdown body** — machine-readable contract for the tool, human-readable prose for the reviewer; both git-diffable (the audit trail *is* the git history of `.planning/`).
- **Per-unit directories** — keeps the F1 surface independent per unit, supports parallel work, and isolates provenance to the thing it describes (the C2PA "assertion bound to an asset" idea, minus the cryptography).
- **`sources` and `context_origins` are distinct** — the human points at sources (steering, in `unit.md`); the agent records what it actually read (`context_origins` in `provenance.yaml`). The gap between them is itself audit-relevant.
- **`progress.yaml` stops at `committed`** — encodes the hard scope border: no push/PR/build states exist in the schema.

For the **A2 walking skeleton**, only `unit.md` (minimal front-matter), `draft.rst`, and a minimal `provenance.yaml` are needed. The full schema above is F1 v0; A2 uses a subset.

## Data Flow

### Drafting Flow (the one capability)

```
[TA points at sources + sets intent/audience]   (CLI, recorded into unit.md)
        │
        ▼
[Orchestrator] reads steering.yaml + unit.md  ──► resolve layered guidance
        │
        ▼
[SourceLookup port] ── grep/glob/view (bounded, read-only) ──► gathers context
        │  (records what was read)
        ▼
[DraftingProvider port] ──► [Copilot adapter] ──► Copilot CLI (JSON-RPC)
        │                        │ translates domain → session config + tools
        ▼                        │
[DraftResult]  ◄─────────────────┘  (anti-corruption translation back to domain)
        │
        ▼
[PlanningStore port] writes:  draft.rst  +  provenance.yaml  +  progress.yaml
        │
        ▼
[Sphinx-publishable output]   (STOP — human reviews; optional QaHook call-out)
```

### Key Data Flows

1. **Sources → context:** Human-pointed `sources` in `unit.md` drive bounded read-only lookup; the agent's actual reads are captured as `context_origins`.
2. **Draft → provenance:** Every generation pass appends a `generations` entry (model/version/effort, tooling/SDK version, context origins, tools used); reviewer edits append to `reviewer_edits`. This is the provable-HITL audit surface.
3. **Steering layering:** org guidance (external ref) → per-repo knowledge → writer preferences are merged before prompt assembly; the core never hard-codes guidance (decoupling constraint).
4. **Optional QA call-out:** After a draft is written, an optional `QaHook` adapter can invoke DOCPR-2822; the default is a no-op, so there is no hard dependency.

## Suggested Build Order

Start at the two in-repo F1/A2 deliverables; everything else hangs off them. **A2 and F1 come first and can be built together** (the skeleton needs a place to write provenance; the schema needs a producer to validate it).

1. **F1 (planning schema v0) + A2 (walking skeleton) — TOGETHER, FIRST.**
   - F1: define `core/models.py` (Unit, Intent, Audience, DraftResult, Provenance) and the `.planning/` file layout above; build `adapters/planning_fs.py` to read/write `unit.md` / `provenance.yaml` / `progress.yaml`.
   - A2: define `core/ports.py` (`DraftingProvider`, `SourceLookup`) and `core/orchestrator.py` for the single drafting use-case; build `adapters/copilot/` (provider + bounded read-only tools + mapping); a thin `cli/` to point at one small unit and run end-to-end into a Sphinx-publishable file. **No commit logic.** Proves the loop, not quality.
   - Validates the seam (core has zero SDK imports) and that the schema is writable from a real run.
2. **Steering layering** — `steering/resolver.py`; introduce org→repo→writer merge into prompt assembly. Makes "steered by intent" real and exercises the decoupled-guidance constraint.
3. **Type-aware intent breadth** — confirm one flow handles reference/tutorial/how-to/explanation via prompt/template variation (no new pipelines).
4. **Bounded SDLC connectors** — add PR/bug/commit lookup as new bounded tools / MCP servers behind the existing `SourceLookup` port (`sources[].ref` already reserved in the schema).
5. **Optional QA extension point** — replace `qa_noop.py` with a real DOCPR-2822 adapter behind `QaHook`; still no hard dependency.
6. **Singular traceable local commit** — the hard border; add last, optional, stops at one local commit (no push/PR/build).

## Anti-Patterns

### Anti-Pattern 1: Leaking the SDK into the core

**What people do:** Import the Copilot SDK (sessions, tool configs, event types) directly in orchestration/domain code "to save a layer."
**Why it's wrong:** The seam becomes fictional; a later SDK swap touches the whole codebase, breaking the central PROJECT.md constraint.
**Do this instead:** All SDK imports live only in `adapters/copilot/`. The core depends on `ports.py`. A grep for the SDK import outside `adapters/copilot/` should return nothing — treat it as a CI guardrail.

### Anti-Pattern 2: Port that mirrors the vendor API

**What people do:** Make `DraftingProvider` a 1:1 proxy of Copilot's `create_session`/`send_and_wait` signatures.
**Why it's wrong:** A different SDK won't match those shapes, so the abstraction provides no insulation — and over-abstraction adds technical debt (the documented pitfall).
**Do this instead:** Shape ports around domain verbs (`draft_unit`, `gather_sources`). Let the adapter absorb the impedance mismatch in `mapping.py`.

### Anti-Pattern 3: Four parallel flows for four doc types

**What people do:** Build separate reference/tutorial/how-to/explanation pipelines.
**Why it's wrong:** Duplicated control flow; every cross-cutting change made four times; contradicts "type-aware generation as ONE capability steered by intent."
**Do this instead:** One flow; `intent` selects prompt/template/steering. New doc type = new template, not new pipeline.

### Anti-Pattern 4: Unbounded agent tool access

**What people do:** Give the agent the full default toolset (including write/shell/network) for convenience.
**Why it's wrong:** Loses controllability and auditability; risks the framework doing things outside drafting (violates the "dumb outside drafting" border); inflates token cost.
**Do this instead:** Explicit read-only allowlist (`grep`/`glob`/`view`) via the SDK's per-agent `tools` + session `excludedTools`. New capabilities are added deliberately, one bounded tool at a time.

### Anti-Pattern 5: Hard-coding guidance or absorbing DOCPR-2822

**What people do:** Embed org style rules in the core, or build QA into the drafting flow.
**Why it's wrong:** Couples the reusable core to mutable guidance and to a separate epic; fragments portfolio guidance and bloats scope.
**Do this instead:** Reference org guidance externally; resolve layered guidance at runtime. Keep QA behind an optional `QaHook` port with a no-op default.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| GitHub Copilot SDK / CLI | Behind `DraftingProvider` port in `adapters/copilot/`; SDK manages CLI process via JSON-RPC | GA, semantic-versioned, Python supported; pin the version and record it in provenance |
| DOCPR-2822 QA framework | Optional `QaHook` port; no-op default adapter | No hard dependency; call-out only after draft is written |
| Sphinx / RTD | Output target only — write `.rst`/`.md` to `sphinx_root` | Framework stops at publishable output; does not build or publish |
| Future SDLC sources (PRs, bugs, commits) | New bounded read-only tools / MCP servers behind `SourceLookup` | Schema already reserves `sources[].ref`; add deliberately |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| core ↔ adapters | Ports (Protocols/ABCs in `core/ports.py`); inward-only deps | The seam. Enforce "no SDK import outside adapters/copilot" in CI |
| orchestrator ↔ planning store | `PlanningStore` port over `.planning/` files | Provenance + progress writes happen here; the F1 audit surface |
| CLI ↔ core | Direct call into the drafting use-case | CLI stays thin; no business logic |
| steering resolver ↔ orchestrator | Resolved `Steering` object passed into prompt assembly | Guidance stays decoupled from core logic |

## Sources

- GitHub Copilot SDK — repo overview (languages, GA status, client→JSON-RPC→CLI model, sessions/agents/tools/skills/MCP): https://github.com/github/copilot-sdk — MEDIUM
- GitHub Copilot SDK — custom agents & tool restriction (per-agent `tools`, session `availableTools`/`excludedTools`, `defaultAgent.excludedTools` orchestrator pattern, MCP, skills): https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/custom-agents — MEDIUM
- github/spec-kit — SDD on-disk layout (specs/[branch]/spec.md, plan.md, tasks.md, data-model.md, research.md, contracts/, memory/constitution.md; spec→plan→tasks→implement): https://github.com/github/spec-kit/blob/main/spec-driven.md — MEDIUM
- Hexagonal architecture / ports & adapters as anti-corruption layer for LLM providers; dependency rule; over-abstraction pitfall: https://en.wikipedia.org/wiki/Hexagonal_architecture_(software) and https://medium.com/@martia_es/applying-hexagonal-architecture-in-ai-agent-development-44199f6136d3 — MEDIUM
- Bounded read-only agent toolset / ripgrep as coding-agent search backbone; context cost dominates: https://yage.ai/share/why-coding-agents-still-use-grep-en-20260327.html and https://arxiv.org/html/2605.15184v1 — MEDIUM
- C2PA / Content Credentials provenance model (manifest, assertions: origin/actions/ingredients/AI-use): https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html — MEDIUM

---
*Architecture research for: platform-thin agentic documentation-drafting framework*
*Researched: 2026-06-19*
