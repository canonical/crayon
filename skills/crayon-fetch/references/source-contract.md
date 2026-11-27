Load this file at workflow step 1, before any source is retrieved or inspected.

# Source contract

The reduced source scope for `crayon-fetch`. A source outside these four classes is
not in scope, and a declaration that does not carry these fields is not a
declaration.

## Accepted source types

| Source type | Meaning | Required locator |
| --- | --- | --- |
| `local-export` | A file or directory already exported onto local disk. | Local path. |
| `repository-path` | A local repository checkout or source tree. | Local path. |
| `url` | A remote web or API resource. | URL. |
| `harness-tool-result` | Content already returned by the agent harness. | Tool name and result identifier, transcript reference, or attached result name. |

## Required source record fields

| Field | Required | Description |
| --- | --- | --- |
| `source_id` | yes | Stable short identifier. |
| `source_type` | yes | One accepted source type. |
| `status` | yes | `accepted`, `partial`, or `failed`. |
| `origin` | yes | Path, URL, harness result identifier, or attachment name. This is the locator handed to `crayon context stage --source`. |
| `retrieval_method` | yes | Integration, tool, or inspection method used. |
| `retrieved_at` | yes | ISO 8601 timestamp for the attempt. |
| `revision` | yes | Commit, version, ETag, Last-Modified, export timestamp, response timestamp, or `unknown`. |
| `content_preserved` | yes | Boolean. |
| `preserved_location` | yes | Local path, inventory path, checksum record, sanitized excerpt path, or `none`. |
| `limitations` | yes | Missing metadata, skipped files, redactions, partial retrieval, or access limits. |
| `failure_reason` | yes for failed | Concrete reason for failure. |
| `next_action` | yes for failed | Action needed to make the source available. |

The record is kept in the conversation and summarised in the handoff and in the
`--note` of `crayon context record`; the tool itself records only each artefact's
`--source` locators, verbatim, in `manifest.json`.

## Status values

- `accepted`: the source was retrieved or inspected through the declared method.
- `partial`: the source was reachable, but revision, preservation, metadata, or
  content access was incomplete.
- `failed`: the source or requested integration was unavailable.

## Revision rules

Use the strongest available revision signal:

1. Git commit id plus dirty or clean status for git repositories.
2. File modification timestamp or export timestamp for local exports.
3. HTTP ETag, Last-Modified, response timestamp, or final URL metadata for URL
   sources.
4. Harness result identifier or transcript timestamp for harness-native tool
   results.
5. `unknown` if no reliable revision signal exists.

Never invent a revision.

## Preservation rules

`content_preserved` records whether content was retained locally beyond the
immediate workflow. If preservation is false, `preserved_location` must be `none`.
If preservation is true, `preserved_location` must point to a local artefact,
inventory, checksum record, or sanitized excerpt.

Preserve only the minimum source content needed for later verification, and never
credentials, tokens, private keys or sensitive private content.

## Failure examples

- the local path does not exist, or exists but is unreadable;
- the requested URL integration is unavailable, or the URL cannot be retrieved;
- the harness result is not present in the context;
- the repository revision cannot be determined after git was explicitly required.

Each becomes a `failed` record with its reason and next action; none becomes a
substitute source.
