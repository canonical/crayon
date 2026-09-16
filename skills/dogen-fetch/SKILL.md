---
name: dogen-fetch
description: "Produce reusable documentation steering artefacts from declared sources. Accept a local export, repository path, URL, or harness-native tool result; record origin, retrieval time or source revision when known, and local preservation status; fail visibly when a requested integration or source is unavailable."
---

# Dogen fetch

Use this skill when a downstream documentation workflow needs project-specific
steering artefacts before drafting, reviewing, or restructuring documentation.

The expected artefacts are:

- `profile.md`
- `glossary.md`
- `glossary.json`
- `structure-notes.md`

The source scope is intentionally narrow. Before retrieval or inspection, each
input must be declared as one of the following source types:

- `local-export`: documentation or other source content that has already been
  exported to a local file or directory.
- `repository-path`: a local repository checkout or source tree to inspect.
- `url`: a remote web page or API resource to retrieve.
- `harness-tool-result`: content already returned by an agent tool, such as an
  attached file or a tool result identified in the conversation.

Each declaration must include a locator appropriate to its type: a local path
for `local-export` or `repository-path`, a URL for `url`, or a tool/result
identifier for `harness-tool-result`.

Do not accept undeclared or implied source classes. Do not silently replace a
requested source or integration with a different one.

## Inputs

For each source, record a declaration with:

- source identifier;
- source type;
- origin locator, such as a path, URL, or harness result identifier;
- requested integration or retrieval method, when specified;
- whether local source preservation is requested;
- allowed fallback retrieval methods, if any.

If a declaration is incomplete but the missing value is obvious from the user
request, infer it and record the inference. If it is not obvious, ask one
focused clarification question.

## Workflow

Follow this workflow in order.

1. **Declare sources.** Normalize each input into the source contract in
   `references/source-contract.md`. Record the source before retrieval.
2. **Retrieve or inspect sources.** Use the declared method only. Record origin,
   retrieval time, source revision or response metadata when known, and whether
   content was preserved locally.
3. **Fail visibly if unavailable.** If the requested integration, path, URL, or
   harness result is unavailable, create a failure record and stop processing
   that source unless an allowed fallback was declared.
4. **Build the evidence base.** Use only accepted or explicitly partial source
   records. Keep source excerpts bounded and preserve paths or identifiers for
   verification.
5. **Write artefacts.** Produce `profile.md`, `glossary.md`, `glossary.json`,
   and `structure-notes.md` according to `references/artefact-contract.md`.
6. **Validate.** Check that all four artefacts exist, `glossary.json` parses,
   and source provenance is recorded in each artefact or in the companion source
   manifest.
7. **Handoff.** Report accepted sources, failed sources, known revisions,
   preservation status, output paths, and limitations.

See `references/workflow.md` for the expanded workflow.

## Source handling

- A local export must exist and be readable.
- A repository path must exist and be readable. If it is a Git repository,
  record `HEAD` and dirty status when available. If not, record revision as
  `unknown`.
- A URL must be retrieved through the requested integration when one is named.
  Record final URL, status or response metadata when available, and retrieval
  time.
- A harness-native tool result must already be present in the harness context.
  Record the tool name and result identifier or transcript reference when
  available. Do not re-run the tool unless the requester asks for fresh input.

## Artefact requirements

`profile.md` records style, voice, audience, formatting, completeness, and
quality signals.

`glossary.md` records project terms, definitions, aliases, and terminology
drift in human-readable form.

`glossary.json` records the same glossary in the JSON shape defined in
`references/artefact-contract.md`.

`structure-notes.md` records documentation topology, coverage notes, structural
risks, and prioritized improvements.

Each artefact must distinguish observed evidence from inference. Do not claim a
gap is exhaustive unless the inspected source scope supports it.

## Output location and names

Unless the user specifies otherwise, write the four artefacts to the current
working directory using these names:

- `profile.md`
- `glossary.md`
- `glossary.json`
- `structure-notes.md`

If the user specifies an output directory, write all four artefacts there. If
the user specifies a filename prefix or replacement names, preserve the four
artefact roles and apply that naming scheme consistently. Keep
`source-manifest.json` beside the artefacts when multiple sources are used or
when provenance needs to be recorded separately.

## Failure behavior

Failure must be visible. For an unavailable source or integration, record:

- requested source declaration;
- failed retrieval method or integration;
- observed error or unavailable capability;
- retrieval attempt time;
- whether any fallback was allowed or attempted;
- next action required.

Do not mark a failed source as accepted. Do not continue with a substitute
source unless an allowed fallback was declared.

## Preservation and privacy

Preservation means retaining source content, a sanitized excerpt, or a bounded
inventory locally for later verification. Source content preservation is not
assumed. Always record whether preservation happened.

Do not preserve credentials, tokens, private keys, or sensitive private content.
If sensitive content is encountered, record that redaction occurred and preserve
only sanitized metadata or excerpts.

## Constraints

- Do not require a specific model provider, SDK, documentation framework, or
  repository hosting platform.
- Do not perform repository-wide analysis until sources are declared and
  provenance has been recorded.
- Do not rewrite source documentation as part of this skill.
- Do not hide missing integrations behind best-effort guesses.
- Keep output suitable for downstream documentation workflows.

## References

- `references/source-contract.md`
- `references/artefact-contract.md`
- `references/workflow.md`
- `templates/source-manifest.json`
