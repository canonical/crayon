# dogen-write eval protocol (protocol-only)

A checklist for a passenger-branch drafting run in a fresh session on a weaker
model. Stand up a signed-off unit with `../dogen-review/setup.sh` STOPPED
before its draft step (comment the `$DOGEN draft` call out, or declare a unit
by hand in any repo); provider must resolve to `host-harness`. Capture
`git status --porcelain` before and after.

## First draft

- [ ] The unit state was read first (`unit show --json --latest`); the probe
      (`draft --resolve-only`) ran before any authoring; no skill-side
      environment probing.
- [ ] Declared sources were read in full; every file read appears in
      `report.yaml` with a hex-or-empty commit stamp; an empty `gaps` list
      carries a one-line `gaps_note`.
- [ ] **Three-check grounding spot-check:** pick 3 behavioral claims from the
      drafted page; the writer can point each at its source location
      (locate), the source actually says it (confirm), and a second in-repo
      signal exists for any "is supported" claim (corroborate). A must/only/
      cannot statement has a locatable enforcing validator.
- [ ] Coverage: every outline/acceptance item is on the page or a recorded
      gap; an outline-named inventory was read AND materialized (no `:ref:`
      punt).
- [ ] Stance check ran: no researcher register, no implementation
      identifiers, no runtime-mechanics narration in the page.
- [ ] The model was settled once (`dogen model set --origin self` + the one
      correctable line) or already stood in config.
- [ ] Writes stayed inside `.dogen/staging/<id>/` (handoff + report.yaml);
      the canonical page under `docs/` was written by the CLI, not the skill;
      porcelain shows only CLI transition commits.
- [ ] The closing summary quoted the `git: committed` hash and the frozen
      referral routed to /dogen-review.

## Re-draft (after a recorded fix verdict that invalidates a prior statement)

Record a `fix` verdict whose note contradicts one sentence of the draft (e.g.
"the retries default is wrong — the source says 2"), then invoke dogen-write
again.

- [ ] The re-draft refused to run on conversation-only correction; it
      proceeded only because the verdict was RECORDED (no
      `unsteered_redraft`).
- [ ] **Staleness-scan direction:** the invalidated sentence was rewritten or
      deleted IN PLACE — not left standing with a correction appended beside
      it.
- [ ] **Steering reconciliation:** the step 4 report accounted for every
      steering entry — applied (where) or declined (why, with TA agreement);
      none silently accepted or dropped.
