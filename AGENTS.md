# AGENTS.md — operating contract for coding agents

Harness-neutral operating contract for any AI coding agent working in this repository
(read by Copilot, Codex, Cursor, and others; Claude Code reads it too). Read it before you
touch anything.

[`docs/contract.md`](docs/contract.md), frozen at the git tag `contract-v1`, is the normative
document. Where it and this file disagree, the contract wins.

## The gate

Every command below must be green before a commit lands. This is the gate **in full** — there
is no shorter version, and a claim of completeness that omits one of these is the failure mode
the list exists against.

```bash
python3 -m unittest tests.test_dogen_unit        # the unit suite
python3 tests/test_dogen_unit.py                 # the SAME suite, script form
python3 -m unittest tests.test_skill_text        # the skill-text contracts
python3 -m unittest tests.test_planning_lint     # the anonymization lint's own tests
python3 -m unittest tests.test_check_docs        # the docs-accuracy checker's own tests
bash tests/test_dogen_lifecycle.sh               # the lifecycle / recovery suite
bash tests/test_dogen_acceptance.sh              # the acceptance suite
bash tests/install_smoke.sh                      # the stranger's install path, end to end
bash validation/fixtures.sh                      # the validation kit's four corruption fixtures
python3 scripts/skill_lint.py                    # the SKILL.md frontmatter gate
python3 tests/check_traces.py                    # the trace-table checker
python3 tests/check_docs.py                      # the docs-accuracy checker
python3 scripts/planning_lint.py                 # the anonymization gate over .planning/
python3 tests/size_guard.py                      # VERB-09's line budget, reported and enforced
```

Set `GIT_CONFIG_GLOBAL=/dev/null` for any fixture that shells out to git.

Both invocation forms of the unit suite are listed on purpose: they reported different counts
once (CR-06), and a suite that is whole under one runner and truncated under the other reports
`OK` either way.

`bash tests/install_smoke.sh` is the only command here that reaches `dogen` through `PATH`
rather than through the in-tree file, and the only one that executes `README.md`'s marked
`QUICKSTART` region as written. It is what keeps the documented install from rotting.

This list is pinned by `tests/test_dogen_unit.py`'s `GATE_COMMANDS` tuple: every string above
appears there verbatim, every `tests/test_*.py` module in the tree appears in it, and no command
in it may name a `tests/`, `scripts/` or `validation/` path that does not exist. Change one side
and the suite goes red until the other catches up.

`bash validation/fixtures.sh` proves what nothing else in the gate does: that each of the four
named corruptions — a bypassed signoff gate, a tampered ledger line, an unsteered redraft, an
unresolved pending request — is reachable from a valid unit built by the real verbs, and that the
kit's oracle catches it independently of the tool's own suites.

`tests/run_matrix.sh` is a local convenience on top of the gate, not part of it: it runs the
unit suite on 3.9 / 3.12 / 3.13 through a local interpreter fetcher. CI gets its interpreters
from the runner's tool cache instead.

The bash suites, the install smoke and the validation kit are kept clean at
`shellcheck -S warning tests/*.sh validation/*.sh` — that exact command, with that exact file
scope, is what CI's `shellcheck` job runs, so the two cannot drift in scope even where they drift
in version. CI runs the runner image's preinstalled shellcheck 0.9.0; a developer machine is
likely newer, so reproduce any CI-only finding against 0.9.0 before changing code — and the
mirror image holds too, so reproduce a local-only finding against 0.9.0 before changing code
for it.

## Non-negotiables

- **The deterministic tool is the gate.** dogen's guarantees live in code, not in skill prose
  and not in the model's discretion. Never weaken a check in exchange for a "nicer" skill
  prompt. The gate is the single stdlib-only `dogen` file at the repo root — one executable,
  one verb per transition — whose behaviour is fixed by [`docs/contract.md`](docs/contract.md).
- **No substantial draft without a recorded human signoff.** `dogen signoff` is the gate verb:
  it freezes `sha256(unit.md)` as the plan hash, and `draft` refuses — with no side effects —
  until a signoff is on record and that hash is still current. The gate is code-enforced; never
  move it into the model's discretion.
- **dogen drafts and stops.** Each transition is one local git commit, staging only `.dogen/`
  and `docs/` and carrying `Dogen-*` trailers. The tool never pushes, opens or reviews pull
  requests, builds, or publishes. The reviewer/merger owns the shipped output.
- **The ledger is the provenance.** The record of truth is `.dogen/units/<id>/ledger.jsonl`:
  hash-chained JSONL, append-only, one canonical line per event, each line's `prev` the sha256
  of the previous line's bytes (contract §5.2). Never invent a second record of truth: state is
  *derived* by reading the ledger, and nothing is stored.
