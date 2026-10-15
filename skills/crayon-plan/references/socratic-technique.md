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
  (`Read`/`Grep`/`Glob`, `git diff`/`git log`, the `.crayon/context/` artifacts)
  **before** asking anything. A question whose answer is on disk wastes the TA's
  turn and teaches them the intake isn't paying attention.
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

## Your view on judgment questions

The mechanical fields already come with evidence-grounded defaults (the family
smart-defaults rule, v1.2). Judgment questions are different — the point is to
draw the TA's own picture out, not to hand them one. So:

- **Open every judgment field open-ended.** The first question about the reader's
  problem or the audience never carries a proposed answer.
- **Give your view only when asked.** When the TA asks "what do you think?",
  state what you saw as evidence — "the siblings under `reference/` are written
  for operators" — and let them choose. Never put it as a marked option, and
  never volunteer it unasked.
- **A stuck or vague TA gets a narrower probe, not a proposal.** Narrow to one
  concrete case, or an either/or in their own words. After two narrowing probes,
  say plainly that the answer is still open, and ask whether they want your view
  on it.
- **Sharpen after they answer** with a narrower question in the TA's terms, not
  a narrowing of your own: "you said operators — wiring the pipeline for the
  first time, or already running it?"
- Ground every view and every narrower probe in something you actually looked
  at (the change, the siblings, `doc-gaps.md`) and say what that something is,
  in one clause.

## Handling scripts

- **Vague answer:** one narrower probe, then a narrower one — one concrete case,
  or an either/or in the TA's words. After those two narrowing probes, say plainly
  that the answer is still open, and ask whether they want your view on it. No
  proposal unless the TA asks for your view.
- **Jump-ahead TA:** they answered three questions at once or dictated the whole
  plan. Bank it all, reflect it back as settled, and ask only what is genuinely
  still open. Re-asking an answered question is the cardinal intake sin. One of
  SKILL.md step 2's two fixed questions — where the reader arrives from, or what
  they do right after — is always open. The leave-out question, what the page can
  leave out, is always open too, asked after the arrival-or-next question, so even a
  brief that answers everything gets those two questions before anything is
  recorded.
- **"Just write it for me":** decline warmly and keep drawing out — drafting is
  crayon-write's job after signoff, and the two minutes of intake are what make
  the draft land right the first time.
- **A patch or diff as input:** the patch usually IS the plan. Read it first,
  confirm the implied reader problem in one question, then offer to skip
  straight to the mechanical fields.

## The glossary as a byproduct

Terminology settles during the dialogue, and catching it there is cheap:

- When the TA's wording conflicts with `.crayon/context/glossary.md`, surface it
  the moment it happens — "you've been saying 'binding'; the glossary calls this
  'attachment' — which should the page use?" — and use the settled term from
  then on.
- When a genuinely new term crystallizes, fold it into the outline — the plan
  body the TA approves — so the drafter inherits it.
- The skill records no note of its own. It holds no write-capable tool, so what
  is recorded reaches disk through the tool: `--notes` on `crayon unit new` /
  `crayon unit edit` carries only the TA's own words given in answer to an open
  question, verbatim, and
  `crayon steer <id> --note '<their words>' --origin plan` carries the TA's
  words given after the plan is signed off. `--origin` defaults to `manual`, so
  the flag is not optional here: the origin is the field `crayon summary` reports
  and the review skill is told to read. `unit.md`'s frontmatter is the fixed
  subset `title` / `intent` / `audience` / `targets` / `sources` / `notes` — any
  other key is refused `unit_invalid`.
- Sparingly: only terms the unit's page actually leans on. The glossary artifact
  itself is maintained outside this loop.
