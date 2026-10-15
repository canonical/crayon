---
name: crayon-review
description: Surfaces a drafted documentation unit for human review through two modes — record (compact provenance summary + verdict) and review (additionally runs a six-dimension findings review). Records the verdict by calling crayon review for all verdicts — accept seals the recorded basis, fix and redraft record the note as steering. Never edits the draft. Use when a TA is ready to review a drafted unit.
allowed-tools: Read, Bash, Glob, Grep, AskUserQuestion
metadata:
  crayon_contract: 1
  crayon_min_tool: "0.2.0"
---
<objective>
Surface a drafted documentation unit for human review and record the reviewer's
structured verdict — without changing anything the reviewer will publish. The
reviewer chooses one of two modes: **record** (present the provenance summary the
tool produced, then record the verdict) or **review** (additionally run a
six-dimension findings review grounded by re-checking claims against the recorded
sources).

This skill also owns two flows that are not verdicts: adopting bytes the record has
never seen, and presenting recovery after an interrupted run. It never edits a page,
never edits the plan, and never runs a build. Regeneration routes back to crayon-write.
</objective>

<opening>
The first two commands of every session — before anything is proposed, written or
recorded:

```bash
crayon version --json                # {"tool": "<version>", "contract": 1}
crayon show "$UNIT_ID" --json        # the derived state, and the routed `next`
```

Stop on exactly two answers from the first call: a `contract` that is not `1`, or a
`tool` older than `min_tool` `0.2.0`. Both numbers are compared as literal strings —
never parsed or rounded as versions. `0.1.9` is older than `0.2.0`: stop, say which
number stopped you, and run nothing else. Any other answer means the pairing is
supported; continue.

The second call is the only source of direction.
**Read `references/routing.md` and act on the row for the emitted `next`.**
Never re-derive the state, never infer the next step from the conversation, and never
decide direction yourself: the tool derives state from the record, and the routing
table is a rendering of the same preconditions the tool enforces.
A refusal is one JSON line with `error`, `hint` and `next`: act on the routing row
for its `error` first — that row says what to do now — and route on `next` only
after it. The `hint` is a reminder, never the whole route.

**The ledger is never hand-edited.** `.crayon/units/<id>/ledger.jsonl` is hash-chained:
every line's `prev` is the digest of the previous line's bytes, so editing any line
invalidates every line after it. Nothing in this skill ever opens it in an editor —
not to fix a typo, not to append a note, not to correct a field.
</opening>

<!-- author-rules:begin -->
<author_rules>
These three rules hold at every question this skill puts to the author.

- **The author's words, verbatim.** A note recorded with `--note`, `--note-file -` or
  `--notes` is exactly what the author typed beyond the verdict, the yes or the no that
  answered the question: that answer alone is not part of the note, so "Fix." then
  "Say …" records the second reply, and "Accept. The table …" records "The table …".
  The words beyond it, given across several turns, are joined in order, one reply per
  line. No spelling fix, no rephrasing, and no text offered for them to approve, such
  as "I'll use: …". When their words are unclear, ask them; never rewrite them. With
  nothing of theirs to record, omit the flag.
  On the command line their words go inside single quotes, each `'` in them written
  as `'\''`, and never inside double quotes: there a backtick runs a command and a `$`
  expands, so the record would hold words they never typed. Through `--note-file -`,
  the same single-quoted words are piped in with `printf '%s'`, which adds nothing.
- **No marked option on a judgment question.** Audience, intent, step choices, the
  verdict and restore-or-amend are the author's judgment. No option of those questions
  carries "(Recommended)", "(default)", "suggested", a star or any other marker, and
  their order implies nothing. This rule wins over any harness's own convention of
  marking a recommended option. A mechanical choice, such as an id, a path or a title,
  may keep a marked default.
- **An explicit go.** A signoff or an accept runs only on an explicit go: an
  affirmative ("yes", "go", "sign it") to a question that named that act. For an
  accept, the go is the verdict itself, or a yes to "Keep accept?". "Looks good" about
  an outline is not a go, and neither is "yes, but …": handle the change, then ask
  again.
</author_rules>
<!-- author-rules:end -->

<!-- plain-words:begin -->
<plain_words>
What the author reads from this skill is in plain words. The record's own words stay in
`--json`, in the ledger and on every command line, and never reach your prose.

