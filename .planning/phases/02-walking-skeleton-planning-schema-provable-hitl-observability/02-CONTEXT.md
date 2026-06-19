# Phase 2: Walking Skeleton, Planning Schema, Provable HITL & Observability - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 builds the **first real end-to-end drafting loop** plus the **F1 planning/provenance surface** it writes to — the inseparable **A2 + F1** slice. The agent drafts **one** operator-defined documentation unit from human-pointed sources into **Sphinx-publishable MyST**, via `CLI → orchestrator → DraftingProvider → Copilot adapter`, **stopping before any commit**. It writes the per-unit planning directory (`unit.md`, draft, `provenance.yaml`, `progress.yaml`), **refuses to draft without recorded steering**, emits **SDK-independent observability** correlated to the provenance record, and **proves the `DraftingProvider` port with a mock**.

Covers **SKEL-01..05, SEAM-03, SEAM-04, PLAN-01..07, HITL-01, HITL-02, OBS-01, OBS-02, OBS-03** (19 requirements).

**In scope:** the `DraftingProvider`/`SourceLookup`/`PlanningStore` ports; the real Copilot adapter on a pinned SDK/CLI; a deterministic mock provider; bounded read-only toolset; the F1 schema v0 (with `schema_version` + reserved verification fields); the provable-HITL steering gate; OTel-based observability with a local Logfire backend; the CLI command surface; standing up the deferred Sphinx/MyST docs toolchain with a real CI build.

**Out of scope (v2 / later phases):** steering layering org→repo→writer (STEER-01); proving type-aware breadth across all four intents (the skeleton drives ONE intent path via prompting); SDLC connectors for PRs/bugs/commits (CONN-01 — `sources[].ref` is reserved only); the DOCPR-2822 `QaHook` extension point (CONN-03); the singular-traceable-local-commit border itself (STEER-03 — `progress` stops at `committed` but the tool never sets it); actionable-content verification *execution* (VERIFY-01/02 — fields reserved, empty); RAG/context-augmentation (spike-gated); a real second provider adapter (OpenCode SDK / Pydantic AI — **design-only** this phase).
</domain>

<decisions>
## Implementation Decisions

### Observability (OBS-01/02/03)
- **D-20 — Instrument the core via the OTel API, not the SDK's telemetry.** The provider-independent instrumentation layer lives in `core/` and uses the OpenTelemetry API directly, so OBS-01 holds and the backend survives an SDK swap. Layered *on top of* whatever the Copilot SDK already emits (OBS-02), not replacing it.
- **D-21 — Concrete local backend = Logfire in local mode.** Pydantic-native, OTel-based, pairs with the Pydantic v2 already in-stack; configured `send_to_logfire=False` → clean console output, no account/egress for local runs. Chosen over pure OTel-SDK-+-ConsoleSpanExporter for DX; the OTel API abstraction (D-20) keeps the exporter swappable.
- **D-22 — Run↔provenance correlation (OBS-03) via a shared `run_id`.** Each drafting run mints a `run_id` (the OTel trace id, or derived from it) that is stamped into the matching `provenance.yaml` `generations[]` entry, so the runtime trace and the on-disk audit surface line up.

