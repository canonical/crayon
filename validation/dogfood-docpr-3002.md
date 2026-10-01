# DOCPR-3002: local dogfood findings

This record covers three public candidates and four local, unpushed dogen legs.
The candidate assessment selected the projects; each page was grounded in its
candidate's own sources. Candidate commits and raw transcripts remain in
separate local checkouts, not in this repository.

| Leg | Public source commit | Accepted local commit | Output SHA-256 |
| --- | --- | --- | --- |
| Workshop / Copilot CLI, `mount-attribute-values` | `edae26b7e5064dbe2084cffc46734aee0283d8a3` | `86b51bc` | `9e5e929dd8154595b5d8079648b4540bb6d21312c2b7649b51e52bed9675adba` |
| Workshop / Claude Code, same task | `edae26b7e5064dbe2084cffc46734aee0283d8a3` | `796fedb` | `ed5eb81bbeecaa80d227761f7f2264b353ce4932222e931fc2e933b64386b2f7` |
| Test Observer / Claude Code, `verify-api-permissions` | `1563e2af03d204d768e7aad94222d28a729fb4c8` | `c4c94a7` | `94fd1fd3e031c12f4ee906ae420866080fa917f70ad3ade7a69f5a6706a3b6f8` |
| Lace / Copilot CLI, `device-tree-selection` | `2e0ad13c64d7a30e2d24af9a034363abcf688762` | `dcb71f4` | `6743144c5a6d041751e42e6c9f8bad76552a3d8df133cfa64ec98b35e55ac8c2` |

The digests are for the primary page in each accepted unit: Workshop
`docs/reference/definition-files/_interfaces/mount.rst`, Test Observer
`docs/how-to/verify-api-permissions.rst`, and Lace
`docs/explanation/device-tree-selection.md`. Each leg has a recorded human
signoff and final accept; no candidate branch was pushed. The two Workshop
onboarding outputs differed, despite the matched source commit and task, so
their drafts support a qualitative comparison, not a controlled
harness-only quality claim. Both revisions corrected the shared mount
snippet's `workshop.yaml` string forms without misdescribing SDK and SDKcraft
integer/boolean schema values. The first Workshop drafts needed one fix each.

Test Observer's how-to needed two fixes: to keep a contributor link out of the
Authentication group, then to replace a dogen-only scratch path with a
portable temporary-copy demonstration. A newly approved three-step offline
walk captured both checker outcomes and cleanup; the published commands were
also run from a normal clone after acceptance, without changing its committed
schema. Lace started without a `docs/` tree or recorded context. Its MyST
explanation needed an index toctree and then a shorter, author-focused
revision. Its declared public raw-file URL was pinned to the Lace source
commit; the unit records the URL while the report names the corresponding
repo-relative source path. No URL was falsely entered as a local digest path.

## Build and validation evidence

| Leg | Sphinx before / after | Independent audit and limits |
| --- | --- | --- |
| Workshop / Copilot | exit 0 / 0; 101 / 97 diagnostic items; 0 new, 4 resolved | `score.py audit` exits 0; `dogen verify` warns about the signed source also being the revised target, with no failing checks. |
| Workshop / Claude | exit 0 / 0; 101 / 97 items; 0 new, 4 resolved | Same audit and verification outcomes; remaining confidence gaps are explicitly recorded. |
| Test Observer / Claude | exit 0 / 0; 15 / 14 items; 0 new, 1 resolved | `score.py audit` exits 0; `dogen verify` reports `ok`. The missing-key variant and schema regeneration were not walked. |
| Lace / Copilot | **No pre-existing Sphinx build** | With a temporary external MyST configuration, a strict Sphinx build (`-n -W`) passes; `dogen verify` reports `ok`. This is not a before/after project build. |

The existing Sphinx diagnostics in the other three legs include shallow-clone
warnings; zero *new* items is the checked property. The three completed
`RUN-*.json` files have post-session transcript SHA-256 values. Lace's local
Copilot `events.jsonl` digest after acceptance is
`c95858c7d2fe0c2bf29cf48a3fc08b77f14e11ff61b3b2e33c8b27905bc653ad`;
no raw transcript is checked in. Signoff-to-accept wall-clock intervals,
including human review waits, were 1h14m13s and 1h07m24s for Workshop,
37m37s for Test Observer, and 10m31s for Lace. These are not active authoring
times; installation was not timed and several question/command metrics were
not measured rather than assigned invented values.

**The validation protocol does not pass in full.** Earlier harness versions
put revisions and prose in `origins[]` strings. `runmeta.sh` hashed absent
paths on both sides, producing a misleading equality. The repaired
`score.py protocol` now flags those origins in the three older `RUN` files;
their pre-registered leg/rubric files are also absent. Lace has no comparable
baseline Sphinx tree or `RUN` file. `score.py audit` treats report gaps as
informational; its exit 0 is not a protocol pass.

## Changes established by the runs

- `dogen.py` refuses unknown report keys and object/non-string entries rather
  than dropping `files_read` or stringifying structured provenance. A fresh
  Lace run with the corrected tool deliberately received `bad_draft_path`
  (exit 2) for `files_read`, then recorded a valid plain-path report and draft.
- `skills/dogen-write/SKILL.md` specifies the exact report shape and
  repo-relative paths; `validation/score.py` refuses an apparent context
  match over missing/stamped sources. The scorer regression covers the
  previously vacuous equal-digest case. The offline eval histories were
  regenerated mechanically after the skill change.
- `validation/runmeta.sh end --transcript-file <path>` records an explicit
  Copilot transcript path, refuses absent or empty inputs, and still leaves
  the digest for an outside-session observer. Focused regressions cover
  these cases.
- `tests/test_dogen_acceptance.sh` checks the exact invalid-verdict choices
  without depending on argparse's version-specific quotation marks; Python
  3.14 exposed that brittle gate assertion while the tool behavior remained
  correct.
- `docs/development.md` documents provenance, transcript capture, and
  unauthenticated visibility checks. One assessed candidate was found to be
  nonpublic **after** a preliminary onboarding pass; it was excluded before
  any unit declaration or draft, and no nonpublic source or transcript is
  included here. An authenticated clone is not proof of public visibility.

To reproduce the public-unit checks from a local candidate checkout, run
`dogen verify <unit> --json` and
`python3 /path/to/dogen/validation/score.py audit <unit> --root <checkout>`.
Run `score.py protocol <checkout>/validation` to see the deliberately
unresolved older provenance and missing leg-file flags, not to claim a
complete protocol result. The candidate commits are local-only identifiers.
