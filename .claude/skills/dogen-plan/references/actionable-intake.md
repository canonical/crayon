Load this file at workflow step 4 (Confirm the Diataxis direction).

# Actionable-direction intake (tutorial + how-to)

dogen drafts the two **actionable** Diataxis directions — **tutorial** and
**how-to** — by *doing*: the draft is produced from a recorded walk of the
procedure, not extracted from artefacts. This is the single shared intake for
both directions (D-08); it holds the tutorial-vs-how-to distinction the intake
confirms and the plan-stage outline framing, then routes to dogen-record.

## The two actionable directions

- **tutorial** — **learning-oriented**. A guided lesson that takes a newcomer
  from nothing to a first success. The reader is *learning by doing*; the page's
  job is a confidence-building journey, not completeness. Success is measured by
  what the reader can now do, not by how much was covered. Concrete, linear, and
  safe to follow start to finish.
- **how-to** — **task-oriented**. A recipe for a reader who already knows the
  domain and wants to accomplish one specific goal. It assumes competence, states
  the goal up front, and gives the shortest reliable path to it. It omits the
  teaching a tutorial needs and the exhaustiveness a reference carries.

The dividing question is the reader's real need: "teach me from scratch"
(tutorial) versus "I know what I'm doing, help me get *this* done" (how-to). If
the real need is instead "look up the facts" it is **reference** (load
`reference-intake.md`); if it is "help me understand why" it is **explanation**
(load `explanation-intake.md`).

## What makes a good actionable unit for dogen

Good tutorial-shaped units:

- a first-run / getting-started walkthrough that ends in a working result,
- an onboarding lesson that introduces one workflow through a single worked
  example.

Good how-to-shaped units:

- accomplish a named task ("migrate X to Y", "configure Z for W"),
- a focused recipe with a clear start state, a goal, and a verifiable end state.

Both directions **declare via `--intent tutorial` or `--intent how-to`**, and
their draft-stage skill is **dogen-record** — the action-based counterpart to
dogen-write. dogen-record walks the procedure step by step under the evidence
gate and authors the page from what actually ran (D-02: actionable units route to
dogen-record, never dogen-write).

## Plan-stage outline / acceptance framing

At the plan stage the outline is **outcome-framed and reader-facing** — it names
what the reader will be able to *do* and the state they reach, phrased in the
reader's terms:

- name the reader's starting state and the concrete end state (what "done" looks
  like to them),
- name the outcomes and checkpoints the reader cares about — the things they
  should be able to observe or verify along the way,
- keep implementation identifiers (command names, file paths, symbols) as
  *source pointers* only, never as what the page is "about".

**Never write a step list at the plan stage.** Enumerating the procedure's steps
is dogen-record's job — the walk *derives* the steps from evidence, capturing
what actually ran. A plan-stage outline that pre-lists steps pre-empts the walk
and invites a draft written from imagination rather than from a recorded run. The
outline states the procedure's *outcome and acceptance*, not its steps.

This is the single shared file for BOTH actionable directions (D-08). It mirrors
the per-direction lazy-load pattern that the explanation intent-walk (Phase 15,
EXPL-02) reuses at this same load point.
