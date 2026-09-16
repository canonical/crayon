# Dogen fetch skill

`dogen-fetch` prepares reusable documentation steering artefacts from sources
you explicitly identify. It captures project style, terminology, structure,
and source provenance so later documentation work starts from evidence rather
than assumptions.

## Where it fits

Use `dogen-fetch` before declaring or drafting a documentation unit when the
target project does not already have reliable context files:

```text
dogen-fetch -> dogen-plan -> dogen-write -> dogen-review
```

The skill prepares context; it does not rewrite source documentation or draft
the final page. Add its outputs to the target repository's `.dogen/context/`
directory for the later skills to use.

## Outputs

By default, write these files to the current working directory:

- `profile.md` - style, voice, audience, formatting, completeness, and quality
  signals.
- `glossary.md` - human-readable terminology and terminology drift.
- `glossary.json` - machine-readable glossary data.
- `structure-notes.md` - documentation topology, coverage, structural risks,
  and prioritized improvements.

For multiple sources, or when provenance needs to be kept separately, also
write `source-manifest.json` beside them. You can specify another directory, a
filename prefix, or replacement names in the prompt. Preserve the four
artefact roles when renaming them.

## Accepted sources

Declare each source as one of these types:

- `local-export` - an existing exported file or directory;
- `repository-path` - a local repository checkout or source tree;
- `url` - a remote page or API resource;
- `harness-tool-result` - content already returned by the agent harness.

The skill records origin, retrieval method, timestamp, revision when known,
preservation status, and limitations. It reports unavailable sources instead
of silently substituting another source.

## Prompt examples

### Local export

```text
Use dogen-fetch on the local export at /tmp/project-docs-export.
Treat it as a local-export source. Write the standard four artefacts to
.dogen/context/ and keep source-manifest.json there as well.
```

### Repository path

```text
Use dogen-fetch on the repository at ~/canonical/product-docs.
Treat it as a repository-path source, inspect its Git revision and dirty status,
and write the outputs to ~/canonical/product-docs/.dogen/context/.
```

### URL

```text
Use dogen-fetch on this URL as a url source:
https://documentation.ubuntu.com/project/docs/page-name/
Use the requested web retrieval integration. Write the outputs to
/tmp/example-steering/ and preserve only a bounded, sanitized excerpt.
```

### Harness result

```text
Use dogen-fetch on the attached harness result named style-guide-export.
Treat it as a harness-tool-result and write the outputs to
.dogen/context/remote-guidance/.
```

### Multiple sources

```text
Use dogen-fetch on these sources:
- repository-path: ~/canonical/kernel-docs
- url: https://docs.example.com/style-guide
Use the repository as the primary source and record the URL as a second source.
Write all outputs and source-manifest.json to .dogen/context/kernel-docs/.
```

### Rename the outputs

```text
Use dogen-fetch on ~/canonical/kernel-docs and write to
.dogen/context/kernel-docs/. Use these names:
kernel-docs-profile.md, kernel-docs-glossary.md,
kernel-docs-glossary.json, and kernel-docs-structure-notes.md.
Keep source-manifest.json beside them.
```

### Declare a fallback

```text
Fetch https://docs.example.com/style-guide using the named web integration.
If that integration is unavailable, you may use the explicitly named fallback
browser tool. Record both attempts in the provenance and write the results to
/tmp/style-steering/.
```

When no output location or naming scheme is given, use the current working
directory and the standard filenames. When a source or requested integration
is unavailable and no fallback was authorized, stop processing that source and
record the failure.
