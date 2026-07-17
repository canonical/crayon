---
name: dogen-plan
description: Guides a Technical Author through declaring one documentation unit via one-question-at-a-time Socratic intake, grounding itself first in the repo's existing docs and any dogen context artifacts, drawing out intent and audience before recording anything, collecting the unit id, title, and source paths directly, then persisting through delegating `dogen unit new` and `dogen signoff` calls; amendments go through `dogen unit edit`, never a clobber. Never writes documentation and never edits the unit files; all persistence delegates to the CLI, whose commit seam records every transition. Accepts only the Diataxis reference direction this cycle. Also serves advise-only triage asks — does this change need docs? — with a grounded Triage Recommendation, declaring nothing until the TA says go. Use when a TA is ready to declare and sign off a new documentation unit before drafting, or asks whether a change needs documentation.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
---

<objective>
Guide the TA through declaring one documentation unit via one-question-at-a-time
Socratic dialogue, then persist the result through the deterministic CLI. Ground
yourself in the repo's prior art before questioning; draw out the judgment fields
(intent + audience) before recording anything; collect the mechanical fields (unit
id, title, source paths) directly. The declaration ends with `dogen signoff` — the
HITL gate act that freezes the exact plan (a content hash of `unit.md`) and unblocks
drafting. This skill holds intent and judgment; the core holds the provable gate and
the commit seam. It never authors documentation and never writes or edits any file
itself — every persisting, side-effecting action is a delegating `Bash` call to
`dogen unit new`, `dogen unit edit`, and `dogen signoff`. `Write` and `Edit` are
excluded from its tool surface so the delegation is enforced at the manifest, not by
discipline (D-05/D-18). See `../README.md` for the shared family contract, glossary,
and status vocabulary.
</objective>

