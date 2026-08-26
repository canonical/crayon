# Fold dogen-record into dogen-write — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Merge the `dogen-record` skill into `dogen-write` (one drafting skill that branches on the declared Diátaxis `intent`), move the evidence gate into the deterministic scripts, and split the per-direction authoring instructions into four symmetric reference files — without losing the capability to prove a tutorial/how-to was drafted from a recorded walk.

**Architecture:** Three skills (`dogen-plan` → `dogen-write` → `dogen-review`) over four deterministic scripts, **two of which are modified** (`dogen-record-draft.sh` and `dogen-common.sh` gain the evidence gate). `dogen-write` becomes a dispatch-on-intent router; the four direction *registers* live in four `references/*-stance.md` files, a register-neutral base in `writing-standards.md`, and the actionable-only walk + evidence mechanics in `walk-protocol.md` + `episode-taxonomy.md` (lazy-loaded only on the tutorial/how-to branch). The evidence gate moves out of prose into `dogen-record-draft.sh` for a structural guarantee.

**Tech Stack:** bash (scripts), Markdown `SKILL.md` (skills), `tests/test_dogen_scripts.sh` (bash test harness). No Python.

## Global Constraints

- **6 scripts/helpers total; 2 modified, 4 untouched.** Modified: `dogen-record-draft.sh` (gains the evidence gate) and `dogen-common.sh` (gains an `unresolved_steps` helper). Untouched: `dogen-signoff.sh`, `dogen-record-review.sh`, `dogen-record-step.sh`, `skill_lint.py`.
- **3 skills** (was 4): `dogen-plan`, `dogen-write`, `dogen-review`. `dogen-record` is deleted.
- **Exit codes** (scripts): `0` success · `1` gate/evidence refusal … **but evidence now needs a distinct code — introduce `4` = evidence gate (unresolved steps)**, keeping `1` = signoff gate (no signoff / stale plan), `2` = bad input, `3` = no-op (identical redraft / stale evidence).
- **Ledger** stays plain markdown at `.dogen/units/<id>/ledger.md`.
- **`skill_lint.py` is unaffected** — it was already stripped to frontmatter-only (name + description) in a prior pass; it holds no `WRITERS` set or write-isolation rule to update.
- **`tests/test_dogen_scripts.sh`** is the only live test suite. The 57 `tests/*.py` files are orphaned dead code (import the removed `dogen.*` Python core) — **out of scope**, flagged for a separate cleanup (see Task 8).

### Out of scope (explicit)

- Cleaning up the 57 orphaned `tests/*.py` files (dead since the Python core was removed).
- The vestigial `mode: passenger` / `provider: host-harness` fields in the ledger generation row (harmless provenance labels; not touched here).
- The Drill eval harness (still deferred).

---

## File Structure

### Delete

| Path | Why |
|---|---|
| `skills/dogen-record/SKILL.md` | folded into `dogen-write` |
| `skills/dogen-record/references/authoring-stance.md` | split into `tutorial-stance.md` + `how-to-stance.md` |
| `skills/dogen-record/references/walk-protocol.md` | **moved** to `dogen-write/references/` |
| `skills/dogen-record/references/episode-taxonomy.md` | **moved** to `dogen-write/references/` |
| `skills/dogen-record/` | entire directory removed after the above |

### Create

| Path | Content source |
|---|---|
| `skills/dogen-write/references/reference-stance.md` | promoted from the inline reference register in `dogen-write/SKILL.md` step 3 |
| `skills/dogen-write/references/tutorial-stance.md` | the tutorial half of `dogen-record/references/authoring-stance.md` |
| `skills/dogen-write/references/how-to-stance.md` | the how-to half of `dogen-record/references/authoring-stance.md` |
| `skills/dogen-write/references/walk-protocol.md` | moved from `dogen-record/references/`, header re-pointed at the folded `dogen-write` step |
| `skills/dogen-write/references/episode-taxonomy.md` | moved from `dogen-record/references/`, header re-pointed |

### Modify

