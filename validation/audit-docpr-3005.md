# DOCPR-3005: steering and provenance audit

This audits the locally committed, **public** DOCPR-3002 units against the
`contract-v1` ledger model, then exercises negative paths in disposable copies.
The source checkouts and raw transcripts are not part of this repository. The
four heads and accepted-page digests are in `validation/dogfood-docpr-3002.md`;
all units used tool version `0.2.0`. Read-only checks below used the current
`dogen.py` and `validation/score.py`, not the historical executables. This
distinction matters when attributing a fixed behavior to an earlier run.

## Reconstruction from committed records

| Local public run / unit | HEAD | Ledger SHA-256 prefix | Signoff / generations / accept seq | Basis and current pages |
| --- | --- | --- | --- | --- |
| Workshop Copilot / `mount-attribute-values` | `86b51bc` | `4ae088b36272a26b` | 2 / 4, 6 / 7 | accept cites generation and basis 6; 1 target current |
| Workshop Claude / `mount-attribute-values` | `796fedb` | `0faa7d46c8f3019d` | 2 / 4, 6 / 7 | accept cites generation and basis 6; 1 target current |
| Test Observer Claude / `verify-api-permissions` | `c4c94a7` | `0cec660d43149e3b` | 15 / 8, 12, 20 / 21 | accept cites generation and basis 20; 2 targets current |
| Lace Copilot / `device-tree-selection` | `dcb71f4` | `6674de4da903f30f` | 2 / 3, 5, 7 / 8 | accept cites generation and basis 7; 2 targets current |

For each run, `ledger.jsonl` is byte-identical to `HEAD`'s copy, its final
signoff's `plan_hash` equals the current `unit.md`, and the accept's `files[]`
digests equal the present page bytes. `dogen verify <unit> --json` reports
V1–V16 and V18 healthy (V17 is healthy in the original checkouts). Test
Observer and Lace report `ok`; both Workshop runs report `warn` because the
source they signed was also the target later revised (V19). The independent
`score.py audit <unit> --root <checkout>` exits 0 on each original. Its
`[context]` warning for those Workshop targets and `[report]` flags for
declared gaps are **informational**, not a clean-source or no-gap claim.

Each Workshop ledger records one reviewer-edit, a fix after the first
generation, then a replacement generation; Test Observer records one
reviewer-edit, six step records, two step plans and a re-sign before its last
generation; Lace records two fix verdicts before its last generation. Source
paths and baseline commits are on signoffs; source digests are in their
`context` maps. The final generations carry 11, 19, 13 and 5 origin strings
respectively, and 0, 9, 9 and 2 declared gaps. The older Workshop/Test
Observer origin strings include annotations that the newer protocol cannot
hash as paths; the corrected Lace report uses plain paths. Model names are
recorded as generation claims with `model_origin`, not authenticated identities.
Lace has no pre-existing Sphinx project build, and the earlier three runs do
not pass the full dogfood protocol; see `validation/dogfood-docpr-3002.md`.

## Claims and actual guarantees

