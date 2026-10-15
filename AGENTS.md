# crayon — Agent Guide

This file is the entry point for any coding agent working in this repository, and the root of
its wiki. A link written as a slug in double square brackets resolves to the page of that name
under `docs/`, so [[install]] is `docs/install.md`; the notation is
reserved to this file and to `docs/`, has no anchors or aliases, and is checked even inside code
fences. Everywhere else a page is cited by its path. After editing this file or anything under
`docs/`, run `python3 scripts/wiki_lint.py`.

## What this repo is

crayon drafts review-ready, Sphinx-publishable documentation (MyST or rST, Diátaxis-structured)
from human-pointed sources, with a recorded human signoff before any substantial draft, and
stops at one traceable local commit. It is one stdlib-only Python file, `crayon.py`, driven by
five portable Agent Skills. Its behaviour is fixed by [[contract]], frozen at the git tag
`contract-v1`; where the contract and any other document disagree, the contract wins.

## Core rules (always apply)

- The deterministic tool is the gate: guarantees live in `crayon.py`, never in skill prose or the
  model's discretion; never weaken a check for a nicer prompt ([[architecture]]).
- No substantial draft without a recorded signoff; `draft` refuses until `crayon signoff` is on
  record and the plan hash is current ([[contract]]).
- crayon drafts and stops: one local commit per transition, `.crayon/` and `docs/` only, `Crayon-*`
  trailers; it never pushes, builds, publishes or opens pull requests ([[architecture]]).
- The ledger is the record of truth, append-only and hash-chained; no line is ever edited, not
  even a step's status, and state is derived, never stored ([[conventions]]).
- `crayon-write` is the sole writer, enforced by the fail-closed allowlist in
  `scripts/skill_lint.py`; no skill writes the canonical page, the ledger or `.crayon/context/`
  — context artefacts reach disk through `crayon context stage` and `record` ([[context]]).
- The tool owns its commits: never run a competing `git add` or `git commit` for a gated
  transition ([[conventions]]).
- A fixture, a routing row, a threshold or a gate command has one definition site and is
  mirrored mechanically; a hand copy is drift ([[development]]).
- Stdlib only, Python 3.9 syntax, no package, no venv, no third-party runner ([[architecture]]).
- Harness-agnostic: no agent harness is named, detected or preferred on any surface; skills are
  invoked as `/crayon-onboard`, `/crayon-fetch`, `/crayon-plan`, `/crayon-write`, `/crayon-review`
  everywhere ([[install]]).
- Sphinx-oriented, stack-agnostic: the output is Sphinx-publishable, but crayon knows no theme,
  extension, `conf.py` or stack and never builds; house conventions arrive only through
  `.crayon/context/` ([[context]]).
- Formatting hooks are adopted, never fought ([[hooks]]).
- Every non-zero exit is one JSON line with `error`, `unit`, `detail`, `hint`, `next`; branch on
  `error`, never on the exit code ([[architecture]]).

## The gate

Every command below must be green before a commit lands. This is the gate in full; there is no
shorter version, and a claim of completeness that omits one is the failure mode the list exists
against. It is pinned by the `GATE_COMMANDS` tuple in `tests/test_crayon_unit.py`: every string
appears here and in [[development]] verbatim, every `tests/test_*.py` module appears in it, and
every `run:` body in `.github/workflows/ci.yml` is one of them.

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

Set `GIT_CONFIG_GLOBAL=/dev/null` for any fixture that shells out to git. Both invocation forms
of the unit suite are listed on purpose: they reported different counts once. The shell files
are kept clean at `shellcheck -S warning install.sh tests/*.sh validation/*.sh` — that exact
command and scope is CI's `shellcheck` job; the version policy is in [[shellcheck]]. What each
command proves, and what pins what, is in [[development]].

## Skills

Five portable skills under `skills/`, to the agentskills.io spec: `crayon-onboard` (walk the
repository's docs and record the context artefacts through the tool), `crayon-fetch` (the same
from declared external sources, with provenance), `crayon-plan` (declare and sign off),
`crayon-write` (the sole writer; drafts from sources, or from an evidence-gated step walk for
tutorials and how-tos) and `crayon-review` (record the verdict). The family contract and
the routing table are in `skills/README.md`; the table is mirrored byte-identically into each
skill's `references/routing.md`, and `tests/test_skill_text.py` asserts the copies are equal.
Three author rules — notes in the author's words, no marked option on a judgment question, an
explicit go — are authored once in `skills/README.md` between the `author-rules` sentinels and
carried byte for byte in the plan, write and review SKILL.md bodies, and
`tests/test_skill_text.py` (S-15) asserts the copies. A plain-words rule is authored once in
`skills/README.md` between the `plain-words` sentinels and carried byte for byte in all five
SKILL.md bodies, and `tests/test_skill_text.py` (S-20) asserts the copies: what the author
reads says "accepted", "the pages as accepted" and "request N", never a ledger token, and
verbatim tool output sits in a code block. Lane B's always-on `plain_words` check grades every
case for it.