- **Accepted, the pages as accepted, request N.** Say "accepted" where the record says
  sealed, "the pages as accepted" where it says basis, and "request 7" where it says
  seq 7 for a request. Give no other record entry a number, neither "event 7" nor
  "ledger line 7": say what is already recorded and name its commit. These record
  words stay out of your own prose altogether, not even as an English idiom: say
  "on what grounds", not "on what basis".
- **No hashes, digests or verify counts.** A `plan_hash` or a file or record hash,
  a sha256, a digest, and a verify or check count never appear in what you say;
  name a commit by its id, never as a hash. Quote the tallies:
  the walk tally and the findings tally are the tool's and the rubric's own lines.
- **The success line, verbatim.** Echo each verb's success response line exactly as the
  tool printed it; it is already plain. These rules cover what you say around it.
- **Refusals in plain words, commands exact.** Tell the author in plain words what a
  refusal means, for example "request 4 is still open". A command you run or show keeps
  its real flags and values, in a code span. Tool output you show verbatim goes in a
  fenced code block, never inside a sentence. That covers what a step or a routing row
  says to show, and any other line you quote beyond the success line, such as a
  diagnostic a verb prints.
</plain_words>
<!-- plain-words:end -->

<quick_start>
1. Run the two-verb opening above and act on the routing row for `next`.
2. Read the shown state and the drafted page(s) under `docs/`.
3. Select the review mode with `AskUserQuestion`: **record** or **review**.
4. Present the provenance summary (both modes), quoting the tool's own lines, and
   end it with every deviated or skipped step put to the author as a question
   (step 3a), before any finding and before the verdict question; when the
   reviewer already authorised the accept, the closure asks them instead.
5. In review mode, run the six-dimension findings review.
6. Ask for the verdict with the one open question and record it with `crayon review`.
   After an accept, close with at most three questions drawn from the record, then
   STOP.
</quick_start>

<pipeline>
crayon-plan -> crayon-write -> crayon-review
                            \-> back to crayon-write (fix/redraft)

This skill is the review stage — the last in the loop. On accept, the author is
asked at most three questions the record still holds open, and the loop stops.
On fix/redraft, it routes back to the draft-stage skill with the note recorded as
the author's request.
</pipeline>

<workflow>
<step_1 name="Read the unit state from the tool">
The opening already answered this. Read what it printed rather than re-deriving any
of it:

```bash
crayon show "$UNIT_ID"
crayon summary "$UNIT_ID"
```

`crayon show` reports the title and intent, the state with a qualifier whenever the
state alone would mislead, each basis path as `current` / `drifted` / `missing`,
signed targets not yet in the basis, paths no longer signed, every recorded request
since the last generation with its disposition, the step tally, reviewer edits, and
`Next:`. `crayon summary` is the paste-ready version — `--md` for PR text.

Then read the drafted page(s) under `docs/` at the paths the plan declares.

If the routed `next` is `draft` or `walk`, the unit has no generation to review —
route the TA to crayon-write. Every other token has a row in `references/routing.md`;
act on it.
</step_1>

<step_2 name="Select the review mode">
Ask the reviewer, with `AskUserQuestion`, which mode they want:

- **record** — "I have already read it; just record my verdict." Skips the findings
  review; goes straight to the provenance summary and the verdict.
- **review** — "Do a full review and show me findings." Runs the six-dimension
  findings review before the verdict.

The raw page source is not dumped by default in either mode — offer it only if the
reviewer asks.
</step_2>

<step_3 name="Present the provenance summary">
Load `references/provenance-summary.md` now for the field map.

Both modes. **The summary is the tool's, not yours.** Quote the lines
`crayon summary <id>` printed — title, files changed, intent and audience, the
recorded requests with their dispositions, reviewer edits with their notes, known
gaps, the steps tally with its skipped reasons, model and origin, and the two-part
provenance line for the record and the page. Add reading of your own around them if
it helps the reviewer, but never recompose a number and never turn "recorded
requests" into "steering applied": a recorded request is a request, and whether it
was applied is not something the record knows.

Two lines deserve to be read out rather than skimmed past:

- **the plan was edited after it was signed** (what the tool calls `plan_stale`) —
  `unit.md` moved after the signature that froze it. The reviewer may want the plan
  re-approved before judging the draft.
- **a `drifted` or `missing` page** — the bytes under review are not the bytes the
  record cites. Handle that before the verdict, in step 4 or step 6.
</step_3>

<step_3a name="Put deviated and skipped steps to the author">
Both modes. After the provenance summary and before any findings or the verdict,
read `handover.steps` from the opening's `crayon show "$UNIT_ID" --json`; run it again
if this conversation no longer holds it. Each entry is a step of the walk that
deviated or was skipped, with its id and its recorded reason.

