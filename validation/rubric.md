# Validation rubric — scoring crayon drafts against a reference bar

**Dev-time evaluation material only.** The reference docs — a hand-written
reference set kept in a checkout outside the repository under test, pointed at by
`$REFERENCE_DOCS` — are the measuring stick, never an input: no drafting session,
skill, or steering note may point at them. Score the accepted
draft of each leg after the run.

Two layers: the mechanical scorecard (`score.py` — run it first) and the human
dimensions below. Score each human dimension 0–2 (0 = fails, 1 = partial,
2 = meets the bar) and note evidence.

**The unfilled-score token is `UNSCORED`.** Every score cell in this file and in every
`validation/legs/<leg>.md` reads `UNSCORED` until that leg's accepted draft has actually been
scored, at which point it is replaced by `0`, `1` or `2`. One token, one spelling, so
`python3 validation/score.py protocol` and a human reader look for the same string. A cell that
still reads `UNSCORED` is an unscored dimension: it is never read as a pass, and it is never
quietly deleted. Where a dimension cannot apply to a leg at all — §3b against a single-target
unit — the cell reads `n/a`, stated rather than left blank.

| dimension | reference leg (`workshop-definition`) | actionable leg (`validate-workshop-definition`) |
| --- | --- | --- |
| 1. Coverage parity | `UNSCORED` | `UNSCORED` |
| 2. Register & fidelity | `UNSCORED` | `UNSCORED` |
| 3. Structure & format hygiene | `UNSCORED` | `UNSCORED` |
| 3b. Cross-page consistency | `UNSCORED` | `UNSCORED` |
| 4. Loop quality | `UNSCORED` | `UNSCORED` |
| 5. Cross-leg comparison | `UNSCORED` | `UNSCORED` |

Scores are **recorded per leg** in `validation/legs/<leg>.md`, under that file's rubric
instantiation — that is where `protocol`'s sixth check reads them, and that is the single
authoring site. The table above is the rubric-side summary: it is transcribed from those files
once a leg has been scored, and never the other way round.

## 1. Coverage parity (vs `workshop-definition.rst` + `_interfaces/`)

The human-written reference covers, in order: filename and location rules;
top-level fields (as a table); nested structures (SDK entry / plug-or-slot entry
/ connection entry / action entry); the per-interface attribute inventory; a
schema pointer; worked examples; see-also. The draft must cover the equivalents
**as derivable from this repo's code** (terms follow this repo, e.g.
`workshop-target`/`workshop-source` mount attributes):

- [ ] file locations: `workshop.yaml` / `.workshop.yaml` / `.workshop/<name>.yaml`
- [ ] `name` — pattern rule + 40-char limit
- [ ] `base` — supported-image rule
- [ ] `sdks` — entry fields: name, channel, plugs, slots
- [ ] name-prefix source rules: plain (store), `try-`, `project-`, `system`,
      sketch/implicit SDKs
- [ ] plugs: bind-vs-inline-attributes rule, bind target syntax
      (`<sdk>:<name>`, `:<name>`), binding constraints
- [ ] slots: freeform attribute map, no bind form
- [ ] interfaces inventory — all seven, with observed-in-this-repo attributes
      stated as facts: mount (workshop-target / workshop-source / read-only),
      tunnel (endpoint), camera, gpu, desktop, ssh-agent, custom-device
      (subsystem in the SDK-definition schema)
- [ ] connections — plug/slot pair syntax + validity rules
- [ ] actions — name pattern, script forms (one-line / block)
- [ ] validation-constraint summary (what loading rejects)
- [ ] at least one complete worked example with realistic values

