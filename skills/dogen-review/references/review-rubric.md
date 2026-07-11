Load this file at workflow step 4 (Perform the findings review).

# Findings review rubric

This is the review-mode rubric: a small, generalized findings framework for a
Diátaxis **reference** unit grounded in **human-pointed sources**. It is derived
from ng-review-docs, deliberately stripped of that rig's specifics (glossary /
varindex, EN+RU lockstep, STYLE_GUIDE grounding, the fixed 10-dimension letter
taxonomy, the SEO/IA/toctree checks, the deterministic Sphinx anchor pre-pass, the
`F-NN` ids and `file:line` pointers, and the report *file*). dogen reviews a single
unit, runs no build, and presents findings in-conversation only — never to a file.

## Dimension 0 — the objective check (assessed first)

Before the four dimensions, ask the one question the unit exists to answer: **does
this draft satisfy the unit's reader problem and every `## Outline / acceptance`
item?** This is the objective check — it measures the draft against the job it was
declared to do, not against its own internal polish.

An objective-check failure is **must-fix by definition** — the severity floor. If
the draft does not solve the reader problem it was declared for, or leaves an
outline/acceptance item unmet (and unrecorded as a `gap`), that finding is pinned
to the existing `[must-fix]` priority and may **never** be downgraded to
`[should-fix]` or `[nit]`, however small the surface edit looks. (This is the
round-3 finding-G floor: the exact inconsistency a unit existed to remove, still
present in the draft, is a `[must-fix]` objective-check failure — never a `[nit]`.)
The floor reuses the existing `[must-fix]` tag; it introduces no fourth priority
and no bracketed run-status token, so the collision guard (D-03) below still holds.

For a **multi-target unit**, the objective check includes the `structure-fit`
**Cross-page consistency (multi-file units only)** check below — which quotes the
diverging lines — so a cross-page inconsistency the unit exists to remove cannot
pass as satisfied. The two stay coherent: the cross-page rule lives once, in
structure-fit, and dimension 0 references it (no duplicated or contradictory
cross-page rule).

Dimension 0 is a `review`-mode gate only; the `record` fast path is unchanged.

## The four review dimensions

Default to assessing all four. Any dimension may be marked **not assessed** with a
stated reason (e.g. the declared sources were unreadable).

**Grounding rule (v1):** source-fidelity and completeness findings are verified
against the sources themselves, not against the draft's internal coherence. Open
the declared `sources` and the generation's `context_origins` (their commit stamps
say which version the writer read) and check the draft's concrete claims there
before flagging or clearing them.

### source-fidelity

Is every concrete claim grounded, does the narrative stay out of the code, and does
it stay out of the writer's own research process? Three failure modes:

- **Ungrounded claims.** Every concrete claim (behaviour, defaults, types, bounds,
  signatures, availability) must be traceable to the declared `sources` or to what
  the agent actually read (`context_origins`). Flag claims grounded in no recorded
  read; flag the **declared-vs-read gap** when `context_origins` is thinner than
  `sources` (the draft may assert more than was read).
- **Code-dumping.** The narrative must not surface implementation source — bodies,
  private internals, verbatim struct or function source — that violates the
  code-in-narrative boundary. Apply the **same per-block boundary the writer is
  bound to** (see "Code-dump binding" below), not a looser reviewer standard.
- **Researcher register (stance leak).** The prose must state what the product
  accepts, does, and enforces — never narrate the writer's evidence. Flag any
  "observed", "the fixtures show", "every observed use", "the corpus" phrasing:
  the writer's stance contract (canonical:
  `dogen.core.authoring.STANCE_CONTRACT`) routes unverifiable facts into the
  generation's `gaps`, not into hedged prose — so hedged prose is a violation, not
  honesty.
- **Runtime-mechanics leak.** The stance contract's fourth failure mode: prose
  that narrates how the machinery executes internally — temporary files,
  interpreter invocations, internal process flow — even in flawless declarative
  voice. Implementation is not interface; flag it like a code-dump (the reader
  can rely on the behaviour, never the mechanism).

### completeness

Does the page cover what the declared sources plus the recorded steering
(intent / audience) imply a *reference* for this unit should cover? Flag
entities / fields / behaviours present in the sources and implied by steering that
the page omits. This is the source-coverage facet: "what is absent that the reader
needs."

Two mandatory checks inside this dimension:

- **Coverage-vs-outline.** Walk the plan's `## Outline / acceptance` items one
  by one: each is **materialized on this page** or covered by a recorded `gap`
  with a reason. An outline item that is neither is a `[should-fix]` minimum. A
  **cross-reference to another page is not coverage** when the outline names an
  inventory to appear here (round 3: a leg punted the seven-interface attribute
  inventory to a `:ref:` and self-accepted — an outline that says "per-interface
  attribute inventory" is a read-and-materialize contract, `[must-fix]` if the
  page ships only a link).
- **Read-but-not-converted.** Compare the generation's `context_origins`
  against the page: an inventory the writer READ (e.g. every per-interface
  reference file) but did not surface is the highest-value completeness flag —
  the grounding existed and the page still omitted it.

### structure-fit

Does the page behave as a Diátaxis **reference** — information-oriented,
descriptive, one category per page, with no tutorial / how-to drift — and is its
section ordering consistent and sensible? Plus **format hygiene, judged per the
page's own format** (the unit's target extension — v1.2):

- **MyST (`.md`)**: fences closed, the heading ladder unbroken (no mixed
  setext/ATX), `colon_fence` used correctly, ONE table style per page, and any
  reused rST snippet wrapped in an `{eval-rst}` fence — a bare rST directive in
  a `.md` page renders as literal text.