When the reviewer already authorised the accept, step 3a is skipped; the closure asks
the steps instead, because none was put to the author in this conversation.

With no entry, ask nothing about steps and go on.

Otherwise end the provenance-summary message with every entry as a question about
the page, in one numbered list, in the order `handover.steps` lists them, with
no cap. Each question names its step and its reason in plain words, for example
"Step install-deps was skipped: no network in CI. Does the page need to say so?" or
"Step init deviated: <its reason>. Does the page need to say so?". Quote each id and
reason as the tool gives them, and add no count of your own: the tally stays the
tool's own line. The questions are plain text, not options in a question tool.

The author may answer any, all or none. Nothing is recorded from an answer: no steer and no note.
When an answer asks for a page change, say in one line that it is not recorded until
the verdict, and that a fix or redraft verdict with those words records it.
The review then moves on, to the findings in review mode (step 5) and to the verdict
question in record mode (step 6). The author's answer to the verdict question is the
note. A fix or redraft given with no words still gets "What should the next draft
change?".

The closure after an accept in this conversation does not ask again a step whose
answer asked for no page change, and a step left unanswered is not asked again. A step
whose answer asked for one comes back there, named with the change the author asked
for (step 6).
</step_3a>

<step_4 name="On record_edits — adopt the bytes before judging them">
`record_edits` means a basis page on disk no longer holds the recorded bytes
(`page_drift`), or a signed target already holds bytes the record has never seen
(`target_exists` — a brownfield page). Neither is an error, and neither is undone.

Show the reviewer what changed:

```bash
crayon show "$UNIT_ID" --diff
```

Then ask, in these words: "record these as your edits?" On yes:

```bash
crayon edits "$UNIT_ID" --note '<their own words>'
```

The note is the author's, in the author's phrasing. When a formatting hook produced
the bytes rather than a person, tell the author once what the record must say, and
why: that a hook changed the bytes and that they kept them, because a formatter is
not a reviewer and the record should not read as though one reviewed the page. Then
ask them for the note and record their words verbatim. If their words leave the hook
out, ask once more, naming only that one fact. If they still leave it out, record
nothing: say that the tool's contract wants a hook's bytes adopted with a note that
says so, and stop. The page stays on `record_edits` until they give one. Never write
the note for them, and never ask a third time.

The recorded set is the complete basis: every path of the previous basis with its
recorded digest unless it changed, plus any adopted target, minus paths that are
missing from disk and no longer signed targets. An absent page alone is not an edit
— `no_edits` (exit 3) says exactly that.

**`crayon edits` records the bytes onto the record; it does not commit the page.**
After it runs, `crayon show` reports that path `current`, because the recorded digest
and the bytes on disk agree — that is all `current` has ever meant, and it is not a
claim that the page is committed. A page the author hand-edited in the worktree can
read `current` and still be listed by `git status`; say which of the two you are
looking at rather than letting `current` answer both questions. crayon commits the
ledger and the files its own verbs write; a page the author edited by hand is the
author's to commit. Ask them to commit the target page before you record an accept,
so the accepted basis and the committed tree name the same bytes. If they would
rather not commit it yet, say so plainly and do not accept.

**When the reviewer already authorised the accept in this same turn, accept in this
same turn.** Adopting the bytes does not entitle you to ask for the verdict twice.
</step_4>

<step_5 name="Perform the findings review (review mode only)">
Load `references/review-rubric.md` now for the pre-pass, dimensions, priority tags,
and verification discipline.

Skip entirely in record mode.

**Deterministic pre-pass (before any judgment):** run cheap read-only greps over
the drafted page(s):
- changelog-framing tells ("previously", "now supports", "starting with")
- banned researcher register ("observed", "the fixtures show", "the corpus")
- self-reference openers ("This page describes", "This document")

Each hit is either promoted into the findings as a prioritized finding marked
`(pre-pass)`, or dismissed with a one-line reason.

**Self-review.** Before the findings, decide whether this is a self-review. It is one
when this conversation ran `crayon draft` for this unit, or when the `model` line of
`crayon summary` names the model you run as. Establish your own model the way you would
record it on a draft, from what you are told about the model you run as, never guessed;
when you cannot, only the first ground applies. When neither holds, because the
recorded model is another one, or is empty with the origin `unknown`, and the draft ran
in another session, there are no grounds: say nothing about it. With grounds, put one
line in the first person directly before the findings, for example:

