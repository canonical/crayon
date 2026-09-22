# dogen contract v1

<!-- provenance: frozen at tag contract-v1; the internal_error reason row and the context verbs (§5.1, §5.5, §5.7, §6) were added after the freeze -->

The normative contract for the `dogen` tool: what it writes, what it refuses, and what the
record it leaves behind does and does not prove. This document is frozen at git tag
`contract-v1`; where it and any plan, skill or README disagree, this document wins.

RFC 2119 keywords carry meaning **only in capitals**. MUST is used only where a rule is
test-bearing — that is the boundary of the closure rule below, and it is what keeps "every MUST
has a test id" finite. Lowercase "must" is ordinary prose and carries no obligation.

## Mechanisms

"Slim" is defined by responsibilities and maintenance cost. Every mechanism answers four
questions: *which observed failure or journey it protects; what the author experiences; the
simplest adequate mechanism; how we know it helped.*

| Mechanism | Failure / journey protected | What the author experiences | Simplest adequate mechanism | Signal (how we know it helped) |
|---|---|---|---|---|
| JSONL ledger, canonical lines, chain | audit defects 1, 2 (refused, not supported, since `357c513`), 5, 7 | a tamper-evident record that survives compaction; a corrupted line refuses loudly instead of silently deriving the wrong state | `json.dumps` sort_keys + sha256 of previous line | N-01/02/05 |
| Derived state, one ordered routing table, `show`/`summary` | audit defect 6; Aug 31 | one `Next:` token after every verb, and a state that can never desync from the record because nothing is stored | one pure `derive()` | U-05 · U-08 — J5; `summary --md` as PR text |
| Explicit-pathspec commits, 4 trailers | audit defect 4 | an unrelated in-`docs/` edit is never swept into the tool's commit | argv lists | N-04 |
| Containment for every write destination | audit defect 3 (string-checked since `357c513`; `realpath` closes the symlink and `docs/docs/` cases) | a target that escapes the docs root is refused before anything is written | one `contained()` | N-03, N-24 |
| Signoff/plan-hash/stale/amended gates | AC5; v1.1 | no substantial draft lands without a recorded signoff, and editing the plan after signing invalidates it rather than passing silently | sha256(unit.md); `gen.signoff_seq == so.seq` | A-08/09, N-19 |
| Unsteered refusal | AC5 | re-drafting without recording what changed is refused, not quietly repeated | seq comparison over H | N-09 |
| Pending requests closed by recorded, disjoint dispositions | round-2 f.1, round-3 f.8 | accept names which requests it satisfies and which it withdraws; nothing is closed by silence | `resolves`/`withdraws` on accept | N-20/21/25/32 |
| Drift over basis paths + `edits` (complete set; brownfield adoption) | a reviewer's hand-edit case; committed edit; existing page; target change | a hand edit is adopted into the record rather than overwritten, and an existing page is adopted rather than clobbered | disk digests vs basis paths | N-10, N-26, N-33/34 |
| Step evidence, tool-computed; conservative reuse | audit §5.1 | a tutorial or how-to step counts as resolved only with captured bytes and a real exit code; reuse carries forward only along an unchanged prefix | `--steps-seq`; `--keep-evidence --note` | N-18, N-27 |
| Manifest write protocol; two-pass `resume`; bounded `--adopt`; honest limit | J6; partial writes; hooks; lost material | a crash or a rewriting hook never loses the author's work; recovery either completes or stops and says exactly what it cannot do | pending/{before,after,manifest}; classify then write | N-13…N-17, N-28…N-31, N-35…N-38 |
| Repo-wide lock | concurrent invocations | a second invocation refuses with `busy` instead of interleaving two transitions | `fcntl.flock` | N-16 |
| `verify` (read-only) | N1; scorer oracle | one read-only command answers "is this unit's record internally valid" without changing anything | V1–V19 | V-01…V-04 (`validation/fixtures.sh`) |
| `retire` | abandoned unit blocks a target | an abandoned unit's target can be claimed again, by one recorded act | one event | N-40 (`tests/test_dogen_lifecycle.sh`) — J7 |
| `context record` (repo-level) | house style, vocabulary and structure reach the skills only as loose files nobody recorded | the context artefacts a skill drafted land in `.dogen/context/` through the tool, digested and committed, so `dogen-plan` grounds itself in a record rather than in whatever is on disk | a fixed set of five names; one manifest; one commit with no unit | N-47 (`tests/test_dogen_lifecycle.sh`) |
| `contract` + `min_tool` | skills drift from tool | a skill paired with an incompatible tool stops with a version message instead of misbehaving | two numbers | A-37 (`tests/install_smoke.sh`) — install smoke |

**Closure rule:** a rule is specified only when each trace in §5.11 follows from the *same*
precondition, routing and recovery rules an implementation executes, and each trace has a test id.
Where supporting a case would overgrow the tool, the contract states a precise limitation that
preserves the author's work rather than a broad success claim.

**Not built:** per-unit locks, HEAD restore inside the tool, `--abandon`, `--amend-model`,
`owners[]`, `run_id`, six of the ten trailers, `signoff_history`, generated test counts, referral
pins, trace-ID CI grep, a second derive/verify in the scorer, `install.sh`, environment
fingerprinting, a step dependency graph, a state field for "amended", a hook runner, a plan-repair
path.

**Reserved, inactive in v1:** `extends` (event field) and `superseded_by` (verify) — parsed if
present, never produced, no behaviour.

## 5.1 Artifacts, ownership, and the guarantee

| Artifact | Writer | May edit | Detected by |
|---|---|---|---|
| `unit.md` | tool (`unit new/edit`) | TA by hand; skills only via `unit edit` | after signoff → `plan_stale` |
| `ledger.jsonl` | tool only | nobody | chain, canonical check, committed prefix |
| `docs/<path>` for paths in the basis | tool on `draft`; TA by hand then `edits` | as stated | drift vs basis (git-independent) |
| `.dogen/staging/<id>/{draft,report.json,scratch/evidence}` | skill or TA | skill | inputs only, gitignored |
| `.dogen/staging/<id>/pending/{before,after,manifest.json}`, `.dogen/staging/lock` | tool | — | gitignored, transient |
| commit trailers | tool via git | rebase/squash (visible) | WARN-level corroboration |
| `.dogen/context/<name>`, `<name>` one of the five context artefacts (§5.6) | tool on `context record`; TA by hand | as stated | `context show`: `drifted` (bytes differ from the manifest), `unrecorded` (present, never recorded) — reported, never refused |
| `.dogen/context/manifest.json` | tool only (`context record`) | nobody | `context show` and `context record` read it; a damaged one refuses 2 `bad_target` |
| `.dogen/staging/_context/{<name>,<name>.sources.json}` | tool (`context stage`) | — | gitignored, transient; cleared by `context record` |

**Guarantee (single wording):** the ledger lets `verify` check that each recorded transition was
valid against the events before it, and lets `show` compare recorded digests with current bytes.
It does not prove that history was never rewritten, that a recorded actor is who the git
identity says, that a recorded request was applied, or that anything outside dogen's own writes
did not happen. Edits outside dogen are detected where recorded digests allow it and never
prevented. `allowed-tools` is a lint rule and a convention, not a write boundary. The tool never
deletes a page.

