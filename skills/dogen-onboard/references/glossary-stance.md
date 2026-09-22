Load this file immediately before authoring `glossary.md`.

# Glossary stance — authoring `glossary.md`

Extract the domain-specific terms, product names and key concepts **as the
documentation prose uses them**. `dogen-plan` reads this to keep a new unit's
vocabulary consistent with the rest of the docs, and `dogen-write` reads it while
drafting.

## What to include

- Product names, domain concepts, abbreviations, jargon, named components.
- Terms pulled from the prose — not from variable names or code identifiers.

## What to exclude

- Generic programming terms (API, function, class) unless the project gives them a
  specific, local meaning.

## For each term, capture

- **Definition** — one sentence, based on how the docs actually use the term.
- **Aliases** — any variant spellings or alternate names for the same concept.
- **Inconsistency flag** — if the term is used inconsistently across pages, say so
  and name where.

## Shape

Write a table, one row per term:

```
| Term | Definition | Aliases | Notes |
|------|------------|---------|-------|
| Escrow mirror | The read-only copy the system keeps for dispute resolution. | mirror | — |
| Unit | One documentation deliverable declared to dogen. | doc unit | inconsistent — called "item" in the CLI guide |
```

Order terms alphabetically. Keep definitions grounded — a term earns a row only if
you read a page that uses it. When the sources were sampled rather than read in
full, say so in a closing note rather than presenting the table as exhaustive.
