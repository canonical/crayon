Load this file at workflow step 4 (Confirm the Diataxis direction).

# Reference-direction intake

The **reference** Diataxis direction is information-oriented: it describes the
machinery accurately and completely so a reader who already knows what they want
can look up the facts. This file holds the reference-shape checklist the intake
confirms before declaring a reference unit.

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
(explanation), it is NOT a reference unit — route to the matching intake instead:

- **tutorial** / **how-to** → load `references/actionable-intake.md`, route to dogen-record.
- **explanation** → load `references/explanation-intake.md`, run the intent walk, route to dogen-write.

## The four directions at a glance

| Direction | Orientation | Draft-stage skill |
|-----------|-------------|-------------------|
| **reference** | information-oriented — look up the facts | dogen-write |
| **tutorial** | learning-oriented — a guided lesson | dogen-record |
| **how-to** | task-oriented — steps to reach a goal | dogen-record |
| **explanation** | understanding-oriented — background and rationale | dogen-write |

A TA-stated direction is honored verbatim; propose one only when the TA supplied
none, and surface a stated-vs-evidence contradiction once for the TA to decide.
