# Developing crayon

<!-- provenance: moved from README.md (Develop crayon itself) and AGENTS.md (The gate), expanded -->

The tooling, the test suites and the checks that verify the tree, for someone changing crayon
rather than using it. The operating rules are in [[architecture]] and [[conventions]], and the behaviour of the
tool is fixed by [[contract]], frozen at the git tag `contract-v1`. This page explains what
each command in the gate proves and how the pieces pin one another, so that a red run names the
thing that moved.

## The shape

One stdlib-only Python file, `crayon.py`, at the repository root, installed as `crayon`: Python 3.9 syntax, no package, no
venv, no dependency, no third-party test runner. One verb per transition over a hash-chained
JSONL ledger. Five portable Agent Skills under `skills/` are the human-facing surface; two
stdlib-only lint utilities under `scripts/` and a validation kit under `validation/` are the
apparatus around it. Nothing in the product tree imports anything outside the standard library,
and the unit suite asserts it.

## The gate

Every command below must be green before a commit lands. The list is pinned three ways: the
`GATE_COMMANDS` tuple in `tests/test_crayon_unit.py` must equal it string for string, every
command must appear in `AGENTS.md` and in this page, and every `run:` body in
`.github/workflows/ci.yml` must be one of them.

```bash
python3 -m unittest tests.test_crayon_unit       # the unit suite
python3 tests/test_crayon_unit.py                # the SAME suite, script form
python3 -m unittest tests.test_skill_text        # the skill-text contracts
python3 -m unittest tests.test_planning_lint     # the anonymization lint's own tests
python3 -m unittest tests.test_check_docs        # the docs-accuracy checker's own tests
bash tests/test_crayon_lifecycle.sh              # the lifecycle / recovery suite
bash tests/test_crayon_acceptance.sh             # the acceptance suite
bash tests/install_smoke.sh                      # the stranger's install path, end to end
bash validation/fixtures.sh                      # the validation kit's four corruption fixtures
python3 scripts/skill_lint.py                    # the SKILL.md frontmatter gate
python3 tests/check_traces.py                    # the trace-table checker
python3 tests/check_docs.py                      # the docs-accuracy checker
python3 scripts/planning_lint.py                 # the anonymization gate over .planning/
python3 tests/size_guard.py                      # VERB-09's line budget, reported and enforced
python3 -m unittest tests.test_wiki_lint         # the wiki lint's own tests
python3 scripts/wiki_lint.py                     # the docs/ wiki and AGENTS.md shape
python3 -m unittest tests.test_evals             # the model-eval kit's offline self-tests
```

Set `GIT_CONFIG_GLOBAL=/dev/null` for anything that shells out to git, so a developer's global
identity or hooks can never mask a missing step in a fixture. Alongside the gate, and pinned to
CI the same way, the shell files are kept clean with:

```bash
shellcheck -S warning install.sh tests/*.sh validation/*.sh
```

See [[shellcheck]] for the version policy.

### One exit contract for every checker

Every script that checks something — the two lints, the three checkers, the install smoke, the
bash harness, the validation kit — answers with the same three codes:

| Exit | Meaning |
|---|---|
| `0` | clean: everything it looked for was checked and agreed |
| `1` | violation: at least one named disagreement, one line each |
| `2` | nothing was checked: the input it scans was absent or reshaped |

The `2` arm is the vacuous-pass guard, and it is the reason the gate can be trusted: a checker
whose region was renamed, whose table was reshaped or whose suite discovered no tests reports
`2`, never a clean run. Each observable in a checker carries its own `2`, so a reshaped table
cannot ride to green on the links that did parse.

## The suites

**`tests/test_crayon_unit.py`** — the unit suite, run twice on purpose. `python3 -m unittest`
and the script form once reported different counts, and a suite whole under one runner and
truncated under the other reports `OK` either way. Beyond the tool's own units it is the home
of the repository's self-pins: the gate tuple, the tree block in `AGENTS.md` (pinned against
the real `docs/`, `scripts/`, `tests/` and `validation/` in both directions), the CI mirror,
the line budget's two thresholds, the Python 3.9 hazard scan and the no-dependency assertion.

**`tests/test_skill_text.py`** — the skill-text contracts: the routing table authored once in
`skills/README.md` between its sentinels is byte-identical in every skill's
`references/routing.md`; every reason and every `next` token has exactly one row; the
author-rules block, the three rules authored once in `skills/README.md` between the
`author-rules` sentinels, is carried byte for byte in the plan, write and review SKILL.md
bodies (S-15); the manual install lines in [[install]] create the directory they copy into.

**`tests/test_crayon_lifecycle.sh`** — the N-series: lifecycle walks, negative paths, recovery
situations and the contract's trace table, each test driving the real executable in a hermetic
temporary git repository. It is the long pole at roughly three minutes.

**`tests/test_crayon_acceptance.sh`** — A-01 … A-38: the black-box acceptance suite ported by
intent from the v1 bash layer, the tests that cannot live in the N file, and A-38, the `context`
verbs driven end to end through the executable.

