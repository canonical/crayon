Load this file at workflow step 3 (Present the provenance summary).

# Ledger field map

The unit's audit trail lives at `.dogen/units/<id>/ledger.md` (plain markdown,
pipe-delimited rows); the plan (with its sources) lives in
`.dogen/units/<id>/unit.md` front-matter. Read both directly — there is no CLI
summary verb. Present the fields below in plain language. This is the sidecar the
TA otherwise never sees; present it truthfully, including honest-empty values.

## Fields to surface

From `ledger.md`:

- **signoff** (`## signoff`) — who signed the plan off and when. Its `plan_hash`
  froze the exact `unit.md` approved: if the current `unit.md` no longer hashes
  to it (compute `sha256sum .dogen/units/<id>/unit.md` and compare), say the plan
  **changed since signoff** — the reviewer may want a re-signoff before judging.
- **steering** (`## steering`) — the append-only guidance stream: manual notes
  and automatic fix/redraft review-verdict notes, in order. Quote the latest;
  together with the `steering_notes` in `unit.md` it is what the most recent
  draft was steered by.
- **generations** (`## generations`, latest row) — the most recent draft pass:
  `model`, `provider`, `mode`, the page `file` and its `sha256`, `run_id`, and
  `steering_count`.
- **reviews** (`## reviews`, latest row) — the most recent verdict: `verdict`
  (`accept` / `fix` / `redraft`), and for an accept, the `sealed` page hash.
- **steps** (`## steps`, present only for actionable units) — each step's
  `status` (`resolved` / `unverified`) and `verdict`.

From `unit.md` front-matter:

- **sources** — the declared starting-point sources.
- **sphinx_target** — where the draft lands (the page the review covers).
- **intent** / **audience** / **title** — the declared direction and reader.

## The declared-vs-read gap

`sources` (declared starting points) and the writer's actually-read list (recorded
in the context report at `.dogen/staging/<id>/report.md`, if staged) are
deliberately distinct — the gap between them is audit-relevant. Surface it plainly:

- read everything declared and beyond → note the draft is grounded in the declared
  sources plus the named discoveries;
- read fewer / different origins than declared → surface the discrepancy so the
  reviewer can weigh it;
- no report staged / nothing recorded → present the honest-empty fact; it is a
  review signal, not an error to hide.

Do not invent, fill, or smooth over any field. If a value is missing or empty,
present it as missing or empty.

## Presentation

Fold these into the `### Provenance` block presented in both modes, ahead of the
verdict. Keep it to: the signoff line (with plan freshness), the latest generation
(model / provider / mode / file / hash), the declared-vs-read comparison, the
steering-stream count (latest quoted), and the derived progress state (pending →
drafted → reviewed, derived from whether `## generations` and `## reviews` are
non-empty).

For a unit that carries a step plan (`## steps` non-empty), a **quality-signals
block** follows in both modes: tally the step verdicts (`deviated` / `skipped` /
`fail`) and read the `reason` fields for the episode color. A step-free unit shows
nothing extra here.