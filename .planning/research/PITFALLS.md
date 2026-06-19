# Pitfalls Research

**Domain:** Agentic documentation-drafting framework (thin Python drafting layer over an adopted agent SDK; human-in-the-loop; draft-only, stop at local commit)
**Researched:** 2026-06-19
**Confidence:** MEDIUM (web-sourced industry evidence on AI-docs failure modes + domain reasoning grounded in PROJECT.md; no single authoritative source for this exact niche)

> **Phase legend** (from PROJECT.md): A=core, B=onboarding/style-scraper, C=lookup, D=customization (layered guidance), E=generation+verification, F=HITL/provenance. **Near-term first-pulse scope is A2 (walking skeleton) + F1 (planning-directory schema v0)**, so pitfalls are flagged for A2/F1 where the design decision lands *now*, even when full mitigation arrives in a later phase.

## Critical Pitfalls

### Pitfall 1: Evidence-free actionable content (the "looks-run-but-wasn't" tutorial)

**What goes wrong:**
The agent drafts a tutorial or how-to whose steps were *never actually executed* — commands, flags, file paths, and expected output are plausible but fabricated. The reader follows them, hits step 4, and it fails. This is the epic's self-declared hardest problem, and it is the single most damaging failure mode because actionable docs make a promise ("do this and it works") that prose docs do not.

**Why it happens:**
LLMs generate the *shape* of a correct procedure from training priors, not from observed execution. Up to ~42% of AI-generated code snippets in industry studies contain phantom functions, nonexistent APIs, or confidently-wrong CLI flags. A drafting agent with no execution loop has no way to know the difference between "this command works" and "this command looks like it should work." Teams skip the execution gate because running steps in a sandbox is the expensive, fiddly part — far easier to trust the prose.

**How to avoid:**
- Make verification *evidence-gated, not assertion-gated*: an actionable step is only "verified" if there is captured proof it ran. Borrow the doctest / `sphinx.ext.doctest` / `sphinxcontrib-shtest` model — documented commands double as executable tests; actual output is compared against documented output.
- Capture **logged proof** as a first-class artifact: command, exit code, stdout/stderr, environment fingerprint, timestamp. Store it in the F1 planning schema as a provenance record attached to the unit, so "verified" is a recorded fact with evidence, not a claim.
- Default actionable content to an explicit `unverified` state. Only a successful, logged run flips it to `verified`. Never let the model self-certify.
- Keep the execution environment reproducible (the Workshop-contained test model in PROJECT.md is the right home for this).

**Warning signs:**
- "Verification" is the model asserting steps are correct rather than a captured run log.
- Expected-output blocks in drafts are suspiciously clean/generic (no real paths, no real version strings, no incidental warnings).
- No schema field distinguishes `verified` from `unverified`; everything is implicitly trusted.

**Phase to address:**
**E (generation+verification)** owns the execution loop and evidence capture. **F1 (now)** must reserve the schema fields — per-step verification state, evidence pointer (log artifact), environment fingerprint — so E has somewhere to write proof. Designing F1 without these fields forces a breaking schema change later. **A2 (now)** should at minimum *model the seam* for "draft → (later) verify" even if A2 only drafts.

---

### Pitfall 2: Hallucinated APIs, symbols, and CLI flags in drafted docs

**What goes wrong:**
The agent documents a function, class method, config key, or CLI flag that does not exist in the target project — or exists but with a different signature/name. Reference docs are especially exposed because they look authoritative.

**Why it happens:**
The model interpolates from training-data conventions ("most CLIs have a `--verbose`") rather than from the actual source. Without grounding, plausible-but-wrong is the default output. PROJECT.md already enables a plan drift-guard / source-grounding gate — the risk is that it is treated as a checkbox rather than enforced symbol-by-symbol.

**How to avoid:**
- Enforce **source-grounding as a hard gate**: every API symbol, flag, and path the draft asserts must resolve against a real artifact in the pointed-at sources (code, `--help` output, specs). If it does not resolve, it is flagged, not shipped.
- Prefer extracting symbols from the source (introspection, `--help` capture, AST/signature parsing) over letting the model free-recall them.
- Pair grounding with static checks where cheap: a symbol-existence pass over the draft against the source surface.
- Record in provenance *which source* grounded each claim, so a reviewer can trace any symbol back to its origin.

**Warning signs:**
- The drift-guard passes at the document level but nothing checks individual symbols.
- Drafts reference flags/methods not present in the human-pointed sources.
- Grounding is "the model was given the code in context" with no post-hoc verification that what it wrote matches what it was given.

