# Feature Research

**Domain:** Agentic documentation-drafting tooling (HITL, draft-only, docs-as-code; Python layer on an adopted agent SDK)
**Researched:** 2026-06-19
**Confidence:** MEDIUM (grounded in real comparable tools — Mintlify, Katara, GitHub Copilot agents/skills, Microsoft Document Writing agent, install-md, doctest — via web search; not yet cross-checked against hands-on trials)

## How to read this file

The PROJECT.md vision is the input; this file **validates and augments** it against what AI/agentic doc tools actually ship in 2026. For each feature it answers: is this conventional (everyone has it) or unusual (a real edge)? The headline finding:

> Most of the epic's feature set is **conventional** as individual capabilities (type-aware generation, instruction/skill layering, provenance, HITL checkpoints all exist in shipping tools). The project's genuine edges are (1) **evidence-gated verification of actionable content** — proving steps run, which no mainstream drafting tool does — and (2) the **deliberate restraint**: unit-scoped iteration + a hard stop at local commits, where the market default is full-set generation that auto-opens PRs.

The strategy implication: differentiate on verification + disciplined scope and *provable* HITL, not on "AI writes docs" (commoditized).

## Comparable tools surveyed

| Tool | What it is | Most relevant trait |
|------|-----------|---------------------|
| **Mintlify Agent** | AI-native docs platform agent | Researches/plans/writes across many files, **auto-opens PRs**, verifies via **build checks only** |
| **Mintlify AI Assistant** | Agentic-RAG chat over published docs | Reader-facing; an anti-feature direction for this project |
| **Katara** | AI Diataxis workflow | Content classifier into Diataxis types + **optional HITL circuit at every step** |
| **GitHub Copilot** (custom agents + Agent Skills) | The likely SDK substrate | `.agent.md` personas, `SKILL.md` skills, `AGENTS.md` instructions — three-tier customization |
| **Microsoft Copilot Document Writing agent** | Long-form doc generator | Template/reference-driven, customizable tone/style |
| **install-md** (Mintlify) | Executable-instruction format | "DONE WHEN" measurable success criteria + verification commands |
| **doctest / "validation via simulation"** | Executable-doc precedents | Run embedded examples / execute each step and check resulting state |

## Feature Landscape

### Table Stakes (Users Expect These)

Missing these and a 2026 doc-drafting tool is not credible. Notably, several of these are *already_ commodity — they are necessary but win nothing.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Drafts a real, structurally-complete doc unit from sources (code, specs, existing docs, tickets) | Every comparable tool (Mintlify, MS Document Writing agent, Copilot @docs-agent) does code-to-docs drafting | MEDIUM | The walking-skeleton A2 loop. Quality bar is "review-ready draft," not perfect. |
| Sphinx-publishable output (correct directives/structure, not just prose) | Output must drop into the GitHub+RTD+Sphinx stack without reformatting | MEDIUM | Format-correctness is a *table stake*; getting RST/MyST right is fiddly but well-trodden. |
| Type/format steering (reference vs tutorial vs how-to vs explanation) | Katara classifies into Diataxis; MS agent customizes format/tone. Type-awareness is now expected | MEDIUM | Project framing is correct: this is **one intent-steered capability, not four flows**. Conventional capability, sensible packaging. |
| Instruction/style customization via a config file | `AGENTS.md` is the cross-tool standard (Copilot, Cursor, VS Code, Claude Code); Mintlify uses it too | LOW | Reuse the convention; do not invent a bespoke config language. |
| Human review/edit checkpoint before output is finalized | HITL approve/reject/edit is the standard pattern; Mintlify gates behind PR review, Katara at every step | LOW-MEDIUM | The *checkpoint* is table stakes. Making it **provable/recorded** is the differentiator (below). |
| Source/context pointing ("draft this feature from these inputs") | Mintlify connects repos + Slack/Notion/Linear; operator-steered context is expected | MEDIUM | Project's "operator-supplied product expertise" = this, done deliberately rather than via broad auto-ingest. |
| Provider/SDK abstraction seam | Vendor churn makes a thin seam expected hygiene, not a feature users see | LOW-MEDIUM | Constraint in PROJECT.md; cheap if done at the start, expensive to retrofit. |
| Iterative refinement of a draft (re-steer, regenerate a section) | Conversational refinement is baseline in all agent tools | LOW | Falls out of the agent SDK; mostly a UX concern. |

