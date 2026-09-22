# Context files

<!-- provenance: new page; the context-file prose moved here from docs/install.md (Add context files) and README.md (Glossary, context files) -->

Context files teach the skills your house style, vocabulary, and where facts live. They are
read from `.dogen/context/` in the docs repository by `dogen-plan` when it grounds a
declaration and by `dogen-write` when it drafts, and they reach that directory through the tool,
which digests and commits them like everything else it records. This page is the one home for
what they are, who produces them, and how they are recorded.

## The five names

The tool recognises exactly five artefacts; anything else is refused. The set is defined once,
in `dogen.py`, and the skills and this page name the same five.

| Name | What it carries | Produced by |
|---|---|---|
| `doc-style.md` | how the project writes: voice, audience, formatting, completeness habits, drift | `/dogen-onboard` from a walk of the repository's docs; `/dogen-fetch` from a declared source such as a house style guide |
| `glossary.md` | the project's terms as its prose uses them, with aliases and inconsistency flags | `/dogen-onboard`; `/dogen-fetch` from a terminology document held elsewhere |
| `structure.md` | the docs' information architecture, Diátaxis balance, structural risks, and the code-versus-docs coverage gaps tagged `[CODE↔DOCS GAP]` | `/dogen-onboard`; `/dogen-fetch` from an exported docs set |
| `code-to-docs-map.md` | which code areas each page documents | tooling outside dogen (below); recorded by you |
| `doc-gaps.md` | prioritized units the docs are missing, derived from the map | tooling outside dogen; recorded by you |

`dogen-plan` treats the first three as the context: while any of them is absent, `dogen context
show` routes `onboard` and the plan skill offers you the bootstrap choice described below. The
last two are optional and never route on their own.

## How they are recorded

No skill writes `.dogen/context/`. Every artefact is handed to the tool as text, and the tool
places it, digests it and commits it:

```bash
printf '%s\n' "$DOC_STYLE" | dogen context stage doc-style.md --body-file - --source docs/index.md
dogen context record --model "$MODEL" --model-origin skill --note "first walk of docs/"
```

`context stage` writes the text under `.dogen/staging/_context/`, the tool's own gitignored
staging directory, with the `--source` locators you declare beside it. `context record`
promotes every staged artefact into `.dogen/context/`, writes `manifest.json` — one sha256 per
artefact computed by the tool, the declared sources, the actor, the model claim, the timestamp
and the HEAD it was recorded against — and makes one commit with `Dogen-Phase:
context-recorded`. It carries no `Dogen-Unit`: the context belongs to the repository, not to a
unit, and no ledger event is written. A partial re-stage keeps every artefact it does not
touch, so a refreshed `doc-style.md` from a fetched style guide leaves a walked `glossary.md`
standing. Re-recording bytes that HEAD already holds is a no-op (`noop_unchanged`, exit 3),
and the staged copies are discarded.

`dogen context show` derives the state rather than storing it: which of the five are present,
which the manifest records, which are `drifted` (edited by hand since the record) and which are
`unrecorded` (placed by hand and never recorded). Drift is reported, never refused; restore the
recorded bytes from git or re-record the edit through the two verbs. The normative rules are in
[[contract]] §5.1, §5.5, §5.6, §5.7 and §6.

## Producing them

**`/dogen-onboard`** walks the repository dogen is run in: it reads the docs tree, the README and
supplementary prose, classifies each page by its Diátaxis direction, cross-reads the product
surface (CLI flags, public API, config, environment variables) for coverage gaps, and authors
`doc-style.md`, `glossary.md` and `structure.md` from what it read, each claim grounded in a page
or a symbol. Run it once to seed the context and again when the docs or the product drift far
enough that the artefacts go stale. It holds no write tool: the three artefacts reach disk
through the two verbs above.

**`/dogen-fetch`** does the same from sources you declare that live outside the repository — a
local export, another checkout, a page at a URL, or a document your agent already holds. Each
source is declared before it is retrieved (type, locator, retrieval method, preservation,
fallbacks), retrieved only through the declared method, and recorded with its origin, retrieval
time and revision; a source that cannot be reached is reported as failed, never replaced by one
you did not declare. The artefacts it produces carry their sources as `--source` locators in the
manifest. Use it occasionally, when the material that should steer the docs is not in the
repository, or when `/dogen-onboard` meets such a source and hands you over.

**By hand.** A style guide or glossary you already trust needs no walk. Stage it through the
tool and record it, so it is digested and committed like the rest:

```bash
dogen context stage doc-style.md --body-file path/to/your-style-guide.md
dogen context stage glossary.md --body-file path/to/glossary.md
dogen context record --note "house style and glossary, supplied by hand"
```

Copying files straight into `.dogen/context/` and committing them yourself also works; `context
show` then reports them as `unrecorded`, and the next `context record` that touches the set
freezes their digests too.

**`code-to-docs-map.md` and `doc-gaps.md`** come from tooling outside dogen. A deterministic map
and the gaps derived from it are produced by the
[Code to docs mapper](https://code.launchpad.net/code-to-docs-mapper), which reads the code and
the docs from two collections in a vector database built with
[Wide scope RAG](https://code.launchpad.net/wide-scope-rag); dogen neither depends on nor
understands either. Record their output through the two verbs so it carries a digest. Without a
map, `dogen-plan`'s ephemeral crawl (below) stands in for it, less repeatably, for one intake.

## When they are missing

`dogen-plan` opens with `dogen context show --json`. When any of `doc-style.md`, `glossary.md`
or `structure.md` is absent it asks you once, and offers three answers:

- **I'll add them** — you supply the files, by hand or through the two verbs; the intake
  pauses until they are there.
- **Run `/dogen-onboard` first** — the plan stops and routes you to the onboarding walk; when it
  has recorded the artefacts, start the plan again.
- **Ground this intake dynamically** — the plan skill reads the declared sources and their
  neighbourhood in memory, for this one intake, and persists nothing; the next session grounds
  again from scratch.

The third answer trades repeatability for speed and is the right one for a quick unit in a
repository you will not document twice. The first two leave a record.

Related: [[install]], [[architecture]], [[contract]], [[conventions]].