Score 2 = every box; 1 = ≥ 90%; 0 = below. (score.py `[cov]` automates most of
this; hand-check what greps can't.)

## 2. Register & fidelity

- Impersonal, present-tense reference voice; states what the file accepts and
  what loading enforces — **never** what the writer observed while reading
  (score.py `[reg]` catches the banned phrases; also read for subtler narration).
- No implementation identifiers in prose (score.py `[impl]`); code entities only
  where the reader types them.
- No runtime-mechanics narration: how the machinery executes internally (temp
  files, interpreter invocations, internal process flow) is implementation, not
  interface — flag it even in flawless declarative voice (round 1's leak:
  "executed as `bash -elo pipefail <path>`").
- Spot-check 5 concrete claims (a default, a bound, a constraint, an attribute,
  a rejection rule) against the code at the generation's `source_commit`. All 5
  must hold. Score 2 = clean; 1 = one miss; 0 = more.

## 3. Structure & format hygiene

- **Format** (round 3): the page is valid markup for its own extension —
  unit 1 is rST (underlines ≥ title length on one consistent ladder, 3-space
  directive indentation, no MyST fences); a `.md` page would use MyST with
  `colon_fence` and `{eval-rst}` around reused rST snippets. Wrong-markup
  content (round 2: bare rST directives in a MyST page, two fix cycles) caps
  this dimension at 0.
- **Placement**: the page sits in the waiting toctree slot
  (`docs/reference/definition-files/`) under the slot's exact basename AND
  extension — set at plan time via `--target`. Docs-root placement or a
  divergent basename (round 1: `-yaml` suffix) caps this dimension at 1.
- **Include/link resolution from the committed location**: every relative
  `literalinclude`/include/link resolves from where the page actually lives —
  round 1 shipped `../../examples/` paths that escape the repo; that class of
  defect is an automatic 0 here.
- Single H1; unbroken heading ladder; tables for field inventories; `colon_fence`
  for admonitions; anchors/cross-refs resolve within the page.
- Section ordering serves lookup (a reader can find one field without reading the
  page top-to-bottom) — the reference set's ordering above is the proven shape.

## 3b. Cross-page consistency (unit 2, the multi-file exercise)

- Both pages were declared as ONE unit (`--also-target`), drafted through one
  `--draft-dir` pass, and sealed together (the accept's `files` digests cover
  both) — a page revised outside the unit's recorded pass scores 0 here.
- The unified JSON Schema sections read identically apart from the schema each
  exports; terminology matches across the set; nothing outside the bounded
  change drifted (diff the rest of each page against the baseline — it must be
  verbatim).

## 4. Loop quality (per leg, not per draft)

Graded against the v2.0 event vocabulary (contract §5.3 and §5.4): every clause below names an
event kind or a field that exists on disk in `.crayon/units/<id>/ledger.jsonl`, so a finding here
is a statement about the record rather than about a recollection.

- Findings in review mode were grounded — the reviewer re-checked claims against the sources,
  not merely against the draft.
- **Corrections landed before the re-draft.** Fix and redraft notes reached the steering stream
  as `steering` events *before* the re-draft ran, and the re-draft applied them. The v1 clause
  keyed on a retired sidecar field (`unsteered_redraft`); v2.0 records the same fact on the
  `generation` event itself — `unsteered: true` must carry an `unsteered_reason`, written with
  `draft --unsteered-reason`. A correction carried informally is a loop-quality failure even
  when the draft came out right.
- **Reviewer edits are legitimate.** A hand edit adopted into the record through `crayon edits`
  (or `crayon resume --adopt`) is the supported brownfield path and is **not** a finding: it
  appends a `reviewer-edit` event whose `files[]` is the complete basis set. What *is* a finding
  is a hand edit that never reached the record — bytes on disk that no `reviewer-edit` accounts
  for. The v1 clause forbidding hand-editing from being offered is deleted; it graded a loop
  that no longer exists.
- **`already_accepted` is a harness-behaviour finding only when the retry carried no new
  information.** A second accept attempt that carried something new — a further `steering` note,
  a fresh `reviewer-edit`, a changed basis — is the loop working and is not flagged. A bare
  retry of an accept the tool had already sealed is the finding.
- **Review routing stayed deterministic.** Every verdict was recorded through `crayon review`
  rather than inferred from prose; the routing token the tool emits on its `next` key was
  followed rather than second-guessed; and every accept disposed of each pending request
  explicitly, through `--resolves` or `--withdraw <seq> "<reason>"`. Nothing was closed by
  silence — contract §5.4 derives `pending` from the steering and non-accept review events minus
  the seqs a later accept `resolves` or `withdraws`, so an undisposed request stays visible in
  the record.
- **Routing voice.** Every next step the skills surfaced to the author spoke skill language
  ("invoke crayon-write…"), never a raw `crayon …` command line; and each phase's closing summary
  **quoted** its committed sha from the tool's own output rather than asserting one. An
  asserted-but-unquoted commit is a blindness, not a record.
- **Stale-plan handling.** A reviewer-ordered plan amendment went through the tool's re-sign
  path — `crayon unit edit … --re-sign`, or an explicit `crayon signoff --re-sign` — which appends
  a fresh `signoff` whose `plan_hash` matches the amended `unit.md`. Drafting on a stale plan and
  clearing it afterwards is a finding.
- **The context report is exhaustive-looking and the gaps are honest.** `origins[]` on the
  `generation` event approximates what a human would have had to read, and an empty `gaps[]`
  beside deep internals reads is overconfidence. In v2.0 an empty gap list must carry a
  `gaps_note`; its absence is the same overconfidence finding. One v1 companion clause cannot be
  graded at all and is retained as a statement rather than dropped in silence: `origins[]` is now
  a list of **plain strings**, so the v1 requirement that every read carry its own commit stamp
  is not merely unmet — it is inexpressible, and no leg is scored against it.
- **Reads converted.** An inventory the writer read and did not surface in the page is the
  flagship completeness miss.
- **The step walk resolved.** Where the leg is actionable, every step the `steps-planned` event
  listed reached a recorded resolution through `crayon step` — a `step-recorded` event carrying a
  `verdict` and, where the contract requires one, its `reason` — and the evidence was captured
  (`output_sha256`, `output_excerpt`) rather than claimed. A `fail` never resolves a step;
  contract §5.4's `resolved ≠ executed` is the reading. A reference leg has no step plan and is
  not scored on this clause.

## 5. Cross-leg comparison (reference vs actionable)

**Scope.** rev8 §10 scopes the v2.0 legs to a single harness, so the cross-harness comparison
this section described in v1 cannot be made and is not reproduced here. The harness set it named
is out of scope for v2.0 and is deliberately not restated, so that nothing in this file points a
later reader at a comparison the v2.0 legs must not chase.

**Scored only if the actionable leg runs.** This section needs two legs. If the actionable leg
does not run, its scorecard cell stays at the unfilled token and this section is recorded as
**unscored** — never inferred from the reference leg alone, never closed by a stand-in session,
and never recorded as a gap that will close at some named time.

What the two legs can be compared on, when both exist:

- **Event shapes and trailer discipline are identical across legs** — the same event kinds in
  the same order for the same transitions, and the same `Crayon-Unit` / `Crayon-Phase` /
  `Crayon-Seq` / `Crayon-Head` / `Crayon-Verdict` trailer set on each commit. A divergence here is
  a finding about the tool or the skills, not about the draft.
- **Draft-quality differences per dimension** (§1, §2, §3, §3b), attributed where possible to
  the model claim recorded on the `generation` event (`model` / `model_origin`), to the unit's
  declared `intent`, or to skill wording. Skill-wording causes become fix candidates; the other
  two are recorded and not actioned here.