- **Skills are the surface; the tool is the tool layer.** Technical Authors drive the
  `dogen-plan` / `dogen-write` / `dogen-review` skills; those skills invoke the deterministic
  tool via `Bash`. `dogen-write` is the sole writer, and that is enforced by a fail-closed
  allowlist in `scripts/skill_lint.py` — a skill may `Write` only its own staging files, never
  the canonical `docs/` page, never the ledger.

---

## Project

**dogen — a documentation-drafting tool for Technical Authors.**

dogen drafts review-ready, **Sphinx-publishable** documentation (MyST Markdown or
reStructuredText, Diátaxis-structured) from human-pointed sources — human-in-the-loop — and
deliberately stops at the boundary of a single traceable local commit.

**Core value:** a Technical Author points dogen at sources for one documentation unit, steers it
on intent and audience, and gets a review-ready, Sphinx-publishable draft — produced through a
*provable* human-in-the-loop loop, with steering and provenance recorded on disk. If everything
else fails, this loop must work: declare → steer → draft → review, no substantial draft without
a recorded human signoff.

### The shape

One stdlib-only Python executable at the repo root. Python 3.9 floor, no package, no venv, no
dependencies, no third-party test runner. Behaviour is fixed by
[`docs/contract.md`](docs/contract.md); the human-facing surface is three portable Agent Skills.
For what changed from the previous release, read [`docs/upgrade.md`](docs/upgrade.md) rather
than reconstructing the history from this file.

### Constraints

- **Stdlib-only.** No third-party dependency anywhere in the product tree, enforced by the
  suite. `scripts/skill_lint.py` and `scripts/planning_lint.py` are standalone stdlib-only lint
  utilities, not a second core.
- **Surface**: portable Agent Skills (`SKILL.md`) to the **agentskills.io** spec, split into
  `dogen-plan` / `dogen-write` / `dogen-review`; validated on Claude Code and Copilot CLI.
- **Licensing**: the tool is LGPL-3.0-only (root [`LICENSE`](LICENSE)); the skills are
  Apache-2.0 ([`skills/LICENSE`](skills/LICENSE)).
- **Agnosticism**: platform-agnostic — any harness that reads `SKILL.md` and exposes `Bash` +
  `Write` works; proven on one stack (GitHub + Read the Docs + Sphinx) this cycle.
- **Output**: Sphinx-publishable MyST Markdown (or rST where siblings are rST),
  Diátaxis-structured.
- **HITL / provenance**: no substantial draft without a recorded signoff; provenance is internal
  observability, not a published "AI-generated" disclaimer.
- **UX**: "if it's easier to circumvent than to use, it will be circumvented."

## The tree

