---
name: crayon-onboard
description: Builds or refreshes the repository-level documentation context that grounds crayon-plan — three artefacts (doc-style.md, glossary.md, structure.md) authored from an agent walk over the project's own documentation surfaces (README, the docs tree, supplementary prose) cross-read against the product surface (CLI flags, public API, config, environment variables). The host agent judges voice and audience, terminology, information architecture, Diataxis balance and coverage gaps, hands each artefact's text to the tool with crayon context stage, and records the set with crayon context record, which freezes a digest manifest and makes one commit. Routes a non-standard source (a URL, an export, a harness result) to crayon-fetch. Use when a Technical Author wants to seed or refresh the repository's context before declaring units, or when crayon-plan reports the context missing.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
metadata:
  crayon_contract: 1
  crayon_min_tool: "0.2.0"
---
<objective>
Build or refresh the three repository-level context artefacts that later ground
`crayon-plan`:

- `.crayon/context/doc-style.md` — how the project writes: voice, tone, audience,
  formatting conventions, completeness habits, and where the style drifts.
- `.crayon/context/glossary.md` — the project's own domain terms as its prose uses
  them, with variant spellings and inconsistency flags.
- `.crayon/context/structure.md` — the documentation's information architecture,
  Diataxis balance, structural risks, and the coverage gaps where the product has a
  capability the user docs do not cover, with a short prioritized list of fixes.

The agent supplies the semantic judgment by reading the docs directly. The tool owns
everything deterministic: the fixed set of artefact names, the staging, the digest
manifest, and the commit seam. This skill writes no file itself. It holds no
write-capable tool: every artefact reaches disk through the tool's `context stage` verb,
and the record through its `context record` verb, under the tool's repo-wide lock.
</objective>

<opening>
The first two commands of every session — before anything is read, proposed or
recorded:

```bash
crayon version --json                # {"tool": "<version>", "contract": 1}
crayon context show --json           # what is present, staged, drifted; the routed `next`
```

Stop on exactly two answers from the first call: a `contract` that is not `1`, or a
`tool` older than `min_tool` `0.2.0`. Both numbers are compared as literal strings —
never parsed or rounded as versions. `0.1.9` is older than `0.2.0`: stop, say which
number stopped you, and run nothing else. Any other answer means the pairing is
supported; continue.

The second call is the only source of direction.
**Read `references/routing.md` and act on the row for the emitted `next`.**
`onboard` means at least one of the three artefacts is absent — this skill's own
work; `record` means artefacts are already staged and not yet recorded — record them
before walking again; `plan` means the context is recorded and current — offer a
refresh only if the author asks for one, otherwise route to `/crayon-plan`.
A refusal is one JSON line with `error`, `hint` and `next`: act on the routing row
for its `error` first — that row says what to do now — and route on `next` only
after it. The `hint` is a reminder, never the whole route.

**The ledger is never hand-edited.** This skill touches no unit and no ledger at all;
the context record it makes is `.crayon/context/manifest.json`, which the tool writes
and nothing else ever edits. Nothing in this skill opens any record in an editor.
</opening>

<hard_gate>
Do NOT write `.crayon/context/*.md` or `.crayon/context/manifest.json` yourself, and
do NOT hand an artefact to the author to commit by hand. The only path an artefact has
to disk is:

1. `crayon context stage <name> --body-file -` for each artefact, and
2. `crayon context record …`, which promotes the staged set, freezes the manifest and
   commits.

The tool refuses `bad_target` (exit 2) for any name outside its fixed set, so no
fourth file can be smuggled into `.crayon/context/` through this skill.
</hard_gate>

<quick_start>
1. Run the two-verb opening above and act on the routing row for `next`.
2. Confirm the scope with the author — the docs root (default `docs/` plus the root
   `README` and supplementary prose) and the code root to cross-read for coverage
   gaps (default the repository minus `docs/` and `.crayon/`).
3. Walk the documentation surfaces: read the prose, classify each page by its
   Diataxis direction, and note voice, terminology and structure as you go.
4. Cross-read the product surface — CLI flags, public API symbols, config fields,
   environment variables — grounding each candidate gap by reading the code at its
   origin.
5. Author the three artefacts, loading the matching stance reference for each, and
   hand each one to the tool with `crayon context stage <name> --body-file -`.
6. Record the set with `crayon context record --model … --model-origin … --note "…"`.
7. Report which artefacts landed and the gap count, end on the priorities question,
   and once the author answers, route to `/crayon-plan` with their first pick.
</quick_start>

<pipeline>
crayon-onboard (repo-level, occasional) ─┐
crayon-fetch (declared sources, occasional) ─┴─> .crayon/context/ ─> crayon-plan -> crayon-write -> crayon-review

Unlike plan, write and review, this skill is not per-unit: it produces the shared
context every later declaration consults. Run it once to seed the context, and again
when the docs or the product drift far enough that the artefacts go stale. A re-run
whose artefacts are byte-identical to the record no-ops (`noop_unchanged`, exit 3).
Material that lives outside the repository — a house style guide at a URL, an
exported docs set, a result the harness already holds — is `/crayon-fetch`'s job, not
this skill's.
</pipeline>

