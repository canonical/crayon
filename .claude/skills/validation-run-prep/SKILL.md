---
name: validation-run-prep
description: Prepares a repeatable, concurrent three-harness dogen validation run on the smoke-docs-1 target repo (a sibling of this repo) by creating one git worktree per harness (Claude Code, Copilot CLI, opencode) branched from the validation-base-v4 baseline, putting this repo's up-to-date dogen on PATH in each, refreshing the staged skill family per harness, confirming the two units' missing-file preconditions (single-file workshop-definition and multi-file schema-section-consistency), and emitting a ready-to-paste starting prompt for each agent. It preps and stops, leaving the human to launch the agents and score per VALIDATION.md; it delegates the deterministic worktree, env, and skills-refresh moves to prepare.sh. Use when starting a new round of the three-harness dogen validation run.
allowed-tools: Read, Bash, Write, Edit, Glob, Grep, AskUserQuestion
---

<objective>
Prepare a repeatable, CONCURRENT three-harness dogen validation run on the target repo
`../smoke-docs-1` (a sibling of this repo) and then STOP. Create one git worktree per
harness (Claude Code, Copilot CLI, opencode) branched from the `validation-base-v4`
baseline, put this repo's up-to-date dogen (`.venv/bin`) on PATH in each, refresh the staged skill
family per harness, confirm the two units' missing-file preconditions, and emit a
ready-to-paste starting prompt for each agent. This skill holds the judgment
(confirmations, interpretation, prompt emission); the deterministic moves — worktree
creation, env-file baking, the per-harness skills refresh — are delegated to the
committed helper `prepare.sh`. The skill never launches the agents, never pushes or
tags, and never points any dogen run at the akcano comparison set. The run itself and
the scoring stay governed by `../smoke-docs-1/VALIDATION.md` and `../smoke-docs-1/validation/`.
</objective>

<quick_start>
1. Confirm intent: prepare a fresh round of the three-harness validation run. If the
   caller wants to drive or score a run, route them to `../smoke-docs-1/VALIDATION.md`
   instead — this skill only preps.
2. Run `./prepare.sh plan` (read-only) and present the resolved paths, branch names, and
   base sha to the caller.
3. With `AskUserQuestion` (BLOCKING), confirm: the worktree container path (default
   `../smoke-docs-worktrees`, outside both repos); the force-recreate policy if worktrees
   or `validation/<harness>-wt` branches already exist; and whether to commit the skills
   refresh (default yes).
4. Run `./prepare.sh apply` (honoring the confirmed `FORCE` / `COMMIT_REFRESH`), then
   `./prepare.sh verify`. Surface any `FAIL` line; do not proceed on a failed verify.
5. Emit the three per-agent starting prompts (workflow step 4), then hand off to
   `VALIDATION.md` and STOP.
</quick_start>

<pipeline>
validation-run-prep -> (human) dogen-plan -> dogen-write -> dogen-review -> score

This skill is the prep stage. It consumes this repo's up-to-date dogen + canonical
skills, the sibling target repo `../smoke-docs-1` at tag `validation-base-v4`, and the
protocol in `../smoke-docs-1/VALIDATION.md`. It produces three isolated worktrees (one per
harness) with dogen on PATH, refreshed skills, the two units' missing-file state, plus
three copy-paste starting prompts. Routing rules:

- On success it hands off to the human, who launches each agent in its worktree and
  drives `dogen-plan -> dogen-write -> dogen-review` for both units, then scores per
  `VALIDATION.md` + `validation/score.py`.
- It never launches an agent, drives the loop, commits a draft, pushes, or tags.
- Deterministic side effects are the helper's; this skill decides and reports.
</pipeline>

<workflow>
<step_1 name="Preflight and confirm">
Run `./prepare.sh plan` from this skill's directory. It preflights (up-to-date dogen at
`$DOGEN_REPO/.venv/bin/dogen`, `smoke-docs-1` is a git repo, `validation-base-v4`
resolves, canonical skills present, git identity set) and prints the resolved worktree
paths, branch names (`validation/<harness>-wt`), and base sha. Present that to the
caller. Then, with `AskUserQuestion` (BLOCKING), settle three things and pass them to
`apply` as env vars: (a) the worktree container path (`WT_ROOT`, default
`../smoke-docs-worktrees`); (b) `FORCE` (1 to remove and recreate an existing worktree or
`-wt` branch — never silently; 0 to leave existing ones as-is); (c) `COMMIT_REFRESH`
(1 to land one explicit-staged local commit per worktree for the skills refresh, 0 to
leave it uncommitted).
</step_1>