```
dogen                              ← the gate: one stdlib-only Python file (contract-v1)
README.md                          ← the reader's entry point; carries the marked QUICKSTART,
                                     VERBS, REASONS, COMPAT and CLAIMS regions
AGENTS.md                          ← this file: the gate, the rules, the tree
CHANGELOG.md                       ← the release record
LICENSE                            ← LGPL-3.0-only, the tool
.github/workflows/ci.yml           ← the CI graph; each job body is a literal local command

docs/
├── contract.md                    ← NORMATIVE. Frozen at tag `contract-v1`
├── upgrade.md                     ← behaviour changes from the previous release
└── sessions/
    ├── TEMPLATE.md                ← the fixed shape an authoring-session record must fill
    ├── NOTES-2026-09.md           ← cross-session notes
    ├── 2026-09-14-early.md        ← recorded authoring session (early leg)
    ├── 2026-09-15-full.md         ← recorded authoring session (full leg)
    ├── 2026-09-17-reference-leg.md
    │                              ← validation leg, reference arm (codex-cli / gpt-5.6-luna)
    ├── 2026-09-17-reference-leg-claude-code.md
    │                              ← the same leg re-run on claude-code / claude-sonnet-5
    └── 2026-09-17-actionable-leg.md
                                   ← validation leg, actionable arm (codex-cli / gpt-5.6-luna)

skills/                            ← the human-facing surface
├── README.md                      ← verb table, routing table (the authoring site), install
├── LICENSE                        ← Apache-2.0, the skills only
├── dogen-plan/
│   ├── SKILL.md                   ← declare + HITL signoff; Socratic intake, routes on Diátaxis
│   └── references/                ← actionable-intake.md, explanation-intake.md,
│                                     reference-intake.md, routing.md, socratic-technique.md
├── dogen-write/
│   ├── SKILL.md                   ← the SOLE writer: drafts from sources or from a step walk
│   └── references/                ← episode-taxonomy.md, explanation-stance.md,
│                                     how-to-stance.md, reference-stance.md, routing.md,
│                                     tutorial-stance.md, walk-protocol.md,
│                                     writing-standards.md
└── dogen-review/
    ├── SKILL.md                   ← review + record the verdict (accept/fix/redraft)
    └── references/                ← provenance-summary.md, review-rubric.md, routing.md

scripts/
├── skill_lint.py                  ← SKILL.md frontmatter + writer-allowlist gate
└── planning_lint.py               ← the anonymization gate over .planning/

validation/                        ← the validation kit: the evidence apparatus, not the tool
├── score.py                       ← the rubric scorer over a leg's drafts
├── fixtures.sh                    ← V-01…V-04: four corruptions built from real verbs, and the
│                                     oracle that catches each one
├── runmeta.sh                     ← records a leg's RUN metadata alongside its drafts
├── rubric.md                      ← the scoring bar a leg's drafts are read against
└── legs/                          ← the pre-registered per-leg checklists and their RUN files

tests/
├── test_dogen_unit.py             ← the unit suite; also the home of the line budget, of the
│                                     GATE_COMMANDS tuple and of the pin over this listing
├── test_skill_text.py             ← the skill-text contracts and the routing-mirror equality
├── test_planning_lint.py          ← the anonymization lint's own tests
├── test_check_docs.py             ← the docs-accuracy checker's own tests
├── test_dogen_lifecycle.sh        ← the lifecycle / recovery suite (hermetic temp git repos)
├── test_dogen_acceptance.sh       ← the acceptance suite, A-01 … A-35
├── lib.sh                         ← the fixtures both bash suites share; ONE definition site
├── install_smoke.sh               ← CI-02 / A-37: install from PATH, run README's QUICKSTART
├── check_traces.py                ← the contract trace-table checker
├── check_docs.py                  ← the docs-accuracy checker: links, verbs, reasons, compat
│                                     and claims, across the nine documents it names
├── size_guard.py                  ← VERB-09's line budget over `dogen`, reported and enforced
└── run_matrix.sh                  ← local-only: the unit suite on 3.9 / 3.12 / 3.13
```

Two tracked files are deliberately absent from this listing because they are not part of
the release tree: `docs/before-after.md`, a narrative of the v1.x → v2.0 shape change written
against the bash layer phase 17 deleted, and `project-timeline.html`. Nothing links to either.

The listing is not decoration. `tests/test_dogen_unit.py` pins the `docs/`, `scripts/`,
`tests/` and `validation/` sections against the real tree in both directions — a file that
ships and is not listed goes red, and so does a listed name that does not exist — with the
two exclusions above named in its `UNSHIPPED_PATHS` tuple rather than merely omitted. The
`skills/` section and the root block are outside that pin on purpose: `skills/*/references/`
contents are summarised inside the `←` comment rather than listed one per line.

### Verbs, exit codes and refusals

Not restated here. The verb table and the reason/exit table each live in exactly one
reader-facing place — [`README.md`](README.md)'s `VERBS` and `REASONS` marked regions — and in
exactly one normative place, [`docs/contract.md`](docs/contract.md) §6 and §5.7. The
authoritative machine list is the `REASONS` dict inside `dogen`.

What an agent needs to know about them here: every non-zero exit prints **exactly one JSON
line** with the five keys `error` / `unit` / `detail` / `hint` / `next` (stderr; stdout under
`--json`). Branch on `error`, never on the exit code — several reasons share one. And
`git log --grep 'Dogen-Unit: <id>'` replays a unit's whole path.

## Conventions

- **Markup**: new drafted pages default to MyST Markdown (`colon_fence`); use rST when a page's
  siblings are already rST — the target extension *is* the format (`.md` → MyST, `.rst` → rST).
- **Diátaxis**: one direction per page (tutorial / how-to / reference / explanation); the
  direction is a declared field (`intent`) that routes the draft-stage skill.
- **Ledger**: append-only, and hash-chained. **No line is ever edited — including a step's
  status** — because editing one line invalidates every `prev` after it. A step's resolution is
  a new appended event, never an edit to the event that planned it. Never hand-edit the file.
- **Commit seam**: the tool owns its commits. Never run a competing `git add -A` or `git commit`
  in a skill for a gated transition.
- **Single definition site**: a fixture, a routing row or a threshold has one home and is
  mirrored mechanically, never copied by hand. A second copy is the drift the rule exists to
  prevent.
