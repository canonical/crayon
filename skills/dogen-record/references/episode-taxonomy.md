Load this file at workflow step 4 (Walk each step (silent-until-signal)).

# Episode taxonomy — improvisation and frustration (REC-09)

The walk's quality signals are **derived**, not stored — they already exist in
provenance (`record show`) and in `git log` (the `Dogen-Step`/`Dogen-Verdict`
trailers and the `step-recorded` commit bodies). This file names the two episode
kinds and maps each to the mechanical signal that carries it, so REC-09 replays
from `git log` alone with zero schema touch (D-14). The taxonomy is adapted from
the user's test-docs skill (D-15).

## Improvisation

**The planned step did not say how, and the agent or TA had to figure it out.**
The step ran and reached a good state, but off the literal plan — a missing detail
supplied, an undocumented flag needed, a fork resolved with an obvious default.

- Deviations from the step's literal text that still succeed.
- Missing-information forks resolved without a TA consult (the default was obvious).
- An informed default taken silently and logged as a delta.

**Signal — record the step as a `deviated` verdict (exit 0) with a `reason`:**

```yaml
verdict: deviated
mode: agent
command: "cd $WS && foo init --config ./foo.toml"   # the actual command run
output_sha256: "…"
exit_code: 0
reason: "the step said 'initialize foo' but not that --config is required on a fresh dir"
```

`deviated` with exit 0 **still resolves** the step (`derive_step_status`, D-08), so
the walk proceeds — AND the `reason` lands in the `step-recorded` commit body via
the shipped `_body_note` precedent, becoming the episode's free-text color. High
improvisation on a step is a signal about **proposal quality**: the plan under-specified
that step.

## Frustration

**Repeated difficulty on one step** — the reader (and the walk) hit friction that a
better plan would have avoided.

- **Repeated failures on one step** — at least two attempts before it resolved.
- **A TA correction of a wrong assumption** — the plan assumed something false and
  the TA had to set it right.
- **A mode override mid-walk** — a step planned agent-runs that had to flip to
  TA-runs (or the reverse) once reality intervened.

**Signal — fail-count plus re-plan commits:** each failed attempt is a recorded
`fail` (a `step-recorded` commit, status stays `unverified`); a wrong-assumption
correction or a mode flip is a `record plan` re-plan (a `step-planned` commit whose
hash-changed step re-derives `unverified`). The count of these across the walk is
the frustration measure — no stored field, all derived from the commit history.

## Why derived, not stored

A `pass` step writes an empty commit body, so plain passes carry no color — by
design. Routing improvisation through `deviated` (which does carry a body) and
frustration through fail-count/re-plan keeps every signal in the mechanical record
without a new schema field or a sidecar. dogen-review surfaces the tally
(deviation/skip/fail counts from `record show` plus the episode notes from
`git log`) in its provenance summary, and the rubric weighs flagged sections
(D-16). A frustration count of three or more on a single walk is a documented
quality signal that the step plan needs work — the Pitfall 1 metric against
ceremony overload and thin proposals.
</content>
</invoke>