<workflow>
<step_1 name="Scope the walk">
Confirm two boundaries with the author before reading anything:

- **docs root** — the prose surfaces to characterize. Default is `docs/` plus the
  root `README` and supplementary prose (`CONTRIBUTING`, `CHANGELOG`, `SECURITY`,
  `ARCHITECTURE`), in the text formats `.md`, `.rst` and `.txt`.
- **code root** — the subtree to cross-read for coverage gaps. Default is the
  repository minus `docs/` and `.crayon/`. Read code only to find product
  capabilities (CLI flags, exported API, config fields, environment variables) that
  the user docs may omit — never to characterize docstring quality.

Propose the defaults; let the author narrow the scope (one docs subtree first, on a
large repository). If the author brings material that is not in this repository —
a URL, an exported directory elsewhere on disk, a result the harness already holds —
stop and route them to `/crayon-fetch`, which declares such sources and records their
provenance; this skill walks the repository it is run in.
</step_1>

<step_2 name="Walk the documentation surfaces">
Read the docs tree page by page. As you read, hold four running observations:

- **Direction** — tutorial, how-to, reference, explanation or landing, judged by what
  the page does for its reader, not by the folder it sits in.
- **Voice** — person, mood, formality, and the formatting habits (admonitions,
  code-example placement, header depth, tables versus prose).
- **Terminology** — the domain terms the prose introduces, and any place the same
  concept is named two different ways.
- **Topology** — the landing pages, the sections under each, and how a new reader
  would navigate.

Ground every observation in a page you actually read. Never characterize a repository
whose docs you have only listed.
</step_2>

<step_3 name="Cross-read the product surface for gaps">
Walk the code root at directory granularity to enumerate user-facing capabilities —
CLI subcommands and flags, exported or public API symbols, config fields, environment
variables. For each capability, check whether any doc page covers it. Apply the
three-check rule — locate, confirm, corroborate — so no gap is asserted without
reading the code at its origin.

A capability the product exposes but the user docs never mention is a coverage gap.
Distinguish three kinds: missing entirely; present only as raw reference with no task
workflow; or mentioned but undiscoverable from the landings and navigation.
</step_3>

<step_4 name="Author each artefact and hand it to the tool">
Compose each artefact in full, then hand it to the tool. Load the matching stance
reference immediately before authoring each — they carry the rubric and the section
shape:

- `doc-style.md` — load `references/style-stance.md`.
- `structure.md` — load `references/structure-stance.md`.
- `glossary.md` — load `references/glossary-stance.md`.

Two rules bind every artefact:

- **Ground each claim.** A style observation quotes a short phrase (under ten words)
  from a page; a gap cites the specific capability by name and where it lives. Never
  assert what you did not read.
- **Tag every coverage gap.** In `structure.md`, each finding that compares a named
  product capability against the docs starts with the literal tag
  `[CODE↔DOCS GAP]`, naming the capability and its origin. This is what lets
  `crayon-plan` trace a proposed unit back to its trigger.

Hand each artefact to the tool on stdin. The tool computes every digest itself; you
never type one:

```bash
printf '%s\n' "$DOC_STYLE" | crayon context stage doc-style.md --body-file - \
  --source README.md --source docs/index.md
printf '%s\n' "$GLOSSARY" | crayon context stage glossary.md --body-file -
printf '%s\n' "$STRUCTURE" | crayon context stage structure.md --body-file -
```

`--source` repeats, once per page or file the artefact was grounded in; it is a
declared locator the manifest records verbatim, so name the pages that carried the
most weight rather than every file you opened. Each verb answers with one line —
what was staged, where, and `Next: record`. Echo those lines as the tool printed
them; never recompose or reword them.
</step_4>

<step_5 name="Record the set">
```bash
crayon context record --model "$MODEL" --model-origin "$MODEL_ORIGIN" \
  --note "<one line: the scope walked and the gap count>"
```

`--model` is a claim about who produced the text, and `--model-origin` says where
that claim came from; omit both when you cannot say (the tool records the honest
default, `unknown`). The verb promotes every staged artefact into `.crayon/context/`,
writes `manifest.json` — one sha256 per artefact, the declared sources, the actor,
the model claim, the HEAD it was recorded against — and makes one commit with
`Crayon-Phase: context-recorded` and no `Crayon-Unit`. Quote the `git: committed
<sha>` line it prints.

On `noop_unchanged` (exit 3) nothing changed since the last record: say so, and act
on the `next` the payload carries. On `bad_target` (exit 2) the refusal names what is
wrong — an artefact name outside the set, an empty body, a stray file in staging —
fix that and re-run; nothing was promoted.
</step_5>

<step_6 name="Report and route">
Present a single summary block, as plain text rather than a code block, ending on
one question about the author's priorities:

