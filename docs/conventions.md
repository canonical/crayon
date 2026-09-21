# Conventions

<!-- provenance: moved from AGENTS.md (Conventions) when AGENTS.md became the router -->

The working rules for anyone changing dogen, its skills or its documents. Each is stated once
here; `AGENTS.md` carries the one-line form and points back.

## Markup and structure of drafted pages

- New drafted pages default to MyST Markdown (`colon_fence`); use rST when a page's siblings are
  already rST. The target extension *is* the format: `.md` → MyST, `.rst` → rST.
- One Diátaxis direction per page (tutorial / how-to / reference / explanation). The direction is
  the declared `intent` field and routes the draft-stage skill.

## The ledger

Append-only and hash-chained. **No line is ever edited — including a step's status** — because
editing one line invalidates every `prev` after it. A step's resolution is a new appended event,
never an edit to the event that planned it. Never hand-edit the file; the rules are in
[[contract]] §5.2 and §5.6.

## The commit seam

The tool owns its commits. Never run a competing `git add -A` or `git commit` in a skill for a
gated transition. Every transition commits explicit pathspecs under `.dogen/` and `docs/` with
`Dogen-*` trailers ([[architecture]]).

## Single definition site

A fixture, a routing row or a threshold has one home and is mirrored mechanically, never copied
by hand. A second copy is the drift the rule exists to prevent. The mirrors that exist, and what
pins each, are listed in [[development]].

## Documents

- `docs/` is the wiki: flat, one page per slug, addressed by slug in double square brackets from `AGENTS.md` and
  from other pages. Every page starts with an H1, carries a provenance comment on line 3, ends
  with a `Related:` line, and is reachable from `AGENTS.md`. `scripts/wiki_lint.py` enforces it.
- Outside the wiki — `README.md`, the skills, tests, scripts — pages are cited by path
  (`docs/<slug>.md`), never with the bracket notation.
- The README is the reader's entry point and is written for a Technical Author, not for an
  agent; it never names a harness.
- A gate command, a tree entry or a shellcheck scope changes in every pinned place at once
  ([[development]]).

## Shell and Python

- Shell files are clean at `shellcheck -S warning` against the pinned version ([[shellcheck]]).
- Python is 3.9 syntax throughout; the unit suite scans for newer-syntax hazards.
- Every checker answers `0` clean, `1` violation, `2` nothing checked.

Related: [[architecture]], [[development]], [[contract]].