<step_2 name="Apply the prep">
Run `FORCE=<n> COMMIT_REFRESH=<n> ./prepare.sh apply`. For each harness it creates the
worktree from `validation-base-v4`, writes `env-<harness>.sh` (baking this repo's
absolute `.venv/bin` onto PATH and `unset DOGEN_PROVIDER` — host-harness passenger,
mandatory for the multi-file unit), refreshes that harness's skills via
`dogen skills install --harness <h> --from <this repo>/skills`, and — when
`COMMIT_REFRESH=1` and there is a diff — commits it with explicit per-file staging (never
`git add -A`). The helper is idempotent: re-running without `FORCE` leaves existing
worktrees untouched.
</step_2>

<step_3 name="Confirm preconditions and prep soundness">
Run `./prepare.sh verify` (read-only). It asserts, per worktree: the worktree exists and
is on `validation/<harness>-wt` containing `validation-base-v4`; dogen resolves to this
repo's venv; the env file exists; `workshop-definition.rst` is ABSENT (unit 1's
missing-file state); the sdk/sdkcraft schema divergence phrases are present (unit 2);
`dogen unit ls` is empty. Every leg must print `OK`. If any `FAIL` appears, surface it
and stop — do not emit prompts against a broken prep.

Also confirm the seeded context is CURRENT before emitting prompts — round-3 ran a leg
against stale seeded context, and this check closes that gap. In
`../smoke-docs-1/.dogen/context/doc-gaps.md`: (a) the suggested-/possible-location prefixes
must point at the repo's real `docs/` layout, not the retired `workshop-docs/` prefix
(`grep -c 'workshop-docs/' ../smoke-docs-1/.dogen/context/doc-gaps.md` must print `0`); and
(b) its line-number links must still resolve against the current sources (line numbers
drift as sources change). If either is stale, refresh `.dogen/context/` — regenerate via
the dogen context tooling, or correct the prefixes — before starting any leg.
</step_3>

<step_4 name="Emit the three per-agent starting prompts">
For each harness, print one copy-paste block with the absolute worktree and env paths
substituted, telling the human to: launch that agent rooted in its worktree pinned to a
Sonnet 4.6-class model; `source <WT_ROOT>/env-<harness>.sh`; verify `command -v dogen`,
`dogen provider show` (host-harness), and `dogen unit ls` (No units); then drive
`/dogen-plan -> /dogen-write -> /dogen-review` for BOTH units using the fixed TA scripts
quoted from `VALIDATION.md` — Unit 1 `workshop-definition` (single-page rST; placement
proposed by the skill from the toctree slot; outline must cover all seven interfaces and
a worked example) and Unit 2 `schema-section-consistency` (multi-file: primary
`sdk-definition.rst` + `--also-target sdkcraft-definition.rst`, one `--draft-dir` pass).
Close each leg by committing the session export as exactly `validation/SESSION-<harness>.md`.
Do not paraphrase the TA answers — comparability across legs depends on them.
</step_4>

<step_5 name="Hand off and stop">
Point the caller to `../smoke-docs-1/VALIDATION.md` (per-leg protocol, pass criteria) and
`../smoke-docs-1/validation/` (`score.py`, `rubric.md`, `RESULTS.md`) for running and
scoring. STOP: do not launch any agent, drive the loop, push, or tag. The human owns the
run and the publishing commit.
</step_5>
</workflow>

<edge_cases>
**Worktree or `-wt` branch already exists:** `apply` without `FORCE` leaves it as-is and
says so; with `FORCE=1` it removes the worktree and deletes the branch (after the step-1
confirmation) and recreates from the tag. Never silently clobber.

**Skills already current:** if the baked skills already match this repo's `skills/`, the
refresh produces no diff and no commit is made — that is expected, not an error.

**dogen not on PATH / non-editable install:** the helper always installs skills with an
explicit `--from <this repo>/skills`, so a non-editable install still refreshes from
the intended source. If `prepare.sh plan` reports the dogen binary missing, this repo's
`.venv` has not been built — build it first (`uv sync` here).