### Differentiators (Competitive Advantage)

Where this tool can actually stand out. These align with Core Value ("quality at speed, without AI slop") and the constraints.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Evidence-gated verification of actionable content** (tutorials/how-tos cannot be "done" until their steps are proven to run) | No mainstream drafting tool does this. Mintlify verifies *builds*, not *step execution*. This directly kills the most dangerous AI slop: confident-but-wrong procedures | **HIGH** | The epic's hardest problem, correctly flagged. Precedents are partial: doctest (run embedded examples), install-md ("DONE WHEN" + verification commands), and a "validation via simulation" patent (execute step, inspect app state, confirm next step reachable). None is a turnkey solution. Expect a spike. LLM-generated executable content runs unmodified only ~70-90% of the time, so the gate must catch the 10-30% failures. |
| **Provable / recorded HITL** (steering on intent + audience captured as durable provenance, tied to the repo's accountability model) | "Accountable intelligence" — a human who took responsibility — is the literal antidote to AI slop. Most tools have a review *step* but no durable record of *what the human steered* | MEDIUM | F1 planning-directory schema is the substrate. Differentiator is the *audit surface* (AC5), not the checkpoint itself. |
| **Layered customization: org-wide guidance (external) -> per-repo knowledge -> writer preferences** | Copilot has agents/skills/instructions layering, and AGENTS.md can be split by scope — but org-vs-repo-vs-writer as an explicit, decoupled hierarchy is uncommon and high-value at portfolio scale | MEDIUM-HIGH | Differentiator is **decoupling the reusable core from the org guidance it consumes** so one portfolio update benefits everyone. The layering mechanic is conventional; the governance model is the edge. |
| **Unit-scoped iterative drafting (deliberately NOT one-shot full sets)** | The market default (Mintlify) is full-set, multi-file generation. Unit scope keeps the human review burden tractable — directly addresses the documented "workload asymmetry" of AI generation | MEDIUM | Counter-positioning: the restraint *is* the feature. Easier to verify, easier to review, less slop. |
| **Internal provenance trail** (model/version/effort, tooling version, context origins, reviewer edits) | Good Documentation Practice (ALCOA+) and audit needs: orgs cannot stand behind output without knowing who/what produced it | MEDIUM | Internal observability only — explicitly **not** a published disclaimer (see anti-features). |
| **Local onboarding / style-scraper** (code-to-docs map + repo style, glossary, structure artefacts) | Bootstraps per-repo knowledge without a heavyweight index; makes the tool deployable by any TA across products | MEDIUM | Cheaper, more legible alternative to RAG for the per-repo layer. Feeds the layered-customization middle tier. |
| **Optional extension point to org-wide doc QA** (DOCPR-2822) without absorbing it | Coexistence keeps the core thin while allowing a richer quality pipeline downstream | LOW-MEDIUM | A seam/hook, not an integration build, this cycle. |

### Anti-Features (Commonly Requested, Often Problematic)

Things mainstream tools do that this project should deliberately NOT build. Each is grounded in a real tool that does it.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-commit / push / open PRs / build / publish** | Mintlify Agent auto-opens PRs; feels like "full automation." Tempting to match | Crosses the accountability border — the framework would own output it cannot stand behind; defeats provable HITL; turns review into rubber-stamping the asymmetry warns about | **Hard stop at singular, traceable LOCAL commits.** Reviewer/merger owns everything downstream. |
| **One-shot full-set generation** | Mintlify/MS agents generate many files at once; looks productive | Produces unreviewable volume, maximizes slop and the generation/review workload asymmetry, hides which unit is verified | Unit-scoped iteration with per-unit verification and review. |
| **Public "AI-generated" disclaimer/watermark on shipped content** | Seems like the honest, compliant move | Slop research is explicit: provenance is "not a watermark you can strip — it is a human who took responsibility." A public label both undersells human ownership and is trivially gamed | **Internal** provenance/observability only; humans own and sign off on shipped docs. |
| **Premature RAG / semantic or structural context index** | "Give the agent all the context" is the reflex; everyone ships RAG | Over-engineering for human-guided, unit-scoped Mode A; adds infra, drift, and failure modes before the loop is proven | Steering-first (operator points at sources) + style-scraper for repo knowledge. **Spike-gate** any index build (S1); default do-not-build. |
| **Reader-facing AI assistant / chat-over-docs** (Mintlify Assistant, MCP server) | It is Mintlify's flagship and very visible | Different product (consumption, not drafting); out of scope and a large net-new surface | Stay on the drafting side of the line; leave consumption to the publishing stack. |
| **Building agent machinery / the agent core** | Control, no vendor lock-in | Reinvents the SDK; the value-add is the drafting layer, not the runtime | Adopt the Copilot SDK behind a thin seam; build only the doc-drafting layer. |
| **Persistent agentic memory** (mem0/Cognee-style) | Agents "should remember" across sessions | Mode-B-facing; unnecessary for human-guided unit-scoped work; adds statefulness and privacy/provenance complexity | Provenance store (F1) captures what matters durably; no autonomous memory. |
| **Continuous verification of content over time** | Docs rot; "keep them correct forever" is appealing | That is a different epic (DOCPR-2822); absorbing it bloats scope | Verify at draft time; coexist with / optionally call DOCPR-2822 for ongoing QA. |
| **Doc-stack / provider agnosticism beyond the proven stack** | "Support everything" sells | Untestable breadth before one stack is proven; agnosticism-as-feature vs agnosticism-as-design-property | Prove GitHub+RTD+Sphinx + Copilot SDK; keep agnosticism as a *seam*, not shipped breadth. |

## Feature Dependencies

```
SDK abstraction seam
    └──enables──> Drafting (A2 walking skeleton)
                      └──requires──> Sphinx-publishable output
                      └──steered-by──> Type/intent steering (Diataxis as direction)
                      └──steered-by──> Source/context pointing

Planning-directory schema v0 (F1)
    └──enables──> Provable/recorded HITL (intent + audience steering captured)
    └──enables──> Internal provenance trail
    └──enables──> Layered customization (org -> repo -> writer surfaces)

Style-scraper / onboarding
    └──feeds──> Per-repo knowledge layer (middle tier of layered customization)

Evidence-gated actionable verification
    └──requires──> Drafting (something to verify)
    └──requires──> A runnable target/sandbox (the genuinely hard part)
    └──gates──> "Done" state for tutorials/how-tos only (not reference/explanation)

Hard stop at local commits  ──conflicts──>  Auto-PR / push / publish
Unit-scoped iteration       ──conflicts──>  One-shot full-set generation
Internal provenance         ──conflicts──>  Public AI-generated disclaimer
Steering-first context      ──conflicts──>  Premature RAG index
```

### Dependency Notes

- **SDK seam must come first:** retrofitting an abstraction after coupling to Copilot is expensive; doing it at A2 is cheap. It is a prerequisite for *all* drafting.
- **F1 schema underpins three differentiators:** provable HITL, provenance, and layered customization all read/write the same planning-directory surface. F1 is correctly first-milestone alongside A2.
- **Evidence-gated verification depends on a runnable target.** The drafting is the easy half; standing up a sandbox where steps can actually execute and state can be inspected (cf. "validation via simulation," doctest, install-md) is the hard half — isolate it in a spike before committing a phase.
- **Verification gate applies only to actionable types.** Reference and explanation content have no "steps that run"; the gate is intent-conditional, reinforcing that type-steering must exist before/alongside verification.
- **The four anti-feature conflicts are design invariants,** not just deferrals — each protects the Core Value (no slop) or a hard constraint (accountability border).

## MVP Definition

### Launch With (v1 = first milestone: A2 + F1)

- [ ] Thin end-to-end drafting loop: agent drafts ONE small unit from human-pointed sources into Sphinx-publishable output — proves the loop, not quality
- [ ] SDK abstraction seam around the Copilot SDK — cheap-swap design property from day one
- [ ] Planning-directory schema v0 (F1): intent/audience steering, unit plan, provenance fields, progress — the audit + provenance substrate
- [ ] No commit logic (loop stops before commit at this milestone, per A2 scope)

### Add After Validation (v1.x)

- [ ] Type/intent steering surfaced as one capability (reference/tutorial/how-to/explanation as direction) — trigger: loop proven, quality work begins
- [ ] Singular traceable local-commit boundary (the hard stop) — trigger: drafting trustworthy enough to land
- [ ] Layered customization tiers (org -> repo -> writer) wired to F1 surfaces — trigger: multi-repo/portfolio use
- [ ] Style-scraper / onboarding artefacts — trigger: need repeatable deployment across products
- [ ] Internal provenance trail fully populated and queryable — trigger: audit (AC5) demand

### Future Consideration (v2+)

- [ ] Evidence-gated actionable verification — defer behind a spike; highest value AND highest risk; do not block MVP on it
- [ ] Context-augmentation index (RAG/structural) — spike-gated (S1), default do-not-build
- [ ] DOCPR-2822 QA extension point — coexistence hook once core is stable
- [ ] Mode B (agent-guided research/planning) — largest net-new build, lowest risk to defer

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| End-to-end unit drafting loop (A2) | HIGH | MEDIUM | P1 |
| SDK abstraction seam | MEDIUM | LOW | P1 |
| Planning-directory schema v0 (F1) | HIGH | MEDIUM | P1 |
| Sphinx-publishable output | HIGH | MEDIUM | P1 |
| Type/intent steering (Diataxis as direction) | HIGH | MEDIUM | P2 |
| Hard stop at local commits | HIGH | LOW | P2 |
| Provable/recorded HITL | HIGH | MEDIUM | P2 |
| Layered customization (org/repo/writer) | HIGH | MEDIUM-HIGH | P2 |
| Internal provenance trail | MEDIUM | MEDIUM | P2 |
| Style-scraper / onboarding | MEDIUM | MEDIUM | P2 |
| Evidence-gated actionable verification | HIGH | HIGH | P3 (spike first) |
| Context-augmentation index (RAG) | LOW (Mode A) | HIGH | P3 (do-not-build by default) |
| DOCPR-2822 QA extension point | MEDIUM | LOW-MEDIUM | P3 |
| Mode B (agent-guided) | MEDIUM | HIGH | P3 |

**Priority key:** P1 = must have for launch (this milestone) · P2 = next pulses · P3 = future/spike-gated

## Competitor Feature Analysis

| Feature | Mintlify Agent | Katara | GitHub Copilot (agents/skills) | Our Approach |
|---------|----------------|--------|--------------------------------|--------------|
| Drafting scope | Full-set, multi-file | Per-content workflow | Per-task agent | **Unit-scoped, iterative** |
| Output handling | **Auto-opens PRs** | In-tool edits | Repo edits / PRs | **Stop at local commit (hard border)** |
| Type-awareness | Style/format config | **Diataxis classifier** | Persona/skill prompts | Intent steering (one capability) |
| Verification | **Build checks only** | None evident | Tests if asked | **Evidence-gated step execution (differentiator)** |
| HITL | PR review | **Per-step edit circuit** | Inline accept/reject | **Provable, recorded steering** |
| Customization | AGENTS.md + integrations | n/a | agents + skills + AGENTS.md | **Layered org -> repo -> writer (decoupled)** |
| Provenance | Implicit (PR history) | n/a | n/a | **Internal observability trail** |
| Context strategy | Repo/Slack/Notion connect | Existing content | Skills + instructions | **Steering-first; RAG spike-gated** |

## Sources

- Mintlify — AI-native docs, Agent launch, agent customization, install-md (MEDIUM): https://www.mintlify.com/docs/ai-native · https://www.mintlify.com/blog/agents-launch · https://www.mintlify.com/docs/agent · https://github.com/mintlify/install-md
- Katara — Diataxis AI workflow with per-step HITL (MEDIUM): https://www.katara.ai/blog/diataxis
- GitHub Copilot — custom agents, Agent Skills, AGENTS.md (MEDIUM): https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli · https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills · https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
- Microsoft Copilot Document Writing agent template (MEDIUM): https://learn.microsoft.com/en-us/microsoft-365/copilot/copilot-tuning-document-writing-template
- Executable-doc verification — Python doctest, LLM test-case executability study, validation-via-simulation patent (MEDIUM): https://docs.python.org/3/library/doctest.html · https://arxiv.org/pdf/2506.16586
- AI slop / provenance / accountability (MEDIUM): https://medium.com/@maxdolphin/ai-slop-and-the-new-knowledge-supply-chain-f1cabcc50b22 · https://www.softwareseni.com/ai-slop-defence-provenance-verification-data-quality-gates-and-content-governance/ · https://arxiv.org/html/2603.27249v1
- HITL workflow patterns (MEDIUM): https://zapier.com/blog/human-in-the-loop/

---
*Feature research for: agentic documentation-drafting tooling (HITL, draft-only, docs-as-code)*
*Researched: 2026-06-19*
