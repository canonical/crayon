Load this file at workflow step 3 (Present the provenance summary).

# Provenance field map

The unit's audit sidecar lives at `.dogen/units/<id>/provenance.yaml`; the lifecycle
state lives at `.dogen/units/<id>/progress.yaml`; the plan (with its sources) lives
in `.dogen/units/<id>/unit.md` front-matter. `dogen unit show <id> --json --latest`
returns everything the review needs in one lean read: the review only ever needs
the **latest** generation, and `--latest` keeps the older passes' full read-lists
out of your context (`generations_count` still reports how many passes ran; the
complete history stays on disk for audits). Present the fields below in plain
language. This is the sidecar the TA otherwise never sees; present it truthfully,
including honest-empty values.

## Fields to surface

From `provenance.yaml` — the gate act and the guidance stream (v1):

- **signoff** — who signed the plan off and when. Its `plan_hash` froze the exact
  `unit.md` approved: if the current `unit.md` no longer hashes to it, say the plan
  **changed since signoff** (the reviewer may want a `dogen signoff --re-sign`
  before judging — or, when the review itself orders the amendment, the folded
  `dogen unit edit … --re-sign`). Its `commit` stamps **the plan state the signoff
  covered** — the last commit that changed `unit.md` before the act, not the
  signoff commit itself (the signoff records into the same tree it froze). This is
  correct, not a bug; it reads as surprising only in a raw `git log`.
- **signoff_history** — superseded gate acts, oldest first (v1.2): every
  re-approval archives the act it replaced, so each previously approved plan
  hash survives in the tip artifact. Mention the count when non-empty ("re-signed
  N time(s); prior plan hashes on record").
- **steering** — the append-only guidance stream: manual `dogen steer --note`
  entries and automatic fix/redraft review-verdict entries, in order. Quote the
  latest; together with the seeded `steering_notes` in `unit.md` it is what the
  most recent draft was steered by.

From `provenance.yaml` — the latest entry in `generations[]` (the most recent draft
pass):

- **provider** / **mode** — the provider that ran and its role (`driver` generated
  in-process; `passenger` means the host authored and dogen recorded).
- **model** / **model_version** — the model identity. For a passenger run this is
  host-asserted (or empty/unknown when the harness hid it) — say so.
- **model_origin** — **who vouched for the model** (the D-03 vocab), read
  alongside model/provider/mode: `ta` a human vouched (a TA-run
  `dogen model set --origin ta`, or a `--amend-model` correction); `self` the
  drafting agent self-asserted it (the frictionless once-per-repo default);
  `config` a persisted model carrying no recorded origin (e.g. hand-edited);
  `flag` an operator override (`--model` flag or `DOGEN_MODEL` env at invocation);
  empty (`""`) when no model was recorded at all (`model_unrecorded`). It tells the
  reviewer not just *which* model but *on whose authority* it was recorded — a
  `self`-only model on a deep-internals draft is a weaker signal than a `ta` vouch.
- **context_origins** — what the writer **actually read**, each entry stamped with
  the commit it was read at (hex, or honestly empty with the explanation in the
  entry's `note` — v1.2). For a passenger run these come from the writer's own
  context report.
- **gaps** — facts the writer could not verify at their origin and deliberately
  left out of the prose. Surface them verbatim; they often seed the next steering
  note. An empty list should carry a **gaps_note** justification (v1.2) — empty
  gaps with no note next to deep internals reads is the overconfidence pattern;
  surface its absence as a review signal.
- **files** — the per-page digests of everything the pass wrote (v1.2; primary
  first). For a multi-file unit this is the page set the review covers. The `path`
  of each digest is where the draft was sealed — check it lands at
  `docs/<sphinx_target>` with a single `docs/`; a doubled `docs/docs/…` seal means
  the page is bound to a slot the toctree never references (a build-breaking
  placement finding — route the fix through `dogen unit edit --target … --re-sign`,
  never a raw `mv`).
- **source_commit** / **draft_sha256** — the code version the draft describes and
  the exact text recorded (mention only if useful).

From `unit.md` front-matter:

- **sources** — the declared starting-point sources, each with its commit stamp and
  role (`primary` = human-pointed at planning; `discovered` = promoted during
  drafting).

From `progress.yaml`:

- **state** — the current progress state (`pending` / `sourced` / `drafted` /
  `reviewed`).

## The declared-vs-read gap

`sources` (declared starting points) and `context_origins` (actually read) are
deliberately distinct fields — the gap between them is itself audit-relevant.
Surface it plainly:

- read everything declared and beyond → note the draft is grounded in the declared
  sources plus the named discoveries;
- read fewer / different origins than declared → surface the discrepancy so the
  reviewer can weigh it;
- `context_origins` empty against non-empty `sources` → present the honest-empty
  fact ("the writer recorded reading nothing"); it is a review signal, not an
  error to hide.

Do not invent, fill, or smooth over any field. If a value is missing or empty,
present it as missing or empty.

## Presentation

Fold these into the `### Provenance` block presented in both modes, ahead of the
verdict. Keep it to: the signoff line (with plan freshness), the
provider/mode/model/origin line, the declared-vs-read comparison (with commit stamps), the
writer's gaps, the steering-stream count (latest quoted), and the progress state.
Priority tags belong to the review-mode findings (step 4), never here: the
run-status reason codes and progress states stay surfaced verbatim (D-03: use the
CLI's status vocabulary only for run-status).

For a unit that carries a **step plan**, a **quality-signals block** follows (see
below) in both modes; a step-free unit shows nothing extra here.

## Quality signals (units with steps only)

This block surfaces the walk's REC-09 quality signals — **derived**, never a new
stored field and never a new review dimension. It appears in **both record and
review modes**, but **only for a unit that carries a step plan**
(`provenance.steps` non-empty). A step-free reference / explanation unit shows
**no** quality-signals block at all — its provenance presentation stays
byte-identical to before this block existed.

Two derived sources, both already on disk:

- **Counts from `dogen record show <id> --json`.** Tally the per-step `verdict`
  wire values (the D-05 vocabulary, surfaced verbatim): how many steps recorded
  `deviated`, how many `skipped`, and how many `fail`. `deviated` and `skipped`
  each carry a reason (D-06); a `fail` is a step that never resolved. These map
  onto the walk's episode taxonomy — a **deviation** is improvisation (the
  planned step didn't say how, so the agent or TA had to figure it out), and a
  repeated `fail` on one step is frustration (D-15). Surface the three counts
  plainly, e.g. "N deviated, M skipped, K failed (of T steps)".
- **Episode notes from `git log`.** Each `record step` writes one
  `step-recorded` commit whose `Dogen-Step` / `Dogen-Verdict` trailers name the
  step and its verdict, and whose body carries the `_body_note` reason for a
  `skipped` / `deviated` step (the Phase-12 bounded-body precedent). Read them
  (`git log --grep='Dogen-Step'`, scoped to the unit's step-recorded commits) and
  quote the reason bodies — they are the free-text episode color the counts alone
  cannot carry.

**Honest-empty, the same stance as the rest of this file:** a unit whose steps
all recorded `pass` has **zero** deviations / skips / fails — surface that as an
honest "no flagged episodes (all N steps passed clean)", never omit the block.
Zero is a signal, not an absence to hide.

Do not invent a stored step flag and do not add a review dimension for this: the
signals are purely derived from `record show` counts plus the git-log reason
bodies. The review rubric carries one line (review mode) telling the reviewer to
**weigh** the sections these signals flag — the weighing happens in the findings
review, never as a re-grade here.