- **rST (`.rst`)**: underlines at least title-length on one consistent ladder
  matching the siblings, directive bodies indented exactly 3 spaces with the
  required blank lines, no MyST fences (```` ``` ````/`:::`) anywhere — they
  render as literal text.

This is Diátaxis conformance + format well-formedness, **not** a house style
guide (dogen has no STYLE_GUIDE this cycle).

Two mandatory checks inside this dimension:

- **Include/link resolution from the committed location.** Resolve every
  relative `literalinclude` / include / link path from where each page actually
  lives (`docs/<target>` — mind the directory depth), not from where a sibling
  page would resolve it. A path that escapes the repo or points at a file that
  is not there is a `[must-fix]` — this is the build-breaking class of defect
  no review may wave through. Check the placement itself too: if the docs tree
  holds a waiting toctree slot or sibling convention this page's
  location/basename/extension diverges from, flag it (the fix is one
  `dogen unit edit --target <path> --re-sign` call, which moves the draft and
  re-approves the amended plan in the same act).
- **Cross-page consistency (multi-file units only).** A unit spanning several
  pages is one change: terminology stays consistent across the set, links
  between the set's pages resolve both ways, and a change applied to one page's
  wording lands on every page the outline says it covers — label each finding
  with its page path and **quote the diverging lines** from every page they
  diverge on (show the offending text verbatim on each page, not just a summary),
  so the inconsistency dimension 0's objective check flags is pinned to concrete
  text rather than described in the abstract.

### clarity

Plain-language correctness (grammar, agreement, typos, run-ons) plus the reference
**register**: impersonal, present-tense, descriptive. Flag marketing voice,
second-person tutorial voice, or future tense in a reference page. Light intra-page
term consistency (one term per concept) folds in here — no varindex machinery.

## Priority mapping

Each finding carries one light priority tag:

| Priority | Trigger |
|----------|---------|
| `[must-fix]` | A claim ungrounded in or contradicting the declared sources; a code-dump surfacing implementation source (source-fidelity); or a category violation that defeats the page as a reference. |
| `[should-fix]` | A material completeness gap; wrong register for a reference; a structural inconsistency that impairs (but does not break) the page. |
| `[nit]` | Wording, ordering, or optional polish. |

### Collision guard (D-03 — non-negotiable)

`[must-fix]` / `[should-fix]` / `[nit]` is a **review-findings** vocabulary **only**.
It must never rename, parallel, or collide with the CLI machine surface — the
failure reason codes (signoff_required, backend_unavailable, model_rejected,
unit_exists, not_drafted, already_accepted, target_exists, bad_target,
bad_report, target_claimed, model_already_set, handoff_incomplete,
undeclared_target, multi_target_unsupported, schema_unsupported,
provenance_invalid) or the progress states
(pending → sourced → drafted → reviewed). Those stay surfaced **verbatim** from
`--json` for run-status. The two
axes are orthogonal: a priority describes *a finding's urgency*; a reason or
progress word describes *the CLI operation's outcome*. This is the sanctioned D-03
revisit, kept deliberately on a different axis.

## Findings layout (in-conversation only)

Present the findings grouped by dimension. One line per finding: the priority tag
first, the observation quoting the offending draft text, then `→` and a concrete
suggested action. A clean dimension shows `(none)`; a skipped one shows
`(not assessed — <reason>)`. The block is presented in the conversation and is
**never written to a file** — only the reviewer's resulting verdict is recorded,
via `dogen review --verdict --note` (a fix/redraft verdict's note lands in the
steering stream automatically, so a finding phrased as a steering correction is
directly actionable).

```
## dogen-review — findings: <unit-id>

### source-fidelity
- [must-fix] <observation, quoting the offending draft text>
  → <suggested action: what to change, or "re-draft with steering: …">
- [nit] <observation> → <action>

### completeness
- [should-fix] <observation> → <action>

### structure-fit
- (none)

### clarity
- [nit] <observation> → <action>

Findings: N total — X must-fix, Y should-fix, Z nit.
(Priority = review findings, NOT the CLI run-status codes.)

Next: accept (the publishing commit is yours) · record fix/redraft — dogen-write applies the note
```

There are exactly TWO next steps: accept, or a recorded fix/redraft verdict that
routes to dogen-write. "Make the edit yourself" is not one of them — an
unrecorded correction steers nothing and is invisible to any future audit.
After the verdict is recorded, route off the result's `next_id` token as the
**frozen referral line** (the exact strings live in `../../README.md`'s routing
table): `Next: /dogen-write — apply the recorded fix.` after a fix,
`Next: /dogen-write — re-draft against the recorded steering.` after a redraft.
Never parrot the raw CLI `next` line to the TA.

## Code-dump binding (governed mirror — keep in sync)

source-fidelity's code-dumping check applies the writer's own boundary. The
canonical source is `dogen.core.authoring.REFERENCE_CODE_RUBRIC`; its per-block
heuristic is carried here verbatim so the reviewer and the writer apply the
**identical** rule:

> Per block, ask: would the reader themselves type, author, or invoke this exact text? If so, a minimal version may be shown; if instead it is how the machinery is implemented internally, reference it by qualified name and never show it.

This copy is **drift-guarded** (`tests/test_review_modes_keyphrases.py`, the
`-k canonical` tests) against `dogen.core.authoring.RUBRIC_HEURISTIC` — the third
governed mirror alongside the Copilot driver strings and the dogen-write passenger
prose. It must be kept byte-for-byte in sync with the core constant; edit the core
symbol and this copy together, never one alone.
