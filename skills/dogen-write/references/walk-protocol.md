Load this file at the start of the actionable (tutorial/how-to) walk branch.

# Walk protocol — evidence, capture, consent, workspace, resume

The operational core of the walk. The SKILL.md holds the step sequence; this file
holds the mechanics: the evidence contract the step gate enforces, the capture
recipe, the just-in-time consent gate and destructive backstop, the workspace
lifecycle, and resume.

## The step gate (`dogen step`)

Every step's evidence is recorded through `dogen step`, which enforces the micro-gate
and commits the step. Branch on the `error` field of the refusal's JSON line, never
on the exit code alone — several reasons share one:

| exit | reason | skill branch |
|---|---|---|
| 0 | recorded; the step resolves (a `fail` is recorded and stays unresolved) | continue the walk |
| 2 | `step_unknown` — the step id is not in the plan named by `--steps-seq` | read the plan back and use an id it contains |
| 2 | `not_actionable` — the unit's signed intent is neither tutorial nor how-to, so a step walk does not belong to it | STOP walking; a reference or explanation page is drafted straight from its declared sources |
| 3 | `already_recorded` — this evidence is already on the record, field for field | report the existing seq and commit; move to the next step |
| 4 | `evidence_incomplete` — a required field is missing, or a `pass` / `fail` / `deviated` step arrived without `--output-file` | re-capture with well-shaped proof; never fabricate a field |
| 4 | `evidence_mismatch` — the evidence's `mode` is not the `mode` the plan declares for this step | record it in the declared mode, or re-plan the step; re-running the command unchanged cannot clear it |
| 4 | `evidence_stale` — the plan was re-planned after this capture | re-run the command against the current `--steps-seq` |
| 5 | `busy` / `git_busy` — another run holds the lock | nothing was written; wait and re-run unchanged |

A recorded `fail` never resolves a step. `pass` with a captured output, `skipped`
with a reason, and `deviated` with exit 0 and a reason do. **`resolved` is not
`executed`** — a skipped step resolves without ever running, so a tally that
collapses the two is a claim the record does not support.

It is the tool's draft gate, not the step record, that refuses over an unresolved
step: `dogen draft` exits 4 with `steps_unresolved` (or `steps_missing` when there is
no plan at all).

## The step plan (`dogen plan-steps`)

The plan is a JSON array piped on stdin — there is no plan file to edit and no
section to write:

```bash
dogen plan-steps "$UNIT_ID" --steps-file -
```

One object per step, four keys, nothing else:

| key | value |
|---|---|
| `id` | `^[a-z0-9][a-z0-9._-]{0,31}$`, unique within the plan |
| `text` | what the step does, in the author's terms |
| `mode` | `agent` or `ta` — see below |
| `stateful` | `true` when the step mutates real state, `false` otherwise |

**The two step modes, written out in full.** `mode` takes exactly two wire values,
and the tool validates them:

- **`agent`** — this skill runs the step itself, cwd-pinned inside the workspace,
  and captures the output. The default.
- **`ta`** — the author runs the step in their own environment and hands back the
  output file. Use it when the step needs a credential, a device, or a judgment the
  skill does not hold.

**The skill supplies no hash.** The tool computes each step's text hash from the text
it was given; that computed hash is what makes stale evidence detectable on a later
plan. A hash typed into the plan would be a claim the record cannot corroborate, and
the tool would have no reason to believe it.

**Re-planning and reuse.** A new plan with no reuse leaves every step unresolved.
`--keep-evidence` carries a resolved prefix forward, and the contract requires a note
whenever it does:

```bash
dogen plan-steps "$UNIT_ID" --steps-file - --keep-evidence --note "<why the plan changed>"
```

Reuse travels only along consecutive reusing plans, and only for the prefix whose
steps are identical in text, mode and statefulness at every hop. Ask the author first:
it asserts that something which has not been re-run still holds.

## Capture mechanics (D-15)

One redirection, one status, no digest.

**`agent` mode (the default):** run the command cwd-pinned in the workspace, with both
streams redirected into one file, then echo the command's own exit status:

