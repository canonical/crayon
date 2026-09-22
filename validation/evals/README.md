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
| B | given this `dogen` output, what is the next action? | 1, replayed history | tool-call regex, stop text, 4 judged | planned |
| C | a whole journey in a real sandbox with a simulated author | many | ledger, `score.py audit`, transcript, 1 judged page | planned |

## Running

```bash
python3 validation/evals/run.py A --roster --dry-run          # offline: oracles through a stub, no key, no cost
python3 validation/evals/run.py A --model z-ai/glm-5.3        # one paid lane on the gate model
python3 validation/evals/run.py all --roster                  # the full sweep, capped by models.json
```

`--filter <regex>` narrows by case id, `--jobs N` sets how many cases run at once, and
`--no-cache` bypasses the response cache.

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
`partial` (a `--filter`), or `errored` (an error or a budget stop). That keeps a partial run from
ever standing in for a baseline. Each run also leaves the full turns of every case in
`results/raw/*.turns.jsonl`.

Baselines are per (candidate, judge) pair. When the judge changes, add a new row; don't edit the
old one.

## The roster and the spend cap

`models.json` holds the candidates, the gate model, the pinned judge and the simulated author.
Every model is pinned to one first-party backend (`provider.order` plus
`allow_fallbacks: false`), so the score belongs to one model on one backend. The judge and the
author are never candidates.

`caps.sweep_usd` caps a whole invocation. `caps.per_model_usd` caps each model, the judge
included. The cap is checked before every paid call. With `--jobs N`, the overshoot is at most
the `N - 1` calls already in flight.

## Adding a case

Each case must be answerable from what its lane shows the model. For Lane A that is the five
descriptions and nothing else.

Every case has an oracle, a known-good reply. `tests/test_evals.py` asserts that each case's
oracle passes its own assertions, and that every other skill fails a Lane A case. So a broken
expectation turns the gate red, not a model's score.

Prefer the deterministic kinds (`skill_choice`, `tool_call`, `no_tool_call`, `text_re`,
`not_text_re`, `not_prescribed`). Use `judge` only for a judgement call a regex cannot make.
`not_prescribed` forbids *telling* the user to run a command or running it; mentioning the
command in a warning is not a failure.

## Feedback for a later optimiser

Every assertion returns `{pass, score, feedback}`, where `feedback` names what was expected and
what was seen. That pair is the evaluator shape a reflective text optimiser such as GEPA needs,
so evolving a skill's prose against Lane B later needs no change to this kit.
