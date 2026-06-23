Tutorial — drafting with dogen
=============================

This short tutorial shows how to draft, steer, and review documentation using dogen's CLI. It is grounded in the repository README and the CLI implementation (src/dogen/cli/main.py). dogen is an agentic, human-in-the-loop drafting tool that produces Sphinx-publishable MyST output and stops at a single local commit.

Quick prerequisites
-------------------
- Python target: 3.12 (see README).
- Project uses uv for env/deps/build; recommended commands (from README):

```bash
uv sync                 # create env & install
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
uv build
```

Core concepts (as implemented)
------------------------------
- Unit: a documentation unit stored in a per-unit directory and scaffolded as an editable unit.md.
- Steering: a human HITL (human-in-the-loop) steering act that records {author, at, intent, audience} into provenance (provenance.yaml.steering). Steering must provably precede drafts.
- Drafting: runs the orchestrator (provider/backends) to produce a draft, provenance, and progress records.
- Review: a reviewer edit appended to provenance and a transition of progress to "reviewed" (never "committed").

CLI quick reference
-------------------

- Create a new unit (scaffolds unit.md)

```bash
dogen unit new <unit_id> [--intent <Intent>] [--audience <text>] [--force]
```

Behavior notes:
- Scaffolds an editable unit.md in a per-unit directory.
- --force overwrites an existing unit.md; absence of --force prevents accidental clobber.

- Record steering (HITL event)

```bash
dogen steer <unit_id> [--force]
```

Behavior notes:
- Reads git identity (author) and records steering into provenance (provenance.yaml.steering).
- Refuses to overwrite existing steering unless --force/--re-steer is passed (to preserve the ordering that steering precedes drafts).
- Re-steering an already-drafted unit is allowed but warns that existing generations predate the new steering.

- Draft a unit

```bash
dogen draft <unit_id> [--provider copilot|mock] [--model <model>]
```

Behavior notes:
- configure_observability() is invoked before drafting.
- Default provider is "copilot"; default model for copilot is left to provider (docstring notes "gpt-5-mini" as the copilot default).
- Refuses to draft if no steering has been recorded (clear message, nonzero exit).
- Errors are mapped to clean exit codes; certain backend errors (ModelRejectedError, BackendUnavailableError) are handled and surfaced clearly.

- Review a unit

```bash
dogen review <unit_id> --note "summary of edit"
```

Behavior notes:
- Reads git identity as reviewer and appends a ReviewerEdit(at, reviewer, summary) to provenance.
- Advances progress to ProgressState.reviewed and appends a stamped history entry if not already reviewed.
- Never advances to "committed" — committing is intentionally left to humans.

Error handling and exit codes (summary)
--------------------------------------
The CLI is intentionally thin: it validates minimally, delegates to core/adapters, prints results, and maps domain errors to nonzero exits. Examples from the implementation:

- Unit creation: refuses to overwrite (UnitExistsError) -> exit 1; invalid id -> exit 2.
- Steering: git-identity failure -> exit 1; missing unit -> exit 2; refusing re-steer -> exit 1.
- Draft: missing steering -> exit 1; read errors -> exit 2; provider/model/backend errors -> exit 1 (handled by name).
- Review: git-identity failure -> exit 1; not drafted / read errors -> exit 2.

Implementation notes (what the CLI does, not how to extend)
-----------------------------------------------------------
- The CLI is a thin Typer-based composition root; it delegates to FilesystemPlanningStore, provider selection, and core orchestrator.
- Provenance is read/initialized via a helper that returns Provenance(unit_id=...) when absent.
- Provider selection is pluggable: main.py uses select_provider(provider, model=model) and supports a "mock" provider for tests/CI.

Example end-to-end flow
-----------------------

```bash
# scaffold
dogen unit new my-unit --intent guides --audience "developers"

# record steering
dogen steer my-unit

# draft (uses copilot by default)
dogen draft my-unit

# review
dogen review my-unit --note "Minor wording and example fixes"
```

End
---
This page strictly reflects the README and the CLI implementation in src/dogen/cli/main.py. For design principles, coding rules, and licensing see AGENTS.md, .planning/refs, and LICENSE files referenced in the README.