| Path | Change |
|---|---|
| `scripts/dogen-common.sh` | add `ledger_has_section` reuse + (if needed) a small `unresolved_steps` helper — see Task 1 |
| `scripts/dogen-record-draft.sh` | add the evidence gate (Task 1) |
| `skills/dogen-write/SKILL.md` | absorb walk, add intent branch, relink refs (Task 3) |
| `skills/dogen-plan/SKILL.md` | route all four directions → `dogen-write` (Task 4) |
| `skills/dogen-plan/references/actionable-intake.md` | route `dogen-record` → `dogen-write` (Task 4) |
| `skills/dogen-plan/references/reference-intake.md` | routing table → `dogen-write` (Task 4) |
| `skills/dogen-plan/references/explanation-intake.md` | any `dogen-record` mention → `dogen-write` (Task 4) |
| `skills/dogen-review/SKILL.md` | fix/redraft always → `dogen-write` (Task 5) |
| `skills/dogen-review/references/review-rubric.md` | `authoring-stance.md` ref → `tutorial-stance.md`/`how-to-stance.md`; `dogen-record` routes → `dogen-write` (Task 5) |
| `skills/README.md` | 3 skills, folded routing, evidence gate doc (Task 6) |
| `README.md` | 3 skills, routing, exit-code table gains `4` (Task 6) |
| `docs/middle-path-plan.md` | architecture + feature map update (Task 6) |
| `docs/before-after.md` | 3 skills (Task 6) |
| `tests/test_dogen_scripts.sh` | evidence-gate tests (Task 1) |

---

## Task 1: Evidence gate in `dogen-record-draft.sh` (TDD)

**Files:**
- Modify: `scripts/dogen-record-draft.sh`
- Modify: `scripts/dogen-common.sh` (add `unresolved_steps` helper)
- Test: `tests/test_dogen_scripts.sh`

**Interfaces:**
- Produces: `dogen-record-draft.sh` gains exit `4` = "evidence incomplete" for actionable units whose `## steps` contains any `status: unverified` (or is missing/empty). Exit `1` remains "signoff gate". Exit `0` unchanged. Reference/explanation units skip the evidence check entirely.

- [ ] **Step 1: Add the helper to `dogen-common.sh`**

Append after `ledger_has_section`:

```bash
# Print unresolved (unverified) step ids in the ledger's ## steps section, one per line.
# Usage: unresolved_steps <ledger_file>
unresolved_steps() {
    local ledger="$1"
    ledger_section_rows "$ledger" "steps" | grep 'status: unverified' \
        | sed -E 's/^([^ ]+).*/\1/' || true
}
```

- [ ] **Step 2: Write the failing tests in `tests/test_dogen_scripts.sh`**

Add a `# --- Tests: evidence gate (record-draft, actionable units) ---` block. Each test needs a `setup_unit` call with a non-reference `intent` (the harness already supports `setup_unit "id" "tutorial"`).

```bash
test_record_draft_evidence_gate_unresolved() {
    setup_repo; setup_unit "walk-unit" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "walk-unit" >/dev/null 2>&1
    local ledger=".dogen/units/walk-unit/ledger.md"
    echo "" >> "$ledger"; echo "## steps" >> "$ledger"
    echo "step-1 | text_hash: aaa111 | status: unverified" >> "$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    mkdir -p .dogen/staging; echo "# Draft" > .dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "walk-unit" ".dogen/staging/draft.md" >/dev/null 2>&1; local rc=$?
    assert_eq "actionable draft with unresolved step exit code" "4" "$rc"
    assert_file_not_exists "no page on unresolved step" "docs/walk-unit.md"
    cleanup
}

test_record_draft_evidence_gate_no_steps() {
    setup_repo; setup_unit "walk-unit" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "walk-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging; echo "# Draft" > .dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "walk-unit" ".dogen/staging/draft.md" >/dev/null 2>&1; local rc=$?
    assert_eq "actionable draft with no step plan exit code" "4" "$rc"
    cleanup
}

test_record_draft_evidence_gate_resolved() {
    setup_repo; setup_unit "walk-unit" "tutorial"
    "$REPO_SCRIPTS/dogen-signoff.sh" "walk-unit" >/dev/null 2>&1
    local ledger=".dogen/units/walk-unit/ledger.md"
    echo "" >> "$ledger"; echo "## steps" >> "$ledger"
    echo "step-1 | text_hash: aaa111 | status: resolved" >> "$ledger"
    git add .dogen/ && git commit -q -m "add steps"
    mkdir -p .dogen/staging; echo "# Draft" > .dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "walk-unit" ".dogen/staging/draft.md" >/dev/null 2>&1; local rc=$?
    assert_eq "actionable draft with all steps resolved exit code" "0" "$rc"
    assert_file_contains "page written" "docs/walk-unit.md" "# Draft"
    cleanup
}

test_record_draft_reference_skips_evidence_gate() {
    setup_repo; setup_unit "ref-unit" "reference"
    "$REPO_SCRIPTS/dogen-signoff.sh" "ref-unit" >/dev/null 2>&1
    mkdir -p .dogen/staging; echo "# Draft" > .dogen/staging/draft.md
    "$REPO_SCRIPTS/dogen-record-draft.sh" "ref-unit" ".dogen/staging/draft.md" >/dev/null 2>&1; local rc=$?
    assert_eq "reference draft skips evidence gate exit code" "0" "$rc"
    cleanup
}
```

