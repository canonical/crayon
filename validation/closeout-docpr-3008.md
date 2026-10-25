# DOCPR-3008: slim-cycle close-out record

This record was refreshed from Jira on 2026-10-09. It separates the published
product evidence from the remaining manual portfolio actions. At this
snapshot, the 40 DOCPR-2845 children comprise 29 Done, seven Rejected, two
Triaged and two In Progress. DOCPR-2999 and DOCPR-3003 are Triaged;
DOCPR-3007 and DOCPR-3008 are In Progress. DOCPR-3008 must not be transitioned
until the other three have terminal dispositions.

## Disposition and evidence

| Work | Recorded outcome |
| --- | --- |
| [DOCPR-2997](https://warthogs.atlassian.net/browse/DOCPR-2997) | Richer retrieval was deferred to a later controlled experiment with explicit triggers; the current evidence does not isolate its value. |
| [DOCPR-3001](https://warthogs.atlassian.net/browse/DOCPR-3001) | The observed hard defects and decision-safety gaps were closed or assigned to follow-up; its Jira status is Done. |
| [DOCPR-3002](https://warthogs.atlassian.net/browse/DOCPR-3002) | Four accepted local dogfood units, their fixes and their evidence limits are recorded in [dogfood-docpr-3002.md](dogfood-docpr-3002.md). |
| [DOCPR-3004](https://warthogs.atlassian.net/browse/DOCPR-3004) | An outside author completed two unaided adoption scenarios; the retained report is qualitative and does not supply a clean timed baseline. |
| [DOCPR-3005](https://warthogs.atlassian.net/browse/DOCPR-3005) | The steering/provenance audit reconstructed the public records, exercised negative paths and closed an independent-audit read-boundary defect; see [audit-docpr-3005.md](audit-docpr-3005.md). |
| [DOCPR-3006](https://warthogs.atlassian.net/browse/DOCPR-3006) | The evidence-limited comparison records an estimated manual path of three active hours to a reviewable patch plus two active hours through review/acceptance; it is not a controlled productivity result. |
| DOCPR-2999, DOCPR-3003, DOCPR-3007 | Manual terminal dispositions remain outside this repository change. Their current non-terminal states are the close-out stop condition. |

The landed hardening is reviewable in
[canonical/crayon#34](https://github.com/canonical/crayon/pull/34),
[canonical/crayon#35](https://github.com/canonical/crayon/pull/35),
[canonical/crayon#36](https://github.com/canonical/crayon/pull/36), and
[canonical/crayon#38](https://github.com/canonical/crayon/pull/38). Together
they cover dogfood provenance/report handling, transcript capture and scorer
regressions; the independent-audit root boundary; CI, privacy and release-note
corrections; and the manual-first install/update/discovery documentation and
smoke path. The portable five-skill family and recorded-context seams are
present on published `main`.

## Release and validation truth

The 0.2.0 product tree reached `main` by force-push on 2026-10-01. There was
no reviewed release pull request or merge, no `v0.2.0` tag, and no GitHub
Release. At this snapshot, published `main` is
`edec520fd7b42082f326077a258d833e55e9fc9a`; GitHub Actions
[run 37534038841](https://github.com/canonical/crayon/actions/runs/37534038841)
is green across all ten jobs. CI is evidence by inspection, not a required
status check on the default branch.

The install smoke executes the documented installer, verifies discovery and
drives an installed unit to a verified draft plus a refusal. It does not
record review or acceptance, so it supports installation health but not a
clean-install-to-accepted-draft claim.

## Known limitations

- The older dogfood legs do not pass the complete repaired protocol: some
  origins are not hashable paths and their pre-registered leg/rubric files are
  absent.
- Active authoring time, installation time and several interaction metrics
  were not retained. Wall-clock intervals include human waits and are not
  substitutes.
- Candidate branches and raw transcripts are local-only and are not retained
  in this repository.
- Local Git history and hash chains detect inconsistency within the local
  trust boundary; they do not provide remote attestation, prevent complete
  history replacement or prove that a human made an approval.
- Model identities and some generation-report fields remain claims rather
  than independently authenticated facts.
- The model evals measure skill selection and next-action skill-following, not
  documentation quality, authoring speed or a whole-journey outcome.
- A green CI run is evidence for one commit, not a platform-enforced merge
  condition.

No unresolved critical provenance, data-loss, bypass or publishability defect
is known from the retained proof, dogfood, adoption, audit and regression
evidence. That conclusion does not erase the missing measurements or turn the
non-terminal Jira items into completed work.

The richer-retrieval experiment and the controlled comparison continue
separately. The work on plain record surfaces, author decisions, calibrated voice
and the model evals landed in the same pull request as this record, for 0.3.0
(`CHANGELOG.md`). This record and the release reconciliation are being prepared in
[canonical/crayon#39](https://github.com/canonical/crayon/pull/39); while that
pull request remains open, they are non-gating follow-up rather than evidence
already landed on `main`.