> I drafted this page, so this is a self-review; I'm likely to miss what I got wrong the first time. Weigh these findings with that in mind.

Record mode has no findings and no such line, and the line is never repeated at the
verdict.

Then assess the six dimensions, presenting findings grouped by dimension:

1. **writing-approach** (always on, assessed first) — stance contract violations,
   researcher register, implementation identifiers in prose.
2. **source-fidelity** — re-check the draft's concrete claims against the recorded
   sources. Open the files; don't judge only on internal coherence.
3. **completeness** — does the draft satisfy every `## Outline / acceptance` item?
   An objective-check failure is must-fix by definition.
4. **focus** — the mirror of completeness: what is on the page that the reader does
   not need. Material the reader's problem does not call for, anything the author's
   intake notes say to leave out (must-fix), and a complete page whose sections do not
   build toward the reader's problem, meet the reader where they arrive or hand them
   their next step.
5. **structure-fit** — format hygiene (MyST/rST), cross-page consistency for
   multi-file units, relative link paths resolve from the page's location.
6. **clarity** — sentence-level clarity, jargon, forward references.

Number findings `F-1`, `F-2`, … Each carries: page path, the verbatim offending
text, a concrete suggested action, and a priority tag (must-fix / should-fix / nit).
Ground source-fidelity and completeness by re-checking claims against the recorded
sources.

A finding you could not fully verify says so inside the finding, in the first person,
naming what you looked for or inferred from, for example "I found no source for the
30-second default" or "I inferred the retry order from queue.py". A verified finding
carries no hedge. There is never a section of doubts and never a general caveat about
the review.
</step_5>

<step_6 name="Elicit the verdict and record it">
Ask for the verdict with one open question that also asks for anything the author
wants on the record with it, in these words:

**What's your verdict, and is there anything you want on the record with it?**

If it is asked with options, they are accept, fix and redraft, unmarked, as the
author rules require.

Read the answer for the verdict and for anything beyond it. Whatever the author said
beyond the verdict is the note, word for word. An answer that names no verdict
("looks pretty good") is not a verdict, and an accept with a condition
("accept, but …") is not a go: ask again, and record nothing until the author names
the verdict.

**The lean, held until the author answers.** In review mode the findings, their tags,
the `Findings:` tally line and the dismissed pre-pass candidates are already in front
of the author (step 5), and the lean is not. The lean is the tally read one way: any
must-fix leans to fix (or to redraft when the must-fixes are pervasive), a clean
tally leans to accept, and a should-fix-only tally has no lean. After the author
answers, a verdict that matches the lean, or any verdict on a tally with no lean, is
recorded without comment. A verdict that differs gets the lean with its one-clause
reason and one question, `Keep <verdict>?`, for example "The tally leans to fix: F-1
is a must-fix. Keep accept?". The answer is final, and there is no second check: a
yes records the verdict they gave, and a no asks which verdict they want instead. If
the author asks what the tally suggests before answering, show the lean then.
Record mode has no findings and no lean.

**On fix / redraft:** the note is required (`note_required`). When the author gave
only the verdict, ask "What should the next draft change?" and record their answer
verbatim.

```bash
crayon review "$UNIT_ID" --verdict fix --note '<their words>'
```

The note is exactly what the next drafting pass reads, in the author's own words. It
is recorded as the author's request, so the next draft is no longer refused
`unsteered`.

When the author cites findings by number ("fix F-2 and F-5"), tell them that
the numbers will not reach the next drafting session, show each cited finding's
text, and ask what the next draft should do about it. Their answer is the note.

**On accept:**

```bash
crayon review "$UNIT_ID" --verdict accept
```

A bare accept records no note. When the reviewer said more than the verdict, those
words, exactly as they typed them, are the note: add
`--note '<their words beyond the verdict>'`.

Accept seals the basis, and it has two preconditions this skill must be ready for.

**`unapplied_steering` (exit 1)** — requests are still pending, and the refusal's
`detail` lists the pending requests' numbers. Nothing is closed by silence:
put each pending request to the reviewer one at a time, as "request <n>" with its note,
then take one disposition for each, and re-run accept carrying all of them:

```bash
crayon review "$UNIT_ID" --verdict accept [--note '<their words beyond the verdict>'] --resolves 7,9 --withdraw 12 '<why it no longer applies>'
```