<quick_start>
1. Confirm the target unit and check its current state: the TA wants to declare a
   NEW unit (this skill's declare mode), so verify the id is not already declared —
   an existing id refuses with `unit_exists` (step 6). If they want to draft or
   review an existing unit, route them to dogen-write or dogen-review. To amend an
   already-declared unit's plan, use `dogen unit edit` (step 6) — never `--force`.
   If their ask is an assessment ("does this need docs?", "look at this change and
   tell me"), take the triage fork in step 1 instead: deliver a grounded Triage
   Recommendation and stop — nothing gets declared until they say so.
2. Ground yourself before questioning: check `dogen context ls` for landed B1/B2
   artifacts and read what is there — `doc-gaps.md` (prioritized unit proposals)
   and `structure.md` (topology + gaps) first, then `doc-style.md` and
   `glossary.md`; `code-to-docs-map.md` can be very large, so grep it for the
   relevant code area rather than reading it whole. Skim the target repo's
   existing docs for conventions and the nearest neighbouring pages; read
   whatever change or feature the TA points at.
3. Open the Socratic intake with the Why: "Looking at what you want to document,
   what problem does this page solve for its reader?" Ask exactly one question per
   turn.
4. Draw out — one question at a time — the judgment fields first (the reader's
   problem, then the audience), then collect the mechanical fields directly: the
   unit id, a human-readable title, the source path(s) the drafter starts from,
   and the page's home in the docs tree (`--target` — propose it from the
   existing structure/toctrees; a waiting toctree slot decides directory,
   basename, AND extension — the extension is the unit's format: `.rst` in an
   rst tree, `.md` in a MyST tree). A change that spans several existing pages
   (a horizontal fix, a content rebalance) declares the whole set:
   `--also-target` per additional page. Propose every mechanical field with a
   recommended default; the TA confirms or overrides — never make them type a
   derivable value.
5. Confirm the Diataxis direction is **reference**. If the TA steers toward
   tutorial, how-to, or explanation, hard-block: explain reference is the only type
   dogen drafts well this cycle, offer to note the intent for a future cycle, and
   stop before declaring (D-07). Load `references/reference-intake.md` now.
6. Once intent, audience, unit id, title, and at least one source are known, reflect
   the picture back for confirmation — including a synthesized steering note passed
   via `--notes` — then run the delegating call sequence (workflow step 6):
   `dogen unit new … --notes …`, persist the dialogue-settled outline via
   `dogen unit edit … --body-file -`, and, after the TA confirms the settled plan,
   `dogen signoff …`. Never ask the TA to paste or hand-edit `unit.md` — the CLI
   is the persistence path.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review

This skill is the declare+signoff stage. It consumes the TA's answers and produces
the CLI-persisted unit (`unit.md` + the recorded signoff act) under
`.dogen/units/<id>/`; the CLI's commit seam records both transitions. Routing rules:

- On success it hands off to dogen-write for drafting with the frozen referral
  line (`Next: /dogen-write — draft the unit.`).
- It never drafts, reviews, or builds, and never runs a git state-changing command
  (the CLI's seam owns the commits).
- Persistence is delegated entirely to `dogen unit new` / `dogen unit edit` /
  `dogen signoff`; this skill has no `Write` or `Edit` tool.
</pipeline>

<workflow>
<step_1 name="Confirm the declare intent and ground yourself">
Confirm the TA wants to declare a new unit. Before any questioning, ground yourself
in the prior art with the read-only tools:

- `dogen context ls` — read any landed context artifacts (`.dogen/context/`):
  `doc-gaps.md` proposes prioritized, user-need-shaped units (often the best
  starting point for "what should we document next"); `structure.md` maps the
  docs topology and its gaps; `doc-style.md` and `glossary.md` set voice and
  vocabulary; `code-to-docs-map.md` links code areas to doc pages — it can be
  hundreds of kilobytes, so grep it for the code area at hand instead of
  reading it whole.
- Skim the repo's existing documentation for conventions and the nearest
  neighbouring pages to the proposed unit.
- Read any change, feature description, or source files the TA points at.

Do not start the dialogue until you have looked at what they want to document. If
they actually want to draft or review, stop and route them to dogen-write or
dogen-review.

**Triage fork (advise-only).** When the TA's ask is an assessment or research
rather than a declaration — "does this need docs?", "look at this change and tell
me what it means for the docs" — do the same grounding, then deliver a **Triage
Recommendation** and STOP:

- what the change touches, and whether a reference surface changed;
- which existing pages are affected (from `structure.md` and the code-to-docs
  map, when landed);
- the unit you *would* declare — id, target, sources — if the TA says go;
- or, just as plainly, "no documentation change needed" and why.

No intake, no ceremony, no signoff — the TA decides what happens next, and only
an explicit "declare it" starts the Socratic intake. A trailing "and fix the docs
if needed" inside a triage ask is not that instruction: surface the
recommendation and let them choose.
</step_1>

<step_2 name="Draw out the Why and audience">
Load `references/socratic-technique.md` now. Begin the Socratic intake with the
reader's problem, then the audience — the two judgment fields. Ask exactly one
question per turn, building each on the previous answer — a battery of questions
is bewildering, and later decisions often hang on earlier answers, so walk the
decision tree in dependency order:

**"Looking at what you want to document, what problem does this page solve for its
reader?"**

Then, once the problem is clear, draw out who the page is for (the audience). Keep
questions open-ended, not leading; probe when an answer is vague; do not record
anything yet. Split facts from decisions: if a fact can be found in the
environment (files, git, the context artifacts), look it up rather than asking —
the decisions (reader problem, audience, scope, angle) belong to the TA, so put
each one to them and wait. When the TA is stuck or asks "what do you think?",
offer ONE evidence-grounded recommendation they can react to — reacting is easier
than generating (the technique file covers when and how).
</step_2>

<step_3 name="Collect the mechanical fields">
Collect the mechanical fields directly (these are not Socratic — just ask for them):

- the **unit id** (the stable identifier and per-unit directory name). The id's
  authority runs the other way from the other fields:
  A TA- or brief-supplied unit id is used verbatim; propose an id only when none is supplied.
- a human-readable **title** for the page,
- the **source path(s)** — one or more repo paths where the drafter *starts*
  reading (repeatable). Verify each path exists with `Read`/`Glob` before
  recording it. Sources are starting points: the drafter may navigate beyond them
  and records everything it reads, so point at the best entry points rather than
  trying to enumerate everything. The code-to-docs map (when landed) is the best
  guide to which code areas feed this unit.
- the page's **home** — the docs-relative output path (`--target`). Derive a
  proposal from the grounding you already did: where do this page's siblings
  live (`structure.md`, the existing `docs/` tree), and does a toctree already
  reference a page by this name (grep `docs/**/index.*` for the slot — a
  broken/waiting toctree entry is the strongest placement signal there is)?
  Propose `dir/of/siblings/<basename>.<ext>` and confirm it with the TA. Match
  the **basename** to the waiting slot / sibling naming convention exactly — a
  divergent name (e.g. a `-yaml` suffix the toctree does not use) orphans the
  page — and match the **extension to the siblings**: the extension IS the
  unit's format (`.rst` → reStructuredText, `.md` → MyST; the CLI refuses an
  extensionless target with `bad_target`). The target is **docs-relative** — do
  not prefix it with `docs/` (the store already writes under `docs/`); if a
  stray `docs/` slips in the CLI strips it and prints a `note: target
  normalized …` line, which you relay. State the resulting format in the
  declared summary. Default only when the docs tree gives no signal:
  `<unit_id>.<dominant-ext>` at the docs root (the CLI detects the tree's
  dominant format itself).
- the unit's **page set**, when the change is horizontal. The smart default is
  a single page; but when the reader problem spans several existing pages
  ("the same fix across…", "rebalance content between…"), propose the full set:
  the anchor page stays `--target`, each additional page is `--also-target`.
  The outline then gets a per-page section. A page held by an *in-flight* unit
  refuses with `target_claimed` — surface which unit holds it; but a page whose
  owner has already **sealed** it (its last review was an accept) is claimable,
  and declaring or editing onto it *supersedes* the seal — the CLI records a
  `extends:` body line and a `Dogen-Extends: <owner-id>` trailer rather than refusing.

If the TA has not decided a unit id or title, help them settle one; do not invent
sources they did not confirm.
</step_3>

<step_4 name="Confirm the reference direction">
Load `references/reference-intake.md` now. Confirm the unit's Diataxis direction is
**reference** — the only type dogen drafts well this cycle (D-07). If the TA's intent
is tutorial, how-to, or explanation, HARD-BLOCK: use `AskUserQuestion` to explain
that reference is the only supported direction right now, offer to note the intended
type for a future cycle, and STOP before declaring. Do not declare a non-reference
unit.
</step_4>

<step_5 name="Shape a reader-facing outline">
Help the TA shape the unit's outline and acceptance criteria (the `unit.md` body they
own) **in the dialogue itself**: propose the body text — an `## Intent & scope`
section and an `## Outline / acceptance` section — in chat, and iterate until the TA
approves it. One rule is non-negotiable: **the outline is phrased in the reader's
terms, never in implementation identifiers.** Coverage items name fields, syntax,
constraints, and behaviours the reader cares about; code entities (type names,
function names, file paths) appear only as *source pointers*, never as things the
page is "about" — an outline that says "document `PipelineSpec` and
`validate_manifest`" steers the drafter into leaking implementation names into a
user-facing page.

