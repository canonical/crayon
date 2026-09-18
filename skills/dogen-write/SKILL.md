---
name: dogen-write
description: Drafts a review-ready, Sphinx-publishable page (MyST or rST — the target extension decides) for a declared and signed-off documentation unit, branching on the unit's declared Diátaxis intent — reference and explanation are authored straight from the declared sources; tutorial and how-to are authored from an evidence-gated step walk (each step's output captured to a file and recorded with dogen step, which computes every digest itself) and curated excerpts of what actually ran. Stages the page under .dogen/staging/ and records it with dogen draft, which enforces the human-in-the-loop gate and — for actionable units — refuses until every step is resolved. Carries Write for staging files only. Use when a TA is ready to draft a signed-off unit.
allowed-tools: Read, Bash, Glob, Grep, Write, Edit
metadata:
  dogen_contract: 1
  dogen_min_tool: "0.2.0"
---
<objective>
Draft a review-ready, Sphinx-publishable page for a unit that has already been
declared and signed off. The host agent (the one the TA is talking to) authors the
page itself — starting from the unit's declared sources and navigating the repo
freely — stages it under `.dogen/staging/<id>/draft/`, then records it through the
tool, which enforces the human-in-the-loop gate, writes the record before it places
any page, and — for an actionable unit — refuses while any step is unresolved.

The skill branches on the unit's declared Diátaxis `intent`:

- **reference** and **explanation** are authored straight from the declared
  sources (explanation additionally from the recorded steering).
- **tutorial** and **how-to** are authored from an evidence-gated step walk: the
  agent proposes one annotated step plan, walks it silent-until-signal capturing the
  command's own output to a file, hands that file to the tool, then authors the page
  from curated excerpts of what actually ran.

The unit's format is decided by its target extension: `.md` → MyST, `.rst` →
reStructuredText. Author in that markup, matching the page's siblings.
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
never parsed, ordered or rounded as versions. Any other answer means the pairing is
supported; continue.

The second call is the only source of direction.
**Read `references/routing.md` and act on the row for the emitted `next`.**
Never re-derive the state, never infer the next step from the conversation, and never
decide direction yourself: the tool derives state from the record, and the routing
table is a rendering of the same preconditions the tool enforces. A refusal carries
its own `next` in the JSON line — route on that the same way.

**The ledger is never hand-edited.** `.dogen/units/<id>/ledger.jsonl` is hash-chained:
every line's `prev` is the digest of the previous line's bytes, so editing any line
invalidates every line after it. Nothing in this skill ever opens it in an editor —
not to fix a typo, not to append a note, not to correct a field.
</opening>

<iron_law>
NO PAGE REACHES `docs/` EXCEPT THROUGH `dogen draft`. This skill writes only under
`.dogen/staging/<id>/draft/` and `.dogen/staging/<id>/scratch/`. Every ledger
mutation and every page placement goes through a verb, under the tool's repo-wide
lock — which is also why two write skills cannot interleave two transitions: the
second one waits, or is refused `busy` (exit 5).

The gate is the tool's, not this skill's: `dogen draft` refuses `no_signoff` or
`plan_stale` (exit 1) without a current signature, and it appends the record and
`fsync`s it *before* it places a single file.
</iron_law>

<iron_law>
NO ACTIONABLE DRAFT WITHOUT RESOLVED STEPS. For a tutorial or how-to the tool
refuses `steps_unresolved` or `steps_missing` (exit 4) while any step is unresolved.
Never skip the walk for an actionable unit, and never present a `resolved` step as
one that was executed or verified — a step also resolves as `skipped` with a reason,
and the tool's own tally line is the only honest report of which is which.
</iron_law>

<quick_start>
1. Run the two-verb opening above and act on the routing row for `next`.
2. Branch on `intent` from the shown plan. **Author-straight** (reference /
   explanation): ground from the declared sources and author directly.
   **Evidence-walk** (tutorial / how-to): propose one annotated step plan, record it
   with `dogen plan-steps`, walk it silent-until-signal, and record each step's
   evidence with `dogen step` before authoring.
3. Author the page in the unit's format (MyST for `.md`, rST for `.rst`), loading
   the direction register for the declared intent.
4. Stage the draft under `.dogen/staging/<id>/draft/<target>`.
5. Record it with `dogen draft <id> <staging file|dir>`.
6. Echo the response line verbatim and route on the `next` it carries.
</quick_start>

<pipeline>
dogen-plan -> dogen-write -> dogen-review

