Load this file at workflow step 1 (Open or resume).

# Walk protocol — reason codes, capture, consent, workspace, resume

The operational core of the walk. The SKILL.md holds the step sequence; this file
holds the mechanics: the reason-code→branch map the skill keys off, the capture
mechanics for both execution modes, the just-in-time consent gate and destructive
backstop, the workspace lifecycle, and resume detection.

## Reason-code → branch map

Every persistence action shells a `dogen record`/`dogen draft` verb and reads the
`--json` `reason`; branch on it in plain language, never re-judge "done" in prose.
The codes are the CLI's shipped vocabulary (append-only; none added this phase):

| reason (exit) | meaning | skill branch |
|---|---|---|
| `evidence_required` (1) | `record step` micro-gate: a `pass`/`fail` lacked a hash or exit code, or a `skipped`/`deviated` lacked its reason | re-capture with well-shaped mechanical proof; never fabricate a hash or exit code |
| `evidence_incomplete` (1) | `draft`/`review accept` macro-gate: steps are present and not all verified | route back into the walk at the unresolved step(s), resolve, then re-record |
| `bad_steps_file` (2) | the `--steps-file` YAML failed validation at the compose root | fix the emitted plan file shape and re-emit — nothing crossed into core |
| `bad_evidence_file` (2) | the `--evidence-file` YAML failed validation | fix the emitted evidence file shape and re-emit |
| `unknown_step` (2) | the `step_id` is not in the recorded plan | run `record plan` first, or fix the id |
| `unit_not_found` (1) | the unit is undeclared | route to `dogen unit new` + `dogen signoff` (D-09) |

A recorded `fail` **succeeds** (its derived status stays `unverified`); it is the
macro-gate at draft/accept, not the step record, that refuses over an unresolved
step.

## The steps-file contract (`record plan`)

A YAML **list** of step mappings, validated into typed `Step` at the compose root.
Any inlined `evidence:` is ignored (carry-forward is by text hash), so it is never
a channel for forging proof.

```yaml
- id: install                 # stable single-line label; the Dogen-Step trailer value
  text: "Install the CLI with `uv tool install foo`"   # its SHA-256 is the staleness bind
  assumptions: ["uv is on PATH"]        # REC-04 — persisted, surfaced as deltas
  invariants: ["no network egress beyond PyPI"]
  consumed: []                          # REC-05 — free-text state in
  produced: ["foo binary on PATH"]      # free-text state out
  deterministic: true                   # false ⇒ single-sample asterisk (Pitfall 7)
- id: verify
  text: "Run `foo --version` and confirm it prints 0.3.x"
```

```bash
printf '%s' "$STEPS_YAML" | dogen record plan "$UNIT" --steps-file - --json
```

**Whole-plan replace with carry-forward (D-12):** `record plan` fully replaces the
step plan; a step whose **text hash is unchanged keeps its recorded evidence**,
changed/new steps derive `unverified`. There is no `--force` and no frozen state —
the hash-bind makes every edit and mid-walk re-plan (branching) safe, re-verifying
only the changed step.

## Capture mechanics (REC-03)

The evidence-file is a YAML **mapping** with no prose "result" field — only
`output_sha256` + `exit_code` (+ `reason` for `skipped`/`deviated`) prove a step.

**Agent-runs (default):** run cwd-pinned in the workspace, tee the full bytes,
digest them, record the command in workspace-anchored form (D-08):

```bash
WS=".dogen/staging/$UNIT/scratch"; mkdir -p "$WS/evidence"
( cd "$WS" && foo --version ) 2>&1 | tee "$WS/evidence/verify.out"; echo "exit:${PIPESTATUS[0]}"
SHA=$(sha256sum "$WS/evidence/verify.out" | cut -d' ' -f1)   # shasum -a 256 on macOS
cat <<YAML | dogen record step "$UNIT" verify --evidence-file - --json
verdict: pass            # pass | fail | skipped | deviated
mode: agent              # agent | ta  (who ran it)
command: "cd $WS && foo --version"          # workspace-anchored (D-08)
output_sha256: "$SHA"                        # SHA-256 of the FULL captured bytes
output_excerpt: "foo 0.3.1"                  # bounded window; capped to 4096 bytes
exit_code: 0                                 # required for pass/fail/deviated; null only for skipped
deterministic: true
YAML
```

**TA-runs (D-11):** print the exact copy-pasteable command with capture built in,
let the TA run it, then ingest the tee'd file **unmodified**:

```bash
foo login 2>&1 | tee .dogen/staging/$UNIT/scratch/evidence/login.out; echo exit:$?
```

If the TA pastes chat output instead, write the paste to the evidence file verbatim
— never re-type, never paraphrase a narration into evidence.

**Improvisation → `deviated`:** when the planned step did not say *how*, record
`deviated` with exit 0 and a `reason` — it still resolves AND the reason rides the
`step-recorded` commit body (see `episode-taxonomy.md`).

## Just-in-time consent + destructive backstop (D-06)

A step's destructive/stateful marker is proposed at plan review and vetoed/corrected
by the TA there. Permission for a marked step is asked **just-in-time**, right
before that step executes — informed by what prior steps actually did. An **unmarked**
command that smells destructive (`rm -rf`, `git reset --hard`, `docker … prune`, a
write outside the workspace) **re-prompts via the runtime backstop instead of
running**. Consent is confined to genuinely dangerous steps — never a confirm-parade
(the calibration axiom). The marker is conversational (no persisted schema field,
REC-06 seam gap); the backstop is the safety net, so safety never depends on
persistence. A step the TA will not consent to can be switched to TA-runs.

## Workspace lifecycle (D-05/D-07/D-08)

The walk workspace is `.dogen/staging/<id>/scratch/`, with an `evidence/` subdir
for the tee'd captures. Agent-runs commands are `cd`-pinned into it (D-05) and
recorded in workspace-anchored form so the transcript proves where each ran (D-08).
Only a stateful-marked step touches real state, via the JIT-consent path.

Because the workspace lives **under staging**, the shipped accept-time
`remove_staging` bounded-removes the whole `.dogen/staging/<id>/` (workspace
included) when the unit seals on `review --verdict accept` — with the
`_resolve_bounded_child` symlinked-leaf refusal and the `--keep-staging` escape
hatch. Zero new core code (D-07). Until seal the workspace persists across sessions,
so resume finds evidence and produced state intact. The `evidence/` subdir is never
a cleanup target — move-never-delete; a cleanup step must not reach `evidence/`,
`docs/`, or `.git`.

Honest framing: the cwd-pin is a **skill-level tripwire**, not a core-verified
sandbox — never claimed as a guarantee.

## Resume detection (REC-08 / D-13)

```bash
dogen record show "$UNIT" --json   # {steps:[{id,text,status,verdict}], all_steps_verified}
```

`status ∈ {resolved, unverified}`, derived on read. When a plan exists with some
`unverified` steps, offer resume as the **default**: show the derived step-status
table, trust every `resolved` step's evidence, and continue at the first
`unverified` step. The Phase-12 hash-bind means an edited step auto-reverts to
`unverified`, so "only unverified steps re-verify" is purely derived — no new verb,
no flag, no stored resume state.
