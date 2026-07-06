---
schema_version: 1
unit_id: workshop-definition
intent: reference
audience: "Workshop users who author workshop.yaml by hand \u2014 both first-time\
  \ authors and experienced users arriving from other tools or projects"
title: Workshop definition
sources:
- path: internal/workshop/workshop_file.go
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/reference/definition-files/schema.json
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
- path: docs/examples/workshop-golang.yaml
  ref: null
  commit: 5e3636a74be47e82b6a2586aa79674f9724c36ea
  role: primary
sphinx_target: reference/definition-files/workshop-definition.rst
steering_notes: The page must give workshop users everything they need to get any
  field in workshop.yaml right without consulting another page; it should cover every
  field's type, whether it is required, its default, and its constraints (name format,
  accepted bases, valid action names), structured so it works both as a first-read
  introduction and a quick-lookup reference for experienced users arriving from elsewhere.
---
## Intent & scope

A complete field-by-field reference for `workshop.yaml` — the file Workshop users author to define a workshop. Covers every accepted field, its type, whether it is required or optional, its default, and any constraint (valid name format, accepted base values). Serves both as a first-read introduction to the file's structure and as a quick-lookup reference for experienced users. Does not explain when or why to use a given feature; for that, see the companion explanation pages.

## Outline / acceptance

- **Filename and location** — where `workshop.yaml` lives, how Workshop searches for it, and the alternate filename (`.workshop.yaml`)
- **Top-level fields** — table: `name`, `base`, `sdks`, `connections`, `actions`; each row gives type, required/optional, default, and a one-line description
- **Name and base constraints** — valid name format (character rules, length limit), accepted `base` values
- **SDK entries** — sub-fields of each entry in `sdks`: the SDK name to install, optional `channel`, optional `source`, and the `plugs`/`slots` maps; includes the `bind:` shorthand syntax
- **Connections** — how to wire a plug on one SDK to a slot on another; the `plug:` / `slot:` reference syntax
- **Actions** — the fields available in each named action entry: command, environment variables, working directory, user/group; name constraints
- **JSON Schema** — link to `schema.json` and embed or link the dropdown (matching sibling page pattern)
- **Examples** — one or more annotated `workshop.yaml` examples drawn from `docs/examples/`
- **See also** — links to the concepts explanation, the `workshop init` CLI reference, and the SDK definition reference
