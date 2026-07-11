Load this file at workflow step 1 (Read the unit state and probe the provider).

# Provider branch + reference-page authoring guidance

Four things this reference holds: the reason-code→branch map dogen-write keys off,
the per-format authoring standards for the passenger branch (MyST and rST, v1.2),
the stance contract (v1), and the context-report shape (v1). The SKILL.md keeps the
decision logic; this file holds the relocated detail.

## The resolve-only branch

Run the zero-side-effect probe, then branch on the reported provider name (D-08):

```bash
PROVIDER=$(dogen draft "$UNIT" --resolve-only --json \
  | python -c "import sys, json; print(json.load(sys.stdin)['provider'])")

case "$PROVIDER" in
  copilot|mock)
    # DRIVER: the provider generates in-process behind its bounded READONLY
    # toolset and observes its own reads. Invoke and report — author nothing,
    # Write nothing. (A multi-file unit refuses here with
    # multi_target_unsupported — route through the passenger.)
    dogen draft "$UNIT" --json
    ;;
  host-harness)
    # PASSENGER: the host authors the page(s) in the unit's format (declared
    # sources as starting points, free navigation beyond them), Writes the
    # handoff + the context report, self-asserts the model once per repo, then
    # records everything.
    # Self-assert the model first (D-01) — once per repo; afterwards the model
    # resolves from config by flag > env > config, so you do NOT force --model:
    dogen model show --json    # {model, source, model_origin} — check what's set
    # No model set yet -> self-assert it (origin self) + narrate the one
    # correctable line; a TA correction re-runs with --origin ta:
    #   dogen model set "$HOST_MODEL" --origin self
    #   # "recording model X (self-asserted) — correct me if wrong."
    #   dogen model set "$TA_NAME" --origin ta   # TA vouched -> origin flips
    # Single-page unit — handoff carries the target's own extension:
    EXT="${TARGET##*.}"                 # from unit show --json .unit.sphinx_target
    HANDOFF=".dogen/staging/$UNIT/handoff.$EXT"
    REPORT=".dogen/staging/$UNIT/report.yaml"
    dogen draft "$UNIT" --draft-file "$HANDOFF" --report "$REPORT" \
      --provider host-harness --json   # model resolves from config (D-01/D-12)
    # Multi-file unit — stage handoff/<target-relpath> for EVERY page, then:
    # dogen draft "$UNIT" --draft-dir ".dogen/staging/$UNIT/handoff" \
    #   --report "$REPORT" --provider host-harness --json
    ;;
esac
```

The resolved name is the ONLY branch signal — never probe the environment yourself.
Selection is explicit in v1 (flag > `DOGEN_PROVIDER` env > repo config >
`host-harness`); there is no `auto` and no silent fallback.

## Reason-code → plain-language TA guidance

Map the CLI `reason` codes (from `--json`) to plain language; do not coin new status
words (D-03; the shared vocabulary lives in `../README.md`):

| reason | what to tell the TA | route |
|--------|---------------------|-------|
| `signoff_required` | "This unit hasn't been signed off yet — dogen won't draft without a recorded signoff." | back to dogen-plan |
| `backend_unavailable` | "The Copilot backend can't be reached right now." | retry later, or use host-harness |
| `model_rejected` | "The requested model `<model>` was refused by the backend." | retry without `--model`, or pick another |
| `unit_exists` (not found) | "No unit with that id exists." | check the id / declare via dogen-plan |
| `bad_report` | "The context report failed validation" (unreadable YAML, or a commit stamp that is neither hex nor empty). | fix the report; prose explanations go in an origin's `note` |
| `handoff_incomplete` | "A declared page has no staged file in the handoff directory." | stage/move each page at its exact `handoff/<relpath>` (a flat handoff with unique basenames is now accepted), then re-record — never delete a staged draft to fix layout |
| `undeclared_target` | "The handoff stages a file outside the unit's declared target set." | move the stray file into place or amend the plan (`--also-target`) first — do not delete staged drafts |
| `multi_target_unsupported` | "This provider drafts a single page; the unit spans several." | run the host-harness passenger branch |