This skill is the sole drafting stage. It consumes a declared and signed-off unit and
produces a recorded generation. It branches on the unit's declared `intent`:
reference and explanation author straight from sources; tutorial and how-to first
walk an evidence-gated step plan. On success it hands off to dogen-review.
</pipeline>

<workflow>
<step_1 name="Read the unit state from the tool">
The opening already answered this: `dogen show <id> --json` reports the plan, the
per-path page status (`current` / `drifted` / `missing`), every recorded request
since the last generation with its disposition, the step tally, and `next`. Read it;
do not re-derive any of it from the files.

Three routed answers stop the drafting branch before it starts:

- **`record_edits`** — a basis page on disk no longer holds the recorded bytes
  (`page_drift`), or a signed target already holds bytes the record has never seen
  (`target_exists`). Either way this skill does not write over the page: hand off to
  dogen-review's edits flow, which adopts the bytes with `dogen edits <id> --note "…"`.
  Drafting over an unadopted page is how an author's work disappears.
- **`sign_off` / `re_sign`** — route back to dogen-plan.
- **`steer`** — a signed target is missing after a seal. The restoration request is
  recorded first; see the unsteered STOP below.

Then branch on the declared intent:

- reference   → steps 2-6 (ground from sources; author the reference register; record)
- explanation → steps 2-6 (ground from sources + the recorded requests; author the
  explanation register; record)
- tutorial    → step 1a (propose a step plan, walk it under the evidence gate) before
  steps 2-6, authoring in the tutorial register
- how-to      → step 1a, before steps 2-6, authoring in the how-to register
</step_1>

<step_1u name="The unsteered STOP">
A second generation with nothing recorded between it and the last one is refused
`unsteered` (exit 1). **This is a STOP, not a retry.** Do not re-run the draft, do
not compose a reason to get past the gate, and do not paraphrase the conversation
into a note. Stop, ask the author what they want changed, and record their answer in
their own words:

```bash
dogen steer "$UNIT_ID" --note "<the author's own words>"
```

Then draft again. **A restoration is not an exception to this.** When a page is
missing and the author wants it back, that request is recorded through `dogen steer`
first — the same verb, the same words, no shortcut — and the next draft restores the
page under the ordinary gates. An absent page never blocks drafting, and it never
waives the steering gate either.

`--unsteered-reason` exists for the case where the author has genuinely authorised a
regeneration with nothing to change, and it records that override on the generation
itself. Reach for it only when the author has said so; it is a record, not a bypass.
</step_1u>

<step_1a name="Walk the actionable unit (tutorial / how-to only)">
Load `references/walk-protocol.md` now for the evidence contract, capture mechanics,
consent, workspace, and resume detail.

**Resume:** the step tally in `dogen show` names every unresolved step. Offer resume
as the default: show the tally as the tool printed it, trust every resolved step, and
continue at the first unresolved one. The workspace under
`.dogen/staging/<id>/scratch/` persists across sessions.

**Investigate and propose ONE annotated plan.** Read the unit's declared sources and
navigate the repo freely to understand what the tutorial or how-to must walk. Then
propose **ONE annotated step plan**, presenting numbered steps conversationally. For
each step surface, inline:

- its **execution mode** — `agent` (this skill runs it, the default) or `ta` (the
  author runs it);
- a **destructive/stateful marker** when the step's command would mutate real state;
- key **assumptions** and **invariants**.

The TA edits the plan conversationally — add, drop, reorder, re-word — until
satisfied. Then take **one confirmation** and record the whole plan:

```bash
dogen plan-steps "$UNIT_ID" --steps-file -
```

The plan is a JSON array on stdin, one object per step:

```json
[
  {"id": "install", "text": "Install the CLI", "mode": "agent", "stateful": false},
  {"id": "login", "text": "Log in to the service", "mode": "ta", "stateful": true}
]
```

Those four keys are the whole contract. **The skill never supplies a text hash** —
the tool computes each step's hash from the text it was given, and that computed
hash is what makes stale evidence detectable later. A hash this skill typed would be
a claim the record cannot corroborate.

**Re-planning.** A new plan with no reuse leaves every step unresolved again. To
carry a resolved prefix forward, the tool needs both flags, and the note is not
optional — the contract requires a reason whenever evidence carries forward:

```bash
dogen plan-steps "$UNIT_ID" --steps-file - --keep-evidence --note "<why the plan changed>"
```

Ask the author before passing `--keep-evidence`. Reuse asserts that a prefix which
has not been re-run still holds; it carries forward only along consecutive reusing
plans and only for steps whose prefix is identical in text, mode and statefulness.
That is the author's call to make, not a default to take silently.

