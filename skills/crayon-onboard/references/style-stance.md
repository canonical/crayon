Load this file immediately before authoring `doc-style.md`.

# Style stance — authoring `doc-style.md`

`doc-style.md` characterizes **how this project communicates about itself** in its
documentation — not what the code does. `crayon-plan` reads it to match the house voice
when it declares a new unit, and `crayon-write` reads it when it drafts. Analyze the
style; never summarize the content.

Ground every trait in prose you read. Where a trait is worth showing, quote a short
phrase from a page (under ten words) as evidence. Prefer a concrete example over an
adjective.

Write the file with these five sections.

## 1. Voice & tone

- Formal, conversational, terse, or verbose?
- Which person — "you", "we", "the user", or passive voice?
- Imperative ("Run this command") or declarative ("The system handles…")?

## 2. Audience assumptions

- What prior knowledge does the prose assume (CLI fluency, domain concepts, a
  specific role)?
- Does it explain jargon or lean on it?
- Is there a clear target reader — developer, operator, end user?

## 3. Formatting conventions

- How are sections structured — flat, hierarchical, mixed?
- What patterns repeat (always a code example, always a Note admonition)?
- Header-depth habits; use of admonitions, tables, lists versus prose.

## 4. Completeness patterns

- Do examples always accompany explanations?
- Are parameters and options consistently listed?
- Are edge cases and error states documented?

## 5. Consistency & drift

This folds in the cross-file consistency read. Report:

- **Terminology drift** — the same concept named differently across files
  ("called X in the README, called Y in the guides"). List specific pairs.
- **Style drift** — pages that follow the house voice versus pages that don't; signs
  of multiple authors with conflicting styles.
- **Conflicting descriptions** — two pages that contradict each other on how
  something works, or stale prose describing removed or changed behaviour.
- The strongest and the weakest part of the docs, each named with a file path.