The dialogue is also where terminology crystallizes. When a term settles — or the
TA's usage conflicts with `.dogen/context/glossary.md` — surface it immediately
("you've been saying 'binding'; the glossary calls this 'attachment' — which
should the page use?") and fold the settled term into the outline and the
synthesized `--notes`. Sparingly: only terms the page actually leans on.

The approved body text is persisted in step 6 via `dogen unit edit --body-file -` —
never ask the TA to paste it into `unit.md` or hand-edit the file as part of this
flow (they *may* edit it on their own initiative later; the plan then shows as
stale until re-signed).
</step_5>

<step_6 name="Reflect back once, then run the declaration ceremony as one batch">
The judgment and mechanical fields were all settled with the TA on screen during
steps 2–5, so the reflect-back drops what they have already seen. Synthesize the
Socratic intake — the reader's problem drawn out in steps 2–3, plus any scope or
angle nuance the TA gave — into ONE concise steering note: a sentence or two in the
TA's own framing, capturing what the draft must do for its reader. Invent no content.
This synthesized note is `$NOTES` below. Reflect back **only** that synthesized note
(the one field they have not already seen verbatim) and get a single confirmation.
The stopping condition is shared understanding: one reflect-back, one
confirmation, then the ceremony — do not re-open settled fields.

After one confirmation, the ceremony runs the three delegating verbs —
`dogen unit new` → `dogen unit edit --body-file -` → `dogen signoff` — back-to-back
via `Bash` (the only persistence in the skill); each verb produces its own transition
commit. Do not pause for a separate confirmation between verbs:

```bash
dogen unit new "$UNIT_ID" \
  --intent reference \
  --audience "$AUDIENCE" \
  --title "$TITLE" \
  --source "$SOURCE_1" [--source "$SOURCE_2" ...] \
  --target "$TARGET" \
  [--also-target "$EXTRA_PAGE" ...] \
  --notes "$NOTES" \
  --json
```

`--target` is the placement settled in step 3 (e.g.
`reference/config/pipeline-definition.rst`) — the store writes the
draft exactly there, creating subdirectories as needed, and the extension
decides the unit's format. `--also-target` (repeatable) declares the extra
pages of a horizontal unit. A later placement correction is one call —
`dogen unit edit "$UNIT_ID" --target <new-path>` moves an existing draft along
with the repoint (add `--re-sign` to re-approve the amended plan in the same
act instead of leaving it stale).

`dogen unit new` scaffolds the editable `unit.md` (sources are commit-stamped by the
CLI) and the seam commits the declaration. Immediately persist the step-5 outline the
TA approved in chat — pipe it to the CLI on stdin; the seam commits the amendment:

```bash
dogen unit edit "$UNIT_ID" --body-file - --json <<'PLAN_BODY'
## Intent & scope

<the approved intent-and-scope prose>

## Outline / acceptance

<the approved outline and acceptance criteria>
PLAN_BODY
```

Field amendments use the same verb's field options (`--title`, `--audience`,
`--add-source`, …; merge semantics — nothing unnamed changes). Never ask the TA to
paste content into `unit.md` themselves.

