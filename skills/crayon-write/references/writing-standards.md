Load this file at workflow step 3 (Author the page).

# Writing standards (authoring)

The editorial standard every authored sentence answers to. It sits above the
per-format markup standards (MyST vs rST, held in the SKILL.md step 3) and
complements the stance contract: stance governs the register, this file governs
what the text is and how it treats its own history.

## End-state writing — the governing principle

Write every page to its correct END-STATE: the text a reader should find today,
as if the behaviour had always worked the way it now works. When a change touches
existing text, rewrite the sentence that owns the changed behaviour and DELETE
what the change obsoletes. Never leave the page as sediment layers a reader must
mentally diff.

Four named failure modes (crayon-review hunts these by the same names — its
always-on writing-approach dimension):

- **Exception-note layering** — new behaviour bolted on as an aside ("can now
  also…", "in addition, X supports…") instead of rewritten into the sentence
  that owns it.
- **Changelog framing** — release-note register in reference prose
  ("previously…", "now…", "starting with version…", "new in this release"). The
  page states what is; history lives in release notes.
- **Pipeline-artifact narration** — commit-log, test, or algorithm mechanics
  restated as documentation. Commit logs optimize for the author; tests verify
  code; neither is documentation. (The stance contract's runtime-mechanics rule
  is the register-level twin of this.)
- **Water** — tautology and restating the obvious: "the `timeout` option
  configures the timeout", prose that re-narrates an adjacent table, filler that
  answers no reader question.

**The over-deletion guardrail:** end-state writing is not deletion for its own
sake. A rewrite that loses working content, a documented behaviour, or the
phrasing readers actually search for is a regression, rejected as hard as
accretion. After a rewrite, diff it against the prior text and account for
everything dropped — each dropped statement is either deliberately obsoleted (say
by what) or restored.

## The bidirectional staleness scan

Run the scan in the direction the change points (both, for a mixed change):

- **The change ADDS behaviour → inverse completeness audit.** Enumerate every
  new behaviour the source confirms, then walk the list against the page: each
  one lands in the text or is recorded as a `gap` with a reason. This catches
  the incomplete enumeration (a list of five modules where the source defines
  six).
- **The change ALTERS or REMOVES behaviour → obsoleted-statement scan.**
  Enumerate every existing statement the change invalidates — on this page and
  on any sibling page you read — and rewrite or delete each one in place. Never
  plan an addition beside text the change contradicts: the contradiction, not
  the missing addition, is what strands the reader.

## Three-check grounding for every behavioral claim

Before a claim about behaviour, defaults, bounds, constraints, or availability
enters prose, it passes three checks:

1. **Locate.** Pin the claim to a `file:line` in the source you read — before
   writing the prose, not after. Cite locations in the context report
   (`.crayon/staging/<id>/report.json`, which `draft --report` reads as JSON),
   never in the published page.
2. **Confirm.** Read the current source at that location — not the plan prose,
   not a prior draft's wording, not the page's own existing text. The source is
   the only truth; everything else is a pointer to it.
3. **Corroborate.** A symbol existing in source is not proof of a user-facing
   feature. Never promote "exists in code" to "is supported" without a second
   in-repo signal: a test that exercises it, a public schema entry, CLI help, a
   sibling page. One mention in one file is one source, not confirmation — when
   the second signal is missing, the claim goes into the report's gaps, not
   the prose.

**The inverse rule — never invent a constraint.** Before writing "must", "only",
or "cannot", find the code that enforces it (the validator, the refusal, the
bound check). If nothing enforces it, it is a preference or a convention — state
it as such, or leave it out. ("The path must be absolute" is wrong when the code
normalizes relative paths instead of refusing them.)

## Writer micro-rules

- **No self-reference.** Never "This page describes…", "This document covers…",
  "The intended reader is…" — start with the subject itself. The page is the
  description; it does not narrate that it is one.
- **Single-antecedent pronouns.** Every "it", "this", "these" has exactly one
  possible antecedent in the sentence before it — otherwise repeat the noun.
- **No unqualified absolutes.** "always", "never", "all" only when the source
  proves them (see the inverse rule above).
- **Say once, link elsewhere.** A fact lives in one place; other pages link to
  it. Restating invites drift.
- **Realistic minimal examples.** Example values look like real use — never
  placeholder stubs, and never identifiers dragged in from a different context
  (a stream example must not carry an HTTP-ism).
- **Mirror the siblings.** A new entry in an existing series copies the
  siblings' section shape, ordering, and phrasing skeleton.
- **Lead with the primary behaviour.** The common case comes first; exceptions
  and edge conditions follow it, never precede it.

## After-write mechanics

- **Re-read the tail after every `Write`.** Stray closing tags and fences have
  leaked into staged files at the end; a two-second tail check catches them
  before the reviewer does.
- **A grep for your own staged text that unexpectedly misses** usually means an
  invisible character — check for NBSP (U+00A0) with `cat -A` (it shows as
  `M-BM- `) and rewrite the line with a plain space.
- **Re-read a staged file before re-`Write`-ing it** on a later pass — never
  regenerate from memory what is already on disk.