**Walk each step (silent-until-signal).** Load `references/episode-taxonomy.md` now
for the improvisation-vs-frustration taxonomy. Walk the plan one step at a time with
a **silent-until-signal** cadence: emit one status line per step. Consult the TA only
at:

- a **genuine fork** — missing information, or an informed choice with doc-visible
  consequences;
- a **destructive/stateful permission gate** — just-in-time, right before a marked
  step runs;
- a **failed step**.

**Capture the command's output (D-15).** One redirection, one status, no digest:

```bash
WS=".dogen/staging/$UNIT_ID/scratch"
mkdir -p "$WS/evidence"
OUT="$WS/evidence/$STEP_ID.out"
( cd "$WS" && <the step's command> ) > "$OUT" 2>&1; echo "exit:$?"
```

Both streams are redirected into one file, so nothing is lost and nothing is
interleaved by a pager. There is no pipe, so `$?` is the command's own status, not
some other process's. **This skill computes no digest of any kind.** The tool copies
the output bytes itself, hashes its own copy, and refuses a digest that arrives in
the evidence file — so typing one is not a shortcut, it is a refusal.

Then write the evidence file into the same workspace with `Write`, carrying exactly
the contract's key set:

```json
{
  "verdict": "pass",
  "exit_code": 0,
  "mode": "agent",
  "command": "cd .dogen/staging/<id>/scratch && <the step's command>",
  "reason": "<required for skipped and deviated, for a pass with a non-zero exit, and for a fail with exit 0>"
}
```

Omit `reason` when the contract does not require it. Then hand both files to the
tool:

```bash
dogen step "$UNIT_ID" "$STEP_ID" \
  --steps-seq "$STEPS_SEQ" \
  --evidence-file "$WS/evidence/$STEP_ID.json" \
  --output-file "$OUT"
```

`--steps-seq` is the seq of the step plan this evidence answers; the response line of
`dogen plan-steps` carries it. The tool reads the output file, keeps its own digest,
commits a control-character-stripped excerpt within the contract's size cap, and
records the step.

**Re-running a step is safe.** An identical call — same plan seq, same step, same
verdict, exit code, output and reason — is recognised as `already_recorded` (exit 3)
and nothing is appended twice. An interrupted walk can simply be repeated from the
last step whose response you actually read.

**Refusals to expect:**

- **`evidence_incomplete` (exit 4)** — a required field is missing, or a `pass`,
  `fail` or `deviated` step arrived without `--output-file`. Re-capture; never
  fabricate a field to satisfy the shape.
- **`evidence_mismatch` (exit 4)** — the evidence JSON's `mode` is not the `mode`
  the plan declares for this step; the refusal names both. Record the step in the
  declared mode, or re-plan the step if the mode itself was wrong. Re-running the
  command and re-capturing its output cannot clear this: `mode` is a field of the
  evidence, not of the run.
- **`evidence_stale` (exit 4)** — the plan was re-planned after this capture. Re-run
  the command against the current `--steps-seq`.
- **`step_unknown` (exit 2)** — the step id is not in that plan. Read the plan back.
- **`not_actionable` (exit 2)** — the unit's signed intent is neither tutorial nor
  how-to, so neither `plan-steps` nor `step` may record against it. STOP walking; a
  reference or explanation page is drafted straight from its declared sources. Re-signing
  the intent is the author's decision, never the skill's.

**Improvisation:** when the planned step did not say *how* and you had to work it
out, record the step as a `deviated` verdict with exit 0 and a `reason`. It still
resolves, so the walk proceeds, and the reason rides the record.

A `fail` never resolves a step. That is the point: the tool's draft gate is what
refuses over it, so a failing step cannot be quietly written up as if it had worked.
</step_1a>

<step_2 name="Ground the draft">
Start from the unit's declared sources — read them in full; they are the primary
grounding. Then navigate the repo freely wherever a fact's origin lies:
implementations, fixtures, sibling docs, `.dogen/context/` artifacts, and — if
present — a top-level `optional-guidance/` directory. The declared sources are
starting points, not a boundary.

**The inventory read-contract.** When the plan's outline promises an inventory — every
option, every field, every module's attributes — that promise is a read-and-materialize
contract, not a pointer. Read every member of the set at its origin and write them
out on the page. An inventory punted to a cross-reference is a coverage failure, and
an inventory partly read is worse than one not attempted: it looks complete. If the
set turns out to be unbounded or unreadable, that is a recorded gap and a conversation
with the TA, never a silently shortened list.

For an actionable unit, the grounding is the walk itself: the captured step output is
the primary source, and the page is authored from curated excerpts of what actually
ran.

