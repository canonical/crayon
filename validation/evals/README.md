# Model evals

Dev-time evaluation material, like the rest of `validation/`. This kit measures how well a model,
driving the five crayon skills, does what the skills say. It does not re-test the tool itself: the
gate already covers that.

The same skill text and the same neutral loop are given to every model, so a score difference
belongs to the model. No agent harness sits in between:

- The system prompt carries the skill catalog: each skill's name, description and install
  location.
- `/crayon-<skill> <args>` appends that skill's `SKILL.md` body to the turn.
- The model reads reference files itself.

Everything is stdlib Python. Models are reached through OpenRouter with the key in
`OPENROUTER_API_KEY`.

## Lanes

| Lane | What it asks | Live turns | Graded by | Status |
|---|---|---|---|---|
| A | which skill handles this ask? | 1, no tools | exact skill name | built, 15 cases |
| B | given this `crayon` output, what is the next action? | until the first consequential action | that action, the calls on the way, 4 judged | built, 77 cases |
| C | a whole journey in a real sandbox with a simulated author | many | ledger, `score.py audit`, transcript, 1 judged page | planned |

## How lane B works

A case invokes one skill (`/crayon-review cfg`) and replays a history: the tool calls a model
made and what `crayon` printed back. Those outputs are never typed by hand.
`fixtures/states.sh` builds each state in a temporary repository using `tests/lib.sh` and the
real `crayon.py`, and records its output. `record_states.py` folds that output into
`cases/decision/states.json`, and the gate re-records it. A change in the tool's output
therefore turns the gate red; lane B never replays stale bytes. A handful of refusals that
cannot be reached without breaking a repository are written inline in their cases, using
`crayon.py`'s own wording.
The fixture copies tracked toyq and skill files from the working tree, not ignored or untracked
files such as local Python bytecode, so the temporary Git commits are reproducible in CI.

A case may also carry a `prelude`: steps replayed before the skill is invoked, for what happened
earlier in the same conversation, such as a write session before a review. A prelude holds
recorded refs, user turns and assistant turns only, and `lanes.load_b` refuses anything else: a
written command, a `Write` or any other tool call belongs in history, because the sandbox is
already the recorded state after the prelude ran. A user turn that invokes a skill
(`/crayon-write cfg`) reaches the model expanded with that skill's body, the same as the
invocation, and a turn that names no installed skill is refused. Its replayed calls are numbered
`p0`, `p1`, … and the history's `h0`, `h1`, …, so the two never collide.

After the history, the model acts in a **real copy of the recorded state**. The recorder keeps a
snapshot of its temp repository at each state, with the skills installed and the history's writes
applied. Snapshots are built once per input digest into the gitignored `.cache/`.

Looking costs nothing and does not end the episode. It runs for real in that copy:
- reading, globbing and grepping;
- read-only `crayon` calls;
- inspection commands, including chains joined by `&&`, `;` or `|`;
- a `python3 -c` script that names nothing able to write, delete, spawn a process, reach the
  network or run code it builds, and only inside the jail;
- staging-directory setup and waiting.

The command list is short and strict: nothing may be redirected into a file, and command
substitution, `-exec` and `-delete` are refused. A command list cannot stop a path from
leaving the sandbox, so every looking command runs inside a bubblewrap jail. The copy is mounted
at a real `/srv/toyq`, with `/usr` read-only, a `crayon` shim on `/opt/crayon` and an empty
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
- a `crayon` verb that records something;
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
the reasoning trace (`…draft it now.crayon`), leaving `-write` as the answer. So before pinning
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
not a model's score. In one conversation (the same skill, ask, sandbox, prelude and history),
every case's oracle passes every other case's assertions, so no reply is both an oracle and a
foil there; a foil need not fail its siblings. A known-good reply that quotes recorded output with
`@RECORDED{…}` puts it in a fenced block, while a success response line, which carries no sha,
is typed. `tests/test_evals.py` checks both.