**Git identity unset in smoke-docs-1:** `signoff` / `review` / `unit edit --re-sign`
during the run require it; preflight fails loudly if `user.name`/`user.email` are unset.

**A stray `workshop-definition.rst` is present:** verify FAILs — the worktree is not at
the clean missing-file baseline; recreate it with `FORCE=1`.
</edge_cases>

<constraints>
<must>
- Branch every worktree only from `validation-base-v4`; use new branch names
  `validation/<harness>-wt` (never reuse the round `-2`/`-3` branches).
- Bake this repo's `.venv/bin` onto PATH in each env file. The target repo's committed
  `dogen-validation-env.sh` resolves the dogen checkout on its own — this skill's
  generated env files, not that script, are the source of truth for a prepped worktree.
- Keep `DOGEN_PROVIDER` unset in the env files (host-harness passenger) — the multi-file
  unit `schema-section-consistency` refuses any driver provider (`multi_target_unsupported`).
- Refresh skills from this repo's `skills/`; if committing the refresh, stage explicit
  paths only.
- Delegate all side-effecting moves to `prepare.sh`; keep the confirmations, verify
  interpretation, and prompt emission in this skill.
- STOP after emitting the prompts: no agent launch, no push, no tag.
</must>
<must_not>
- Never point dogen, a skill, or a drafting session at the akcano comparison set
  (the `workshop-akcano` sibling checkout) — it is dev-time scoring material only.
- Never edit committed baseline files in `../smoke-docs-1` (its `dogen-validation-env.sh`,
  its `.gitignore`, the docs overlay) — the worktrees are the only place changes land.
- Never use `git add -A`; stage explicit paths.
- Never launch the harness agents or drive the loop from this skill.
</must_not>
</constraints>

<output_specification>
Present, inline in the conversation (no file is written beyond the worktrees + env files
+ optional refresh commits that `prepare.sh` makes):

```
## validation-run-prep

### Prep
- Base: validation-base-v4 <sha> · worktrees under <WT_ROOT>
- claude   -> <WT_ROOT>/claude   (validation/claude-wt)   skills: refreshed|current
- copilot  -> <WT_ROOT>/copilot  (validation/copilot-wt)  skills: refreshed|current
- opencode -> <WT_ROOT>/opencode (validation/opencode-wt) skills: refreshed|current
- verify: all legs OK

### Starting prompts (one per harness)
<three copy-paste blocks — launch + source env + verify + Unit 1 + Unit 2 TA scripts>

### Next (human)
Run + score per ../smoke-docs-1/VALIDATION.md and ../smoke-docs-1/validation/.
```
</output_specification>

<success_criteria>
- [ ] `prepare.sh plan` preflight passed and the caller confirmed WT_ROOT / FORCE /
      COMMIT_REFRESH via AskUserQuestion.
- [ ] Three worktrees exist under WT_ROOT, each on `validation/<harness>-wt` from
      `validation-base-v4`, with an `env-<harness>.sh` baking this repo's dogen
      and `unset DOGEN_PROVIDER`.
- [ ] Skills refreshed per harness from this repo's `skills/` (committed when asked).
- [ ] `prepare.sh verify` prints `OK` for every leg (dogen resolves; both units'
      missing-file preconditions hold; unit ls empty).
- [ ] Three per-agent starting prompts emitted with absolute paths and the verbatim
      VALIDATION.md TA scripts for both units.
- [ ] No agent was launched, nothing was pushed or tagged, akcano was never referenced.
</success_criteria>

<self_healing>
After completing a run, or after any error that required a workaround, check whether
the issue came from a gap or inaccuracy in this skill's instructions, references, or
workflow steps.

What qualifies for a skill update:

- Tooling issues (CLI syntax changes, path changes, deprecated commands)
- Structural problems (missing files, wrong folder layout, dangling references)
- Missing edge cases that caused failures
- Incorrect assumptions about the environment or dependencies

Off-limits for self-edits: the skill's objective, the workflow step sequence, and the
success criteria. Propose changes to those to the user as ideas, never as self-edits.

How to update:

1. Report to the user: (a) the gap detected, (b) which skill file needs the change,
   (c) the proposed change, quoted in full.
2. Wait for explicit confirmation.
3. Apply the change directly to the skill file with Edit (or Write for new reference
   files).
4. Preserve the shared skill conventions: section order, this self_healing block, and
   the <NAME> placeholder style.
</self_healing>
