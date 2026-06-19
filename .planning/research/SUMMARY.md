# Project Research Summary

**Project:** Agentic Documentation Drafting Framework (DOCPR-2845)
**Domain:** Platform-thin agentic doc-drafting layer — distributable Python package on the GitHub Copilot SDK, Sphinx/RTD output
**Researched:** 2026-06-19
**Confidence:** MEDIUM (Copilot SDK surface HIGH; features/architecture MEDIUM; pitfalls MEDIUM)

---

> **First-pulse reading guide.** This project is delivered agile; the only in-repo work for Pulse 1 is **A2** (thin walking skeleton) and **F1** (planning-directory schema v0). The full findings below are destination context. Sections and findings that bear *directly* on A2 + F1 are flagged **[A2/F1 NOW]**.

---

## Executive Summary

This is a thin Python drafting layer — not an agent runtime — that rides the GitHub Copilot SDK (GA as of 2026-06-02, Python package `github-copilot-sdk==1.0.2`) and outputs Sphinx-publishable content for the GitHub + Read the Docs + Sphinx stack. The standard pattern for this class of tool is hexagonal / ports-and-adapters: a pure domain core that depends only on interfaces (ports), with the Copilot SDK living entirely in one adapter module. The seam's rule — "no SDK import outside `adapters/copilot/`" — is a CI-enforceable invariant, not a guideline, and must be set at the walking skeleton (A2), because retrofitting costs far more than establishing it from the start.

The project's feature set is mostly conventional in 2026: type-aware generation, instruction layering, provenance, and HITL checkpoints all exist in shipping tools (Mintlify, Katara, Copilot agents). The genuine edges are (1) **evidence-gated verification of actionable content** — proving steps actually run, which no mainstream drafting tool does — and (2) **deliberate restraint**: unit-scoped iteration with a hard stop at singular traceable local commits. Evidence-gated verification is the epic's hardest problem, is spike-worthy, and must not block the MVP. Steering-first (human points at sources) is the correct Mode A default; RAG is spike-gated (S1) and must not appear before that spike runs.