When the tool's output changes, re-record the states with
`python3 validation/evals/record_states.py` and review the diff to `states.json`. Do this before
touching any case.

A skill edit moves every recorded commit sha too, because the fixture repository commits the
installed skills first. So re-record in the same commit as the skill edit. Never type a commit
sha into an oracle's assertions, a judge rubric or a judge context; describe the line instead
(`record: intact at <seven-character commit>`), or match any seven hex characters. A reply
that quotes what the tool printed splices it in with `@RECORDED{<state>/<label>}`, which
`lanes.py` replaces with that recorded output when it loads the case. The same ref works inside
history and prelude steps: in a reply, a user turn, a call's arguments or its result. A `file:`
label keeps the recorded bytes exactly, trailing newline included; any other label drops the
trailing newline.

Prefer the deterministic kinds:
- `skill_choice`, `tool_call`, `no_tool_call`, `text_re`, `not_text_re` and `not_prescribed`;
- for an episode: `decisive`, `asks_user`, `question_count`, `bash_sequence` and `before`.
  `question_count` bounds how many questions the decisive reply asks, with an inclusive `min`
  and `max`, counting a question tool's questions or the reply's question marks outside code;
- `any_of`, for when more than one action is right. Use `judge` only for a judgement call a regex cannot make.

`plain_words` is always on in Lane B and is never listed in a case: `lanes.load_b` appends it to
every case, and a case that lists it is refused. It reads what the agent says to the author, the
prose outside code, and fails on a record word in exactly these forms, as whole words in any
case: seal, seals, sealed; basis; seq, seqs; `plan_hash` or plan hash; hash, hashes; sha256 or
sha-256; digest, digests; event N; and ledger line N. "Sealing" and a page's "line 13" pass. An
English idiom such as "on a daily basis" fails too, because the plain-words rule tells the model
to avoid these words even as an idiom. Tool output a skill shows verbatim belongs in a fenced
code block, opened and closed with three backticks or three tildes, where the check does not read
it. An indented block is not a fence: the check reads it as prose.

`not_prescribed` forbids *telling* the user to run a command or running it; mentioning the
command in a warning is not a failure. `not_text_re` takes an optional `except_re`: a line
that matches it is not read, so a mechanical choice's marked default (`Resume at step 1
(default)`) can sit beside a judgment question the check still reads.

A Lane B pattern can name a macro from `lanes.MACROS`, so the same rule reads the same in every
case. `TestMacros` in `tests/test_evals.py` proves the last four in both directions, on text
that must match and text that must not:
- `@MUTATING`: a `crayon` verb that records anything (`resume --dry-run` only looks);
- `@PUBLISH`: a git write, a build or a pull request, never the skill's to run;
- `@MARKER`: a recommended or default marker on a judgment option, such as `(Recommended)`,
  `(default)` or a star; the order of the options alone is not a marker;
- `@OFFERS_PUBLISH`: publishing, a pull request or opening a PR, offered as a step
  (`Next: publish`, `the publish is yours`); naming it, as in `crayon does not publish`
  or quoting the routed token, is not an offer;
- `@OFFERS_NOTE`: note text the agent offers in the author's place (`I'll record: …`,
  `Proposed note: …`); a colon that introduces a question is asking, not offering;
- `@HEDGE`: a blanket disclaimer or reminder to check (`Please double-check …`,
  `may contain errors`, `I can't verify everything`, `I cannot verify all of it`,
  `This could be wrong`); a grounded first-person line that names its command, source,
  setting or inference (`I couldn't verify the details of log_level: …`) is not one, and
  neither is a finding that says a cited claim may be wrong.

## Feedback for a later optimiser

Every assertion returns `{pass, score, feedback}`, where `feedback` names what was expected and
what was seen. That pair is the evaluator shape a reflective text optimiser such as GEPA needs,
so evolving a skill's prose against Lane B later needs no change to this kit.
