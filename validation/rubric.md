# Validation rubric — scoring dogen drafts against the akcano reference bar

**Dev-time evaluation material only.** The akcano docs —
`docs/reference/definition-files/` inside the `workshop-akcano` checkout that
sits under the same parent directory as the `dogen-mvp-1` and `smoke-docs-1`
checkouts (`~/Documents/` here; from the smoke-docs-1 primary checkout that is
`../workshop-akcano/…`, from a validation worktree under `smoke-docs-worktrees/`
it is `../../workshop-akcano/…`) — are the measuring stick, never an input: no
drafting session, skill, or steering note may point at them. Score the accepted
draft of each leg after the run.

Two layers: the mechanical scorecard (`score.py` — run it first) and the human
dimensions below. Score each human dimension 0–2 (0 = fails, 1 = partial,
2 = meets the bar) and note evidence.

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
  page top-to-bottom) — the akcano ordering above is the proven shape.

## 3b. Cross-page consistency (unit 2, the multi-file exercise)

- Both pages were declared as ONE unit (`--also-target`), drafted through one
  `--draft-dir` pass, and sealed together (the accept's `files` digests cover
  both) — a page revised outside the unit's recorded pass scores 0 here.
- The unified JSON Schema sections read identically apart from the schema each
  exports; terminology matches across the set; nothing outside the bounded
  change drifted (diff the rest of each page against the baseline — it must be
  verbatim).

## 4. Loop quality (per leg, not per draft)

- Findings in review mode were grounded (the reviewer skill re-checked claims
  against sources, not just the draft).
- fix/redraft notes landed in the steering stream **before** the re-draft ran
  (the draft output's `unsteered_redraft: true` means a correction was carried
  informally — a loop-quality failure even when the draft came out right), and
  the re-draft actually applied them.
- Review routing stayed deterministic: verdicts recorded via `dogen review`,
  the `next_id` token followed, no reviewer/TA hand-editing offered, no
  duplicate accepts (`already_accepted` firing is a harness-behavior finding).
- **Routing voice** (round 3): every next-step the skills surfaced to the TA
  spoke skill language ("invoke dogen-write…"), never a raw `dogen …` command
  line (round 2's `--force` and "Next: dogen draft …" leaks); and each phase's
  closing summary quoted its `git: committed <sha7>` line — an asserted-but-
  unquoted commit is the round-2 blindness this line exists to end.
- **Stale-plan handling** (round 3): a reviewer-ordered plan amendment used the
  folded `dogen unit edit … --re-sign` (or an explicit `dogen signoff
  --re-sign`); a leg that drafted on a stale plan and cleared it turns later
  repeats the round-2 opencode detour — flag it.
- The context report is exhaustive-looking (origins ≈ what a human would have had
  to read) and **gaps are honest**: an empty `gaps: []` next to deep internals
  reads (overlord/exec handlers, policy code) is overconfidence — flag it; the
  best round-1 legs recorded 2–3 candid gaps. Round 3: an empty list must carry
  a `gaps_note` justification (the CLI records it) — its absence is the same
  overconfidence finding; commit stamps are hex-or-empty with explanations in
  the origin's `note` (a prose stamp now refuses as `bad_report`).
- Reads converted: an inventory the writer read (e.g. all seven `_interfaces/`
  pages) and did not surface in the page is the flagship completeness miss.

## 5. Cross-harness comparison (after all legs)

- Sidecar shapes and commit-trailer discipline identical across legs.
- Draft quality differences noted per dimension — attribute them (model, harness
  tool behavior, skill wording) where possible; skill-wording causes become fix
  candidates.
