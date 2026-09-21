---
name: dogen-onboard
description: Builds (or refreshes) the repo-level documentation context that later grounds dogen-plan — three artifacts (doc-style.md, glossary.md, structure.md) authored from an agent walk over the project's own documentation surfaces (README, the docs tree, supplementary prose) cross-read against the product surface (CLI flags, public API, config, env vars). The host agent judges voice/audience, terminology, information architecture, Diataxis balance, and coverage gaps, stages the three files under .dogen/staging/context/, and calls dogen-record-context.sh — which refuses any unrecognized artifact, promotes the staged files into .dogen/context/, freezes a manifest (one SHA-256 per file), and commits. Replaces the external Python docs-scraper tool. Use when a Technical Author wants to seed or refresh the repo's documentation context before declaring units.
allowed-tools: Read, Bash, Glob, Grep, Write, Edit
---

<objective>
Build (or refresh) the three repo-level dogen context artifacts that later ground
`dogen-plan`:

- `.dogen/context/doc-style.md` — how the project writes (voice, tone, audience,
  formatting conventions, completeness habits, and where the style drifts).
- `.dogen/context/glossary.md` — the project's own domain terms as its prose uses
  them, with variant spellings and inconsistency flags.
- `.dogen/context/structure.md` — the documentation's information architecture,
  Diátaxis balance, structural risks, and the coverage gaps where the product has a
  capability the user docs do not cover (with a short prioritized list of fixes).

This replaces the earlier standalone Python "docs-scraper" (collect → chunk → three
LLM passes → write the artifacts). The agent supplies the semantic judgment by reading
the docs directly; `dogen-record-context.sh` owns everything deterministic — the
enumerated-artifact gate, the promotion into `.dogen/context/`, the frozen manifest,
and the commit seam. The only thing traded away versus the external tool is a
reproducible run; the artifacts stay auditable because each finding is grounded in
prose or code the agent actually read.
</objective>

<Iron-Law>
THE SKILL WRITES ONLY STAGING. Author the three artifacts under
`.dogen/staging/context/` and nowhere else. Do NOT write `.dogen/context/*.md`
directly — `dogen-record-context.sh` owns those writes. The recorder refuses
(exit 2) any staged file whose name is not one of `doc-style.md`, `glossary.md`,
`structure.md`, so never stage a fourth file in that directory.
</Iron-Law>

<quick_start>
1. Confirm the scope with the TA — the docs root (default `docs/`, plus the root
   `README` and supplementary prose like `CONTRIBUTING` / `CHANGELOG` / `SECURITY`)
   and the code root to cross-read for coverage gaps (default the repo minus
   `docs/` and `.dogen/`).
2. Walk the documentation surfaces: read the prose, classify each page by its
   Diátaxis direction, and note voice, terminology, and structure as you go.
3. Cross-read the product surface — CLI flags, public API symbols, config fields,
   env vars — grounding each candidate gap by reading the code at its origin.
4. Author the three artifacts into `.dogen/staging/context/`, loading the matching
   stance reference for each (style, structure, glossary).
5. Call `dogen-record-context.sh --staging .dogen/staging/context --model <model>`.
6. Report which artifacts landed and the gap count, and route the TA to dogen-plan.
</quick_start>

<pipeline>
dogen-onboard (occasional, repo-level)  ->  grounds dogen-plan

Unlike plan/write/review, this skill is not per-unit — it produces the shared
context every later unit's planning consults. Run it to seed the context, and
refresh it when the docs or product drift far enough that the artifacts go stale.
Re-running with unchanged artifacts no-ops (the recorder exits 3).
</pipeline>

<workflow>
<step_1 name="Scope the walk">
Confirm two boundaries with the TA before reading anything:

- **docs root** — the prose surfaces to characterize. Default is `docs/` plus the
  root `README` and supplementary prose (`CONTRIBUTING`, `CHANGELOG`, `SECURITY`,
  `ARCHITECTURE`). These are the text formats `.md` / `.rst` / `.txt`.
- **code root** — the subtree to cross-read for coverage gaps. Default is the repo
  minus `docs/` and `.dogen/`. You read code only to find product capabilities
  (CLI flags, exported API, config fields, env vars) that user docs may omit — not
  to characterize docstring quality.

Propose the defaults; let the TA narrow the scope (for example, one docs subtree
first on a large repo).
</step_1>

<step_2 name="Walk the documentation surfaces">
Read the docs tree page by page. As you read, hold four running observations:

- **Direction** — tutorial / how-to / reference / explanation / landing, judged by
  what the page does for its reader, not by the folder it sits in.
- **Voice** — person, mood, formality, and the formatting habits (admonitions,
  code-example placement, header depth, tables vs prose).
- **Terminology** — the domain terms the prose introduces, and any place the same
  concept is named two different ways.
- **Topology** — the landing pages, the sections under each, and how a new reader
  would navigate.

Ground every observation in a page you actually read. Do not characterize a repo
whose docs you have only listed.
</step_2>

