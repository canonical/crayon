Load this file at the start of the actionable (tutorial/how-to) walk branch.

# Walk protocol — evidence, capture, consent, workspace, resume

The operational core of the walk. The SKILL.md holds the step sequence; this file
holds the mechanics: the evidence contract the step gate enforces, the capture
mechanics for both execution modes, the just-in-time consent gate and destructive
backstop, the workspace lifecycle, and resume detection.

## The step gate (`dogen-record-step.sh`)

Every step's evidence is recorded through `dogen-record-step.sh`, which enforces
the micro-gate and commits the step. Exit codes:

| exit | meaning | skill branch |
|---|---|---|
| 0 | evidence recorded; step resolved (or `fail` recorded, stays `unverified`) | continue the walk |
| 1 | evidence incomplete — missing `verdict`, `output_sha256`, `exit_code` (pass/fail), `reason` (skipped/deviated), or `step_text_sha256` | re-capture with well-shaped proof; never fabricate |
| 2 | bad input — unknown step id, missing evidence file, or path traversal in the unit id | fix the step id / evidence file path |
| 3 | stale evidence — the evidence's `step_text_sha256` no longer matches the step's recorded `text_hash` | re-capture against the current step text, or update the ledger's `text_hash` |

A recorded `fail` keeps the step `status: unverified` (default-FAIL); only
`pass` / `skipped` / `deviated` resolve it. It is the walk's own
all-steps-resolved check at draft time — not the step record — that refuses over
an unresolved step.

## The step plan (ledger `## steps`)

The step plan lives in the ledger's `## steps` section, one pipe-delimited row per
step:

```
step-1 | text_hash: <sha256 of step text> | status: unverified
```

Each step's `text_hash` is the SHA-256 of its text — the staleness bind. Write the
plan directly with `Edit` (the SKILL.md does this); there is no separate
plan-file or plan verb. Committing the plan is done through the shared commit
helper (see SKILL.md step 2).

## Capture mechanics

The evidence-file is a simple `key: value` mapping — no prose "result" field, only
`output_sha256` + `exit_code` (+ `reason` for `skipped`/`deviated`) prove a step.

**Agent-runs (default):** run cwd-pinned in the workspace, tee the full bytes,
digest them, record the command in workspace-anchored form:

```bash
WS=".dogen/staging/$UNIT/scratch"; mkdir -p "$WS/evidence"
( cd "$WS" && foo --version ) 2>&1 | tee "$WS/evidence/verify.out"; echo "exit:${PIPESTATUS[0]}"
SHA=$(sha256sum "$WS/evidence/verify.out" | cut -d' ' -f1)   # shasum -a 256 on macOS
HASH=$(sha256sum step-text-file | cut -d' ' -f1)             # the step's text_hash from the ledger
cat > "$WS/evidence/verify.evidence" <<YAML
verdict: pass
mode: agent
command: "cd $WS && foo --version"
output_sha256: "$SHA"
exit_code: 0
step_text_sha256: "$HASH"
YAML
scripts/dogen-record-step.sh "$UNIT" verify --evidence-file "$WS/evidence/verify.evidence"
```

**TA-runs:** print the exact copy-pasteable command with capture built in, let the
TA run it, then ingest the tee'd file **unmodified**:

```bash
foo login 2>&1 | tee .dogen/staging/$UNIT/scratch/evidence/login.out; echo "exit:${PIPESTATUS[0]}"
```

If the TA pastes chat output instead, write the paste to the evidence file verbatim
— never re-type, never paraphrase a narration into evidence.

**Improvisation → `deviated`:** when the planned step did not say *how*, record
`deviated` with exit 0 and a `reason` — it still resolves AND the reason rides the
evidence record (see `episode-taxonomy.md`).

## Just-in-time consent + destructive backstop

A step's destructive/stateful marker is proposed at plan review and vetoed/corrected
by the TA there. Permission for a marked step is asked **just-in-time**, right
before that step executes — informed by what prior steps actually did. An **unmarked**
command that smells destructive (`rm -rf`, `git reset --hard`, `docker … prune`, a
write outside the workspace) **re-prompts via the runtime backstop instead of
running**. Consent is confined to genuinely dangerous steps — never a confirm-parade.
The marker is conversational (no persisted field); the backstop is the safety net,
so safety never depends on persistence. A step the TA will not consent to can be
switched to TA-runs.

## Workspace lifecycle

The walk workspace is `.dogen/staging/<id>/scratch/`, with an `evidence/` subdir
for the tee'd captures. Agent-runs commands are `cd`-pinned into it and recorded
in workspace-anchored form so the transcript proves where each ran. Only a
stateful-marked step touches real state, via the JIT-consent path.

The workspace lives under `staging/`, which is gitignored (the seeded
`.dogen/.gitignore`), so it never leaks into commits. It persists across sessions,
so resume finds evidence and produced state intact. The `evidence/` subdir is never
a cleanup target — move-never-delete; a cleanup step must not reach `evidence/`,
`docs/`, or `.git`.

Honest framing: the cwd-pin is a **skill-level tripwire**, not a verified sandbox —
never claimed as a guarantee.

## Resume detection

Read the ledger's `## steps` section directly — no summary verb:

```bash
grep '^step-' .dogen/units/"$UNIT"/ledger.md   # each row: status unverified|resolved
```

`status ∈ {resolved, unverified}`. When a plan exists with some `unverified` steps,
offer resume as the **default**: show the step-status table, trust every `resolved`
step's evidence, and continue at the first `unverified` step. An edited step
auto-reverts to `unverified` (its `text_hash` no longer matches its evidence's
`step_text_sha256`), so "only unverified steps re-verify" is purely derived — no
stored resume state.