`--resolves` is the reviewer's recorded judgment that a request is satisfied — not
proof that any bytes changed. `--withdraw` repeats, once per seq, and every
withdrawal carries a non-empty reason. The two sets are disjoint and every listed seq
must be pending; otherwise the tool refuses `bad_resolution` (exit 2). Never guess a
disposition, and never resolve a seq the reviewer did not speak to.

**`target_missing` (exit 1)** — a signed target is absent from disk, or is not in the
basis. See step 7. **Accept is never issued a second time.**

Then route:
- **accept** → close as below; the loop stops.
- **fix** → `Next: /crayon-write — apply the recorded request.`
- **redraft** → `Next: /crayon-write — re-draft against the recorded request.`

Echo the verb's own response line verbatim. Then STOP: no build, no publish, no edits
to the page. After an accept, the closure below is that STOP.

**After an accept — close on what the record holds open.**

1. Read what the record still holds open:

   ```bash
   crayon show "$UNIT_ID" --json
   ```

   Each `handover.steps` entry (a deviated or skipped step) is open,
   except a step this conversation already put to the author in step 3a, unless its
   answer asked for a page change; a step left unanswered is not asked again. A step
   whose answer asked for a page change is open: its question names the change the author asked for, in their
   words. In a later session, every step counts again, because the asking is not on
   the record. Each `handover.judged` entry (a request accepted without a page change) is
   open too. `withdrawn` entries are not.
2. Findings count only when review mode ran in this same conversation. Each
   must-fix or should-fix finding the author did not speak to in the verdict
   exchange is open. Nits never count. In a later session this source is absent,
   and the skill never guesses at it.
3. Where a reader arrives from: search the docs tree read-only for each accepted
   page. A hit counts only when it resolves to that page: its docs-relative path
   without the extension (`reference/config`) anywhere, or its bare stem (`config`)
   in a toctree entry or a `{doc}` / `:doc:` role of a page in the same directory
   (`reference/index.md`), because those resolve relative to the page that holds
   them. A file name alone (`config.md`) is a link only when it resolves to the
   accepted page from the page that holds it; another directory's `config.md` is
   not. It is open only when no other page links to the page or lists it in a
   toctree.
4. Nothing open: no questions. The message is the accept line alone.
5. Ask at most three questions. Take one per source first, in the fixed order
   steps → judged requests → findings → where a reader arrives from, then fill the
   remaining slots in the same order. Anything beyond three gets one plain line, not
   a question: how many more are open, a pointer to "Author decisions" in
   `crayon summary "$UNIT_ID" --md` for the steps and judged requests among them, and
   any finding or reader-arrival item among them named in plain words, because that
   summary does not list those.
6. It is one message: the accept response line, echoed verbatim (it already ends
   `Next: yours — crayon stops here`), then a numbered list of the questions in plain
   words, each naming its item, for example "Step install-deps was skipped: no
   network in CI. Does the page need to say so?" or "Nothing links to
   reference/config.md yet; where should a reader come from?". The questions are
   plain text, not options in a question tool. There is no second stops-here line,
   and no publishing, pull request or build is offered as a next step.
7. The author may answer any question or none. Nothing is recorded from an answer by
   default, and crayon stops. If an answer asks for a page change, record the
   author's words verbatim and route to `/crayon-write`:

   ```bash
   crayon steer "$UNIT_ID" --note '<their words>'
   ```

   Steering an accepted unit is legal: it reopens the unit for a redraft, and a
   fresh accept follows.
</step_6>

<step_7 name="On target_missing — the author's call, not yours">
The signed plan still lists a target that is not on disk. **Accept is never issued a
second time.** Re-running it cannot change the outcome, because absence is a
precondition the tool checks, not a transient failure — a second accept only records
that the skill did not read the first refusal.

There are exactly two paths out, and they produce different documentation:

**The author has already asked, explicitly, for the page to be restored.** Then the
direction is given; record it with `crayon steer` without reconfirming it, and route
to crayon-write. The next draft writes every signed target, which restores the page,
and the accept follows after that.

```bash
crayon steer "$UNIT_ID" --note '<their own restoration request>'
```

**The author has said nothing about the missing page.** Then ask — once, plainly, and
without proposing an answer: the signed plan still includes that target, so the
unit cannot be accepted while it is absent.
**Restore the page, or amend the plan so that path is no longer a target?**

- **restore** → record that request as above, route to crayon-write, then accept.
- **amend** → route to crayon-plan, which re-signs the plan without that target. The
  old page is then reported once as an orphan and kept on disk; the generation that
  answered the old plan becomes `generation_stale` and cannot be accepted, so the
  unit drafts again before its verdict.

