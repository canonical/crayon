# Artefact contract

`dogen-fetch` produces four required artefacts. Source provenance may be
kept in a companion source manifest, but the expected steering artefacts remain
unchanged.

## Required artefacts

### `profile.md`

Records how the source set communicates. Include:

- voice and tone;
- audience and assumed knowledge;
- formatting and structural conventions;
- completeness patterns, including examples, parameters, verification, and
  failure handling;
- overall quality signals, outliers, and limitations.

### `glossary.md`

Records terms from source prose. Include:

- term;
- definition based on inspected source evidence;
- aliases or variant spellings;
- inconsistency notes;
- source evidence path or identifier when available.

### `glossary.json`

Machine-readable glossary. Required shape:

```json
{
  "terms": [
    {
      "term": "string",
      "definition": "string",
      "aliases": ["string"],
      "inconsistent": false,
      "inconsistency_note": null,
      "evidence": ["source-id:path-or-identifier"]
    }
  ]
}
```

### `structure-notes.md`

Records how documentation or source content is organized. Include:

- source inventory summary;
- documentation topology or observed content structure;
- category or taxonomy notes when the source declares one;
- coverage notes tied to inspected evidence;
- structural risks and prioritized improvements;
- limitations from failed or partial sources.

## Evidence rules

- Distinguish observed evidence from inference.
- Cite source identifiers, paths, URLs, or harness result identifiers.
- Do not claim exhaustive coverage if sources were partial, sampled, or failed.
- Include failed and partial source limitations in `structure-notes.md`.
- Keep source excerpts short and avoid unnecessary private content.
