Load this file at workflow step 3 (Present the provenance summary).

# Field map

The record of truth is `.crayon/units/<id>/ledger.jsonl` — chained JSONL, one
canonical line per event. **Do not read it by hand.** Every field below is derived
state, and deriving it is the tool's job, not yours: two verbs already compute it
from that one file and print it.

```bash
crayon summary "$UNIT_ID" --json    # the provenance report, as an object
crayon show "$UNIT_ID" --json       # the whole derived state, as an object
```

Use the non-`--json` form when you are reading it yourself, and the `--json` form
when you need a specific field. Quote the tool's lines in a fenced block first, as
SKILL.md step 3 asks; plain language is for your reading around them, never a bulleted
re-composition of them. In that reading the author
hears "accepted" for the `sealed` state, "the pages as accepted" for the basis, and
"request <n>" for a request; a seq, a digest and a check count are never read out.
Quote what
the tool printed; never recompute a number, never total a tally yourself, and
never turn a recorded request into "steering applied" — whether a request was
acted on is not something the record knows.

## What `crayon summary <id>` gives you

| field | what it is |
|---|---|
| `title`, `intent`, `audience` | the declared direction and reader, from the current signoff |
| `files` | the basis paths — the pages this review covers |
| `requests` | every request recorded since the last generation, each with `seq`, `note`, `origin` and its `disposition` (`pending`, `resolved` or `withdrawn`, the withdrawal's `reason` in its own field). `origin` is one of four strings, not two: `steering (plan)` and `steering (manual)` for a `crayon steer` note, and `review fix` / `review redraft` for a verdict — a fix or a redraft IS a recorded request, and on a unit that has been through one it is most of them |
| `reviewer_edits` | reviewer edits since the last generation, as `seq` and `note` — and nothing else. The ledger event can carry `hook: true` (a formatter's rewrite the author kept on `resume --adopt`), but neither `summary --json` nor `show --json` surfaces that field, so do not tell the reviewer which kind an edit was unless the note says so |
| `gaps` | the drafter's declared known gaps (`gaps[]` plus `gaps_note` from the generation) |
| `steps` | the step tally for an actionable unit, `null` for a step-free one |
| `model`, `model_origin` | what drafted it, and where that name came from |
| `provenance` | two halves: `record: verify <verdict> at <head> (<n> checks, <n> warn, <n> fail)` and `page: current` / `drifted since <sha>` / `missing` / `no basis recorded`. The `--json` value keeps that counted form; what you present is the human line `crayon summary` prints, `record: intact at <sha7>` or what it names as needing a look, so the counts are never read out |
| `state`, `next` | the derived state (`declared`, `signed-off`, `drafted`, `reviewed`, `sealed`, `retired`) and the routed next token; `sealed` is presented as accepted |

`page: current` compares the bytes crayon recorded with the bytes on disk and says
nothing about git: a page the author hand-edited and `crayon edits` then adopted reads
`current` while it is still uncommitted in the worktree. Present it as what it is, and
see step 4 for who commits the page before an accept is recorded.

## What `crayon show <id>` adds

- `qualifier` — free prose, not a token: the comma-joined list of whatever would
  otherwise mislead, from `accepted at seq N` (an accept a later amendment or request
  overtook), `plan amended at seq N`, `unit.md edited since the signoff at seq N` and
  `N request(s) pending`. Empty when the state alone is honest. The `--json`
  qualifier names seqs, so it is never read out: read out the human `crayon show`
  qualifier instead, which names the commit (`accepted in <sha7>`) and says
  `plan amended since the draft` or `unit.md edited since the signoff`. Read it out
  rather than skimming past it: the reviewer may want the plan re-approved before
  judging the draft.
- `paths` — one row per path with `status`, `recorded_sha` and `current_sha`. The
  status is one of `current`, `new`, `missing`, `drifted (uncommitted)`,
  `drifted (committed in <sha7>)`, `no longer a target (file kept)` or
  `no longer a target (file gone)`. Match on the `drifted (` prefix rather than on
  the whole string, and note the brownfield pair: a path that left the signed
  targets is reported either way, and whether the file is still there is the
  difference. `orphan` is not a status — orphans are the separate key below.
  `crayon show <id> --diff` prints the diff for each drifted one.
- `orphans` — paths still in the basis that are no longer signed targets. Reported,
  never deleted.
- `seqs` — the signoff / generation / reviewer-edit / review / basis / tip sequence
  numbers, when you need to point at one event precisely on a command line. They are
  never read out to the author.

## The declared-vs-read gap

The signoff's `sources[]` are the declared starting points. What the drafter
actually read is the generation's `origins[]`, recorded from the context report the
`draft` verb was given (`.crayon/staging/<id>/report.json`, passed with `--report`).

This is the one pair of fields no verb surfaces, so read the two events — and only
read them; the ledger is append-only and chained, and a hand edit invalidates
every line after it:

```bash
grep '"kind":"signoff"' ".crayon/units/$UNIT_ID/ledger.jsonl" | tail -1
grep '"kind":"generation"' ".crayon/units/$UNIT_ID/ledger.jsonl" | tail -1
```

The gap between `sources[]` and `origins[]` is audit-relevant. Surface it plainly:

- read everything declared and beyond → note the draft is grounded in the declared
  sources plus the named discoveries;
- read fewer or different origins than declared → surface the discrepancy so the
  reviewer can weigh it;
- no report passed / nothing recorded → present the honest-empty fact; it is a
  review signal, not an error to hide.

Do not invent, fill, or smooth over any field. If a value is missing or empty,
present it as missing or empty.

## Presentation

Fold these into the `### Provenance` block presented in both modes, ahead of the
verdict, every field in plain words, as the plain-words block says. Keep it to: the state and its qualifier, the two-part provenance line, the
recorded requests with their dispositions, the reviewer edits with their notes, the
declared-vs-read comparison, the known gaps, and the model with its origin.

For an actionable unit (`steps` is not `null`), a **quality-signals block** follows
in both modes: read out the tally the tool printed — `pass` / `fail` / `skipped` /
`deviated` and how many remain unresolved — with the `reason` fields for the
episode colour. A step-free unit shows nothing extra here.