The success object may additionally carry:

- `commit` — the transition commit's hash (also printed as a
  `git: committed <sha7> — …` stderr line). Quote it in the closing summary.
- `stale_plan: true` — the plan changed after its signoff. Surface it; suggest
  re-approving (`dogen signoff --re-sign`, or folding the re-approval into a
  future amendment via `dogen unit edit … --re-sign`).
- `unsteered_redraft: true` — a re-draft ran with no recorded steering or review
  verdict since the last generation; the correction lived only in conversation.
  Surface it and get the correction recorded (`dogen review --verdict fix` /
  `dogen steer --note`) so the audit trail shows what steered the pass.
- `model_unrecorded: true` — the generation recorded an empty model (no model in
  the repo config and neither the self-assert nor the TA fallback named one).
  Self-assert it first — `dogen model set <name> --origin self` (the persisted,
  once-per-repo path), or `--origin ta` for a TA-supplied name — then
  `dogen draft <id> --amend-model <name>` to stamp the already-recorded
  generation; or state plainly the model is unknown. Honest-empty is legal, but
  it must be a surfaced choice, not a silent miss (M4, R4).

## The context report (report.yaml — the v1 provenance contract)

Every passenger draft ships a report of what actually grounded it. Shape (validated
by the CLI against `dogen.core.models.ContextReport`):

```yaml
context_origins:            # EVERY file you read while grounding the draft
  - path: internal/workshop/workshop_file.go
    commit: <git rev-parse HEAD>     # one HEAD stamp for the whole session
  - path: tests/main/interface-plug-binding/workshop.yaml
    commit: <same>
  - path: vendor/example/dep.go     # out-of-repo / unpinnable read:
    commit: ""                       # stamp stays honestly empty…
    note: external dependency, pinned by go.sum at v3.0.1   # …prose goes here
tools_used: [Read, Grep, Glob]
gaps:                       # facts you could NOT verify at their origin
  - "per-interface attribute semantics live in the SDK implementations, not read"
gaps_note: ""               # REQUIRED (one line) when gaps is empty — why
                            # nothing was left unverified; never a default
```

