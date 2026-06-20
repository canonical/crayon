# dogen CLI reference

`dogen` is steered from a single console command. The CLI is deliberately thin:
each subcommand validates its inputs, delegates into the core and adapters,
prints the result, and maps domain errors to a clean nonzero exit. It holds no
business logic of its own.

The drafting lifecycle is four ordered verbs — **`unit new` → `steer` →
`draft` → `review`** — and one hard border: `dogen` never commits, pushes, or
publishes. It stops at a reviewed draft; the human owns the commit.

## `dogen unit new`

Scaffold an editable `unit.md` for a new documentation unit.

```
dogen unit new UNIT_ID [--intent INTENT] [--audience AUDIENCE] [--force]
```

| Argument / option | Meaning |
| --- | --- |
| `UNIT_ID` | Identifier and per-unit directory name for the new unit. |
| `--intent` | Pre-fill the Diátaxis direction (`tutorial`, `how-to`, `reference`, or `explanation`). |
| `--audience` | Pre-fill the target audience. |
| `--force` | Overwrite an existing `unit.md`. Without it, an existing unit is refused. |

The unit is scaffolded under `.dogen/units/<UNIT_ID>/unit.md`. Editing this file
by hand is the intended way to express intent before drafting.

## `dogen steer`

Record the human-in-the-loop steering event for a unit.

```
dogen steer UNIT_ID
```

Steering is a discrete, recorded act: it captures the author and timestamp (from
your git identity) together with the unit's steered `intent` and `audience` into
`provenance.yaml`. Because it is recorded, it **provably precedes** any draft —
this is what makes the human-in-the-loop accountability auditable rather than
assumed.

`steer` fails with a clear message if your git identity cannot be read, or if the
unit does not exist.

## `dogen draft`

Run the drafting loop for a unit.

```
dogen draft UNIT_ID [--provider copilot|mock]
```

| Option | Meaning |
| --- | --- |
| `--provider` | The drafting backend. Defaults to `copilot`; `mock` is the deterministic, no-network provider used in tests and CI. |

`draft` **refuses with a nonzero exit if no steering has been recorded** — you
cannot draft a unit that no human has steered. On success it writes the drafted
page (the `sphinx_target`, e.g. this `cli-reference.md`) plus updated provenance
and progress, and prints the path it wrote.

If the real Copilot backend is unavailable, `draft` reports that distinctly and
exits nonzero, so an environment problem is never mistaken for a drafting result.

## `dogen review`

Append a reviewer edit and advance the unit's progress to `reviewed`.

```
dogen review UNIT_ID --note "summary of the reviewer's edit"
```

| Option | Meaning |
| --- | --- |
| `--note` | A short summary of the reviewer's edit, recorded in provenance. |

`review` records who reviewed, when, and the note, then moves progress to
`reviewed`. It **never** advances to `committed` — committing is the human's
border, outside the framework.

## Where state lives

Each unit keeps its planning and audit surface under `.dogen/units/<UNIT_ID>/`:

- `unit.md` — the editable intent/outline scaffolded by `unit new`.
- `provenance.yaml` — the recorded steering, each generation's model metadata
  (model, version, effort, run id, context origins), and reviewer edits. This is
  the audit trail; it lives in git history as the human-in-the-loop evidence.
- `progress.yaml` — the unit's lifecycle state (`sourced` → `drafted` →
  `reviewed`) and its history.

The drafted documentation page itself lands under `docs/` as MyST Markdown,
ready for Sphinx to publish — this page is the first such dogfood draft.