Both bash suites source `tests/lib.sh`, the one definition site for the temp-repo fixture, the
assertion set, the hook fixtures, the step-evidence helpers (`last_plan_seq`, `record_step` and
`skip_step`), the vacuous-test guard and the TAP runner; `validation/evals/fixtures/states.sh`
sources the same file. Never add a second copy of any of those.

**`tests/install_smoke.sh`** — the only test that reaches `crayon` through `PATH` rather than the
in-tree file. It extracts the fenced shell between the `INSTALL:BEGIN` / `INSTALL:END` markers in
[[install]] byte for byte, runs it from a temporary `HOME` in a temporary
repository, then drives one unit to a written page and one refusal from that vantage point. It
is what keeps the documented install from rotting.

**`validation/fixtures.sh`** — V-01 … V-04: a bypassed signoff gate, a tampered ledger line, an
unsteered redraft and an unresolved pending request, each reached from a valid unit built by the
real verbs and each caught by `validation/score.py audit`, an oracle that shares no code with the
tool. The kit is evidence apparatus, not product code; it reports as its own CI job.

`validation/audit-docpr-3005.md` reconstructs four public dogfood ledgers and separates
enforced transition gates from audit-only findings and self-reported provenance. Run
`score.py audit <unit> --root <checkout>` only against a trusted checkout path: the scorer
confines ledger reads to that root, but local Git history, model names and reviewer identity
are not independently authenticated. A `FLAG [report]` for declared gaps or a source changed
since signoff is informational; inspect the gating checks and exit code before claiming a pass.

`validation/closeout-docpr-3008.md` consolidates the slim-cycle disposition,
the release delivery that actually occurred, the landed hardening evidence and
the known limitations. Its Jira snapshot is dated: read any non-terminal item
as a stop condition, not as evidence that the portfolio has already closed.

**`validation/runmeta.sh`** records a dogfood leg's before/after Sphinx builds and provenance
in the candidate repository. Before an external harness reads a candidate, check its repository
visibility without authentication: an authenticated clone is not evidence that its contents are
public. Stop if a source is internal or private, even if it is already checked out locally.
For a harness without an automatic transcript resolver, including Copilot CLI, capture its session
transcript to a local file and pass
`--transcript-file <path>` to `runmeta.sh end`. The script refuses a missing file and records its
resolved path, but intentionally leaves `transcript.sha256` null: compute and fill that digest
*outside* the measured session after the last interaction. Do not commit private transcripts or
mistake a captured final answer for a complete session transcript.
The writer's `--report` JSON uses `origins` and `gaps` as arrays of plain strings; unknown keys
and structured entries are refused as `bad_draft_path` rather than recorded as stringified
objects or silently dropped. Each `origins` string must be a repository-relative path to a
readable file, without a revision suffix. The validation scorer flags paths it cannot read
instead of passing a comparison of two digests over absent files. Record external source
revisions in the unit or context provenance and disclose what the local-file comparison
cannot cover.

**`tests/test_evals.py`** — the offline half of the model evals under `validation/evals/`. The
evals measure a model driving the skills, not the tool: every model gets the same skill text
through the same neutral loop, and OpenRouter serves each one. Paid runs are started by hand
with `OPENROUTER_API_KEY` set, and never run in the gate or in CI. What this module holds the
kit to is everything that needs no model:
- the transport's request shape, retries, cache and spend cap, against a fake opener;
- every assertion kind, against hand-built turns;
- every case file, against its own known-good reply;
- the rule that no prompt or kit file names an agent harness.

[[evals]] explains what the evals measure and how to read their results;
`validation/evals/README.md` says how to run a lane, where results land and how to add a case.

## The checkers and lints

**`tests/check_docs.py`** — the docs-accuracy checker. It compares observables, never judges
prose: the `VERBS` region (in `docs/internals.md`, exactly once in the documented set) against
`crayon --help`'s subcommand list; the compact `REASONS` table (likewise) and the reason table in
`docs/contract.md` §5.7 against the tool's `REASONS` dict, name and exit code; the `COMPAT`
region (exactly once) and contract §5.10 against the two numbers the tool reports; every
in-repo link and anchor across the documented set; no `crayon <verb>` in the reader-facing
documents outside a `## Under the hood` section; the changelog's topmost release heading, which
must be dated and carry no placeholder. It calls `check_traces.py` itself.

**`tests/check_traces.py`** — every row of the contract's trace table and every Mechanisms row
that names a suite file must have a test whose function name carries the row's id. It says a
test exists, and nothing about what the test asserts.

**`scripts/skill_lint.py`** — agentskills.io frontmatter invariants for each `SKILL.md`: the
name matches the directory, the description parses, the compatibility numbers are the contract's
as literal strings, and only `crayon-write` may hold a write-capable tool. The single-writer rule
is fail-closed.

**`scripts/planning_lint.py`** — no unscrubbed prior-art identity in `.planning/`. A missing
planning tree is a clean scan; on a release branch it checks nothing and says so.

