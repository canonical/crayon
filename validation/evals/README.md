# Model evals

Dev-time evaluation material, like the rest of `validation/`. This kit measures how well a model,
driving the five dogen skills, does what the skills say. It does not re-test the tool itself: the
gate already covers that.

The same skill text and the same neutral loop are given to every model, so a score difference
belongs to the model. No agent harness sits in between:

- The system prompt carries the skill catalog: each skill's name, description and install
  location.
- `/dogen-<skill> <args>` appends that skill's `SKILL.md` body to the turn.
- The model reads reference files itself.

Everything is stdlib Python. Models are reached through OpenRouter with the key in
`OPENROUTER_API_KEY`.

## Lanes

| Lane | What it asks | Live turns | Graded by | Status |
|---|---|---|---|---|
| A | which skill handles this ask? | 1, no tools | exact skill name | built, 15 cases |
| B | given this `dogen` output, what is the next action? | until the first consequential action | that action, the calls on the way, 4 judged | built, 31 cases |
| C | a whole journey in a real sandbox with a simulated author | many | ledger, `score.py audit`, transcript, 1 judged page | planned |

## How lane B works

A case invokes one skill (`/dogen-review cfg`) and replays a history: the tool calls a model
made and what `dogen` printed back. Those outputs are never typed by hand.
`fixtures/states.sh` builds each state in a temporary repository using `tests/lib.sh` and the
real `dogen.py`, and records its output. `record_states.py` folds that output into
`cases/decision/states.json`, and the gate re-records it. A change in the tool's output
therefore turns the gate red; lane B never replays stale bytes. A handful of refusals that
cannot be reached without breaking a repository are written inline in their cases, using
`dogen.py`'s own wording.

After the history, the model acts in a **real copy of the recorded state**. The recorder keeps a
snapshot of its temp repository at each state, with the skills installed and the history's writes
applied. Snapshots are built once per input digest into the gitignored `.cache/`.

Looking costs nothing and does not end the episode. It runs for real in that copy:
- reading, globbing and grepping;
- read-only `dogen` calls;
- inspection commands, including chains joined by `&&`, `;` or `|`;
- a `python3 -c` script that names nothing able to write, delete, spawn a process, reach the
  network or run code it builds, and only inside the jail;
- staging-directory setup and waiting.

The command list is short and strict: nothing may be redirected into a file, and command
substitution, `-exec` and `-delete` are refused. A command list cannot stop a path from
leaving the sandbox, so every looking command runs inside a bubblewrap jail. The copy is mounted
at a real `/srv/toyq`, with `/usr` read-only, a `dogen` shim on `/opt/dogen` and an empty
`/tmp`. The jail has its own process table and no network. Nothing else of the machine running
the eval exists in there: not its home, not this checkout. The environment is built from scratch
rather than inherited: that `PATH`, a throwaway `HOME`, and git config switched off, so no key
or setting reaches a command. A live lane B run needs `bwrap`, and without one it refuses to
start; only the self-tests' fixed commands may run on the host. A command the history wrote
rather than recorded answers as the history says.

Grading sees the action, not its wrapping. A leading `cd /srv/toyq &&` and trailing looking
parts such as `; echo "exit:$?"` are dropped before a pattern matches what a command *is*. A
"no such call" check still reads the whole command, so nothing forbidden hides in a tail.

The first consequential action ends the episode, is never carried out, and is what the case
grades:
- a `dogen` verb that records something;
- any other command;
- a write;
- a question to the author;
- a turn with no tool call.

Every case carries two replies:
- an `oracle`: a correct run, which must pass;
- a `foil`: a plausible wrong run, which must fail.

Both are enforced offline, so an assertion that would pass anything cannot land.

## Running

```bash
python3 validation/evals/run.py A --roster --dry-run          # offline: oracles through a stub, no key, no cost
python3 validation/evals/run.py A --model z-ai/glm-5.3        # one paid lane on the gate model
python3 validation/evals/run.py all --roster                  # the full sweep, capped by models.json
```