**Claim policy (one rule, every claiming path):** a target is blocked when another unit that is
not retired lists it in its current signoff — whether that unit is in flight or sealed
(`target_claimed`, naming the unit and the retire command); `retire` releases the claim.
`unit new`, `unit edit`, `signoff` and reopen all apply this rule. (`extends` takeover is not in v1.)

## 5.2 Envelope and serialization

`{kind, seq, prev, at, actor:{name,email}, tool_version, contract, commit, …}`; `seq` contiguous
from 0; `prev` = sha256 of the previous line's exact bytes without LF; `at` informational;
`commit` = HEAD before the transition, advisory. Writer:
`json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)` + `\n`;
no floats. A transition is an
**event batch** (1 event for most verbs; 2 for `unit new` and `--re-sign`; 3 for adopting
`signoff`; +1 for `resume --adopt`), appended in one `write()` + `fsync`; the manifest (§5.8) is
the recovery boundary. Caps: line ≤ 256 KiB, note ≤ 64 KiB, steps ≤ 64 KiB, excerpt ≤ 4096
bytes, ≤ 64 files, ≤ 500 origins. `.dogen/.gitattributes` pins `*.jsonl -text`.

## 5.3 Event catalogue

Twelve kinds; `void` reserved.

| kind | verb | payload (required; *optional*; ~reserved~) |
|---|---|---|
| `ledger` | `unit new`, adopting `signoff` | `v:1`, `unit`, `docs_root:"docs"` |
| `unit-declared` | `unit new` | `unit_hash`, `frontmatter`; *`adopted:true`*; ~`extends`~ |
| `unit-edited` | `unit edit` | `unit_hash_before`, `unit_hash_after`, `frontmatter` |
| `signoff` | `signoff`, `--re-sign` | `plan_hash` (sha256 of whole `unit.md`), `intent`, `audience`, `title`, `targets[]`, `sources[{path,commit\|null}]`, `context:{path:sha256}`, `supersedes` |
| `steering` | `steer` | `note`, `origin ∈ {plan, manual}` |
| `steps-planned` | `plan-steps` | `steps[{id,text,text_hash,mode,stateful}]`, `replaces`, `reuse:bool`; *`reuse_note`* (required when `reuse`) |
| `step-recorded` | `step` | `step_id`, `steps_seq`, `text_hash`, `mode`, `verdict`, `exit_code`, `output_sha256`, `output_excerpt`; *`command`*, *`reason`* (required for skipped/deviated, pass with exit ≠ 0, fail with exit 0) |
| `generation` | `draft` | `files[{path,sha256,bytes}]` = exactly the current signed targets, `signoff_seq`, `plan_hash`, `model`, `model_origin`, `basis_seq\|null`, `unsteered`; *`unsteered_reason`*, *`steps_seq`*, *`origins[]`*, *`gaps[]`*, *`gaps_note`* |
| `reviewer-edit` | `edits`, `resume --adopt` | `files[]` = **the complete basis set** (every path of the previous basis with its recorded digest unless changed; plus adopted targets; minus paths missing from disk that are no longer signed targets), `generation_seq` (null when no generation exists), `note`, *`hook:true`* (`resume --adopt` only — the author was shown the bytes and chose to keep them; `edits` never sets it, and there is no flag to make it) |
| `review` | `review` | `verdict`, `generation_seq`, `note`; accept also `basis_seq`, `files`, `resolves[]`, `withdraws[{seq,reason}]` |
| `retired` | `unit retire` | `note` |
| ~`void`~ | none in v1 | reserved for committed events; readers skip voided seqs if present |

Commit per transition: subject `dogen: <phase> <id>`; body = collapsed note ≤ 400 chars;
trailers `Dogen-Unit`, `Dogen-Phase`, `Dogen-Seq: n[-m]`, `Dogen-Head: <16 hex>`, and
`Dogen-Verdict` on review. Pathspecs explicit; never a directory.

`context record` is the one repo-level transition. It writes no event and touches no unit
ledger; its commit is subject `dogen: context recorded`, body = collapsed note ≤ 400 chars,
trailers `Dogen-Phase: context-recorded`, `Dogen-Head: <16 hex>` and, when a model is claimed,
`Dogen-Model` — no `Dogen-Unit`, no `Dogen-Seq`, because the context belongs to the repository
and not to a unit (§5.1). Pathspecs are the promoted artefacts and the manifest, explicitly.

## 5.4 Derivation

```
E      = events in seq order
H      = {steering, review fix|redraft, signoff}
so     = last signoff; gen = last generation; edit = last reviewer-edit; rev = last review
basis  = latest of {gen, edit} by seq                 # may be an edit with no generation
tip    = latest of {gen, edit, rev} by seq
targets = so.targets
plan_stale       = sha256(unit.md) != so.plan_hash
generation_stale = gen and gen.signoff_seq != so.seq
h_after(x)       = ∃ h ∈ H: h.seq > x.seq
page_drift       = basis and ∃ p ∈ basis.files: disk(p) exists and sha256(disk(p)) != p.sha256
                   # changed bytes only; absence is not drift
page_missing     = basis and ∃ p ∈ basis.files ∩ targets: disk(p) missing     # shown; restored by draft
target_exists    = ∃ t ∈ targets: t ∉ basis.files and disk(t) exists and is non-empty
target_missing   = ∃ t ∈ targets: t ∉ basis.files or disk(t) missing        # accept gate only
orphans          = [p ∈ basis.files: p ∉ targets]                              # reported, never deleted
pending          = [h ∈ H, h.kind ≠ signoff, h.seq > (gen.seq if gen else 0)]
                   minus seqs in any later accept.resolves ∪ withdraws
steered_since_gen = h_after(gen)      # defined only when gen exists
state:
  retired    if last retired
  declared   if not so
  signed-off if not gen                      # a brownfield basis alone is still signed-off
  sealed     if tip is review.accept and not h_after(tip) and not generation_stale
  reviewed   if tip is review                # accept-then-amended/steered, fix, redraft
  drafted    otherwise
```

Step status: a `step-recorded` resolves the step it names in the plan `steps_seq`; it carries
forward to later plans only along consecutive `reuse:true` plans and only for steps whose prefix
`[0..i]` is identical in `(text_hash, mode, stateful)` across every hop. `pass`+sha, `skipped`
+reason, `deviated`+exit 0+sha resolve; `fail` never. `resolved` ≠ `executed`.

Target changes: a re-sign may add, remove or rename targets. Removed paths stay in `basis.files`
until the next generation (whose `files[]` is exactly the new target set); the file is kept on
disk; `show` and the `draft` response name each orphan once ("no longer a target; kept on
disk"). A renamed target is a removal plus an addition; a pre-existing non-empty new target is
adopted through `edits` like any brownfield page. A signed target missing from disk blocks
accept (`target_missing`), never drafting: a draft that writes every signed target restores it
under the ordinary gates (signoff, steering, evidence). `edits` keeps a missing **current**
target's last recorded digest in the complete basis set (historical basis preserved; no
placeholder file, no fabricated digest) and drops a missing path only when it is no longer a
signed target. After a seal, a missing page routes to `steer` (the author records the
restoration request), then `draft`.