- [ ] **Step 3: Run tests, confirm the two negative tests fail (exit `1`, not `4`)**

Run: `bash tests/test_dogen_scripts.sh`
Expected: `test_record_draft_evidence_gate_unresolved` and `test_record_draft_evidence_gate_no_steps` FAIL with `expected: '4', got: '0'`.

- [ ] **Step 4: Implement the evidence gate**

In `dogen-record-draft.sh`, insert immediately **after** the signoff gate block (after line `# --- End gate check ---`, before "Read target path"):

```bash
# --- Evidence gate (actionable units only) ---
intent=$(get_unit_field "$unit_file" "intent")
if [ "$intent" = "tutorial" ] || [ "$intent" = "how-to" ]; then
    if ! ledger_has_section "$ledger" "steps"; then
        echo "ERROR: evidence incomplete: no step plan recorded for actionable unit ${unit_id}" >&2
        exit 4
    fi
    unresolved=$(unresolved_steps "$ledger")
    if [ -n "$unresolved" ]; then
        echo "ERROR: evidence incomplete: unverified step(s) for ${unit_id}:" >&2
        echo "$unresolved" | sed 's/^/  - /' >&2
        exit 4
    fi
fi
# --- End evidence gate ---
```

Also update the header comment and usage line to document exit `4`:

```
# Exit: 0 success, 1 signoff-gate refusal, 2 bad input, 3 identical redraft, 4 evidence incomplete
```

- [ ] **Step 5: Run tests, confirm all pass**

