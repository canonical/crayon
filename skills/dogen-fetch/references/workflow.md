# Expanded workflow

This workflow expands the concise steps in `SKILL.md`.

## 1. Source declaration

Create a source record for each requested source before retrieval. If multiple
sources are requested, create a source manifest using
`templates/source-manifest.json`.

Required declaration fields:

- `source_id`
- `source_type`
- `origin`
- `requested_integration`
- `preserve_content`
- `allowed_fallbacks`

## 2. Retrieval or inspection

Use only the declared source type and retrieval method.

For `local-export`, inspect filesystem metadata and optionally preserve a copy,
inventory, or checksum record.

For `repository-path`, inspect filesystem metadata. If Git is available for the
path, record `HEAD` and dirty status. If not, record revision as `unknown`.

For `url`, use the requested integration. Record final URL, status, response
metadata, and retrieval time when available.

For `harness-tool-result`, record the existing tool result. Do not re-run the
tool unless the requester asks for fresh retrieval.

## 3. Visible failure

If retrieval fails, mark the source `failed`, record the reason, and stop using
that source. If an allowed fallback exists, record both the failed primary
method and fallback result.

Failure examples:

- local path does not exist;
- path exists but is unreadable;
- requested URL integration is unavailable;
- URL cannot be retrieved;
- harness result is not present in context;
- repository revision cannot be determined after Git was explicitly required.

## 4. Evidence base

Use accepted and partial sources only. Preserve provenance with every extracted
piece of evidence. Keep excerpts bounded and avoid copying sensitive content.

## 5. Artefact generation

Generate all four required artefacts:

- `profile.md`
- `glossary.md`
- `glossary.json`
- `structure-notes.md`

Use `references/artefact-contract.md` for required content.

## 6. Validation

Validate that:

- every requested source has a source record;
- unavailable sources are marked failed or partial;
- each source record includes origin, retrieval time, revision or `unknown`,
  and preservation status;
- all four artefacts exist;
- `glossary.json` parses;
- limitations from source failures are visible in the handoff.

## 7. Handoff

Report:

- accepted sources;
- failed or partial sources;
- known revisions;
- local preservation status;
- output artefact paths;
- downstream limitations.