```
## crayon-onboard

- Style: .crayon/context/doc-style.md
- Glossary: .crayon/context/glossary.md (<n> terms)
- Structure: .crayon/context/structure.md (<n> coverage gaps)
- Recorded: <the tool's response line, verbatim>

Which three gaps would your readers miss first?
```

That question is for three gaps or more. With one or two, ask
`Which of these would your readers miss first?`; with none, ask
`What would your readers miss most?`. Only their first pick is used.

Ask nothing else in the report, and give it no route line yet: which gaps matter
most is the author's judgment, not something the walk can settle. So the question is
plain text, not options in a question tool, and no gap is marked as recommended,
suggested or a default, whatever a harness's own convention: the order of the gaps
implies nothing. Nothing is recorded from the answer; `crayon context record` has
already run. Once the author answers, the route line names their first pick in their
own words:

```
Next: /crayon-plan — start with <their first pick>
```

Their first pick is the first item in their reply, in the words they used for it,
whatever the walk called that gap. If they name none, the route line is
`Next: /crayon-plan`, with no pick: never pick one for them.

Do not push or build — the tool's commit seam already recorded the transition.
</step_6>
</workflow>

<edge_cases>
**No docs found:** if the docs root and README yield no prose, tell the author there
is nothing to characterize and stop — never fabricate a profile from code alone.

**Large repository:** do not attempt an exhaustive function-by-function code walk.
Map the product surface at directory granularity, or narrow the scope with the
author to one subtree, record it, and refresh other subtrees later; `context record`
keeps every artefact it does not touch.

**A gap you cannot verify:** leave it out. An unlisted capability is honest; an
invented gap misdirects planning.

**A non-standard source:** a style guide at a URL, an exported docs set outside this
repository, a document the harness already holds. Route the author to
`/crayon-fetch`, which declares such sources, retrieves them through the requested
integration, and records their provenance; do not paste external material into a
walk of this repository.

**Non-file SDLC sources (issues, pull requests):** out of scope — crayon never reaches
into a forge. If the harness exposes a repository-history tool and the author wants a
capability discussed there folded in, tag that finding `[SDLC]` with the issue or PR
number as its citation; otherwise omit it.

**Refresh versus first run:** treat each run as a complete snapshot — author all
three artefacts every time. The tool freezes the manifest over the whole published
set; when nothing changed since the last record, it no-ops (exit 3) and discards the
staged copies.

**`drifted` in `context show`:** someone edited a recorded artefact by hand. Nothing
is refused; say so, and let the author choose between keeping the edit (a fresh walk
that reads it and re-records) and restoring the recorded bytes from git.

**`busy` (exit 5) or `git_busy` (exit 5):** another run holds the lock, or a git
process is mid-write. Nothing was written. Wait, then re-run the same command
unchanged.

**A refusal you do not recognise:** it is still one JSON line with `error`, `detail`,
`hint` and `next`. Branch on `error`, not on the exit code (several reasons share
one), and act on the routing row for `next`.
</edge_cases>

<constraints>
<must>
- Open every session with `crayon version --json` then `crayon context show --json`,
  and act on the routing row for `next`.
- Confirm the docs and code scope with the author before walking.
- Ground every observation and gap by reading the prose or code at its origin.
- Hand each artefact to the tool with `crayon context stage <name> --body-file -`,
  and record the set with `crayon context record`, in that order.
- Tag every code-versus-docs coverage gap `[CODE↔DOCS GAP]` (or `[SDLC]` for a
  forge-discussion trigger) with a named citation.
- Echo each verb's own response line verbatim.
- End the report on the priorities question, and route to `/crayon-plan` only after
  the author answers, naming their first pick in their own words, or none.
</must>
<must_not>
- Never write `.crayon/context/*.md` or `manifest.json` yourself, or hand a file to
  the author to commit by hand — this skill holds no write-capable tool and needs
  none.
- Never stage a name outside the tool's fixed set; the tool refuses it anyway.
- Never assert a style trait, term or gap for prose or code you have not read.
- Never invent a coverage gap to look thorough.
- Never fold external material into a walk of this repository — route it to
  `/crayon-fetch`.
- Never declare, draft, review, push or build — those belong to the other skills and
  to the author.
- Never re-derive state or invent a next step; the tool emits `next`.
- Never choose the author's priorities or first unit for them.
</must_not>
</constraints>

<success_criteria>
- [ ] The session opened on `crayon version --json` and `crayon context show --json`.
- [ ] The docs and code scope was confirmed with the author.
- [ ] Every observation and gap was grounded in prose or code actually read.
- [ ] Each artefact reached the tool through `crayon context stage … --body-file -`.
- [ ] `crayon context record` exited 0, or 3 on an unchanged set, and its line was quoted.
- [ ] The term count and gap count were reported, and the report ended on the
      priorities question.
- [ ] The route line to `/crayon-plan` named the author's first pick in their own
      words, or none when they named none.
</success_criteria>
