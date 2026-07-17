Load this file at workflow step 5 (Draft handoff (mirror dogen-write's passenger flow)).

# Authoring stance — tutorial and how-to (action-based drafting)

The stance every dogen-record-authored page answers to. dogen-write drafts the
**reference** direction; dogen-record drafts the two **action-based** Diátaxis
types that cannot be extracted from artefacts alone — a **tutorial** and a
**how-to** — from what the walk actually ran. This file governs which of the two
you are writing and how captured evidence becomes reader-facing prose. It
complements, and does not replace, the general grounding discipline: assert only
what the walk's evidence and the sources support.

## Tutorial vs how-to (Diátaxis)

Pick the direction from the unit's declared intent and audience, and hold it for
the whole page — the two shapes optimise for different readers and must not blur.

- **Tutorial — learning-oriented.** A guided lesson for a newcomer who is learning
  by doing. The author is the teacher and owns the route: concrete, from a known
  starting state to a single visible success, every step guaranteed to work if
  followed exactly. Show what happens after each step so the learner knows they are
  on track. No branching, no options menu, no "it depends" — defer alternatives and
  the *why* to explanation/reference and link out. Success is the learner reaching
  the end and feeling it worked.
- **How-to — task-oriented.** A recipe for a competent user with a specific goal in
  hand. It assumes background knowledge, states its starting preconditions, and is
  a sequence of steps toward a real-world result. It may acknowledge decision
  points and sensible alternatives at a genuine fork, but stays focused on the goal
  — it does not teach concepts from scratch and it does not try to be complete.
  Success is the reader getting their task done.

The shared spine: both are **action sequences grounded in steps that provably
ran** — that is why dogen-record produces them through the evidence-gated walk
rather than by summarising artefacts. Neither type narrates the machinery's
internals; both describe what the reader does and sees.

## The curated-excerpt rule (D-04)

Captured step output enters the drafted page **only as curated excerpts** —
deliberately selected and scrubbed of environment-specific noise during authoring,
never auto-pasted wholesale. The split is deliberate:

- **Provenance keeps the verbatim truth.** The full bytes, the SHA-256, the exit
  code, the workspace-anchored command line, and the raw tee'd file all live in the
  evidence record and the scratch workspace — the audit surface, untouched.
- **The page gets the reader-facing version.** Show the command the reader would
  actually type and a representative, trimmed slice of its output — enough to
  confirm success or orient the reader, not the raw transcript.

**Scrub before a capture becomes page text.** Remove or generalise: absolute and
scratch-workspace paths (`.dogen/staging/<id>/scratch/…`), timestamps, hostnames
and usernames, SHA-256 digests, the `exit:<N>` capture lines, and any local
environment specifics that would not reproduce for a reader. Replace a real home
path with a placeholder, a real host with an example name, a long hash with an
elision.

**Never leak the evidence apparatus into the page.** No `sha256`, no `output_sha256`
or `verified:`/`evidence:` key, no exit-code line, no scratch path, no
`Dogen-Step`/`Dogen-Verdict` trailer text belongs in the published MyST/rST. A
page's code block must never be byte-identical to a raw capture — if it is, it was
pasted, not curated. Evidence is internal observability; the page is the reader's.

## Markup

Author in the unit's `format` (from `dogen unit show --json`): MyST for `.md`
targets (`colon_fence` directives, `{ref}` cross-references), reStructuredText for
`.rst` targets (3-space directive indentation, one heading ladder). Never write one
markup into the other's extension. A single top-level title, a clean heading
ladder, no skipped levels — matching the page's siblings.
</content>
</invoke>