`identical_draft` (no-op) requires all of: a generation exists; `gen.signoff_seq == so.seq`;
the staging `steps_seq` equals the generation's; no H event since the generation; and **every
signed target already exists on disk with the staging digest**. Comparison is against the
destination files, never against a historical basis: a missing destination, a hook-rewritten
destination, or a brownfield basis with no generation can never make a draft a no-op.
Defeating the no-op does not waive the steering gate: with an existing generation and no H
event since it, `draft` is refused `unsteered` (§5.7 e) until the author's restoration request
is recorded via `steer`.

## 5.5 Routing

One ordered table; first match wins.

| # | Condition | `next` |
|---|---|---|
| 1 | uncommitted tail | `resume` |
| 2 | retired | `retired` |
| 3 | no signoff | `sign_off` |
| 4 | plan_stale | `re_sign` |
| 5 | page_drift or target_exists | `record_edits` |
| 6 | no generation (brownfield basis or none) | `walk` if actionable with unresolved steps else `draft` |
| 7 | generation_stale | `walk`/`draft` (qualifier: plan amended) |
| 8 | tip is accept and not h_after(tip) and not target_missing | `publish` |
| 8b | tip is accept and not h_after(tip) and target_missing | `steer` (record the restoration request; the next draft restores) |
| 9 | tip is accept with H after, or tip is fix/redraft | `walk`/`draft` |
| 10 | tip is generation or reviewer-edit | `review` |

`page_missing` never routes on its own: `show` marks the path `missing` and the draft route
restores it. `show` distinguishes `missing` (absent) from `drifted` (changed bytes).

**Context routing.** The `context` verbs route on the repository's context artefacts, not on a
unit; one ordered table, first match wins.

| # | Condition | `next` |
|---|---|---|
| C1 | an artefact is staged under `.dogen/staging/_context/` | `record` |
| C2 | any of `doc-style.md`, `glossary.md`, `structure.md` is absent from `.dogen/context/` | `onboard` |
| C3 | otherwise | `plan` |

`code-to-docs-map.md` and `doc-gaps.md` never route on their own: they come from tooling outside
dogen, when the author has it, and their absence is not a missing context.

## 5.6 Validation rules

| Input | Rule |
|---|---|
| unit id | `^[a-z0-9][a-z0-9-]{0,63}$` |
| step id | `^[a-z0-9][a-z0-9._-]{0,31}$`, unique in the plan |
| target | docs-relative POSIX `^[A-Za-z0-9._/-]{1,200}$`, no `\`, no `.`/`..`/empty segment, not absolute, `.md`/`.rst`, leading `docs/` refused, no duplicates |
| every write destination | `realpath` inside the repo root; docs root inside the repo (symlinked out → `bad_write_path`); `.dogen/` inside and not a symlink; pages inside the docs root; pending/evidence inside `.dogen/staging/` |
| draft source | file or dir resolving inside `.dogen/staging/<id>/draft/`; a dir contains exactly the signed targets |
| note / reason | UTF-8, C0 controls except `\n`/`\t` stripped, `\r` refused, ≤ 64 KiB, non-empty; `\|` and newlines are ordinary characters (JSON), where `slim@357c513` refuses them in review notes — a stated behaviour change |
| model | single line ≤ 128; `""` iff `model_origin == "unknown"` |
| `--resolves a,b` / `--withdraw <seq> "<reason>"` (repeatable) | every seq ∈ current `pending`; no duplicates; the two sets disjoint; every withdrawal has a non-empty reason; else 2 `bad_resolution`. `resolves` = the reviewer's recorded judgment that the request is satisfied (no proof that bytes changed). |
| `--steps-seq` | required on `step`; must name a `steps-planned` of this unit |
| evidence file | JSON `{verdict, exit_code, mode, command, reason}`; digests never typed |
| `--output-file` (`step`) | `realpath` inside `.dogen/staging/<id>/scratch/`; anything else → 2 `bad_write_path`. Not merely "inside the repository": up to 4096 bytes of it are excerpted **verbatim** into the committed ledger and the excerpt is control-character-stripped, never credential-stripped, so an in-repo `.env.local` or `.git/config` would be published by the next transition. `.dogen/staging/<id>/` and `.dogen/staging/<id>/scratch/` are `islink`-checked by name FIRST: `realpath` resolves both operands, so a containment test anchored on a symlinked directory resolves through the link and passes for every target |
| `unit.md` | the exact subset below |
| context artefact name | one of `doc-style.md`, `glossary.md`, `structure.md`, `code-to-docs-map.md`, `doc-gaps.md`; anything else → 2 `bad_target` |
| context body (`context stage --body-file`) | UTF-8, non-empty; recorded byte for byte, never re-encoded |
| context source (`context stage --source`, repeatable) | one line, non-empty, ≤ 1024 bytes, ≤ 500 per artefact; a locator the skill declares (a path, a URL, a tool-result id), recorded verbatim and never digested — the tool cannot see behind a URL |

`unit.md` frontmatter subset (not YAML; the tool always writes this shape):

```
---
title: "Validate a workshop definition"
intent: how-to
audience: "Workshop maintainers who edit workshop.yaml"
targets:
  - "how-to/validate-workshop-definition.rst"
sources:
  - "workshop/schema.json"
notes: "Steps must run offline."
---
<body: the plan outline, free Markdown>
```

Required: `title`, `intent`, `audience`, `targets` (≥ 1); optional `sources`, `notes`.
`intent ∈ {tutorial, how-to, reference, explanation}` (`tutorial`, `how-to` actionable).
Scalars: JSON double-quoted string, or bare text with no `#`, `: `, leading quote, `[` or `{`.
Lists: `key:` then `  - <scalar>`. Anything else → 2 `unit_invalid` with the line number and the
flag: `title → --title`, `intent → --intent`, `audience → --audience`, `targets → --target /
--also-target`, `sources → --source`, `notes → --notes`, body → `--body-file`.

## 5.7 Verb order, per-verb preconditions, refusals

Every mutating verb: **a** lock, `.git/index.lock`, chain, committed prefix, tail/pending
classification (5/6) → **b** input validation (2) → **c** per-verb preconditions (1), in the
listed order → **d** no-op recognition (3; payload = existing event's seq and commit **and the
current `next`**) → **e** content gates (1/4) → **f** write. Preconditions are defined **here
only**; the routing table is a rendering of them.

