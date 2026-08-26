---
name: dogen-plan
description: Guides a Technical Author through declaring one documentation unit via one-question-at-a-time Socratic intake, grounding first in existing docs and dogen context artifacts, drawing out intent and audience before recording anything, then writing unit.md and calling dogen-signoff.sh to persist the declaration and record the HITL gate act (lazy-creates the ledger). Routes by declared Diataxis direction — reference/explanation to dogen-write, tutorial/how-to to dogen-write (evidence-walk branch). Also serves advise-only triage asks. Use when a TA is ready to declare and sign off a new documentation unit before drafting, or asks whether a change needs documentation.
allowed-tools: Read, Bash, Glob, Grep, Write, Edit, AskUserQuestion
---

<objective>
Guide the TA through declaring one documentation unit via one-question-at-a-time
Socratic dialogue, then persist the result by writing `unit.md` and calling the
deterministic scripts. Ground yourself in the repo's prior art before questioning;
draw out the judgment fields (intent + audience) before recording anything; collect
the mechanical fields (unit id, title, source paths) directly. The declaration ends
with `dogen-signoff.sh` — the HITL gate act that freezes the exact plan (a content
hash of `unit.md`) and unblocks drafting.
</objective>

<HARD-GATE>
Do NOT invoke dogen-write, write any documentation, or take any
drafting action until:
1. `unit.md` has been written under `.dogen/units/<id>/unit.md`
2. `dogen-signoff.sh <id>` has been called and exited 0 (it lazy-creates the
   ledger on first call)

This applies to EVERY unit regardless of perceived simplicity. The gate is enforced
inline by `dogen-record-draft.sh` — it will refuse to record any draft without a
valid signoff. You cannot bypass it.
</HARD-GATE>

<quick_start>
1. Confirm the TA wants to declare a NEW unit. If they want to draft or review an
   existing unit, route them to dogen-write or dogen-review. If their ask is an
   assessment ("does this need docs?"), take the triage fork in step 1 instead.
2. Ground yourself before questioning: check `.dogen/context/` for landed artifacts
   (`doc-gaps.md`, `structure.md`, `doc-style.md`, `glossary.md`), skim the repo's
   existing docs for conventions, and read whatever change or feature the TA points at.
3. Open the Socratic intake with the Why. Ask exactly one question per turn.
4. Draw out the judgment fields first (reader's problem, then audience), then collect
   the mechanical fields directly (unit id, title, source paths, target placement).
5. Confirm the Diataxis direction and route on it (step 4).
6. Write `unit.md`, call `dogen-signoff.sh` (lazy-creates ledger), then route.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review

This skill is the declare+signoff stage. It consumes the TA's answers and produces
`unit.md` + `ledger.md` under `.dogen/units/<id>/`; the scripts' commit seam records
both transitions. On success it hands off to dogen-write, which branches internally
on the declared direction: reference/explanation, or tutorial/how-to via the
evidence-walk branch.
</pipeline>

<workflow>
<step_1 name="Confirm the declare intent and ground yourself">
Confirm the TA wants to declare a new unit. Before any questioning, ground yourself
in the prior art with the read-only tools:

- Read any landed context artifacts in `.dogen/context/`: `doc-gaps.md` proposes
  prioritized units; `structure.md` maps the docs topology; `doc-style.md` and
  `glossary.md` set voice and vocabulary; `code-to-docs-map.md` links code areas
  to doc pages — grep it rather than reading it whole.
- Skim the repo's existing documentation for conventions and the nearest
  neighbouring pages to the proposed unit.
- Read any change, feature description, or source files the TA points at.

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

<step_3 name="Collect the mechanical fields">
Collect the mechanical fields directly:

- the **unit id** (stable identifier and per-unit directory name). A TA- or
  brief-supplied id is used verbatim; propose one only when none is supplied.
- a human-readable **title** for the page.
- the **source path(s)** — one or more repo paths where the drafter starts reading.
  Verify each path exists with `Read`/`Glob` before recording it.
- the page's **home** — the docs-relative output path (`sphinx_target` in the
  frontmatter). Derive a proposal from the docs tree: where do siblings live, does
  a toctree reference a page by this name? The extension IS the format (`.rst` →
  reStructuredText, `.md` → MyST). The target is docs-relative — do not prefix
  with `docs/`.
