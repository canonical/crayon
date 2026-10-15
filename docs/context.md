# Context files

<!-- provenance: new page; the context-file prose moved here from docs/install.md (Add context files) and README.md (Glossary, context files) -->

Context files teach the skills your house style, your terms and where facts live. They live in
`.crayon/context/` in your docs repository. `/crayon-plan` reads them when it plans a page, and
`/crayon-write` reads them when it drafts one. No skill writes them directly: the skills hand
them to the `crayon` tool, which records them with a commit. This page is the one home for what
they are, who produces them and how they are recorded.

## The five names

crayon recognises exactly five context files. Any other name is refused.

| Name | What it carries | Produced by |
|---|---|---|
| `doc-style.md` | how the project writes: voice, audience, formatting, completeness habits, drift | `/crayon-onboard` from a walk of the repository's docs; `/crayon-fetch` from a declared source such as a house style guide |
| `glossary.md` | the project's terms as its prose uses them, with aliases and inconsistency flags | `/crayon-onboard`; `/crayon-fetch` from a terminology document held elsewhere |
| `structure.md` | the docs' information architecture, Diátaxis balance, structural risks, and the code-versus-docs coverage gaps tagged `[CODE↔DOCS GAP]` | `/crayon-onboard`; `/crayon-fetch` from an exported docs set |
| `code-to-docs-map.md` | which code areas each page documents | tooling outside crayon (below); recorded with `/crayon-fetch` |
| `doc-gaps.md` | prioritized units the docs are missing, derived from the map | tooling outside crayon; recorded with `/crayon-fetch` |

The first three are the context. While any of them is missing, `/crayon-plan` offers you the
choice described in [When they are missing](#when-they-are-missing). The last two are optional.

## Producing them

**`/crayon-onboard`** walks the repository you run it in. It reads the docs tree, the README and
other prose, sorts each page by its Diátaxis type, and compares the docs with the product
surface (CLI flags, public API, configuration, environment variables) to find coverage gaps.
Then it writes `doc-style.md`, `glossary.md` and `structure.md`. Each claim points to a page or
a symbol. Run it once to create the context. Run it again when the docs or the product have
changed enough that the files are out of date.

**`/crayon-fetch`** does the same from sources outside the repository: a local file or export,
another checkout, a page at a URL, or a document your agent already holds. You declare each
source before it is read. The skill records where each source came from, when it was read and
its revision. If a source cannot be reached, the skill reports it as failed and never replaces
it with another source. Use it when the material that should guide the docs is not in the
repository, or when `/crayon-onboard` finds such a source and hands it over to you.

**From a file you already have.** A style guide or a glossary you already trust needs no walk.
Run `/crayon-fetch` and give it the file path. It writes `doc-style.md` or `glossary.md` from
the file and records the path as the source.

**`code-to-docs-map.md` and `doc-gaps.md`** come from tooling outside crayon. The
[Code to docs mapper](https://code.launchpad.net/code-to-docs-mapper) produces a deterministic
map and the gaps derived from it. It reads the code and the docs from two collections in a
vector database built with [Wide scope RAG](https://code.launchpad.net/wide-scope-rag). crayon
neither depends on nor understands either tool. Record their output with `/crayon-fetch`, so it
carries a digest. Without a map, `/crayon-plan` reads the sources around the page for one
planning session instead (see below), which is less repeatable.

## When they are missing

`/crayon-plan` checks for the context first. If `doc-style.md`, `glossary.md` or `structure.md`
is missing, it asks you once and offers three answers:

- **I'll add them**: you supply the files yourself, for example with `/crayon-fetch` from a
  style guide you already have. The plan waits until they are there.
- **Run `/crayon-onboard` first**: the plan stops and sends you to the onboarding walk. When the
  walk has recorded the files, start the plan again.
- **Ground this intake dynamically**: the plan skill reads the declared sources and the pages
  around them in memory, for this one plan, and saves nothing. The next plan starts again from
  nothing.

The third answer is faster but not repeatable. It suits a quick page in a repository you will
not document again. The first two leave a record.

## Under the hood

Every context file is handed to the tool as text, and the tool places it, digests it and
commits it:

```bash
printf '%s\n' "$DOC_STYLE" | crayon context stage doc-style.md --body-file - --source docs/index.md
crayon context record --model "$MODEL" --model-origin skill --note "first walk of docs/"
```

`context stage` writes the text under `.crayon/staging/_context/`, the tool's own gitignored
staging directory, with the `--source` locators you declare beside it. `context record`
promotes every staged artefact into `.crayon/context/`, writes `manifest.json` — one sha256 per
artefact computed by the tool, the declared sources, the actor, the model claim, the timestamp
and the HEAD it was recorded against — and makes one commit with `Crayon-Phase:
context-recorded`. It carries no `Crayon-Unit`: the context belongs to the repository, not to a
unit, and no ledger event is written. A partial re-stage keeps every artefact it does not
touch, so a refreshed `doc-style.md` from a fetched style guide leaves a walked `glossary.md`
standing. Re-recording bytes that HEAD already holds is a no-op (`noop_unchanged`, exit 3),
and the staged copies are discarded.

`crayon context show` derives the state rather than storing it: which of the five are present,
which the manifest records, which are `drifted` (edited by hand since the record) and which are
`unrecorded` (placed by hand and never recorded). Drift is reported, never refused; restore the
recorded bytes from git or re-record the edit through the two verbs. While any of the first
three is absent, `crayon context show` routes `onboard`; `crayon-plan` opens with
`crayon context show --json`. The normative rules are in [[contract]] §5.1, §5.5, §5.6, §5.7
and §6.

The skills hold no write tool for `.crayon/context/`. A file you trust can also be recorded
without a skill, in the same two verbs:

```bash
crayon context stage doc-style.md --body-file path/to/your-style-guide.md
crayon context stage glossary.md --body-file path/to/glossary.md
crayon context record --note "house style and glossary, supplied by hand"
```

Copying files straight into `.crayon/context/` and committing them yourself also works;
`context show` then reports them as `unrecorded`, and the next `context record` that touches
the set freezes their digests too.

Related: [[install]], [[architecture]], [[contract]], [[conventions]], [[internals]].