| Public claim | Mechanism / negative evidence | Strength and limit |
| --- | --- | --- |
| A **recorded** substantial draft needs fresh signoff | `draft` refuses `no_signoff`/`plan_stale`; generation cites current signoff and plan hash (V5); A-08, V-01, N-19 | **Enforced for dogen transitions.** A manually written page outside dogen is not a recorded generation; a later plan edit is detectable, not prevented. |
| Accept cannot silently close an unapplied fix or redraft | Pending requests require explicit `--resolves` or reasoned `--withdraw` (V10); V-04 and Lace trial below | **Enforced as recorded disposition**, not proof that the requested prose changed; a reviewer can explicitly withdraw a request. |
| Accept seals the latest recorded generation | Accept cites last generation (V6) and latest basis `files[]`; all four real runs cite their final generation | **Enforced within the recorded sequence.** A later reviewer-edit can itself become the latest basis; a local history can be forged wholesale. |
| An accepted page edit cannot go unnoticed | `review accept` refuses `page_drift`; V14 reports status, independent oracle-3 checks current bytes; Lace trial below | **Detected, not made immutable.** V14 is status/warn, while oracle-3 gates its audit. Deleted pages, reversion to identical bytes, and history rewrites have different observability. |
| Source origins, gaps, evidence, model and version are honestly recorded | Signoff freezes local source commits/digests; actionable steps carry evidence hashes (V8/V9); generation report, model/origin, and tool version fields survive in committed ledger | **Mixed.** Shape and internal consistency are checked; report strings and model identity are author claims, external URLs are not locally verified, and a step digest does not prove where/how a command ran. Absent reports and unknown models are permitted and must be shown as such. |
| Ledger and Git prevent tampering | Canonical hash chain and committed-prefix check (V1–V4); trailer/ancestry corroboration (V15/V16); V-02 and Lace trial below | **Detection within the local trust boundary**, not tamper-proofing or remote attestation. Git history and a chain can both be rewritten by someone controlling the repository; missing/squashed trailers warn, not fail. Ignored staging is not committed provenance. |
| Independent audit reads only the selected repository | Previously `audit` joined an unchecked unit ID to `--root`, then read that ledger *before* invoking dogen, which refused the ID | **Now enforced:** audit rejects malformed IDs and paths resolving outside `--root`, including symlinks, before reading; three regressions cover traversal, link escape and matching the tool's ID alphabet. |

## Negative-path evidence and reproduction

`GIT_CONFIG_GLOBAL=/dev/null bash validation/fixtures.sh` builds hermetic
repositories from real verbs. V-01 attempts a draft after changing a signed
plan (`plan_stale`); V-02 changes a ledger digest (chain failure); V-03 removes
the reason for an unsteered generation; V-04 tries to accept with an
unresolved request (`unapplied_steering`). The independent audit flags all
four reached corruptions. The same suite now tests the audit read boundary.
`bash tests/test_dogen_acceptance.sh` covers missing signoff and malformed
target/identifier paths (A-06, A-08, A-11, A-31, A-33).
`bash tests/test_dogen_lifecycle.sh` covers every crash point and classifiable
recovery (N-37), truncated/uncommitted tails, malformed ledger lines and
refusals, so an interrupted append is not silently treated as a successful
transition.

Additional trials used separate, disposable clones of the public Lace commit
`dcb71f4`; none changed the original checkout:

| Mutation / attempt | Tool result | Independent reading |
| --- | --- | --- |
| Append to accepted `docs/explanation/device-tree-selection.md`; retry accept; commit the edit manually | `page_drift`; V14 `warn` and names the manual commit (`4c0a255`) | oracle-3 flags changed page SHA; audit exits 1 |
| Record a new steering request after accept; retry accept without disposition | `unapplied_steering`, pending seq 9 | an unchanged page cannot silence the recorded request |
| Change `unit.md` after signoff; retry accept | `plan_stale` | oracle-2 flags mismatched plan hashes; audit exits 1 |
| Change the final generation's committed digest while preserving valid JSON | `verify` fails V3, V4 and V6; `ledger_corrupt` exit 6 | oracle-1 flags the broken chain; audit exits 1 |
| Pass `../../../.dogen/units/device-tree-selection` with `--root <clone>/docs`, whose nested path reaches the real ledger | Before fix oracle-1 read that out-of-root ledger, then dogen refused the ID | After fix `FLAG [io] invalid unit id`, audit exits 1 without a ledger read; a symlink escape is also refused |

The disposable clones may report V17 warnings because an ignored staging
directory/configuration is not transferred by a shallow clone; those warnings
are not findings about the original accepted commits. `score.py audit` has
informational `FLAG` lines that do not gate: read its exit code and each line's
role, not the word `FLAG` alone. No trial proves that an attacker who can
rewrite every ledger line, the pages, all Git commits and their trailers
cannot make a self-consistent false history. Likewise, no local record proves
that a human rather than an agent made a recorded approval.