**Phase to address:**
**E (generation+verification)** for the symbol-resolution gate; the existing drift-guard lives here. **A2 (now)** is the earliest place this bites — even the walking skeleton drafting "one small unit from human-pointed sources" can emit a hallucinated symbol. Build the skeleton so source extraction feeds the prompt, establishing the grounding habit from day one. **F1 (now)** stores the source-of-record per claim.

---

### Pitfall 3: AI slop — generic, lore-blind content that ignores style and product intent

**What goes wrong:**
Output is fluent but hollow: overused phrasing ("delve into," "seamless," "robust"), generic structure, no awareness of project lore, the repo's established voice, the glossary, or what the product is actually *for*. It reads like documentation-shaped filler. Reviewers either spend more time fixing it than writing from scratch (see Pitfall 6) or, worse, ship slop.

**Why it happens:**
LLMs default to the averaged voice of their training data. Without explicit, *specific* steering they produce vague output — vague rules produce vague results. Teams under-invest in feeding the model the org guidance, per-repo knowledge, and writer preferences that make output distinctive.

**How to avoid:**
- Treat steering as a first-class input, layered exactly as PROJECT.md describes: org-wide guidance → per-repo product knowledge → writer preferences. Each layer must be concrete (real terms, real do/don't examples), not "write in a professional tone."
- Capture and reuse repo doc-style, glossary, and structure artifacts (the B onboarding/style-scraper output) so drafts inherit established voice rather than inventing one.
- Add a slop-detection pass (banned-phrase lists, repetition/meta-commentary checks) as a cheap quality gate before the human sees the draft.
- Record the steering inputs in provenance so a poor draft can be traced to thin/missing guidance rather than blamed vaguely on "the AI."

**Warning signs:**
- Drafts could belong to any product (no proper nouns, no lore, no glossary terms).
- Telltale buzzwords and repeated boilerplate openings.
- Style guidance fed to the agent is generic prose rather than specific, example-backed rules.

**Phase to address:**
**D (customization / layered guidance)** owns the steering layers; **B (onboarding/style-scraper)** produces the per-repo style/glossary artifacts that prevent generic voice. **A2 (now)** should at least thread *one* steering input through the skeleton so customization is a designed seam, not a bolt-on. **F1 (now)** records which steering layers were active per unit.

---

### Pitfall 4: SDK lock-in leaking through the abstraction seam

**What goes wrong:**
The thin seam over the Copilot SDK exists on paper, but provider-specific concepts bleed through it — tool-call formats, streaming shapes, model/effort knobs, prompt-templating quirks, tokenizer assumptions. A later SDK swap (an explicit design goal) turns out to touch the whole drafting layer because the "abstraction" was a pass-through.

**Why it happens:**
The path of least resistance is to expose whatever the SDK already gives you. Seams leak when the internal interface mirrors the vendor's surface instead of defining its own vocabulary. Direct provider calls creep into drafting logic "just this once" under time pressure.

**How to avoid:**
- The seam must define its *own* request/response vocabulary (standardized prompt inputs, params, and response schema) — never call the provider API directly from drafting business logic.
- Establish the rule early and test it: write the seam so a second (even mock/stub) provider could be slotted in. If you cannot describe how a swap would work, the seam is leaking.
- Keep provider-specific adaptation (auth, tool-call translation, streaming) inside the adapter, behind the interface.
- Periodically grep the drafting layer for SDK-specific imports/types outside the adapter — any hit is a leak.

**Warning signs:**
- SDK types or vendor field names appear in modules outside the adapter.
- The "abstraction" method signatures are 1:1 with the SDK's.
- No one can sketch how an SDK swap would actually work.

**Phase to address:**
**A (core)** owns the seam; this is a **A2 (now)** decision — the walking skeleton is exactly where the seam shape gets set, and getting it 1:1 with the SDK now is the cheapest mistake to make and the most expensive to unwind. Build A2 with a deliberate, vendor-neutral interface even though only one provider exists.

---

### Pitfall 5: HITL theatre — unprovable, ceremonial human steering

**What goes wrong:**
The tool *claims* human-in-the-loop, but the human's involvement is cosmetic: a default-yes prompt nobody reads, or steering that is requested but never recorded. When the AC5 audit asks "prove a human steered intent and audience," there is no recorded gate to point at. This is "accountability laundering" — the human is a moral crumple zone with no real power and no evidence trail.

**Why it happens:**
Recording a *provable* decision is more work than a quick confirmation. Under time pressure and automation bias, confirmation prompts decay into rubber-stamps. Teams conflate "we showed the human the output" with "the human made a recorded, consequential decision."

**How to avoid:**
- Make the steering gate **provable by construction**: intent and audience must be *captured as recorded inputs* before drafting proceeds, stored in the F1 schema with author and timestamp. No recorded steering → no draft.
- Distinguish a *consequential* gate (the human's input changes what gets drafted) from a *ceremonial* one (a yes/no after the fact). Steer-before-draft is consequential; approve-after is theatre.
- Record reviewer edits as provenance so the human's contribution is visible and auditable, satisfying the existing repo accountability model.
- Avoid friction that pushes users to bypass the gate (ties to Pitfall 6) — but never remove the recording to reduce friction.

**Warning signs:**
- The "human-in-the-loop" is a single confirmation with a default that lets users blow through it.
- No artifact records *what* the human steered, only *that* they clicked.
- The audit story is "trust us, a human was involved."

**Phase to address:**
**F (HITL/provenance)** owns this; **F1 (now)** is the decisive moment — the planning-directory schema must make recorded intent/audience steering a structural prerequisite, not an optional field. **A2 (now)** must wire the skeleton so drafting *consumes* the recorded steering inputs, proving the gate end-to-end even in the thin slice.

---

### Pitfall 6: UX circumvention — the tool is harder than writing from scratch

**What goes wrong:**
Setup, steering ceremony, and review overhead make the tool slower than a TA just opening an editor. TAs quietly bypass it. The framework's entire value proposition ("review-ready docs faster than from scratch") inverts, and adoption dies — regardless of output quality.

**Why it happens:**
Each safeguard (steering capture, grounding, verification, provenance) adds friction. Stacked naively, the safeguards make the tool a chore. PROJECT.md explicitly names good design as a *hard requirement* precisely because friction is the default outcome of a safety-heavy tool.

**How to avoid:**
- Budget friction deliberately: every mandatory step must buy more time than it costs. Measure end-to-end time-to-review-ready against the from-scratch baseline (the external H1 UX baseline / H2 candidate assessment feed this).
- Make the high-value, low-cost path the default; make safeguards feel like assistance, not gates (e.g., pre-fill steering from the onboarding artifacts so the human edits rather than authors from blank).
- Resist solving friction by *weakening* the provable gate (Pitfall 5) — solve it with better defaults and ergonomics instead.
- Dogfood on a real candidate repo early; if the team avoids the tool, that is the signal.

**Warning signs:**
- Internal users describe steps as "ceremony" or do dry runs by hand first.
- Time-to-first-useful-draft exceeds the from-scratch baseline.
- Feature requests are all about skipping steps.

**Phase to address:**
Cross-cutting, but the foundation is set in **A2 (now)** (the end-to-end loop's ergonomics) and **B (onboarding)** (pre-filling steering to remove blank-page cost). Validate against the externally-produced H1 UX baseline.

---

### Pitfall 7: Over-engineering RAG / context augmentation before it is needed

**What goes wrong:**
The team builds a semantic or structural index, embeddings pipeline, and retrieval layer up front — a large, brittle subsystem — when steering-first drafting of human-pointed, unit-scoped sources would have sufficed for Mode A. The index becomes a maintenance burden and a source of subtle wrong-context bugs, delaying the actual value (the drafting loop).

**Why it happens:**
RAG is the industry-default answer to hallucination, so it feels mandatory. But PROJECT.md explicitly gates context-augmentation *build* behind the S1 spike with a do-not-build default, because Mode A is human-guided and unit-scoped — the human points at the sources, removing the retrieval problem RAG solves.

**How to avoid:**
- Honor the spike gate: do not build a semantic/structural index until the S1 spike proves a concrete need (likely the intentionally-unwieldy brownfield repo).
- For the MVP, source context comes from the human pointing at it, not from automated retrieval.
- If retrieval is later justified, scope it to the one repo class that needs it, not the framework default.

**Warning signs:**
- Embeddings/vector-store work appears in the roadmap before the S1 spike has run.
- Discussions assume RAG is a dependency rather than a spike outcome.
- The drafting loop slips while index infrastructure is built.

**Phase to address:**
Guarded at the roadmap level (keep it behind **S1 spike**). **A2 (now)** must work *without* RAG — human-pointed sources only — to prove steering-first is sufficient for the MVP.

---

### Pitfall 8: Provenance / planning-schema churn (F1 designed too narrowly)

**What goes wrong:**
The F1 v0 schema is designed only for what A2 needs today, then every subsequent phase (verification evidence, steering records, reviewer edits, multi-source provenance, type-direction) forces a breaking change. The schema is the future audit surface everything hangs off; churn there ripples through every consumer and invalidates stored history.

**Why it happens:**
F1 ships first, alongside the thinnest slice (A2), so the natural temptation is to model only the skeleton's immediate fields. The downstream consumers (E's verification evidence, F's steering/provenance, D's steering layers) are not yet built, so their fields get omitted.

**How to avoid:**
- Design F1 as an *extensible* schema: versioned, with reserved/optional sections for verification evidence (Pitfall 1), source-of-record per claim (Pitfall 2), active steering layers (Pitfall 3), recorded intent/audience steering (Pitfall 5), reviewer edits, and provenance (model/version/effort, tooling version, context origins).
- Include a schema version field from v0 so future migrations are explicit and detectable.
- Model the fields *now* even if A2 leaves them empty — an empty-but-present field costs nothing; an absent field costs a breaking migration.
- Keep the reusable core's schema distinct from the consumed guidance (PROJECT.md decoupling constraint) so guidance changes don't churn the schema.

**Warning signs:**
- F1 fields map only to A2's immediate needs.
- No schema version field.
- Adding verification or steering records would require restructuring, not just filling fields.

**Phase to address:**
**F1 (now)** — this is *the* design decision of the first pulse. Get the extensibility and reserved sections right at v0.

---

### Pitfall 9: Scope creep past the hard drafting boundary

**What goes wrong:**
"It would be so easy to also push the branch / open the PR / trigger the build / publish." The framework drifts past its singular hard border (drafting only; stop at singular traceable local commits), absorbing the reviewer/merger's responsibility and the separate DOCPR-2822 QA stage — diluting focus and eroding the human-owns-the-output accountability model.

**Why it happens:**
Each step past the border is individually small and "helpful." The agent already has the context; automating the next step feels natural. Boundaries erode one convenient feature at a time.

**How to avoid:**
- Treat the boundary as a hard architectural invariant: no push, no PR, no review automation, no build, no publish. The framework's last action is a singular traceable local commit.
- Make DOCPR-2822 (org-wide QA) and any publish step *external extension points the core optionally calls*, never absorbs.
- Code-review every new capability against the Out-of-Scope list in PROJECT.md.

**Warning signs:**
- Roadmap items mention PR/push/build/publish as in-scope.
- The tool starts "helpfully" offering to do the next git step.
- DOCPR-2822 functionality starts being reimplemented internally.

**Phase to address:**
**A (core)** enforces the commit boundary as an invariant; reviewed at every phase against PROJECT.md Out-of-Scope. **A2 (now)** must explicitly stop *before* commit logic (per PROJECT.md: "No commit logic" in A2) — proving the loop without crossing the border.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Self-certified verification (model asserts steps work) | Skips building the execution sandbox | Ships broken tutorials; destroys trust; is the epic's hardest problem unsolved | Never — at minimum mark content `unverified` and surface it |
| Seam mirrors the SDK 1:1 | Fastest path to a working A2 | SDK swap touches the whole drafting layer; agnosticism lost | Never — vendor-neutral vocabulary costs little up front |
| F1 schema models only A2's fields | Smaller schema now | Breaking migrations every phase; invalidated audit history | Never — reserve optional sections + version field now |
| Generic style prompt ("professional tone") | No onboarding work needed | AI slop; reviewer rewrites everything; adoption dies | MVP demo only, never for real repos |
| Build RAG up front | Feels like the standard hallucination fix | Brittle subsystem before value; delays drafting loop | Only after the S1 spike proves need |
| Confirmation-prompt "HITL" | Quick to ship | HITL theatre; fails AC5 audit; accountability laundering | Never — record consequential steering |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Copilot SDK | Calling provider methods directly from drafting logic | Route all calls through the seam's own vocabulary; provider specifics live only in the adapter |
| Sphinx output | Drafting markup that isn't actually Sphinx-publishable / doesn't build | Validate against a real Sphinx build; treat build failure as a drafting bug |
| Source extraction (code/`--help`/specs) | Trusting the model's recall of symbols instead of extracting them | Introspect/parse the real source; feed extracted symbols into grounding |
| DOCPR-2822 (org QA) | Reimplementing QA inside the core | Call it as an optional external extension point; never absorb it |
| Verification sandbox (Workshop) | Running steps in a non-reproducible env | Pin a reproducible environment; capture its fingerprint into provenance |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-grounding/re-extracting whole repo per unit | Slow drafts on large repos | Scope grounding to human-pointed sources (Mode A) | Brownfield repos large enough to need the S1 spike |
| Verification re-runs every step on every draft | Slow iterate loop; users disable it | Cache verification evidence keyed by step + environment fingerprint | When doc sets grow / many actionable steps |
| Stuffing entire source into prompt context | Token bloat, cost, lost-in-middle errors | Human-pointed, unit-scoped context; spike RAG only if proven | Unwieldy brownfield repo (the S1 spike target) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Executing AI-drafted commands in verification without sandboxing | Drafted step runs a destructive/exfiltrating command on the host | Run verification in an isolated, reproducible sandbox (Workshop); never on the author's live machine with broad rights |
| Hallucinated dependency in a "setup" step | Reader installs a non-existent/typosquatted package (package-hallucination supply-chain risk) | Strict dependency allow-list; ground install steps against real, resolvable packages |
| Provenance log captures secrets from command output | Tokens/keys in stdout get stored in the planning directory | Scrub/redact captured run output before persisting evidence |
| Steering/provenance treated as publishable | Internal model/version/effort metadata leaks into shipped docs | Keep provenance internal-only (PROJECT.md: no public AI disclaimer); never emit it into Sphinx output |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Blank-page steering (author intent/audience from scratch) | High friction; tool feels slower than writing | Pre-fill steering from onboarding/style artifacts; human edits, not authors |
| Stacking every safeguard as a blocking modal | Ceremony fatigue → bypass or rubber-stamp | Budget friction; make safeguards assistive with smart defaults |
| Surfacing unverified content identically to verified | Reviewer can't tell what's trustworthy | Visibly mark verification state; show evidence on demand |
| Opaque "the AI decided" output | Reviewer can't trace claims; over-trusts (automation bias) | Show source-of-record per claim so review is fast and grounded |

## "Looks Done But Isn't" Checklist

- [ ] **Verification:** Often missing *captured evidence* — verify a logged run (command, exit code, output, env fingerprint) exists, not just a "verified" flag.
- [ ] **Source-grounding gate:** Often only document-level — verify individual symbols/flags/paths resolve against real sources.
- [ ] **SDK seam:** Often a 1:1 pass-through — verify a (mock) second provider could slot in and grep drafting layer for vendor types.
- [ ] **HITL gate:** Often a confirmation click — verify recorded intent/audience steering exists *before* drafting, with author + timestamp.
- [ ] **F1 schema:** Often A2-only — verify reserved fields for verification evidence, steering layers, reviewer edits, provenance, and a version field.
- [ ] **Sphinx output:** Often unbuilt — verify the draft actually builds in Sphinx.
- [ ] **Commit boundary:** Often crept past — verify the tool stops at a singular local commit (A2: stops before commit logic) with no push/PR/build/publish.
- [ ] **Style adherence:** Often generic — verify drafts carry repo voice/glossary terms, not averaged-LLM phrasing.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| F1 schema churn (designed too narrow) | HIGH | Add version field retroactively; write migration; re-key stored history — avoidable by reserving fields at v0 |
| Leaky SDK seam | HIGH | Re-define seam vocabulary; refactor every drafting-layer call site; move vendor specifics into adapter |
| HITL theatre discovered at audit | MEDIUM | Add recorded steering capture before drafting; backfill is impossible for past drafts (lost evidence) |
| Hallucinated symbols shipped | MEDIUM | Add symbol-resolution gate; re-verify affected docs against source; correct + re-commit |
| Evidence-free tutorial shipped | MEDIUM | Run steps in sandbox, capture evidence, fix failing steps, re-mark verified |
| AI slop shipped | LOW–MEDIUM | Add specific steering + slop-detection pass; regenerate; the cost is reviewer time |
| RAG built prematurely | MEDIUM | Shelve the index; revert to steering-first; salvage only if S1 spike later justifies |
| Scope crept past commit boundary | LOW | Remove the offending capability; re-assert invariant in code review |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Evidence-free actionable content | E (loop); F1 now (evidence fields) | A documented step has an attached, captured run log; `unverified` is the default state |
| 2. Hallucinated APIs/symbols/flags | E (symbol-resolution gate); A2 now (grounding habit) | Every asserted symbol resolves against a real source; drift-guard checks symbols not just docs |
| 3. AI slop / lore-blind content | D (steering layers); B (style artifacts) | Drafts carry repo voice/glossary; slop-detection pass passes; steering recorded |
| 4. SDK lock-in / seam leak | A core (A2 now) | Grep finds no vendor types outside adapter; a mock second provider slots in |
| 5. HITL theatre | F (HITL); F1 now (structural gate) | Recorded intent/audience steering exists before drafting, with author + timestamp |
| 6. UX circumvention | A2 now (loop ergonomics); B (pre-fill) | Time-to-review-ready beats from-scratch baseline (H1) |
| 7. Premature RAG | S1 spike gate; A2 now (works without RAG) | MVP drafts using only human-pointed sources; no index before the spike |
| 8. Provenance/schema churn | F1 now | Schema has version field + reserved sections for E/F/D consumers |
| 9. Scope creep past boundary | A core; reviewed every phase | Tool stops at singular local commit (A2 stops before commit logic); no push/PR/build/publish |

## Sources

- [doctest — Python docs](https://docs.python.org/3/library/doctest.html) — literate testing / executable documentation model (HIGH for the mechanism)
- [sphinx.ext.doctest — Sphinx docs](https://www.sphinx-doc.org/en/master/usage/extensions/doctest.html) and [sphinxcontrib-shtest](https://github.com/tillahoffmann/sphinxcontrib-shtest) — testing CLI/shell commands in Sphinx docs
- [Testing CLI Scripts in Python & Sphinx doctest (bskinn)](https://bskinn.github.io/Testing-CLI-Scripts/) — CLI invocations are harder than REPL snippets
- [AI Hallucinations in Production Code: Risks and Mitigations (DevX)](https://www.devx.com/uncategorized/ai-hallucinations-production-code-risks-mitigations-2026/) and [How to keep AI hallucinations out of your code (InfoWorld)](https://www.infoworld.com/article/3822251/how-to-keep-ai-hallucinations-out-of-your-code.html) — ~42% snippet hallucination, fabricated CLI flags, grounding/static-analysis mitigations
- [Package Hallucination (Snyk)](https://snyk.io/articles/package-hallucinations/) — phantom-package supply-chain risk in setup steps
- [Why Does Enterprise AI Hallucinate? (Contextual AI)](https://contextual.ai/blog/why-does-enterprise-ai-hallucinate) — source grounding / RAG as primary mitigation
- [The LLM Abstraction Layer (ProxAI)](https://www.proxai.co/blog/archive/llm-abstraction-layer), [AI model gateways / vendor lock-in prevention (TrueFoundry)](https://www.truefoundry.com/blog/vendor-lock-in-prevention), [Avoid LLM Vendor Lock-in (Bluebag)](https://www.bluebag.ai/blog/avoid-llm-vendor-lock-in) — never call provider directly; gateway/seam pattern; where leaks happen
- [Human-in-the-Loop: Safety Mechanism or Safety Theater? (McNeilly)](https://markmcneilly.substack.com/p/human-in-the-loop-safety-mechanism), [From Human-in-the-Loop to Human-with-Agency (ISI)](https://www.systemsintegrity.org/from-human-in-the-loop-to-human-with-agency-why-ai-oversight-fails-when-humans-are-present-but-powerless/), [AI's "human in the loop" isn't (Doctorow)](https://doctorow.medium.com/ais-human-in-https-pluralistic-net-2024-10-30-a-neck-in-a-noose-is-also-a-human-in-the-loopthe-loop-isn-t-4b9510251ce5), [Avoiding Rubber-Stamping (MIT Sloan)](https://sloanreview.mit.edu/article/ai-explainability-how-to-avoid-rubber-stamping-recommendations/) — HITL theatre, rubber-stamping, automation bias, accountability laundering
- [How to Stop Content Sounding Like AI Slop (1up.ai)](https://1up.ai/blog/ai-slop-guidelines), [Build a Writing Style Guide for AI (Atom Writer)](https://www.atomwriter.com/blog/ai-writing-style-guide-template/), [Build Your Writing Style Guide: XML Framework (Clark Dever)](https://www.clarkdever.com/blog/build-writing-style-guide-xml-ai) — AI slop patterns; specific-not-vague steering
- PROJECT.md (DOCPR-2845) — scope boundary, A2/F1 first-pulse scope, S1 spike gate, constraints (HIGH, authoritative for this project)

---
*Pitfalls research for: agentic documentation-drafting framework*
*Researched: 2026-06-19*