Run: `bash tests/test_dogen_scripts.sh`
Expected: `Results: <N> passed, 0 failed` (the four new tests plus all prior tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/dogen-common.sh scripts/dogen-record-draft.sh tests/test_dogen_scripts.sh
git commit -m "feat(scripts): evidence gate in record-draft refuses unresolved actionable steps"
```

---

## Task 2: Four stance reference files + move the walk/evidence refs

**Files:**
- Create: `skills/dogen-write/references/reference-stance.md`
- Create: `skills/dogen-write/references/tutorial-stance.md`
- Create: `skills/dogen-write/references/how-to-stance.md`
- Move: `skills/dogen-record/references/walk-protocol.md` → `skills/dogen-write/references/walk-protocol.md`
- Move: `skills/dogen-record/references/episode-taxonomy.md` → `skills/dogen-write/references/episode-taxonomy.md`
- Delete: `skills/dogen-record/references/authoring-stance.md`

- [ ] **Step 1: `reference-stance.md`** — promote the inline reference register. Header:

```
Load this file at workflow step 3 (Author the page).

# Reference stance (authoring)

The register an authored **reference** page answers to. It is the neutral,
information-oriented "look it up" voice: describe the machinery accurately and
completely (each item, its type, default, and bounds); state what is; do not teach
or narrate. One category per page.
```

Body: move the existing reference-register prose verbatim from `dogen-write/SKILL.md` step 3 (the "neutral, information-oriented register … banned register … reference code entities by qualified name … show a code block only when the reader themselves authors or invokes it" block), plus the per-format MyST/rST standards currently folded there, so the inline prose is *removed* from the SKILL (not duplicated).

- [ ] **Step 2: `tutorial-stance.md`** — the tutorial half of `authoring-stance.md`. Header:

```
Load this file at workflow step 3 (Author the page).

# Tutorial stance (authoring)

The register an authored **tutorial** page answers to: learning-oriented, a single
guaranteed-to-work route from a known starting state to one visible success, with
per-step confirmation of what the learner sees — no branching, no options menu, no
"it depends".
```

Body: the "Tutorial — learning-oriented" paragraph + the shared "curated-excerpt rule" (curated, env-scrubbed excerpts; never leak the evidence apparatus into the page) + the "Markup" section, all taken from `authoring-stance.md`. The "How-to" paragraph is deliberately *excluded* here.

- [ ] **Step 3: `how-to-stance.md`** — the how-to half. Header:

```
Load this file at workflow step 3 (Author the page).

# How-to stance (authoring)

The register an authored **how-to** page answers to: task-oriented, focused on one
goal. It assumes competence, states its starting preconditions, and gives the
shortest reliable path to a real-world result — the shortest reliable path; forks
only at a genuine decision point. It does not teach from scratch and does not try
to be complete.
```

Body: the "How-to — task-oriented" paragraph + the same shared curated-excerpt + Markup sections (curated-excerpt and Markup are duplicated across tutorial/how-to by design, so each file is self-contained when loaded in isolation — accept the small duplication; it is the price of register isolation).

- [ ] **Step 4: Move `walk-protocol.md` and `episode-taxonomy.md`** into `dogen-write/references/`, updating their first lines to point at the folded `dogen-write` steps (walk-protocol → step 2/3 of the walk branch; episode-taxonomy → the walk step). Their `dogen-record-step.sh` / `dogen-record-draft.sh` script references are still correct and unchanged.

- [ ] **Step 5: Delete `authoring-stance.md`.**

- [ ] **Step 6: Commit.**

```bash
git add skills/dogen-write/references skills/dogen-record/references
git commit -m "feat(skills): four per-direction stance refs; move walk refs into dogen-write"
```

---

## Task 3: Rewrite `dogen-write/SKILL.md` (fold walk + branch + relink)

**Files:**
- Modify: `skills/dogen-write/SKILL.md`

**Interfaces:**
- Consumes: `dogen-record-draft.sh` (now with evidence gate), `dogen-record-step.sh`, the reference files from Task 2.
- Produces: a skill whose `description` names all four directions, whose step 1 dispatches on `intent`, and whose actionable branch runs the walk.

- [ ] **Step 1: Rewrite the `description`** (precondition P3 — name the branch):

```
Drafts a review-ready, Sphinx-publishable page (MyST or rST — the target extension
decides) for a declared and signed-off documentation unit, branching on the unit's
declared Diátaxis intent: reference and explanation are authored straight from the
declared sources; tutorial and how-to are authored from an evidence-gated step walk
(each step captured as proof and recorded via dogen-record-step.sh) and curated
excerpts of what actually ran. Stages under .dogen/staging/ and records via
dogen-record-draft.sh, which enforces the HITL gate and — for actionable units —
refuses until every step is resolved. Carries Write for staging files only. Use when
a TA is ready to draft a signed-off unit.
```

- [ ] **Step 2: Rewrite step 1 to dispatch on `intent`** (precondition P3). The first workflow step reads the unit state, then branches with an explicit, exhaustive table:

```
Read .dogen/units/<id>/unit.md and .dogen/units/<id>/ledger.md, then branch on the
declared intent:
- reference   → steps 2–6 (ground from sources, author the reference register, record)
- explanation → steps 2–6 (ground from sources + intent, author the explanation register, record)
- tutorial    → step 3a (propose a step plan, walk it under the evidence gate), then steps 2–6 with the tutorial register
- how-to      → step 3a, then steps 2–6 with the how-to register
```

- [ ] **Step 3: Absorb the walk as `step 3a`** (contents of the old `dogen-record` steps 2–4): investigate sources → propose ONE annotated step plan → write it to the ledger `## steps` section with `text_hash` per step → walk silent-until-signal → record each step through `dogen-record-step.sh`. Load `references/walk-protocol.md` at 3a start and `references/episode-taxonomy.md` for the deviated/fail taxonomy. (These bodies already exist in `dogen-record/SKILL.md`; move them, don't re-invent.)

- [ ] **Step 4: Relink the reference files in step 3** (the author step):

```
Load references/writing-standards.md in every direction. Then load the direction
register: reference → references/reference-stance.md; explanation →
references/explanation-stance.md; tutorial → references/tutorial-stance.md;
how-to → references/how-to-stance.md.
```

- [ ] **Step 5: Replace the `<Iron-Law>` + `<objective>` + edge-cases text** with the folded equivalents (the signoff Iron Law stays; add the evidence Iron Law "NO ACTIONABLE DRAFT WITHOUT RESOLVED STEPS — `dogen-record-draft.sh` enforces this, exit 4").

- [ ] **Step 6: Commit.**

```bash
git add skills/dogen-write/SKILL.md
git commit -m "feat(skills): dogen-write folds in the evidence walk; dispatches on intent"
```

---

## Task 4: Delete `dogen-record` + update `dogen-plan` routing

**Files:**
- Delete: `skills/dogen-record/SKILL.md` (and the now-empty `skills/dogen-record/` directory)
- Modify: `skills/dogen-plan/SKILL.md`
- Modify: `skills/dogen-plan/references/actionable-intake.md`
- Modify: `skills/dogen-plan/references/reference-intake.md`

- [ ] **Step 1: Delete** `skills/dogen-record/SKILL.md` and the directory if empty.

- [ ] **Step 2: `dogen-plan/SKILL.md`** — every `dogen-record` routing becomes `dogen-write`:
  - step 4: `tutorial/how-to → declare intent, route to dogen-write` (no longer `dogen-record`)
  - `<HARD-GATE>`: "Do NOT invoke `dogen-write` …" (drop "or dogen-record")
  - the summary block: `Next: /dogen-write — draft the unit.` for all four directions, with a direction annotation but never `/dogen-record`
  - `<pipeline>`: `dogen-plan -> dogen-write -> dogen-review` (one line)

- [ ] **Step 3: `actionable-intake.md`** — replace "routes to dogen-record" phrasing with "routes to dogen-write's evidence-walk branch"; note that the walk *still* derives steps from what actually ran, the split is now internal to dogen-write.

- [ ] **Step 4: `reference-intake.md`** — the four-direction routing table gains a "draft-stage skill: dogen-write (all four)" note; the tutorial/how-to row's draft skill becomes `dogen-write` (evidence-walk branch).

- [ ] **Step 5: Commit.**

```bash
git rm -r skills/dogen-record
git add skills/dogen-plan
git commit -m "feat(skills): dogen-plan routes all directions to dogen-write; drop dogen-record"
```

---

## Task 5: Update `dogen-review` routing

**Files:**
- Modify: `skills/dogen-review/SKILL.md`
- Modify: `skills/dogen-review/references/review-rubric.md`

- [ ] **Step 1: `dogen-review/SKILL.md`** — the fix/redraft routing collapses from two arms to one (dogen-write re-branches internally on intent):

```
- fix    → Next: /dogen-write — apply the recorded fix.
- redraft → Next: /dogen-write — re-draft against the recorded steering.
```

Remove the "reference/explanation → dogen-write vs actionable → dogen-record" split in step 5 and the "route to dogen-write/dogen-record" wording → "route to dogen-write".

- [ ] **Step 2: `review-rubric.md`** — replace the `skills/dogen-record/references/authoring-stance.md` import (line ~190) with two pointers: tutorial conformance → `skills/dogen-write/references/tutorial-stance.md`, how-to conformance → `skills/dogen-write/references/how-to-stance.md`. Update the fix/redraft routing table at the bottom ("`Next: /dogen-record …`" → "`/dogen-write …`").

- [ ] **Step 3: Commit.**

```bash
git add skills/dogen-review
git commit -m "feat(skills): dogen-review routes fix/redraft to dogen-write"
```

---

## Task 6: Docs — README, skills/README, middle-path-plan, before-after

**Files:**
- Modify: `skills/README.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/middle-path-plan.md`
- Modify: `docs/before-after.md`

- [ ] **Step 1: `skills/README.md`** — pipeline diagram → one line `dogen-plan -> dogen-write -> dogen-review`; replace the four-per-skill descriptions with three (fold dogen-record's description into dogen-write); script table unchanged; add a one-line note that `dogen-record-draft.sh` now exits `4` on unresolved actionable steps.

- [ ] **Step 2: `README.md`** — "four SKILL.md files" → "three"; step-3 "Draft — by direction" now shows one skill branching (reference/explanation authored straight; tutorial/how-to via the evidence walk), all calling `dogen-record-draft.sh`; the script exit-code table gains row `4 = evidence incomplete (unresolved steps)` for `dogen-record-draft.sh`.

- [ ] **Step 3: `AGENTS.md`** — the Architecture section drops `dogen-record` from the skill tree (3 skills) and folds its "draft tutorial/how-to from an evidence-gated step walk" line into `dogen-write`; the non-negotiables note `dogen-record-draft.sh` exits `4` on unresolved actionable steps.

- [ ] **Step 4: `docs/middle-path-plan.md`** — architecture tree (3 skills); feature-map rows referencing `dogen-record` → `dogen-write`; the "three preconditions" now realized (note the evidence gate is now in the script, not prose).

- [ ] **Step 5: `docs/before-after.md`** — skills count 4→3; the routing "tutorial/how-to → dogen-record" → "tutorial/how-to → dogen-write (evidence-walk branch)"; add a "folded dogen-record" note.

- [ ] **Step 6: Commit.**

```bash
git add README.md AGENTS.md skills/README.md docs/
git commit -m "docs: 3-skill architecture, folded routing, evidence-gate exit code"
```

---

## Task 7: Pathway walkthrough verification (all 14 pathways)

After all tasks land, run the scripts + lint + exercise each path. The bash suite covers the script-level outcomes; the human reviewer walks the skill-level prose paths.

Run `bash tests/test_dogen_scripts.sh` (expect all green) and `python3 scripts/skill_lint.py` (expect `OK - 3 skills`).

### Happy paths (one per direction)

| # | Direction | Walkthrough | Expected |
|---|---|---|---|
| 1 | reference | `setup_unit "u1" "reference"` → signoff → author reference → `record-draft` | exit `0`, no evidence gate |
| 2 | explanation | `setup_unit "u2" "explanation"` → signoff → author explanation → `record-draft` | exit `0`, no evidence gate |
| 3 | tutorial | `setup_unit "u3" "tutorial"` → signoff → write `## steps` + `record-step`×2 (`pass`) → author → `record-draft` | exit `0` (all resolved) |
| 4 | how-to | same as #3 with `intent: how-to` | exit `0` |

### Refusal paths (gates)

| # | Scenario | Command | Expected |
|---|---|---|---|
| 5 | no signoff | `record-draft` without `signoff` | exit `1` → route dogen-plan |
| 6 | stale plan | edit `unit.md` after signoff → `record-draft` | exit `1` → re-signoff |
| 7 | actionable, unresolved steps | tutorial with a `status: unverified` step → `record-draft` | exit `4` → back into walk |
| 8 | actionable, no step plan | tutorial with no `## steps` → `record-draft` | exit `4` → propose plan first |
| 9 | identical redraft | `record-draft` twice with identical bytes | exit `3` (no-op) |
| 10 | step evidence incomplete | `record-step` missing `output_sha256` | exit `1` → re-capture |
| 11 | step stale evidence | `record-step` with mismatched `step_text_sha256` | exit `3` → re-capture |
| 12 | step recorded as `fail` | `record-step` verdict `fail` | exit `0`, step stays `unverified` → #7 blocks later |

### Review → re-draft paths

| # | Scenario | Expected |
|---|---|---|
| 13 | review `fix` on a tutorial | `dogen-review` routes `Next: /dogen-write`; dogen-write re-branches on `intent: tutorial` and re-walks |
| 14 | review `redraft` on a reference | `dogen-review` routes `Next: /dogen-write`; dogen-write re-authors |

**Completeness check:** every direction has a happy path (1–4); every script exit code `1`/`2`/`3`/`4` is exercised (5–12); every review verdict routes correctly (13–14); the four stance reference files are each reachable via the dispatch table (1–4); the two shared refs (`walk-protocol.md`, `episode-taxonomy.md`) are reachable only via the actionable branch (3–4).

---

## Task 8 (done) — orphaned `tests/*.py` cleanup

The 57 orphaned `tests/*.py` files were removed in a prior commit (`de71584`) alongside the full Python purge. Nothing to do here.

---

## Self-Review

- **Spec coverage** — all three goals map to tasks: folding (Tasks 3–4), three preconditions (P1 = Task 1; P2 = Task 2 walk-protocol lazy-load + Task 3 dispatch; P3 = Task 3 description + step-1 branch), four reference files (Task 2). Verification = Task 7 (14 pathways).
- **Placeholder scan** — no "TBD"/"TODO"; every task has concrete file paths and, where code, actual snippets.
- **Type/name consistency** — exit code `4` introduced in Task 1 and referenced identically in Tasks 3/6/7; reference filenames (`reference-stance.md`, `tutorial-stance.md`, `how-to-stance.md`) consistent across Tasks 2/3/5; `dogen-record-draft.sh`/`dogen-record-step.sh` script names unchanged throughout.