Load this file at workflow step 4 (Confirm the reference direction).

# Reference-direction intake

dogen drafts one Diataxis direction well this cycle: **reference**. This file holds
the reference-shape checklist the intake confirms and the exact hard-block wording
for the other three directions (D-07).

## What the reference direction is for

Reference documentation is **information-oriented**: it describes the machinery
accurately and completely so a reader who already knows what they want can look up
the facts. It is neutral and austere — it states what is, not how to learn it or how
to accomplish a task.

Good reference-shaped units for dogen:

- a directive / option / field reference (each item, its type, default, and bounds),
- a configuration-key reference,
- an API surface, CLI command, or schema reference,
- an enumerated list of states, error codes, or flags.

Confirm the TA's unit fits this shape before declaring. If the reader's real need is
"teach me" (tutorial), "help me do X" (how-to), or "help me understand why"
(explanation), it is NOT a reference unit — hard-block below.

## The three non-reference directions (hard-block this cycle)

- **tutorial** — learning-oriented, a guided lesson.
- **how-to** — task-oriented, steps to reach a goal.
- **explanation** — understanding-oriented, background and rationale.

Declaring any of these would set up a draft that misleads or fails, because dogen
only drafts the reference direction well right now.

## Hard-block wording

When the TA steers toward a non-reference type, use `AskUserQuestion` with wording of
this shape, then STOP before declaring:

> Right now dogen only drafts the **reference** Diataxis direction well — the neutral,
> information-oriented "look it up" shape. What you're describing reads more like a
> {tutorial | how-to | explanation}, which dogen doesn't draft reliably this cycle.
>
> I can (a) note the intended type so a future cycle can pick it up, and stop here, or
> (b) reframe this as a reference unit if there's a genuine reference surface to
> document. Which would you like?

Do not declare a unit with `--intent tutorial`, `--intent how-to`, or
`--intent explanation`. The only intent this skill passes to `dogen unit new` is
`--intent reference`.