<step_3 name="Cross-read the product surface for gaps">
Walk the code root at directory granularity to enumerate user-facing capabilities —
CLI subcommands and flags, exported/public API symbols, config fields, environment
variables. For each capability, check whether any doc page covers it. Reuse the
three-check rule — locate, confirm, corroborate — so no gap is asserted without
reading the code at its origin.

A capability the product exposes but the user docs never mention is a coverage gap.
Distinguish three kinds: missing entirely; present only as raw reference with no
task workflow; or mentioned but undiscoverable from the landings and navigation.
</step_3>

<step_4 name="Author the three artifacts into staging">
Create `.dogen/staging/context/` and write exactly these three files. Load the
matching stance reference immediately before authoring each — they carry the full
rubric and the section shape:

- `doc-style.md` — load `references/style-stance.md`.
- `structure.md` — load `references/structure-stance.md`.
- `glossary.md` — load `references/glossary-stance.md`.

Two rules bind every artifact:

- **Ground each claim.** A style observation quotes a short phrase (under ~10
  words) from a page; a gap cites the specific capability by name and where it
  lives. Do not assert what you did not read.
- **Tag every coverage gap.** In `structure.md`, each finding that compares a named
  product capability against the docs starts with the literal tag
  `[CODE↔DOCS GAP]`, naming the capability and its origin. This is what lets
  dogen-plan trace a proposed unit back to its trigger.
</step_4>

<step_5 name="Record the artifacts via the script">
Call the deterministic recorder:

```bash
dogen-record-context.sh --staging .dogen/staging/context --model "$MODEL"
```

The script:
1. Refuses (exit 2) an unrecognized staged file, an empty staging dir, a missing
   `--model`, an unknown flag, or a staging dir that escapes the repo.
2. No-ops (exit 3) when every staged artifact is byte-identical to the published
   one and the published set drops nothing.
3. Promotes the staged files into `.dogen/context/`, freezes `manifest.md` (one
   SHA-256 per artifact), and commits with `Dogen-Phase: onboard`.

**On exit 2:** fix the offending staged file / flag / scope and re-run.
**On exit 3:** nothing changed — surface this to the TA.
**On exit 0:** quote the `git: committed <sha7>` line.

Use `--force` only to re-record deliberately over an unchanged set.
</step_5>

<step_6 name="Report and route">
Report the recorded context:

```
## dogen-onboard

- Style: .dogen/context/doc-style.md
- Glossary: .dogen/context/glossary.md (<n> terms)
- Structure: .dogen/context/structure.md (<n> coverage gaps)
- Committed: <sha7 from the script's git: committed line>

Next: /dogen-plan — the context now grounds unit declarations.
```

Do not push or build — the script's commit seam already recorded the transition.
</step_6>
</workflow>

<edge_cases>
**No docs found:** if the docs root and README yield no prose, tell the TA there is
nothing to characterize and stop — do not fabricate a profile from code alone.

**Large repo:** do not attempt an exhaustive function-by-function code walk. Map the
product surface at directory granularity, or narrow the scope with the TA to one
subtree and record it, then refresh other subtrees later.

**A gap you cannot verify:** leave it out. An unlisted capability is honest; an
invented gap misdirects planning.

**Non-file SDLC sources (PRs / issues):** out of scope for this skill — dogen never
reaches into a forge. If the harness exposes a repo-history tool and the TA wants a
capability discussed in issues/PRs folded in, tag that finding `[SDLC]` with the
issue/PR number as its citation; otherwise omit it.

**Refresh vs. first run:** treat each run as a complete snapshot — author all three
artifacts every time, first run or refresh. The recorder re-freezes the manifest over
the whole published set; when nothing changed since the last record, it no-ops
(exit 3).
</edge_cases>

<constraints>
<must>
- Confirm the docs/code scope with the TA before walking.
- Ground every observation and gap by reading the prose or code at its origin.
- Write ONLY the three artifacts under `.dogen/staging/context/`.
- Record through `dogen-record-context.sh`, which owns the enumerated-artifact
  gate, the promotion, the manifest, and the commit seam.
- Tag every code-versus-docs coverage gap `[CODE↔DOCS GAP]` (or `[SDLC]` for a
  forge-discussion trigger) with a named citation.
</must>
<must_not>
- Never write `.dogen/context/*.md` or `manifest.md` directly — the script owns
  those writes.
- Never stage a file other than the three recognized artifacts.
- Never assert a style trait, term, or gap for prose or code you have not read.
- Never invent a coverage gap to look thorough.
- Never commit, push, or build — the script's seam owns the commit.
</must_not>
</constraints>

<success_criteria>
- [ ] The docs/code scope was confirmed with the TA.
- [ ] Every observation and gap was grounded in prose or code actually read.
- [ ] Only the three artifacts under `.dogen/staging/context/` were written by the skill.
- [ ] The artifacts were recorded via `dogen-record-context.sh` (exit 0, or an unchanged no-op exit 3), not written directly.
- [ ] The term count and gap count were reported, and the TA was routed to dogen-plan.
</success_criteria>
