# dogen — Agent Guide

This file is the entry point for any coding agent working in this repository, and the root of
its wiki. A link written as a slug in double square brackets resolves to the page of that name
under `docs/`, so [[install]] is `docs/install.md`; the notation is
reserved to this file and to `docs/`, has no anchors or aliases, and is checked even inside code
fences. Everywhere else a page is cited by its path. After editing this file or anything under
`docs/`, run `python3 scripts/wiki_lint.py`.

## What this repo is

dogen drafts review-ready, Sphinx-publishable documentation (MyST or rST, Diátaxis-structured)
from human-pointed sources, with a recorded human signoff before any substantial draft, and
stops at one traceable local commit. It is one stdlib-only Python file, `dogen.py`, driven by
three portable Agent Skills. Its behaviour is fixed by [[contract]], frozen at the git tag
`contract-v1`; where the contract and any other document disagree, the contract wins.

## Core rules (always apply)

- The deterministic tool is the gate: guarantees live in `dogen.py`, never in skill prose or the
  model's discretion; never weaken a check for a nicer prompt ([[architecture]]).
- No substantial draft without a recorded signoff; `draft` refuses until `dogen signoff` is on
  record and the plan hash is current ([[contract]]).
- dogen drafts and stops: one local commit per transition, `.dogen/` and `docs/` only, `Dogen-*`
  trailers; it never pushes, builds, publishes or opens pull requests ([[architecture]]).
- The ledger is the record of truth, append-only and hash-chained; no line is ever edited, not
  even a step's status, and state is derived, never stored ([[conventions]]).
- `dogen-write` is the sole writer, enforced by the fail-closed allowlist in
  `scripts/skill_lint.py`; no skill writes the canonical page or the ledger ([[architecture]]).
- The tool owns its commits: never run a competing `git add` or `git commit` for a gated
  transition ([[conventions]]).
- A fixture, a routing row, a threshold or a gate command has one definition site and is
  mirrored mechanically; a hand copy is drift ([[development]]).
- Stdlib only, Python 3.9 syntax, no package, no venv, no third-party runner ([[architecture]]).
- Harness-agnostic: no agent harness is named, detected or preferred on any surface; skills are
  invoked as `/dogen-plan`, `/dogen-write`, `/dogen-review` everywhere ([[install]]).
- Sphinx-oriented, stack-agnostic: the output is Sphinx-publishable, but dogen knows no theme,
  extension, `conf.py` or stack and never builds; house conventions arrive only through
  `.dogen/context/` ([[install]]).
- Formatting hooks are adopted, never fought ([[hooks]]).
- Every non-zero exit is one JSON line with `error`, `unit`, `detail`, `hint`, `next`; branch on
  `error`, never on the exit code ([[architecture]]).

## The gate

