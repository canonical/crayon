# Architecture and Non-Negotiables

<!-- provenance: moved from AGENTS.md (Non-negotiables, Project, The shape, Constraints) when AGENTS.md became the router -->

What dogen is made of, what it guarantees, and the rules that are never traded away. An agent
changing the tool reads this before touching anything; the one-line versions live in
`AGENTS.md` and delegate here.

## The shape

One stdlib-only Python file, `dogen.py`, at the repository root, installed on `PATH` as
`dogen`. Python 3.9 floor, no package, no venv, no dependencies, no third-party test runner.
One verb per transition over a hash-chained JSONL ledger; behaviour fixed by [[contract]],
frozen at the git tag `contract-v1`. The human-facing surface is three portable Agent Skills
under `skills/`, to the agentskills.io spec, split into `dogen-plan`, `dogen-write` and
`dogen-review`.

**Core value.** A Technical Author points dogen at sources for one documentation unit, steers
it on intent and audience, and gets a review-ready, Sphinx-publishable draft — produced through
a *provable* human-in-the-loop loop, with steering and provenance recorded on disk. If
everything else fails, this loop must work: declare → steer → draft → review, no substantial
draft without a recorded human signoff.

## Non-negotiables

**The deterministic tool is the gate.** dogen's guarantees live in code, not in skill prose and
not in the model's discretion. Never weaken a check in exchange for a "nicer" skill prompt. The
gate is the single `dogen.py` — one executable, one verb per transition — whose behaviour is
fixed by [[contract]].

**No substantial draft without a recorded human signoff.** `dogen signoff` is the gate verb: it
freezes `sha256(unit.md)` as the plan hash, and `draft` refuses — with no side effects — until a
signoff is on record and that hash is still current. Code-enforced; never moved into the model's
discretion.

**dogen drafts and stops.** Each transition is one local git commit, staging only `.dogen/` and
`docs/` and carrying `Dogen-*` trailers. The tool never pushes, opens or reviews pull requests,
builds, or publishes. The reviewer/merger owns the shipped output.

**The ledger is the provenance.** The record of truth is `.dogen/units/<id>/ledger.jsonl`:
hash-chained JSONL, append-only, one canonical line per event, each line's `prev` the sha256 of
the previous line's bytes ([[contract]] §5.2). Never invent a second record of truth: state is
*derived* by reading the ledger, and nothing is stored.

**Skills are the surface; the tool is the tool layer.** Technical Authors drive the three
skills; the skills invoke the deterministic tool through shell commands. `dogen-write` is the
sole writer, enforced by a fail-closed allowlist in `scripts/skill_lint.py` — a skill may write
only its own staging files, never the canonical `docs/` page, never the ledger.

## Constraints

- **Stdlib-only.** No third-party dependency anywhere in the product tree, enforced by the
  suite. The lints under `scripts/` are standalone stdlib utilities, not a second core.
- **Harness-agnostic.** Any agent that reads `SKILL.md` and can run shell commands works; the
  installer serves both discovery roots in use, `.agents/skills/` and `.claude/skills/`. No
  harness is named, preferred or detected anywhere on the surface.
- **Sphinx-oriented, stack-agnostic.** Output is Sphinx-publishable MyST Markdown (or rST where
  siblings are rST), Diátaxis-structured. dogen carries no knowledge of any Sphinx stack, theme,
  extension set or `conf.py`, never runs a build, and learns house conventions only through the
  context files described in [[install]].
- **Licensing.** The tool is LGPL-3.0-only; the skills are Apache-2.0.
- **HITL and provenance.** Provenance is internal observability, not a published "AI-generated"
  disclaimer.
- **UX.** If it is easier to circumvent than to use, it will be circumvented.

## Verbs, exit codes and refusals

The verb table and the reason table each have exactly one reader-facing home — `README.md`'s
`VERBS` and `REASONS` marked regions, under its Glossary — and one normative home, [[contract]]
§6 and §5.7. The README's reason table is one compact row per exit code; the contract's is one
row per reason; `tests/check_docs.py` flattens both against the authoritative machine list, the
`REASONS` dict inside `dogen.py`. The compatibility pair has the same shape of home:
[[compatibility]] and [[contract]] §5.10.

Every non-zero exit prints exactly one JSON line with the five keys `error`, `unit`, `detail`,
`hint` and `next` (stderr; stdout under `--json`). Branch on `error`, never on the exit code —
several reasons share one. `git log --grep 'Dogen-Unit: <id>'` replays a unit's whole path.

Related: [[contract]], [[conventions]], [[development]].