Rules: list reads exhaustively (the declared-vs-read gap is audit-relevant, D-37);
stamp `commit` from one `git rev-parse HEAD` run — a stamp is a **hex SHA or
honestly empty** (the CLI refuses prose there with `bad_report`; explanations
belong in the origin's `note`); `gaps` is the stance contract's outlet — anything
that would otherwise become hedged prose goes here instead. An empty `gaps` list
needs a one-line `gaps_note` justification: "nothing unverified" is a claim, not
a default. An empty report is legal but must be true.

## Source policy (v1): starting points, not a boundary

The unit's declared `sources` are the primary grounding and where reading starts —
read them in full. Beyond them, navigate the repo freely wherever a fact's origin
lies: implementations behind a schema, fixtures, sibling pages, the repo's own docs
conventions, and `.dogen/context/` artifacts when present — `doc-style.md` and
`glossary.md` set voice and vocabulary; grep `code-to-docs-map.md` for the code
area at hand (it can be very large) to find the neighbouring documented
concepts. The grounding rule is: **every claim traceable to
something you actually read and recorded** — stronger than any boundary, because it
is auditable. Suggest promoting load-bearing discoveries:
`dogen unit edit <id> --add-source <path>`.

## Stance contract (v1 — governed mirror)

Canonical source: `dogen.core.authoring.STANCE_CONTRACT` — keep this section in
sync; the drift guard binds this file to the anchor sentence.

> Write as the product's reference, never as a researcher describing their evidence.

State what the product accepts, does, and enforces — not what you observed while
reading. Banned register: "observed", "the fixtures show", "every observed use",
"the corpus", "at this level". When a fact cannot be verified from what you have
read, navigate to its origin and verify it there; if it still cannot be verified,
leave it out of the prose and record it as a gap in the context report — confidence
gaps are provenance, not content. The same discipline covers **runtime mechanics**:
how the machinery executes internally (temporary files, interpreter invocations,
internal process flow) is implementation, not interface — describe the behaviour
the reader can rely on, never the mechanism, even in declarative voice. Before
recording, grep your draft for the banned register, for implementation
identifiers, and for runtime-mechanics narration; fix any hit.

## Thin reference-page standards (passenger authoring, per format)

Author for the **reference** Diataxis direction only (dogen drafts no other type
this cycle). **The unit's `format` field decides the markup** (v1.2) — the target
extension IS the format, and it was chosen at plan time to match the page's
siblings. Never write one markup into the other's extension: MyST fences in an
`.rst` file render as literal text, and bare rST directives in a `.md` file do
the same (round 2 paid fix cycles for both directions). For a multi-file unit,
each page follows its own extension's standard.

### MyST (`.md` targets)

- **Directives / roles:** use `colon_fence` for directives — a fenced block opened
  with three colons, e.g.:

  ````
  :::{note}
  Reference note body.
  :::
  ````

- Anchors are `(label)=` lines; cross-references `{ref}`. Field inventories are
  `{list-table}` colon-fences or pipe tables — pick ONE style per page and keep
  headings on one ladder (no mixed setext/ATX).
- Reusing rST snippets (e.g. shared `_interfaces/*.rst` includes) from a MyST
  page requires an `{eval-rst}` fence around the `.. include::` directives.

### reStructuredText (`.rst` targets)

- **Whitespace is load-bearing** — the malformed-output risk rST carries is the
  reason to be strict here: directive bodies indent exactly 3 spaces under the
  directive; a blank line separates the directive line, options, and body.
- **Headings:** underline (no overline) at least as long as the title text; keep
  ONE ladder for the page, matching the siblings' convention (commonly `=`, then
  `-`, then `~`, then `^`); no skipped levels.
- **Directives:** `.. note::`, `.. list-table::` for field inventories,
  `.. literalinclude::` / `.. include::` with paths relative to the page's
  committed location, `.. code-block:: yaml` for reader-authored snippets.
- **Anchors / cross-references:** `.. _label:` targets and `:ref:`label``
  roles; match the sibling pages' label naming convention.

### Both formats

- **Shape:** reference is information-oriented and neutral — describe the machinery
  accurately and completely (each item, its type, default, bounds). State what is;
  do not teach or narrate. One category per page.
- **Show vs. reference (code-in-narrative):** rooting a draft _in_ the code you read
  is not the same as surfacing that code _in_ the narrative.
  - _Default:_ document behaviour — fields, types, defaults, bounds, constraints — in
    prose and tables, and refer to code entities by qualified name (`package.Type`,
    `package.Function`). Do not reproduce their source.
  - _Exception (closed list):_ show a minimal code block only when the reader
    themselves authors or invokes it — a minimal input/config, a public signature or
    CLI/API call, or a short snippet that cannot be stated in prose.
  - _Never show:_ implementation bodies, private internals, or verbatim struct/function
    source lifted from the sources.
  - _Per-block heuristic (verbatim from the canonical constant):_
    Per block, ask: would the reader themselves type, author, or invoke this exact text? If so, a minimal version may be shown; if instead it is how the machinery is implemented internally, reference it by qualified name and never show it.
  - Canonical source: `dogen.core.authoring.REFERENCE_CODE_RUBRIC` — keep this section
    in sync.
- **Grounding:** assert only what you actually read supports. Do not invent
  defaults, bounds, or availability nothing you read confirms.
- **Headings:** a single top-level title, then a clean heading ladder; no skipped
  levels.

This is intentionally thin (D-04): one supported Diataxis type does not yet justify a
shared normative STYLE_GUIDE. dogen-review judges the draft against these same stated
criteria.
