# Formatting hooks on target pages

<!-- provenance: moved from README.md (Formatting hooks on target pages); the routes are contract 5.8 -->

A `pre-commit` hook in your docs repository may reformat the pages dogen writes. dogen does
not fight the hook. With your approval, it keeps the hook's version.

- **The hook changes the page and the commit succeeds.** The step is done. The next time you
  run a skill, it shows you that the page changed and asks whether to record the change as
  your edit. Say yes once. From then on, the record stands behind the hook's version.
- **The hook changes the page and rejects the commit.** The step is not finished. Run the same
  skill again. It shows you what is on disk and what dogen meant to write, and asks you to
  choose: keep the hook's version, or restore dogen's version. If the hook rejects the commit a
  second time, remove what is blocking the commit first.

A hook that *deletes* the page is not supported. There is nothing left to keep, so the only
choice is to restore dogen's version.

When you keep the hook's version, the record says that a hook changed the page and that you
kept it. A formatter is not a reviewer, and the record does not pretend it is one.

## Under the hood

- **Hook rewrites, commit succeeds.** The transition is committed. The verb exits 0 with the
  warning `hook changed <path> after recording`, re-derives state, and routes to
  `dogen edits`. Recording the hook's bytes as the author's edits makes them the basis: adopt
  once, and the hook's output is what the record stands behind.
- **Hook rewrites, commit rejected.** The transition is incomplete and the tool says so
  (`uncommitted_tail`), routing to `dogen resume`. Where the rewritten bytes are not the ones
  dogen intended, `resume` stops (`resume_ambiguous`) and offers the two choices explicitly:
  `--overwrite` to re-place the intended bytes, or `--adopt --note` to keep the hook's. A second
  failed commit on the same batch is refused rather than retried: a hint that reproduces its
  own refusal is not an escape.
- **Hook deletes the file.** There are no current bytes to adopt, so `--adopt` refuses.
  Adoption always records a note saying a hook changed the bytes and the author retained them.

The normative statement of both routes is [[contract]] §5.8. The skills follow the routing rows
for `uncommitted_tail`, `resume_ambiguous` and `recovery_unsupported` in `skills/README.md`.

Related: [[contract]], [[conventions]], [[internals]].
