# Model evals

<!-- provenance: new page; condenses validation/evals/README.md and what the first eval rounds found -->

The gate proves the tool. It cannot prove that a model driving the five skills does what they
say: opens on the two calls, routes on the tool's `next`, asks one question at a time, never
bypasses the signoff, stops where a refusal says stop. The model evals under
`validation/evals/` measure that, the same way for every model. This page says what they
measure, why they are built the way they are, and how to read what they report.
`validation/evals/README.md` is the operational guide: how to run a lane, where results land and
how to add a case.

## What they measure

Every model gets the same skill text through one neutral loop. The system prompt carries the
skill catalog; a `/crayon-<skill>` invocation appends that skill's `SKILL.md`; the model reads
reference files itself, through the seven tools the skills declare. No agent harness is named,
detected or preferred, so a score difference belongs to the model.

Models are reached through OpenRouter with the key in `OPENROUTER_API_KEY`. Paid runs are
started by hand and never run in the gate or in CI. The gate's half is
`tests/test_evals.py`, which holds the kit to everything that needs no model.

| Lane | What it asks | Status |
|---|---|---|
| A | which skill handles this ask? | built, 15 cases |
| B | given this `crayon` output, what is the next action? | built, 31 cases |
| C | a whole journey in a sandbox, with a simulated author | planned |

## How lane B stays honest

A lane B case replays a history of tool calls and what `crayon` printed back, then lets the model
act. The history is never typed by hand: `validation/evals/fixtures/states.sh` builds each state
with the real `crayon.py` and records its output, and the gate re-records it, so a change in the
tool's output turns the gate red rather than leaving lane B replaying stale bytes.

The model then acts in a real copy of the recorded state. Looking is free and runs for real:
reads, searches, read-only `crayon` verbs, inspection commands, a `python3 -c` script that names
nothing able to write. The first consequential action — a verb that records, any other command,
a write, a question to the author, a turn with no tool call — ends the episode, is never
carried out, and is what the case grades.

Every command a model runs executes in a bubblewrap jail. The copy is mounted at `/srv/toyq`
beside `/usr`, a `crayon` shim and an empty `/tmp`, with its own process table and no network.
Nothing else of the machine running the eval exists in there. A command list alone could not
keep a path from leaving the sandbox, and an early run proved it, so a live run refuses to
start without the jail.

Every case carries a known-good reply that must pass and a plausible wrong one that must fail,
both enforced offline. An assertion that would pass anything cannot land.

## Grading

Each assertion returns a pass, a score and one line of feedback, the shape a prompt optimiser can
consume later. The action is graded, not its wrapping: a leading `cd` into the working directory,
trailing read-only parts such as `; echo "exit:$?"`, and quoting do not count against a command.
A "no such call" check still reads the whole command, so nothing forbidden hides in a tail. A
pinned judge model grades only the few judgement calls a pattern cannot make, such as whether a
summary was quoted verbatim.

## Models, backends and cost

`validation/evals/models.json` holds the roster, the judge and the spend caps. Every model is
pinned to one backend, so a score belongs to one model on one backend, and only to Zero Data
Retention endpoints. A backend can serve a model badly: on one, a model's first answer token
landed in its reasoning trace and the answer arrived clipped. Probe a backend once, with the
reasoning shown, before trusting a pin. A sweep and each model have a spend cap, checked before
every paid call.

## Reading results

Clean, complete runs are committed under `validation/evals/results/`; partial, dry, errored and
re-graded runs go to the gitignored `results/raw/`, beside the full turns of every case.

The backends are not deterministic even at temperature 0. The same model moves one or two
points between identical runs, so a single run cannot tell a small change from noise.
`run.py --repeat K` runs a lane K times and reports each case as passes out of K. A case at K/K
or 0/K is settled; one in between is flaky, and a change to a skill has to be measured there,
over repeated runs. The first three-run baseline, on 2026-09-24, had 15 of the 31 lane B cases
passing every run of every model.

## What they changed in crayon

The first rounds found more in the product than in the models:

- A model follows the refusal in front of it — its `hint` and its `next` — over a routing row it
  has to go and open. The `internal_error`, `unsteered` and `unapplied_steering` hints now lead
  with the act their row prescribes, and every skill acts on the row for a refusal's `error`
  before routing on `next`.
- A session that had not proposed a step plan could not see it: `crayon show` now lists the
  recorded plan, and `crayon-write` resumes from it.
- A step marked stateful takes the author's yes every time, on resume too.
- The version stop rule said "older than" and "never ordered" at once; it now gives a concrete
  case.
- `crayon-fetch` records nothing when every declared source failed.

`CHANGELOG.md` records each of these.

Related: [[development]], [[architecture]], [[contract]], [[conventions]].
