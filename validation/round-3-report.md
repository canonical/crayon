# dogen round-3 validation report

Scope: the round-3 legs (`validation/claude-3`, `validation/copilot-3`,
`validation/opencode-3`) run from `validation-base-v3`. Only **unit 1**
(`workshop-definition`, the single-page rst reference) was driven on any leg;
unit 2 (`schema-section-consistency`, the multi-file exercise) was not run —
see [§4](#4-what-did-not-run).

Comparison target (dev-time evaluation material only, never a dogen input):
`workshop-akcano/docs/reference/definition-files/workshop-definition.rst`
("gold" below), 377 lines.

Headline: **the v1.2 investments held everywhere** — three legs, three clean
rst pages, zero MyST leaks, correct slot-derived placement, full git-event
relay, verdict-before-redraft throughout. The remaining defects are a CLI path
trap that wrecked one leg, a coverage bar no draft (nor the gold page) meets,
and provenance honesty that is good but uneven. Details and a best-of
corrections plan follow.

---

## 1. Sphinx build validation (A1)

Each leg's branch was built in an isolated worktree with the repo's provisioned
venv (`sphinx 7.4.7`), mirroring Read the Docs' contract —
`sphinx-build -b dirhtml … -W --keep-going` (`fail_on_warning: true`):

| Leg | Build | Warnings/errors | Verdict |
|---|---|---|---|
| claude | as committed | **0** | `build succeeded` — publishable |
| copilot | as committed | **0** | `build succeeded` — publishable |
| opencode | **as committed** | **19** | **build fails under RTD** — page unpublishable |
| opencode | file moved to canonical slot | **0** | `build succeeded` — content is sound |

**The opencode leg is the whole story of this round.** Its accepted page was
sealed at `docs/docs/reference/definition-files/workshop-definition.rst` (a
doubled `docs/`; [§3](#3-provenance-who-did-how-a3) explains why). Consequences,
all from the real build:

- **7 CRITICAL failures** — every `.. include:: _interfaces/*.rst` resolves from
  the wrong depth (`docs/docs/reference/definition-files/_interfaces/…` does not
  exist). The seven per-interface inventories silently vanish from the rendered
  page.
- **5 more** — the four example `literalinclude`s and the `schema.json` include
  fail the same way.
- **1 toctree break** — `reference/definition-files/index.rst:28: WARNING:
  toctree contains reference to nonexisting document
  'reference/definition-files/workshop-definition'`. The canonical slot is
  empty; the page is an orphan at the wrong path.

Moving the one file to the canonical slot and rebuilding yields **0 warnings**.
So the opencode draft's *content* is publication-grade; the leg failed purely on
a path the CLI should never have accepted. That gap is fixed in v1.3 (M1).

---

## 2. rst vs the gold standard (A2)

### 2.1 Structure (heading inventory vs gold)

Gold is a three-level page: 1 H1 / 7 H2 / 4 H3 (12 headings), ladder `=`/`-`/`~`,
with a **Nested structures** parent grouping the four sub-entries.

| | Headings | Ladder | "Nested structures" parent | "Interfaces" section |
|---|---|---|---|---|
| **gold** | 12 | 3-level | yes | yes (7 includes) |
| claude | 11 | **2-level** | no — 4 entries promoted to H2 | yes (7 includes) |
| copilot | 15 | 3-level | no — Name/Base/SDK-name/Channel added | **no — punted to `:ref:`** |
| opencode | 13 | 3-level | **yes** | yes (7 includes) |

- **opencode is structurally closest to gold**: same three-level shape, same
  *Nested structures* grouping, Interfaces embedded (it even splits plug/slot
  into two H3s, 5 vs gold's 4 — more granular, not less).
- **claude is complete but flat**: it drops the *Nested structures* grouping and
  promotes SDK entries / references / Connections / Actions to H2. All the
  content is present; the page just reads as a longer flat ladder.
- **copilot diverges most**: it adds *Name* and *Base* detail sections (a nice
  touch) but has **no Interfaces section at all** — the seven interface
  inventories are replaced by a cross-reference to `sdk-definition`. That is the
  single biggest content gap of the round.

### 2.2 Coverage (mechanical scorecard)

`score.py draft` coverage, register, and structure checks:

| | Coverage | Register | Impl-ids | rst structure | list-tables |
|---|---|---|---|---|---|
| **gold (ceiling)** | **24/29 (82%)** | clean | clean | clean | 5 |
| claude | **25/29 (86%)** | clean | clean | clean | 4 |
| opencode | 24/29 (82%) | clean | clean | clean | 3 |
| copilot | 21/29 (72%) | clean | clean | clean | 4 |

**The coverage bar is miscalibrated, and this is a finding in its own right.**
The runbook's pass criterion 5 asks for ≥ 90%, but **the gold page itself scores
82%** — the checklist counts items (`mount attrs`, `read-only attr`, `tunnel
endpoint attr`, `custom-device subsystem`, `validation summary`) that live in the
`_interfaces/*.rst` includes or are phrased in ways the raw main-page text does
not match. No page that mirrors gold's include-based structure can hit 90% under
this checklist. **claude at 86% actually scores above gold.** Two corrections
worth making to the kit (not blockers): resolve `.. include::` directives before
scoring, and re-derive the checklist from gold so the ceiling is 100%.

Register and implementation-identifier hygiene were **perfect on all three
legs** — the v1 stance contract is holding under real drafting.

### 2.3 Factual accuracy — the review loop earned its keep

The copilot leg is the clearest evidence the loop catches hallucination. Draft
#1 invented a Base-version table with codenames, including
`ubuntu@26.04 → "Ubuntu 26.04 LTS (Plucky Puffin)"` — **factually wrong** (Plucky
Puffin is 25.04). The review flagged it; draft #2 dropped the table for a plain
prose sentence. A fabricated, verifiable fact was introduced and then removed
before accept — exactly what the human-in-the-loop review is for.

### 2.4 Best-of corrections plan

**Strongest base: claude.** It is the only leg that is *both* clean-building and
content-complete (all seven interfaces embedded, register clean, 86% coverage,
above gold). Recommended path to a publication draft:

1. **Start from the claude page.**
2. **Graft opencode's structure**: restore the *Nested structures* H2 grouping
   over the four sub-entries so the ladder matches gold's three-level shape
   (claude's only real structural miss).
3. **Graft copilot's *Name* and *Base* field detail** into *Top-level fields* —
   copilot documented those two fields more thoroughly than the others.
4. **Close the residual coverage gaps** all legs share: `read-only` plug/slot
   attribute, `custom-device` subsystem attribute, and the mount/tunnel
   attribute rows — these need the authoring pass to actually read every
   `_interfaces/*.rst` member (v1.3 S5 makes that a contract).
5. **Do not** take copilot's interface handling — the `:ref:` punt is the one
   thing to reject outright.

Estimated distance to publishable: claude is ~1 structural edit + 3–4 attribute
rows away. copilot is a section rewrite away. opencode is one `mv` +
re-seal away (its content already builds clean).

---

## 3. Provenance: who did how (A3)

Full `score.py audit` is **green on all three legs** — signoff fresh, every read
commit-stamped, generation hashes matching, accept sealing the latest
generation. But green audits hide three very different levels of care.

| | Origins | Gaps | gaps_note | Notes | Model | Cycles |
|---|---|---|---|---|---|---|
| claude | 31 → 32 | 3 real | — | interface note on 1 origin | `claude-sonnet-5` ✓ | 2 (fix→accept) |
| copilot | 18 | 1 real (merge semantics) | — | mostly empty | `claude-sonnet-4.6 (host-asserted)` ✓ | 2 (fix→accept) |
| opencode | 23 ×3 | 0 / 1 / 1 | used (gen 1) | **all empty** | **`''` (was GLM-5.1)** | 3 (fix×3→accept) |

**Best parts, by leg:**

- **claude — depth and honesty.** 31 origins climbing to 32 when the fix verdict
  drove it to read `internal/workshop/workshop.go` and *stamp that new read
  against the review commit*. Three specific, verifiable gaps (SDK-ordering,
  explicit-`system`-listing, the auto-connection algorithm it deliberately
  cross-linked instead of asserting). This is the model provenance record.
- **copilot — discipline under thin reading.** Fewest origins (18, and it never
  read the interface files — the coverage cost), but it self-served its model
  honestly as `claude-sonnet-4.6 (host-asserted)` and logged the one gap that
  genuinely matters for correctness (slot-name-collision merge order the schema
  leaves unspecified).
- **opencode — the `gaps_note` and the context reads.** The only leg to fill
  `gaps_note` when its gap list was empty (gen 1), and the only leg that read
  the `.dogen/context/{doc-gaps,structure,doc-style}.md` artifacts. Undone by
  the model going unrecorded and every origin note left blank.

**The provenance paradox (the sharpest finding).** opencode's audit is
**fully green — including the seal check** — while its page is unpublishable. The
audit confirmed `draft_sha256 matches the recorded draft file` because the
doubled-path file really exists and really hashes correctly; it never checked
that the sealed path *is the unit's declared slot under a single `docs/`*. So a
correct seal certified a broken location. Traceability-green and
publishable-green diverged, silently. (Kit fix: the audit should assert the
sealed path equals `docs/<sphinx_target>` with exactly one prefix.)

**Also worth recording:** every leg's `signoff.commit` points at the last
*plan-content* commit (the `edited` commit), not the `signed-off` commit. That
is correct by design — it pins the plan state the signoff covered — but it reads
as surprising in a raw log; documented now in `provenance-summary.md`.

### Improvement plan (mapped to v1.3)

| Weakness observed | Fix |
|---|---|
| `docs/`-prefixed target accepted → `docs/docs/…`, wrong-path seal, 3 wasted cycles | **M1**: normalize a leading `docs/` at declare/edit with a notice |
| Model unrecorded on the one leg where it wasn't self-evident | **M4** (flag) + **S3** (blocking model-ask, not a fallback) |
| Orphan fix note recorded, then accept with no draft between | **M5**: `unapplied_steering` warning on accept |
| Reviewer diagnosed "unfixable CLI bug", handed the TA a raw `mv` | **S6**: a wrong-path finding checks the stored target first, prescribes `unit edit --target … --re-sign` |
| Interface inventory punted to a cross-ref, self-accepted | **S4** (outline-conformance in review) + **S5** (inventory read contract) |
| "re-draft" language for a bounded *fix* verdict | **M2** + **S2**: fix says "apply the recorded fix" |
| Coverage checklist unreachable (gold scores 82%) | Kit: resolve includes before scoring; re-derive checklist from gold |
| Seal certifies a broken path | Kit: audit asserts sealed path == `docs/<sphinx_target>` |

---

## 4. What did not run

- **Unit 2 (`schema-section-consistency`) was not executed on any leg.** No
  commits, no `.dogen/units/schema-section-consistency/`, no diffs on
  `sdk-definition.rst` / `sdkcraft-definition.rst`. The v1.2 multi-file flow
  (`--also-target` / `--draft-dir`, cross-page sealing) remains **unvalidated in
  the wild** — proven only by unit tests. No further round is scheduled; this is
  the standing gap to close whenever multi-file drafting next matters.
- **`validation/RESULTS.md` was not produced** on any leg.
- **Session-export discipline slipped again**: claude committed no export (only
  an untracked terminal capture, now preserved as
  `validation/SESSION-claude.md`); copilot and opencode landed exports at the
  repo root under non-standard names.

## 5. Environment notes

- The claude leg ran `claude-sonnet-5`, off the runbook's Sonnet-4.6-class pin —
  recorded honestly, but a comparability caveat: it is a stronger model than the
  other two legs. Its branch was `validation/sonnet-3`, renamed to
  `validation/claude-3` for uniform namespacing.
- Wall-clock was comparable across legs (~23–30 min) despite opencode's extra
  cycle — the wasted cycles were fast because the bug reproduced immediately.

## 6. Round-4 include-aware re-score (Phase 11 / VAL-01)

`score.py` now resolves `.. include::` one level before scanning (D-08..D-11).
Re-scoring the frozen round-3 captures under the fix — after staging the shared
`_interfaces/*.rst` snippets beside the **claude** draft only (the frozen `.rst`
drafts and the opencode `docs/docs/` doubling are untouched) — the honest
per-leg outcome:

- **claude:** all 7 dir-relative includes resolve → interface attributes are now
  genuinely counted → `coverage 29/29 (100%)`, zero `unresolved include` FLAGs.
  The old 86% was partly a keyword-on-directive-line artifact; the include-aware
  score reflects what Sphinx actually builds.
- **copilot:** 0 includes (interfaces punted to `:ref:`) → nothing to resolve →
  the interface gap stays a **real miss**, correctly.
- **opencode:** the deliberate doubled `docs/docs/…` path means the 7 includes
  resolve from the wrong depth even with the snippets staged at the canonical
  single-`docs` location → they stay unresolved (7 `unresolved include` FLAGs,
  `coverage 24/29 (82%)`) → **remains a true miss**, faithfully reproducing the
  real Sphinx build failure. rST-faithful resolution (D-08) mirrors the build.

`score.py draft` stays report-only (exit 0) throughout — unresolved-include
FLAGs never change the exit code (D-09).
