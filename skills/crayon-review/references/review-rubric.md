Load this file at workflow step 5 (Perform the findings review).

# Findings review rubric

This is the review-mode rubric: a small, generalized findings framework that
grades a unit against **its own declared Diátaxis type**. crayon-write drafts the
**reference** direction grounded in **human-pointed sources**; crayon-write
drafts the two **actionable** types — a **tutorial** and a **how-to** — from a
step walk that provably ran, and this phase routes those drafts into review. The
reference-only checks below are therefore **gated on the unit's declared type**
(read from the `intent` field in `unit.md` front-matter, the same field the rubric
already uses for `format`): they apply to a unit **whose declared type is
reference**, while the
tutorial / how-to conformance criteria apply for **actionable units** — so a
correctly-authored tutorial or how-to is never graded as reference "drift". It is
derived from a prior production documentation-review rig, deliberately stripped of
that rig's specifics (its glossary and term-index machinery, bilingual lockstep
checks, house style-guide grounding, the fixed ten-dimension letter taxonomy,
the SEO/IA/toctree checks — and, above all, the report *file*). crayon reviews a
single unit, runs no build, and presents findings in-conversation only — never
to a file.

## Deterministic pre-pass (before any judgment)

Run every deterministic check first, so judgment is spent only where a machine
cannot decide — anything mechanically decidable belongs in this layer, and the
judgment dimensions never re-derive it. Cheap read-only greps over the drafted
page(s), within Read/Bash/Glob/Grep only (no build — D-13, no writes):

- **Changelog-framing tells:** `previously`, `now supports`, `starting with`,
  `can now`, `new in` — candidate writing-approach findings.
- **Researcher register:** `observed`, `the fixtures show`, `every observed
  use`, `the corpus` — candidate source-fidelity (stance) findings.
- **Self-reference openers:** `This page describes`, `This document`, `The
  intended reader` — candidate clarity findings.

Each hit is **promoted** into the findings as a normal prioritized finding
marked `(pre-pass)` — the marker is unbracketed; the priority tags stay the only
bracketed vocabulary — or **dismissed** with a one-line reason (a "previously"
inside a legitimate migration cross-reference is not changelog framing).
Dismissed candidates are listed separately after the findings and never enter
the findings tally.

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

When the unit carries a step plan, weigh the sections its walk flagged through the quality signals (the `deviated` / `skipped` / `fail` episodes surfaced in the provenance summary) more heavily — a flagged section is where improvisation or repeated failure concentrated, so it is the likeliest place a must-fix hides.

## writing-approach (always on, assessed first among the dimensions)

Does every touched page read as if written fresh to its correct end-state, or
does it carry the sediment of its own history? This dimension is **always on**:
it may never be skipped or marked not assessed (it needs only the draft), it
runs in the scoped re-review as well as the full pass (over the touched
sections), and it is assessed before the four generalized dimensions — scaled to
the surface: a bounded fix gets a quick hunt over the touched text; a fresh page
gets a line-by-line pass. Hunt adversarially — on a large or brand-new page,
assume the defects ARE present and go looking; return `(none)` only after
actively trying to find one and failing.

Four named failure modes (shared, name for name, with crayon-write's end-state
standard in its `references/writing-standards.md`):