Record only the direction the author actually gave.
**The skill invents no steering note.**
A restoration request the author never made is a line in a tamper-evident record
saying they did, and no amount of helpfulness is worth that.
</step_7>

<step_8 name="On uncommitted_tail — resume, dry run first">
An interrupted run left lines the commit never covered. Classify before writing:

```bash
crayon resume "$UNIT_ID" --dry-run
```

The dry run writes nothing — not the record, not a page, not the index — and prints
how it classifies each file: `done` (disk already holds the intended bytes),
`recoverable` (disk holds the pre-operation bytes, or the file is absent as
recorded), or `unexpected` (anything else). Show that classification to the author,
then read it yourself before issuing anything else. If any file is `unexpected`,
use step 9's choices. Only with no `unexpected` files:

```bash
crayon resume "$UNIT_ID"
```

Never issue two write verbs without reading the first one's response. The dry run is
how this skill reads the situation before it changes it.
</step_8>

<step_9 name="On resume_ambiguous — exactly two choices">
Some file on disk differs from what the interrupted run intended. The tool wrote
nothing: both the pages and the record are byte-identical to how it found them.

Show its stdout verbatim, in a code block, including the per-file diffs — that is
what the author needs to decide, and paraphrasing a diff loses the decision. Then
offer exactly the two choices the contract names, and no third:

- **discard the on-disk bytes**, taking the interrupted run's intended bytes:
  `crayon resume <id> --overwrite`
- **keep the on-disk bytes**, recorded as a reviewer edit:
  `crayon resume <id> --adopt --note '<their note>'`

Recording a new adoption with `--adopt --note` is allowed only when the interrupted
batch ends in a generation or a reviewer edit that is not itself an adoption,
at least one file is `unexpected`,
and every unexpected file's rewritten bytes are still on disk. A deleted file has
no bytes to adopt: offer the discard alone there. A batch whose last event is
already an adoption (`hook: true`) instead offers `crayon resume <id> --adopt`
to retain the on-disk bytes while completing the existing batch, or
`crayon resume <id> --overwrite` to restore that adoption's saved bytes.
Repeated `--adopt` appends no event and records no note, so do not offer it as a
way to amend the note. Bare `crayon resume <id>` is available only with no
`unexpected` files. After completion, follow the emitted route: if the bytes still
differ from that adoption, `record_edits` calls for `crayon edits <id> --note "…"`;
a hook may have restored them during the commit. Remove what is refusing the
transition before retrying either choice. For other ineligible batches the tool refuses
`adopt_unsupported` (exit 6), and the two honest answers are the discard above
or the printed expert recipe. Do not invent a
third path, and do not recommend one of the two — the choice is whose bytes to keep,
which is the author's to make.
</step_9>

<step_10 name="On recovery_unsupported — the honest limit">
Show the tool's printed findings verbatim, in a code block, then branch on the
refusal's `detail`. There are two different situations under this one reason and they
have opposite answers.

**`detail: commit_rejected` or `detail: stage_rejected` — the write path's own limit.**
Here the batch *was* appended to the record and the files *were* placed; git failed to
complete the transition twice, so the tool stopped rather than re-placing the same bytes
for a third attempt. Do not tell the author their work was not written — the ledger tail
and the placed pages are both on disk, and `.crayon/staging/<id>/pending` holds the
recovery material. Show the git output the refusal carries: that is what is actually
blocking the transition.

Read the two details apart, because they have different causes and you will be naming
the wrong thing to look at otherwise. **`commit_rejected`** means git ran the commit and
something refused it — a pre-commit hook, most often — so the answer is the repository's
commit hooks. **`stage_rejected`** means `git add` failed and the commit was never
attempted, so **no hook ran**: it is `git status` and the index — an unstageable
pathspec, an index that will not lock, a read-only `.git`. The refusal's `step` field
names which git call failed. Either way, offer the escape that always works: remove what
is refusing the transition, then inspect `crayon resume <id> --dry-run`.
Use bare `crayon resume <id>` only with no `unexpected` files; otherwise use step 9.