Ground every behavioral claim with the three-check rule: locate, confirm, corroborate.
Never assert what you have not read. Keep a running list of every file you read —
it becomes the context report.
</step_2>

<step_3 name="Author the page">
Load `references/writing-standards.md` now for the editorial standard. Then load
the direction register matching the unit's declared `intent`:

- reference   → `references/reference-stance.md`
- explanation → `references/explanation-stance.md`
- tutorial    → `references/tutorial-stance.md`
- how-to      → `references/how-to-stance.md`

Author a Sphinx-publishable page in the unit's Diátaxis direction, following the
loaded register. Reference code entities by qualified name; show a code block only
when the reader themselves authors or invokes it. Facts you cannot verify at their
origin are left out of the prose and recorded as gaps — never hedged into the page.

**Relative links resolve from the page's location, not from the docs root.** A link
written for one directory depth silently breaks when the page lands at another, and
a unit with more than one target has more than one depth. Resolve every relative
link against the target path the plan declares, check each one against a file that
actually exists in the docs tree, and prefer the cross-reference syntax the sibling
pages already use over a hand-built path.

For an actionable unit, captured output enters the page only as curated excerpts,
chosen line by line for the reader — never a whole capture pasted in. Choose what a
reader needs to recognise; leave the rest in the workspace.

**Coverage check (before staging):** walk the unit plan's `## Outline / acceptance`
items one by one against the authored page. Every item is either present or recorded
as a gap with a reason — never silently dropped.

**Stance check:** grep the authored page for the banned researcher register, for
implementation identifiers (type/function names, `internal/` paths), and for
runtime-mechanics narration. Fix every hit before staging.
</step_3>

<step_4 name="Stage the draft and the context report">
Write the authored page to `.dogen/staging/<id>/draft/<target>` — the same
docs-relative path the plan declares, under the unit's own draft directory. For a
multi-target unit, stage the directory so that it holds exactly the signed targets;
the tool refuses `bad_draft_path` (exit 2) for anything outside that directory or for
a directory whose contents are not exactly the target set.

Write a context report to `.dogen/staging/<id>/report.json` listing every file read
(with its commit stamp or honestly empty) and any confidence gaps; an empty gaps list
needs a one-line justification.

These staging files are the ONLY files this skill writes. Never write to `docs/` —
the tool owns that placement, and it places nothing until the record is on disk.
</step_4>

<step_5 name="Record the generation">
```bash
dogen draft "$UNIT_ID" ".dogen/staging/$UNIT_ID/draft/" \
  --model "$MODEL" \
  --model-origin "$MODEL_ORIGIN" \
  --report ".dogen/staging/$UNIT_ID/report.json"
```

Capture the model metadata silently — it is provenance, not a conversation. When the
model cannot be established, the honest origin is `unknown` and the model string is
empty; do not guess one to fill the field.

The response is one line: what changed, where, what remains, and `Next:`. Echo it
verbatim. It also names every orphan — a path that is still on disk but is no longer
a signed target — once, and the tool never deletes it.

**Refusals to expect:** `no_signoff` / `plan_stale` (exit 1) route back to
dogen-plan; `page_drift` / `target_exists` (exit 1) route to dogen-review's edits
flow; `steps_unresolved` / `steps_missing` (exit 4) send you back to the walk;
`unsteered` (exit 1) is the STOP above; `identical_draft` (exit 3) means every signed
target already holds these bytes — nothing was recorded, so surface the existing seq
and commit from the payload and act on the `next` it carries.
</step_5>

<step_6 name="Report and route">
Report the recorded draft:

```
## dogen-write: <unit-id>

- Draft: .dogen/staging/<unit-id>/draft/<target>
- Recorded: <the response line, verbatim>
- Progress: drafted

Next: /dogen-review — review the draft.
```

For an actionable unit, also surface the walk tallies — **as the tool printed them**.
The response and `dogen show` both carry a tally of the form `passed 4 · skipped 1
(<reason>) · deviated 0 · unresolved 1: <id>`. Quote it. Never recompute it, never
reword it into a single "all steps verified", and never describe a resolved step as
executed: `skipped` resolves a step without running it, and collapsing the two is
exactly the claim the record does not support.

Do not commit, stage, push, or build — the tool's commit seam already recorded the
transition.
</step_6>
</workflow>

<edge_cases>
**Gate refusal (exit 1 — `no_signoff` or `plan_stale`):** route the TA back to
dogen-plan. If the plan changed after signoff, the amendment and the new signature
are one command: `dogen unit edit <id> [flags] --re-sign`.

