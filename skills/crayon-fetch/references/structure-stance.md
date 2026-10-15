Load this file immediately before authoring `structure.md`.

# Structure stance — authoring `structure.md`

Evaluate how the **user documentation** is organized, whether that organization is
logical, and where important product capabilities are missing or hard to find. Focus
on user-facing docs, not docstring quality. Be specific with file paths.

This one artefact carries both the information-architecture read and the
code-versus-docs coverage read. Write it with these five sections.

## 1. Documentation topology

- The main landing pages and entry points.
- The topical subdivisions under each major section.
- Whether navigation is intuitive for a new reader.

## 2. Diátaxis coverage and balance

- How complete each category is — tutorial, how-to, reference, explanation.
- Which categories are thin, overloaded, or mixed in purpose.
- Which pages look misplaced for their Diátaxis category.

## 3. Coverage gaps (code versus docs)

Each bullet compares a **named** product capability against the docs and starts with
the literal tag `[CODE↔DOCS GAP]`, citing the capability by category and name:

```
[CODE↔DOCS GAP] CLI flag --dry-run (scrape.py) is not mentioned in any how-to or reference page.
[CODE↔DOCS GAP] Public API symbol collector.DocCollector is exported but has no reference page.
```

Distinguish three kinds of gap:

- **missing entirely** — no page covers the capability;
- **raw reference only** — present as reference with no task workflow;
- **undiscoverable** — mentioned but hard to reach from the landings and navigation.

Only use the tag when the finding is a direct comparison between a named item on the
product surface and the prose docs. A purely qualitative weakness ("the CLI section
feels thin") with no named capability behind it belongs in section 4, untagged.

If the harness surfaced forge discussion (pull requests, issues) and the author opted
it in, tag a capability discussed there but absent from the docs `[SDLC]` and cite
the issue or PR number instead of a code symbol.

## 4. Structural gaps and risks

Pure documentation-structure analysis — no code comparison here:

- Orphaned or hard-to-find pages.
- Missing cross-links between related pages.
- Concepts referenced in tasks or reference but never explained.

## 5. Prioritized improvements

The top five highest-impact changes to information architecture and coverage. For
each, say what to add, move or link and why. If a recommendation addresses a
section-3 finding, prefix it with the same `[CODE↔DOCS GAP]` or `[SDLC]` tag so the
reader can trace it back; otherwise leave it untagged.

When the sources were sampled, partial or failed, close with a short limitations
note naming what was not inspected, so a reader never mistakes a sample for the
whole.
