---
schema_version: 0
unit_id: dogen-tutorial
intent: tutorial
audience: technical authors new to dogen
title: Draft your first doc with dogen
sources:
- path: README.md
- path: src/dogen/cli/main.py
sphinx_target: dogen-tutorial.md
steering_notes: >-
  Learning-oriented Diataxis tutorial. Walk a first-time technical author through
  one full pass of the dogen loop on a tiny example unit, so they end with a
  drafted, reviewed page and a complete provenance trail. Keep it runnable
  start-to-finish: every command must be copy-pasteable and match the real CLI in
  src/dogen/cli/main.py (unit new -> steer -> draft -> review). Show, don't just
  tell: include the actual commands and what each one writes
  (.dogen/units/<id>/unit.md, provenance.yaml, progress.yaml, docs/<target>).
  Reinforce the human-in-the-loop gate (steering must come before drafting) and
  the scope border (dogen stops at the draft; the human owns review and the
  commit). Use --provider mock so the tutorial is reproducible without a live
  model or network. Terse, technical voice; MyST Markdown with colon-fence
  directives where useful. No marketing prose, no slop.
status: pending
---
## Intent & scope

A first run-through of dogen for someone who has just installed it. By the end the
reader has scaffolded a unit, recorded steering, produced a draft, recorded a
review, and can see the provenance trail dogen wrote. It teaches the loop and the
two hard rules (steer-before-draft; stop at the commit border), not the full CLI
surface.

## Outline / acceptance

Outline:

1. What you'll build — one tiny documentation unit, end to end.
2. Prerequisites — dogen installed; run commands with `uv run dogen ...`.
3. Step 1: scaffold a unit (`dogen unit new`) — what `unit.md` is for.
4. Step 2: steer it — edit intent/audience/sources in `unit.md`, then
   `dogen steer` (why steering is mandatory before drafting).
5. Step 3: draft it (`dogen draft --provider mock`) — what lands in `docs/` and
   what gets recorded in `provenance.yaml` / `progress.yaml`.
6. Step 4: review it (`dogen review --note ...`) — recording the human edit and
   advancing to `reviewed`.
7. Where it stops — dogen never commits; the human owns the commit.
8. Next steps — swap `--provider mock` for a real provider; point `sources` at
   real files.

Acceptance criteria a reviewer checks:

- Every command matches the real CLI (subcommands, flags) in `src/dogen/cli/main.py`.
- The flow runs start-to-finish as written, using `--provider mock`.
- The HITL gate (steer before draft) and the scope border (stop at commit) are
  both stated explicitly.
- Paths named (`.dogen/units/<id>/...`, `docs/<target>`) are accurate.
- MyST Markdown; clean enough to pass the `-W` Sphinx build.
