# Skill evals

Regression evals for the portable skill family in `skills/`. dogen-review has a
full harness (seeded-defect fixtures + judge rubric); dogen-plan and dogen-write
are protocol-only checklists (conversational skills — fixture cost exceeds
value).

These trees live here, NOT under `skills/<skill>/eval/`, because
`dogen skills install` copies each skill directory wholesale into every consumer
harness root and hashes every file into the drift manifest — eval content would
ship to users and every eval edit would flip `dogen skills status` to drifted.
`validation/` is the repo's established dev-time evidence home and is excluded
from the ruff gate.

## Layout

```
skill-evals/
  dogen-review/          # FULL harness
    manifest.json        # ground truth: 15 seeded defects + 2 traps + a clean control
    protocol.md          # the numbered regression procedure
    judge-rubric.md      # axes, thresholds, scorecard template
    setup.sh             # stands a fixture up via the real CLI verbs
    fixtures/
      src/               # invented-neutral product source (shared)
      pipeline-config-seeded/   # plan-body + seeded draft + report
      pipeline-config-clean/    # zero-defect control
    runs/<RN>/           # per-run report.md + scorecard.md (created per run)
  dogen-plan/protocol.md   # scripted-dialogue checklist (incl. triage bait)
  dogen-write/protocol.md  # passenger-drafting checklist (incl. re-draft)
```

## Method (the family pattern)

1. **Skill run on a weaker model**, fresh session — the skill must not depend
   on frontier attention. Non-destructiveness is scored from
   `git status --porcelain` before/after.
2. **Judge on a stronger model**, fresh session, scoring against
   `manifest.json` — recompute every count.
3. **Human spot-check of 3 random findings** — never skipped; disagreement
   widens the check and is recorded as a judge-calibration gap.
4. **Iterate** — never weaken a check to pass; threshold changes carry a
   recorded rationale. Recurring legitimate extras get folded into the
   manifest.

All fixture content is product-neutral by construction — invented `pipeline`
naming only, no real product, vendor, or upstream names in any casing.