## Topic index

- **Using**: [[contents]] the reader's index of every document . [[install]] by hand or with
  the installer, every choice, uninstall . [[context]] the five context files, who produces
  them, how the tool records them . [[upgrade]] tool, skills, records across releases .
  [[compatibility]] contract number and min_tool . [[hooks]] what a formatting hook leads to
- **Contract**: [[contract]] the normative specification, frozen . [[internals]] the glossary,
  the verb and exit-code tables, branches and the record . [[architecture]] the shape, the
  non-negotiables, the constraints . [[conventions]] markup, ledger, commit seam, documents
- **Developing**: [[development]] gate, suites, checkers, what pins what, driving the verbs by
  hand . [[shellcheck]] the pinned analyzer and the version rule . [[evals]] the model evals:
  lanes, the jail, reading results

## The tree

```
crayon.py                          ← the gate: one stdlib-only Python file (contract-v1),
                                     installed on PATH as `crayon`
install.sh                         ← the interactive installer; --yes takes every default,
                                     --verify-only checks an existing install; ends by
                                     printing the uninstall commands for the paths it used
README.md                          ← the reader's entry point: what crayon is, install, use;
                                     names skills only, never a `crayon` command
AGENTS.md                          ← this file: the agent guide and the wiki's root
CHANGELOG.md                       ← the release record
LICENSE                            ← LGPL-3.0-only, the tool
.github/workflows/ci.yml           ← the CI graph; each job body is a literal local command

docs/                              ← the wiki: flat, one page per slug, bracket-addressed
├── contents.md                    ← the reader's index of every document, in path links
├── internals.md                   ← under the hood: glossary, verbs, exit codes, branches;
│                                     carries the marked VERBS and REASONS regions
├── contract.md                    ← NORMATIVE. Frozen at tag `contract-v1`
├── architecture.md                ← the shape, the non-negotiables, the constraints
├── conventions.md                 ← markup, ledger, commit seam, documents, shell and Python
├── install.md                     ← the install guide, manual first; carries the marked
│                                     INSTALL region tests/install_smoke.sh executes
├── compatibility.md               ← the contract number and min_tool; carries the marked
│                                     COMPAT region
├── hooks.md                       ← what a formatting hook on a target page leads to
├── shellcheck.md                  ← the shellcheck version policy
├── development.md                 ← tooling, testing and verification for contributors;
│                                     the gate's second pinned home
├── upgrade.md                     ← upgrading the tool, the skills and existing records
├── evals.md                       ← the model evals: what they measure, reading results
└── context.md                     ← the five context files, who produces them, the two verbs

skills/                            ← the human-facing surface
├── README.md                      ← verb table, routing table (the authoring site), install
├── LICENSE                        ← Apache-2.0, the skills only
├── crayon-onboard/
│   ├── SKILL.md                   ← repo walk → doc-style, glossary, structure, through the tool
│   └── references/                ← glossary-stance.md, routing.md, structure-stance.md,
│                                     style-stance.md (the stance authoring site)
├── crayon-fetch/
│   ├── SKILL.md                   ← declared external sources → the same artefacts, provenance
│   └── references/                ← glossary-stance.md, routing.md, source-contract.md,
│                                     structure-stance.md, style-stance.md (stances mirrored)
├── crayon-plan/
│   ├── SKILL.md                   ← declare + HITL signoff; Socratic intake, routes on Diátaxis
│   └── references/                ← actionable-intake.md, context-bootstrap.md,
│                                     explanation-intake.md, reference-intake.md, routing.md,
│                                     socratic-technique.md
├── crayon-write/
│   ├── SKILL.md                   ← the SOLE writer: drafts from sources or from a step walk
│   └── references/                ← episode-taxonomy.md, explanation-stance.md,
│                                     how-to-stance.md, reference-stance.md, routing.md,
│                                     tutorial-stance.md, walk-protocol.md,
│                                     writing-standards.md
└── crayon-review/
    ├── SKILL.md                   ← review + record the verdict (accept/fix/redraft)
    └── references/                ← provenance-summary.md, review-rubric.md, routing.md

scripts/
├── skill_lint.py                  ← SKILL.md frontmatter + writer-allowlist gate
├── planning_lint.py               ← the anonymization gate over .planning/
└── wiki_lint.py                   ← the docs/ wiki and AGENTS.md shape

validation/                        ← the validation kit: the evidence apparatus, not the tool
├── score.py                       ← the rubric scorer and the independent audit oracle
├── fixtures.sh                    ← V-01…V-04: four corruptions built from real verbs, and the
│                                     oracle that catches each one
├── audit-docpr-3005.md            ← public-run accountability audit and guarantee table
├── closeout-docpr-3008.md         ← slim-cycle dispositions, release truth and known limits
├── runmeta.sh                     ← records a leg's RUN metadata alongside its drafts
├── dogfood-docpr-3002.md          ← local public-candidate dogfood findings and limits
├── rubric.md                      ← the scoring bar a leg's drafts are read against
└── evals/                         ← the model evals: one neutral loop, many OpenRouter models;
    │                                 paid runs by hand only, never in the gate
    ├── README.md                  ← lanes, running, where results go, adding a case
    ├── run.py                     ← the runner: a lane × a model or the roster, --dry-run offline
    ├── openrouter.py              ← the one transport: pinned backend, retries, cache, spend cap
    ├── skills.py                  ← the catalog and /skill invocation, shared by every model
    ├── lanes.py                   ← each lane's case loader, live call and oracle
    ├── agent.py                   ← the seven tools, the replayed history, the decisive action
    ├── sandbox.py                 ← real snapshots of the recorded states, copied per episode
    ├── grade.py                   ← the assertion kinds and the pinned judge
    ├── record_states.py           ← records the real tool's output for lane B; --check for drift
    ├── models.json                ← the roster: candidates, gate, judge, author, caps
    ├── fixtures/                  ← states.sh (the recorder, on tests/lib.sh) and the toyq project
    ├── cases/                     ← the case files, one set per lane
    └── results/                   ← committed clean summaries; raw/ is gitignored

tests/
├── test_crayon_unit.py            ← the unit suite; also the home of the line budget, of the
│                                     GATE_COMMANDS tuple and of the pin over this listing
├── test_skill_text.py             ← the skill-text contracts and the routing-mirror equality
├── test_planning_lint.py          ← the anonymization lint's own tests
├── test_check_docs.py             ← the docs-accuracy checker's own tests
├── test_wiki_lint.py              ← the wiki lint's own tests
├── test_evals.py                  ← the model-eval kit's offline self-tests: transport, kinds,
│                                     every case against its own oracle
├── test_crayon_lifecycle.sh       ← the lifecycle / recovery suite (hermetic temp git repos)
├── test_crayon_acceptance.sh      ← the acceptance suite, A-01 … A-38
├── lib.sh                         ← the fixtures both bash suites share; ONE definition site
├── install_smoke.sh               ← CI-02 / A-37: run docs/install.md's INSTALL region, then
│                                     one unit through the installed tool
├── check_traces.py                ← the contract trace-table checker
├── check_docs.py                  ← the docs-accuracy checker: links, verbs, reasons, compat
│                                     and the release record, across the documents it names
├── size_guard.py                  ← VERB-09's line budget over `crayon.py`, reported and enforced
└── run_matrix.sh                  ← local-only: the unit suite on 3.9 / 3.12 / 3.13
```

The `docs/`, `scripts/`, `tests/` and `validation/` sections are pinned against the real tree
in both directions by `tests/test_crayon_unit.py`; a file that ships and is not listed goes red,
and so does a listed name that does not exist. One tracked-elsewhere file is deliberately absent
and named in that suite's `UNSHIPPED_PATHS`: `before-after.md` under `docs/`. The `skills/`
section and the root block are outside the pin; the two `.html` files at the root are v1-era
records kept as they are on `main`.

## Key files

| File | Purpose |
|------|---------|
| `crayon.py` | the tool; every guarantee is code here |
| `docs/contract.md` | the normative specification; wins every disagreement |
| `skills/README.md` | the skill family contract and the single-source routing table |
| `tests/test_crayon_unit.py` | the suite that pins the gate, the tree, CI and the line budget |
| `scripts/wiki_lint.py` | the checker for this file and `docs/` |