`crayon resume <id> --adopt --note '<their note>'` is the OTHER escape, and it
is conditional — offer it only when every condition below holds.
`--adopt` needs the batch's last event to be a generation or a reviewer edit that
is not itself an adoption (any other batch refuses `adopt_unsupported`, exit 6;
an already-adopted batch uses step 9's repeated `--adopt` or `--overwrite`
completion, with no new event or note), and it needs the hook to have
REWRITTEN the placed bytes (with nothing on disk `unexpected` it degrades to a plain
resume, which re-places the same bytes and is refused again, reproducing the very
refusal it was offered against). Read `crayon resume <id> --dry-run` first: if no path
is listed `unexpected`, `--adopt` is not the answer here. Every unexpected file's
current bytes must also be still on disk; a deleted file refuses `adopt_unsupported`,
so offer `--overwrite` after removing any remaining blocker. Do not route on the emitted
`next` either: it is `resume`, and a plain `crayon resume <id>` under an unchanged hook
is the command that just refused.

**Every other detail — `no_material`, `material_invalid`, `event_invalid`,
`tail_unknown` — is stage a's.** There the tool could not derive a safe completion and
it wrote nothing; it printed what it found — the uncommitted seqs, which paths it could
account for and against which bytes, and which it could not.
Show the tool's printed findings verbatim and stop. Offer no
recipe of your own. Restore nothing from git history; committed history is not the
same as the pre-operation bytes. Suggest nothing that would commit the tail: a line
the tool refused to derive state from does not become true by being committed. The
unit directory and every file the tool could not attribute are preserved exactly as
they are, which is the point of stopping.

The stage-a answer also holds for `ledger_corrupt`, `ledger_diverged`,
`ledger_version_unsupported` and `unit_id_mismatch`: show the refusal verbatim, in a
code block, and stop.
</step_10>
</workflow>

<edge_cases>
**Unit never drafted:** the routed `next` is `draft` or `walk`. Route the TA to
crayon-write.

**Reviewer wants text edits:** this skill does not edit the page. There are two
recorded paths: the reviewer edits the file themselves and the change is adopted with
`crayon edits <id> --note "…"`, or the change is recorded as a fix/redraft verdict and
crayon-write applies it. Never offer to edit the page yourself.

**`already_accepted` (exit 3):** the unit is already accepted on these pages with
nothing recorded since. Say that it is already accepted and
give the commit from the payload, naming no record number — a second accept is
neither needed nor recorded.

**The unit is already accepted (`publish`):** the session opens on an accepted unit
with nothing recorded since. Say in one plain line that the unit is already accepted
and that crayon stops here. Then ask the questions step 6's closure asks, drawn from
the record, without the findings source, because no review ran in this conversation.
The same rules hold: at most three, one per source first, none when nothing is open,
and a change request steered in the author's words. Nothing is lost when a session
ends before its closure: the accept is already committed, and the next session closes
again.

**Reopening an accepted unit:** record a `fix` or `redraft` verdict. That reopens the
unit, and the next crayon-write pass re-drafts it.

**`generation_stale` (exit 1):** the plan was amended after the generation under
review, so that draft answers a plan that has moved. It cannot be accepted; the unit
drafts again first. Say that plainly rather than presenting it as an error.

**A hook changed a page after the commit:** the transition stands — it is committed —
and the tool warns and re-derives, routing to `record_edits`. Adopt the bytes with the
author's own note, which says a hook changed them (step 4).

**`busy` (exit 5) or `git_busy` (exit 5):** another run holds the lock, or a git
process is mid-write. Nothing was written. Wait, then re-run the same command
unchanged.
</edge_cases>

<constraints>
<must>
- Open every session with `crayon version --json` then `crayon show <id> --json`, and
  act on the routing row for `next`.
- Offer two selectable modes up front (record vs review) via `AskUserQuestion`.
- Present the provenance summary in both modes, quoting the tool's own lines.
- After the provenance summary, in both modes, put every deviated or skipped step in
  `handover.steps` to the author as a question, in one numbered list, before any
  findings or the verdict, unless the reviewer already authorised the accept, when the
  closure asks them; record nothing from an answer, and when an answer asks for a page
  change, say in one line that it is not recorded until the verdict.
- In review mode, run the deterministic pre-pass before judgment, then present
  six-dimension findings grouped by dimension, numbered F-N with
  must-fix/should-fix/nit tags.
- In review mode, when this conversation ran the draft or the recorded model is yours,
  say in one line before the findings that this is a self-review.
- Ground source-fidelity/completeness findings by re-checking claims against the
  recorded sources.
- On `record_edits`, show `crayon show <id> --diff`, ask "record these as your edits?",
  and record with `crayon edits <id> --note "…"` in the author's words.
