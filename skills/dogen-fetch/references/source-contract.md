# Source contract

This contract defines the reduced source scope for `dogen-fetch`.

## Accepted source types

| Source type | Meaning | Required locator |
| --- | --- | --- |
| `local-export` | A file or directory already exported onto local disk. | Local path. |
| `repository-path` | A local repository checkout or source tree. | Local path. |
| `url` | A remote web or API resource. | URL. |
| `harness-tool-result` | Content already returned by the agent harness. | Tool name and result identifier, transcript reference, or attached result name. |

No other source class is in scope.

## Required source record fields

| Field | Required | Description |
| --- | --- | --- |
| `source_id` | yes | Stable short identifier. |
| `source_type` | yes | One accepted source type. |
| `status` | yes | `accepted`, `partial`, or `failed`. |
| `origin` | yes | Path, URL, harness result identifier, or attachment name. |
| `retrieval_method` | yes | Integration, tool, or inspection method used. |
| `retrieved_at` | yes | ISO 8601 timestamp for the attempt. |
| `revision` | yes | Commit, version, ETag, Last-Modified, export timestamp, response timestamp, or `unknown`. |
| `content_preserved` | yes | Boolean. |
| `preserved_location` | yes | Local path, inventory path, checksum record, sanitized excerpt path, or `none`. |
| `limitations` | yes | Missing metadata, skipped files, redactions, partial retrieval, or access limits. |
| `failure_reason` | yes for failed | Concrete reason for failure. |
| `next_action` | yes for failed | Action needed to make the source available. |

## Status values

- `accepted`: the source was retrieved or inspected through the declared
  method.
- `partial`: the source was reachable, but revision, preservation, metadata,
  or content access was incomplete.
- `failed`: the source or requested integration was unavailable.

## Revision rules

Use the strongest available revision signal:

1. Git commit hash plus dirty/clean status for Git repositories.
2. File modification timestamp or export timestamp for local exports.
3. HTTP ETag, Last-Modified, response timestamp, or final URL metadata for URL
   sources.
4. Harness result identifier or transcript timestamp for harness-native tool
   results.
5. `unknown` if no reliable revision signal exists.

Do not invent revisions.

## Preservation rules

`content_preserved` records whether content was retained locally beyond the
immediate workflow. If preservation is false, `preserved_location` must be
`none`. If preservation is true, `preserved_location` must point to a local
artefact, inventory, checksum record, or sanitized excerpt.

Preserve only the minimum source content needed for later verification.
