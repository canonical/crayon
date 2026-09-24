---
name: dogen-plan
description: Guides a Technical Author through declaring one documentation unit via one-question-at-a-time Socratic intake, grounding first in existing docs and dogen context artifacts, drawing out intent and audience before recording anything, then recording the declaration with dogen unit new and the human-in-the-loop gate act with dogen signoff. Routes by declared Diataxis direction — reference/explanation to dogen-write, tutorial/how-to to dogen-write (evidence-walk branch). Also serves advise-only triage asks. Use when a TA is ready to declare and sign off a new documentation unit before drafting, or asks whether a change needs documentation.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
metadata:
  dogen_contract: 1
  dogen_min_tool: "0.2.0"
---
<objective>
Guide the TA through declaring one documentation unit via one-question-at-a-time
Socratic dialogue, then record the result through the tool. Ground yourself in the
repo's prior art before questioning; draw out the judgment fields (intent +
audience) before recording anything; collect the mechanical fields (unit id, title,
source paths, targets) directly. The declaration ends with the gate act that freezes
the exact plan and unblocks drafting.

This skill writes no file itself. It holds no write-capable tool: every byte it
produces reaches disk through a verb, under the tool's repo-wide lock.
</objective>

<opening>
The first two commands of every session — before anything is proposed, written or
recorded:

```bash
dogen version --json                 # {"tool": "<version>", "contract": 1}
dogen show "$UNIT_ID" --json         # the derived state, and the routed `next`
```

Stop on exactly two answers from the first call: a `contract` that is not `1`, or a
`tool` older than `min_tool` `0.2.0`. Both numbers are compared as literal strings —
never parsed or rounded as versions. `0.1.9` is older than `0.2.0`: stop, say which
number stopped you, and run nothing else. Any other answer means the pairing is
supported; continue.

The second call is the only source of direction.
**Read `references/routing.md` and act on the row for the emitted `next`.**
Never re-derive the state, never infer the
next step from the conversation, and never decide direction yourself: the tool
derives state from the record, and the routing table is a rendering of the same
preconditions the tool enforces.
A refusal is one JSON line with `error`, `hint` and `next`: act on the routing row
for its `error` first — that row says what to do now — and route on `next` only
after it. The `hint` is a reminder, never the whole route.

For a brand-new unit there is no id to show yet. Run the version call, take the
intake below, and the first `dogen show` is the one that follows the declaration.

**The ledger is never hand-edited.** `.dogen/units/<id>/ledger.jsonl` is hash-chained:
every line's `prev` is the digest of the previous line's bytes, so editing any line
invalidates every line after it. Nothing in this skill ever opens it in an editor —
not to fix a typo, not to append a note, not to correct a field.
</opening>

<hard_gate>
Do NOT invoke dogen-write, write any documentation, or take any drafting action
until:

1. `dogen unit new <id> …` has recorded the declaration, and
2. `dogen signoff <id>` has exited 0.

This applies to EVERY unit regardless of perceived simplicity. The gate is enforced
by the tool — `dogen draft` refuses `no_signoff` (exit 1) without a current signoff,
and `plan_stale` (exit 1) when `unit.md` moved after the signature. You cannot
bypass it, and you never need to: every refusal names the verb that clears it.
</hard_gate>

<quick_start>
1. Run the two-verb opening above.
2. Confirm the TA wants to declare a NEW unit. If they want to draft or review an
   existing unit, route them to dogen-write or dogen-review. If their ask is an
   assessment ("does this need docs?"), take the triage fork in step 1 instead.
3. Ground yourself before questioning: run `dogen context show --json` and read the
   recorded artefacts in `.dogen/context/` (`doc-style.md`, `glossary.md`,
   `structure.md`, and `code-to-docs-map.md` and `doc-gaps.md` when present); when
   the routed `next` is `onboard`, offer the TA the bootstrap choice ONCE (step 1).
   Then skim the repo's existing docs for conventions, and read whatever change or
   feature the TA points at.
