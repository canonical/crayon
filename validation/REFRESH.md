# Smoke-repo refresh runbook (VAL-04)

This is a **prescription-here** runbook: the canonical validation kit lives in
`dogen-mvp-1/validation/` and Phase 11 makes **zero commits** into the sibling
repos (`../DOCPR-2845/smoke-docs-1`, `../DOCPR-2845`) — D-01/D-03. The steps
below describe exactly what a **human** applies in those sibling repos to make
the smoke baseline round-4-ready. Nothing in this file crosses a repo boundary
on its own; a person runs each step and commits in the sibling repos.

## Assumed layout

`dogen-mvp-1` and `DOCPR-2845` are siblings under `~/Documents/`:

```
~/Documents/
  dogen-mvp-1/               <- canonical kit (this repo, source of truth)
    validation/
  DOCPR-2845/                <- its own git repo
    .claude/skills/validation-run-prep/
    smoke-docs-1/            <- a nested git repo of its own
      validation/            <- the kit MIRROR (sync.sh target)
      VALIDATION.md
      .dogen/context/
```

`smoke-docs-1` is its own git repo nested inside `DOCPR-2845`, which is also a
repo. Both are separate from `dogen-mvp-1`. If the checkout is not laid out this
way, `sync.sh` errors loudly (`mirror not found: …`) rather than copying to the
wrong place (Pitfall 6).

## PyYAML caveat

`score.py audit` imports PyYAML (`yaml.safe_load`) to read `provenance.yaml`.
PyYAML is **not** a declared dogen dependency — it rides in transitively via the
dogen venv (6.0.1 today). `draft` and `protocol` do **not** need PyYAML; only
`audit` does. When running the kit in the smoke repo, make sure the dogen venv
(with PyYAML on PATH) is active before running `audit`; `draft`/`protocol` run
without it (Pitfall 5). If a future dependency bump drops the transitive PyYAML,
`audit` will fail at import until PyYAML is reinstalled.

## Steps (a human applies these in the sibling repos)

### 1. Correct the seeded `doc-gaps.md` path prefix

File: `../DOCPR-2845/smoke-docs-1/.dogen/context/doc-gaps.md`

The seeded context uses a stale `workshop-docs/` prefix for its suggested-location
paths; the repo's actual docs live under `docs/`. Replace every `workshop-docs/`
prefix with `docs/`. Confirm the live count first (it was 11 at the time this
runbook was written — grep, do not trust the number):

```sh
grep -c 'workshop-docs/' ../DOCPR-2845/smoke-docs-1/.dogen/context/doc-gaps.md
```

After the prefix correction, re-verify that any stale line-number links in
`doc-gaps.md` still resolve against the current sources (line numbers drift as
sources change). This file can also be regenerated from scratch via the dogen
context tooling instead of hand-editing — prefer regeneration if the drift is
large.

### 2. Add a "context freshness check" step to the run-prep skill

File: `../DOCPR-2845/.claude/skills/validation-run-prep/SKILL.md`

Before the skill emits the per-harness starting prompt, add a step that confirms
the seeded `.dogen/context/` is current against the baseline:

- the `doc-gaps.md` suggested-location prefixes point at the repo's real `docs/`
  layout (not the stale `workshop-docs/`), and
- its line-number links still resolve against the current sources.

If either is stale, refresh `.dogen/context/` (per step 1) before starting a leg.
This closes the round-3 gap where a leg ran against stale seeded context.

### 3. Add the RESULTS.md template to the run

The run's results file is governed by `../DOCPR-2845/smoke-docs-1/VALIDATION.md`.
Copy this repo's staged template into the run's `RESULTS.md`:

```sh
cp dogen-mvp-1/validation/RESULTS.template.md \
   ../DOCPR-2845/smoke-docs-1/validation/RESULTS.md   # adjust to the run's location
```

The template carries one `## <harness>` heading per leg (`## claude`,
`## copilot`, `## opencode`) — the exact shape `score.py protocol` requires
(D-06), so a filled-in RESULTS.md passes the protocol conformance gate. Add or
remove leg headings to match the legs actually run (one per `SESSION-*.md`).

### 4. Sync the kit into the smoke-docs-1 mirror

From `dogen-mvp-1/validation/`, run the sync:

```sh
cd dogen-mvp-1/validation
sh sync.sh
```

This overwrites `../DOCPR-2845/smoke-docs-1/validation/{score.py,rubric.md,export.sh}`
with the current canonical copies (one-directional, idempotent — D-02). It copies
**only** those three kit files; it does not sync captures, fixtures, this runbook,
or the RESULTS template. Re-run it any time the canonical kit changes.

## Zero sibling commits by this phase

To be explicit: **Phase 11 makes zero commits into `smoke-docs-1` or
`DOCPR-2845`.** Every step above is applied and committed by a human in the
sibling repos. The canonical kit and this runbook are the only artifacts the
phase produces, and they live entirely in `dogen-mvp-1` (D-01/D-03).