`--filter <regex>` narrows by case id, `--jobs N` sets how many cases run at once, and
`--no-cache` bypasses the response cache.

`--repeat K` runs each lane K times per model, and always bypasses the cache. The backends are
not deterministic even at temperature 0, so one run cannot tell a one-point change from noise.
The K-run summary reports each case as passes out of K. A case at K/K or 0/K is settled; one in
between is flaky, and that's where a change to a skill has to be measured.

The exit codes are those of every checker in this repository:
- `0`: every case passed.
- `1`: at least one case failed.
- `2`: run-level error. That covers an API error, an empty or looping answer, a judge that could
  not answer, a reached budget, or nothing having run. Treat `2` as "no result", never as a low
  score.

## Where results go

A clean, complete, paid run writes a slim summary to `results/<date>-<lane>-<model>.json`. It
never overwrites: a second run on the same day gets `-2`. Those files are committed.

Everything else goes to the gitignored `results/raw/`, with the reason in the file name: `dry`,
`partial` (a `--filter`), `errored` (an error or a budget stop), or `regrade` (every answer came
from the cache). That keeps a partial run from
ever standing in for a baseline. Each run also leaves the full turns of every case in
`results/raw/*.turns.jsonl`.

With `--repeat K`, each run goes to `results/raw/` as `…-runIofK.json`, and the per-case pass
counts go to `results/<date>-<lane>-<model>-kK.json`, under the same rules.

Baselines are per (candidate, judge) pair. When the judge changes, add a new row; don't edit the
old one.

## The roster and the spend cap

`models.json` holds the candidates, the gate model, the pinned judge and the simulated author.
Every model is pinned to one backend (`provider.order` plus `allow_fallbacks: false`), so the
score belongs to one model on one backend. Every pin also sends `zdr: true`, so only Zero Data
Retention endpoints serve these requests; the list of compliant endpoints is at
`https://openrouter.ai/api/v1/endpoints/zdr`. The judge and the author are never candidates.

A backend can serve a model badly. On `novita/fp8`, minimax-m3's first answer token landed in
the reasoning trace (`…draft it now.dogen`), leaving `-write` as the answer. So before pinning
a backend, probe it once with `reasoning.exclude` off and read the end of the reasoning.

Before a model's cases run, one tiny call checks that it can be reached on its pin. A model that
cannot be reached is skipped with one line, rather than failing every case with the same
error.

`caps.sweep_usd` caps a whole invocation. `caps.per_model_usd` caps each model, the judge
included, and scales with `--repeat`. The cap is checked before every paid call. With
`--jobs N`, the overshoot is at most the `N - 1` calls already in flight.

## Adding a case

Each case must be answerable from what its lane shows the model. For Lane A that is the five
descriptions and nothing else.

Every case has an oracle, a known-good reply. `tests/test_evals.py` asserts that each case's
oracle passes its own assertions. It also asserts that every other skill fails a Lane A case,
and that every Lane B case's `foil` fails. So a broken or vacuous expectation turns the gate red,
not a model's score.

When the tool's output changes, re-record the states with
`python3 validation/evals/record_states.py` and review the diff to `states.json`. Do this before
touching any case.

Prefer the deterministic kinds:
- `skill_choice`, `tool_call`, `no_tool_call`, `text_re`, `not_text_re` and `not_prescribed`;
- for an episode: `decisive`, `asks_user`, `bash_sequence` and `before`;
- `any_of`, for when more than one action is right. Use `judge` only for a judgement call a regex cannot make.
`not_prescribed` forbids *telling* the user to run a command or running it; mentioning the
command in a warning is not a failure.

## Feedback for a later optimiser

Every assertion returns `{pass, score, feedback}`, where `feedback` names what was expected and
what was seen. That pair is the evaluator shape a reflective text optimiser such as GEPA needs,
so evolving a skill's prose against Lane B later needs no change to this kit.
