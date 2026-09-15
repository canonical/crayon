Load this file at workflow step 3 (Author the page).

# Reference stance (authoring)

The register an authored **reference** page answers to. Load it when the unit's
declared direction is reference; the explanation path never loads it. It sits
above `references/writing-standards.md` the same way the explanation stance does —
writing-standards.md governs what the text is and how it treats its own history
for every direction; this file governs the reference register on top of it.

## The neutral, information-oriented register

Reference is **information-oriented**. It states what is, in a neutral register.
Write as the product's reference, never as a researcher describing evidence.
Banned register: "observed", "the corpus", "the fixtures show". Unverifiable
facts become report gaps, never hedged prose.

## Code in narrative

Reference code entities by qualified name; show a code block only when the reader
themselves authors or invokes it. Facts you cannot verify at their origin are left
out of the prose and recorded as gaps — never hedged into the page.

## Markup

Author in the unit's `format` (from the target extension in `unit.md`): MyST
for `.md` targets (`colon_fence` directives, `{ref}` cross-references),
reStructuredText for `.rst` targets (3-space directive indentation, one heading
ladder). Never write one markup into the other's extension. A single top-level
title, a clean heading ladder, no skipped levels — matching the page's siblings.