The single biggest stack risk is the Copilot CLI auto-update vector: the CLI removed `--headless --stdio` without deprecation once already (issue github/copilot-cli#1606, closed "not planned"), breaking older SDK versions. Mitigation is to pin `github-copilot-sdk==1.0.2` and the SDK-compatible CLI version, and to treat "Copilot drafting backend unavailable" as an expected handled state. The F1 planning-directory schema is the fulcrum of the entire audit/provenance surface; designing it too narrowly for A2's immediate needs forces breaking migrations every subsequent phase. Reserve extensibility fields — schema version, verification evidence, steering records, reviewer edits — at v0, even if A2 leaves them empty.

---

## Key Findings

### Recommended Stack

The stack is dominated by two constraints: the Copilot SDK is a fixed decision (pragmatic-first per PROJECT.md), and Python 3.12 is the practical floor because Sphinx 9.x requires it (the SDK floor is 3.11). The modern Python packaging golden path — `uv` + `hatchling` + `pyproject.toml` — is the clear 2026 recommendation. Pydantic v2 serves double duty: it is already the schema layer the Copilot SDK uses for `@define_tool` parameter schemas, and it is the right tool for validating the F1 planning-directory schema.

For doc output, MyST Markdown (via `myst-parser`) is strongly preferred over rST for AI-emitted content: models produce clean Markdown far more reliably than whitespace-strict rST, directly lowering malformed-output risk. Diátaxis (tutorial / how-to / reference / explanation) is the structural methodology; encode the four types as operator-selected intent *directions*, not separate code paths.

**[A2/F1 NOW] Core technologies:**
- `github-copilot-sdk==1.0.2` — the adopted agent backend; **pin exactly**; CLI auto-updates are a verified breakage vector (issue #1606); requires Python ≥ 3.11
- `GitHub Copilot CLI` — pin the SDK-compatible version; bundled with the SDK; the transport layer the SDK drives via JSON-RPC
- `Python 3.12` — floor set by Sphinx 9.x; covers both the SDK (3.11+) and the docs toolchain (3.12+)
- `Pydantic v2` — F1 schema validation + Copilot SDK `@define_tool` parameter schemas; one validation layer for both
- `Typer` — CLI framework; type-hint-driven DX; matches "good UX is a primary requirement" per PROJECT.md
- `uv` + `hatchling` — project/dependency/build/publish driver; 2026 golden path; reproducible lockfile
- `myst-parser 5.1.0` + `Sphinx 9.1.0` — MyST Markdown in Sphinx; lower AI malformed-output rate vs rST
- `httpx` — fetch org-wide guidance from remote URLs (pre-MCP); async, matches the SDK's async model

**Critical version note:** `github-copilot-sdk==1.0.2` must be pinned exactly. The underlying Copilot CLI auto-updates and has broken SDK transport without deprecation (issue #1606, closed "not planned"). Gate SDK upgrades behind a smoke test of the full drafting loop.

**Agent Skills (SKILL.md)** are an open, cross-agent standard (`.github/skills`, `.claude/skills`, `.agents/skills`) — skills authored for Copilot today are portable to the Claude Agent SDK or `opencode-agent-sdk` later, making org-wide drafting skills durable across the abstraction seam.

### Expected Features

The market has commoditized the basics. Differentiation lies in verification rigor and disciplined restraint, not in "AI writes docs."

**Must have (table stakes — expected in any 2026 doc-drafting tool):**
- End-to-end unit drafting from human-pointed sources into Sphinx-publishable output **[A2 NOW]**
- SDK abstraction seam (hexagonal adapter) — cheap-swap from day one **[A2 NOW]**
- Planning-directory schema (F1): intent/audience steering, unit plan, provenance, progress **[F1 NOW]**
- Type/format steering (Diátaxis as direction, not four parallel flows)
- Instruction/style customization via `AGENTS.md`-compatible config (cross-tool standard)
- Human review/edit checkpoint before output is finalized
- Source/context pointing ("draft this from these inputs")
- Iterative refinement (re-steer, regenerate)

**Should have (differentiators — where the tool actually stands out):**
- **Evidence-gated actionable verification** — prove steps run; no mainstream tool does this; highest value, highest risk; spike first
- **Provable / recorded HITL** — intent + audience steering captured as durable provenance before drafting; the audit surface (AC5)
- **Layered customization: org → repo → writer** — decoupled hierarchy; portfolio-scale update benefit
- **Unit-scoped iterative drafting** (counter-positioning: the restraint is the feature)
- **Internal provenance trail** — model/version/effort, tooling version, context origins, reviewer edits
- **Local onboarding / style-scraper** — code-to-docs map + repo style/glossary artifacts; bootstraps per-repo knowledge without a heavyweight index

**Defer to v2+ / spike-gate:**
- Evidence-gated actionable verification — do not block MVP; run a spike first; epic's hardest problem
- Context-augmentation index (RAG/structural) — spike-gated (S1), default do-not-build
- DOCPR-2822 QA extension point — coexistence hook once core is stable
- Mode B (agent-guided research/planning) — largest net-new build, lowest risk to defer

**Anti-features (deliberate non-builds):**
- Auto-commit / push / open PRs / build / publish — crosses the accountability border
- One-shot full-set generation — unreviewable volume, maximizes slop
- Public "AI-generated" disclaimer — provenance is internal observability only
- Premature RAG — steering-first is sufficient for Mode A
- Reader-facing AI assistant / chat-over-docs — different product

### Architecture Approach

The dominant pattern for "thin layer over an agent SDK" is **hexagonal / ports-and-adapters**: a pure Python domain core (`core/`) that depends only on Protocols/ABCs defined in `core/ports.py`, with the Copilot SDK isolated entirely in `adapters/copilot/`. The core owns the domain concepts (Unit, Intent, Audience, Steering, DraftResult, Provenance); the adapter translates between domain vocabulary and SDK vocabulary via `mapping.py` (the anti-corruption layer). **The core must have zero vendor imports** — this is the CI-enforceable rule that makes a future SDK swap genuinely cheap.

**[A2/F1 NOW] Major components:**
1. **`core/models.py`** — domain types: Unit, Intent, Audience, Steering, DraftResult, Provenance (no vendor imports)
2. **`core/ports.py`** — interfaces: DraftingProvider, SourceLookup, PlanningStore, QaHook (Protocols/ABCs shaped by domain, not by the SDK)
3. **`core/orchestrator.py`** — the single drafting use-case: reads steering, calls provider, persists draft + provenance + progress
4. **`adapters/copilot/`** — the seam; the ONLY module that imports the Copilot SDK; `provider.py` + `tools.py` + `mapping.py`
5. **`adapters/planning_fs.py`** — implements PlanningStore over `.planning/` filesystem files
6. **`adapters/qa_noop.py`** — default no-op QaHook; DOCPR-2822 adapter added later
7. **`steering/resolver.py`** — org → repo → writer guidance merge; org guidance referenced externally (decoupled)
8. **`cli/main.py`** — thin Typer driving adapter; no business logic
9. **`.planning/`** — the F1 deliverable: `steering.yaml` + `units/<unit-id>/{unit.md, draft.rst, provenance.yaml, progress.yaml}`

**Key architectural rules:**
- Dependencies point inward only (adapters → core; core → nothing vendor-specific)
- Copilot SDK imported in exactly one adapter (`adapters/copilot/`) — CI guardrail: grep for SDK import outside this path should return nothing
- Bounded, read-only toolset only: `grep`/`glob`/`view`; no write/exec/network tools
- One drafting flow; `intent` selects prompt/template, not a separate pipeline per doc type

**[A2/F1 NOW] F1 planning-directory schema — must reserve at v0:**

The F1 schema is the audit/provenance surface everything downstream hangs off. Designing it too narrowly for A2's immediate needs forces breaking migrations every subsequent phase. The following must be present at v0 (even if A2 leaves them empty):

- `schema_version` field — enables explicit, detectable future migrations
- `intent` + `audience` + `steering_notes` in `unit.md` front-matter — the provable HITL steering surface; recorded *before* drafting
- `sources` list in `unit.md` — human-pointed inputs (distinct from `context_origins` in provenance)
- `status` field in `unit.md` (mirrors `progress.yaml` for quick scan)
- `generations` array in `provenance.yaml` — one entry per draft pass; fields: `at`, `action`, `model`, `model_version`, `effort`, `tooling_version`, `sdk`, `context_origins`, `tools_used`
- `reviewer_edits` array in `provenance.yaml` — human edits after generation; fields: `at`, `reviewer`, `summary`
- `state` + `history` in `progress.yaml` — lifecycle: `pending → sourced → drafted → reviewed → committed`; stops at `committed` (no push/PR/build states)
- Reserved optional fields for verification evidence (step state, evidence pointer, environment fingerprint) — for Phase E; empty at v0 but structurally present

The gap between `sources` (human-pointed) and `context_origins` (agent-actually-read) is itself audit-relevant and must be preserved as two distinct fields.

### Critical Pitfalls

**[A2/F1 NOW] Must-address at first pulse:**

1. **SDK transport instability (issue #1606)** — the Copilot CLI removed `--headless --stdio` without deprecation, breaking older SDK versions (closed "not planned"). Mitigation: pin `github-copilot-sdk==1.0.2` AND the compatible CLI version; gate upgrades on a drafting-loop smoke test; treat "backend unavailable" as an expected handled state. This is the single biggest stack risk.

2. **SDK seam leak into core** — importing Copilot types outside `adapters/copilot/` makes the abstraction fictional and the swap goal unachievable. Mitigation: enforce "no SDK import outside adapters/copilot" as a CI guardrail (grep check); shape ports around domain verbs, not SDK method signatures; prove swappability with a mock provider during A2. Must be set correctly at the walking skeleton — retrofitting costs far more.

3. **F1 schema designed too narrowly** — the temptation is to model only A2's immediate fields; every subsequent phase then forces a breaking migration of the future audit surface. Mitigation: include `schema_version`, reserved optional sections for verification evidence (Phase E), steering records, reviewer edits, and multi-source provenance at v0 — empty-but-present costs nothing; absent costs a breaking migration.

4. **HITL theatre / unprovable steering** — a confirmation click after generation is not provable HITL. Mitigation: make recorded intent + audience steering a structural prerequisite in `unit.md` front-matter before drafting proceeds; "no recorded steering → no draft" enforced by the orchestrator. Record with author + timestamp. The AC5 audit demands this.

**Important but not blocking MVP:**

5. **Evidence-free actionable content** — tutorials/how-tos drafted by LLMs may contain confidently-wrong procedures that were never executed (~42% of AI-generated code snippets contain errors per industry studies). No mainstream drafting tool gates on step execution. Mitigation: default actionable content to `unverified` state; only a captured run (command, exit code, stdout, env fingerprint) flips it to `verified`. Reserve the evidence fields in F1 now. Full mitigation belongs in Phase E behind a spike — do NOT block A2/MVP on it.

6. **Premature RAG / context augmentation** — building an index before the S1 spike is the most common over-engineering mistake for this class of tool. Mitigation: A2 must work with steering-first (human-pointed sources only); no index before the spike proves a concrete need.

---

## Implications for Roadmap

Based on combined research, the natural phase structure follows the dependency order: seam + schema must exist before quality work begins; quality work before verification; verification before portfolio scale; Mode B deferred entirely.

### Phase 1: Walking Skeleton + Planning Schema (A2 + F1)

**Rationale:** The seam shape and the schema extensibility are the two decisions most expensive to get wrong. Both must be proven in the thinnest possible end-to-end slice before any quality work begins. They cannot be separated: the skeleton needs a place to write provenance; the schema needs a producer to validate it.

**Delivers:**
- Thin end-to-end draft loop: CLI → orchestrator → Copilot adapter → Sphinx-publishable output; no commit logic
- `adapters/copilot/` seam with CI guardrail (no SDK import outside adapter)
- F1 planning-directory schema v0 with `schema_version`, all reserved fields, and filesystem adapter
- Provable HITL: recorded intent + audience steering in `unit.md` consumed by the orchestrator before drafting
- Verified: (a) core has zero vendor imports; (b) a mock provider could slot into DraftingProvider port; (c) F1 schema has version field + reserved sections

**Addresses:** A2 walking skeleton, F1 planning schema, SDK abstraction seam, provable HITL gate

**Avoids:** SDK seam leak (Pitfall 4), F1 schema churn (Pitfall 8), HITL theatre (Pitfall 5), premature RAG (Pitfall 7)

**Research flag:** Verify exact Copilot SDK 1.0.2 Python API names against the installed package at the start of planning — architecture examples in ARCHITECTURE.md are illustrative (MEDIUM confidence on specific method/field names).

### Phase 2: Steering Quality + Type-Aware Intent (D + E partial)

**Rationale:** Once the loop is proven, quality becomes the priority. Layered guidance (org → repo → writer) and explicit Diátaxis intent steering are the two levers that separate review-ready drafts from AI slop. One flow, intent-steered — not four parallel pipelines.

**Delivers:**
- `steering/resolver.py`: org → repo → writer guidance merge; org guidance fetched via `httpx` from external ref
- Type/intent steering surfaced as one capability (reference/tutorial/how-to/explanation as `intent` direction)
- Singular traceable local-commit boundary (hard stop)
- Slop-detection pass (banned-phrase list, repetition checks) as a cheap pre-review quality gate

**Addresses:** Layered customization, type-aware generation, AI slop (Pitfall 3), scope-creep boundary (Pitfall 9)

**Research flag:** Standard patterns — skip research phase. Prompt engineering for Diátaxis type-differentiation may need iteration during execution.

### Phase 3: Onboarding / Style Scraper (B)

**Rationale:** Deploys the tool repeatably across products. The style-scraper produces per-repo knowledge artifacts that pre-fill steering and prevent blank-page friction.

**Delivers:**
- Local onboarding tool: code-to-docs map + repo doc-style + glossary + structure artifacts
- Pre-filled steering defaults (human edits rather than authors from blank)
- Deployable by any TA across products

**Addresses:** AI slop (per-repo voice/glossary), UX circumvention (Pitfall 6), repeatable deployment

**Research flag:** Standard patterns — skip research phase.

### Phase 4: Evidence-Gated Actionable Verification (spike + E)

**Rationale:** The epic's highest-value, highest-risk feature. The drafting half is straightforward; the execution-sandbox half is the genuinely hard problem. Must be isolated behind a spike before committing a phase plan. Do NOT block the MVP on this.

**Delivers:**
- Spike: assess feasibility of a reproducible sandbox (Workshop-contained) where drafted steps can actually execute and state can be inspected
- If spike succeeds: evidence-gated verification for tutorials/how-tos; captured run logs as provenance artifacts; `verified`/`unverified` state (fields already reserved in F1)

**Addresses:** Evidence-free actionable content (Pitfall 1), hallucinated CLI flags (Pitfall 2 partial)

**Research flag:** SPIKE REQUIRED — do not plan a full phase without spike results. No turnkey solution exists. Partial precedents: `sphinx.ext.doctest`, `sphinxcontrib-shtest`, install-md "DONE WHEN" format, "validation via simulation" patent approach. LLM-generated executable content runs unmodified ~70–90% of the time; the gate must catch the 10–30% failures.

### Phase 5: Bounded SDLC Connectors + Portfolio Scale (C + scaling)

**Rationale:** Extend source lookup to SDLC artifacts (PRs, bugs, commit histories) as new bounded tools behind the existing `SourceLookup` port. The `sources[].ref` field is already reserved in F1 — no schema change needed.

**Delivers:**
- PR/bug/commit lookup as new bounded read-only tools or MCP servers behind `SourceLookup`
- Proven across multiple products (greenfield + brownfield)
- Optional DOCPR-2822 QA extension point (`qa_noop.py` replaced with a real adapter)

**Research flag:** MCP server integration is well-documented in the Copilot SDK — standard patterns, skip research phase.

### Phase 6: Context Augmentation (S1 spike gate — conditional)

**Rationale:** Only if the S1 spike (intentionally-unwieldy brownfield repo) proves a concrete retrieval need that steering-first cannot cover. Default: do not build. If justified, scope to the one repo class that needs it.

**Research flag:** Spike-gated. Do not plan a full phase here without spike results. Building RAG before this point is Pitfall 7.

### Phase 7: Mode B — Agent-Guided Research/Planning (deferred)

**Rationale:** Largest net-new build, lowest risk to defer. Mode A must be validated and stable first.

**Research flag:** Defer to end-cycle or later milestone.

### Phase Ordering Rationale

- A2 + F1 are inseparable and come first: the seam shape and schema extensibility are the two most expensive decisions to get wrong; the skeleton needs F1 to have somewhere to write; F1 needs A2 to validate it with a real run
- Steering quality (Phase 2) before onboarding (Phase 3): the layered-guidance mechanic must exist before the style-scraper has somewhere to feed
- Verification (Phase 4) comes after the loop is proven: invest in the execution sandbox only once the drafting loop is trustworthy
- RAG (Phase 6) is unconditionally gated on the S1 spike — cannot appear earlier
- Mode B (Phase 7) is deferred entirely from this cycle

### Research Flags Summary

| Phase | Research Status | Notes |
|-------|----------------|-------|
| Phase 1 (A2 + F1) | Verify SDK API names at planning time | Architecture examples are illustrative; confirm against installed 1.0.2 |
| Phase 2 (Steering + Type) | Standard patterns — skip research phase | Prompt engineering iteration expected during execution |
| Phase 3 (Style Scraper) | Standard patterns — skip research phase | |
| Phase 4 (Verification) | SPIKE REQUIRED — do not plan full phase without spike | Hardest problem; no turnkey solution |
| Phase 5 (SDLC Connectors) | Standard patterns — skip research phase | MCP docs available |
| Phase 6 (RAG) | Spike-gated (S1) — conditional on spike outcome | Default: do not plan |
| Phase 7 (Mode B) | Deferred — no planning needed this cycle | |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Copilot SDK surface verified against official GitHub Docs + PyPI + changelog. Sphinx/packaging stack HIGH. Exact Python method/field names in SDK are illustrative — verify against installed 1.0.2 before coding. |
| Features | MEDIUM | Grounded in real comparable tools via web search; not yet cross-checked against hands-on trials. Feature categorization is sound; complexity estimates are indicative. |
| Architecture | MEDIUM | Hexagonal pattern and dependency rules are solid and well-established. Specific SDK API names in code examples are illustrative — cross-check against installed SDK. Overall shape is reliable. |
| Pitfalls | MEDIUM | Web-sourced industry evidence + domain reasoning grounded in PROJECT.md. No single authoritative source for this exact niche. Top pitfalls (seam leak, schema churn, HITL theatre, CLI breakage) are well-evidenced. |

**Overall confidence:** MEDIUM — sufficient to begin Phase 1 planning. The shape of the architecture, the phase structure, and the critical design decisions (seam, schema extensibility, HITL gate, SDK pinning) are reliable.

### Gaps to Address

- **Exact Copilot SDK 1.0.2 Python API surface** (method signatures, event types, `SessionConfig` fields, `@define_tool` specifics): confirm against the installed package at the start of Phase 1 planning.
- **SDK-compatible Copilot CLI version pin**: confirm the exact bundled CLI version at setup time; record in `pyproject.toml` and provenance.
- **OpenTelemetry extra fields** (`github-copilot-sdk[telemetry]`): confirmed present on PyPI but exact emitted fields unverified; validate at build time before relying on OTel hooks for provenance capture.
- **Verification sandbox feasibility**: the execution-sandbox approach has no turnkey implementation for Sphinx-authored how-tos; this is the spike target for Phase 4.
- **H1 UX baseline and H2 candidate assessment**: produced outside this repo (Pulse 1 out-of-repo work); results must be brought in before Phase 2 planning.

---

## Sources

### Primary (HIGH confidence)
- GitHub Docs — Copilot SDK GA, getting started, custom agents, agent skills, CLI programmatic reference: https://docs.github.com/en/copilot/how-tos/copilot-sdk/getting-started · https://docs.github.com/en/copilot/reference/custom-agents-configuration · https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically
- GitHub Changelog — Copilot SDK GA 2026-06-02, Agent Skills 2025-12-18: https://github.blog/changelog/2026-06-02-copilot-sdk-is-now-generally-available/ · https://github.blog/changelog/2025-12-18-github-copilot-now-supports-agent-skills/
- PyPI — `github-copilot-sdk` 1.0.2: https://pypi.org/project/github-copilot-sdk/
- GitHub issue #1606 — `--headless --stdio` removed, breakage, closed "not planned": https://github.com/github/copilot-cli/issues/1606
- PyPI / official — Sphinx 9.1.0, myst-parser 5.1.0, furo 2025.12.19: https://pypi.org/project/sphinx/ · https://pypi.org/project/myst-parser/
- Read the Docs — MyST vs rST guidance + Diátaxis endorsement: https://docs.readthedocs.com/platform/stable/guides/migrate-rest-myst.html · https://diataxis.fr/start-here/
- uv docs — build backend: https://docs.astral.sh/uv/concepts/build-backend/

### Secondary (MEDIUM confidence)
- Mintlify Agent, install-md: https://www.mintlify.com/blog/agents-launch · https://github.com/mintlify/install-md
- Katara — Diataxis AI workflow with HITL: https://www.katara.ai/blog/diataxis
- github/spec-kit — SDD on-disk layout: https://github.com/github/spec-kit/blob/main/spec-driven.md
- C2PA provenance model: https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html
- Hexagonal architecture for AI agents: https://medium.com/@martia_es/applying-hexagonal-architecture-in-ai-agent-development-44199f6136d3
- AI hallucination / ~42% snippet error rate: https://arxiv.org/pdf/2506.16586
- HITL theatre / rubber-stamping: https://markmcneilly.substack.com/p/human-in-the-loop-safety-mechanism · https://sloanreview.mit.edu/article/ai-explainability-how-to-avoid-rubber-stamping-recommendations/
- `opencode-agent-sdk` (provider-agnostic, drop-in for `claude_agent_sdk`): https://pypi.org/project/opencode-agent-sdk/
- Python doctest + sphinxcontrib-shtest: https://docs.python.org/3/library/doctest.html · https://github.com/tillahoffmann/sphinxcontrib-shtest

---
*Research completed: 2026-06-19*
*Ready for roadmap: yes*
