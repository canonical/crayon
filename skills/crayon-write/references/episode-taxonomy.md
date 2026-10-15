Load this file at the walk step (silent-until-signal).

# Episode taxonomy — improvisation and frustration

The walk's quality signals are **derived**, not stored — they already exist in the
ledger (`## steps` section: each step's `verdict`, `status`, and `reason`) and in
`git log` (the `Crayon-Step` trailers per step-recorded commit). This file names the
two episode kinds and maps each to the mechanical signal that carries it, so the
walk replays from `git log` + the ledger alone with zero extra stored state. The
taxonomy is adapted from the user's test-docs skill.

## Improvisation

**The planned step did not say how, and the agent or TA had to figure it out.**
The step ran and reached a good state, but off the literal plan — a missing detail
supplied, an undocumented flag needed, a fork resolved with an obvious default.

- Deviations from the step's literal text that still succeed.
- Missing-information forks resolved without a TA consult (the default was obvious).
- An informed default taken silently and logged as a delta.

**Signal — record the step as a `deviated` verdict (exit 0) with a `reason`:**

```
verdict: deviated
mode: agent
command: "cd $WS && foo init --config ./foo.toml"   # the actual command run
output_sha256: "…"
exit_code: 0
reason: "the step said 'initialize foo' but not that --config is required on a fresh dir"
step_text_sha256: "…"
```

`deviated` with exit 0 **still resolves** the step, so the walk proceeds — AND the
`reason` lands in the ledger step row (the `| reason: …` field), becoming the
episode's free-text color. High improvisation on a step is a signal about
**proposal quality**: the plan under-specified that step.

## Frustration

**Repeated difficulty on one step** — the reader (and the walk) hit friction that a
better plan would have avoided.

- **Repeated failures on one step** — at least two attempts before it resolved.
- **A TA correction of a wrong assumption** — the plan assumed something false and
  the TA had to set it right.
- **A mode override mid-walk** — a step planned agent-runs that had to flip to
  TA-runs (or the reverse) once reality intervened.

**Signal — fail-count plus step-plan re-edits:** each failed attempt is a recorded
`fail` (the ledger step row's `verdict: fail`, status stays `unverified`); a
wrong-assumption correction or a mode flip re-edits the `## steps` section (a step
whose text changed re-derives `unverified` because its `text_hash` no longer
matches its evidence). The count of these across the walk is the frustration
measure — no stored field, all derived from the ledger + commit history.

## Why derived, not stored

A `pass` step carries no `reason` — plain passes carry no color, by design. Routing
improvisation through `deviated` (which carries a `reason`) and frustration through
fail-count/re-plan keeps every signal in the mechanical record without a new field
or a sidecar. crayon-review surfaces the tally (deviation/skip/fail counts from the
ledger plus the reason notes) in its quality-signals block, and the rubric weighs
flagged sections. A frustration count of three or more on a single walk is a
documented quality signal that the step plan needs work.