| Verb | c: preconditions (in order) | d: no-op | e: content gates |
|---|---|---|---|
| `draft` | retired · no_signoff · plan_stale · page_drift (changed bytes only; absence never blocks) · target_exists · steps_unresolved/steps_missing (4) | `identical_draft` per §5.4: generation exists, current signoff and steps context, no H since, **every signed target on disk already holds the staging bytes** | `unsteered` (only when a generation exists; a missing or hook-rewritten destination defeats the no-op but never waives this gate) |
| `review` fix/redraft | retired · no_signoff · no_generation · plan_stale · generation_stale | — | `note_required` (2) |
| `review` accept | as above · page_drift · target_missing (absence or unlisted target; checked after drift so an untouched deleted page reports `target_missing`) | `already_accepted`: tip is accept, not h_after(tip), same basis, not target_missing | `unapplied_steering` (pending ⊄ resolves ∪ withdraws; lists seqs) |
| `edits` | retired · no_signoff | `no_edits`: no existing basis file has changed bytes and no adoptable target (absence alone is not an edit) | — |
| `steer` | retired · no_signoff | — | — |
| `plan-steps`, `step` | retired · no_signoff · `not_actionable` (2 — the current signoff's `intent` is neither `tutorial` nor `how-to`; a reference or explanation page is drafted straight from its declared sources) | `already_recorded` (step: same `(steps_seq, step_id, verdict, exit_code, output_sha256, reason)`) — recognised **only against the current plan**, **only for a complete submission** and **only when the evidence's `mode` is the plan's**: a `--steps-seq` the current plan has superseded, a non-`skipped` verdict with no `--output-file`, and a divergent `mode` are all three e's, and d answering any of them would shadow the refusal that names the real problem — `mode` is not in the no-op tuple, so an identical capture resubmitted under the wrong mode would otherwise be reported "already on the record, field for field" when the field that matters differs | in this order: `evidence_stale` (4), `evidence_incomplete` (4), `evidence_mismatch` (4 — the evidence's `mode` is not the `mode` the plan declares for that step) |
| `signoff`, `unit edit --re-sign` | retired · claim policy | `already_signed` (same `plan_hash`) | — |
| `unit edit` (plain) | unit_not_found (2) · retired · claim policy when targets change | `noop_unchanged` (frontmatter and body unchanged) | — |
| `unit new` | unit_exists (2) · claim policy | — | — |
| `unit retire` | unit_not_found (2) | `already_retired` | — |
| `resume` | exempt from `retired`; see §5.8 | `nothing_to_resume` (no tail, no pending — also the result of calling `resume` again after a successful completion) | — |
| `context stage` | artefact name (2 `bad_target`) · body · sources | — | — |
| `context record` | at least one artefact staged (2 `bad_target`) | `noop_unchanged`: HEAD already holds every staged artefact's bytes at its published path — disk alone is never consulted, so a record whose commit was refused is retried, not no-op'd; the staged copies are discarded | — |

Reason table:

| Reason | Exit |
|---|---|
| `no_signoff` | 1 |
| `plan_stale` | 1 |
| `page_drift` | 1 |
| `target_exists` | 1 |
| `target_missing` | 1 |
| `generation_stale` | 1 |
| `unapplied_steering` | 1 |
| `unsteered` | 1 |
| `no_generation` | 1 |
| `target_claimed` | 1 |
| `retired` | 1 |
| `bad_target` | 2 |
| `bad_write_path` | 2 |
| `bad_draft_path` | 2 |
| `bad_resolution` | 2 |
| `unit_invalid` | 2 |
| `unit_exists` | 2 |
| `unit_not_found` | 2 |
| `step_unknown` | 2 |
| `not_actionable` | 2 |
| `note_required` | 2 |
| `git_identity_missing` | 2 |
| `not_a_repo` | 2 |
| `legacy_unit` | 2 |
| `identical_draft` | 3 |
| `already_signed` | 3 |
| `already_accepted` | 3 |
| `already_recorded` | 3 |
| `already_retired` | 3 |
| `no_edits` | 3 |
| `noop_unchanged` | 3 |
| `nothing_to_resume` | 3 |
| `steps_unresolved` | 4 |
| `steps_missing` | 4 |
| `evidence_stale` | 4 |
| `evidence_incomplete` | 4 |
| `evidence_mismatch` | 4 |
| `busy` | 5 |
| `git_busy` | 5 |
| `ledger_corrupt` | 6 |
| `ledger_version_unsupported` | 6 |
| `unit_id_mismatch` | 6 |
| `uncommitted_tail` | 6 |
| `ledger_diverged` | 6 |
| `resume_ambiguous` | 6 |
| `recovery_unsupported` | 6 |
| `adopt_unsupported` | 6 |
| `internal_error` | 6 |

`bad_target`, `bad_write_path`, `bad_draft_path` and `bad_resolution` are the `bad_*` family
rev8 names (§5.6, §5.11 T23, §8.1). Every non-zero exit prints one JSON line
`{"error","unit","detail","hint","next"}` on stderr (`--json`: stdout).

## 5.8 Write protocol and resume

Mutating verb (after a–e):

1. Write `pending/after/<path>` (intended bytes) and `pending/before/<path>` (current bytes or
   `.absent`) for every file the verb writes; then `pending/manifest.json` `{events:[exact
   lines], files:[{path, before_sha|null, after_sha}]}` via temp + `os.replace`; `fsync` all.
2. Append the event batch in one `write()`; `fsync` the ledger **before** any placement.
3. Place each file: copy `after/<path>` to a temp beside the destination, `os.replace`. Pending
   copies are not consumed. Record the paths just placed in `pending/progress.json` (temp +
   `os.replace`) **before** step 4 can fail, so pass 1 can tell "never placed" from "placed and
   rewritten since".
4. Snapshot `git diff --cached --name-only`; `git add -- <pathspecs>`; `git commit -- <pathspecs>`
   with trailers. The attempt is counted in `pending/progress.json` as `transition_attempts`,
   before **either** git call — so an add failure, a commit refusal and a run killed between the
   two all consume one; the counter is a count of attempts to complete the transition, never of
   refusals. A failed transition is 6 `uncommitted_tail` (hint `dogen resume <id>`) the first
   time and 6 `recovery_unsupported` from the **second** attempt on the same batch onward:
   resuming again would re-place the same bytes and fail the same way, and a hint that reproduces
   its own refusal is not an escape. The `detail` names **which** git call failed, because the two
   have different causes and different answers: `commit_rejected` for `git commit` (a hook, most
   often — inspect the repository's commit hooks) and `stage_rejected` for `git add` (an index
   that will not lock, an unstageable pathspec, a read-only `.git` — no hook has run, because the
   commit was never attempted).
5. **Post-commit check:** for each manifest file, digest of `git show HEAD:<path>` and of the
   disk file must equal `after_sha`. Mismatch = a hook changed bytes after recording: the
   transition stands (it is committed); the verb exits 0 with the warning `hook changed <path>
   after recording` and then **re-derives state and prints the routed `Next:`** — a changed page
   yields `record_edits`; a changed `unit.md` yields `plan_stale` → `re_sign`.
   On resume, a path already `unexpected` is reported as `still differs from the recorded
   bytes after resume` only if both the committed and final on-disk digests equal its
   pre-resume disk digest. If either changed, the `hook changed` warning still applies.
   If any path
   **outside the verb's explicit pathspecs** is staged after the commit that was not staged
   before, warn `hook staged unrelated paths: …` (never undone; the tool's own pathspecs leaving
   the index is normal and not warned).
6. Delete `pending/`; release the lock.

Stage-a classification of `pending/` and the tail, every verb. **Write boundary:** the
cleanup actions below are performed only by a mutating verb in write mode. `resume --dry-run`
and the read-only verbs (`show`, `summary`, `verify`) classify identically, print what write
mode would delete (`would delete pending/: <situation>`), and delete nothing; the same holds
for a stray `adopt/`. A dry-run leaves `ledger.jsonl`, every page, `pending/` and the index
byte-identical and exits with the classification result (0 resumable, 3 `nothing_to_resume`,
6 `resume_ambiguous` / `recovery_unsupported`); the next write-mode verb performs the cleanup
(T33; N-41).

| Situation | Action |
|---|---|
| no `pending/`, no tail | proceed |
| `pending/` without a complete manifest | delete it; proceed |
| complete manifest, none of its events in the ledger, no tail | delete it (nothing was placed: 2 precedes 3); proceed |
| all manifest events in the **committed** ledger, no tail | delete it (crash after 4/5); proceed |
| tail present, manifest present, tail is an exact byte-prefix of the batch (at most one truncated final line, itself a byte-prefix of the next expected line), chain verifies | 6 `uncommitted_tail`, hint `dogen resume <id>` |
| tail present but no manifest, or tail not a prefix of the batch, or any `after/`/`before/` copy fails its manifest digest, or a manifest event line is not canonical | 6 `recovery_unsupported` (detail: `no_material` / `tail_unknown` / `material_invalid` / `event_invalid`) with the expert recipe below; nothing written |
| committed prefix rewritten | 6 `ledger_diverged` with the git recipe |

`dogen resume <id> [--dry-run | --overwrite | --adopt --note]` (any unit, retired included):

**Pass 1 (read-only, always):** load and validate the manifest as above; classify each file:
`done` (disk == after), `recoverable` (step 3 had not yet placed this file and disk == before, or
absent with before null), `unexpected` (anything else — including a file step 3 **did** place
whose disk bytes are no longer the intended ones, even when they happen to equal `before`: this
tool wrote `after_sha` there, so anything else on disk is someone else's rewrite). The placement
record is `pending/progress.json`; absent, unreadable or malformed it reads as "nothing placed
yet", which is the pre-`progress.json` behaviour and never a worse answer than re-placing. Print
the classification. `--dry-run` stops here, having written nothing (stage-a cleanup included).

**Decision:** no `unexpected` → proceed. Some `unexpected` and no flag → 6 `resume_ambiguous`
with a per-file diff (disk vs intended) and the two choices; nothing written, both pages and
the ledger bytes untouched. `--overwrite` → treat `unexpected` as `recoverable` (author's
decision to discard). `--adopt --note` → allowed only when the batch's last event is a
`generation` or `reviewer-edit`; otherwise 6 `adopt_unsupported` (e.g. an interrupted
`--re-sign` with an edited `unit.md`: `--overwrite` restores the intended plan bytes, or use the
recipe). Adopt builds one `reviewer-edit` whose `files[]` is the **complete** batch file set
(unchanged paths with their recorded digests, unexpected ones with current digests),
`generation_seq` = the batch's generation seq, or the prior generation, or null if none, `note`
= the author's note + "(bytes changed outside dogen after recording; retained by the author)",
`hook:true`. **Persistence invariant: every published manifest references durable copies
matching all of its recovery digests.** Adopt therefore (i) copies each unexpected file's
current bytes to `pending/adopt/<path>` and `fsync`s them; (ii) publishes the revised manifest
(temp + `os.replace`) whose `after` entries for those paths point at `adopt/` with the new
digests and whose event batch gains the reviewer-edit line — the original `after/` copies and
the generation's event bytes are left untouched; (iii) appends and continues as pass 2. A crash
before (ii) leaves the old manifest authoritative and `adopt/` is deleted as stray on the next
write-mode run (a dry-run reports it); a crash after (ii) and before the append classifies as
"tail is a prefix of the batch" and plain `resume` completes it; a repeated `--adopt` finds the
line already in the batch and completes it without appending a duplicate. With
`unexpected` files, bare `resume` still refuses `resume_ambiguous`: repeated `--adopt`
retains the current bytes without another event or note; `--overwrite` restores the saved
adoption bytes. Follow the route derived after the commit: retained divergence calls for
`edits`, while a hook that restores the recorded bytes clears the drift. An unused note is
reported in a structured `notices` field on BOTH outcomes — beside `ok`/`message`/`next` on
the `--json` success document, and in the refusal's own `notices` if completion fails — and as
stderr prose after a success (a refusal stays a single JSON line on stderr). The other
post-commit notices the verb can raise — retained drift, and a state derivation that could not
be re-run after the commit — exist only once the commit has landed, so they travel with the
success outcome alone.
`--adopt`
with zero `unexpected` files is a plain resume, and needs no `--note`: the note is required for
the reviewer edit an adopt writes, and a plain resume writes none. Symmetrically, `--note`
without `--adopt` is 2 `bad_target` — a note is the record of a decision, and there is no
decision here to attach it to; it is never accepted and silently discarded.

**Pass 2 (write, only after the decision):** truncate the partial line; append the missing
batch lines (exact bytes; chain re-verified); place `recoverable` files; commit with the
manifest's pathspecs; run the post-commit check; delete `pending/`.

**Honest limit (`recovery_unsupported`).** `commit_rejected` and `stage_rejected` (step 4,
above) are the two `recovery_unsupported` details the write path raises, and for both the batch
IS appended and the files ARE placed; every other detail below is stage a's, and for
those the tool writes nothing and prints what it found:
the uncommitted tail seqs; for every path it can identify (from the tail events, and from the
manifest if any part of it is readable) whether the disk bytes equal the recorded digest, the
HEAD bytes, or neither; and which paths it cannot account for. It then states the safety
boundary rather than a universal recipe: **the current unit directory and every file whose
bytes it cannot attribute are preserved**; nothing is restored from HEAD, because HEAD holds
committed history, not necessarily the pre-operation bytes (`unit.md` may carry legitimate
uncommitted author changes; a placed page may have replaced uncommitted work). Supported expert
steps, printed only where the evidence supports them: the tail was never committed, so removing
those lines from `ledger.jsonl` (after inspection) returns the record to its committed prefix; a
page whose disk bytes match the interrupted operation's recorded output carries evidence, not
proof, that the operation wrote it; the author decides whether to discard or keep it; for a lost
`unit new` (no ledger in HEAD), move `.dogen/units/<id>/` aside for inspection
(`mv … .dogen/staging/recovery-<ts>/`), never delete it. Where a complete safe restore cannot be
derived the tool says "expert intervention required" and stops. No `void` event, no claim that
the record is truthful, no "commit it and continue". Corrupt or invalid event lines are never
legitimised by committing them.

Hooks: a hook that rewrites a target and **rejects** the commit ends in `resume_ambiguous` →
`--adopt`; a hook that rewrites and **succeeds** ends in the post-commit warning → `edits`. This
holds for **both** rewrite shapes, and the second is the common one: a canonicalising hook whose
output happens to equal the target's own pre-transition bytes (the steady state once the hook has
been adopted once) restores `before_sha`, and only the step-3 placement record keeps that from
reading as `recoverable` and sending `resume` around the same rejection forever. Where the loop
cannot be broken by classification alone — `--overwrite` re-places the intended bytes the hook
will reject again — the second failed commit on one batch is 6 `recovery_unsupported`
(`commit_rejected`) naming what refused it, never a third identical `dogen resume <id>` hint. In
both cases the recorded note says a hook changed the bytes and the author retained them; a
formatter is not a reviewer. Restoring the intended bytes instead is a re-draft from staging
after `edits` (the no-op rule compares against the destination, which now holds the hook's
bytes, so it is not suppressed; `edits` is not steering, so the redraft needs a recorded `steer`
first), which the hook will rewrite again: the supported behaviour with a formatting hook on
target paths is "adopt", and the README says so. Both hook shapes are fixtures (N-15, N-36) and
are tried on a real repository's hooks in a full session.

## 5.9 What dogen verify reports

**Record integrity (FAIL):** V1 header; V2 lines parse, canonical, within caps; V3 seq and
chain; V4 committed prefix; V5 every generation cites the signoff current at its seq with equal
`plan_hash`, every accept's generation cites the signoff current at the accept's seq; V6 every
review cites the last generation at its seq; every reviewer-edit's `generation_seq` is the last
generation at its seq or null iff none existed; accept `files` == basis; V7 no two generations
without an intervening H unless `unsteered:true` with reason; V8 step hashes, each record's `mode` equal to its plan step's, and evidence shape;
V9 actionable generations had all steps resolved at their seq; V10 every accept's `pending` at
its seq ⊆ `resolves ∪ withdraws`, those ⊆ pending, disjoint, every withdrawal with a reason;
V11 model/origin consistency; V12 `reuse` has `reuse_note`; V13 every generation's `files[]`
equals the current signoff's targets at its seq; every reviewer-edit's `files[]` is a superset of
the previous basis minus missing non-targets.

**Page currency (status):** V14 per basis path `current` / `drifted` (+ commits since,
`Dogen-Unit` ones marked) / `missing`; orphans listed.

**Git corroboration (WARN/INFO):** V15 committed seq ranges have trailer commits in order, else
WARN `history_squashed`; V16 `event.commit` ancestry; V17 ignore/attributes patterns and
`check-ignore`; V18 target overlap with non-retired units; V19 context digests vs signoff;
`plan_stale` → WARN. ~`superseded_by`~ reserved, not evaluated.

Unknown kinds: ignored for derivation and verification with one WARN; gates over known kinds
only; a state-affecting new kind requires contract 2. History policy: squash merge → green except
`history_squashed`; cherry-pick without the ledger line → `ledger_diverged`; later maintenance
edits → `drifted`, never FAIL.

This section is contract as of `contract-v1`; the code that implements it lands in phase 17.

## 5.10 Compatibility

| Number | Value |
|---|---|
| `contract` | `1` |
| `min_tool` | `0.2.0` |

`contract: 1` in every event; `metadata.dogen_contract: 1` and `metadata.dogen_min_tool:
"0.2.0"` in every SKILL.md; `dogen version --json` → `{"tool","contract"}`; a skill stops only on
contract mismatch or a tool older than `min_tool`. Contract 2 = rename/removal, enum change,
state-affecting kind, canonicalization change; no in-place migration. Legacy units: 2
`legacy_unit`, archive hint.

A ledger whose header event's `v` is not this tool's `contract` is never half-read: stage a
refuses it 6 `ledger_version_unsupported` on **every** verb, read-only ones included, beside the
`unit` check and before the committed-prefix check, with the same archive-never-migrate hint.
`verify`'s V1 reports the same fact for a record it is allowed to read. Both header writers
stamp the tool's own `contract`, so a freshly written ledger can never fail its own V1.

The two numbers above are compared as literal strings by `tests/check_docs.py`; they are never
parsed or rounded as versions.

**Revision (`internal_error`).** §5.7's reason table gains one row: `internal_error`, exit 6,
raised only by `main`'s blanket fault arm when dogen itself falls over below the verb. The
addition is additive under `contract: 1` — the two numbers above are unchanged, and so are the
`metadata.dogen_contract` and `metadata.dogen_min_tool` values in every SKILL.md. The reading:
this section's "enum change" names a rename, a removal, or a semantic change to an existing
member, and a new refusal reason is none of those. No caller can provoke it by using the tool
correctly; the only callers that meet it are the ones the arm previously answered
`ledger_corrupt` — telling them their own hash-chained record was damaged, and routing them at a
recovery verb, for a defect in dogen. The exit code does not move: 6 is the record-and-recovery
code and the arm already used it.

That reading reverses an earlier one, and both are recorded here rather than only the one that
won. The phase-16 round-5 fix report classified this same row as "a contract-v2 change" and
deferred it on that basis. Under the stricter reading the row belongs in contract 2, with
`min_tool` and three SKILL.md metadata values moving beside it and every existing ledger's header
event refusing 6 `ledger_version_unsupported` on every verb until its unit is archived — a
migration this contract explicitly does not offer. The reading above is what this revision ships
on, and it goes to review with the pull request that lands the row.

**Revision (context verbs).** §6 gains `context stage`, `context record` and `context show`; §5.1
gains the three artefact rows they own; §5.5 gains the context routing table and its three
tokens (`record`, `onboard`, `plan`); §5.7 gains their precondition rows. The addition is
additive under `contract: 1` by the same reading as the row above: no event kind is added,
renamed or removed — `context record` writes no event and never opens a unit ledger — no
existing member of any enum changes meaning, and no reason is added to the reason table. A
ledger written before this revision derives exactly as it did; a tool from before it simply
does not know the verbs, which `dogen --help` and `tests/check_docs.py` make visible rather
than silent. The two numbers above are unchanged, and so are every SKILL.md's
`metadata.dogen_contract` and `metadata.dogen_min_tool`.

## 6 Verb table

| Verb | Key args | Events |
|---|---|---|
| `unit new <id> --intent --audience --title --target [--also-target]… [--source]… [--notes] --body-file -\|F` | | `ledger`, `unit-declared` |
| `unit edit <id> [flags] [--body-file -] [--re-sign]` | | `unit-edited` (+ `signoff`) |
| `unit retire <id> --note` | | `retired` |
| `signoff <id>` | | `signoff` (+2 on adoption) |
| `steer <id> --note\|--note-file - [--origin]` | | `steering` |
| `plan-steps <id> --steps-file -\|F [--keep-evidence --note]` | | `steps-planned` |
| `step <id> <step-id> --steps-seq N --evidence-file F [--output-file F]` | | `step-recorded` |
| `draft <id> <staging file\|dir> [--model --model-origin] [--report F] [--unsteered-reason T]` | | `generation` |
| `edits <id> --note\|--note-file -` | complete basis set; brownfield adoption | `reviewer-edit` |
| `review <id> --verdict accept\|fix\|redraft --note\|--note-file - [--resolves a,b] [--withdraw <seq> "<reason>"]…` | | `review` |
| `resume <id> [--dry-run\|--overwrite\|--adopt --note]` | two-pass | batch completion (+ `reviewer-edit`) |
| `context stage <name> --body-file -\|F [--source]…` | repo-level; tool-owned staging | — |
| `context record [--model --model-origin] [--note]` | repo-level; one commit, no unit | — (manifest) |
| `context show [--json]` | read-only | — |
| `show <id> [--json\|--diff]`, `summary <id> [--json\|--md]`, `verify <id> [--json]`, `version [--json]` | read-only | — |

## 5.11 Traces

Normative; each is a test; outcomes follow from §5.4–5.8.

| # | Trace | Outcome (rule) |
|---|---|---|
| T1 | gen → fix F → unrelated edit → `edits` → accept | 1 `unapplied_steering` (§5.7 e); `--resolves F` or `--withdraw F "…"` seals |
| T2 | gen → F1 → F2 → `edits` → `accept --resolves F1` | 1 `unapplied_steering` (F2) |
| T3 | gen → steer S → gen2 → accept | 0; S non-pending (pending counts from gen2) |
| T4 | sealed → steer S → accept | 1 `unapplied_steering`; state `reviewed` |
| T5 | gen → hand edit **committed** outside dogen → steer → draft | 1 `page_drift` (c); `edits` → draft 0 |
| T6 | gen → `edits` → draft, staging differs from the edited destination | 1 `unsteered` (e); with staging equal to the edited destination the outcome is 3 `identical_draft` (d precedes e) |
| T7 | gen → `edits` → steer → draft | 0; basis = edit |
| T8 | draft A → `--re-sign` → accept | 1 `generation_stale` (c); `show`: `reviewed`/`drafted` + qualifier, `next: draft` |
| T9 | sealed → `--re-sign` → hand edit → `edits` → draft | `edits` 0 (no drift/stale precondition on edits); draft 0 (signoff ∈ H) |
| T9b | draft A → `--re-sign` (audience only) → hand edit → accept | 1 `generation_stale` before drift; routing 4→(none)→5 `record_edits`; after `edits` still `generation_stale` → draft |
| T10 | accept → later steer → accept retry | 1 `unapplied_steering`, not `already_accepted` |
| T11 | draft → identical retry, no H | 3 `identical_draft` with existing seq/commit and current `next` |
| T12 | P1 → steps → `plan-steps` P2 (no reuse) → draft | 4 `steps_unresolved`; with `--keep-evidence --note` + identical prefix → 0 |
| T13 | P1 → P2 (reuse) → P3 (reuse), step 3 changed in P2 | steps ≥ 3 unresolved in P3 |
| T14 | old output with old `--steps-seq`, no reuse | 4 `evidence_stale`; exact duplicate under reuse → 3 `already_recorded` |
| T15 | two-file draft, crash after page 1 placed | resume: page 1 `done`, page 2 `recoverable`, commit |
| T16 | hook rewrites page 2 — a **new** page, so no pre-transition bytes — and rejects commit | `resume_ambiguous` → `--adopt` → reviewer-edit with **both** pages (1 recorded, 2 current), commit |
| T16b | hook rewrites an **existing** page back to its own pre-transition bytes and rejects; hook still installed across the resume | the page is `unexpected` (step 3 placed it), not `recoverable`; `resume_ambiguous` → `--adopt` commits; a second `--overwrite` attempt on one batch ends 6 `recovery_unsupported` (`commit_rejected`), never a loop |
| T17 | draft fails at commit; author edits page while fixing; pending intact | `resume_ambiguous`; `--adopt` keeps; `--overwrite` discards |
| T17b | two-file: page 1 `recoverable`, page 2 human-edited after failure | pass 1 → `resume_ambiguous`; **nothing written** (pass 2 never runs) |
| T18 | crash between manifest and append | next verb deletes pending |
| T19 | `--re-sign` crash after first line | tail is a prefix → resume appends the second line, commits |
| T19b | interrupted `--re-sign`, `unit.md` edited meanwhile | `resume_ambiguous`; `--adopt` → 6 `adopt_unsupported`; `--overwrite` or recipe |
| T20 | crash after commit before cleanup | next verb deletes pending |
| T21 | `retire` commit fails | resume commits it |
| T22 | `index.lock` present | 5 `git_busy`; nothing written; retry |
| T23 | write `docs/<target>` first, pass it as source | 2 `bad_draft_path` |
| T24 | brownfield, single existing page | `target_exists` → `edits` (files=[page], gen null) → routing 6 → draft 0 → review |
| T24b | brownfield: one existing + one new target | adopt lists the existing page only; draft writes both; generation lists both |
| T24c | `edits` twice before the first draft | second → 3 `no_edits` |
| T25 | unknown kind between two generations | WARN once; V7 over known kinds |
| T26 | gen for `old.rst` → `--re-sign` to `new.rst`, nobody edits | no drift (old matches), no `target_exists`; draft writes `new.rst`; `old.rst` reported once as orphan, kept |
| T26b | same, author `git mv old new` by hand | `old` missing (not drift; no longer a target, so not `page_missing` either); `new` non-empty and not in the basis → `target_exists` → `record_edits`; `edits` records `[new]` (old dropped: missing and no longer a target); draft |
| T26c | author deletes a **current** target → accept | 1 `target_missing` (absence is not drift, so `page_drift` does not fire first) |
| T26d | sealed → author deletes a current target → `show` → steer "restore" → draft (staging holds the page) → accept | `show`: `missing`, `next: steer`; draft 0 (signoff/steering current; absence never blocks; not a no-op because the destination is missing); accept 0 |
| T26e | drafted → author deletes a current target → `edits` → draft (no new steering) → steer "restore" → draft | `edits` 3 `no_edits` (absence alone is not an edit; basis keeps the last digest); first draft 1 `unsteered` (not a no-op, gate not waived); after `steer` draft 0, page restored → review |
| T11b | identical staging bytes, one destination missing, no H since the generation | not a no-op; 1 `unsteered` |
| T11c | T11b after `steer "restore"` | generation recorded, page restored, `next: review` |
| T24d | brownfield basis, first draft with bytes equal to the adopted page | not a no-op (no generation exists); generation recorded |
| T27 | `--adopt`: crash **before** the revised manifest is published | old manifest authoritative; `adopt/` deleted as stray; `resume` classifies as before |
| T27b | `--adopt`: crash **after** the revised manifest, before the append | tail is a prefix of the revised batch; plain `resume` appends the adopt line and completes; material validation passes (adopt copies durable) |
| T27c | re-run `--adopt` after T27b | line already in the batch → plain resume; no duplicate event |
| T28 | tail present, no manifest (material lost), page 1 placed | 6 `recovery_unsupported` (`no_material`): findings printed; nothing written; unit dir and both pages preserved; supported steps named only for attributable paths |
| T28b | lost `unit new` (ledger not in HEAD), hand-written `unit.md` | recipe moves the unit dir aside for inspection; never deletes; `unit.md` content preserved |
| T29 | hook rewrites a page and **succeeds** | commit stands; warning; state re-derived → `next: record_edits`; `edits --note` records the hook change, with the note as the carrier and **no** `hook:true` — §5.3 scopes that field to `resume --adopt`, where the author was asked and answered. A succeeding hook's rewrite is committed before anyone is asked, so `edits` cannot distinguish it from a hand edit and must not claim to |
| T29b | hook rewrites `unit.md` and succeeds | commit stands; warning; state re-derived → `plan_stale` → `next: re_sign` |
| T29c | hook stages an unrelated path outside the pathspecs | warning names the path; nothing undone; the tool's own pathspecs leaving the index is not warned |
| T30 | `--resolves 12 --withdraw 12 "…"` | 2 `bad_resolution` (disjoint) |
| T31 | plain `unit edit` with no change; `unit edit` that adds a target claimed by another non-retired unit | 3 `noop_unchanged`; 1 `target_claimed` |
| T32 | `resume` after a successful completion, or with nothing pending | 3 `nothing_to_resume` |
| T33 | `resume --dry-run` with (a) `pending/` without a manifest, (b) a completed batch awaiting cleanup, (c) a stray `adopt/`, (d) a resumable tail | prints the classification and what write mode would delete; ledger, pages, `pending/` and index byte-identical before and after; the next write-mode verb performs the cleanup |
| T34a | drafted unit, author deletes a current target, explicitly asks to restore it | accept never retried; the review skill records the request via `steer` without reconfirming and routes to `/dogen-write`; draft 0, page restored → review |
| T35 | `context stage` three artefacts → `context record` | one commit, subject `dogen: context recorded`, pathspecs = the three files + `manifest.json`, trailers `Dogen-Phase`/`Dogen-Head` and no `Dogen-Unit`; every manifest digest equals the committed bytes; staging cleared; `Next: plan` |
| T35b | `context stage profile.md`; a stray file in `_context/` at record time | 2 `bad_target` naming the five artefacts; 2 `bad_target` naming the stray file; nothing promoted |
| T35c | record → stage the same bytes → record; then stage one changed artefact → record | 3 `noop_unchanged` with the last commit, staged copies discarded; then one commit promoting the changed artefact while the manifest keeps every other published row |
| T36 | recorded artefact hand-edited on disk → `context show`; `context record` with nothing staged | `drifted` named, exit 0, nothing refused; 2 `bad_target` (nothing staged), `next` per context routing |
| T34b | drafted unit, author deletes a current target, asks to accept without explaining | accept 1 `target_missing`; the skill explains that the signed plan still lists the target and asks restore-or-amend; no `steering` event is recorded until the author answers; "amend" → `--re-sign` without the target (old page reported as orphan, kept) → `generation_stale`, the old generation cannot be accepted → draft → review |

## Trace table

One row per trace in §5.11, in §5.11's order; traces whose outcomes compare equal keep that
source order, so the table is stable across regenerations. The governing-rule cell names the
section the outcome follows from — this is the closure rule of §"Mechanisms" made checkable.

Test ids are reserved from rev8's own series (A-01…A-35, N-01…N-41, U-01…U-10, S-01…S-09,
V-01…V-04); ids beyond a series' rev8 range are the next free id in that series. At
`contract-v1` this table was phase 17's work list and no trace test had been written yet; phase
17 cleared a mark as each test landed, and plan 17-11 cleared the last of them. Every row below
now names a test FUNCTION that exists, which `tests/check_traces.py` re-proves by grepping the
suites for a function whose name carries the id. That is the whole of the claim: the checker does
not read the function's body, so it cannot re-prove that the outcome this row states is the
outcome that test asserts. A row can therefore be "cleared" while its clause is unexercised in the
shape that matters, or unimplemented — WR-12, which CR-01 (T16) and WR-05 (T29) were both
instances of. Keeping a row honest is the reviewer's job at the point the test is written or
moved. No cell is ever blank.

| T# | Governing rule (§) | Test id |
|---|---|---|
| T1 | §5.7 e (`unapplied_steering`) | N-20 |
| T2 | §5.7 e (`unapplied_steering`) | N-21 |
| T3 | §5.4 (`pending` counts from the last generation) | N-43 |
| T4 | §5.4 (state `reviewed`) · §5.7 e | N-22 |
| T5 | §5.7 c (`page_drift`) | N-10 |
| T6 | §5.7 d then e (`identical_draft` precedes `unsteered`) | N-11 |
| T7 | §5.4 (basis = latest of gen, edit) | N-11 |
| T8 | §5.7 c (`generation_stale`) | N-19 |
| T9 | §5.7 c (no drift/stale precondition on `edits`) · §5.4 (signoff ∈ H) | N-44 |
| T9b | §5.5 routing 4→5 · §5.7 c | N-19 |
| T10 | §5.7 e (`unapplied_steering` before the accept no-op) | N-23 |
| T11 | §5.7 d (`identical_draft`) | N-45 |
| T12 | §5.4 step status · §5.7 c (`steps_unresolved`) | N-27 |
| T13 | §5.4 step status (reuse prefix) | N-27 |
| T14 | §5.7 e (`evidence_stale`) then d (`already_recorded`) | N-27 |
| T15 | §5.8 pass 1/pass 2 | N-14 |
| T16 | §5.8 hooks · `--adopt` | N-15 |
| T16b | §5.8 pass 1 (step-3 placement record) · hooks | N-46 |
| T17 | §5.8 decision (`resume_ambiguous`) | N-17 |
| T17b | §5.8 decision (nothing written before pass 2) | N-35 |
| T18 | §5.8 stage a (manifest, no events) | N-28 |
| T19 | §5.8 stage a (tail is a byte-prefix) | N-29 |
| T19b | §5.8 decision (`adopt_unsupported`) | N-29 |
| T20 | §5.8 stage a (committed batch awaiting cleanup) | N-30 |
| T21 | §5.8 step 4 · pass 2 | N-13 |
| T22 | §5.8 stage a (`.git/index.lock`) | N-42 |
| T23 | §5.6 (draft source containment) | N-31 |
| T24 | §5.5 routing 5→6 · §5.4 (brownfield basis) | N-26 |
| T24b | §5.4 (generation `files[]` = signed targets) | N-26 |
| T24c | §5.7 d (`no_edits`) | N-26 |
| T25 | §5.9 (unknown kinds; V7 over known kinds) | V-05 |
| T26 | §5.4 target changes (orphans kept) | N-33 |
| T26b | §5.5 routing 5 · §5.4 target changes | N-34 |
| T26c | §5.7 c (`target_missing` after `page_drift`) | N-34 |
| T26d | §5.5 routing 8b · §5.4 (absence never blocks drafting) | N-34 |
| T26e | §5.7 d (`no_edits`) then e (`unsteered`) | N-34 |
| T11b | §5.4 `identical_draft` · §5.7 e (`unsteered`) | N-39 |
| T11c | §5.4 (steering recorded; destination restored) | N-39 |
| T24d | §5.4 `identical_draft` (no generation → never a no-op) | N-39 |
| T27 | §5.8 adopt persistence invariant (i) | N-37 |
| T27b | §5.8 adopt persistence invariant (ii) | N-37 |
| T27c | §5.8 adopt idempotence | N-37 |
| T28 | §5.8 honest limit (`recovery_unsupported`) | N-38 |
| T28b | §5.8 honest limit (lost `unit new` recipe) | N-38 |
| T29 | §5.8 step 5 (hook changed, commit stands) | N-36 |
| T29b | §5.8 step 5 (hook changed `unit.md` → `re_sign`) | N-36 |
| T29c | §5.8 step 5 (hook staged unrelated paths) | N-36 |
| T30 | §5.6 (`--resolves`/`--withdraw` disjoint) | N-32 |
| T31 | §5.7 d (`noop_unchanged`) · §5.1 claim policy | N-40 |
| T32 | §5.7 d (`nothing_to_resume`) | N-40 |
| T33 | §5.8 stage-a write boundary (dry-run) | N-41 |
| T34a | §5.5 routing 8b · §5.4 (restoration request via `steer`) | S-09 |
| T34b | §5.7 c (`target_missing`) · §5.4 target changes | S-09 |
| T35 | §5.3 (repo-level commit) · §5.1 (`manifest.json`) · §5.5 C3 | N-47 |
| T35b | §5.6 (context artefact name) | N-47 |
| T35c | §5.7 d (`noop_unchanged` against HEAD) · §5.1 (partial re-stage keeps the set) | N-47 |
| T36 | §5.1 (`drifted`, reported never refused) · §5.5 C1–C3 | N-47 |

Related: [[architecture]], [[hooks]], [[compatibility]].
