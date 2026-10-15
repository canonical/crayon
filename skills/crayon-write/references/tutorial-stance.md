Load this file at workflow step 3 (Author the page).

# Tutorial stance (authoring)

## Tutorial — learning-oriented

A guided lesson for a newcomer who is learning by doing. The author is the teacher
and owns the route: concrete, from a known starting state to a single visible
success, every step guaranteed to work if followed exactly. Show what happens after
each step so the learner knows they are on track. No branching, no options menu, no
"it depends" — defer alternatives and the *why* to explanation/reference and link
out. Success is the learner reaching the end and feeling it worked.

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
scratch-workspace paths (`.crayon/staging/<id>/scratch/…`), timestamps, hostnames
and usernames, SHA-256 digests, the `exit:<N>` capture lines, and any local
environment specifics that would not reproduce for a reader. Replace a real home
path with a placeholder, a real host with an example name, a long hash with an
elision.

**Never leak the evidence apparatus into the page.** No `sha256`, no `output_sha256`
or `verified:`/`evidence:` key, no exit-code line, no scratch path, no
`Crayon-Step`/`Crayon-Verdict` trailer text belongs in the published MyST/rST. A
page's code block must never be byte-identical to a raw capture — if it is, it was
pasted, not curated. Evidence is internal observability; the page is the reader's.

## Markup

Author in the markup the signed target's extension implies: MyST for `.md`
targets (`colon_fence` directives, `{ref}` cross-references), reStructuredText
for `.rst` targets (3-space directive indentation, one heading ladder). The
markup is read off the extension and is not a field — `unit.md`'s frontmatter is
the fixed six `title` / `intent` / `audience` / `targets` / `sources` / `notes`,
and any other key is refused `unit_invalid`.

Never write one markup into the other's extension. A single top-level title, a
clean heading ladder, no skipped levels — matching the page's siblings.