### Provider seam, mock & SDK pin (SEAM-03/04, SKEL-04/05)
- **D-23 — Ship the real Copilot adapter AND a deterministic `MockDraftingProvider`.** Mock returns a canned, deterministic `DraftResult` (plus synthetic provenance fields) so the **port (SEAM-03) and the full loop run in CI without the SDK**. Real adapter on the pinned SDK is the production path.
- **D-24 — Acceptance proof = mock in CI + real local smoke.** The deterministic mock is the **CI-runnable** proof of the loop and the F1 writes. A real `github-copilot-sdk==1.0.2` run is the **manual local smoke test** (SKEL-05), demonstrated once (capture the run as evidence) and **kept out of CI** — no Copilot CLI auth in CI, and issue #1606 (CLI auto-update breaking SDK transport) is a real risk. The smoke test **gates SDK/CLI version bumps**.
- **D-25 — Provider selection by explicit choice, defaulting to Copilot.** A CLI flag (`--provider copilot|mock`) with an env/config fallback; default = `copilot`, CI/tests use `mock`. No runtime plugin discovery (that's v2 / non-goal, per D-07).
- **D-26 — SEAM-04 = design-only.** The `DraftingProvider` port is documented as Copilot-agnostic (domain verbs, no SDK shapes leaking — ARCHITECTURE.md Anti-Pattern 2). The **mock *is* the second provider** that proves swappability. OpenCode SDK / homegrown Pydantic AI are **named as viable target alternates, not built**.
- **D-27 — Pin both `github-copilot-sdk==1.0.2` and a compatible Copilot CLI**, and handle "backend unavailable" as a **handled, non-crashing state** (clear message, nonzero exit) — SKEL-05. This is where D-08's deferred real SDK dependency lands.
- **D-28 — Bounded read-only toolset = `grep` / `glob` / `view` only** (SKEL-04). No write/exec/network tools; enforced via the SDK's per-agent `tools` allowlist + session `excludedTools` (ARCHITECTURE.md Pattern 3 / Anti-Pattern 4).
- **D-29 — Upgrade seam enforcement to `import-linter`** now that the SDK is a real installable dependency (the named D-09 upgrade), alongside/replacing the Phase-1 AST check. *(Confirm at planning whether to keep the AST check as belt-and-braces.)*

### Dogfood target & output layout (PLAN-01, SKEL-01/02)
- **D-30 — Dogfood THIS repo.** dogen drafts documentation for `dogen` itself. **`.planning/` is excluded from source-lookup and is NEVER written to** (it is GSD's directory — no collision). Agent sources = `src/dogen/**`, `README.md`, `AGENTS.md`, `pyproject.toml` (the code this phase builds).
- **D-31 — Output layout: audit surface in `.dogen/units/<unit-id>/`, drafted MyST `.md` under `docs/`** (the Sphinx root). The audit YAML/MD (`unit.md`, `provenance.yaml`, `progress.yaml`) stays out of the publishable docs tree; the draft lands where Sphinx builds it.
- **D-32 — First unit = a reference/explanation page about dogen** (e.g. the CLI usage or the provider seam), drafted from the real `src/dogen/` + `README`/`AGENTS.md`. Exact unit/title is a planning detail.

### F1 schema v0 (PLAN-01..07)
- **D-33 — Per-unit directory `.dogen/units/<unit-id>/` with `unit.md` + `provenance.yaml` + `progress.yaml`** (PLAN-01). YAML front-matter + Markdown body; git-diffable.
- **D-34 — `schema_version` integer (`0`) at the top level of each machine-readable file** (`provenance.yaml`, `progress.yaml`, and `unit.md` front-matter) so migrations are explicit/detectable (PLAN-02).
- **D-35 — `unit.md` front-matter = the editable steering+plan artifact** (PLAN-03): `unit_id`, `intent` (reference|tutorial|how-to|explanation — DIRECTION), `audience`, `title`, `sources` (human-pointed, list of `{path|ref}`), `sphinx_target`, `steering_notes`, `status` (mirrors progress). The operator authors this by hand.
- **D-36 — `provenance.yaml` is the unit's consolidated audit record.** Top-level blocks:
  - `steering:` — the **recorded HITL event** (PLAN/HITL): `{author, at, intent, audience}`, stamped by `dogen steer`.
  - `generations[]` — one entry per draft pass (PLAN-04): `model`, `model_version`, `effort`, `tooling_version`, `sdk` (version), `context_origins` (what the agent **actually read** — distinct from the human-pointed `sources`), `tools_used`, `run_id` (OBS-03 link), `at`, `action`.
  - `reviewer_edits[]` — post-generation human edits (PLAN-05): `{at, reviewer, summary}`.
  - `verification:` — **reserved, empty at v0** (PLAN-07): `steps: []`, each reserving `{id, state: unverified, evidence: null, env_fingerprint: null}`.
- **D-37 — `sources` (human-pointed, in `unit.md`) and `context_origins` (agent-actually-read, in `provenance.yaml`) are two distinct fields.** The gap between them is itself audit-relevant — never collapse them.
- **D-38 — `progress.yaml` lifecycle = `pending → sourced → drafted → reviewed → committed`** (PLAN-06), with `schema_version`, `unit_id`, `state`, and a `history[]` of `{at, state}`. The loop auto-advances `pending → sourced → drafted`; `dogen review` sets `reviewed`; **the tool NEVER sets `committed`** (it encodes the scope border — no push/PR/build/publish states exist). SKEL-03 stop-before-commit.

### Provable HITL gate (HITL-01/02)
- **D-39 — "Recorded steering" = an explicit `dogen steer` event.** The operator edits `unit.md` (intent/audience/sources), then runs `dogen steer <unit>`, which **stamps `{author, at}` (+ the steered intent/audience) into `provenance.yaml.steering`**. This is the strongest AC5 audit: steering provably *precedes* the draft as a discrete recorded act.
- **D-40 — `dogen draft` hard-refuses without a recorded steering event** (HITL-01): clear message + nonzero exit, no draft produced ("no recorded steering → no draft"). An audit of `.dogen/units/` then shows no substantial draft lacking a recorded human steering input (HITL-02 / AC5).
- **D-41 — Author + timestamp captured from git config** (`user.name` / `user.email`) at `dogen steer` / `dogen review` time.

### CLI command surface (SKEL-01, UX)
- **D-42 — Four thin subcommands** (Typer): `dogen unit new <id>` (scaffold an editable `unit.md` template; optional `--intent`/`--audience` pre-fill) → operator edits → `dogen steer <id>` (record the HITL steering event) → `dogen draft <id>` (run the loop, write draft + provenance + progress) → `dogen review <id> --note "..."` (append a `reviewer_edits` entry, advance progress to `reviewed`). PLAN-05/06 are **exercised end-to-end**, not merely declared. CLI stays thin — no business logic (ARCHITECTURE.md).

### Sphinx-publishable proof & docs toolchain (SKEL-02; resolves D-17)
- **D-43 — Prove publishability with a real, minimal Sphinx build in CI.** Stand up `docs/conf.py` + `.readthedocs.yaml` configured for **MyST + `colon_fence`** (Sphinx 9.1.0 / myst-parser 5.1.0, Python 3.12), and a CI job that **actually builds** the drafted page. "Sphinx-publishable" is proven, not asserted. This resolves the Phase-1 deferral D-17.

### Licensing follow-on (surfaced by real docs landing)
- **D-44 — A docs/content license decision now becomes live** (D-03 deferred it to "when real docs land" — that is this phase). Drafted `.md` under `docs/` and any committed sample output are prose/content needing SPDX headers for `reuse lint`. **Lean `CC-BY-SA-4.0`** (Canonical policy default for docs) — but first reconcile the policy's own `CC-BY-NC-SA-4.0` inconsistency, per D-03. Resolve at planning.

### Claude's Discretion
- Exact OTel span names/attributes and Logfire configuration details.
- The mock provider's canned draft content/shape (must be deterministic).
- Provider-selection precedence details (flag vs env vs config).
- Exact wording/fields of the `unit.md` scaffold template.
- Progress/streaming UX during a draft run (status lines, where written-file paths are reported at the end).
- The smoke-test harness layout and how it gates SDK/CLI bumps.
- Whether to keep the Phase-1 AST seam check alongside `import-linter` (D-29).
- The precise sub-module layout inside `core/` (`models.py`, `ports.py`, `orchestrator.py`, instrumentation) and `adapters/` per ARCHITECTURE.md.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Binding in-repo references (read first)
- `.planning/refs/coding-guide.md` — **binding** coding standards (ruff + `ty`, AI-anti-pattern→rule table, testing rules, architecture invariants, REUSE/Canonical file header §7). Every new file in this phase follows it.
- `.planning/refs/licensing.md` — **system of record** for licensing; holds the docs/content-license rules relevant to D-44 (CC-BY-SA-4.0 vs the policy's CC-BY-NC-SA-4.0 inconsistency).
- `AGENTS.md` — agent operating contract (seam invariant, AI discipline, provenance, shell-allowlists, header, branching). **Also a dogfood source** (D-30).
- `.planning/refs/synthetic-code-provenance.md` — the dev-process provenance prompt/templates; **mirrors the product `provenance.yaml` shape** — useful reference when designing D-36's fields.
- `.planning/refs/engineering-handbook.md` — Canonical engineering practice (trunk-based dev, versioning/release model, machine-assisted-development critique).

### Architecture & schema (the skeleton's shape)
- `.planning/research/ARCHITECTURE.md` — hexagonal core/adapters layout; **Pattern 1** (Provider Port + Adapter), **Pattern 2** (one capability steered by intent), **Pattern 3** (bounded read-only toolset); the **F1 planning-directory/provenance schema sketch**; **Anti-Patterns 1–4** (SDK leak, vendor-mirroring port, four-flows, unbounded tools); the build order (A2+F1 first).
- `.planning/research/STACK.md` — `github-copilot-sdk==1.0.2` + CLI pin guidance and **issue #1606**; Sphinx 9.1.0 / myst-parser 5.1.0 / `colon_fence`; Logfire/OTel observability; Typer; Python 3.12.
- `.planning/research/PITFALLS.md` — **Pitfall 4** (seam leak) and **Pitfall 9** (scope border past commit) — invariants the loop and the schema must protect.
- `.planning/research/FEATURES.md` — feature framing for the A2/F1 slice.

### Project planning & requirements
- `.planning/ROADMAP.md` → "Phase 2" — goal, the 19 requirements, the six success criteria, and the open-decision notes (now resolved here).
- `.planning/REQUIREMENTS.md` — SKEL-01..05, SEAM-03/04, PLAN-01..07, HITL-01/02, OBS-01..03 (full wording downstream agents must satisfy).
- `.planning/phases/01-compliant-scaffold-provider-seam-boundary/01-CONTEXT.md` — Phase-1 decisions carried forward: **D-07** (hot-swap = design property), **D-08** (empty adapter → real SDK lands now), **D-09** (AST check → `import-linter` upgrade), **D-12** (uv+hatchling, Python 3.12), **D-17** (Sphinx deferred → now), **D-18** (uv.lock + dep-bot deferred → now relevant with the SDK pin).

### Research flag (verify before/at planning)
- **Verify the exact `github-copilot-sdk==1.0.2` Python API** against the installed package — session creation, tool allowlisting, model/effort selection, event/streaming surface, `@define_tool`. ARCHITECTURE.md's code examples are **illustrative**, not verified API names.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/dogen/{core,adapters/copilot,cli}/__init__.py` — empty stubs from Phase 1; this phase fills them (`core/models.py`, `core/ports.py`, `core/orchestrator.py`, core instrumentation; `adapters/copilot/{provider,tools,mapping}.py`; `adapters/planning_fs.py`; a mock provider; `cli/main.py`).
- **Phase-1 seam guardrail** (AST check, single-sourced by pytest) — upgrade target for `import-linter` (D-29) now the SDK is a real dep.
- **Phase-1 CI workflow + pre-commit mirror** — extend with the drafting-loop smoke gate (D-24) and the Sphinx build job (D-43).
- **`canonical.jinja2` REUSE template** — annotate every new source/content file (incl. drafted `.md` per D-44).

### Established Patterns
- **Hexagonal, inward-only deps** (ARCHITECTURE.md): `core/` has **zero vendor imports**; the Copilot SDK is imported **only** in `adapters/copilot/`. Ports shaped by domain verbs, not SDK signatures.
- `core/` (pure) / `adapters/copilot/` (sole SDK importer) / `cli/` (thin) layout is fixed from Phase 1.

### Integration Points
- **NEW real dependency:** `github-copilot-sdk==1.0.2` → pinned Copilot CLI via JSON-RPC, confined to `adapters/copilot/` (D-27).
- **Observability:** OTel API in `core/` → Logfire local backend (D-20/21).
- **Docs build:** drafted `.md` in `docs/` → Sphinx 9.x build in CI (D-43).
- **F1 surface:** `PlanningStore` port → filesystem adapter over `.dogen/units/` (D-31/33).
</code_context>

<specifics>
## Specific Ideas

- User explicitly wants **a test run by dogfooding this repo** — "dogfooding this repo seems to be the best idea but I need to exclude `.planning` obviously." Drove D-30/31/32: draft dogen's own docs, exclude `.planning/` from both source-lookup and output.
- User accepted the **recommendation-first defaults** across all areas (Logfire-local, mock+real-smoke, `.dogen/units/`+`docs/`, real Sphinx build), and chose the **stronger provability options** where offered: explicit `dogen steer` event (over implicit capture) and a working `dogen review` command (over reserve-field-only) — provable HITL and exercised PLAN-05/06 matter to the user.
</specifics>

<deferred>
## Deferred Ideas

- **Steering layering org→repo→writer** (STEER-01) — the `steering/resolver.py` merge; v2.
- **Type-aware breadth across all four intents** — the skeleton drives ONE intent path via prompting; proving reference/tutorial/how-to/explanation all flow through one pipeline is later.
- **SDLC connectors** (PR/bug/commit lookup, CONN-01) — `sources[].ref` is reserved in the schema; add as new bounded tools/MCP later.
- **DOCPR-2822 `QaHook` extension point** (CONN-03) — not even a v1 port; keep the core thin.
- **Singular traceable local commit** (STEER-03) — the hard border; `progress` reserves `committed` but the tool never sets it; v2.
- **Actionable-content verification execution** (VERIFY-01/02) — only the `verification:` fields are reserved+empty at v0 (PLAN-07).
- **Real second provider adapter** (OpenCode SDK / Pydantic AI) — design-only now (D-26); building one is v2.
- **RAG / context-augmentation** — spike-gated; default do-not-build.
- **Dependency-update bot** (Renovate/Dependabot) — now relevant with the SDK/CLI pin (D-18); confirm at planning whether it lands this phase or next.

None — discussion stayed within phase scope.
</deferred>

---

*Phase: 2-Walking Skeleton, Planning Schema, Provable HITL & Observability*
*Context gathered: 2026-06-19*