- Ask for the verdict with the one open question
  "What's your verdict, and is there anything you want on the record with it?",
  and show no lean before the author answers unless they ask what the tally suggests.
- Record a fix or redraft note, and an accept's note, exactly as the author typed it,
  and a bare accept with no note.
- When the verdict differs from the lean, show the lean once and ask
  `Keep <verdict>?`; the answer is final.
- When the author cites findings by number, restate each cited finding and ask what
  the next draft should do about it.
- Accept in the same turn when the reviewer already authorised it.
- After an accept, echo the accept line verbatim and ask at most three questions
  drawn from the record, one per source first in the fixed order, none when nothing
  is open.
- On `unapplied_steering`, take one disposition per pending seq and pass them as
  `--resolves` and `--withdraw <seq> "<reason>"`, disjoint, every withdrawal with a
  reason.
- On `target_missing`, ask the restore-or-amend question unless the author has
  already given the direction, and record only what they said.
- On `uncommitted_tail`, run the dry run and read its classification before the real
  resume.
- On `resume_ambiguous`, show the tool's stdout verbatim and offer exactly the two
  contract choices.
- On `recovery_unsupported`, show the printed findings verbatim and stop.
</must>
<must_not>
- Never run `sphinx-build` or any build — building and publishing are out of scope.
- Never edit a page under `docs/`, the plan, or any file — the correction path is a
  recorded verdict plus a drafting pass.
- Never hand-edit the ledger, and never suggest that anyone else does.
- Never retry accept after `target_missing`.
- Never record a request the author did not make, and never resolve or withdraw a seq
  the reviewer did not speak to.
- Never show the lean before the author answers, unless they ask what the tally
  suggests.
- Never write, rephrase, correct or offer note text, the hook-adoption note included.
- Never ask `Keep <verdict>?` twice, and never overrule the author's answer to it.
- Never offer publishing, a pull request or a build as a next step.
- Never record anything from a closure answer that asks for no page change, and never
  put a change request in words other than the author's.
- Never record a steer or a note from an answer to a step question.
- Never let a page change asked for in a step answer pass without saying it is not
  recorded until the verdict.
- Never offer a recovery step the tool did not print, and never suggest that
  committing an interrupted tail makes the situation go away.
- Never recompose or reword the tool's own summary and tally lines.
- Never call a review a self-review without grounds in this conversation or the
  record, and never repeat that line at the verdict.
- Never dump the raw page source into the conversation by default; offer only on
  request.
</must_not>
</constraints>

<success_criteria>
- [ ] The session opened on `crayon version --json` and `crayon show <id> --json`.
- [ ] The review mode (record or review) was selected up front.
- [ ] The provenance summary was presented from the tool's own lines before the verdict.
- [ ] Every deviated or skipped step was put to the author as a question after the
      provenance summary, in both modes, unless the reviewer already authorised the accept,
      when the closure asked them. Nothing was recorded from an answer; a change asked
      for in a step answer was said to be not recorded until the verdict, and was asked
      again at the closure after an accept.
- [ ] In review mode, the pre-pass and six-dimension findings ran, grounded against
      the recorded sources; in record mode, findings were skipped.
- [ ] A self-review was named in one line before the findings when, and only when,
      this conversation ran the draft or the recorded model was the reviewer's.
- [ ] `record_edits` showed the diff, asked "record these as your edits?", and
      recorded the author's own words.
- [ ] The verdict was asked with the one open question, and the lean appeared only
      after the answer or on request.
- [ ] Every note was recorded verbatim, as the author typed it; a bare accept carried
      none, and a hook-adoption note was the author's own words.
- [ ] A verdict that departed from the lean got one `Keep <verdict>?`, and the answer
      stood.
- [ ] Finding numbers cited by the author were restated with them before any note was
      recorded.
- [ ] After an accept, the accept line was echoed verbatim, followed by at most three
      questions drawn from the record (none when nothing was open) and no publishing
      step; a change request was steered in the author's words.
- [ ] `unapplied_steering` was closed by one recorded disposition per pending seq.
- [ ] `target_missing` never produced a second accept, and only the author's own
      direction was recorded.
- [ ] `uncommitted_tail` ran the dry run first and the real resume second.
- [ ] `resume_ambiguous` showed the tool's stdout verbatim and offered exactly two
      choices.
- [ ] `recovery_unsupported` was shown verbatim and the skill stopped.
- [ ] No build was run, no file under `docs/` was edited, and hand-editing was never
      suggested.
</success_criteria>
