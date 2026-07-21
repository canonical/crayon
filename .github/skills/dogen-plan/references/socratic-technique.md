Load this file at workflow step 2 (Draw out the Why and audience).

# Socratic intake technique

How the intake dialogue is run so it feels like a sharp colleague thinking along —
never a form, never an interrogation. The SKILL.md keeps the decision logic; this
file holds the technique.

## Facts vs decisions

Every open item in the intake is one of two kinds, and they are handled
differently:

- **Facts** live in the environment: what a change touches, where sibling pages
  sit, what a toctree already references, what the glossary calls a concept, what
  a source file actually defines. Look these up with the read-only tools
  (`Read`/`Grep`/`Glob`, `git diff`/`git log`, `dogen context ls`) **before**
  asking anything. A question whose answer is on disk wastes the TA's turn and
  teaches them the intake isn't paying attention.
- **Decisions** belong to the TA: the reader's problem, the audience, the scope,
  the angle. These cannot be grepped. Put each one to the TA — one at a time —
  and wait for the answer.

The test for "is this worth a question?": if you would recognize the answer as
right or wrong by looking somewhere, it is a fact — go look.

## Walking the decision tree

Decisions depend on each other: the reader's problem shapes who the audience is;
the audience shapes the scope; the scope shapes the angle and the outline. Ask in
dependency order and one at a time — a battery of questions is bewildering, and
an answer to a later question often changes when an earlier one lands
differently. Each turn carries exactly one focused question, optionally preceded
by a one-sentence acknowledgment of the previous answer (the SKILL.md's dialogue
example shows the shape).

## Recommendations on judgment questions

The mechanical fields already come with evidence-grounded defaults (the family
smart-defaults rule, v1.2). Judgment questions are different — the point is to
draw the TA's own picture out, not to hand them one. So:

- **Open every judgment field open-ended.** The first question about the reader's
  problem or the audience never carries a proposed answer.
- **Recommend when it helps, not before:** offer ONE evidence-grounded
  recommendation when the TA is stuck, asks "what do you think?", or gave a vague
  answer that one narrower probe did not sharpen. Reacting to a concrete
  proposal is easier than generating from nothing.
- **Sharpen after they answer.** Reflecting a first answer back with an
  evidence-grounded narrowing is not leading — it is the fastest path to shared
  understanding: "you said operators — from the config surface this page covers,
  I'd narrow that to operators wiring the pipeline for the first time. Does that
  match?"
- Ground every recommendation in something you actually looked at (the change,
  the siblings, `doc-gaps.md`) and say what that something is, in one clause.

## Handling scripts

- **Vague answer:** one narrower probe. Still vague → one recommendation to react
  to. Never a third open probe.
- **Jump-ahead TA:** they answered three questions at once or dictated the whole
  plan. Bank it all, reflect it back as settled, and ask only what is genuinely
  still open. Re-asking an answered question is the cardinal intake sin.
- **"Just write it for me":** decline warmly and keep drawing out — drafting is
  dogen-write's job after signoff, and the two minutes of intake are what make
  the draft land right the first time.
- **A patch or diff as input:** the patch usually IS the plan. Read it first,
  confirm the implied reader problem in one question, then offer to skip
  straight to the mechanical fields.

## The glossary as a byproduct

Terminology settles during the dialogue, and catching it there is cheap:

- When the TA's wording conflicts with `.dogen/context/glossary.md`, surface it
  the moment it happens — "you've been saying 'binding'; the glossary calls this
  'attachment' — which should the page use?" — and use the settled term from
  then on.
- When a genuinely new term crystallizes, fold it into the outline and the
  synthesized `--notes` so the drafter inherits it (this skill writes no file;
  the notes are the carrier).
- Sparingly: only terms the unit's page actually leans on. The glossary artifact
  itself is maintained outside this loop.