```bash
WS=".dogen/staging/$UNIT_ID/scratch"
mkdir -p "$WS/evidence"
OUT="$WS/evidence/verify.out"
( cd "$WS" && foo --version ) > "$OUT" 2>&1; echo "exit:$?"
```

There is no pipe, so `$?` is the command's own status and nothing else's. Write the
evidence file beside the output, carrying exactly the contract's key set:

```json
{
  "verdict": "pass",
  "exit_code": 0,
  "mode": "agent",
  "command": "cd .dogen/staging/<id>/scratch && foo --version"
}
```

`reason` joins that set — and is required — for a `skipped` or `deviated` step, for a
`pass` with a non-zero exit, and for a `fail` with exit 0. No other key belongs in the
file. Then hand both files to the tool:

```bash
dogen step "$UNIT_ID" verify \
  --steps-seq "$STEPS_SEQ" \
  --evidence-file "$WS/evidence/verify.json" \
  --output-file "$OUT"
```

**The skill computes no digest of any kind.** The tool copies the output bytes,
hashes its own copy, and refuses a digest that arrives in the evidence file. There is
therefore nothing to gain by typing one: the recipe above has no hashing step because
a hashing step would be refused.

What the tool commits from the output is an excerpt: it strips the C0 control
characters and keeps within the contract's 4096-byte cap. That is the whole of the
transformation. Whatever the command prints is what lands in the record, so a step
that prints a credential commits a credential — tell the author that before the step
runs, and switch a step to `ta` mode or reshape the command if it would.

**`ta` mode:** print the exact copy-pasteable command with the redirection built in,
let the author run it, then ingest the resulting file **unmodified**:

```bash
foo login > .dogen/staging/$UNIT_ID/scratch/evidence/login.out 2>&1; echo "exit:$?"
```

If the author pastes chat output instead, write the paste to the output file verbatim
— never re-type it, never paraphrase a narration into evidence.

**Improvisation → `deviated`:** when the planned step did not say *how*, record
`deviated` with exit 0 and a `reason` — it still resolves AND the reason rides the
record (see `episode-taxonomy.md`).

**Repeating a step is safe.** An identical call — same plan seq, same step, same
verdict, exit code, output and reason — is recognised as `already_recorded` (exit 3)
and appends nothing. An interrupted walk resumes from the last step whose response
you actually read.

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

"TA-runs" is `mode: ta` on the wire; the marker itself is the plan's `stateful` flag.

## Workspace lifecycle

The walk workspace is `.dogen/staging/<id>/scratch/`, with an `evidence/` subdir for
the captured output and the evidence files. `agent` steps are `cd`-pinned into it and
recorded in workspace-anchored form so the transcript proves where each ran. Only a
stateful-marked step touches real state, via the JIT-consent path.

The workspace lives under `staging/`, which is gitignored (the seeded
`.dogen/.gitignore`), so it never leaks into commits. It persists across sessions,
so resume finds evidence and produced state intact. The `evidence/` subdir is never
a cleanup target — move-never-delete; a cleanup step must not reach `evidence/`,
`docs/`, or `.git`.

Honest framing: the cwd-pin is a **skill-level tripwire**, not a verified sandbox —
never claimed as a guarantee.

## Resume

Ask the tool; read no file:

```bash
dogen show "$UNIT_ID" --json
```

The step tally names every unresolved step by id, in the form `passed 4 · skipped 1
(<reason>) · deviated 0 · unresolved 1: <id>`. Quote it as printed. Below the tally,
`show` lists the recorded plan itself — one row per step with its id, mode, stateful
marker, status and text; `--json` carries the same rows as `steps.plan`. That listing
**is** the plan in a session that did not propose it: never re-propose or re-record it,
and never read the ledger for it. When a plan exists with unresolved steps, offer resume
as the **default**: show that tally, trust every resolved step, and continue at the first
unresolved one — a step marked stateful still takes its just-in-time permission gate.

A step whose text changed on a later plan carries no evidence forward, because the
tool's own computed hash no longer matches the one the evidence answered — so "only
unresolved steps re-run" is derived from the record, with no resume state stored
anywhere.