**`scripts/wiki_lint.py`** — the shape of the `docs/` wiki and its entry point `AGENTS.md`:
every bracketed link resolves, every page is reachable from `AGENTS.md`, slugs are unique, pages
start with an H1, carry a provenance comment and end with a `Related:` line, the bracket
notation appears nowhere outside the wiki, and every `docs/<slug>.md` path cited from outside
exists. The live tree is its fixture; `tests/test_wiki_lint.py` mutates a two-page tree once
per check.

**`tests/size_guard.py`** — VERB-09's line budget over `crayon`, a review trigger rather than a
design goal. Above the reporting threshold it reports and stays green; at the failing threshold
it fails. It loads both thresholds and the comparison out of the unit suite, so the CI job and
the local guard are the same code.

## What pins what

| This | is pinned to | by |
|---|---|---|
| `GATE_COMMANDS` | `AGENTS.md`, this page, `ci.yml` `run:` bodies, every `tests/test_*.py` | the unit suite |
| Bracketed links and the wiki shape | `docs/*.md` and `AGENTS.md` | `wiki_lint.py` |
| `AGENTS.md`'s tree block | the real `docs/`, `scripts/`, `tests/`, `validation/` | the unit suite |
| The routing table | each skill's `references/routing.md` | `test_skill_text.py` |
| The three stance references | `crayon-fetch`'s copies of `crayon-onboard`'s | `test_skill_text.py` |
| The author-rules block | the plan, write and review `SKILL.md` bodies | `test_skill_text.py` |
| The five context artefact names | `docs/context.md`, the plan and onboard skills | the unit suite |
| The verb rows in `docs/internals.md` | `crayon --help` | `check_docs.py` |
| Reader-facing pages name skills, not tool commands | `crayon --help` | `check_docs.py` |
| The two reason tables | `crayon.REASONS` | `check_docs.py` and the unit suite |
| The compatibility numbers | `crayon version --json` | `check_docs.py`, `skill_lint.py`, `install.sh` |
| The install region | an install that reaches a page, then the uninstall it prints | `install_smoke.sh` |
| The manual install lines | `mkdir -p` and `cp -r` name one directory | `test_skill_text.py` |
| The trace table | test function names | `check_traces.py` |

When one side moves, the other goes red until it catches up. That is the intended failure mode;
never make a pin pass by loosening it.

## CI

Eight independent jobs in `.github/workflows/ci.yml`, no `needs:` edge between any two, so every
verdict lands on the checks list at once. Each job body is the literal local command, so a red
check reproduces with one paste. First-party actions only, pinned to commit SHAs. The unit
matrix runs 3.9 / 3.12 / 3.13 from the runner's tool cache; `tests/run_matrix.sh` is the local
equivalent, fetching interpreters with `uv` as a fetcher only — it never installs a package.

## Driving the verbs by hand

The skills are the surface, but every guarantee is in the tool, and the fastest way to reproduce
a report is to drive the verbs directly in a scratch repository:

```bash
mkdir -p /tmp/crayon-try && cd /tmp/crayon-try
git init -q -b main . && git config user.name "Anne Example" && git config user.email "anne@example.com"
printf '.crayon/staging/\n' > .gitignore
printf '# Widget API\n\nCreate and delete widgets.\n' > source.md
mkdir -p docs && printf '# Docs\n' > docs/index.md
git add -A && git commit -q -m "seed"

printf '# Plan\n\nOutline the widget API reference.\n' \
  | crayon unit new widget-api --intent reference \
      --audience "developers integrating the widget API" \
      --title "Widget API" --target reference/widget-api.md \
      --source source.md --body-file -
crayon signoff widget-api
crayon steer widget-api --note "Lead with the create call."
mkdir -p .crayon/staging/widget-api/draft
printf '# Widget API\n\n## create\n\nCreates a widget.\n' > .crayon/staging/widget-api/draft/widget-api.md
crayon draft widget-api .crayon/staging/widget-api/draft/widget-api.md
crayon verify widget-api
crayon show widget-api
```

`steer` is load-bearing: without a steering record since the last generation, `draft` refuses
with `unsteered`. Every refusal is one JSON line with `error`, `unit`, `detail`, `hint` and
`next`; branch on `error`. `git log --grep 'Crayon-Unit: widget-api'` replays the unit's path.

## Changing the documented surface

- A new verb or reason: change `crayon`, then the contract, then the region in
  `docs/internals.md` and the routing table in `skills/README.md`, then re-copy the routing mirrors. `check_docs.py` and
  `test_skill_text.py` name whichever side is behind.
- A new file under `docs/`, `scripts/`, `tests/` or `validation/`: list it in `AGENTS.md`'s tree
  block, or name it in the unit suite's `UNSHIPPED_PATHS` if it is deliberately not released.
- A new test module: add it to `GATE_COMMANDS`, `AGENTS.md`, this page and `ci.yml` together.
- A new page under `docs/`: H1, provenance comment on line 3, `Related:` last line, and a
  bracketed link from `AGENTS.md` or from a page it reaches; the wiki lint names what is missing.
- A new shell file: add it to the shellcheck command in all three places.

Related: [[architecture]], [[conventions]], [[shellcheck]], [[install]], [[evals]].