Every command below must be green before a commit lands. This is the gate in full; there is no
shorter version, and a claim of completeness that omits one is the failure mode the list exists
against. It is pinned by the `GATE_COMMANDS` tuple in `tests/test_dogen_unit.py`: every string
appears here and in [[development]] verbatim, every `tests/test_*.py` module appears in it, and
every `run:` body in `.github/workflows/ci.yml` is one of them.

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
python3 -m unittest tests.test_wiki_lint         # the wiki lint's own tests
python3 scripts/wiki_lint.py                     # the docs/ wiki and AGENTS.md shape
```

Set `GIT_CONFIG_GLOBAL=/dev/null` for any fixture that shells out to git. Both invocation forms
of the unit suite are listed on purpose: they reported different counts once. The shell files
are kept clean at `shellcheck -S warning install.sh tests/*.sh validation/*.sh` — that exact
command and scope is CI's `shellcheck` job; the version policy is in [[shellcheck]]. What each
command proves, and what pins what, is in [[development]].

## Skills

Three portable skills under `skills/`, to the agentskills.io spec: `dogen-plan` (declare and
sign off), `dogen-write` (the sole writer; drafts from sources, or from an evidence-gated step
walk for tutorials and how-tos) and `dogen-review` (record the verdict). The family contract and
the routing table are in `skills/README.md`; the table is mirrored byte-identically into each
skill's `references/routing.md`, and `tests/test_skill_text.py` asserts the copies are equal.

## Topic index

- **Using**: [[install]] the installer, every choice, context files . [[upgrade]] tool, skills,
  records across releases . [[compatibility]] contract number and min_tool . [[hooks]] what a
  formatting hook leads to
- **Contract**: [[contract]] the normative specification, frozen . [[architecture]] the shape,
  the non-negotiables, the constraints . [[conventions]] markup, ledger, commit seam, documents
- **Developing**: [[development]] gate, suites, checkers, what pins what, driving the verbs by
  hand . [[shellcheck]] the pinned analyzer and the version rule

## The tree

```
dogen.py                           ← the gate: one stdlib-only Python file (contract-v1),
                                     installed on PATH as `dogen`
install.sh                         ← the interactive installer; --yes takes every default,
                                     --verify-only checks an existing install
README.md                          ← the reader's entry point: quickstart, usage, branch
                                     practice, glossary; carries the marked VERBS and
                                     REASONS regions
AGENTS.md                          ← this file: the agent guide and the wiki's root
CHANGELOG.md                       ← the release record
LICENSE                            ← LGPL-3.0-only, the tool
.github/workflows/ci.yml           ← the CI graph; each job body is a literal local command

docs/                              ← the wiki: flat, one page per slug, bracket-addressed
├── contract.md                    ← NORMATIVE. Frozen at tag `contract-v1`
├── architecture.md                ← the shape, the non-negotiables, the constraints
├── conventions.md                 ← markup, ledger, commit seam, documents, shell and Python
├── install.md                     ← the install guide; carries the marked INSTALL region
│                                     tests/install_smoke.sh executes
├── compatibility.md               ← the contract number and min_tool; carries the marked
│                                     COMPAT region
├── hooks.md                       ← what a formatting hook on a target page leads to
├── shellcheck.md                  ← the shellcheck version policy
├── development.md                 ← tooling, testing and verification for contributors;
│                                     the gate's second pinned home
└── upgrade.md                     ← upgrading the tool, the skills and existing records

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
├── planning_lint.py               ← the anonymization gate over .planning/
└── wiki_lint.py                   ← the docs/ wiki and AGENTS.md shape

validation/                        ← the validation kit: the evidence apparatus, not the tool
├── score.py                       ← the rubric scorer and the independent audit oracle
├── fixtures.sh                    ← V-01…V-04: four corruptions built from real verbs, and the
│                                     oracle that catches each one
├── runmeta.sh                     ← records a leg's RUN metadata alongside its drafts
└── rubric.md                      ← the scoring bar a leg's drafts are read against

tests/
├── test_dogen_unit.py             ← the unit suite; also the home of the line budget, of the
│                                     GATE_COMMANDS tuple and of the pin over this listing
├── test_skill_text.py             ← the skill-text contracts and the routing-mirror equality
├── test_planning_lint.py          ← the anonymization lint's own tests
├── test_check_docs.py             ← the docs-accuracy checker's own tests
├── test_wiki_lint.py              ← the wiki lint's own tests
├── test_dogen_lifecycle.sh        ← the lifecycle / recovery suite (hermetic temp git repos)
├── test_dogen_acceptance.sh       ← the acceptance suite, A-01 … A-38
├── lib.sh                         ← the fixtures both bash suites share; ONE definition site
├── install_smoke.sh               ← CI-02 / A-37: run docs/install.md's INSTALL region, then
│                                     one unit through the installed tool
├── check_traces.py                ← the contract trace-table checker
├── check_docs.py                  ← the docs-accuracy checker: links, verbs, reasons, compat
│                                     and the release record, across the documents it names
├── size_guard.py                  ← VERB-09's line budget over `dogen.py`, reported and enforced
└── run_matrix.sh                  ← local-only: the unit suite on 3.9 / 3.12 / 3.13
```

The `docs/`, `scripts/`, `tests/` and `validation/` sections are pinned against the real tree
in both directions by `tests/test_dogen_unit.py`; a file that ships and is not listed goes red,
and so does a listed name that does not exist. One tracked-elsewhere file is deliberately absent
and named in that suite's `UNSHIPPED_PATHS`: `before-after.md` under `docs/`. The `skills/`
section and the root block are outside the pin; the two `.html` files at the root are v1-era
records kept as they are on `main`.

## Key files

| File | Purpose |
|------|---------|
| `dogen.py` | the tool; every guarantee is code here |
| `docs/contract.md` | the normative specification; wins every disagreement |
| `skills/README.md` | the skill family contract and the single-source routing table |
| `tests/test_dogen_unit.py` | the suite that pins the gate, the tree, CI and the line budget |
| `scripts/wiki_lint.py` | the checker for this file and `docs/` |
