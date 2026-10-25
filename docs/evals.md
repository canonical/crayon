# Model evals

<!-- provenance: rewritten for the promptfoo and Workshop kit with deterministic grading; condenses validation/evals/README.md -->

The model evals answer one question: **can an author rely on crayon, with the model they use, to
keep them in control and keep the record true?** The answer drives two decisions:

1. **Ship.** A skill change ships only if no case that passed three out of three times on the gate
   model now passes fewer times.
2. **Supported models.** A model is listed below as supported only if it passes every critical case
   three out of three times, on the current skills.

The gate proves the tool. The evals measure what the tool cannot enforce: whether a model driving
the five skills does what they require at the moments where the author's control or the record's
truth is at stake. They do not measure page quality or time saved. `validation/evals/README.md` is
the operational guide: how to run a lane, where results land and how to add a case.

## Supported models

<!-- supported-models:begin -->
| Model | Backend | Critical cases | Standard cases | Status |
|---|---|---|---|---|
| anthropic/claude-sonnet-5.5 | google-vertex/global | no result | no result | not yet run |
| anthropic/claude-haiku-5.5 (gate) | google-vertex/global | no result | no result | not yet run |
<!-- supported-models:end -->

`uv run --project validation/evals python validation/evals/run.py --table --write` generates this
table from the committed results, and the eval suite fails when the table differs from them. A
result counts only on the skills it was run on: a skill change marks every row stale until the
model is run again.

## What a case checks

| Lane | What it asks | Status |
|---|---|---|
| A | which skill handles this ask? | built, 15 cases |
| B | given this `crayon` output, what is the next action? | built, 79 cases |

Every case names the skill rule it protects, an S-id from the skill-text suite
(`tests/test_skill_text.py`), and whether it is critical. A case is critical when it checks that
the agent:

- does not record, sign off, accept or publish without the author's explicit yes;
- does not put words in the author's mouth: notes, steering, context, verdicts;
- does not go past a refusal or an incompatibility the tool raised;
- quotes the tool's output and the record as printed.

Every other case (question order, voice, routing wording, mode choice) is standard. Every rule a
model can break at run time has at least one case, and the eval suite checks that it does.

Every case carries a known-good reply that must pass and a plausible wrong one that must fail,
both checked offline, so a check that would pass anything cannot land. Every check is
deterministic: no model grades another model's answer.

## How a case runs

promptfoo runs every case (`pf_provider.py`) and grades it with the case's own checks
(`pf_assert.py`); `promptfoo view` shows each run with its turns and tool calls.

A lane B case replays a history of tool calls and what `crayon` printed back. The history is never
typed by hand: `validation/evals/fixtures/states.sh` records each state with the real `crayon.py`,
and the eval suite records them again and compares, so a change in the tool's output fails the suite
rather than leaving lane B to replay outdated output.

The model then acts in a real copy of the recorded state, inside a Workshop container. Reads,
searches and commands run there, and the episode goes on while nothing changes. The first call that
would change something ends the episode and is what the case grades:

- `Write`, `Edit`, a question to the author, or a reply with no tool call;
- a command that names a `crayon` verb that records; it is not run;
- any other command after which the copy's files or git index differ from before it; its output
  is not shown to the model.

The kit decides by what a command changed, not by predicting what a shell command will do. The
container is launched from a staging directory that holds only the Workshop definition, `crayon.py`,
the digest script and the current case's copy: no eval case, no checkout and no secret. Commands run
as an unprivileged user with an environment built from scratch, and the copy is reset before every
case. The container's network is not closed; it holds nothing a command could send.

## Reading a result

Each case runs three times per model, because the backends are not deterministic. A case that
passes three of three or none is settled; one in between is flaky. A result file records the counts
per case, what it cost, the skills and kit it ran on, and its `decision` block:

- `supported`: whether every critical case passed every run. A dry run, a filtered run, a run with
  errors, a run of part of the cases or fewer than three runs decides nothing.
- `ship`, for the gate model: the cases that passed every run in the baseline and now fail a run.
  The baseline is the latest committed result on the same kit; a comparison across kits is refused.

Lane B has a held-out set of 21 cases (`validation/evals/cases/holdout.json`). A skill change is
measured on the other cases and accepted only if the held-out cases do not regress, so a fix cannot
be fitted to the cases it targets.

Every case that does not pass three of three on a certified model is recorded in
`validation/evals/dispositions.json` as a skill fix, a case fix or a limitation of that model, and the
eval suite fails while one is missing. A limitation on a critical case means the model is not
supported.

## Models and cost

The certified models are the ones authors run crayon with: Claude Sonnet 5.5, and Claude Haiku 5.5,
which is also the gate model because it costs least. Each is pinned to one backend that serves Zero
Data Retention endpoints only, and runs with its default sampling and reasoning, as authors run it.
The system prompt and the skill text are sent with cache breakpoints, since every turn repeats them.

Before every paid call, its largest possible cost is reserved against two caps in `models.json`: one
per run and one per model. Calls in flight therefore never spend past a cap, and the backend
checks before a run are charged to the same caps.

## Limits

- Page quality, speed and effort saved are not measured.
- Each case grades one decision, not a whole journey. Real sessions are recorded in the
  `validation/dogfood-*.md` records.
- The loop is neutral: no agent harness is named or detected. A supported model is supported in
  this loop; a harness adds its own instructions.
- Paid runs are started by hand, never in the gate or CI.

## What the evals changed in crayon

The first rounds found more in the product than in the models:

- A model follows the refusal in front of it, its `hint` and its `next`, over a routing row it has
  to go and open. The `internal_error`, `unsteered` and `unapplied_steering` hints now lead with the
  act their row prescribes, and every skill acts on the row for a refusal's `error` before routing
  on `next`.
- A session that had not proposed a step plan could not see it: `crayon show` now lists the
  recorded plan, and `crayon-write` resumes from it.
- A step marked stateful takes the author's yes every time, on resume too.
- The version stop rule said "older than" and "never ordered" at once; it now gives a concrete
  case.
- `crayon-fetch` records nothing when every declared source failed.

`CHANGELOG.md` records each of these.

Related: [[development]], [[architecture]], [[contract]], [[conventions]].