Then record the gate act — no extra confirmation is needed, the batch already has it:

```bash
dogen signoff "$UNIT_ID" --json
```

The signoff freezes the exact `unit.md` (a content hash) and provably precedes any
draft — so it must come AFTER the outline amendment, not before. Later plan edits are
allowed but surface as a stale plan until re-signed — a deliberate amendment folds
the re-approval into the same act with `dogen unit edit … --re-sign`.

**One summary block closes the ceremony.** When all three verbs land, read their
`--json` output and present a SINGLE block that quotes all three
`git: committed <sha7> — …` lines together (declaration, outline amendment, signoff —
each `--json` object carries the same hash as its `commit`). Do not narrate the three
commits as they happen; batch them into this one audit anchor, then close with the
frozen referral line:

```
## dogen-plan: <unit-id>

- Declared: <title> → docs/<target> [+ each --also-target for a multi-file unit]
- git: committed <sha7> — <declaration>
- git: committed <sha7> — <outline amendment>
- git: committed <sha7> — <signoff>
- Progress: <progress state> (signed off)

Next: /dogen-write — draft the unit.
```

**Mid-batch failure (D-04): stop, show what landed, do not roll back.** If a verb
fails after an earlier one already committed (e.g. `signoff` fails after `unit new` +
`unit edit` landed), STOP the batch. Print exactly the `git: committed <sha7>` lines
already produced, then print the single command to finish — `dogen signoff <id>` (or
the earliest remaining verb) — so the TA resumes from the partial state. Do **not**
roll back: the commits are real work on the append-only, commit-per-transition seam,
and deleting a freshly-committed unit would fight the seam and can itself fail.

On a `unit_exists` reason the unit already exists — offer `dogen unit edit` to amend
it, or a different id; `--force` is a full re-scaffold reserved for genuinely starting
over.
</step_6>
</workflow>

<examples>
During the intake, each turn carries exactly one focused question, optionally
preceded by a one-sentence acknowledgment of the previous answer.

<dialogue_example>
Got it — so the reader is trying to understand exactly which fields the config
accepts and what each one defaults to.

Given that, who is the primary reader here: an operator wiring up the config for the
first time, or a developer extending it?
</dialogue_example>
</examples>

<edge_cases>
**TA asks you to write the docs:** politely decline and redirect — this skill only
declares and signs off; dogen-write drafts, after signoff. Keep drawing out the
plan; do not switch roles mid-intake.

**Triage ask ("does this need docs?"):** the step 1 triage fork — ground, deliver
the Triage Recommendation, STOP. The run ends there unless the TA explicitly says
to declare.

