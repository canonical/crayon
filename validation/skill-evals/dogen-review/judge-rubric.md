# dogen-review judge rubric

Score the transcript against `manifest.json`. Recompute every count; do not
eyeball. A presented finding matches a manifest defect when it flags the same
text/behaviour (wording may differ); a finding matching no defect and no
legitimate extra is a false positive.

## Axes and thresholds (v1)

| Axis | Measure | Threshold |
|------|---------|-----------|
| Recall | matched defects / 15 seeded | ≥ 0.80 overall; ≥ 0.70 per dimension (every dimension is gated — each carries 3 seeds; a gate on fewer than 3 seeds is noise, so keep that floor if the manifest changes) |
| Precision | matched findings / all presented findings | ≥ 0.75 |
| False positives on controls | findings on `pipeline-config-clean` + flagged traps (T-01 promoted as a finding, or T-02's "watch undocumented") | **0 — hard gate** |
| Severity calibration | of matched findings: exact severity / within one band | exact ≥ 0.60; within-one ≥ 0.90 |
| Format compliance | binary — see checklist | PASS — hard gate |
| Non-destructiveness | binary — porcelain diff shows only CLI transition commits | PASS — hard gate |

**Deterministic-detection floor:** every defect with
`expected_detection: "deterministic"` (D-01, D-02, D-05, D-15) must be caught —
a miss there is a pre-pass regression, not judgment variance, and fails the run
regardless of overall recall.

## Format-compliance checklist (recompute, do not eyeball)

- [ ] Findings grouped by dimension, writing-approach first, all five present
      (a clean dimension shows `(none)`).
- [ ] Every finding numbered `F-N` in presentation order, with page:line and a
      verbatim quote.
- [ ] Every writing-approach finding names its failure mode AND gives a
      concrete end-state rewrite.
- [ ] The tally line's counts equal the findings actually listed.
- [ ] Dismissed pre-pass candidates listed separately, outside the tally
      (T-01 must appear here, with a reason).
- [ ] `Recommended verdict` present and consistent with the tally
      (seeded fixture: must-fixes exist → fix or redraft; clean fixture:
      accept).
- [ ] No bracketed run-status token used as a finding tag (D-03 guard).
- [ ] The verdict was recorded via `dogen review` and the `git: committed`
      hash quoted; the frozen referral line closed the run.

## Scorecard template (`runs/<RN>/scorecard.md`)

```
# dogen-review eval scorecard — R<N>

- Model (skill run / judge): <weaker> / <stronger>
- Fixtures: pipeline-config-seeded, pipeline-config-clean

| Axis | Result | Threshold | Verdict |
|------|--------|-----------|---------|
| Recall (overall) | <n>/15 = <x.xx> | ≥ 0.80 | PASS/FAIL |
| Recall per dimension | wa <n>/3 · sf <n>/3 · co <n>/3 · st <n>/3 · cl <n>/3 | ≥ 0.70 each | PASS/FAIL |
| Deterministic floor | <n>/4 (D-01 D-02 D-05 D-15) | 4/4 | PASS/FAIL |
| Precision | <n>/<m> = <x.xx> | ≥ 0.75 | PASS/FAIL |
| FPs on clean/traps | <n> | 0 | PASS/FAIL |
| Severity exact / within-one | <x.xx> / <x.xx> | ≥ 0.60 / ≥ 0.90 | PASS/FAIL |
| Format compliance | — | checklist | PASS/FAIL |
| Non-destructiveness | — | porcelain clean | PASS/FAIL |

VERDICT: PASS / FAIL — <one line>
Human spot-check: <3 findings re-verified; agreement/disagreement>
```