**`generation_stale` (exit 1):** the plan was amended after the last generation, so
that draft no longer answers the current plan. Draft again — walking the steps first
if the unit is actionable.

**Unresolved steps (exit 4):** a tutorial or how-to still has unresolved steps.
Return to step 1a and finish the walk. Never skip the walk for an actionable unit.

**`identical_draft` (exit 3):** every signed target already holds these bytes.
Nothing was recorded — surface it; the TA may want to record a change first.

**A missing target page:** absence never blocks drafting. After a seal the tool
routes to `steer`: record the author's restoration request, then draft; the draft
writes every signed target, which restores the page.

**`busy` (exit 5) or `git_busy` (exit 5):** another run holds the lock, or a git
process is mid-write. Nothing was written. Wait, then re-run the same command
unchanged.

**A destructive-smelling command with no marker:** re-prompt for just-in-time consent
or switch the step to `ta` mode.

**A fact you cannot verify:** leave it out of the prose and record it under gaps in
the report — a gap is provenance, not content.

**Honest framing:** the gate proves a well-shaped capture exists and that the tool
hashed the bytes it was handed. It does not prove the command was not staged, and it
is not a filter on what the command printed: whatever the command prints is what gets
committed, minus the control characters the tool strips and beyond the size cap it
applies. Say so before a step prints anything the author would not publish.
</edge_cases>

<constraints>
<must>
- Open every session with `dogen version --json` then `dogen show <id> --json`, and
  act on the routing row for `next`.
- Branch on the declared `intent`; never author an actionable unit without walking it.
- Record the step plan with `dogen plan-steps <id> --steps-file -`, supplying `id`,
  `text`, `mode` and `stateful` per step and no hash of any kind.
- Ask the author before passing `--keep-evidence`, and pass `--note` with it.
- Capture each step by redirecting both streams into one file in the unit's scratch
  workspace and echoing the command's own exit status.
- Record each step with `dogen step <id> <step-id> --steps-seq N --evidence-file F
  --output-file F`, and let the tool compute every digest.
- Ground every behavioral claim with the three-check rule (locate, confirm, corroborate).
- Materialize every inventory the outline promises; resolve every relative link from
  the page's own location.
- Write ONLY under `.dogen/staging/<id>/draft/` and `.dogen/staging/<id>/scratch/`.
- Author in the unit's format: MyST for `.md`, rST for `.rst`.
- Echo each verb's own response line, and the walk tallies, verbatim.
</must>
<must_not>
- Never write to `docs/` — the tool owns that placement, after the record.
- Never compute, type or transcribe a digest; the tool hashes its own copy.
- Never read a pipeline's exit-status array: there is no pipe, and `$?` is the
  command's own status.
- Never treat `unsteered` as a retry — it is a STOP, and a restoration is not an
  exception.
- Never draft over a page the tool has not told you to write; `page_drift` and
  `target_exists` route to dogen-review's edits flow.
- Never hand-edit the ledger.
- Never commit, stage, push, or build — the tool's seam owns the commit.
- Never assert a fact you have not read at its origin.
- Never narrate your evidence in the drafted prose ("observed", "the fixtures show").
- Never paste a whole capture into the page, and never claim the committed excerpt is
  anything other than what the command printed.
- Never mark a step resolved by narration; only a recorded capture resolves one.
- Never run an `agent` step in the real repo cwd; they are cwd-pinned to the
  throwaway workspace.
- Never claim the evidence gate is tamper-proof, and never report a resolved step as
  executed or verified.
</must_not>
</constraints>

<success_criteria>
- [ ] The session opened on `dogen version --json` and `dogen show <id> --json`.
- [ ] The draft branched on the declared `intent`; an actionable unit was walked
      before authoring.
- [ ] `unsteered` was treated as a STOP and the author's own words were recorded
      with `dogen steer` before any redraft.
- [ ] The step plan was recorded with `dogen plan-steps … --steps-file -`, with no
      hash supplied by this skill.
- [ ] The author was asked before `--keep-evidence`, and `--note` went with it.
- [ ] Each step's output was captured to one file and handed to `dogen step` with
      `--steps-seq`, `--evidence-file` and `--output-file`.
- [ ] No digest was computed, typed or transcribed anywhere in the walk.
- [ ] The page was authored in the unit's format, with every promised inventory
      materialized and every relative link resolved from the page's location.
- [ ] The draft was staged under `.dogen/staging/<id>/draft/` and recorded with
      `dogen draft`.
- [ ] The response line and the walk tallies were quoted verbatim, with no resolved
      step reported as executed.
- [ ] The TA was routed on the `next` the tool emitted.
</success_criteria>