**Vague answer:** probe once with a narrower follow-up. If the answer is still
vague, stop probing and offer ONE evidence-grounded recommendation to react to —
a third open probe reads as an interrogation.

**Jump-ahead TA (answers three questions at once, or dictates the whole plan):**
bank everything they gave — reflect it back as settled fields — and continue the
intake only for what is genuinely still open. Never re-ask what they already
answered; nothing is more tedious than a form that forgets its own fields.

**A patch or diff as input:** the patch usually IS the plan. Read it, confirm the
reader problem it implies in one question, then offer to jump straight to the
mechanical fields.

**TA steers toward a non-reference type:** hard-block per step 4; offer to note the
intent for a future cycle; do not declare.

**Unit already exists (`unit_exists`):** surface the refusal; offer
`dogen unit edit` to amend the existing plan, a different id, or — only for a true
start-over — `--force`. Never clobber silently.

**TA wants to change an already-signed-off plan:** amend via `dogen unit edit`
(field options, or `--body-file -` for the outline) **with `--re-sign`** when the
TA is deliberately approving the amendment — one act, no stale-plan limbo, the
superseded signoff is archived in the provenance history. Without `--re-sign` the
plan shows as stale until `dogen signoff --re-sign`. A hand-edit of `unit.md` on
the TA's own initiative is legitimate too — but never the path you instruct.
Steering notes are different — guidance flows freely via `dogen steer --note` with
no re-sign needed.

**Placement or set correction after drafting:** a reviewer-ordered move is
`dogen unit edit <id> --target <new-path> --re-sign` — the draft moves with the
repoint and the amended plan is re-approved in the same call. Growing or
shrinking a horizontal unit is `--also-target` / `--drop-target` (dropping only
de-scopes; the on-disk page is never touched, and the primary cannot be
dropped).

**No source pointed at:** a reference draft needs at least one starting-point
source. Ask the TA to point at the best entry-point file(s) before declaring.
</edge_cases>

<constraints>
<must>
- Ground yourself first: check `dogen context ls` artifacts and the repo's existing
  docs conventions before the intake.
- Ask exactly one question per turn during the Socratic intake; build each question
  on the previous answer.
- Look up any fact the environment can answer (files, git history,
  `dogen context ls` artifacts) instead of asking the TA; reserve the questions
  for genuine decisions (reader problem, audience, scope, angle).
- Draw out the judgment fields (reader problem, audience) before recording anything;
  collect the mechanical fields (unit id, title, sources, target placement)
  directly.