4. Open the Socratic intake with the Why. Ask exactly one question per turn.
5. Draw out the judgment fields first (reader's problem, then audience), then collect
   the mechanical fields directly (unit id, title, source paths, target placement).
6. Confirm the Diataxis direction and route on it (step 4).
7. Take ONE confirmation for the whole ceremony, then record it (step 6) and route.
</quick_start>

<pipeline>
dogen-onboard / dogen-fetch -> .dogen/context/ -> dogen-plan -> dogen-write -> dogen-review

This skill is the declare+signoff stage. The context the two skills before it record
is what it grounds itself in; when that context is missing it offers the TA a choice
rather than inventing one. It consumes the TA's answers and records
them as events; the tool's commit seam owns both transitions. On success it hands off
to dogen-write, which branches internally on the declared direction:
reference/explanation, or tutorial/how-to via the evidence-walk branch.
</pipeline>

<workflow>
<step_1 name="Confirm the declare intent and ground yourself">
Confirm the TA wants to declare a new unit. Before any questioning, ground yourself
in the prior art with the read-only tools:

- Run `dogen context show --json`. Its payload says which of the five context
  artefacts are present, which are recorded, and which have `drifted` since their
  record; its `next` is `onboard` while any of `doc-style.md`, `glossary.md` or
  `structure.md` is absent, and `plan` when the context is there.
- Read the recorded artefacts in `.dogen/context/`: `doc-gaps.md` proposes
  prioritized units; `structure.md` maps the docs topology and tags each
  code-versus-docs gap `[CODE↔DOCS GAP]`; `doc-style.md` and `glossary.md` set voice
  and vocabulary; `code-to-docs-map.md` links code areas to doc pages — grep it
  rather than reading it whole. A `drifted` artefact was edited by hand after its
  record: read it as it is, and mention the drift once.
- Skim the repo's existing documentation for conventions and the nearest
  neighbouring pages to the proposed unit.
- Read any change, feature description, or source files the TA points at.

**Context bootstrap (when `next` is `onboard`).** One or more of the three onboarding
artefacts is missing. Surface it ONCE, with `AskUserQuestion`, offering three answers:

- **I'll add them** — the TA supplies the missing files, by hand or through
  `dogen context stage <name> --body-file F` and `dogen context record`. Pause the
  intake until they are there, then re-run `dogen context show --json` and ground.
- **Run /dogen-onboard first** — STOP and route the TA to `/dogen-onboard`, which walks
  the docs and records the three artefacts through the tool; the declaration starts
  again once it has. Material outside the repository is `/dogen-fetch`'s case instead.
- **Ground this intake dynamically** — load `references/context-bootstrap.md` and
  follow it: crawl the unit's own area of the code and docs IN MEMORY, for this one
  intake, persisting nothing. Nothing is written to `.dogen/context/` and nothing is
  committed; the next session grounds again from scratch, and says so.

Whichever answer, this skill never authors a context artefact itself: `.dogen/context/`
is written by the tool on `dogen context record`, and only the onboarding and fetch
skills hand it artefacts to record. When the artefacts are already present, skip the
ask and ground from them directly.

Do not start the dialogue until you have looked at what they want to document.

**Triage fork (advise-only).** When the TA's ask is an assessment — "does this need
docs?" — do the same grounding, then deliver a **Triage Recommendation** and STOP:
what the change touches; which existing pages are affected; the unit you *would*
declare (id, target, sources, Diataxis type, route) if the TA says go; or "no
documentation change needed" and why. No intake, no ceremony, no signoff — only an
explicit "declare it" starts the Socratic intake.
</step_1>

<step_2 name="Draw out the Why and audience">
Load `references/socratic-technique.md` now for the intake technique.

Begin the Socratic intake with the reader's problem, then the audience — the two
judgment fields. Ask exactly one question per turn, building each on the previous
answer:

**"Looking at what you want to document, what problem does this page solve for its
reader?"**

Then, once the problem is clear, draw out who the page is for (the audience). Keep
questions open-ended, not leading; probe when an answer is vague; do not record
anything yet. When the TA is stuck, offer ONE evidence-grounded recommendation they
can react to.
</step_2>

<step_3 name="Propose the mechanical fields; ask only for what you cannot infer">
**J1 — propose, do not interrogate.** Derive every mechanical field you can from the
request and the repository, present the proposal as a settled default, and ask only
for what the repo cannot answer:

- the **unit id** — `^[a-z0-9][a-z0-9-]{0,63}$`, the per-unit directory name. A TA-
  or brief-supplied id is used verbatim; propose one only when none is supplied.
- a human-readable **title**.
- the **source path(s)** — repo paths where the drafter starts reading. Verify each
  one exists with `Read` / `Glob` before proposing it.
- the page's **home** — the docs-relative target. Derive it from the docs tree: where
  do siblings live, does a toctree reference a page by this name? The extension IS
  the format (`.rst` → reStructuredText, `.md` → MyST). Targets are docs-relative,
  `.md` or `.rst`, and a leading `docs/` is refused.
- the unit's **page set** for a horizontal change: the anchor target plus one extra
  target per additional page.

A field you can derive is a proposal the TA confirms or overrides, not a question.
</step_3>

<step_4 name="Confirm the Diataxis direction and route">
Load `references/reference-intake.md` (reference), `references/actionable-intake.md`
(tutorial/how-to), or `references/explanation-intake.md` (explanation) for the
settled direction.

Settle the unit's Diataxis direction, then route on it:

- **reference** → declare `intent: reference`, route to dogen-write.
- **tutorial** / **how-to** → declare `intent: tutorial` / `intent: how-to`, route
  to dogen-write (evidence-walk branch).
- **explanation** → run the intent walk (Socratic "5 whys" that draws out recorded
  intent), then declare `intent: explanation` and route to dogen-write.

A TA-stated direction is honored verbatim; propose one only when the TA supplied none.
If the intake evidence contradicts a stated type, surface that tension once, in one
line, and let the TA decide.
</step_4>

<step_5 name="Shape a reader-facing outline">
Help the TA shape the unit's outline and acceptance criteria — the body of the plan.
Propose an `## Intent & scope` section and an `## Outline / acceptance` section in
chat, and iterate until the TA approves it. One rule is non-negotiable: **the outline
is phrased in the reader's terms, never in implementation identifiers.** Code entities
appear only as source pointers, never as things the page is "about".

For an actionable direction the outline is a procedure's outcome and acceptance —
the reader's start state, the concrete end state, and the checkpoints — phrased
outcome-framed, and **never a step list**. Enumerating steps is dogen-write's job
(evidence-walk branch).
</step_5>

<step_6 name="One confirmation, then record the declaration and the gate act">
**J1 — batch the whole ceremony behind ONE confirmation.** Read back the settled
plan in a single block — id, title, intent, audience, targets, sources, outline —
and ask once: "record this and sign it off?" Do not confirm the fields one at a time,
and do not ask again between the two verbs below.

**Record the declaration.** Compose the frontmatter fields as flags and pipe the
approved body on stdin. This is the only path `unit.md` has to disk: the skill holds
no write-capable tool, so the plan reaches the filesystem through the tool, under its
repo-wide lock — two plan skills running at once cannot race on the same unit,
because the second one waits for the lock or is refused `busy` (exit 5).

```bash
printf '%s\n' "$APPROVED_BODY" | dogen unit new "$UNIT_ID" \
  --intent "$INTENT" \
  --audience "$AUDIENCE" \
  --title "$TITLE" \
  --target "$TARGET" \
  --also-target "$EXTRA_TARGET" \
  --source "$SOURCE" \
  --notes "$NOTES" \
  --body-file -
```

`--also-target` and `--source` repeat, once per additional page or source; omit
`--notes` when there are none. The tool writes `unit.md` in its own frontmatter
shape, so never compose the frontmatter block yourself — pass the fields as flags
and let the tool render them.

**Record the gate act.**

```bash
dogen signoff "$UNIT_ID"
```

Each verb answers with one line — what changed, where, what remains, and `Next:`.
Echo those lines as the tool printed them; never recompose or reword them. Then run
`dogen show "$UNIT_ID" --json` if you need the state again, and act on the routing
row for the emitted `next`.

Present a single summary block:

```
## dogen-plan: <unit-id>

- Declared: <title> → docs/<target>
- Direction: <declared direction>
- Recorded: <the two response lines, verbatim>
- Progress: signed off

Next: /dogen-write — draft the unit.                    # reference/explanation
Next: /dogen-write — draft the unit (evidence-walk).    # tutorial/how-to
```
</step_6>

<step_7 name="J3 — amend a plan that is already signed">
An amendment is one verb, and it is never a hand edit.

1. **Show the plan diff first.** Read the recorded plan back and present, in chat,
   exactly what changes: field by field for the frontmatter, and the body diff.
2. **Name every target that becomes an orphan.** A target dropped or renamed by the
   amendment stops being a target but keeps its page: the tool reports each orphan
   once as "no longer a target; kept on disk", and it never deletes a page. Say so
   before the TA confirms — a renamed target is a removal plus an addition, and the
   old page stays where it is.
3. **Take one confirmation, then re-sign in the same command:**

```bash
dogen unit edit "$UNIT_ID" --title "$NEW_TITLE" --target "$NEW_TARGET" --re-sign
```

Pass only the flags that change; `--body-file -` replaces the body from stdin.
`--re-sign` records the amendment and the new signature in one commit, so there is no
window where the plan has moved and nothing has signed it. Without `--re-sign` the
next draft is refused `plan_stale` (exit 1), which routes to `re_sign` — the same
verb, one step later.

An amendment after an acceptance is legitimate and expected: the accepted generation
then answers a plan that has moved, so the tool reports `generation_stale` and routes
back to drafting. Say that plainly rather than presenting it as an error.
</step_7>

<step_8 name="J7 — the target is claimed by another unit">
`target_claimed` (exit 1) means another unit that is not retired still lists this
target in its current signoff. The refusal's own JSON line already names the holding
unit and the command that releases it — echo the `detail` and `hint` verbatim rather
than paraphrasing them.

Then tell the TA what the refusal means — the target is still spoken for by that
unit's record — and offer to release it. Retire only on an explicit yes: it is
another unit's record, and retiring it is a recorded act on that unit, not
housekeeping on this one.

```bash
dogen unit retire "$HOLDING_UNIT" --note "<why the TA is releasing this target>"
```

Then retry the refused declaration unchanged. If the TA says no, agree a different
target with them instead.
</step_8>

<step_9 name="J8 — the page already exists (brownfield)">
`target_exists` (exit 1) means a signed target already holds bytes the record has
never seen. Do not draft over it, and do not propose a different target to route
around it. The page is adopted as the basis first, which is the review skill's edits
flow — hand off to dogen-review, which records the existing page with
`dogen edits <id> --note "…"`; the first draft then writes every target with drift
protection on the adopted one.

Absent targets are simply not listed in that adoption. A unit with one existing page
and one new target adopts the existing page only, and the first draft writes both.
</step_9>
</workflow>

<edge_cases>
**TA asks you to write the docs:** politely decline — this skill only declares and
signs off. dogen-write drafts, after signoff.

**Triage ask ("does this need docs?"):** the step 1 triage fork — ground, deliver
the Triage Recommendation, STOP.

**Vague answer:** probe once with a narrower follow-up. If still vague, offer ONE
evidence-grounded recommendation.

**Jump-ahead TA:** bank everything they gave and continue only for what is genuinely
open. Never re-ask what they already answered.

**`unit_exists` (exit 2):** that id is already declared. Show it with
`dogen show <id>` and continue on it, or agree a new id with the TA.

**`already_signed` (exit 3):** the plan is already signed at that hash. Nothing is
wrong — report the existing seq and commit from the payload and act on the `next` it
carries.

**`unit_invalid` (exit 2):** the recorded plan is not the declared shape. The refusal
names the offending line AND the flag that owns that field. Fix it through that flag
with `dogen unit edit`, never by editing around the tool.

**`retired` (exit 1):** the unit is retired and every mutating verb refuses on it. A
retired unit is never reopened — offer a fresh declaration for the same target.

**`busy` (exit 5) or `git_busy` (exit 5):** another run holds the lock, or a git
process is mid-write. Nothing was written. Wait, then re-run the same command
unchanged.

**A refusal you do not recognise:** it is still one JSON line with `error`, `detail`,
`hint` and `next`. Branch on `error`, not on the exit code (several reasons share
one), and act on the routing row for `next`.
</edge_cases>

<constraints>
<must>
- Open every session with `dogen version --json` then `dogen show <id> --json`, and
  act on the routing row for `next`.
- Ground yourself first: `dogen context show --json`, the recorded `.dogen/context/`
  artefacts and the repo's existing docs conventions, before the intake.
- When the context is missing (`next` is `onboard`), offer the TA the bootstrap choice
  once — supply the files, run `/dogen-onboard`, or ground dynamically — and persist
  nothing from a dynamic crawl.
- Ask exactly one question per turn during the Socratic intake.
- Draw out the judgment fields (reader problem, audience) before recording anything.
- Propose every field the repo can answer; ask only for what it cannot.
- Batch the declaration ceremony behind ONE confirmation.
- Ground the target placement in the docs tree (siblings, toctree slots); the
  extension IS the format.
- Keep the outline reader-facing: implementation identifiers are source pointers,
  never coverage items.
- Record the plan with `dogen unit new <id> … --body-file -`, then the gate act with
  `dogen signoff <id>`, in that order — the gate must follow the plan, not precede it.
- Verify each source path exists before proposing it.
- Show the plan diff and name every orphaned target before an amendment, then
  `dogen unit edit <id> … --re-sign`.
- Echo each verb's own response line verbatim.
</must>
<must_not>
- Never override a TA-stated Diataxis direction — propose only when absent.
- Never record agent-invented intent as the TA's own — the recorded note reflects
  only the TA's actual answers.
- Never invoke dogen-write before `dogen signoff` exits 0.
- Never hand-edit the ledger, compose `unit.md` yourself, or write any file — this
  skill holds no write-capable tool and needs none.
- Never author or persist a `.dogen/context/` artefact — the onboarding and fetch skills
  hand them to the tool; a dynamic crawl stays in memory and must not outlast the
  session.
- Never retire another unit without the TA's explicit yes.
- Never draft over an existing page — `target_exists` routes to the edits flow.
- Never draft, review, push, or build — those belong to dogen-write/dogen-review.
- Never re-derive state or invent a next step; the tool emits `next`.
</must_not>
</constraints>

<success_criteria>
- [ ] The session opened on `dogen version --json` and `dogen show <id> --json`.
- [ ] Prior art was consulted first (`dogen context show --json`, the recorded
      `.dogen/context/` artefacts, existing docs).
- [ ] When the context was missing, the TA was offered the bootstrap choice once, and
      any dynamic crawl persisted nothing.
- [ ] The intake ran one question at a time, drawing out intent and audience first.
- [ ] Every derivable field was proposed, not asked.
- [ ] The whole ceremony was confirmed once.
- [ ] `dogen unit new … --body-file -` recorded the plan and `dogen signoff` exited 0.
- [ ] An amendment showed the plan diff, named every orphan, and used `--re-sign`.
- [ ] `target_claimed` offered `dogen unit retire` and retried only after a yes.
- [ ] `target_exists` was handed to the review skill's edits flow, never drafted over.
- [ ] The TA was routed to dogen-write on the row the tool's `next` named.
</success_criteria>