- **Exception-note layering** — new behaviour bolted on as an aside ("can now
  also…") instead of rewritten into the sentence that owns it.
- **Changelog framing** — release-note register in reference prose
  ("previously…", "now…", "starting with…"). The page states what is; history
  lives in release notes.
- **Pipeline-artifact narration** — commit-log, test, or algorithm mechanics
  restated as documentation. Tag it here when the defect is register and shape;
  when it is a mechanism claim, it belongs to source-fidelity's
  runtime-mechanics leak.
- **Water** — tautology and restating the obvious ("the `timeout` option
  configures the timeout"), prose that re-narrates an adjacent table.

**Counter-guardrail (anti-manufactured-nit):** every writing-approach finding
must (a) name which failure mode it is AND (b) give a concrete end-state rewrite
of the offending text. A finding that can do neither is a manufactured nit —
drop it (list it with the dismissed pre-pass candidates, with the reason).

**Escalation:** when the stale text a writing-approach finding flags ALSO
misstates current behaviour, record a `[must-fix]` co-finding under
source-fidelity — the approach defect stays here at its own severity; the
factual misstatement is graded there.

**The deletion mirror:** end-state writing cuts both ways. A re-drafted page
that silently *lost* working content the steering never ordered removed is a
completeness finding, graded there — hunt for it on every re-draft.

## The four review dimensions

Default to assessing all four (writing-approach above is always on and cannot
be deselected). Any of the four may be marked **not assessed** with a stated
reason — source-fidelity is `(not assessed — <reason>)`, never guessed, when
the declared sources are unreadable or absent: fabricating source behaviour is
the one unforgivable reviewer move.

**Grounding rule (v1):** source-fidelity and completeness findings are verified
against the sources themselves, not against the draft's internal coherence. Open
the signoff's declared `sources[]` and the generation's `origins[]` — what the
drafter actually read — and check the draft's concrete claims there before flagging
or clearing them. Only `sources[]` carries `{path, commit|null}`; `origins[]` is a
list of plain strings, so it tells you WHAT was read and never which version.

### source-fidelity

Is every concrete claim grounded, does the narrative stay out of the code, and does
it stay out of the writer's own research process? Three failure modes:

- **Ungrounded claims.** Every concrete claim (behaviour, defaults, types, bounds,
  signatures, availability) must be traceable to the signoff's declared `sources[]`
  or to what the drafter actually read (the generation's `origins[]`). Flag claims
  grounded in no recorded read; flag the **declared-vs-read gap** when `origins[]`
  is thinner than `sources[]` (the draft may assert more than was read).
- **Code-dumping.** The narrative must not surface implementation source — bodies,
  private internals, verbatim struct or function source — that violates the
  code-in-narrative boundary. Apply the **same per-block boundary the writer is
  bound to** (see "Code-dump binding" below), not a looser reviewer standard.
- **Researcher register (stance leak).** The prose must state what the product
  accepts, does, and enforces — never narrate the writer's evidence. Flag any
  "observed", "the fixtures show", "every observed use", "the corpus" phrasing:
  the writer's stance contract routes unverifiable facts into the report's
  gaps, not into hedged prose — so hedged prose is a violation, not
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
  inventory to appear here (round 3: a leg punted the seven-module attribute
  inventory to a `:ref:` and self-accepted — an outline that says "per-module
  attribute inventory" is a read-and-materialize contract, `[must-fix]` if the
  page ships only a link).
- **Read-but-not-converted.** Compare the generation's `origins[]`
  against the page: an inventory the writer READ (e.g. every per-module
  reference file) but did not surface is the highest-value completeness flag —
  the grounding existed and the page still omitted it.

### structure-fit

Grade the page against its **declared Diátaxis type** (from the `intent` field in
`unit.md` front-matter), then check format hygiene.

**For a unit whose declared type is reference:** does the page behave as a
Diátaxis **reference** — information-oriented, descriptive, one category per
page, with no tutorial / how-to drift — and is its section ordering consistent
and sensible? This reference-drift check applies **only** to reference units; it
must never fire on a declared tutorial or how-to (imperative, step-sequenced
prose is the correct shape for those types, not drift).

**For an actionable unit (a declared tutorial or how-to):** grade the page
against the conformance shape for its type, imported from
`skills/crayon-write/references/tutorial-stance.md` (tutorial conformance) and
`skills/crayon-write/references/how-to-stance.md` (how-to conformance):

- **Tutorial** — a **single guaranteed-to-work route** from a known starting
  state to one **visible success**, with per-step confirmation of what the
  learner sees and no branching, no options menu, no "it depends" (defer
  alternatives and the *why* to explanation/reference and link out).
- **How-to** — stated starting preconditions, a goal-focused step sequence, and
  forks only at a **genuine decision point** — it stays focused on the goal and
  does not teach concepts from scratch or try to be complete.

Then, for either type, check **format hygiene, judged per the page's own format**
(the unit's target extension — v1.2):

- **MyST (`.md`)**: fences closed, the heading ladder unbroken (no mixed
  setext/ATX), `colon_fence` used correctly, ONE table style per page, and any
  reused rST snippet wrapped in an `{eval-rst}` fence — a bare rST directive in
  a `.md` page renders as literal text.
- **rST (`.rst`)**: underlines at least title-length on one consistent ladder
  matching the siblings, directive bodies indented exactly 3 spaces with the
  required blank lines, no MyST fences (```` ``` ````/`:::`) anywhere — they
  render as literal text.

This is Diátaxis conformance + format well-formedness, **not** a house style
guide (crayon has no STYLE_GUIDE this cycle).

Two mandatory checks inside this dimension:

- **Include/link resolution from the committed location.** Resolve every
  relative `literalinclude` / include / link path from where each page actually
  lives (`docs/<target>` — mind the directory depth), not from where a sibling
  page would resolve it. A path that escapes the repo or points at a file that
  is not there is a `[must-fix]` — this is the build-breaking class of defect
  no review may wave through. Check the placement itself too: if the docs tree
  holds a waiting toctree slot or sibling convention this page's
  location/basename/extension diverges from, flag it (the fix is
  `crayon unit edit <id> --target <corrected path> --re-sign`, then a re-draft at
  the corrected path).
- **Cross-page consistency (multi-file units only).** A unit spanning several
  pages is one change: terminology stays consistent across the set, links
  between the set's pages resolve both ways, and a change applied to one page's
  wording lands on every page the outline says it covers — label each finding
  with its page path and **quote the diverging lines** from every page they
  diverge on (show the offending text verbatim on each page, not just a summary),
  so the inconsistency dimension 0's objective check flags is pinned to concrete
  text rather than described in the abstract.

### clarity

Plain-language correctness (grammar, agreement, typos, run-ons) plus a
**register** expectation **scoped to the declared type**. For a unit **whose
declared type is reference**, the register is impersonal, present-tense,
descriptive — flag marketing voice, second-person tutorial voice, or future
tense in a reference page. For an **actionable unit (a declared tutorial or
how-to)**, **imperative second-person voice is required**, not a defect — do
**not** flag it, and the reference register expectation does not apply. Light
intra-page term consistency (one term per concept) folds in here — no term-index
machinery.

## Verification discipline (before any finding is reported)

Only verified findings reach the report — never intermediate hypotheses. Every
finding carries its `F-N` id, its page path and line, and the verbatim offending
quote. For **absence-based** findings ("not supported", "not in source",
"missing from the page") the bar is higher:

- **At least two search strategies, recorded in the finding** — e.g. the exact
  symbol AND a concept/synonym grep; an entrypoint trace AND a test search. One
  failed grep is one strategy, not an absence.
- **Confirm before grading.** A finding graded on the absence of a hit, or on a
  claim to have enumerated all hits, is confirmed with `Read` or an explicit
  `grep -c` whose count is echoed into the finding, before grading — a zero-hit
  read through a pager or filter is not evidence.
- **Prefer the conservative classification.** When the source is complex,
  "inconclusive — needs a human look at <specific place>" beats "unsupported";
  when the draft is vague-but-not-wrong, "imprecise" beats "incorrect". A
  retracted accusation costs more trust than a hedged one.
- **Cross-check before flagging as missing.** Content living on another page of
  the set is a cross-reference question, not an absence — but an
  outline-mandated inventory punted to a link is still a coverage failure (the
  coverage-vs-outline rule wins).

## Priority mapping

Each finding carries one light priority tag — assigned by these definitions,
never by impression:

| Priority | Trigger |
|----------|---------|
| `[must-fix]` | A claim ungrounded in or contradicting the declared sources; an instruction or path that fails the reader (broken include/link, wrong syntax); an outline/acceptance item unmet and unrecorded (the dimension 0 floor); a code-dump surfacing implementation source (source-fidelity); a category violation that defeats the page as its **declared Diátaxis type** (for a reference unit, tutorial/how-to drift; for an actionable unit, a failure of the tutorial/how-to conformance shape — never reference-only drift); or a writing-approach finding escalated as a source-fidelity co-finding. |
| `[should-fix]` | A material completeness gap; wrong register for a reference; a terminology contradiction; a structural inconsistency that impairs (but does not break) the page; a writing-approach failure mode with no factual misstatement. |
| `[nit]` | Wording, ordering, or optional polish with no reader-facing consequence. |

A candidate matching no row is a `[nit]` at most — or not a finding.

### Collision guard (non-negotiable)

`[must-fix]` / `[should-fix]` / `[nit]` is a **review-findings** vocabulary **only**.
It must never rename, parallel, or collide with the scripts' machine surface — the
exit codes (0 = success, 1 = gate/evidence refusal, 2 = bad input, 3 = no-op/stale)
or the derived progress states (pending → drafted → reviewed, derived from the
ledger). Those stay surfaced **verbatim** for run-status. The two
axes are orthogonal: a priority describes *a finding's urgency*; an exit code or
progress word describes *the script operation's outcome*.

## Findings layout (in-conversation only)

Present the findings grouped by dimension. One line per finding: the `F-N` id,
the priority tag, `(pre-pass)` when the deterministic pre-pass produced it, the
observation quoting the offending draft text with its page and line, then `→`
and a concrete suggested action. Number in presentation order. The ids are for
this conversation only; they do not reach the next drafting session, so a note
that cites one is restated with the author (SKILL.md step 6).
A clean dimension shows `(none)`; a skipped one shows
`(not assessed — <reason>)`. The block is presented in the conversation and is
**never written to a file** — only the reviewer's resulting verdict is recorded,
via `crayon review <id> --verdict <accept|fix|redraft>`, with the reviewer's own
words as `--note "…"`: required for fix and redraft, and present on an accept only
when the reviewer gave words beyond the verdict (a fix/redraft verdict's note lands
in the steering stream automatically, so it is exactly what the next draft reads).

```
## crayon-review — findings: <unit-id>

### writing-approach
- F-1 [should-fix] <failure mode: changelog framing — "<offending text>" (<page>:<line>)>
  → <the concrete end-state rewrite>

### source-fidelity
- F-2 [must-fix] <observation, quoting the offending draft text (<page>:<line>)>
  → <suggested action: what to change, or "re-draft with steering: …">
- F-3 [nit] (pre-pass) <observation> → <action>

### completeness
- F-4 [should-fix] <observation> → <action>

### structure-fit
- (none)

### clarity
- F-5 [nit] <observation> → <action>

Findings: N total — X must-fix, Y should-fix, Z nit.
Dismissed pre-pass candidates: <M, each with its one-line reason — or (none)>

What's your verdict, and is there anything you want on the record with it?
```

**The lean, held until the author answers.** The lean is the tally read one way:
any `[must-fix]` → **fix** (or **redraft** when the must-fixes are pervasive
rather than bounded); `[should-fix]` only → no lean, genuinely the reviewer's call;
clean → **accept**. It is never shown before the reviewer answers the verdict
question, unless they ask what the tally suggests. After they answer, a verdict
that matches the lean, or any verdict on a tally with no lean, is recorded without
comment; a verdict that differs gets the lean with its one-clause reason and one
`Keep <verdict>?`, whose answer is final (SKILL.md step 6). Self-check before
showing it: the lean must agree with the tally line above it (dismissed pre-pass
candidates are not in the tally); if it does not, re-derive it. The verdict is
the reviewer's.

There are exactly TWO next steps: accept, or a recorded fix/redraft verdict that
routes to the draft-stage skill. "Make the edit yourself" is not one of them — an
unrecorded correction steers nothing and is invisible to any future audit.
After the verdict is recorded, route on the unit's declared direction:
- **fix**: `Next: /crayon-write — apply the recorded fix.`
- **redraft**: `Next: /crayon-write — re-draft against the recorded steering.`

## Code-dump binding (keep in sync)

source-fidelity's code-dumping check applies the writer's own boundary. The
per-block heuristic is carried here so the reviewer and the writer apply the
**identical** rule:

> Per block, ask: would the reader themselves type, author, or invoke this exact text? If so, a minimal version may be shown; if instead it is how the machinery is implemented internally, reference it by qualified name and never show it.

The stance contract and the code-in-narrative rubric are stated once, in
crayon-write's SKILL.md (step 3) and its `references/writing-standards.md`; this
copy is the reviewer-side mirror and must match them.