- the unit's **page set** for horizontal changes: the anchor page is `sphinx_target`,
  each additional page goes in `extra_targets`.

Propose every derivable field with a recommended default; the TA confirms or overrides.
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
Help the TA shape the unit's outline and acceptance criteria — the `unit.md` body.
Propose an `## Intent & scope` section and an `## Outline / acceptance` section in
chat, and iterate until the TA approves it. One rule is non-negotiable: **the outline
is phrased in the reader's terms, never in implementation identifiers.** Code entities
appear only as source pointers, never as things the page is "about".

For an actionable direction the outline is a procedure's outcome and acceptance —
the reader's start state, the concrete end state, and the checkpoints — phrased
outcome-framed, and **never a step list**. Enumerating steps is dogen-write's job
(evidence-walk branch).
</step_5>

<step_6 name="Write unit.md, init the ledger, sign off">
After the TA confirms the settled plan, write `unit.md` and call the scripts.

1. **Write** `.dogen/units/<unit-id>/unit.md` with the YAML frontmatter and the
   approved body:

```yaml
---
unit_id: <id>
intent: <reference|tutorial|how-to|explanation>
audience: <audience>
title: <title>
sources:
  - path: <source-1>
  - path: <source-2>
sphinx_target: <docs-relative-path.md|.rst>
extra_targets: []
steering_notes: <synthesized steering note>
---

## Intent & scope

<approved intent-and-scope prose>

## Outline / acceptance

<approved outline and acceptance criteria>
```

2. **Record the HITL gate act** (lazy-creates `ledger.md`, freezes SHA-256 of
   `unit.md`, commits "signoff"):

```bash
dogen-signoff.sh "$UNIT_ID"
```

If the TA wants to amend the plan after signoff, edit `unit.md` with `Edit` and
re-run `dogen-signoff.sh "$UNIT_ID" --force` to re-sign. If the TA wants to append
a steering note, append a row to the `## steering` section of `ledger.md` with `Edit`.

Present a single summary block:

```
## dogen-plan: <unit-id>

- Declared: <title> → docs/<target>
- Direction: <declared direction>
- Committed: <sha7 from dogen-signoff.sh>
- Progress: signed off

Next: /dogen-write — draft the unit.                    # reference/explanation
Next: /dogen-write — draft the unit (evidence-walk).    # tutorial/how-to
```
</step_6>
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

**Unit already exists:** check if `.dogen/units/<id>/ledger.md` exists. If so, offer
to amend via `Edit` on `unit.md` + re-sign, or pick a different id.

**TA wants to change an already-signed-off plan:** edit `unit.md` with `Edit`, then
re-run `dogen-signoff.sh "$UNIT_ID" --force`. Steering notes append freely to the
`## steering` section of `ledger.md` with `Edit` — no re-sign needed.
</edge_cases>

<constraints>
<must>
- Ground yourself first: check `.dogen/context/` artifacts and the repo's existing
  docs conventions before the intake.
- Ask exactly one question per turn during the Socratic intake.
- Draw out the judgment fields (reader problem, audience) before recording anything.
- Ground the `sphinx_target` placement in the docs tree (siblings, toctree slots);
  the extension IS the format.
- Keep the outline reader-facing: implementation identifiers are source pointers,
  never coverage items.
- Write `unit.md` with `Write`, then call `dogen-signoff.sh`
  in that order — the gate must follow the plan, not precede it.
- Verify each source path exists before recording it.
</must>
<must_not>
- Never override a TA-stated Diataxis direction — propose only when absent.
- Never record agent-invented intent as the TA's own — the steering note reflects
  only the TA's actual answers.
- Never invoke dogen-write before `dogen-signoff.sh` exits 0.
- Never draft, review, push, or build — those belong to dogen-write/dogen-review.
</must_not>
</constraints>

<success_criteria>
- [ ] Prior art was consulted first (`.dogen/context/` artifacts + existing docs).
- [ ] The intake ran one question at a time, drawing out intent and audience first.
- [ ] `unit.md` was written with verified sources and a docs-tree-grounded target.
- [ ] `dogen-signoff.sh` was called and exited 0.
- [ ] The TA was routed to dogen-write based on the declared direction.
</success_criteria>