- Ground the `--target` placement in the docs tree before proposing it: sibling
  pages and existing toctree entries (grep `docs/**/index.*`) decide the
  directory, the exact basename, AND the extension (the unit's format); never
  default to the docs root when a waiting slot exists.
- Propose every derivable mechanical field (title, target, format) with an
  evidence-grounded recommended default (labeled choices); never require the TA
  to type a derivable value. The **unit id** is the exception: a TA-/brief-supplied
  id is used verbatim, proposed only when none is supplied.
- Keep the outline reader-facing: implementation identifiers are source pointers,
  never coverage items (step 5).
- Persist ONLY through the delegating `dogen unit new` / `dogen unit edit` /
  `dogen signoff` calls; the outline body goes through
  `dogen unit edit --body-file -` on stdin. All persistence is the CLI's.
- Run `dogen signoff` only after the TA confirms the settled plan — the act freezes
  the plan hash.
- Restrict `Bash` to read-only inspection (`Read`/`git diff`/`git log`/`grep`/`ls`/
  `dogen context ls`/`dogen unit show`/`dogen status`) plus the delegating `dogen`
  calls; never a command that edits files or git state directly.
- Verify each `--source` path exists before recording it.
</must>
<must_not>
- D-07: Never declare a non-reference Diataxis type (tutorial, how-to, explanation)
  this cycle. Hard-block-and-ask and stop before declaring if the TA steers toward
  one; offer to note the intent for a future cycle.
- Never write or edit documentation text, `unit.md`, or any file — this skill has no
  `Write`/`Edit` tool and delegates all persistence to the CLI (D-05/D-18).
- Never ask the TA to paste content into `unit.md` or hand-edit a dogen artefact as
  part of the flow — outline persistence is `dogen unit edit --body-file -`.
- Never use `dogen unit new --force` as an amendment path — amendments are
  `dogen unit edit`; `--force` is an explicit full re-scaffold the TA must ask for.
- Never invent an intent, audience, title, or source the TA did not provide.
- Never convert an assessment ask into a declaration. When the TA asks whether
  something needs docs, deliver a grounded Triage Recommendation and STOP — no
  intake, no ceremony, no signoff; the TA decides, and only an explicit "declare
  it" starts the intake. A trailing "and fix the docs if needed" in a triage ask
  is not that instruction.
- Never draft, review, commit, stage, push, or build — the CLI's commit seam owns
  the transition commits.
</must_not>
</constraints>

<output_specification>
The recorded artifact is the CLI-persisted unit — the editable `unit.md` and the
recorded signoff act under `.dogen/units/<id>/`, written by the store and committed
by the seam (this skill writes no file). After the batched declaration ceremony
(step 6) lands its three transition commits, report inline — ONE summary block
quoting all three `git: committed <sha7>` lines from the `--json` output, never
narrated per-verb:

```
## dogen-plan: <unit-id>

- Declared: <title> → docs/<target> [+ each --also-target for a multi-file unit]
- Sources: <declared source path(s)>
- Direction: reference
- git: committed <sha7> — <declaration>
- git: committed <sha7> — <outline amendment>
- git: committed <sha7> — <signoff>
- Progress: <progress state> (signed off)

Next: /dogen-write — draft the unit.
```

The `git: committed <sha7>` lines are quoted verbatim from the CLI (never
fabricated), and `Next: /dogen-write — draft the unit.` is the frozen referral for
`next_id = draft` (first draft, freshly signed off) from `../README.md`'s routing
table — reused verbatim, never re-worded. On a mid-batch failure (D-04) the block
degrades to exactly the `git: committed` lines that landed plus the single
`dogen signoff <id>` resume command — no rollback.
</output_specification>

<success_criteria>
- [ ] Prior art was consulted first (`dogen context ls` artifacts + existing docs
      conventions) and informed the proposed unit shape and sources.
- [ ] The intake ran one question at a time, drawing out intent and audience before
      recording anything.
- [ ] The unit id, title, and at least one starting-point source were collected and
      each source path verified to exist.
- [ ] The page's `--target` placement was proposed from the docs tree's own
      structure (siblings + toctree slots), its basename AND extension match
      the slot's convention (the format was stated in the summary), and the TA
      confirmed it; a horizontal change set was declared via `--also-target`.
- [ ] Non-reference Diataxis intents were hard-blocked before any declaration (D-07).
- [ ] The outline/acceptance framing is reader-facing; implementation identifiers
      appear only as source pointers.
- [ ] The unit was persisted ONLY via `dogen unit new` (with the synthesized
      `--notes`), the approved outline via `dogen unit edit --body-file -`,
      amendments via `dogen unit edit`, and the gate act via `dogen signoff` after
      the TA confirmed the settled plan; no file was written or edited by the
      skill, and the TA was never asked to hand-edit one.
- [ ] A triage-shaped ask ended at the Triage Recommendation with nothing
      declared; only an explicit "declare it" started the intake.
- [ ] On success the TA was routed to dogen-write.
</success_criteria>

<self_healing>
After completing a run, or after any error that required a workaround, check whether
the issue came from a gap or inaccuracy in this skill's instructions, references, or
workflow steps.

What qualifies for a skill update:

- Tooling issues (CLI syntax changes, path changes, deprecated commands)
- Structural problems (missing files, wrong folder layout, dangling references)
- Missing edge cases that caused failures
- Incorrect assumptions about the environment or dependencies

Off-limits for self-edits: the skill's objective, the workflow step sequence, and the
success criteria. Propose changes to those to the user as ideas, never as self-edits.

How to update:

1. Report to the user: (a) the gap detected, (b) which skill file needs the change,
   (c) the proposed change, quoted in full.
2. Wait for explicit confirmation.
3. Apply the change directly to the skill file with Edit (or Write for new reference
   files).
4. Preserve the shared skill conventions: section order, this self_healing block, and
   the <NAME> placeholder style.
</self_healing>
