# Architecture and Non-Negotiables

<!-- provenance: moved from AGENTS.md (Non-negotiables, Project, The shape, Constraints) when AGENTS.md became the router -->

What crayon is made of, what it guarantees, and the rules that are never traded away. An agent
changing the tool reads this before touching anything; the one-line versions live in
`AGENTS.md` and delegate here.

## The shape

One stdlib-only Python file, `crayon.py`, at the repository root, installed on `PATH` as
`crayon`. Python 3.9 floor, no package, no venv, no dependencies, no third-party test runner.
One verb per transition over a hash-chained JSONL ledger; behaviour fixed by [[contract]],
frozen at the git tag `contract-v1`. The human-facing surface is five portable Agent Skills
under `skills/`, to the agentskills.io spec: `crayon-onboard` and `crayon-fetch` record the
repository's context, and `crayon-plan`, `crayon-write` and `crayon-review` carry one unit through
the loop.

**Core value.** A Technical Author points crayon at sources for one documentation unit, steers
it on intent and audience, and gets a review-ready, Sphinx-publishable draft — produced through
a *provable* human-in-the-loop loop, with steering and provenance recorded on disk. If
everything else fails, this loop must work: declare → steer → draft → review, no substantial
draft without a recorded human signoff.

## Non-negotiables

**The deterministic tool is the gate.** crayon's guarantees live in code, not in skill prose and
not in the model's discretion. Never weaken a check in exchange for a "nicer" skill prompt. The
gate is the single `crayon.py` — one executable, one verb per transition — whose behaviour is
fixed by [[contract]].

**No substantial draft without a recorded human signoff.** `crayon signoff` is the gate verb: it
freezes `sha256(unit.md)` as the plan hash, and `draft` refuses — with no side effects — until a
signoff is on record and that hash is still current. Code-enforced; never moved into the model's
discretion.

**crayon drafts and stops.** Each transition is one local git commit, staging only `.crayon/` and
`docs/` and carrying `Crayon-*` trailers. The tool never pushes, opens or reviews pull requests,
builds, or publishes. The reviewer/merger owns the shipped output.

**The ledger is the provenance.** The record of truth is `.crayon/units/<id>/ledger.jsonl`:
hash-chained JSONL, append-only, one canonical line per event, each line's `prev` the sha256 of
the previous line's bytes ([[contract]] §5.2). Never invent a second record of truth: state is
*derived* by reading the ledger, and nothing is stored.

**Skills are the surface; the tool is the tool layer.** Technical Authors drive the five
skills; the skills invoke the deterministic tool through shell commands. `crayon-write` is the
sole writer, enforced by a fail-closed allowlist in `scripts/skill_lint.py` — a skill may write
only its own staging files, never the canonical `docs/` page, never the ledger. The context
skills write nothing at all: each artefact reaches `.crayon/context/` through `crayon context
stage` and `crayon context record`, which digest and commit it ([[context]]).

## Constraints

- **Stdlib-only.** No third-party dependency anywhere in the product tree, enforced by the
  suite. The lints under `scripts/` are standalone stdlib utilities, not a second core. The
  model evals under `validation/evals/` are not the product and have their own environment
  ([[evals]]).
- **Harness-agnostic.** Any agent that reads `SKILL.md` and can run shell commands works; the
  installer serves both discovery roots in use, `.agents/skills/` and `.claude/skills/`. No
  harness is named, preferred or detected anywhere on the surface.
- **Sphinx-oriented, stack-agnostic.** Output is Sphinx-publishable MyST Markdown (or rST where
  siblings are rST), Diátaxis-structured. crayon carries no knowledge of any Sphinx stack, theme,
  extension set or `conf.py`, never runs a build, and learns house conventions only through the
  context files described in [[context]].
- **Licensing.** The tool is LGPL-3.0-only; the skills are Apache-2.0.
- **HITL and provenance.** Provenance is internal observability, not a published "AI-generated"
  disclaimer.
- **UX.** If it is easier to circumvent than to use, it will be circumvented.

## Verbs, exit codes and refusals

The verb table and the reason table each have exactly one reader-facing home — the `VERBS` and
`REASONS` marked regions in [[internals]] — and one normative home, [[contract]] §6 and §5.7.
The compact reason table is one row per exit code; the contract's is one row per reason;
`tests/check_docs.py` finds each region by its markers, requires exactly one carrier, and
flattens both tables against the authoritative machine list, the `REASONS` dict inside
`crayon.py`. The compatibility pair has the same shape of home: [[compatibility]] and
[[contract]] §5.10.

The reader drives crayon through the skills, never through the tool. `README.md` and the
reader-facing pages ([[contents]], [[install]], [[context]], [[upgrade]], [[hooks]]) name no
`crayon <verb>` outside a section headed `## Under the hood`; `tests/check_docs.py` enforces
it.

Every non-zero exit prints exactly one JSON line with the five keys `error`, `unit`, `detail`,
`hint` and `next` (stderr; stdout under `--json`). Branch on `error`, never on the exit code —
several reasons share one. `git log --grep 'Crayon-Unit: <id>'` replays a unit's whole path.

Related: [[contract]], [[context]], [[conventions]], [[development]].
