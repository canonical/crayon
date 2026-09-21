# Formatting hooks on target pages

If a `pre-commit` hook reformats the pages dogen writes, the supported behaviour is
**adoption**, and the routes say so:

- **The hook rewrites the page and the commit succeeds.** The transition stands — it is
  committed. The verb exits 0 with the warning `hook changed <path> after recording`, re-derives
  state, and routes you to `dogen edits`. Recording the hook's bytes as your edits makes them
  the basis. That is the steady state: adopt once, and the hook's output is what the record
  stands behind.
- **The hook rewrites the page and rejects the commit.** The transition is incomplete and the
  tool says so (`uncommitted_tail`), routing you at `dogen resume`. Where the rewritten bytes
  are not the ones dogen intended, `resume` stops and offers the two choices explicitly —
  `--overwrite` to re-place the intended bytes, or `--adopt --note` to keep the hook's. A second
  failed commit on the same batch is refused rather than retried: a hint that reproduces its own
  refusal is not an escape.

What is **not** supported is a hook that *deletes* the placed file. There are no current bytes
to adopt, so `--adopt` refuses. A formatter is not a reviewer; adoption always records a note
saying a hook changed the bytes and the author retained them.

The normative statement of both routes is [`docs/contract.md`](contract.md#58-write-protocol-and-resume)
§5.8; the skills follow the routing rows for `uncommitted_tail`, `resume_ambiguous` and
`recovery_unsupported` in [`skills/README.md`](../skills/README.md#routing).
