# Copilot CLI Session

> [!NOTE]
> - **Session ID:** `b9b04ca6-50b8-4ddd-89ac-4e1452276e07`  
> - **Started:** 4/7/2026, 19:06:28  
> - **Duration:** 30m 49s  
> - **Exported:** 4/7/2026, 19:37:17  

---

<sub>3s</sub>

### User

/dogen-plan workshop yaml reference

---

<sub>7s</sub>

### `skill`

**dogen-plan**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "dogen-plan"
}
```

</details>

```
Skill "dogen-plan" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>13s</sub>

### Copilot

Let me ground myself in the repo before we start the intake.

---

<sub>14s</sub>

### `bash`

**Check dogen context artifacts**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen context ls 2>&1

<details>
<summary>7 lines</summary>

```
.dogen/context/code-to-docs-map.md
.dogen/context/doc-gaps.md
.dogen/context/doc-style.md
.dogen/context/glossary.json
.dogen/context/glossary.md
.dogen/context/structure.md
<shellId: 1 completed with exit code 0>
```

</details>


---

<sub>14s</sub>

### `bash`

**List existing docs structure**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && find docs -type f | sort 2>/dev/null | head -60

<details>
<summary>61 lines</summary>

```
docs/404.rst
docs/404.svg
docs/coding-style-guide.md
docs/conf.py
docs/contributing.rst
docs/coverage.md
docs/coverage.py
docs/coverage_requirements.txt
docs/.coverage.yaml
docs/.custom_wordlist.txt
docs/_dev/get_vale_conf.py
docs/_dev/pa11y.json
docs/_dev/.pre-commit-config.yaml
docs/_dev/.pymarkdown.json
docs/_dev/update_sp.py
docs/_dev/version
docs/doc-style-guide.md
docs/examples/go-sdkcraft.yaml
docs/examples/prompts/flask-architect.txt
docs/examples/prompts/flask-coder.txt
docs/examples/prompts/flask-shared.txt
docs/examples/prompts/flask-synthesis.txt
docs/examples/sdkcraft-multibase.yaml
docs/examples/sdkcraft-ros2.yaml
docs/examples/sdk-go-runtime.yaml
docs/examples/sdk-project-cache.yaml
docs/examples/workshop-digits-cuda.yaml
docs/examples/workshop-go-dev.yaml
docs/examples/workshop-golang.yaml
docs/examples/workshop-try-go.yaml
docs/explanation/architecture/components.rst
docs/explanation/architecture/index.rst
docs/explanation/architecture/runtime-behavior.rst
docs/explanation/cli.rst
docs/explanation/index.rst
docs/explanation/interfaces/camera-interface.rst
docs/explanation/interfaces/concepts.rst
docs/explanation/interfaces/custom-device-interface.rst
docs/explanation/interfaces/desktop-interface.rst
docs/explanation/interfaces/gpu-interface.rst
docs/explanation/interfaces/index.rst
docs/explanation/interfaces/mount-interface.rst
docs/explanation/interfaces/plugs-and-slots.rst
docs/explanation/interfaces/ssh-interface.rst
docs/explanation/interfaces/tunnel-interface.rst
docs/explanation/sdks/best-practices.rst
docs/explanation/sdks/concepts.rst
docs/explanation/sdks/index.rst
docs/explanation/sdks/lifecycle.rst
docs/explanation/sdks/parts.rst
docs/explanation/sdks/runtime-hooks.rst
docs/explanation/sdks/sdk-vs-dockerfile.rst
docs/explanation/workshops/changes-tasks.rst
docs/explanation/workshops/concepts.rst
docs/explanation/workshops/index.rst
docs/explanation/workshops/multi-workshop-patterns.rst
docs/explanation/workshops/projects.rst
docs/_extensions/flat_toctree.py
docs/.gitignore
docs/how-to/customize-workshops/add-actions.rst
<shellId: 0 completed with exit code 0>
```

</details>


---

<sub>18s</sub>

### `bash`

**List remaining docs files**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && find docs -type f | sort 2>/dev/null | tail -80

<details>
<summary>81 lines</summary>

```
docs/reference/cli/sdkcraft-register.rst
docs/reference/cli/sdkcraft-release.rst
docs/reference/cli/sdkcraft-revisions.rst
docs/reference/cli/sdkcraft.rst
docs/reference/cli/sdkcraft-stage.rst
docs/reference/cli/sdkcraft-test.rst
docs/reference/cli/sdkcraft-try.rst
docs/reference/cli/sdkcraft-upload.rst
docs/reference/cli/sdkcraft-version.rst
docs/reference/cli/sdkcraft-whoami.rst
docs/reference/cli/sdk-find.rst
docs/reference/cli/sdk-info.rst
docs/reference/cli/sdk-list.rst
docs/reference/cli/sdk.rst
docs/reference/cli/workshop-actions.rst
docs/reference/cli/workshop-changes.rst
docs/reference/cli/workshop-connections.rst
docs/reference/cli/workshop-connect.rst
docs/reference/cli/workshopctl.rst
docs/reference/cli/workshop-disconnect.rst
docs/reference/cli/workshop-exec.rst
docs/reference/cli/workshop-info.rst
docs/reference/cli/workshop-init.rst
docs/reference/cli/workshop-launch.rst
docs/reference/cli/workshop-list.rst
docs/reference/cli/workshop-okay.rst
docs/reference/cli/workshop-refresh.rst
docs/reference/cli/workshop-remount.rst
docs/reference/cli/workshop-remove.rst
docs/reference/cli/workshop-restore.rst
docs/reference/cli/workshop.rst
docs/reference/cli/workshop-run.rst
docs/reference/cli/workshop-shell.rst
docs/reference/cli/workshop-sketches.rst
docs/reference/cli/workshop-sketch-sdk.rst
docs/reference/cli/workshop-start.rst
docs/reference/cli/workshop-stop.rst
docs/reference/cli/workshop-tasks.rst
docs/reference/cli/workshop-warnings.rst
docs/reference/definition-files/index.rst
docs/reference/definition-files/_interfaces/camera.rst
docs/reference/definition-files/_interfaces/custom-device.rst
docs/reference/definition-files/_interfaces/desktop.rst
docs/reference/definition-files/_interfaces/gpu.rst
docs/reference/definition-files/_interfaces/mount.rst
docs/reference/definition-files/_interfaces/ssh-agent.rst
docs/reference/definition-files/_interfaces/tunnel.rst
docs/reference/definition-files/schema.json
docs/reference/definition-files/schema-sdkcraft.json
docs/reference/definition-files/schema-sdk.json
docs/reference/definition-files/sdkcraft-definition.rst
docs/reference/definition-files/sdk-definition.rst
docs/reference/index.rst
docs/reference/sdks.rst
docs/reference/workshops.rst
docs/reference/workshop-status.rst
docs/release-notes/index.rst
docs/release-notes/v0.9.0.md
docs/release-notes/v0.9.1.md
docs/release-notes/v0.9.2.md
docs/requirements.in
docs/requirements.txt
docs/security.md
docs/_static/cookie-banner.css
docs/_static/favicon.png
docs/_static/flat-toctree.css
docs/_static/flat-toctree.js
docs/_static/js/bundle.js
docs/_static/js/overwrite_links.js
docs/_static/workshop.css
docs/_templates/base.html
docs/_templates/footer.html
docs/_templates/header.html
docs/tutorial/index.rst
docs/tutorial/part-1-get-started.rst
docs/tutorial/part-2-work-with-interfaces.rst
docs/tutorial/part-3-sketch-sdks.rst
docs/tutorial/part-4-craft-sdks.rst
docs/update_redirected_links.py
docs/.wokeignore
<shellId: 4 completed with exit code 0>
```

</details>


---

<sub>18s</sub>

### `bash`

**Read doc-gaps context artifact**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat .dogen/context/doc-gaps.md

<details>
<summary>127 lines</summary>

```
# User-Need Documentation Gaps

This proposal is based on `code_to_docs_coverage.md`, which reports 3644 likely undocumented code chunks at a 0.60 similarity threshold. The raw report contains many internal helpers, tests, generated command reference paths, and low-level implementation details. The recommendations below filter those signals through a user question: "Would someone need this page to complete a real task or recover from a real problem?"

## Recommended New Docs

### 1. Run and debug workshop actions

- Suggested location: `workshop-docs/how-to/customize-workshops/run-and-debug-actions.rst`
- User need: A user has actions in `workshop.yaml` and wants to run them reliably, pass arguments, choose interactive or non-interactive mode, set environment variables, set a working directory, or understand why an action behaves differently in CI.
- Why this is a gap: The report flags `cmd/workshop/exec.go` and action-related code such as `workshop run`, `workshop exec`, `workshop actions`, action argument handling, terminal mode detection, timeouts, user/group IDs, and action completion. Existing docs cover adding actions and CLI reference, but not the task of running and debugging them end to end.
- Suggested content:
  - When to use `workshop run`, `workshop exec`, and `workshop shell`.
  - How `--` separates Workshop arguments from command or action arguments.
  - How interactive and non-interactive modes change input and output.
  - How to pass environment variables and working directories.
  - How to use timeouts and interpret exit codes.
  - Common failure cases: workshop not ready, action not found, command blocked waiting for input, and output split between stdout and stderr.

### 2. Troubleshoot workshop network access and firewall warnings

- Suggested location: `workshop-docs/how-to/fix-workshops/fix-network-forwarding.rst`
- User need: A user starts a workshop but network access is broken, port forwarding does not work, or Workshop warns that the LXD bridge may be blocked by Docker, UFW, or nftables rules.
- Why this is a gap: The report flags `internal/workshop/lxd/firewall.go`, bridge detection, Docker and UFW-specific remediation, and LXD network helpers. Existing docs include general installation/debug pages and port-forwarding docs, but the firewall warning path is specific and likely to be searched by users after seeing the warning.
- Suggested content:
  - What the warning means in plain language: traffic cannot cross the LXD bridge.
  - How to identify the bridge name from the warning.
  - How to apply the Docker-specific nft rules suggested by Workshop.
  - How to apply the UFW-specific rules suggested by Workshop.
  - How to verify that forwarding works afterward.
  - How to undo or adapt the rules for local security policy.

### 3. Restore a workshop and understand snapshot behavior

- Suggested location: `workshop-docs/how-to/develop-with-workshops/restore-workshop-state.rst`
- User need: A user wants to return a workshop to a known state, recover after an experiment, or understand what `workshop restore` changes and what it does not change.
- Why this is a gap: The report flags snapshot and restore code in `internal/workshop/lxd/lxd_backend_snapshots.go`, `cmd/workshop/restore.go`, and project lifecycle methods. Existing docs have CLI reference for `workshop restore`, but users need a workflow-oriented guide before they trust it on real work.
- Suggested content:
  - When snapshots are created and what they represent.
  - What is restored: instance state, SDK-derived environment, project files, mounts, and metadata.
  - What may not be restored: external services, host-side files outside mounted paths, and manual changes outside Workshop control.
  - How restore interacts with running tasks.
  - How to verify the restored state.
  - Safe practices before destructive experiments.

### 4. Fix SDK definition validation errors

- Suggested location: `workshop-docs/how-to/develop-sdks/fix-sdk-definition-errors.rst`
- User need: An SDK author runs `sdkcraft` or Workshop tooling and gets an error about an unknown YAML field, invalid SDK name, unsupported base, unsupported architecture, invalid hook, or invalid plug/slot/interface name.
- Why this is a gap: The report flags `internal/sdk/validate.go`, `internal/sdk/revision.go`, SDK YAML unknown-field errors, allowed bases, architecture validation, hook validation, and plug/slot/interface name validation. Existing reference pages list fields, but they do not appear to offer a repair guide centered on real validation failures.
- Suggested content:
  - How to read validation errors, including line and column for unknown fields.
  - Valid SDK name rules with examples.
  - Supported bases and architectures.
  - Supported runtime hook names.
  - Valid plug, slot, and interface names.
  - A small table of common errors, likely cause, and fix.

### 5. Choose, inspect, and pin SDK versions

- Suggested location: `workshop-docs/how-to/develop-with-workshops/manage-sdk-versions.rst`
- User need: A user wants to find an SDK, inspect who published it, choose a revision/channel, understand local versus store revisions, or avoid surprises when refreshing a workshop.
- Why this is a gap: The report flags `cmd/sdk/find.go`, `cmd/sdk/info.go`, `internal/sdk/revision.go`, `internal/sdk/store.go`, `internal/sdkstore/find.go`, `internal/sdkstore/info.go`, and `internal/sdkstore/download.go`. Existing CLI reference covers commands one by one; a task guide would connect discovery, inspection, selection, and refresh behavior.
- Suggested content:
  - How to search with `sdk find` and interpret results.
  - How to inspect an SDK with `sdk info`.
  - What local, store, revision, track, and channel mean in user terms.
  - How a workshop chooses an SDK when the definition gives a name, revision, or channel.
  - How to refresh intentionally and how to avoid accidental changes.

### 6. Manage interface connections safely

- Suggested location: `workshop-docs/how-to/customize-workshops/manage-interface-connections.rst`
- User need: A user wants to see which plugs and slots are connected, connect or disconnect them, understand unsupported interface actions, and resolve connection conflicts without reading individual reference pages.
- Why this is a gap: The report flags `cmd/workshop/connections.go`, `cmd/workshop/connect.go`, `cmd/workshop/disconnect.go`, `client/connections.go`, `internal/daemon/api_connections.go`, and interface conflict paths. Existing docs explain interface concepts and some conflict repair, but there is room for a practical guide for daily connection management.
- Suggested content:
  - How to list connections and filter the output.
  - How to connect and disconnect plugs and slots.
  - How to tell whether a connection is manual or automatic.
  - What common conflict messages mean.
  - What to do when an interface does not support a requested action.

### 7. Use the Go client API to control Workshop

- Suggested location: `workshop-docs/how-to/integrate-with-workshop/use-the-go-client.rst`
- User need: A tool author wants to write Go code that talks to `workshopd`, starts or restores projects, waits for changes, streams command execution, handles warnings, and reports errors correctly.
- Why this is a gap: The report flags the public `client/` package heavily: `Config`, socket connection behavior, retries and timeouts, async changes, wait behavior, warnings, projects, connections, SDK lookup, and exec websockets. This is a real developer-facing surface, not just an internal implementation detail.
- Suggested content:
  - How to create a client with default socket behavior.
  - How to configure base URL, socket path, timeout, retry interval, and user agent.
  - How to start, launch, restore, refresh, and remove projects.
  - How to wait for async changes and handle maintenance mode.
  - How to run commands and handle resize, signal, stdin, stdout, stderr, and exit code.
  - How to handle typed errors such as socket-not-found and conflict errors.

### 8. Integrate directly with the Workshop daemon API

- Suggested location: `workshop-docs/reference/api/workshopd-rest-api.rst`
- User need: A non-Go integration author wants to call the daemon API directly, or a support engineer needs to inspect what the CLI and client are doing over HTTP and websockets.
- Why this is a gap: The report flags daemon endpoint handlers for changes, tasks, exec, workshops, warnings, connections, responses, and websocket task output. Existing docs explain architecture and CLI behavior, but there does not appear to be a direct REST API reference.
- Suggested content:
  - Authentication and socket/base URL expectations.
  - Response envelope shape for sync, async, and error responses.
  - Change and task lifecycle endpoints.
  - Workshop lifecycle endpoints.
  - Exec websocket behavior.
  - Warning and maintenance responses.
  - Error shapes and conflict handling.

### 9. Understand Workshop data, cache, and project directories

- Suggested location: `workshop-docs/explanation/workshops/data-and-cache-directories.rst`
- User need: A user wants to know where Workshop stores project data, cache data, APT cache data, locks, and generated state so they can back it up, clean it safely, or debug disk usage.
- Why this is a gap: The report flags `internal/workshop/workshop_dirs.go`, project ID allocation, lock paths, project tracking, and cache path helpers. Existing docs include moving projects and purging, but a focused explanation would reduce fear around hidden state and cleanup.
- Suggested content:
  - The difference between project data, cache data, and host project files.
  - Which directories are safe to remove and when.
  - How project IDs are used.
  - How locks prevent concurrent modification.
  - How this relates to `workshop list`, `workshop remove`, and purge instructions.

## Lower-Priority Candidates

These may be worth creating later, but only if support questions or issue reports show real demand.

### Workshop warnings lifecycle

- Possible location: `workshop-docs/explanation/workshops/warnings.rst`
- User need: Understand how warnings are stored, summarized, and acknowledged with `workshop okay`.
- Reason to wait: Existing CLI reference and troubleshooting pages may be enough unless users often ask why warnings keep appearing.

### Local development with `go tool try`

- Possible location: `workshop-docs/how-to/contribute/run-workshop-locally.rst`
- User need: Contributors want a fast local daemon and client shell for testing changes.
- Reason to wait: This serves contributors rather than Workshop users, and the coverage report only flags `tools/try/main.go` lightly.

## Do Not Create Separate Docs For These Signals

- Test helpers, mocks, and export-test functions: These inflate the uncovered count but do not represent user tasks.
- Sorting helpers, string formatting helpers, YAML helper functions, and table rendering utilities: These are implementation details behind existing CLI behavior.
- Low-level OS helpers under `internal/osutil`, `internal/fsutil`, `internal/ptyutil`, `internal/progress`, and similar packages: These should only be documented when they surface as user-visible behavior, such as terminal mode handling or file cleanup.
- Internal daemon response helper types by themselves: Include their behavior in an API reference if that reference is created; do not create standalone pages for response structs.
- Generated command docs for every command: The reference pages already exist. Add task guides only where users need a workflow across several commands.

## Suggested Priority

1. `fix-network-forwarding.rst` because it maps to a concrete warning and recovery task.
2. `run-and-debug-actions.rst` because actions, exec, shell, and run are daily workflow commands with subtle behavior.
3. `fix-sdk-definition-errors.rst` because validation errors are common authoring blockers.
4. `restore-workshop-state.rst` because users need confidence before using restore.
5. `use-the-go-client.rst` if the Go client is supported as a public integration surface.
6. `manage-sdk-versions.rst` if users commonly choose among SDK revisions or channels.
7. `manage-interface-connections.rst` if connection conflicts remain a recurring support topic.
8. `workshopd-rest-api.rst` if non-Go integrations are expected.
9. `data-and-cache-directories.rst` if cleanup, backup, or disk usage questions are common.
<shellId: 2 completed with exit code 0>
```

</details>


---

<sub>18s</sub>

### `bash`

**Read structure context artifact**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat .dogen/context/structure.md

<details>
<summary>16 lines</summary>

```
Output too large to read at once (25.4 KB). Saved to: /tmp/copilot-tool-output-1783188406216-38dwm7.txt
Consider using tools like grep (for searching), head/tail (for viewing start/end), view with view_range (for specific sections), or jq (for JSON) to examine portions of the output.

Preview (first 500 chars):
# Documentation Structure Notes

**Repo:** `workshop`
**Generated:** 2026-07-03 09:55
**Source:** 149 doc files, 11 docstring blocks

> This artefact was generated by `repo-scraper` and is intended as
> **steering input** for a documentation generation pipeline.
> It is not end-user documentation.

---

## Purpose of this artefact

This document maps the **documentation architecture** of `workshop`:
    what doc surfaces exist, how they are organized, and where user-doc
    coverage appears inco
<shellId: 3 completed with exit code 0>
```

</details>


---

<sub>25s</sub>

### `bash`

**Read reference/definition-files/index.rst**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat docs/reference/definition-files/index.rst

<details>
<summary>34 lines</summary>

```
.. meta::
   :description: Overview of the YAML definition files used by Workshop and
                 SDKcraft, with links to the reference page for each file.

SDK and workshop definition files
=================================

.. @artefact SDK
.. @artefact workshop definition
.. @artefact SDK definition

Three YAML files describe what a workshop is
and how the SDKs inside it behave.
Each file has one authoritative reference page:

- :file:`workshop.yaml` is authored by workshop users;
  |ws_markup| reads it to launch a workshop.
  See :ref:`ref_workshop_definition`.
- :file:`sdk.yaml` ships inside SDK packages;
  |ws_markup| reads it at install time.
  Also authored directly for in-project SDKs.
  See :ref:`ref_sdk_definition`.
- :file:`sdkcraft.yaml` is authored by SDK publishers;
  |sdk_markup| reads it to build an SDK package,
  which embeds the generated :file:`sdk.yaml`.
  See :ref:`ref_sdkcraft_definition`.

.. toctree::
   :maxdepth: 1

   workshop-definition
   sdk-definition
   sdkcraft-definition


See also
--------

Explanation:

- :ref:`exp_in_project_sdk`
- :ref:`exp_sdk_definition`
- :ref:`exp_workshop_definition`
<shellId: 5 completed with exit code 0>
```

</details>


---

<sub>25s</sub>

### `bash`

**Grep structure.md for workshop**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "workshop" .dogen/context/structure.md 2>/dev/null | head -60

<details>
<summary>61 lines</summary>

```
3:**Repo:** `workshop`
15:This document maps the **documentation architecture** of `workshop`:
39:| `docs/how-to/customize-workshops/add-mounts.rst` | how-to | 8,218 |
40:| `docs/how-to/customize-workshops/move-projects.rst` | how-to | 3,624 |
41:| `docs/how-to/customize-workshops/forward-ports.rst` | how-to | 6,439 |
42:| `docs/how-to/customize-workshops/add-actions.rst` | how-to | 3,834 |
43:| `docs/how-to/customize-workshops/use-multiple-workshops.rst` | how-to | 8,644 |
44:| `docs/how-to/customize-workshops/index.rst` | how-to | 696 |
45:| `docs/how-to/develop-with-workshops/connect-vscode.rst` | how-to | 1,647 |
46:| `docs/how-to/develop-with-workshops/run-github-actions-locally.rst` | how-to | 10,093 |
47:| `docs/how-to/develop-with-workshops/manage-python-environments.rst` | how-to | 6,188 |
48:| `docs/how-to/develop-with-workshops/run-jetbrains-gateway.rst` | how-to | 4,258 |
49:| `docs/how-to/develop-with-workshops/run-workshops-in-github-actions.rst` | how-to | 6,071 |
50:| `docs/how-to/develop-with-workshops/use-workshops-with-ai-agents.rst` | how-to | 12,497 |
51:| `docs/how-to/develop-with-workshops/index.rst` | how-to | 1,319 |
52:| `docs/how-to/develop-with-workshops/use-git.rst` | how-to | 4,958 |
53:| `docs/how-to/develop-with-workshops/run-jupyterlab-in-browser.rst` | how-to | 1,317 |
54:| `docs/how-to/fix-workshops/fix-installation.rst` | how-to | 2,954 |
55:| `docs/how-to/fix-workshops/debug-issues.rst` | how-to | 8,015 |
56:| `docs/how-to/fix-workshops/purge.rst` | how-to | 5,658 |
57:| `docs/how-to/fix-workshops/resolve-plug-conflicts.rst` | how-to | 3,015 |
58:| `docs/how-to/fix-workshops/index.rst` | how-to | 1,066 |
65:| `docs/reference/workshop-status.rst` | reference | 2,618 |
66:| `docs/reference/workshops.rst` | reference | 8,005 |
71:| `docs/reference/cli/workshop-launch.rst` | reference | 2,064 |
73:| `docs/reference/cli/workshop-run.rst` | reference | 3,170 |
74:| `docs/reference/cli/workshop-sketches.rst` | reference | 766 |
77:| `docs/reference/cli/workshop-stop.rst` | reference | 1,096 |
79:| `docs/reference/cli/workshop-remove.rst` | reference | 1,068 |
81:| `docs/reference/cli/workshopctl.rst` | reference | 1,776 |
82:| `docs/reference/cli/workshop-start.rst` | reference | 1,091 |
83:| `docs/reference/cli/workshop-remount.rst` | reference | 1,543 |
84:| `docs/reference/cli/workshop-refresh.rst` | reference | 2,637 |
85:| `docs/reference/cli/workshop-init.rst` | reference | 1,289 |
87:| `docs/reference/cli/workshop-actions.rst` | reference | 682 |
89:| `docs/reference/cli/workshop-okay.rst` | reference | 565 |
91:| `docs/reference/cli/workshop-exec.rst` | reference | 3,018 |
92:| `docs/reference/cli/workshop-info.rst` | reference | 1,115 |
93:| `docs/reference/cli/workshop-connections.rst` | reference | 1,235 |
95:| `docs/reference/cli/workshop-changes.rst` | reference | 1,308 |
96:| `docs/reference/cli/workshop-tasks.rst` | reference | 1,162 |
98:| `docs/reference/cli/workshop-sketch-sdk.rst` | reference | 2,016 |
99:| `docs/reference/cli/workshop-warnings.rst` | reference | 1,244 |
100:| `docs/reference/cli/workshop.rst` | reference | 36,750 |
107:| `docs/reference/cli/workshop-shell.rst` | reference | 1,040 |
108:| `docs/reference/cli/workshop-restore.rst` | reference | 1,534 |
110:| `docs/reference/cli/workshop-list.rst` | reference | 1,182 |
111:| `docs/reference/cli/workshop-disconnect.rst` | reference | 1,900 |
117:| `docs/reference/cli/workshop-connect.rst` | reference | 1,845 |
120:| `docs/reference/definition-files/workshop-definition.rst` | reference | 18,398 |
141:| `docs/explanation/workshops/changes-tasks.rst` | explanation | 1,779 |
142:| `docs/explanation/workshops/projects.rst` | explanation | 2,858 |
143:| `docs/explanation/workshops/concepts.rst` | explanation | 18,705 |
144:| `docs/explanation/workshops/index.rst` | explanation | 849 |
145:| `docs/explanation/workshops/multi-workshop-patterns.rst` | explanation | 8,441 |
180:| `cmd/internal/doctemplates/workshop.rst` | supplementary | 2,123 |
194:  - `docs/explanation/workshops/index.rst`
195:  - `docs/how-to/customize-workshops/index.rst`
197:  - `docs/how-to/develop-with-workshops/index.rst`
198:  - `docs/how-to/fix-workshops/index.rst`
<shellId: 6 completed with exit code 0>
```

</details>


---

<sub>25s</sub>

### `bash`

**Peek at sdk-definition.rst for convention**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat docs/reference/definition-files/sdk-definition.rst | head -40

<details>
<summary>30 lines</summary>

```
.. _ref_sdk_definition:

.. meta::
   :description: Reference for the runtime sdk.yaml definition file. Covers
                 filename conventions, top-level fields, interface attributes,
                 the JSON Schema, and worked examples.

SDK definition
==============

.. @artefact SDK definition

The :file:`sdk.yaml` file is the *runtime* SDK definition:
|ws_markup| reads it when it installs an SDK in a workshop.
For Store SDKs and SDKs from :command:`sdkcraft try`,
this file is produced by |sdk_markup| from :file:`sdkcraft.yaml`
(see :ref:`ref_sdkcraft_definition`).
For sketch SDKs and in-project SDKs,
you author :file:`sdk.yaml` directly:
sketch SDKs through :command:`workshop sketch-sdk`,
in-project SDKs by hand under :file:`.workshop/`.


Filename and location
---------------------

.. @artefact SDK definition

- Store SDKs and SDKs from :command:`sdkcraft try` ship :file:`sdk.yaml`
  inside their packed contents at :file:`meta/sdk.yaml`.

- In-project SDKs use
  :file:`.workshop/<NAME>/sdk.yaml` or :file:`.workshop/<NAME>/meta/sdk.yaml`,
  relative to the project directory.
  Their hook scripts live next to the definition,
  under :file:`.workshop/<NAME>/hooks/`.

- Sketch SDK definitions live in the per-workshop data directory:
  :file:`~/.local/share/workshop/id/<PROJECT-ID>/<WORKSHOP>/sdk/sketch/current/sdk.yaml`.
<shellId: 7 completed with exit code 0>
```

</details>


---

<sub>38s</sub>

### `bash`

**Check dogen status for existing units**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen status 2>&1 | head -30

```
No units. Declare one with `dogen unit new`.
<shellId: 8 completed with exit code 0>
```


---

<sub>38s</sub>

### `bash`

**Peek at existing workshop-definition.rst**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && head -60 docs/reference/definition-files/workshop-definition.rst

```
head: cannot open 'docs/reference/definition-files/workshop-definition.rst' for reading: No such file or directory
<shellId: 9 completed with exit code 1>
```


---

<sub>38s</sub>

### `bash`

**Grep code-to-docs-map for workshop yaml**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "workshop" .dogen/context/code-to-docs-map.md 2>/dev/null | grep -i "yaml\|definition\|workshop\.yaml" | head -30

<details>
<summary>31 lines</summary>

```
2203:- `MarshalYAML.<unknown>` class · internal/workshop/workshop_file.go:158 [0.56]
2204:- `UnmarshalYAML.<unknown>` class · internal/workshop/workshop_file.go:163 [0.56]
3070:- `MarshalYAML` method · internal/workshop/workshop_file.go:137 [0.59]
3250:- `MarshalYAML` method · internal/workshop/workshop_file.go:215 [0.60]
3318:- `RemoveNodes` function · cmd/workshop/yaml.go:35 [0.50]
3323:- `<unknown>` class · cmd/workshop/yaml.go:45 [0.51]
3332:- `TestRemoveNodesAliases` method · cmd/workshop/yaml_test.go:335 [0.52]
3337:- `UnmarshalYAML` method · cmd/workshop/yaml.go:29 [0.52]
3346:- `TestRemoveNodesWithComments` method · cmd/workshop/yaml_test.go:213 [0.53]
3368:- `TestRemoveNodesMapping` method · cmd/workshop/yaml_test.go:126 [0.54]
3377:- `unmarshalAndDecode` function · cmd/workshop/yaml_test.go:106 [0.55]
3382:- `TestRemoveNodesMultiple` method · cmd/workshop/yaml_test.go:348 [0.55]
3393:- `remove` method · cmd/workshop/yaml.go:49 [0.56]
3398:- `checkRemoveNodes` function · cmd/workshop/yaml_test.go:456 [0.56]
3405:- `contains` function · cmd/workshop/yaml_test.go:113 [0.56]
3411:- `TestRemoveNodesFlowStyle` method · cmd/workshop/yaml_test.go:195 [0.57]
3412:- `<unknown>` class · cmd/workshop/yaml_test.go:25 [0.57]
3414:- `TestRemoveNodesSequence` method · cmd/workshop/yaml_test.go:161 [0.57]
3436:- `TestNodeRefIsUnmarshaler` method · cmd/workshop/yaml_test.go:29 [0.58]
3438:- `TestNodeRefSlice` method · cmd/workshop/yaml_test.go:60 [0.58]
3443:- `TestRemoveNodesMerged` method · cmd/workshop/yaml_test.go:395 [0.58]
3460:- `TestNodeRefNested` method · cmd/workshop/yaml_test.go:73 [0.59]
3470:- `TestNodeRefAlias` method · cmd/workshop/yaml_test.go:48 [0.60]
3774:  - `TestCreateWorkshopNoWorkshopDefinitionFound` method · internal/overlord/workshopstate/handlers_test.go:321 [0.67]
3954:  - `TestInitYamlRoundTrip` method · cmd/workshop/init_test.go:367 [0.71]
3962:  - `TestInitWorkshopYamlExists` method · cmd/workshop/init_test.go:256 [0.68]
3963:  - `TestInitDotWorkshopYamlExists` method · cmd/workshop/init_test.go:268 [0.68]
4071:  - `TestCreateWorkshopNoWorkshopDefinitionFound` method · internal/overlord/workshopstate/handlers_test.go:321 [0.68]
4081:  - `TestRefreshSystemDefinitionExtended` method · internal/daemon/api_workshops_test.go:3105 [0.67]
4251:  - `TestInitYamlRoundTrip` method · cmd/workshop/init_test.go:367 [0.69]
<shellId: 10 completed with exit code 0>
```

</details>


---

<sub>2m 12s</sub>

### Info

MCP Servers reloaded: 3 servers connected

---

<sub>2m 14s</sub>

### User

go on

---

<sub>2m 16s</sub>

### Reasoning

*The user wants me to continue with the dogen-plan skill. Let me review what I've found so far:

1. The docs tree uses `.rst` files in `docs/reference/definition-files/`
2. The toctree in `docs/reference/definition-files/index.rst` already has a `workshop-definition` slot (but the file doesn't exist yet - `workshop-definition.rst` is listed in the toctree but the file is missing!)
3. There are existing sibling pages: `sdk-definition.rst`, `sdkcraft-definition.rst` - both `.rst` files
4. The user mentioned "workshop yaml reference" - this maps to the missing `workshop-definition.rst` page
5. The toctree slot is already reserved for `workshop-definition`, so I just need to create the file at `reference/definition-files/workshop-definition.rst` with the workshop YAML schema documentation
6. The source code reference would be `internal/workshop/workshop_file.go`

Now I'm ready to start the Socratic intake process to understand what the user needs for this documentation page.*

---

<sub>2m 25s</sub>

### `bash`

**Check workshop_file.go source**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && ls internal/workshop/workshop_file.go 2>/dev/null && head -80 internal/workshop/workshop_file.go

<details>
<summary>66 lines</summary>

```
internal/workshop/workshop_file.go
// Copyright (c) 2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License version 3 as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package workshop

import (
	"cmp"
	"errors"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/canonical/workshop/internal/sdk"
)

const MAX_WORKSHOP_NAME_LENGTH = 40

var (
	SupportedBases = sdk.AllowedBases

	workshopName = regexp.MustCompile(`^[a-z](?:-?[a-z0-9])*$`)
	actionName   = workshopName

	Directory = ".workshop"
	Filenames = []string{"workshop.yaml", ".workshop.yaml"}
)

func filename(name string) string {
	return fmt.Sprintf("%s.yaml", name)
}

func Filepath(project, name string) string {
	return filepath.Join(project, Directory, filename(name))
}

func ProjectSdkPath(project, name string) string {
	return filepath.Join(project, Directory, name)
}

type PlugOrBind struct {
	Bind *PlugRef
	Plug any
}

func (p *PlugOrBind) UnmarshalYAML(value *yaml.Node) error {
	if value.Kind != yaml.MappingNode {
		p.Bind = nil
		return value.Decode(&p.Plug)
	}

	var plug struct {
		Bind       *PlugRef       `yaml:"bind"`
		Attributes map[string]any `yaml:",inline"`
	}
	if err := value.Decode(&plug); err != nil {
		return err
	}

	if plug.Bind == nil {
		*p = PlugOrBind{Plug: plug.Attributes}
		return nil
	}
<shellId: 0 completed with exit code 0>
```

</details>


---

<sub>2m 25s</sub>

### `bash`

**Find workshop yaml source files**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && find . -name "workshop_file.go" -o -name "workshop*.go" | grep -v test | grep -v "_test" | head -20

<details>
<summary>6 lines</summary>

```
./internal/workshop/workshop_file.go
./internal/workshop/workshop_dirs.go
./internal/workshop/workshop.go
./client/workshopctl.go
./client/workshop.go
<shellId: 1 completed with exit code 0>
```

</details>


---

<sub>2m 27s</sub>

### Reasoning

*Good. Now I have a clear picture:

1. The toctree slot `workshop-definition` already exists in `docs/reference/definition-files/index.rst` but the file is missing
2. The format is `.rst` (matching siblings `sdk-definition.rst`, `sdkcraft-definition.rst`)
3. The primary source is `internal/workshop/workshop_file.go`
4. The target would be `reference/definition-files/workshop-definition.rst`

The user said "workshop yaml reference" - this is clearly a reference page request. I should now start the Socratic intake with the "Why" question.
The toctree slot is already reserved and waiting for this file, which is the strongest signal for where it belongs. Let me begin the intake by asking what problem this page solves for readers.*

---

<sub>2m 31s</sub>

### Copilot

Good — I have my grounding. The docs tree has a **waiting toctree slot** at `docs/reference/definition-files/workshop-definition` (listed in the index but the file doesn't exist), with sibling pages `sdk-definition.rst` and `sdkcraft-definition.rst` both in reStructuredText. The primary source entry point is `internal/workshop/workshop_file.go`.

Time to open the intake — one question at a time.

---

<sub>3m 8s</sub>

### `ask_user`

**Looking at what you want to document — the `workshop.yaml...**

<details>
<summary>Arguments</summary>

```json
{
  "question": "Looking at what you want to document — the `workshop.yaml` reference — what problem does this page solve for its reader?"
}
```

</details>

```
User responded:  i need exhaustive referfernce for people manually edioting workshops of their authoring and arriving from elsewhere; a self contained referrnce enabling menchanical fixes and comprehension
```


---

<sub>3m 11s</sub>

### Reasoning

*The reader's problem is: they're manually editing `workshop.yaml` (either authoring a new one or arriving from another tool/context), and they need an exhaustive, self-contained reference so they can make precise field edits without having to go elsewhere. The page needs to cover every field, constraint, default, and behavior in a way that allows both mechanical fixes and genuine comprehension.

Now I need to draw out the audience more specifically.*

---

<sub>3m 13s</sub>

### Copilot

So the reader is mid-task — editing a `workshop.yaml` by hand — and needs a single authoritative page they can consult to get any field right, without chasing other docs. Got it.

---

<sub>3m 20s</sub>

### `ask_user`

**Who is the primary reader: someone authoring a workshop.y...**

<details>
<summary>Arguments</summary>

```json
{
  "question": "Who is the primary reader: someone authoring a workshop.yaml for the first time, an experienced user arriving from a different tool or project who just needs to check field names and constraints, or both equally?",
  "choices": [
    "Both equally — the page must serve first-time authors AND experienced users arriving from elsewhere (Recommended)",
    "Primarily first-time authors",
    "Primarily experienced users doing spot-checks"
  ]
}
```

</details>

```
User selected: Both equally — the page must serve first-time authors AND experienced users arriving from elsewhere (Recommended)
```


---

<sub>3m 22s</sub>

### Reasoning

*Now I have the judgment fields:
- **Problem**: Reader is manually editing `workshop.yaml`, needs an exhaustive self-contained reference for mechanical fixes and comprehension
- **Audience**: Both first-time authors AND experienced users arriving from elsewhere

Now I need to collect the mechanical fields. The Diataxis direction is clearly **reference** — which is the only type dogen supports this cycle.

Let me confirm:
1. **Unit ID**: I'll propose `workshop-definition` (matching the toctree slot)
2. **Title**: I'll propose "Workshop definition" (matching the sibling `sdk-definition.rst` which has title "SDK definition")
3. **Sources**: I'll pull from `internal/workshop/workshop_file.go` as the primary source, and check the example YAML files and any schema definitions for additional context
4. **Target**: `reference/definition-files/workshop-definition.rst` (waiting toctree slot, `.rst` format matching siblings)*

---

<sub>3m 29s</sub>

### Copilot

Great — a page that serves both audiences with exhaustive, self-contained coverage. This is clearly a **reference** page, which is the direction dogen drafts well this cycle. ✓

Now for the mechanical fields — I'll propose a default for each and you confirm or override.

The toctree in `docs/reference/definition-files/index.rst` already has a waiting slot for `workshop-definition`, and the siblings are `sdk-definition.rst` / `sdkcraft-definition.rst`. That fixes the target exactly.

---

<sub>3m 51s</sub>

### `ask_user`

**I'd propose the unit ID **`workshop-definition`** — it ma...**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "workshop-definition (Recommended — matches the waiting toctree slot)",
    "workshop-yaml-reference",
    "workshop-yaml"
  ],
  "question": "I'd propose the unit ID **`workshop-definition`** — it matches the waiting toctree slot and keeps it consistent with the sibling `sdk-definition` unit. Does that work?"
}
```

</details>

```
User selected: workshop-definition (Recommended — matches the waiting toctree slot)
```


---

<sub>4m 1s</sub>

### `ask_user`

**For the page title, I'd propose **"Workshop definition"**...**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "Workshop definition (Recommended — matches sibling page convention)",
    "workshop.yaml reference",
    "Workshop YAML reference"
  ],
  "question": "For the page title, I'd propose **\"Workshop definition\"** — it matches the pattern of the sibling \"SDK definition\" page. Does that work, or would you prefer something different?"
}
```

</details>

```
User selected: Workshop definition (Recommended — matches sibling page convention)
```


---

<sub>4m 3s</sub>

### Reasoning

*Now I need to collect the sources. The primary source is `internal/workshop/workshop_file.go`. Let me also look at what other relevant files might be starting points:
- `docs/examples/workshop-*.yaml` - example files
- `docs/reference/definition-files/schema.json` - the schema
- `docs/reference/definition-files/sdkcraft-definition.rst` - sibling for format reference

Let me verify what files exist and propose sources to the user.*

---

<sub>4m 5s</sub>

### Copilot

Now let me verify candidate source paths before proposing them.

---

<sub>4m 7s</sub>

### `bash`

**Verify candidate source paths**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && ls docs/examples/workshop-*.yaml docs/reference/definition-files/schema.json docs/reference/definition-files/schema-sdk.json 2>&1 && wc -l internal/workshop/workshop_file.go

<details>
<summary>8 lines</summary>

```
docs/examples/workshop-digits-cuda.yaml
docs/examples/workshop-go-dev.yaml
docs/examples/workshop-golang.yaml
docs/examples/workshop-try-go.yaml
docs/reference/definition-files/schema.json
docs/reference/definition-files/schema-sdk.json
431 internal/workshop/workshop_file.go
<shellId: 2 completed with exit code 0>
```

</details>


---

<sub>4m 10s</sub>

### `bash`

**Check for workshop-specific schema file**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && ls docs/reference/definition-files/schema*.json

```
docs/reference/definition-files/schema.json
docs/reference/definition-files/schema-sdkcraft.json
docs/reference/definition-files/schema-sdk.json
<shellId: 3 completed with exit code 0>
```


---

<sub>4m 13s</sub>

### Reasoning

*Good. The schema files are:
- `docs/reference/definition-files/schema.json` - likely the workshop schema
- `docs/reference/definition-files/schema-sdk.json` - SDK schema
- `docs/reference/definition-files/schema-sdkcraft.json` - sdkcraft schema

Let me verify schema.json is the workshop one.*

---

<sub>4m 14s</sub>

### `bash`

**Check what schema.json covers**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && head -5 docs/reference/definition-files/schema.json

<details>
<summary>6 lines</summary>

```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://canonical.com/workshop.yaml",
  "title": "Workshop",
  "description": "Workshop definition.",
<shellId: 4 completed with exit code 0>
```

</details>


---

<sub>4m 16s</sub>

### Reasoning

*`schema.json` is indeed the workshop.yaml schema. So the sources I'd propose are:
1. `internal/workshop/workshop_file.go` - the Go struct definitions (primary)
2. `docs/reference/definition-files/schema.json` - the JSON schema for workshop.yaml
3. `docs/examples/workshop-golang.yaml` - a representative example

Let me now ask the user about sources.*

---

<sub>4m 18s</sub>

### Copilot

All three paths confirmed. I'd propose these starting-point sources for the drafter:

- `internal/workshop/workshop_file.go` — Go structs defining every field, constraint, and default (431 lines)
- `docs/reference/definition-files/schema.json` — the authoritative JSON Schema for `workshop.yaml`
- `docs/examples/workshop-golang.yaml` — a representative worked example

---

<sub>4m 31s</sub>

### `ask_user`

**Should I use all three of those as starting-point sources...**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "Yes, use all three (Recommended)",
    "Just the Go source and schema (skip example)",
    "Add more example files too"
  ],
  "question": "Should I use all three of those as starting-point sources, or would you adjust the set?"
}
```

</details>

```
User selected: Yes, use all three (Recommended)
```


---

<sub>4m 33s</sub>

### Reasoning

*Now I have all the fields. Let me now move to step 5 — shape a reader-facing outline. Let me look at the reference-intake.md for guidance, and also look at the sdk-definition.rst structure to understand what a good sibling reference page looks like.*

---

<sub>4m 34s</sub>

### Copilot

Good. Now let me read the reference-intake guidance and skim the sibling page structure before proposing an outline.

---

<sub>4m 37s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-plan/references/reference-intake.md.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-plan/references/reference-intake.md

<details>
<summary>37 lines</summary>

```
Load this file at workflow step 4 (Confirm the reference direction).

# Reference-direction intake

dogen drafts one Diataxis direction well this cycle: **reference**. This file holds
the reference-shape checklist the intake confirms and the exact hard-block wording
for the other three directions (D-07).

## What the reference direction is for

Reference documentation is **information-oriented**: it describes the machinery
accurately and completely so a reader who already knows what they want can look up
the facts. It is neutral and austere — it states what is, not how to learn it or how
to accomplish a task.

Good reference-shaped units for dogen:

- a directive / option / field reference (each item, its type, default, and bounds),
- a configuration-key reference,
- an API surface, CLI command, or schema reference,
- an enumerated list of states, error codes, or flags.

Confirm the TA's unit fits this shape before declaring. If the reader's real need is
"teach me" (tutorial), "help me do X" (how-to), or "help me understand why"
(explanation), it is NOT a reference unit — hard-block below.

## The three non-reference directions (hard-block this cycle)

- **tutorial** — learning-oriented, a guided lesson.
- **how-to** — task-oriented, steps to reach a goal.
- **explanation** — understanding-oriented, background and rationale.

Declaring any of these would set up a draft that misleads or fails, because dogen
only drafts the reference direction well right now.

## Hard-block wording

When the TA steers toward a non-reference type, use `AskUserQuestion` with wording of
this shape, then STOP before declaring:

> Right now dogen only drafts the **reference** Diataxis direction well — the neutral,
> information-oriented "look it up" shape. What you're describing reads more like a
> {tutorial | how-to | explanation}, which dogen doesn't draft reliably this cycle.
>
> I can (a) note the intended type so a future cycle can pick it up, and stop here, or
> (b) reframe this as a reference unit if there's a genuine reference surface to
> document. Which would you like?

Do not declare a unit with `--intent tutorial`, `--intent how-to`, or
`--intent explanation`. The only intent this skill passes to `dogen unit new` is
`--intent reference`.
```

</details>


---

<sub>4m 37s</sub>

### `bash`

**Skim sdk-definition.rst section headings**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "^[=-]\+\|^\.\. " docs/reference/definition-files/sdk-definition.rst | head -60

<details>
<summary>38 lines</summary>

```
1:.. _ref_sdk_definition:
3:.. meta::
9:==============
11:.. @artefact SDK definition
25:---------------------
27:.. @artefact SDK definition
29:- Store SDKs and SDKs from :command:`sdkcraft try` ship :file:`sdk.yaml`
32:- In-project SDKs use
38:- Sketch SDK definitions live in the per-workshop data directory:
48:----------------
50:.. list-table::
147:.. note::
159:.. _ref_sdk_definition_interfaces:
162:----------
168:.. include:: _interfaces/camera.rst
170:.. include:: _interfaces/custom-device.rst
172:.. include:: _interfaces/desktop.rst
174:.. include:: _interfaces/gpu.rst
176:.. include:: _interfaces/mount.rst
178:.. include:: _interfaces/ssh-agent.rst
180:.. include:: _interfaces/tunnel.rst
184:-----------
186:.. @artefact SDK schema
191:.. note::
206:.. dropdown:: SDK definition schema
213:--------
217:.. literalinclude:: ../../examples/sdk-project-cache.yaml
223:.. literalinclude:: ../../examples/sdk-go-runtime.yaml
229:--------
233:- :ref:`exp_in_project_sdk`
234:- :ref:`exp_sdk_concepts`
235:- :ref:`exp_sdk_definition`
236:- :ref:`exp_system_sdk`
240:- :ref:`ref_sdk_internals`
241:- :ref:`ref_sdkcraft_definition`
242:- :ref:`ref_workshop_definition`
246:- :ref:`tut_sketch_sdks`
<shellId: 5 completed with exit code 0>
```

</details>


---

<sub>4m 39s</sub>

### Reasoning

*Now I have a great picture of the sibling page structure:
1. A ref label at top (e.g., `.. _ref_workshop_definition:`)
2. Meta description
3. A title
4. Artefact annotation
5. Filename and location section
6. Top-level fields table (a list-table)
7. Interface sub-section with includes
8. Schema section
9. Examples section
10. See also section

For the workshop.yaml reference, I should propose a similar structure, but in reader-facing terms.

Let me also check the workshop_file.go more fully to understand what fields it has.*

---

<sub>4m 42s</sub>

### `bash`

**List YAML field tags in workshop_file.go**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "yaml:" internal/workshop/workshop_file.go | head -60

<details>
<summary>15 lines</summary>

```
69:		Bind       *PlugRef       `yaml:"bind"`
70:		Attributes map[string]any `yaml:",inline"`
142:	Name    string                `yaml:"name"`
143:	Channel string                `yaml:"channel,omitempty"`
144:	Source  sdk.Source            `yaml:"source,omitempty"`
145:	Plugs   map[string]PlugOrBind `yaml:"plugs,omitempty"`
146:	Slots   map[string]any        `yaml:"slots,omitempty"`
192:	PlugRef PlugRef `yaml:"plug"`
193:	SlotRef SlotRef `yaml:"slot"`
199:	Name        string            `yaml:"name"`
200:	Base        string            `yaml:"base"`
201:	Sdks        []SdkRecord       `yaml:"sdks,omitempty"`
202:	Connections []Connection      `yaml:"connections,omitempty"`
203:	Actions     map[string]Action `yaml:"actions,omitempty"`
<shellId: 6 completed with exit code 0>
```

</details>


---

<sub>4m 45s</sub>

### Reasoning

*Now I have a good picture. The `workshop.yaml` has these top-level fields:
- `name` (string)
- `base` (string)
- `sdks` (list of SdkRecord)
- `connections` (list of Connection)
- `actions` (map of Action)

And for SdkRecord:
- `name` (string)
- `channel` (string, optional)
- `source` (sdk.Source, optional)
- `plugs` (map of PlugOrBind, optional)
- `slots` (map of any, optional)
I'm sketching out a reference page structure that mirrors the SDK definition format, starting with where the file lives and how it's discovered, then laying out all the top-level fields in a reference table, followed by detailed sections on SDK entries, connection syntax, and action definitions.*

---

<sub>4m 50s</sub>

### Copilot

I have everything I need. Here's the picture I'll reflect back, then propose an outline.

---

**Summary so far:**
- **Problem**: Reader is editing `workshop.yaml` by hand and needs one complete, self-contained page to look up any field, constraint, or default without going elsewhere.
- **Audience**: Both first-time authors and experienced users arriving from other tools.
- **Unit id**: `workshop-definition`
- **Title**: Workshop definition
- **Diataxis**: reference ✓
- **Target**: `reference/definition-files/workshop-definition.rst` (waiting toctree slot, `.rst` format matching siblings)
- **Sources**: `internal/workshop/workshop_file.go`, `docs/reference/definition-files/schema.json`, `docs/examples/workshop-golang.yaml`

---

Now, here is the outline I propose — phrased in reader terms, with code entities appearing only as source pointers:

---

**## Intent & scope**

A complete field-by-field reference for `workshop.yaml` — the file Workshop users author to define a workshop. Covers every accepted field, its type, whether it is required or optional, its default, and any constraint (valid name format, accepted base values). Serves both as a first-read introduction to the file's structure and as a quick-lookup reference for experienced users. Does not explain when or why to use a given feature; for that, see the companion explanation pages.

**## Outline / acceptance**

- **Filename and location** — where `workshop.yaml` lives, how Workshop searches for it, and alternate filename (`.workshop.yaml`)
- **Top-level fields** — table: `name`, `base`, `sdks`, `connections`, `actions`; each row gives type, required/optional, default, and a one-line description
- **Name and base constraints** — valid name format (character rules, length limit), accepted `base` values
- **SDK entries** — sub-fields of each entry in `sdks`: the SDK name to install, optional `channel`, optional `source`, and the `plugs`/`slots` maps; includes the `bind:` shorthand syntax
- **Connections** — how to wire a plug on one SDK to a slot on another; the `plug:` / `slot:` reference syntax
- **Actions** — the fields available in each named action entry: command, environment variables, working directory, user/group; name constraints
- **JSON Schema** — link to `schema.json` and embed or link the dropdown (matching sibling page pattern)
- **Examples** — one or more annotated `workshop.yaml` examples drawn from `docs/examples/`
- **See also** — links to the concepts explanation, the `workshop init` CLI reference, and the SDK definition reference

---

---

<sub>5m 20s</sub>

### `ask_user`

**Does this outline and the full picture above match what y...**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "Yes, looks good — proceed to declare",
    "Adjust the outline before declaring"
  ],
  "question": "Does this outline and the full picture above match what you want declared?"
}
```

</details>

```
User selected: Yes, looks good — proceed to declare
```


---

<sub>5m 22s</sub>

### Reasoning

*Now I need to run the delegating call sequence:
1. `dogen unit new "workshop-definition" --intent reference --audience "..." --title "Workshop definition" --source "..." --target "..." --notes "..." --json`
2. `dogen unit edit "workshop-definition" --body-file - --json` with the outline piped in
3. `dogen signoff "workshop-definition" --json`

Let me now construct the calls.

Synthesized steering note: "The page must give workshop users — both first-time authors and experienced users arriving from other tools — everything they need to get any field in workshop.yaml right without consulting another page; it should cover every field's type, whether it is required, its default, and its constraints (name format, accepted bases, valid action names), structured so it works both as a first-read introduction and a quick-lookup reference."
Executing the command sequence now.*

---

<sub>5m 27s</sub>

### Copilot

Declaring now.

---

<sub>5m 30s</sub>

### `bash`

**dogen unit new for workshop-definition**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen unit new "workshop-definition" \
  --intent reference \
  --audience "Workshop users who author workshop.yaml by hand — both first-time authors and experienced users arriving from other tools or projects" \
  --title "Workshop definition" \
  --source "internal/workshop/workshop_file.go" \
  --source "docs/reference/definition-files/schema.json" \
  --source "docs/examples/workshop-golang.yaml" \
  --target "reference/definition-files/workshop-definition.rst" \
  --notes "The page must give workshop users everything they need to get any field in workshop.yaml right without consulting another page; it should cover every field's type, whether it is required, its default, and its constraints (name format, accepted bases, valid action names), structured so it works both as a first-read introduction and a quick-lookup reference for experienced users arriving from elsewhere." \
  --json 2>&1

```
git: committed b36d632 — dogen(workshop-definition): declared — Workshop definition
{"unit": "workshop-definition", "provider": null, "draft_path": "/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/units/workshop-definition/unit.md", "progress": null, "reason": null, "commit": "b36d632fb4eeb97b77c5e61ca26460ca6d065bec"}
<shellId: 7 completed with exit code 0>
```


---

<sub>5m 37s</sub>

### `bash`

**dogen unit edit with approved outline**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen unit edit "workshop-definition" --body-file - --json <<'PLAN_BODY'
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
PLAN_BODY

```
git: committed 4f7b67d — dogen(workshop-definition): edited — plan amended
{"unit": "workshop-definition", "provider": null, "draft_path": "/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/units/workshop-definition/unit.md", "progress": null, "reason": null, "commit": "4f7b67d0dd7672c1265eccaed87f9481cb2d9b84"}
<shellId: 8 completed with exit code 0>
```


---

<sub>5m 39s</sub>

### `bash`

**dogen signoff workshop-definition**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen signoff "workshop-definition" --json 2>&1

```
git: committed 25d76b7 — dogen(workshop-definition): signed-off — plan signed off by Artem Konev
{"unit": "workshop-definition", "provider": null, "draft_path": null, "progress": null, "reason": null, "commit": "25d76b730f865d52e824a862bab6c96103ce01a0"}
<shellId: 9 completed with exit code 0>
```


---

<sub>5m 42s</sub>

### Copilot

All three transitions landed cleanly:

- `b36d632` — declared
- `4f7b67d` — plan amended (outline persisted)
- `25d76b7` — **signed off** ✓

The unit `workshop-definition` is declared and its plan is frozen. The target is `reference/definition-files/workshop-definition.rst` (`.rst`, matching the waiting toctree slot and sibling pages).

**Next step:** invoke the `dogen-write` skill to draft the page.

---

<sub>8m 22s</sub>

### User

/dogen-write

---

<sub>8m 25s</sub>

### Reasoning

*The user wants me to invoke the "dogen-write" skill.*

---

<sub>8m 26s</sub>

### `skill`

**dogen-write**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "dogen-write"
}
```

</details>

```
Skill "dogen-write" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>8m 28s</sub>

### Reasoning

*Let me follow the skill's instructions step by step.

1. First, read the unit state with `dogen unit show "workshop-definition" --json --latest`
2. Run the provider probe `dogen draft "workshop-definition" --resolve-only --json`
3. Load `references/provider-branch.md`
4. Branch on the provider

Let me do steps 1 and 2 in parallel, and also load the provider-branch.md reference.*

---

<sub>8m 33s</sub>

### `bash`

**Read unit state**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen unit show "workshop-definition" --json --latest 2>&1

```
{"unit": {"schema_version": 1, "unit_id": "workshop-definition", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "title": "Workshop definition", "sources": [{"path": "internal/workshop/workshop_file.go", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/reference/definition-files/schema.json", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/examples/workshop-golang.yaml", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}], "sphinx_target": "reference/definition-files/workshop-definition.rst", "extra_targets": [], "steering_notes": "The page must give workshop users everything they need to get any field in workshop.yaml right without consulting another page; it should cover every field's type, whether it is required, its default, and its constraints (name format, accepted bases, valid action names), structured so it works both as a first-read introduction and a quick-lookup reference for experienced users arriving from elsewhere."}, "format": "rst", "progress": "pending", "signoff": {"author": "Artem Konev", "at": "2026-07-04T18:12:07.674646+00:00", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "plan_hash": "fe06b324249c9d5f9da3e9fa0aefed5ab5e45814fbe5b0a1dea423c0af0e3ece", "commit": "4f7b67d0dd7672c1265eccaed87f9481cb2d9b84"}, "steering": [], "generations": [], "generations_count": 0, "reviewer_edits": []}
<shellId: 10 completed with exit code 0>
```


---

<sub>8m 33s</sub>

### `bash`

**Probe provider**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen draft "workshop-definition" --resolve-only --json 2>&1

```
{"unit": "workshop-definition", "provider": "host-harness", "draft_path": null, "progress": null, "reason": null}
<shellId: 11 completed with exit code 0>
```


---

<sub>8m 33s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-write/references/provider-branch.md.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-write/references/provider-branch.md

<details>
<summary>170 lines</summary>

`````
Load this file at workflow step 1 (Read the unit state and probe the provider).

# Provider branch + reference-page authoring guidance

Four things this reference holds: the reason-code→branch map dogen-write keys off,
the per-format authoring standards for the passenger branch (MyST and rST, v1.2),
the stance contract (v1), and the context-report shape (v1). The SKILL.md keeps the
decision logic; this file holds the relocated detail.

## The resolve-only branch

Run the zero-side-effect probe, then branch on the reported provider name (D-08):

```bash
PROVIDER=$(dogen draft "$UNIT" --resolve-only --json \
  | python -c "import sys, json; print(json.load(sys.stdin)['provider'])")

case "$PROVIDER" in
  copilot|mock)
    # DRIVER: the provider generates in-process behind its bounded READONLY
    # toolset and observes its own reads. Invoke and report — author nothing,
    # Write nothing. (A multi-file unit refuses here with
    # multi_target_unsupported — route through the passenger.)
    dogen draft "$UNIT" --json
    ;;
  host-harness)
    # PASSENGER: the host authors the page(s) in the unit's format (declared
    # sources as starting points, free navigation beyond them), Writes the
    # handoff + the context report, then records everything.
    # Single-page unit — handoff carries the target's own extension:
    EXT="${TARGET##*.}"                 # from unit show --json .unit.sphinx_target
    HANDOFF=".dogen/staging/$UNIT/handoff.$EXT"
    REPORT=".dogen/staging/$UNIT/report.yaml"
    dogen draft "$UNIT" --draft-file "$HANDOFF" --report "$REPORT" \
      --provider host-harness --model "$HOST_MODEL" --json   # D-12
    # Multi-file unit — stage handoff/<target-relpath> for EVERY page, then:
    # dogen draft "$UNIT" --draft-dir ".dogen/staging/$UNIT/handoff" \
    #   --report "$REPORT" --provider host-harness --model "$HOST_MODEL" --json
    ;;
esac
```

The resolved name is the ONLY branch signal — never probe the environment yourself.
Selection is explicit in v1 (flag > `DOGEN_PROVIDER` env > repo config >
`host-harness`); there is no `auto` and no silent fallback.

## Reason-code → plain-language TA guidance

Map the CLI `reason` codes (from `--json`) to plain language; do not coin new status
words (D-03; the shared vocabulary lives in `../README.md`):

| reason | what to tell the TA | route |
|--------|---------------------|-------|
| `signoff_required` | "This unit hasn't been signed off yet — dogen won't draft without a recorded signoff." | back to dogen-plan |
| `backend_unavailable` | "The Copilot backend can't be reached right now." | retry later, or use host-harness |
| `model_rejected` | "The requested model `<model>` was refused by the backend." | retry without `--model`, or pick another |
| `unit_exists` (not found) | "No unit with that id exists." | check the id / declare via dogen-plan |
| `bad_report` | "The context report failed validation" (unreadable YAML, or a commit stamp that is neither hex nor empty). | fix the report; prose explanations go in an origin's `note` |
| `handoff_incomplete` | "A declared page has no staged file in the handoff directory." | stage every page of the unit's set, then re-record |
| `undeclared_target` | "The handoff stages a file outside the unit's declared target set." | remove the stray file, or amend the plan (`--also-target`) first |
| `multi_target_unsupported` | "This provider drafts a single page; the unit spans several." | run the host-harness passenger branch |

The success object may additionally carry:

- `commit` — the transition commit's hash (also printed as a
  `git: committed <sha7> — …` stderr line). Quote it in the closing summary.
- `stale_plan: true` — the plan changed after its signoff. Surface it; suggest
  re-approving (`dogen signoff --re-sign`, or folding the re-approval into a
  future amendment via `dogen unit edit … --re-sign`).
- `unsteered_redraft: true` — a re-draft ran with no recorded steering or review
  verdict since the last generation; the correction lived only in conversation.
  Surface it and get the correction recorded (`dogen review --verdict fix` /
  `dogen steer --note`) so the audit trail shows what steered the pass.

## The context report (report.yaml — the v1 provenance contract)

Every passenger draft ships a report of what actually grounded it. Shape (validated
by the CLI against `dogen.core.models.ContextReport`):

```yaml
context_origins:            # EVERY file you read while grounding the draft
  - path: internal/workshop/workshop_file.go
    commit: <git rev-parse HEAD>     # one HEAD stamp for the whole session
  - path: tests/main/interface-plug-binding/workshop.yaml
    commit: <same>
  - path: vendor/example/dep.go     # out-of-repo / unpinnable read:
    commit: ""                       # stamp stays honestly empty…
    note: external dependency, pinned by go.sum at v3.0.1   # …prose goes here
tools_used: [Read, Grep, Glob]
gaps:                       # facts you could NOT verify at their origin
  - "per-interface attribute semantics live in the SDK implementations, not read"
gaps_note: ""               # REQUIRED (one line) when gaps is empty — why
                            # nothing was left unverified; never a default
```

Rules: list reads exhaustively (the declared-vs-read gap is audit-relevant, D-37);
stamp `commit` from one `git rev-parse HEAD` run — a stamp is a **hex SHA or
honestly empty** (the CLI refuses prose there with `bad_report`; explanations
belong in the origin's `note`); `gaps` is the stance contract's outlet — anything
that would otherwise become hedged prose goes here instead. An empty `gaps` list
needs a one-line `gaps_note` justification: "nothing unverified" is a claim, not
a default. An empty report is legal but must be true.

## Source policy (v1): starting points, not a boundary

The unit's declared `sources` are the primary grounding and where reading starts —
read them in full. Beyond them, navigate the repo freely wherever a fact's origin
lies: implementations behind a schema, fixtures, sibling pages, the repo's own docs
conventions, and `.dogen/context/` artifacts when present — `doc-style.md` and
`glossary.md` set voice and vocabulary; grep `code-to-docs-map.md` for the code
area at hand (it can be very large) to find the neighbouring documented
concepts. The grounding rule is: **every claim traceable to
something you actually read and recorded** — stronger than any boundary, because it
is auditable. Suggest promoting load-bearing discoveries:
`dogen unit edit <id> --add-source <path>`.

## Stance contract (v1 — governed mirror)

Canonical source: `dogen.core.authoring.STANCE_CONTRACT` — keep this section in
sync; the drift guard binds this file to the anchor sentence.

> Write as the product's reference, never as a researcher describing their evidence.

State what the product accepts, does, and enforces — not what you observed while
reading. Banned register: "observed", "the fixtures show", "every observed use",
"the corpus", "at this level". When a fact cannot be verified from what you have
read, navigate to its origin and verify it there; if it still cannot be verified,
leave it out of the prose and record it as a gap in the context report — confidence
gaps are provenance, not content. The same discipline covers **runtime mechanics**:
how the machinery executes internally (temporary files, interpreter invocations,
internal process flow) is implementation, not interface — describe the behaviour
the reader can rely on, never the mechanism, even in declarative voice. Before
recording, grep your draft for the banned register, for implementation
identifiers, and for runtime-mechanics narration; fix any hit.

## Thin reference-page standards (passenger authoring, per format)

Author for the **reference** Diataxis direction only (dogen drafts no other type
this cycle). **The unit's `format` field decides the markup** (v1.2) — the target
extension IS the format, and it was chosen at plan time to match the page's
siblings. Never write one markup into the other's extension: MyST fences in an
`.rst` file render as literal text, and bare rST directives in a `.md` file do
the same (round 2 paid fix cycles for both directions). For a multi-file unit,
each page follows its own extension's standard.

### MyST (`.md` targets)

- **Directives / roles:** use `colon_fence` for directives — a fenced block opened
  with three colons, e.g.:

  ````
  :::{note}
  Reference note body.
  :::
  ````

- Anchors are `(label)=` lines; cross-references `{ref}`. Field inventories are
  `{list-table}` colon-fences or pipe tables — pick ONE style per page and keep
  headings on one ladder (no mixed setext/ATX).
- Reusing rST snippets (e.g. shared `_interfaces/*.rst` includes) from a MyST
  page requires an `{eval-rst}` fence around the `.. include::` directives.

### reStructuredText (`.rst` targets)

- **Whitespace is load-bearing** — the malformed-output risk rST carries is the
  reason to be strict here: directive bodies indent exactly 3 spaces under the
  directive; a blank line separates the directive line, options, and body.
- **Headings:** underline (no overline) at least as long as the title text; keep
  ONE ladder for the page, matching the siblings' convention (commonly `=`, then
  `-`, then `~`, then `^`); no skipped levels.
- **Directives:** `.. note::`, `.. list-table::` for field inventories,
  `.. literalinclude::` / `.. include::` with paths relative to the page's
  committed location, `.. code-block:: yaml` for reader-authored snippets.
- **Anchors / cross-references:** `.. _label:` targets and `:ref:`label``
  roles; match the sibling pages' label naming convention.

### Both formats

- **Shape:** reference is information-oriented and neutral — describe the machinery
  accurately and completely (each item, its type, default, bounds). State what is;
  do not teach or narrate. One category per page.
- **Show vs. reference (code-in-narrative):** rooting a draft _in_ the code you read
  is not the same as surfacing that code _in_ the narrative.
  - _Default:_ document behaviour — fields, types, defaults, bounds, constraints — in
    prose and tables, and refer to code entities by qualified name (`package.Type`,
    `package.Function`). Do not reproduce their source.
  - _Exception (closed list):_ show a minimal code block only when the reader
    themselves authors or invokes it — a minimal input/config, a public signature or
    CLI/API call, or a short snippet that cannot be stated in prose.
  - _Never show:_ implementation bodies, private internals, or verbatim struct/function
    source lifted from the sources.
  - _Per-block heuristic (verbatim from the canonical constant):_
    Per block, ask: would the reader themselves type, author, or invoke this exact text? If so, a minimal version may be shown; if instead it is how the machinery is implemented internally, reference it by qualified name and never show it.
  - Canonical source: `dogen.core.authoring.REFERENCE_CODE_RUBRIC` — keep this section
    in sync.
- **Grounding:** assert only what you actually read supports. Do not invent
  defaults, bounds, or availability nothing you read confirms.
- **Headings:** a single top-level title, then a clean heading ladder; no skipped
  levels.

This is intentionally thin (D-04): one supported Diataxis type does not yet justify a
shared normative STYLE_GUIDE. dogen-review judges the draft against these same stated
criteria.
`````

</details>


---

<sub>8m 36s</sub>

### Reasoning

*The provider is `host-harness`. I'm in the passenger branch. I need to:

1. Read the declared sources in full
2. Navigate freely to find additional relevant files
3. Author the reference page in reStructuredText (`.rst` format)
4. Write the handoff and context report
5. Record via `dogen draft --draft-file --report`

Let me start reading the declared sources and then expand to sibling pages, examples, etc.

First, let me get the commit hash and then read all the primary sources.*

---

<sub>8m 38s</sub>

### Copilot

Provider is `host-harness` — passenger branch. I'll read all declared sources fully, then navigate freely, before authoring the `.rst` page.

---

<sub>8m 42s</sub>

### `bash`

**Get commit stamp for report**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && git rev-parse HEAD

```
25d76b730f865d52e824a862bab6c96103ce01a0
<shellId: 12 completed with exit code 0>
```


---

<sub>8m 42s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/workshop/workshop_file.go.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/workshop/workshop_file.go

<details>
<summary>363 lines</summary>

```
// Copyright (c) 2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License version 3 as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package workshop

import (
	"cmp"
	"errors"
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"regexp"
	"slices"
	"strings"

	"gopkg.in/yaml.v3"

	"github.com/canonical/workshop/internal/sdk"
)

const MAX_WORKSHOP_NAME_LENGTH = 40

var (
	SupportedBases = sdk.AllowedBases

	workshopName = regexp.MustCompile(`^[a-z](?:-?[a-z0-9])*$`)
	actionName   = workshopName

	Directory = ".workshop"
	Filenames = []string{"workshop.yaml", ".workshop.yaml"}
)

func filename(name string) string {
	return fmt.Sprintf("%s.yaml", name)
}

func Filepath(project, name string) string {
	return filepath.Join(project, Directory, filename(name))
}

func ProjectSdkPath(project, name string) string {
	return filepath.Join(project, Directory, name)
}

type PlugOrBind struct {
	Bind *PlugRef
	Plug any
}

func (p *PlugOrBind) UnmarshalYAML(value *yaml.Node) error {
	if value.Kind != yaml.MappingNode {
		p.Bind = nil
		return value.Decode(&p.Plug)
	}

	var plug struct {
		Bind       *PlugRef       `yaml:"bind"`
		Attributes map[string]any `yaml:",inline"`
	}
	if err := value.Decode(&plug); err != nil {
		return err
	}

	if plug.Bind == nil {
		*p = PlugOrBind{Plug: plug.Attributes}
		return nil
	}

	if len(plug.Attributes) > 0 {
		return fmt.Errorf("plug is bound to %q and must not define other attributes", plug.Bind.String())
	}
	*p = PlugOrBind{Bind: plug.Bind}
	return nil
}

func (p PlugOrBind) MarshalYAML() (any, error) {
	if p.Bind == nil {
		return p.Plug, nil
	}

	if p.Plug != nil {
		return nil, fmt.Errorf("plug is bound to %q and must not define other attributes", p.Bind.String())
	}

	bind, err := p.Bind.MarshalYAML()
	if err != nil {
		return nil, err
	}
	return map[string]any{"bind": bind}, nil
}

type PlugRef struct {
	Sdk  string
	Name string
}

func (p PlugRef) String() string {
	return fmt.Sprintf("%s:%s", p.Sdk, p.Name)
}

type SlotRef = PlugRef

func (b *PlugRef) UnmarshalYAML(value *yaml.Node) error {
	var refStr string
	if err := value.Decode(&refStr); err != nil {
		return err
	}

	parts := strings.Split(refStr, ":")
	if len(parts) != 2 {
		return fmt.Errorf("%q is not a valid plug or slot reference (use <sdk>:<plug or slot>)", refStr)
	}
	if len(parts[0]) == 0 {
		parts[0] = sdk.System.String()
	}
	if err := sdk.ValidateName(parts[0]); err != nil {
		return fmt.Errorf("%q is not a valid plug or slot reference: %w", refStr, err)
	}

	b.Sdk = parts[0]
	b.Name = parts[1]
	return nil
}

func (b PlugRef) MarshalYAML() (any, error) {
	return fmt.Sprintf("%s:%s", b.Sdk, b.Name), nil
}

type SdkRecord struct {
	Name    string                `yaml:"name"`
	Channel string                `yaml:"channel,omitempty"`
	Source  sdk.Source            `yaml:"source,omitempty"`
	Plugs   map[string]PlugOrBind `yaml:"plugs,omitempty"`
	Slots   map[string]any        `yaml:"slots,omitempty"`
}

func (s SdkRecord) MarshalYAML() (any, error) {
	switch s.Source {
	case sdk.TrySource:
		s.Name = fmt.Sprintf("try-%s", s.Name)
	case sdk.ProjectSource:
		s.Name = fmt.Sprintf("project-%s", s.Name)
	}
	s.Source = 0

	type record SdkRecord
	return (*record)(&s), nil
}

func (s *SdkRecord) UnmarshalYAML(value *yaml.Node) error {
	type record SdkRecord
	err := value.Decode((*record)(s))
	s.Name, s.Source = parseSdkName(s.Name)
	return err
}

func parseSdkName(name string) (string, sdk.Source) {
	if sdk.IsSystem(name) {
		return name, sdk.SystemSource
	}

	if sdk.IsSketch(name) {
		return name, sdk.SketchSource
	}

	suffix, found := strings.CutPrefix(name, "try-")
	if found {
		return suffix, sdk.TrySource
	}

	suffix, found = strings.CutPrefix(name, "project-")
	if found {
		return suffix, sdk.ProjectSource
	}

	return name, sdk.StoreSource
}

type Connection struct {
	PlugRef PlugRef `yaml:"plug"`
	SlotRef SlotRef `yaml:"slot"`
}

type Action string

type File struct {
	Name        string            `yaml:"name"`
	Base        string            `yaml:"base"`
	Sdks        []SdkRecord       `yaml:"sdks,omitempty"`
	Connections []Connection      `yaml:"connections,omitempty"`
	Actions     map[string]Action `yaml:"actions,omitempty"`
}

func (a Action) String() string {
	// Trim newlines, then append a newline for multi-line scripts.
	script := strings.Trim(string(a), "\n")
	if strings.ContainsRune(script, '\n') {
		script += "\n"
	}
	return script
}

func (a Action) MarshalYAML() (any, error) {
	node := &yaml.Node{}
	err := node.Encode(a.String())
	return node, err
}

func (a *Action) UnmarshalYAML(value *yaml.Node) error {
	var script string
	if err := value.Decode(&script); err != nil {
		return err
	}

	// Scripts should have trailing newlines,
	// but YAML one-liners don't.
	if !strings.HasSuffix(script, "\n") {
		script += "\n"
	}

	// Adjust line numbers to improve error messages.
	// Only accurate for literals (|) and one-liners.
	if (value.Kind & yaml.ScalarNode) != 0 {
		line := value.Line
		if (value.Style & (yaml.LiteralStyle | yaml.FoldedStyle)) != 0 {
			line += 1
		}
		if line > 1 {
			script = strings.Repeat("\n", line-1) + script
		}
	}

	*a = Action(script)
	return nil
}

// ValidateFile validates a workshop File struct.
func ValidateFile(file *File) error {
	if !workshopName.MatchString(file.Name) {
		return fmt.Errorf("a workshop's name must: (1) start with a letter, (2) only include digits, lowercase letters, and hyphens joining them")
	}
	if len(file.Name) > MAX_WORKSHOP_NAME_LENGTH {
		return fmt.Errorf("workshop name %q too long", file.Name)
	}

	if !slices.Contains(SupportedBases, file.Base) {
		return fmt.Errorf("base %q not supported", file.Base)
	}

	if err := validateSdks(file.Sdks); err != nil {
		return err
	}

	if err := validateBinding(file.Sdks); err != nil {
		return err
	}

	if err := validateConnections(file); err != nil {
		return err
	}

	if err := validateActions(file); err != nil {
		return err
	}

	return nil
}

func readWorkshop(path string) (*File, error) {
	var err error
	var file File

	buf, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, fmt.Errorf("workshop definition %q not found", path)
		}
		return nil, err
	}
	if err = yaml.Unmarshal(buf, &file); err != nil {
		te, ok := err.(*yaml.TypeError)
		if ok {
			errs := strings.Join(te.Errors, "\n")
			return nil, fmt.Errorf("workshop definition YAML:\n%s", errs)
		}
		return nil, err
	}

	if err := ValidateFile(&file); err != nil {
		return nil, err
	}

	return &file, nil
}

func validateSdks(sdks []SdkRecord) error {
	seen := map[string]bool{}
	for _, s := range sdks {
		if err := sdk.ValidateName(s.Name); err != nil {
			return err
		}

		if _, ok := seen[s.Name]; ok {
			return fmt.Errorf("%q SDK must only be included once", s.Name)
		}
		seen[s.Name] = true

		if s.Channel != "" {
			if _, err := sdk.ParseChannel(s.Channel); err != nil {
				return fmt.Errorf("%q SDK: %w", s.Name, err)
			}
		}
	}
	return nil
}

func validateBinding(sdks []SdkRecord) error {
	// All bindings must refer to the existing SDKs and meet the name validity
	// checks (at this stage). Later, when SDK metadata will be received, the
	// plugs must be checked again (e.g. ensure all those plugs actually exist).
	masters := make(map[PlugRef][]PlugRef)
	slaves := make(map[PlugRef]PlugRef)
	for _, s := range sdks {
		for name, p := range s.Plugs {
			if p.Bind == nil {
				continue
			}
			mr := *p.Bind
			sl := PlugRef{Sdk: s.Name, Name: name}
			masters[mr] = append(masters[mr], sl)
			slaves[sl] = mr

			if sdk.IsSystem(sl.Sdk) {
				return fmt.Errorf("cannot bind system SDK plug %q", sl.String())
			}
			if sdk.IsSystem(mr.Sdk) {
				return fmt.Errorf("cannot bind to system SDK plug %q", mr.String())
			}
			if !IsImplicitSdk(p.Bind.Sdk) && !slices.ContainsFunc(sdks, func(sr SdkRecord) bool { return p.Bind.Sdk == sr.Name }) {
				return fmt.Errorf("cannot bind plug %q: SDK %q not found", p.Bind.String(), p.Bind.Sdk)
			}
			if mr == sl {
				return fmt.Errorf(`cannot bind plug %q to itself`, p.Bind.String())
			}
		}
	}

	// Ensure that there are no "multi-level" binds, e.g. s1 bind to m1 bind to m2.
	slaveKeysOrdered := slices.Collect(maps.Keys(slaves))
	slices.SortFunc(slaveKeysOrdered, func(a, b PlugRef) int {
		c := cmp.Compare(a.Sdk, b.Sdk)
		if c == 0 {
			return cmp.Compare(a.Name, b.Name)
		}
		return c
	})
	for _, sl := range slaveKeysOrdered {
		m := slaves[sl]
		if _, ok := masters[sl]; ok {
			return fmt.Errorf(`cannot bind %q to %q: plug %q is already bound`, sl.String(), m.String(), sl.String())
		}
	}
	return nil
}

func isBound(plug PlugRef, wf *File) bool {
	return slices.ContainsFunc(wf.Sdks, func(s SdkRecord) bool {
		if s.Name != plug.Sdk {
			return false
		}

		for name, p := range s.Plugs {
			if name == plug.Name && p.Bind != nil {
				return true
			}
		}
		return false
	})
}

func validateConnections(wfile *File) error {
	for _, conn := range wfile.Connections {
		if isBound(conn.PlugRef, wfile) {
			return fmt.Errorf(`cannot connect plug %q to slot %q: plug is bound`,
				conn.PlugRef.String(), conn.SlotRef.String())
		}

		if !slices.ContainsFunc(wfile.Sdks, func(r SdkRecord) bool { return r.Name == conn.PlugRef.Sdk || IsImplicitSdk(conn.PlugRef.Sdk) }) {
			return fmt.Errorf(`cannot connect plug %q to slot %q: workshop %q has no SDK named %q`,
				conn.PlugRef.String(), conn.SlotRef.String(), wfile.Name, conn.PlugRef.Sdk)
		}
		if !slices.ContainsFunc(wfile.Sdks, func(r SdkRecord) bool { return r.Name == conn.SlotRef.Sdk || IsImplicitSdk(conn.SlotRef.Sdk) }) {
			return fmt.Errorf(`cannot connect plug %q to slot %q: workshop %q has no SDK named %q`,
				conn.PlugRef.String(), conn.SlotRef.String(), wfile.Name, conn.SlotRef.Sdk)
		}
	}
	return nil
}

func validateActions(wfile *File) error {
	for name := range wfile.Actions {
		if !actionName.MatchString(name) {
			return fmt.Errorf("action name %q must: (1) start with a letter, (2) only include digits, lowercase letters, and hyphens joining them", name)
		}
	}
	return nil
}

// IsImplicitSdk checks whether the given SDK is installed
// regardless of whether it appears in the workshop file.
func IsImplicitSdk(name string) bool {
	return sdk.IsSystem(name) || sdk.IsSketch(name)
}

// IsProjectSdk checks whether the given SDK is defined
// in the project directory.
func IsProjectSdk(name string) bool {
	return strings.HasPrefix(name, "project-")
}
```

</details>


---

<sub>8m 42s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/schema.json.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/schema.json

<details>
<summary>175 lines</summary>

```
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://canonical.com/workshop.yaml",
  "title": "Workshop",
  "description": "Workshop definition.",
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Workshop name. Must start with a lowercase letter and may contain lowercase letters, digits, and hyphens between them. Up to 40 characters. Must match the definition file basename if the workshop is stored under .workshop/.",
      "pattern": "^[a-z](?:-?[a-z0-9])*$",
      "maxLength": 40,
      "errorMessage": "A workshop's name must start with a lowercase letter and can only include digits, lowercase letters, and hyphens joining them."
    },
    "base": {
      "type": "string",
      "description": "Base operating system image for the workshop. Must be one of the supported Ubuntu releases. SDKs with a declared base must match the workshop base; SDKs without a base are accepted on any workshop.",
      "enum": [
        "ubuntu@20.04",
        "ubuntu@22.04",
        "ubuntu@24.04",
        "ubuntu@26.04"
      ],
      "errorMessage": "The base must be one of the supported values: ubuntu@20.04, ubuntu@22.04, ubuntu@24.04, ubuntu@26.04."
    },
    "sdks": {
      "type": "array",
      "description": "Ordered list of SDKs to install on top of the base. Each entry references an existing SDK; names must be unique within the list. The system SDK is installed first implicitly and need not be listed.",
      "uniqueItems": true,
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "description": "SDK name. Prefix with try- for a locally tried SDK, project- for an in-project SDK, or use system for the built-in system SDK; an unprefixed name resolves to an SDK from the Store. The underlying name must contain at least one lowercase letter, may consist of lowercase letters, digits, and hyphens between them, and cannot be agent. Without a prefix the name is at most 40 characters; with try- at most 44; with project- at most 48.",
            "if": {
              "pattern": "^try-"
            },
            "then": {
              "maxLength": 44,
              "pattern": "^(?!(?:try-|project-)?agent$)try-(?!try-|project-)(?:[a-z0-9]-?)*[a-z](?:-?[a-z0-9])*$"
            },
            "else": {
              "if": {
                "pattern": "^project-"
              },
              "then": {
                "maxLength": 48,
                "pattern": "^(?!(?:try-|project-)?agent$)project-(?!try-|project-)(?:[a-z0-9]-?)*[a-z](?:-?[a-z0-9])*$"
              },
              "else": {
                "maxLength": 40,
                "pattern": "^(?!(?:try-|project-)?agent$)(?!try-|project-)(?:[a-z0-9]-?)*[a-z](?:-?[a-z0-9])*$"
              }
            },
            "errorMessage": "An SDK's name must contain a letter, may have a single 'try-' or 'project-' prefix, must not chain prefixes, and the underlying name cannot be 'agent'."
          },
          "channel": {
            "type": "string",
            "description": "Store channel used to retrieve the SDK at launch and refresh. Snap-like format: [<TRACK>/]<RISK>[/<BRANCH>], or <TRACK>, or <RISK>/<BRANCH>. Risk is one of stable, candidate, beta, edge. Track is at most 28 characters; branch is at most 128 characters; neither may equal a risk name. Default is latest/stable. Only applies to SDKs from the Store; for try-, project-, and system SDKs the value has no effect but must still be well formed.",
            "pattern": "^(?:(?:[a-zA-Z0-9](?:[_.-]?[a-zA-Z0-9])*/)?(?:stable|candidate|beta|edge)(?:/[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9])?|[a-zA-Z0-9](?:[_.-]?[a-zA-Z0-9])*)$",
            "errorMessage": "Channel must look like [<track>/]<risk>[/<branch>] or [<track>]."
          },
          "plugs": {
            "type": "object",
            "description": "Plug bindings and additional plug definitions for the SDK. Each key must start with a lowercase letter and contain only lowercase letters, digits, and hyphens between them.",
            "additionalProperties": false,
            "patternProperties": {
              "^[a-z](?:-?[a-z0-9])*$": {
                "description": "Either an inline plug definition (a mapping whose keys are interface-specific attributes such as interface, workshop-target, endpoint), a string naming the interface, null to use the key as the interface name, or a binding to another plug declared in the same workshop. To bind, provide a single bind key whose value is the target plug reference; bound plugs cannot define other attributes and cannot also appear in connections.",
                "properties": {
                  "bind": {
                    "type": "string",
                    "description": "Plug reference in the form <sdk>:<plug>. The target plug must use the same interface as this plug, must not itself be bound, and must not belong to the system SDK (so the <sdk> portion must name a non-system SDK).",
                    "pattern": "^(?!system:)(([a-z0-9]-?)*[a-z](-?[a-z0-9])*):[a-z](-?[a-z0-9])*$",
                    "errorMessage": "Bind reference must follow the pattern <sdk>:<plug>, where <sdk> names a non-system SDK."
                  }
                },
                "if": {
                  "type": "object",
                  "required": [
                    "bind"
                  ]
                },
                "then": {
                  "type": "object",
                  "properties": {
                    "bind": true
                  },
                  "additionalProperties": false,
                  "errorMessage": "When 'bind' is set, no other attributes are allowed on the plug."
                }
              }
            }
          },
          "slots": {
            "type": "object",
            "description": "Additional slot definitions grafted onto the SDK by the workshop. Each key must start with a lowercase letter and contain only lowercase letters, digits, and hyphens between them. Each value is either an inline slot definition (a mapping with interface and any interface-specific attributes), a string naming the interface, or null to use the key as the interface name.",
            "patternProperties": {
              "^[a-z](?:-?[a-z0-9])*$": {
                "type": ["object", "string", "null"],
                "description": "Slot definition: an inline mapping with interface and any interface-specific attributes, a string naming the interface, or null to take the interface from the key."
              }
            },
            "additionalProperties": false
          }
        },
        "required": [
          "name"
        ],
        "errorMessage": {
          "required": {
            "name": "Each SDK must specify a name."
          }
        },
        "additionalProperties": false
      }
    },
    "connections": {
      "type": "array",
      "description": "Explicit connections from plugs to slots, applied on top of auto-connection. Both endpoints must reference an SDK that is present in the workshop or is implicit (system, sketch), and must share the same interface. A plug that is bound elsewhere cannot also appear here.",
      "items": {
        "type": "object",
        "properties": {
          "plug": {
            "type": "string",
            "description": "Plug reference in the form <sdk>:<plug>. The <sdk> portion may be empty (for example, :ssh-agent) to refer to the system SDK.",
            "pattern": "^(([a-z0-9]-?)*[a-z](-?[a-z0-9])*)?:[a-z](-?[a-z0-9])*$",
            "errorMessage": "Plug reference must follow the pattern <sdk>:<plug> (the <sdk> portion may be empty for the system SDK)."
          },
          "slot": {
            "type": "string",
            "description": "Slot reference in the form <sdk>:<slot>. The <sdk> portion may be empty (for example, :ssh-agent) to refer to the system SDK.",
            "pattern": "^(([a-z0-9]-?)*[a-z](-?[a-z0-9])*)?:[a-z](-?[a-z0-9])*$",
            "errorMessage": "Slot reference must follow the pattern <sdk>:<slot> (the <sdk> portion may be empty for the system SDK)."
          }
        },
        "required": [
          "plug",
          "slot"
        ],
        "errorMessage": {
          "required": {
            "plug": "Each connection must specify a plug.",
            "slot": "Each connection must specify a slot."
          }
        },
        "additionalProperties": false
      }
    },
    "actions": {
      "type": "object",
      "description": "Named shell scripts available via workshop run. Action names must start with a lowercase letter and contain only lowercase letters, digits, and hyphens between them. Each script body runs under bash as a login shell with errexit and pipefail set; positional parameters $@, $1, $2, ... receive the arguments passed after the workshop name.",
      "patternProperties": {
        "^[a-z](?:-?[a-z0-9])*$": {
          "type": "string",
          "description": "Shell script body executed by bash inside the workshop."
        }
      },
      "additionalProperties": false,
      "errorMessage": "Action names must start with a lowercase letter and contain only lowercase letters, digits, and hyphens between them."
    }
  },
  "required": [
    "name",
    "base"
  ],
  "additionalProperties": false,
  "errorMessage": {
    "required": {
      "name": "The 'name' field is required.",
      "base": "The 'base' field is required."
    }
  }
}
```

</details>


---

<sub>8m 42s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/examples/workshop-golang.yaml.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/examples/workshop-golang.yaml

<details>
<summary>10 lines</summary>

```
name: golang
base: ubuntu@22.04
sdks:
  - name: go
    channel: "1.26"
actions:
  lint: |
    go vet
    golangci-lint run
  tests: go test "$@"
```

</details>


---

<sub>8m 45s</sub>

### Reasoning

*Good, I've read all three declared sources. Now I need to navigate freely to gather more context:
1. The `sdk.AllowedBases` - what are the allowed bases?
2. The `sdk.ValidateName` function
3. The sibling pages `sdk-definition.rst` and `sdkcraft-definition.rst` for format/structure conventions
4. More example files
5. The `docs/reference/definition-files/index.rst` already read
6. The `docs/_dev/doc-style.md` for voice conventions
7. Check what `sdk.Source`, `sdk.ParseChannel`, `sdk.IsSystem`, `sdk.IsSketch` are
8. The `cmd/workshop/init_test.go` to understand what the init command produces

The schema.json gives me the authoritative definitions, so I should prioritize reading the validation functions and sibling reference pages to understand the constraints and structure conventions, then look at more examples.*

---

<sub>8m 52s</sub>

### Copilot

Now navigating freely to gather more grounding.

---

<sub>8m 55s</sub>

### `bash`

**Find SDK-level validation constants**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "AllowedBases\|ValidateName\|ParseChannel\|IsSystem\|IsSketch\|Source\b" internal/sdk/*.go | grep -v "_test.go" | head -60

<details>
<summary>37 lines</summary>

```
internal/sdk/channel.go:53:	channel, err := ParseChannel(string(data))
internal/sdk/channel.go:64:func ParseChannel(channel string) (Channel, error) {
internal/sdk/sdk.go:42:	Source    Source   `json:"source,omitempty"`
internal/sdk/sdk.go:56:	return s.Source == StoreSource || s.Source == SystemSource || s.Source == TrySource
internal/sdk/sdk.go:63:type Source int
internal/sdk/sdk.go:66:	StoreSource Source = iota
internal/sdk/sdk.go:67:	SystemSource
internal/sdk/sdk.go:68:	TrySource
internal/sdk/sdk.go:69:	ProjectSource
internal/sdk/sdk.go:70:	SketchSource
internal/sdk/sdk.go:73:func (s Source) MarshalText() ([]byte, error) {
internal/sdk/sdk.go:76:	case StoreSource:
internal/sdk/sdk.go:78:	case SystemSource:
internal/sdk/sdk.go:80:	case TrySource:
internal/sdk/sdk.go:82:	case ProjectSource:
internal/sdk/sdk.go:84:	case SketchSource:
internal/sdk/sdk.go:92:func (s *Source) UnmarshalText(text []byte) error {
internal/sdk/sdk.go:95:		*s = StoreSource
internal/sdk/sdk.go:97:		*s = SystemSource
internal/sdk/sdk.go:99:		*s = TrySource
internal/sdk/sdk.go:101:		*s = ProjectSource
internal/sdk/sdk.go:103:		*s = SketchSource
internal/sdk/sdk.go:110:func (s Source) NeedsRetrieve() bool {
internal/sdk/sdk.go:111:	return s == StoreSource || s == SystemSource
internal/sdk/sdk.go:167:func IsSystem(name string) bool {
internal/sdk/sdk.go:171:func IsSketch(name string) bool {
internal/sdk/sdk.go:186:	Source      Source
internal/sdk/sdk.go:296:	if sdkYaml.Type == System.String() && !IsSystem(sdkYaml.Name) {
internal/sdk/validate.go:65:	AllowedBases = []string{"ubuntu@20.04", "ubuntu@22.04", "ubuntu@24.04", "ubuntu@26.04"}
internal/sdk/validate.go:112:	if y.Type == System.String() && !IsSystem(y.Name) {
internal/sdk/validate.go:162:	if err := ValidateName(sdk.Name); err != nil {
internal/sdk/validate.go:166:	if sdk.Base != "" && !slices.Contains(AllowedBases, sdk.Base) {
internal/sdk/validate.go:167:		return fmt.Errorf("invalid SDK base %q; supported bases: %s", sdk.Base, strings.Join(AllowedBases, ", "))
internal/sdk/validate.go:222:	if !IsSketch(y.Name) {
internal/sdk/validate.go:305:// ValidateName checks if a string can be used as an SDK name.
internal/sdk/validate.go:306:func ValidateName(name string) error {
<shellId: 13 completed with exit code 0>
```

</details>


---

<sub>8m 55s</sub>

### `bash`

**Read sibling sdk-definition.rst in full**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat docs/reference/definition-files/sdk-definition.rst

<details>
<summary>174 lines</summary>

```
.. _ref_sdk_definition:

.. meta::
   :description: Reference for the runtime sdk.yaml definition file. Covers
                 filename conventions, top-level fields, interface attributes,
                 the JSON Schema, and worked examples.

SDK definition
==============

.. @artefact SDK definition

The :file:`sdk.yaml` file is the *runtime* SDK definition:
|ws_markup| reads it when it installs an SDK in a workshop.
For Store SDKs and SDKs from :command:`sdkcraft try`,
this file is produced by |sdk_markup| from :file:`sdkcraft.yaml`
(see :ref:`ref_sdkcraft_definition`).
For sketch SDKs and in-project SDKs,
you author :file:`sdk.yaml` directly:
sketch SDKs through :command:`workshop sketch-sdk`,
in-project SDKs by hand under :file:`.workshop/`.


Filename and location
---------------------

.. @artefact SDK definition

- Store SDKs and SDKs from :command:`sdkcraft try` ship :file:`sdk.yaml`
  inside their packed contents at :file:`meta/sdk.yaml`.

- In-project SDKs use
  :file:`.workshop/<NAME>/sdk.yaml` or :file:`.workshop/<NAME>/meta/sdk.yaml`,
  relative to the project directory.
  Their hook scripts live next to the definition,
  under :file:`.workshop/<NAME>/hooks/`.

- Sketch SDK definitions live in the per-workshop data directory:
  :file:`~/.local/share/workshop/id/<PROJECT-ID>/<WORKSHOP>/sdk/sketch/current/sdk.yaml`.


In-project and sketch SDKs do not support |sdk_markup| build-time features
such as :samp:`build-base`, :samp:`platforms`, or :samp:`parts`.
These belong to :file:`sdkcraft.yaml`.


Top-level fields
----------------

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 6

   * - Key
     - Value
     - Description

   * - :samp:`name` (required)
     - string
     - SDK identifier. Must contain at least one lowercase letter
       and may consist of lowercase letters, digits, and hyphens between them.
       Up to 40 characters.
       Cannot be :samp:`agent`, :samp:`system`, :samp:`sketch`,
       or start with :samp:`try-` or :samp:`project-`; those names are reserved.

   * - :samp:`architecture` (required for built SDKs)
     - string
     - CPU architecture the SDK is built for,
       following `Debian's naming scheme <https://www.debian.org/ports/>`__
       (for example, :samp:`amd64`, :samp:`arm64`).
       Use :samp:`all` for SDKs that ship no compiled binaries.

   * - :samp:`version` (required for built SDKs)
     - string
     - SDK version. Semantic versioning is recommended.

       .. note::

          Quote version strings in YAML when they look numeric
          (for example, :samp:`version: "1.0"`) to avoid type coercion.

   * - :samp:`summary` (required for built SDKs)
     - string
     - One-line summary, up to 78 characters.

   * - :samp:`description` (required for built SDKs)
     - string
     - Longer free-form description, up to about a hundred words.

   * - :samp:`sdkcraft-started-at` (required for built SDKs)
     - string
     - UTC timestamp marking when |sdk_markup| started the build.
       Set automatically; do not edit by hand.

   * - :samp:`base`
     - string
     - Base operating system image the SDK targets.
       One of :samp:`ubuntu@20.04`, :samp:`ubuntu@22.04`, :samp:`ubuntu@24.04`,
       or :samp:`ubuntu@26.04`.
       Omit for SDKs that work on any supported base.

   * - :samp:`title`
     - string
     - Human-readable title.

   * - :samp:`license`
     - string
     - License name, as it would appear in package metadata.

       .. note::

          Match the license to the actual components the SDK installs.

   * - :samp:`contact`
     - string, array, or URL
     - Contact information for the SDK publisher.

   * - :samp:`issues`
     - string, array, or URL
     - Where users should report problems with the SDK.

   * - :samp:`source-code`
     - URL
     - Where the SDK's source code is hosted.

   * - :samp:`website`
     - URL
     - The web page for the SDK.

   * - :samp:`plugs`
     - object
     - Plugs the SDK requests from the workshop environment.
       Each key is the plug name; each value is an inline plug definition.
       See :ref:`ref_sdk_definition_interfaces`.

   * - :samp:`slots`
     - object
     - Slots the SDK provides.
       Each key is the slot name;
       each value is an inline slot definition.
       Only the :samp:`mount` and :samp:`tunnel` interfaces
       support slots on regular SDKs.
       See :ref:`ref_sdk_definition_interfaces`.


.. note::

   "Required for built SDKs" means |sdk_markup| writes the field
   when it builds an SDK package;
   for an in-project SDK,
   you can author :file:`sdk.yaml` with only :samp:`name`,
   plus whichever optional fields you need.
   In particular,
   :samp:`architecture` for in-project SDKs is assumed
   to match the host (or :samp:`all`).


.. _ref_sdk_definition_interfaces:

Interfaces
----------

A plug or slot value is an inline definition:
a mapping that specifies the :samp:`interface`
and any interface-specific attributes.

.. include:: _interfaces/camera.rst

.. include:: _interfaces/custom-device.rst

.. include:: _interfaces/desktop.rst

.. include:: _interfaces/gpu.rst

.. include:: _interfaces/mount.rst

.. include:: _interfaces/ssh-agent.rst

.. include:: _interfaces/tunnel.rst


JSON Schema
-----------

.. @artefact SDK schema

The following JSON Schema is exported from |sdk_markup|'s runtime metadata model
and describes the structure above:

.. note::

   The schema describes a *built* :file:`sdk.yaml`,
   that is, the file |sdk_markup| writes when it packs an SDK.
   The :samp:`required` list reflects what a packed SDK must carry;
   for an in-project :file:`sdk.yaml` you author by hand,
   only :samp:`name` is mandatory
   (see the note below the table).

   Numeric bounds use pydantic-style :samp:`ge`, :samp:`le`, and :samp:`lt` keywords.
   Generic JSON Schema validators will not enforce them;
   treat the bounds as documentation of the runtime's accepted ranges,
   and rely on the field table above for the authoritative rules.


.. dropdown:: SDK definition schema

   .. literalinclude:: schema-sdk.json
      :language: json


Examples
--------

In-project SDK that declares a mount plug:

.. literalinclude:: ../../examples/sdk-project-cache.yaml
   :language: yaml
   :caption: .workshop/ccache/sdk.yaml

Runtime :file:`sdk.yaml` written by |sdk_markup| for a Go development SDK:

.. literalinclude:: ../../examples/sdk-go-runtime.yaml
   :language: yaml
   :caption: meta/sdk.yaml


See also
--------

Explanation:

- :ref:`exp_in_project_sdk`
- :ref:`exp_sdk_concepts`
- :ref:`exp_sdk_definition`
- :ref:`exp_system_sdk`

Reference:

- :ref:`ref_sdk_internals`
- :ref:`ref_sdkcraft_definition`
- :ref:`ref_workshop_definition`

Tutorial:

- :ref:`tut_sketch_sdks`
<shellId: 14 completed with exit code 0>
```

</details>


---

<sub>8m 55s</sub>

### `bash`

**Read remaining workshop example files**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat docs/examples/workshop-try-go.yaml docs/examples/workshop-go-dev.yaml docs/examples/workshop-digits-cuda.yaml

<details>
<summary>33 lines</summary>

```
name: try-go
base: ubuntu@24.04
sdks:
  - name: try-go
name: go-dev
base: ubuntu@22.04
sdks:
  - name: go
    channel: edge
  - name: project-cache
    plugs:
      data:
        bind: go:mod-cache
name: digits-cuda
base: ubuntu@22.04
sdks:
  - name: tensorflow
    plugs:
      cuda:
        interface: mount
        workshop-target: /usr/local/cuda/lib64
  - name: imagenet
    slots:
      images:
        interface: mount
        workshop-source: $SDK/images
  - name: cuda
connections:
  - plug: tensorflow:cuda
    slot: cuda:libs
  - plug: tensorflow:images
    slot: imagenet:images
<shellId: 15 completed with exit code 0>
```

</details>


---

<sub>8m 58s</sub>

### Reasoning

*Let me also read `internal/sdk/validate.go` and `internal/sdk/sdk.go` for the `ValidateName` function and `IsSystem`/`IsSketch`, as well as `internal/sdk/channel.go` for channel format.*

---

<sub>9m 1s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/validate.go.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/validate.go (lines 1-80)

<details>
<summary>64 lines</summary>

```
// Copyright (c) 2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License version 3 as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package sdk

import (
	"errors"
	"fmt"
	"io"
	"regexp"
	"slices"
	"strings"
	"time"

	"gopkg.in/yaml.v3"

	"github.com/canonical/workshop/internal/arch"
)

// InvalidSDKHookNameError reports an unsupported SDK hook name.
type InvalidSDKHookNameError string

// UnknownYamlField reports where an unknown top-level SDK YAML field was
// found.
type UnknownYamlField struct {
	Column int
	Line   int
}

// UnknownYamlFieldsError reports unknown top-level fields in an SDK YAML
// definition.
type UnknownYamlFieldsError struct {
	Fields map[string]UnknownYamlField
}

type sdkYamlValidator struct {
	sdkYaml `yaml:",inline"`
	Unknown map[string]UnknownYamlField `yaml:",inline"`
}

type sketchSDKYamlValidator struct {
	SketchSDKYaml `yaml:",inline"`
	Unknown       map[string]UnknownYamlField `yaml:",inline"`
}

const MAX_SDK_NAME_LENGTH = 40

var (
	// ErrorInvalidSDKName reports an invalid SDK name.
	ErrorInvalidSDKName = errors.New("invalid SDK name")
)

var (
	AllowedBases = []string{"ubuntu@20.04", "ubuntu@22.04", "ubuntu@24.04", "ubuntu@26.04"}

	// AllowedHooks lists hook names accepted in sketch SDK YAML.
	AllowedHooks = []string{"setup-base", "setup-project", "save-state", "restore-state", "check-health"}

	sdkName = regexp.MustCompile(`^(?:[a-z0-9]-?)*[a-z](?:-?[a-z0-9])*$`)
	// Regular expression describing correct plug, slot and interface names.
	validPlugSlotIface = regexp.MustCompile("^[a-z](?:-?[a-z0-9])*$")
)

// Error returns a human-readable message describing the invalid hook name.
func (e InvalidSDKHookNameError) Error() string {
	return "invalid SDK hook name"
}

// Error returns a human-readable message describing the unknown YAML fields.
```

</details>


---

<sub>9m 1s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/sdk.go.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/sdk.go (lines 155-200)

<details>
<summary>38 lines</summary>

```

const Sketch = "sketch"

const (
	Regular Type = "regular"
	System  Type = "system"
)

func (t Type) String() string {
	return string(t)
}

func IsSystem(name string) bool {
	return name == System.String()
}

func IsSketch(name string) bool {
	return name == Sketch
}

type Info struct {
	ProjectId   string
	Workshop    string
	Name        string
	PackageID   string
	Base        string
	Arch        string
	Version     string
	Type        Type
	Revision    Revision
	Channel     string
	Source      Source
	BuiltAt     *time.Time
	Title       string
	Summary     string
	Description string
	License     string

	Plugs     map[string]*PlugInfo
	PlugBinds map[string]PlugRef
	Slots     map[string]*SlotInfo
	// Plugs or slots with issues (they are not included in Plugs or Slots)
	BadInterfaces map[string]string
}

func (i *Info) Ref() Ref {
```

</details>


---

<sub>9m 1s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/channel.go.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/channel.go

<details>
<summary>117 lines</summary>

```
// -*- Mode: Go; indent-tabs-mode: t -*-

/*
 * Copyright (C) 2018-2019 Canonical Ltd
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

package sdk

import (
	"fmt"
	"regexp"
	"slices"
	"strings"
)

const (
	MAX_TRACK_LENGTH  = 28
	MAX_BRANCH_LENGTH = 128
)

var (
	channelTrack  = regexp.MustCompile(`^[a-zA-Z0-9](?:[_.-]?[a-zA-Z0-9])*$`)
	channelRisks  = []string{"stable", "candidate", "beta", "edge"}
	channelBranch = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]$`)
)

// Channel identifies and describes completely a store channel.
type Channel struct {
	Name   string `json:"name"`
	Track  string `json:"track"`
	Risk   string `json:"risk"`
	Branch string `json:"branch,omitempty"`
}

func (c Channel) MarshalText() ([]byte, error) {
	return []byte(c.String()), nil
}

func (c *Channel) UnmarshalText(data []byte) error {
	channel, err := ParseChannel(string(data))
	if err == nil {
		*c = channel
	}
	return err
}

func (c Channel) String() string {
	return c.Name
}

func ParseChannel(channel string) (Channel, error) {
	parts := strings.Split(channel, "/")
	var risk, track, branch *string
	switch len(parts) {
	case 1:
		if slices.Contains(channelRisks, parts[0]) {
			risk = &parts[0]
		} else {
			track = &parts[0]
		}
	case 2:
		if slices.Contains(channelRisks, parts[0]) {
			risk, branch = &parts[0], &parts[1]
		} else {
			track, risk = &parts[0], &parts[1]
		}
	case 3:
		track, risk, branch = &parts[0], &parts[1], &parts[2]
	default:
		return Channel{}, fmt.Errorf("channel %q has too many components", channel)
	}

	ch := Channel{Name: channel}
	if track != nil {
		if len(*track) > MAX_TRACK_LENGTH || !channelTrack.MatchString(*track) || slices.Contains(channelRisks, *track) {
			return Channel{}, fmt.Errorf("invalid track %q in channel %q", *track, channel)
		}
		ch.Track = *track
	}
	if risk != nil {
		if !slices.Contains(channelRisks, *risk) {
			return Channel{}, fmt.Errorf("invalid risk %q in channel %q", *risk, channel)
		}
		ch.Risk = *risk
	}
	if branch != nil {
		if len(*branch) > MAX_BRANCH_LENGTH || !channelBranch.MatchString(*branch) || slices.Contains(channelRisks, *branch) {
			return Channel{}, fmt.Errorf("invalid branch %q in channel %q", *branch, channel)
		}
		ch.Branch = *branch
	}
	return ch, nil
}

// Full replaces empty fields with their defaults.
func (c *Channel) Full() Channel {
	track := c.Track
	if track == "" {
		track = "latest"
	}
	risk := c.Risk
	if risk == "" {
		risk = "stable"
	}

	var name strings.Builder
	fmt.Fprint(&name, track, "/", risk)
	if c.Branch != "" {
		fmt.Fprint(&name, "/", c.Branch)
	}

	return Channel{
		Name:   name.String(),
		Track:  track,
		Risk:   risk,
		Branch: c.Branch,
	}
}
```

</details>


---

<sub>9m 4s</sub>

### Reasoning

*Now I have a deep understanding of the schema. Let me also read the ValidateName function and read the conf.py or the index.rst to understand substitutions like |ws_markup| and |sdk_markup|, as well as the `docs/reference/workshops.rst` to understand the existing workshop reference.*

---

<sub>9m 9s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/validate.go.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/internal/sdk/validate.go (lines 300-340)

<details>
<summary>36 lines</summary>

```
	}

	return Validate(sdkInfo)
}

// ValidateName checks if a string can be used as an SDK name.
func ValidateName(name string) error {
	if name == "agent" || strings.HasPrefix(name, "try-") || strings.HasPrefix(name, "project-") {
		return fmt.Errorf("%q is a reserved SDK name", name)
	}
	if !sdkName.MatchString(name) {
		return fmt.Errorf("invalid SDK name %q", name)
	}
	if len(name) > MAX_SDK_NAME_LENGTH {
		return fmt.Errorf("SDK name %q too long", name)
	}
	return nil
}

// ValidatePlug checks if a string can be used as a slot name.
//
// Slot names and plug names within one sdk must have unique names.
func ValidatePlugName(name string) error {
	if !validPlugSlotIface.MatchString(name) {
		return fmt.Errorf("invalid plug name: %q", name)
	}
	return nil
}

// ValidateSlot checks if a string can be used as a slot name.
//
// Slot names and plug names within one sdk must have unique names.
func ValidateSlotName(name string) error {
	if !validPlugSlotIface.MatchString(name) {
		return fmt.Errorf("invalid slot name: %q", name)
	}
	return nil
}

// ValidateInterface checks if a string can be used as an interface name.
func ValidateInterfaceName(name string) error {
```

</details>


---

<sub>9m 9s</sub>

### `bash`

**Find substitution definitions in conf.py**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "ws_markup\|sdk_markup\|substitution\|replace" docs/conf.py | head -20

```
183:# Inlined from former docs/reuse/links.txt and docs/reuse/substitutions.txt.
192:.. |ws_markup| replace:: :program:`Workshop`
193:.. |sdk_markup| replace:: :program:`SDKcraft`
<shellId: 16 completed with exit code 0>
```


---

<sub>9m 9s</sub>

### `bash`

**Find where substitutions are defined**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -rn "ws_markup\|sdk_markup" docs/ --include="*.rst" | head -5

<details>
<summary>6 lines</summary>

```
docs/index.rst:10:|ws_markup|
docs/index.rst:39:With |ws_markup|, you can launch a setup
docs/index.rst:49:That's where |ws_markup| thrives.
docs/index.rst:52:|ws_markup| publishes :ref:`LLM-readable docs <ref_ai_discovery>`,
docs/index.rst:145::doc:`Tutorial <tutorial/index>`: Hands-on learning path for new |ws_markup| users,
<shellId: 17 completed with exit code 0>
```

</details>


---

<sub>9m 16s</sub>

### `bash`

**Check cross-reference labels for workshop definition**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "ref_workshop_definition\|exp_workshop_definition\|workshop.yaml\|workshop_definition" docs/reference/definition-files/index.rst docs/explanation/workshops/concepts.rst 2>/dev/null | head -30

<details>
<summary>14 lines</summary>

```
docs/reference/definition-files/index.rst:16:- :file:`workshop.yaml` is authored by workshop users;
docs/reference/definition-files/index.rst:18:  See :ref:`ref_workshop_definition`.
docs/reference/definition-files/index.rst:43:- :ref:`exp_workshop_definition`
docs/explanation/workshops/concepts.rst:142:see :ref:`exp_workshop_definition_sdks` for the layering details.
docs/explanation/workshops/concepts.rst:193:.. _exp_workshop_definition:
docs/explanation/workshops/concepts.rst:211:   :caption: workshop.yaml
docs/explanation/workshops/concepts.rst:243:.. _exp_workshop_definition_sdks:
docs/explanation/workshops/concepts.rst:290:.. _exp_workshop_definition_connections:
docs/explanation/workshops/concepts.rst:316:  This is done within an SDK's entry in the :file:`workshop.yaml` file.
docs/explanation/workshops/concepts.rst:434:.. _exp_workshop_definition_actions:
docs/explanation/workshops/concepts.rst:534:    * - :ref:`Workshop definition <exp_workshop_definition>`
docs/explanation/workshops/concepts.rst:571:    * - :ref:`Actions <exp_workshop_definition_actions>`
docs/explanation/workshops/concepts.rst:599:- :ref:`ref_workshop_definition`
<shellId: 18 completed with exit code 0>
```

</details>


---

<sub>9m 16s</sub>

### `bash`

**Find cross-ref labels in sibling pages**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "ref_workshop_definition\|exp_workshop_definition\|exp_workshop_concepts\|exp_workshop" docs/reference/definition-files/sdk-definition.rst docs/reference/definition-files/sdkcraft-definition.rst 2>/dev/null | head -20

```
docs/reference/definition-files/sdk-definition.rst:242:- :ref:`ref_workshop_definition`
docs/reference/definition-files/sdkcraft-definition.rst:293:- :ref:`ref_workshop_definition`
<shellId: 19 completed with exit code 0>
```


---

<sub>9m 16s</sub>

### `bash`

**Check sdkcraft-definition.rst labels and see-also**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && head -5 docs/reference/definition-files/sdkcraft-definition.rst && echo "---" && grep -n "^\.\. _\|^See also\|:ref:" docs/reference/definition-files/sdkcraft-definition.rst | head -30

<details>
<summary>24 lines</summary>

```
.. _ref_sdkcraft_definition:

.. meta::
   :description: Reference for the sdkcraft.yaml build-time definition file.
                 Covers filename conventions, top-level fields, platforms, parts,
---
1:.. _ref_sdkcraft_definition:
17:|sdk_markup| writes the runtime :file:`sdk.yaml` (see :ref:`ref_sdk_definition`)
62:       See :ref:`ref_sdkcraft_definition_platforms`.
129:       See :ref:`ref_sdkcraft_definition_parts`.
134:       See :ref:`ref_sdkcraft_definition_interfaces`.
140:       See :ref:`ref_sdkcraft_definition_interfaces`.
153:.. _ref_sdkcraft_definition_platforms:
189:.. _ref_sdkcraft_definition_parts:
209:.. _ref_sdkcraft_definition_interfaces:
279:See also
284:- :ref:`exp_in_project_sdk`
285:- :ref:`exp_sdk_concepts`
286:- :ref:`exp_sdk_definition`
287:- :ref:`exp_sdk_hooks`
288:- :ref:`exp_system_sdk`
292:- :ref:`ref_sdk_definition`
293:- :ref:`ref_workshop_definition`
297:- :ref:`tut_craft_sdks`
<shellId: 20 completed with exit code 0>
```

</details>


---

<sub>9m 19s</sub>

### Reasoning

*Now I have a comprehensive picture. Let me also check the `docs/reference/cli/workshop-init.rst` for the `workshop init` cross-reference label, and check `docs/reference/cli/workshop-run.rst` for the `workshop run` cross-ref label.*

---

<sub>9m 23s</sub>

### `bash`

**Get anchor labels from CLI reference pages**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && head -3 docs/reference/cli/workshop-init.rst docs/reference/cli/workshop-run.rst docs/reference/cli/workshop.rst docs/reference/workshops.rst 2>/dev/null

<details>
<summary>11 lines</summary>

```
==> docs/reference/cli/workshop-init.rst <==
.. _ref_workshop_init:



==> docs/reference/cli/workshop-run.rst <==
.. _ref_workshop_run:



==> docs/reference/cli/workshop.rst <==
.. _ref_workshop__cli:

.. meta::

==> docs/reference/workshops.rst <==
.. _ref_workshop_internals:

.. meta::
<shellId: 22 completed with exit code 0>
```

</details>


---

<sub>9m 23s</sub>

### `bash`

**Get explanation page labels**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "^.. _\|^exp_workshop\|exp_sdk" docs/explanation/workshops/concepts.rst | head -20

<details>
<summary>17 lines</summary>

```
1:.. _exp_workshop_concepts:
31:.. _exp_workshop_status:
78:.. _exp_workshop_lifecycle:
133:.. _exp_workshop_launch:
150:.. _exp_workshop_refresh:
172:.. _exp_workshop_restore:
193:.. _exp_workshop_definition:
226:software packages, and :ref:`hooks <exp_sdk_hooks>`.
229:.. _exp_base:
243:.. _exp_workshop_definition_sdks:
252:see :ref:`exp_sdk_concepts` for details.
290:.. _exp_workshop_definition_connections:
374:.. _exp_workshop_connection_lifecycle:
434:.. _exp_workshop_definition_actions:
546:    * - :ref:`Regular SDKs <exp_sdk_concepts>`
585:- :ref:`exp_sdks`
<shellId: 21 completed with exit code 0>
```

</details>


---

<sub>9m 25s</sub>

### Reasoning

*Now I have all the information I need. Let me now also check if there's a `.dogen/context/doc-style.md` to understand the voice conventions.*

---

<sub>9m 27s</sub>

### `bash`

**Read doc-style for voice conventions**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && cat .dogen/context/doc-style.md

<details>
<summary>213 lines</summary>

````
# Documentation Style Profile

**Repo:** `workshop`
**Generated:** 2026-07-03 09:55
**Source:** 149 doc files, 11 docstring blocks

> This artefact was generated by `repo-scraper` and is intended as
> **steering input** for a documentation generation pipeline.
> It is not end-user documentation.

---

## Purpose of this artefact

This profile describes **how the `workshop` project communicates
about itself** in its documentation. Use it to:
- Match the existing style when generating new docs
- Identify style patterns to preserve or improve
- Brief a writer or LLM on the project's documentation voice

---

## Part 1 — Style Analysis

# Documentation Style Analysis: Workshop / SDKcraft

---

## 1. Voice & Tone

**Predominantly second-person imperative, with a relaxed but authoritative register.**

The tutorials and how-to guides lean heavily on direct address ("you will learn", "you can connect", "here you will practice") combined with imperative instructions ("Install Workshop", "Run this command", "Add the SDK"). The first-person plural appears briefly in tutorial narration ("we'll build an SDK", "let's look at an example") but never in reference or explanation pages.

Passive voice is reserved for system-describing sentences: "SDKs are downloaded from the SDK Store", "the workshop must be in the *Ready* state." This creates a clear split — the human acts imperatively, the system acts declaratively.

Tone is confident without being stiff. The style guide explicitly calls for "water cooler conversation, not classroom session," and this lands: phrases like "All too familiar, isn't it?" (in the Dockerfile comparison) or "let's build something better" signal conversational intent. The register is noticeably more relaxed than, say, Kubernetes documentation, while still being precise.

---

## 2. Audience Assumptions

**Target reader is a developer or DevOps practitioner; ops concepts and CLI fluency are assumed, domain jargon is introduced once then assumed.**

The docs assume:
- Comfort with a Linux terminal, `snap`, YAML, and Git (including worktrees)
- Awareness of containers (Docker, LXD) without requiring mastery
- Ability to read `bash` scripts and systemd unit files without explanation

Terms like "plug," "slot," and "interface" are defined at first use in the tutorial and explanation sections (e.g., "SDKs use interfaces to interact in an organized manner, exposing the resources they provide via slots and consuming them via plugs") but are used as shared vocabulary everywhere else with no re-definition.

There is a clear **role split**: workshop users (developers who consume SDKs) versus SDK publishers (who build and publish SDKs). How-to and tutorial content is labelled and scoped accordingly. The AI-agents how-to further assumes familiarity with specific CLI tools (`claude`, `copilot`) without explaining them.

No "beginner" scaffolding (no "what is YAML?" notes, no "what is a container?" interludes). The tutorial assumes readers already know what a development environment is and why they might want one.

---

## 3. Formatting Conventions

**Hierarchical Diátaxis structure; code-first in tutorials/how-tos; rigid rubric pattern in reference.**

**Section structure:** Tutorial pages follow a narrative arc with named anchors at each step. How-to pages are flat (one task per heading level 2, substeps at level 3). Reference pages use a fixed rubric: *Usage → Description → Examples → Flags → See also*.

**Code blocks are ubiquitous and consistently annotated:**
- Always use `.. code-block::` with a language specifier
- YAML examples almost always include `:caption:` naming the file
- Modified lines are highlighted with `:emphasize-lines:`
- Console blocks use `$` prompt and show both command and representative output

**Admonitions follow a placement rule:** Notes appear at the *end* of the subsection they qualify, not inline mid-paragraph. This prevents interrupting the main flow. Warnings are used for destructive operations ("Don't delete the project directory without first removing the workshop").

**"See also" sections** close every explanation and how-to page, consistently broken into sub-lists by Diátaxis type (Explanation / How-to / Reference / Tutorial), in alphabetical order within each group.

**Semantic line breaks** in RST source (one clause per line) are enforced throughout, giving git diffs a clean appearance.

**Tables** appear for reference data: flag listings, status values, feature comparisons, environment variable tables. List-tables with headers are the dominant form; prose lists are used for shorter enumerations.

---

## 4. Completeness Patterns

**Examples consistently accompany explanations; parameters are comprehensively listed; error states are documented, edge cases variably so.**

**Tutorials:** Every conceptual step is followed immediately by a working command or YAML snippet with expected output. There are no "exercise left to reader" gaps — the reader is walked through complete, copy-pasteable sequences.

**How-to guides:** The pattern is scenario-first (a named use case), followed by YAML and console blocks. Most scenarios show both the definition change *and* the resulting `workshop info` or `workshop connections` output, grounding abstract config changes in observable results.

**Reference CLI pages:** All commands have Usage, Description, Examples, and Flags sections. Flags are described individually with type information. The description blocks use "Notes:" sub-sections for edge-case behaviour (e.g., "If multiple workshops are listed and an error occurs, the operation is aborted").

**Health/error states:** The `workshopctl set-health` contract (okay / waiting / error), the workshop status lifecycle, and rollback behaviour on failed refresh are all explicitly documented. The debug how-to shows sample task output with real error text.

**Gaps:** The tunnel cross-protocol bridging section documents constraints (UDP/Unix incompatibility) but does not show what the error output looks like. The AI agents how-to says agents "presumably" produce certain output, signalling that the scenario is more illustrative than verified.

---

## 5. Overall Quality Signals

**Highly consistent across files; single editorial voice evident; strongest in tutorials and reference; weakest in architecture explanation and contributing guide.**

**Consistency:** The documentation reads as the work of a small, tightly coordinated team with an enforced style guide. Sentence structure, admonition placement, anchor naming (`tut_`, `how_`, `exp_`, `ref_`), YAML caption patterns, and "See also" format are reproduced identically across dozens of files from different surfaces. The presence of the `doc-style-guide.md` and `@artefact` comment system (a machine-readable coverage tracker) suggests active governance.

**Signs of multiple authors:** The contributing guide (`contributing.rst`) has a noticeably more internal/engineering tone ("optimize for commit history clarity", "normalize symmetries") compared to the user-facing docs. The release notes are changelog-like rather than narrative. These are appropriate voice shifts for their audience, not stylistic drift.

**Strongest parts:**
- The four-part tutorial is a model of step-by-step progression with full output shown at each stage.
- CLI reference pages are mechanically complete and uniformly structured.
- The `doc-style-guide.md` itself is unusually thorough and self-consistent.

**Weakest parts:**
- The architecture explanation pages (system components, runtime behavior) feel denser and more diagram-heavy with less prose scaffolding — concepts are named and diagrammed but not narrated at the same depth as, say, the interface explanation pages.
- `coverage.md` is an HTML table embedded in a Markdown file, which breaks the prose documentation convention and is clearly generated output rather than authored content.
- Some explanation articles (e.g., `changes-tasks.rst`) are very short and feel like placeholders that gesture at a concept without fully developing it.

---

## Part 2 — Consistency Analysis

# Documentation Consistency Analysis: Workshop / SDKcraft

---

## 1. TERMINOLOGY DRIFT

### 1.1 Workshop Definition Filename: `.workshop/NAME.yaml` vs `workshop.yaml`

**Severity: Medium**

The tutorial establishes that `workshop init dev` creates `.workshop/dev.yaml`, yet the majority of how-to guides silently switch to using `workshop.yaml` as the YAML caption without explanation.

| Location | Filename used |
|---|---|
| `tutorial/part-1-get-started.rst` | `.workshop/dev.yaml` (created by `workshop init`) |
| `how-to/customize-workshops/add-mounts.rst` | `workshop.yaml` |
| `how-to/customize-workshops/add-actions.rst` | `workshop.yaml` |
| `how-to/customize-workshops/forward-ports.rst` | `workshop.yaml` |
| `how-to/develop-with-workshops/connect-vscode.rst` | `workshop.yaml` |
| `how-to/develop-with-workshops/run-github-actions-locally.rst` | `workshop.yaml` |
| `how-to/develop-with-workshops/run-jetbrains-gateway.rst` | `workshop.yaml` |
| `how-to/develop-with-workshops/manage-python-environments.rst` | `workshop.yaml` |
| `how-to/develop-with-workshops/run-jupyterlab-in-browser.rst` | `workshop.yaml` |

Both forms are valid per `reference/definition-files/workshop-definition.rst`, but that reference does not appear to be linked from any of the how-to guides that make this silent switch. A reader who followed the tutorial will hold a `.workshop/dev.yaml` mental model and won't understand why the how-to guides show a different filename.

The `use-multiple-workshops.rst` how-to correctly explains the difference but does not back-link to justify the single-workshop how-to convention.

---

### 1.2 LXD Minimum Version: 6.8+ vs 6.6+

**Severity: Medium-High**

The LXD prerequisite is stated differently for Workshop versus SDKcraft contexts:

| Location | LXD requirement |
|---|---|
| `tutorial/part-1-get-started.rst` | "LXD 6.8+" |
| `tutorial/part-4-craft-sdks.rst` | "LXD 6.8+" |
| `how-to/develop-sdks/build-an-sdk.rst` | "LXD 6.6 or later" |
| `how-to/develop-sdks/publish-an-sdk.rst` | "LXD 6.6 or later" |

A contributor developing their first SDK will encounter a lower version requirement than a workshop user, which may cause confusion about the actual system requirement. If 6.8 is needed for the full system, the SDKcraft guides are stale. If 6.6 genuinely suffices for SDKcraft alone, that distinction needs to be made explicit.

---

### 1.3 `check-health` Waiting State: Retry Count

**Severity: Low**

The number of retries before `waiting` escalates to `error` is described inconsistently:

- `tutorial/part-4-craft-sdks.rst`: *"the health is eventually set to error automatically"* — no count given, implies "a few seconds"
- `explanation/sdks/runtime-hooks.rst`: **"After ten consecutive waiting results, the SDK is moved to Error"** — explicit count

The explanation document is authoritative here, but the tutorial's vaguer language could mislead SDK authors into thinking the window is more or less than ten attempts.

---

### 1.4 `$SDK_STATE_DIR` Lifetime

**Severity: Low-Medium**

The state directory lifetime is described with conflicting framing across three pages:

- `explanation/sdks/runtime-hooks.rst`: *"pointing at a directory that **survives the refresh**"*
- `reference/sdks.rst` (`ref_sdk_state`): *"removed when the workshop **stops**"*
- `how-to/develop-sdks/write-runtime-hooks.rst`: *"the directory is **gone as soon as the workshop stops**"*

The last two are consistent. The first is technically accurate (it persists from `save-state` to `restore-state` within a single refresh cycle) but in isolation reads as if the directory persists indefinitely. SDK authors relying only on the explanation page could be surprised to find the state directory absent at runtime after a refresh completes.

---

## 2. STRUCTURAL INCONSISTENCIES

### 2.1 Invalid YAML in `run-jupyterlab-in-browser.rst`

**Severity: High (broken example)**

The code block in `how-to/develop-with-workshops/run-jupyterlab-in-browser.rst` has a YAML indentation error:

```yaml
 name: dev
 base: ubuntu@24.04
 sdks:
 - name: system      ← same indentation level as sdks:, not nested under it
   plugs:
     jupyter:
       interface: tunnel
       endpoint: 127.0.0.1:8989
 - name: jupyter
```

Every other workshop definition in the docs uses the correct form:

```yaml
sdks:
  - name: system
```

This YAML would fail to parse as written. Contrast with the correct form in `tutorial/part-2-work-with-interfaces.rst` which shows the same pattern correctly.

---

### 2.2 Internal Contradiction Within `reference/sdks.rst`

**Severity: High**

Within the same page (`docs/reference/sdks.rst`), the text states:

> "Slots can only be defined for the `:samp:mount` interface."

— and then immediately below, in the **Tunnel interface** section of the same page, provides a slot definition example:

```yaml
slots:
  <NAME>:
    interface: tunnel
    endpoint: <ENDPOINT>
```

This is an outright contradiction on a single reference page. The tunnel slot syntax is used throughout the documentation (in `tutorial/part-2-work-with-interfaces.rst`, `explanation/sdks/best-practices.rst`, the ollama SDK example in `tutorial/part-4-craft-sdks.rst`), confirming that tunnel slots are real and supported. The "mount only" statement is simply incorrect.

---

### 2.3 Cross-section Navigation: SDK Authoring Guide Linked from Workshop User Guide

**Severity: Low**

`how-to/customize-workshops/add-mounts.rst` (a workshop-user guide) links in its "See also" section to:

```
:ref:`how_configure_mount`
```

This resolves to `how-to/develop-sdks/configure-mount.rst`, which is an **SDK authoring** how-to guide under `develop-sdks/`. A workshop user following the mount how-to who clicks through will land unexpectedly in SDK publisher territory, with no contextual explanation of why the distinction matters.

---

### 2.4 `use-workshops-with-ai-agents.rst` Uses `.workshop.yaml` Caption

**Severity: Low**

This how-to uses `.workshop.yaml` (dot-prefixed root file) as its definition caption, which is valid but is the least common of the three valid forms. None of the tutorial or other how-to guides use this form. The difference is not flagged, and coupled with the broader `workshop.yaml` vs `.workshop/NAME.yaml` confusion (§1.1), this adds a third variant into the mix without explanation.

---

## 3. CONFLICTING DESCRIPTIONS

### 3.1 Tunnel Slots: Mount-Only Claim vs Documented Tunnel Slots

**Severity: Critical**

This is the most concrete factual contradiction in the documentation set.

**Claim in `reference/sdks.rst`:**
> "Slots can only be defined for the `:samp:mount` interface."

**Contradicted by:**

| Location | Evidence |
|---|---|
| `reference/definition-files/sdk-definition.rst` | "Only the `mount` and `tunnel` interfaces support slots on regular SDKs." |
| `reference/definition-files/sdkcraft-definition.rst` | Same language: "Only the `mount` and `tunnel` interfaces support slots here." |
| `tutorial/part-4-craft-sdks.rst` | Ollama SDK defines `ollama-server` tunnel slot |
| `explanation/sdks/best-practices.rst` | Shows tunnel slot definition as a best-practice example |
| `tutorial/part-2-work-with-interfaces.rst` | `workshop connections` output shows `dev/ollama:ollama-server` tunnel slot |

The `sdk-definition.rst` and `sdkcraft-definition.rst` references are authoritative and internally consistent. The sentence in `sdks.rst` is a leftover from an earlier implementation or a copy-paste error.

---

### 3.2 LXD Version Requirements (Detailed)

As enumerated in §1.2, the 6.8+ requirement stated in all Workshop tutorial content conflicts with the 6.6+ stated in the SDKcraft how-to guides. Readers preparing to build and publish SDKs may install LXD 6.7 based on the SDKcraft prerequisites, only to find that the full Workshop runtime requires 6.8.

---

### 3.3 `workshop restore` Hook Execution Ambiguity

**Severity: Low-Medium**

`reference/sdks.rst` (the `ref_sdk_hooks` table) states that `setup-project`, `save-state`, `restore-state`, and `check-health` all run during `workshop restore`. However, the explanation in `explanation/workshops/concepts.rst` says:

> "No SDK changes are applied; the container filesystem is rolled back to the snapshot it had right after the last successful launch or refresh, discarding any changes made inside the workshop since then."

If no SDK changes are applied and it's purely a filesystem rollback, it's unclear why `save-state`/`restore-state` would run (there is no "old vs new" SDK revision to preserve state across). `how-to/develop-sdks/write-runtime-hooks.rst` further states: *"`save-state` and `restore-state` only run when `workshop refresh` has work to do: a new SDK revision to swap in, an added or removed SDK, or a change to the workshop definition."* This directly contradicts the reference table's claim that they run during `workshop restore`.

---

## 4. RECOMMENDATIONS

### Top 3 Highest-Impact Changes

**1. Fix the `reference/sdks.rst` "mount-only slots" error**

The single sentence "Slots can only be defined for the `mount` interface" in `docs/reference/sdks.rst` is factually wrong and directly contradicts three other reference pages plus the tutorial. Replace it with the correct language used in `sdk-definition.rst`:

> "Slots can be defined for the `mount` and `tunnel` interfaces."

This is a one-line fix that eliminates a high-severity contradiction on a reference page.

**2. Standardize the LXD version prerequisite**

Audit whether LXD 6.6 or 6.8 is the true minimum requirement. Unify it across all four affected pages (`part-1-get-started.rst`, `part-4-craft-sdks.rst`, `build-an-sdk.rst`, `publish-an-sdk.rst`). If the version differs between Workshop and SDKcraft, explicitly state *why* in the SDKcraft prerequisites.

**3. Fix the `run-jupyterlab-in-browser.rst` YAML syntax error**

The misaligned `sdks:` list items will cause any reader who copies the code block to experience a confusing parse failure. Correct the indentation to match the form used everywhere else in the docs:

```yaml
name: dev
base: ubuntu@24.04
sdks:
  - name: system
    plugs:
      jupyter:
        interface: tunnel
        endpoint: 127.0.0.1:8989
  - name: jupyter
```

---

### What a New Contributor Would Find Most Confusing

**The filename problem is the most likely day-one stumbling block.** A new contributor reads the tutorial, runs `workshop init dev`, gets `.workshop/dev.yaml`, then opens any how-to guide to extend their setup and encounters `:caption: workshop.yaml` everywhere. The reference says both are valid, but the reference isn't linked from the how-to guides, and there's no callout saying "this guide uses the single-workshop convention; if you used `workshop init`, your file is at `.workshop/dev.yaml`."

The second most confusing issue is the tunnel-slot contradiction: a contributor implementing their first SDK, reading `reference/sdks.rst` to understand what they can put in an SDK definition, will conclude they cannot create tunnel slots — directly contradicting the tutorial they may have just completed and the best-practices page they may have read.
<shellId: 23 completed with exit code 0>
````

</details>


---

<sub>9m 30s</sub>

### Reasoning

*Now I have a very comprehensive picture. Let me now also check the `docs/reference/workshops.rst` for the existing workshop reference page and understand what `workshop.yaml` filename conventions are documented there.*

---

<sub>9m 34s</sub>

### `bash`

**Skim existing workshops.rst reference**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && head -80 docs/reference/workshops.rst

<details>
<summary>58 lines</summary>

```
.. _ref_workshop_internals:

.. meta::
   :description: Reference guide to Workshop internals, covering container-based
                 environments, SDK layering, and user/session management.

Workshop internals
==================

This topic speaks about what goes into building and running a workshop.


What a workshop is
------------------

.. @artefact workshop (container)
.. @artefact workshopd

A workshop is a development environment running in a container,
mapping your project to its contained dependencies.
It is fully described in a :ref:`definition file <ref_workshop_definition>`.

|ws_markup| currently uses LXD as its container engine,
communicating to it via the socket-activated :program:`workshopd` backend,
but that is an implementation detail and potential subject to change.

When you launch a workshop, you create and start a container with a base image.
The image is downloaded from the container engine server and cached locally.

.. @artefact SDK
.. @artefact SDK Store

On top of the base image, one or more SDKs are usually applied,
which provide tools for development and runtime tasks.
SDKs are downloaded from the SDK Store that is specific to |ws_markup|.

SDKs are installed in the order dictated by the workshop definition:
first :samp:`system`, then user-listed SDKs, and finally :samp:`sketch`.
Each SDK's :samp:`setup-base` hook runs immediately after that SDK is installed;
this serves to customize the workshop
and prepare each SDK for use before proceeding further.

After all SDKs are installed,
the following hooks execute sequentially in the same deterministic order:
:samp:`setup-project` hooks run first to prepare the project environment,
followed by :samp:`check-health` hooks to verify the workshop is ready for use.

The host user running |ws_markup| is mapped to the default workshop user,
named :samp:`workshop` in the container,
with :samp:`uid=1000` and :samp:`gid=1000`.
This ensures that files and directories changed by the :samp:`workshop` user
inside the container map back to the same user on the host,
preserving consistent ownership and permissions.


User sessions and ID mapping
----------------------------

.. @artefact workshop exec
.. @artefact workshop run
.. @artefact workshop shell

By default, all commands that execute something inside a workshop
(:command:`exec`, :command:`run`, :command:`shell`)
run login shells as :samp:`uid=1000` and :samp:`gid=1000`,
unless you explicitly change the IDs.
This ensures files created inside the container map back to the host user.

By default, :envvar:`$XDG_RUNTIME_DIR` is set to :samp:`/run/user/1000/`,
and a user-scoped session bus address is created at :samp:`/run/user/1000/bus`.
Using other IDs can break sessions.

Finally, it's worth mentioning that having an active session
doesn't prevent :command:`refresh` or any other change from running.
However, you may need to restart the session to see the effect.


How workshops are built
-----------------------
<shellId: 24 completed with exit code 0>
```

</details>


---

<sub>9m 34s</sub>

### `bash`

**Check workshop.rst for filename/location docs**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "^.. _\|filename\|Filename\|workshop.yaml\|\.workshop" docs/reference/workshops.rst | head -20

```
1:.. _ref_workshop_internals:
<shellId: 25 completed with exit code 0>
```


---

<sub>9m 37s</sub>

### Reasoning

*Now I have all the information I need to author the `workshop-definition.rst` page. Let me now plan and then write the page.

Key facts gathered:
1. **Filename and location**: `workshop.yaml` or `.workshop.yaml` at project root; under `.workshop/\<NAME>.yaml` when using `workshop init`
   - From workshop_file.go: `Filenames = []string{"workshop.yaml", ".workshop.yaml"}` and `Directory = ".workshop"`, `func filename(name string) string { return fmt.Sprintf("%s.yaml", name) }`
   - From doc-style.md: terminology drift issue with `workshop.yaml` vs `.workshop/NAME.yaml` - both are valid
2. **Top-level fields**: The schema includes `name`, `base`, `sdks`, `connections`, and `actions` as the primary sections.
3. **Name constraints**: Must start with a lowercase letter, contain only lowercase letters, digits, and hyphens, with a maximum of 40 characters, following the pattern `^[a-z](?:-?[a-z0-9])*$`.
4. **Base values**: Supports Ubuntu versions 20.04, 22.04, 24.04, and 26.04.
5. **SDK entries**: Each SDK can have a `name` with optional prefixes (`try-` for locally tried, `project-` for in-project, or no prefix for Store SDKs), must contain at least one lowercase letter, and has character limits depending on the prefix. The `channel` field specifies the release track and risk level (stable, candidate, beta, edge) with a default of `latest/stable`, and applies only to Store SDKs. There's also an optional `plugs` map for additional configuration.

6. **Connections**: Each connection entry requires both a `plug` and `slot` field to establish relationships between components.

7. **Actions**: The `actions` map contains action names as keys with shell script values that execute with bash in login shell mode, supporting positional parameters for arguments.

Now I'm structuring the documentation page with metadata and a reference section for the workshop definition.

The `workshop.yaml` file is what the system reads when launching or refreshing a workshop, either authored manually or generated with the init command. The system looks for it in three possible locations: as `workshop.yaml` at the project root, as `.workshop.yaml` for keeping it hidden from version control, or as a named file under `.workshop/` directory where the filename must match the workshop name.

Now I'm looking at the top-level fields that define a workshop, starting with required fields like `name` and `base` for the OS image, followed by optional fields like `sdks` for specifying which software development kits to install.

The `name` field has specific constraints: it must start with a lowercase letter, can include lowercase letters, digits, and hyphens between characters, with a maximum of 40 characters total, following the pattern of lowercase alphanumeric with optional hyphens.

The `base` field specifies the Ubuntu operating system image for the workshop container, with options including Ubuntu 20.04 LTS and Ubuntu 22.04 LTS.

Continuing the table with Ubuntu 24.04 LTS and Ubuntu 26.04 LTS as additional base options. SDKs must match the workshop's declared base, though SDKs without a base declaration work with any workshop. The `sdks` field lists SDK entries that are installed in order on top of the base image, with each SDK name appearing only once in the list. Generating documentation table... The channel format follows a pattern of track, risk level, and optional branch, where risk defaults to stable if not specified. Track names can use alphanumerics with separators up to 28 characters, branch names up to 128 characters, and both must avoid matching reserved risk names like stable, candidate, beta, or edge. The default channel is latest/stable when omitted.

Now I'm looking at how plugs are defined in the workshop configuration—they're named with lowercase letters and hyphens, and can be specified either as inline definitions with an interface type and attributes, or using shorthand notation where a string names the interface directly or null inherits it from the plug name itself. Slot names follow the same naming convention as plugs, and each slot can be defined inline with an interface and attributes, or simply as a string referencing the interface type. Workshop-level slots extend the SDK's built-in slot definitions. The connections field then lists explicit plug-to-slot wires that layer on top of any automatic connections, with each entry requiring both source and target keys.

Generating markdown table... Arguments passed after `--` are available as positional parameters in the script. I'm also including the JSON schema that defines the complete structure of the workshop.yaml file, followed by examples showing a minimal workshop, one with plug bindings, and another with explicit connections and inline definitions.

Now I'm double-checking the schema details—specifically that the `source` field in `SdkRecord` is derived from the name prefix rather than being a separate YAML field, so I shouldn't document it as an independent field. I see the `MarshalYAML` method handles the source field by encoding it as a prefix in the name (like "try-" or "project-"), then clearing the source field before marshaling. So the YAML schema only exposes `name`, `channel`, `plugs`, and `slots` as the user-facing fields. Now I'm looking at the `Action` type and its validation logic.

Validating action names... I'll stick with what the schema explicitly states about arguments being passed to the action, without overspecifying the CLI syntax I haven't fully verified. For the file location section, I'm looking at how the code constructs the workshop directory structure—it uses `.workshop` as the directory with `workshop.yaml` or `.workshop.yaml` as possible filenames, and builds paths by joining the project directory with this structure.

The `source` field appears to be internal only, not user-authored in the YAML, since the SDK record schema only exposes `name`, `channel`, `plugs`, and `slots`. Now I'm checking my outline coverage to see what's been addressed so far. I'm double-checking the Actions section to make sure I'm describing user-facing behavior correctly — the bash environment setup and how positional parameters work are things users need to know. I'm also verifying that workshop authors can indeed define slots in their SDK entries, which the schema confirms as "additional slot definitions grafted onto the SDK by the workshop." Now I'm looking at how implicit SDKs are handled in the code. System SDK plugs can't be used in bindings, and each SDK name must appear only once in the list. I'm reconsidering whether "implicit" is the right term for `system` and `sketch` — they don't need to be listed but can be if the user wants to attach plugs or slots to them, similar to how `cuda` appears in the workshop example.

Let me look more carefully at how connections are validated to understand the SDK reference rules better. So both the plug's SDK and the slot's SDK need to exist in the workshop's SDK list or be implicit SDKs. Looking at the JSON schema, I notice the connection patterns allow for an empty SDK part, which means you can reference the system SDK implicitly by writing something like `:ssh-agent`. Let me check what the `bind` field specifies for plugs.

The bind target has a specific constraint—it must be in the form `\<sdk>:\<plug>` where the SDK cannot be "system", and the validation logic confirms this by rejecting any attempt to bind a system SDK plug or bind to a system SDK plug.

Looking at the validation checks, the target SDK must either be an implicit SDK (like sketch) or exist in the workshop's SDK list. Let me trace through what `IsImplicitSdk` actually returns to understand which SDKs qualify as valid bind targets. The schema only blocks the system SDK, not sketch, so theoretically you could bind to sketch. But I'll keep the explanation simple and just note what's actually validated—that the target plug can't belong to the system SDK. I'm getting confused about which SDK is which here though; let me clarify that `sl.Sdk` refers to the workshop SDK containing the binding plug, not the target SDK.

So the two constraints are: a plug from the system SDK can't be bound, and a plug from the system SDK can't be the target of a bind. This makes sense since the system SDK is always present and provides baseline functionality.

Now I'm drafting the documentation page, being careful about the reStructuredText format with proper heading levels, using list tables for structured data, code blocks for YAML examples, and setting up anchors for cross-references.

I'm also checking the SdkRecord struct to understand the YAML schema — specifically looking at how the `source` field is defined and whether it's user-authored or derived.

Actually, I need to reconsider this. The MarshalYAML method clears the source field before marshaling to YAML, and the UnmarshalYAML method derives the source from the name prefix instead of reading it directly from the YAML.

When decoding, the `type record SdkRecord` pattern prevents infinite recursion and allows all YAML-tagged fields to be decoded, but then `parseSdkName` immediately overrides whatever source value was decoded. However, the JSON schema shows `additionalProperties: false` and doesn't even list `source` as a valid property, so it shouldn't be present in the YAML to begin with.

Looking at the validation flow in `readWorkshop`, there's a YAML unmarshal followed by schema validation, but the `UnmarshalYAML` for `SdkRecord` doesn't enforce unknown-field checking. This means a user could technically include a `source:` field in their YAML and it would be decoded without triggering an error.

However, the JSON schema is the authoritative definition here—it doesn't list `source` as a valid property, so I should document what the schema actually specifies. I'm also reconsidering the `slots` field, which can be added at the workshop level per SDK entry, as shown in the `workshop-digits-cuda.yaml` example where the `imagenet` SDK has additional slot definitions. I need to clarify what "after the workshop name" means in the schema description for action scripts. Looking at the examples like `tests: go test "$@"`, it's clear that `$@` receives the arguments, so the phrasing probably refers to arguments passed via `--` on the command line rather than literally after the workshop name itself. I should check the `workshop run` reference documentation to confirm how arguments are actually passed through the CLI.

Now I'm verifying the anchor labels I'll need: `exp_workshop_concepts` for the concepts page, `exp_workshop_definition` for the definition section, and `ref_workshop_init` and `ref_workshop_run` for the command references. I also need to reconsider the schema for the `plugs` map, where each plug value can be `null` to use the key as the interface name, a string specifying the interface name, or a mapping with more complex configuration. with `interface` and attributes, a mapping with `bind` key, or a string naming the interface. The four possible forms are: null (using the key as the interface name), a string (the interface name), a mapping with interface-specific attributes, or a binding reference with a `bind` key pointing to another plug. The workshop-level plugs augment or override the SDK's own plugs, so I need to be careful not to over-specify the merge behavior since I haven't reviewed the implementation. There's also a gap around how the `source` field in YAML gets handled—it might be silently ignored or cause a strict validation error. Now I'll write out the complete documentation page in reStructuredText format to match the other pages in this section. that the interface-specific attributes are documented in the SDK definition's interfaces reference rather than re-documenting them here, since workshop.yaml uses those same interface types. I need to verify which interfaces are actually supported at the workshop.yaml SDK entry level though.

For the reference page, I'll describe the plugs map structure, note that each value can be an inline plug definition, interface shorthand, or binding, and cross-reference the SDK definition's interfaces section for attribute details. Looking at the digits-cuda example, I can see how the mount interface is used with workshop-target to specify where the plug should be mounted. The `source` field isn't actually user-facing since the UnmarshalYAML function overrides it, and while JSON Schema validation would flag it as an error, the runtime just uses yaml.Unmarshal without schema enforcement, so it gets silently ignored. This means the field is really just for tooling and IDE support rather than actual validation.

Now I need to structure the documentation page. Looking at the outline, I should have a top-level fields table showing name, base, sdks, connections, and actions with their types and descriptions, then separate subsections for the constraints on name and base values. I'm deciding between having individual subsections for each field versus grouping everything into one constraints section, and I'm checking how the sibling documentation handles this.

I also need to make sure I use the correct anchor label `.. _ref_workshop_definition:` since other pages are already linking to it. Let me write out the complete reference page now.

Writing the workshop definition reference... Generating markdown table... Generating markdown table... Continuing with the channel field description, then covering the plugs and slots object fields that can be defined for each SDK entry, along with a note that no other keys are permitted. The SDK name field identifies which SDK to install, with an optional prefix determining where it comes from. The `system` and `sketch` SDKs are built-in and automatically installed, though they can appear in listings to attach workshop-specific overrides. The `channel` field specifies which Store channel to use for retrieving SDKs, defaulting to `latest/stable` when not specified, and follows a format like `[\<track>/]\<risk>[/\<branch>]` where risk includes options like `stable`, `candidate`, and `beta`. Plugs can be defined inline with an interface key and interface-specific attributes, specified as a string or null for shorthand, or bound to another SDK's plug using a bind key with a reference in the form `\<sdk>:\<plug>`.

Bound plugs have constraints: they can't define other attributes, can't appear in connections, the target plug can't be bound, and neither can belong to the system SDK. Now I'm moving on to slots, which map slot names to slot definitions that layer on top of the SDK's own slots—slot names follow the same lowercase letter and hyphen rules as plug names. Continuing with the table structure, each connection entry requires a plug and slot reference in the format of `\<sdk>:\<name>`, where the SDK portion can be omitted to reference the system SDK. Both endpoints must point to an SDK that's listed in the sdks field or is one of the implicit ones like system or sketch.

Now looking at the actions section, which defines named shell scripts accessible through the workshop run command. Action names follow the same format as workshop names—starting with a lowercase letter and using only lowercase letters, digits, and hyphens. Each action is a YAML string (typically using literal blocks for multi-line scripts) that executes as a bash login shell with error handling flags enabled. Finishing up the example with the CUDA workshop configuration, then moving into a coverage checklist to verify the documentation covers filename location, top-level fields with their types and requirements, and name/base constraints. I'm checking that I haven't used implementation identifiers in the prose and verifying the runtime behavior is user-observable rather than internal mechanics. Now I'm validating the relative paths for the included files — the schema.json reference and the example YAML files all resolve correctly from the workshop definition page location. `ref_workshop_run` is at line 193 of `docs/explanation/workshops/concepts.rst`. ✅

Now I'm checking the reStructuredText formatting - list-table and code-block directives need 3-space indentation for their content, and I'm verifying the options like `widths` are properly positioned under the directive. Looking at how the sibling pages structure their dropdowns with literalinclude directives to make sure I'm following the same pattern.

I should confirm that `schema.json` exists at the same directory level and contains the workshop schema, which I've already verified from the JSON content. The `dropdown` directive is clearly supported since it's used elsewhere in the codebase. I'm focusing on documenting the user-facing interface rather than internal implementation details like the `source` field.

Looking at the actual workshop YAML files, none of them include a `source` field, confirming it's derived internally and not something users need to specify. For the report.yaml documentation, I'm identifying two main gaps: the interface-specific semantics for plug/slot values like `workshop-target` and `workshop-source` (which are defined in the SDK interfaces), and the exact bash invocation details for actions.

But reconsidering—the first gap isn't really a gap since I'm cross-referencing to those interfaces anyway. The second one about CLI invocation details belongs to the `workshop run` command documentation, not the workshop.yaml reference page itself. The real gap I should focus on is understanding the merge semantics when workshop-level slot definitions interact with the SDK's own slot definitions—specifically what happens if there's a naming conflict or overlap.

Let me verify a couple of constraints before I finalize this. I'm checking the validation logic to confirm that neither the binding plug nor the target can belong to the system SDK, and that a target plug can't already be bound to something else.

Looking at the schema and the example from `workshop-go-dev.yaml`, I can see how binding works at the workshop level: a plug from one SDK entry binds to a plug from another SDK entry, like `project-cache`'s `data` plug binding to `go`'s `mod-cache` plug.

In `validateBinding`, both the source SDK (`project-cache`) and target SDK (`go`) are checked, and neither can be "system". There's also validation that the target SDK must either exist in the workshop's SDK list or be an implicit SDK like sketch. Since system is already blocked, only sketch would qualify as an implicit binding target, and I should add this constraint to the validation logic. I'm settling on a simpler constraint: the target SDK must be present in the workshop's SDK list, keeping the reference page clear and avoiding edge cases that might confuse readers. Looking at the validation logic, I can see that sketch is treated as an implicit SDK, so you can bind to it without explicitly listing it in the workshop's SDK entries. However, the schema pattern seems to prevent system-prefixed SDKs, which creates an inconsistency I need to clarify in the documentation. Checking the validation logic...

So the target SDK in a bind is allowed if it's either an implicit SDK like sketch, or if it's explicitly listed in the workshop's SDKs. System is blocked earlier, so the practical rule is: you can bind to any listed SDK or to sketch, but not to system. I'll document this clearly.

Looking at the reference documentation standards, I need to be accurate and complete, so I should include the sketch detail. The sibling pages use bullet lists for constraints, so I'll follow that format and write the final version now.

Writing the reference page... The table continues with the remaining configuration fields: `base` for the OS image, `sdks` for SDK installations, `connections` for plug-to-slot wiring, and `actions` for named shell scripts that can be executed via the workshop command. No other keys are permitted in the configuration.

Now I'm detailing the constraints for the `name` field—it must start with a lowercase letter, can include lowercase letters, digits, and hyphens between characters, with a maximum of 40 characters matching the pattern for valid workshop identifiers. The `base` field specifies which Ubuntu release to use as the container image, with accepted values listed in a reference table. The SDK list entries are installed in order on top of the base image, with the system SDK applied automatically first. Each SDK entry requires a name field and optionally includes channel and plugin configuration, with each SDK appearing only once in the list. The SDK name can use prefixes like `try-` for locally tested SDKs or `project-` for in-project SDKs, and the underlying name must follow specific rules: at least one lowercase letter, only lowercase letters and digits with hyphens between them, not reserved names like `agent`, and within character limits depending on the prefix. The system and sketch SDKs are implicit and install automatically, though you can list them explicitly to configure workshop-specific settings.

The `channel` field specifies which Store channel to pull the SDK from, defaulting to `latest/stable` if omitted, though it doesn't apply to locally tried, project, system, or sketch SDKs. The channel format follows a pattern of track, risk level, and optional branch, where risk can be stable, candidate, beta, or edge.

Now I'm looking at the `plugs` key, which maps plug names to their definitions or bindings. Plug names follow a specific pattern starting with a lowercase letter and containing only lowercase letters, digits, and hyphens between characters. Each plug value can be either an inline definition with an interface key or other forms. Now I'm looking at the constraints on plug bindings—a bound plug can't have other attributes, can't appear in connections, and the target plug itself can't be bound. I'm also noting that neither the binding nor target plug can belong to the system SDK, and the target SDK must be listed in the workshop's SDK entries or be sketch. Then I'm moving into the slots section, which supplements the SDK's own slot definitions with names following the same lowercase letter and hyphen pattern as plugs. Continuing the table with the plug and slot reference formats, both required fields that follow the pattern of SDK name and identifier, along with constraints that both endpoints must reference listed SDKs or implicit ones like system and sketch.

Now I'm looking at the actions section, which defines named shell scripts available through the workshop run command. Action names follow the same pattern as workshop names—starting with lowercase letters and containing only lowercase letters, digits, and hyphens. Each action is a YAML string containing the script body, typically using literal blocks for multi-line scripts, and the script executes as a bash login shell with error handling flags set.

The next part covers the JSON schema that describes the complete structure of workshop.yaml files, followed by practical examples showing a minimal workshop setup, one with plug bindings across multiple SDKs, and another with explicit connections and inline definitions. Verifying the annotation patterns match across the documentation files and confirming the reference anchors are correct. I need to record all the files I've reviewed and the commit hash for the report. , and style guidelines)
18. `.dogen/context/doc-structure.md` (hierarchy and organization)

I've reviewed the workshop file structure, schema definitions, and example configurations to understand how workshops are defined and validated. I'm also examining the documentation structure and style guidelines to ensure consistency across reference pages.

I'm noting a couple of gaps: the exact conflict resolution when workshop-level slot definitions clash with SDK-level ones isn't explicitly verified in the schema or code I've reviewed—the schema just says they're "grafted on top"—and I need to clarify the exact bash invocation syntax for actions, particularly whether `--` is required to separate the action name from its arguments.

Now I need to finalize the report by setting up the staging directory and writing both files, but first I should ask the TA about the model identity before running the dogen draft command, since the instructions say to ask them once if the harness doesn't expose it programmatically.

Actually, I can see from the system context that my model is Claude Sonnet 4.6, so I'll pass `--model claude-sonnet-4.6` to the dogen command and proceed with creating the files.*

---

<sub>15m 10s</sub>

### Copilot

Excellent grounding. Now I'll navigate a few more files before authoring.

---

<sub>15m 13s</sub>

### `bash`

**Confirm explanation anchor labels**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "^.. _\|workshop_definition\|exp_workshop" docs/explanation/workshops/concepts.rst | head -15

<details>
<summary>16 lines</summary>

```
1:.. _exp_workshop_concepts:
31:.. _exp_workshop_status:
78:.. _exp_workshop_lifecycle:
133:.. _exp_workshop_launch:
142:see :ref:`exp_workshop_definition_sdks` for the layering details.
150:.. _exp_workshop_refresh:
172:.. _exp_workshop_restore:
193:.. _exp_workshop_definition:
229:.. _exp_base:
243:.. _exp_workshop_definition_sdks:
290:.. _exp_workshop_definition_connections:
374:.. _exp_workshop_connection_lifecycle:
434:.. _exp_workshop_definition_actions:
534:    * - :ref:`Workshop definition <exp_workshop_definition>`
571:    * - :ref:`Actions <exp_workshop_definition_actions>`
<shellId: 26 completed with exit code 0>
```

</details>


---

<sub>15m 13s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/conf.py.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/conf.py (lines 180-200)

<details>
<summary>18 lines</summary>

```
    "examples/*",
]

# Inlined from former docs/reuse/links.txt and docs/reuse/substitutions.txt.
rst_epilog = """
.. _Canonical website: https://canonical.com/
.. _GitHub: https://github.com/canonical/workshop/
.. _LXC: https://documentation.ubuntu.com/lxd/latest/explanation/lxd_lxc/
.. _LXD: https://documentation.ubuntu.com/lxd/latest/
.. _SDKcraft: https://github.com/canonical/sdkcraft/
.. _Releases: https://github.com/canonical/workshop/releases/

.. |ws_markup| replace:: :program:`Workshop`
.. |sdk_markup| replace:: :program:`SDKcraft`
"""

# Specifies a reST snippet to be prepended to each .rst file.
# This defines a :center: role that centers table cell content.
# This defines a :h2: role that styles content for use with PDF generation.
rst_prolog = """
.. role:: center
```

</details>


---

<sub>15m 13s</sub>

### `bash`

**Create staging directory**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && mkdir -p .dogen/staging/workshop-definition

```

<shellId: 27 completed with exit code 0>
```


---

<sub>15m 18s</sub>

### Reasoning

*Now I have everything I need. Let me write the handoff.rst and report.yaml files.

I know:
- `|ws_markup|` = `:program:`Workshop``
- `|sdk_markup|` = `:program:`SDKcraft``
- The labels are confirmed
- The commit hash is `25d76b730f865d52e824a862bab6c96103ce01a0`
- Model is `claude-sonnet-4.6`

Let me now create the handoff file and the report.*

---

<sub>15m 19s</sub>

### Copilot

All facts confirmed. Writing the handoff page now.

---

<sub>16m 17s</sub>

### `create`

**create a new file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/handoff.rst.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/handoff.rst

```
Created file /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/handoff.rst with 11163 characters
```


---

<sub>16m 17s</sub>

### Copilot

Now the context report:

---

<sub>16m 27s</sub>

### `create`

**create a new file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/report.yaml.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/report.yaml

```
Created file /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/report.yaml with 3163 characters
```


---

<sub>16m 30s</sub>

### `bash`

**Record draft via dogen CLI**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen draft "workshop-definition" \
  --draft-file ".dogen/staging/workshop-definition/handoff.rst" \
  --report ".dogen/staging/workshop-definition/report.yaml" \
  --provider host-harness \
  --model "claude-sonnet-4.6" \
  --json 2>&1

```
19:22:58.527 dogen.draft
git: committed 794514a — dogen(workshop-definition): drafted — draft #1 via host-harness
{"unit": "workshop-definition", "provider": "host-harness", "draft_path": "/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/workshop-definition.rst", "progress": "drafted", "reason": null, "stale_plan": false, "unsteered_redraft": false, "commit": "794514a514ad2db1c64d7332cf821406b57bf887"}
<shellId: 28 completed with exit code 0>
```


---

<sub>16m 34s</sub>

### Copilot

Draft recorded cleanly. Here's the summary:

---

## dogen-write: workshop-definition

- **Provider:** host-harness (claude-sonnet-4.6)
- **Handoff:** `.dogen/staging/workshop-definition/handoff.rst`
- **Report:** `.dogen/staging/workshop-definition/report.yaml`
- **Recorded draft:** `docs/reference/definition-files/workshop-definition.rst`
- **Committed:** `794514a` — `dogen(workshop-definition): drafted — draft #1 via host-harness`
- **Progress:** drafted
- **Plan:** fresh (no stale plan)

The page covers all outline items: filename/location, top-level fields table, name and base constraints, SDK entries (name, channel, plugs, slots with binding syntax), connections, actions, JSON Schema dropdown, three worked examples, and see-also links. One gap recorded: slot name-collision semantics between workshop-level and SDK-level definitions.

**Next: invoke `dogen-review` to review the draft.**

---

<sub>17m 9s</sub>

### User

yo

---

<sub>17m 12s</sub>

### Reasoning

*The user just said "yo" - a casual greeting. I should respond briefly and check if they need anything.*

---

<sub>17m 12s</sub>

### Copilot

Hey! The draft is recorded at `docs/reference/definition-files/workshop-definition.rst`. Ready to review it, or something else on your mind?

---

<sub>17m 17s</sub>

### User

/dogen-review

---

<sub>17m 20s</sub>

### Reasoning

*The user wants me to invoke the "dogen-review" skill.*

---

<sub>17m 21s</sub>

### `skill`

**dogen-review**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "dogen-review"
}
```

</details>

```
Skill "dogen-review" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>17m 25s</sub>

### Reasoning

*Let me follow the skill instructions. First, I need to:
1. Read the unit state with `dogen unit show "workshop-definition" --json --latest`
2. Read the unit's sidecars and the drafted page
3. Load the reference files
4. Select review mode

Let me start by reading the unit state and all relevant files in parallel, and also load the reference files.*

---

<sub>17m 29s</sub>

### `bash`

**Read unit state**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen unit show "workshop-definition" --json --latest 2>&1

```
{"unit": {"schema_version": 1, "unit_id": "workshop-definition", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "title": "Workshop definition", "sources": [{"path": "internal/workshop/workshop_file.go", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/reference/definition-files/schema.json", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/examples/workshop-golang.yaml", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}], "sphinx_target": "reference/definition-files/workshop-definition.rst", "extra_targets": [], "steering_notes": "The page must give workshop users everything they need to get any field in workshop.yaml right without consulting another page; it should cover every field's type, whether it is required, its default, and its constraints (name format, accepted bases, valid action names), structured so it works both as a first-read introduction and a quick-lookup reference for experienced users arriving from elsewhere."}, "format": "rst", "progress": "drafted", "signoff": {"author": "Artem Konev", "at": "2026-07-04T18:12:07.674646+00:00", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "plan_hash": "fe06b324249c9d5f9da3e9fa0aefed5ab5e45814fbe5b0a1dea423c0af0e3ece", "commit": "4f7b67d0dd7672c1265eccaed87f9481cb2d9b84"}, "steering": [], "generations": [{"model": "claude-sonnet-4.6", "model_version": "", "effort": "medium", "tooling_version": "0.0.0", "sdk": "", "provider": "host-harness", "mode": "passenger", "context_origins": [{"path": "internal/workshop/workshop_file.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/reference/definition-files/schema.json", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-golang.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-go-dev.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-try-go.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-digits-cuda.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "internal/sdk/validate.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "source of AllowedBases list and ValidateName constraints"}, {"path": "internal/sdk/sdk.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "source of Source enum, IsSystem, IsSketch"}, {"path": "internal/sdk/channel.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "source of ParseChannel, channel component constraints"}, {"path": "docs/reference/definition-files/sdk-definition.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "sibling page \u2014 used for heading conventions, list-table format, dropdown schema pattern, see-also structure"}, {"path": "docs/reference/definition-files/sdkcraft-definition.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "sibling page \u2014 checked anchor label ref_sdkcraft_definition and cross-ref to ref_workshop_definition"}, {"path": "docs/reference/definition-files/index.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed waiting toctree slot (workshop-definition), cross-refs to exp_workshop_definition and ref_workshop_definition"}, {"path": "docs/reference/cli/workshop-init.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed anchor label ref_workshop_init for see-also"}, {"path": "docs/reference/cli/workshop-run.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed anchor label ref_workshop_run for see-also"}, {"path": "docs/reference/workshops.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "checked for any existing workshop.yaml location documentation"}, {"path": "docs/conf.py", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed |ws_markup| and |sdk_markup| substitution definitions"}, {"path": ".dogen/context/doc-style.md", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "voice conventions; noted terminology drift between workshop.yaml and .workshop/NAME.yaml forms"}, {"path": "docs/explanation/workshops/concepts.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed anchor labels exp_workshop_concepts and exp_workshop_definition for see-also"}], "tools_used": ["view", "bash", "grep"], "gaps": ["Merge/conflict resolution semantics when a workshop-level slot definition shares a name with a slot already defined in the SDK's own definition \u2014 the schema describes them as supplementary but does not specify resolution order when names collide; this edge case is not documented in the page."], "gaps_note": "", "files": [{"path": "docs/reference/definition-files/workshop-definition.rst", "sha256": "853fb1d733f7a4399f4e9dff43a3e15ae9c119f74637561198486e4cc4440117"}], "run_id": "019f2e5e95df43cf40372955ffa393d7", "at": "2026-07-04T18:22:58.529270+00:00", "action": "draft", "draft_path": "docs/reference/definition-files/workshop-definition.rst", "draft_sha256": "853fb1d733f7a4399f4e9dff43a3e15ae9c119f74637561198486e4cc4440117", "handoff_path": ".dogen/staging/workshop-definition/handoff.rst", "source_commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "steering_count": 0, "reviewer_edit_count": 0}], "generations_count": 1, "reviewer_edits": []}
<shellId: 29 completed with exit code 0>
```


---

<sub>17m 29s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-review/references/provenance-summary.md.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-review/references/provenance-summary.md

<details>
<summary>74 lines</summary>

```
Load this file at workflow step 3 (Present the provenance summary).

# Provenance field map

The unit's audit sidecar lives at `.dogen/units/<id>/provenance.yaml`; the lifecycle
state lives at `.dogen/units/<id>/progress.yaml`; the plan (with its sources) lives
in `.dogen/units/<id>/unit.md` front-matter. `dogen unit show <id> --json --latest`
returns everything the review needs in one lean read: the review only ever needs
the **latest** generation, and `--latest` keeps the older passes' full read-lists
out of your context (`generations_count` still reports how many passes ran; the
complete history stays on disk for audits). Present the fields below in plain
language. This is the sidecar the TA otherwise never sees; present it truthfully,
including honest-empty values.

## Fields to surface

From `provenance.yaml` — the gate act and the guidance stream (v1):

- **signoff** — who signed the plan off and when. Its `plan_hash` froze the exact
  `unit.md` approved: if the current `unit.md` no longer hashes to it, say the plan
  **changed since signoff** (the reviewer may want a `dogen signoff --re-sign`
  before judging — or, when the review itself orders the amendment, the folded
  `dogen unit edit … --re-sign`). Its `commit` stamps the repo version at
  approval.
- **signoff_history** — superseded gate acts, oldest first (v1.2): every
  re-approval archives the act it replaced, so each previously approved plan
  hash survives in the tip artifact. Mention the count when non-empty ("re-signed
  N time(s); prior plan hashes on record").
- **steering** — the append-only guidance stream: manual `dogen steer --note`
  entries and automatic fix/redraft review-verdict entries, in order. Quote the
  latest; together with the seeded `steering_notes` in `unit.md` it is what the
  most recent draft was steered by.

From `provenance.yaml` — the latest entry in `generations[]` (the most recent draft
pass):

- **provider** / **mode** — the provider that ran and its role (`driver` generated
  in-process; `passenger` means the host authored and dogen recorded).
- **model** / **model_version** — the model identity. For a passenger run this is
  host-asserted (or empty/unknown when the harness hid it) — say so.
- **context_origins** — what the writer **actually read**, each entry stamped with
  the commit it was read at (hex, or honestly empty with the explanation in the
  entry's `note` — v1.2). For a passenger run these come from the writer's own
  context report.
- **gaps** — facts the writer could not verify at their origin and deliberately
  left out of the prose. Surface them verbatim; they often seed the next steering
  note. An empty list should carry a **gaps_note** justification (v1.2) — empty
  gaps with no note next to deep internals reads is the overconfidence pattern;
  surface its absence as a review signal.
- **files** — the per-page digests of everything the pass wrote (v1.2; primary
  first). For a multi-file unit this is the page set the review covers.
- **source_commit** / **draft_sha256** — the code version the draft describes and
  the exact text recorded (mention only if useful).

From `unit.md` front-matter:

- **sources** — the declared starting-point sources, each with its commit stamp and
  role (`primary` = human-pointed at planning; `discovered` = promoted during
  drafting).

From `progress.yaml`:

- **state** — the current progress state (`pending` / `sourced` / `drafted` /
  `reviewed`).

## The declared-vs-read gap

`sources` (declared starting points) and `context_origins` (actually read) are
deliberately distinct fields — the gap between them is itself audit-relevant.
Surface it plainly:

- read everything declared and beyond → note the draft is grounded in the declared
  sources plus the named discoveries;
- read fewer / different origins than declared → surface the discrepancy so the
  reviewer can weigh it;
- `context_origins` empty against non-empty `sources` → present the honest-empty
  fact ("the writer recorded reading nothing"); it is a review signal, not an
  error to hide.

Do not invent, fill, or smooth over any field. If a value is missing or empty,
present it as missing or empty.

## Presentation

Fold these into the `### Provenance` block presented in both modes, ahead of the
verdict. Keep it to: the signoff line (with plan freshness), the
provider/mode/model line, the declared-vs-read comparison (with commit stamps), the
writer's gaps, the steering-stream count (latest quoted), and the progress state.
Priority tags belong to the review-mode findings (step 4), never here: the
run-status reason codes and progress states stay surfaced verbatim (D-03: use the
CLI's status vocabulary only for run-status).
```

</details>


---

<sub>17m 29s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-review/references/review-rubric.md.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.github/skills/dogen-review/references/review-rubric.md

<details>
<summary>152 lines</summary>

`````
Load this file at workflow step 4 (Perform the findings review).

# Findings review rubric

This is the review-mode rubric: a small, generalized findings framework for a
Diátaxis **reference** unit grounded in **human-pointed sources**. It is derived
from ng-review-docs, deliberately stripped of that rig's specifics (glossary /
varindex, EN+RU lockstep, STYLE_GUIDE grounding, the fixed 10-dimension letter
taxonomy, the SEO/IA/toctree checks, the deterministic Sphinx anchor pre-pass, the
`F-NN` ids and `file:line` pointers, and the report *file*). dogen reviews a single
unit, runs no build, and presents findings in-conversation only — never to a file.

## The four review dimensions

Default to assessing all four. Any dimension may be marked **not assessed** with a
stated reason (e.g. the declared sources were unreadable).

**Grounding rule (v1):** source-fidelity and completeness findings are verified
against the sources themselves, not against the draft's internal coherence. Open
the declared `sources` and the generation's `context_origins` (their commit stamps
say which version the writer read) and check the draft's concrete claims there
before flagging or clearing them.

### source-fidelity

Is every concrete claim grounded, does the narrative stay out of the code, and does
it stay out of the writer's own research process? Three failure modes:

- **Ungrounded claims.** Every concrete claim (behaviour, defaults, types, bounds,
  signatures, availability) must be traceable to the declared `sources` or to what
  the agent actually read (`context_origins`). Flag claims grounded in no recorded
  read; flag the **declared-vs-read gap** when `context_origins` is thinner than
  `sources` (the draft may assert more than was read).
- **Code-dumping.** The narrative must not surface implementation source — bodies,
  private internals, verbatim struct or function source — that violates the
  code-in-narrative boundary. Apply the **same per-block boundary the writer is
  bound to** (see "Code-dump binding" below), not a looser reviewer standard.
- **Researcher register (stance leak).** The prose must state what the product
  accepts, does, and enforces — never narrate the writer's evidence. Flag any
  "observed", "the fixtures show", "every observed use", "the corpus" phrasing:
  the writer's stance contract (canonical:
  `dogen.core.authoring.STANCE_CONTRACT`) routes unverifiable facts into the
  generation's `gaps`, not into hedged prose — so hedged prose is a violation, not
  honesty.
- **Runtime-mechanics leak.** The stance contract's fourth failure mode: prose
  that narrates how the machinery executes internally — temporary files,
  interpreter invocations, internal process flow — even in flawless declarative
  voice. Implementation is not interface; flag it like a code-dump (the reader
  can rely on the behaviour, never the mechanism).

### completeness

Does the page cover what the declared sources plus the recorded steering
(intent / audience) imply a *reference* for this unit should cover? Flag
entities / fields / behaviours present in the sources and implied by steering that
the page omits. This is the source-coverage facet: "what is absent that the reader
needs."

Two mandatory checks inside this dimension:

- **Coverage-vs-outline.** Walk the plan's `## Outline / acceptance` items one
  by one: each is present in the page or covered by a recorded `gap` with a
  reason. An outline item that is neither is a `[should-fix]` minimum.
- **Read-but-not-converted.** Compare the generation's `context_origins`
  against the page: an inventory the writer READ (e.g. every per-interface
  reference file) but did not surface is the highest-value completeness flag —
  the grounding existed and the page still omitted it.

### structure-fit

Does the page behave as a Diátaxis **reference** — information-oriented,
descriptive, one category per page, with no tutorial / how-to drift — and is its
section ordering consistent and sensible? Plus **format hygiene, judged per the
page's own format** (the unit's target extension — v1.2):

- **MyST (`.md`)**: fences closed, the heading ladder unbroken (no mixed
  setext/ATX), `colon_fence` used correctly, ONE table style per page, and any
  reused rST snippet wrapped in an `{eval-rst}` fence — a bare rST directive in
  a `.md` page renders as literal text.
- **rST (`.rst`)**: underlines at least title-length on one consistent ladder
  matching the siblings, directive bodies indented exactly 3 spaces with the
  required blank lines, no MyST fences (```` ``` ````/`:::`) anywhere — they
  render as literal text.

This is Diátaxis conformance + format well-formedness, **not** a house style
guide (dogen has no STYLE_GUIDE this cycle).

Two mandatory checks inside this dimension:

- **Include/link resolution from the committed location.** Resolve every
  relative `literalinclude` / include / link path from where each page actually
  lives (`docs/<target>` — mind the directory depth), not from where a sibling
  page would resolve it. A path that escapes the repo or points at a file that
  is not there is a `[must-fix]` — this is the build-breaking class of defect
  no review may wave through. Check the placement itself too: if the docs tree
  holds a waiting toctree slot or sibling convention this page's
  location/basename/extension diverges from, flag it (the fix is one
  `dogen unit edit --target <path> --re-sign` call, which moves the draft and
  re-approves the amended plan in the same act).
- **Cross-page consistency (multi-file units only).** A unit spanning several
  pages is one change: terminology stays consistent across the set, links
  between the set's pages resolve both ways, and a change applied to one page's
  wording lands on every page the outline says it covers — label each finding
  with its page path.

### clarity

Plain-language correctness (grammar, agreement, typos, run-ons) plus the reference
**register**: impersonal, present-tense, descriptive. Flag marketing voice,
second-person tutorial voice, or future tense in a reference page. Light intra-page
term consistency (one term per concept) folds in here — no varindex machinery.

## Priority mapping

Each finding carries one light priority tag:

| Priority | Trigger |
|----------|---------|
| `[must-fix]` | A claim ungrounded in or contradicting the declared sources; a code-dump surfacing implementation source (source-fidelity); or a category violation that defeats the page as a reference. |
| `[should-fix]` | A material completeness gap; wrong register for a reference; a structural inconsistency that impairs (but does not break) the page. |
| `[nit]` | Wording, ordering, or optional polish. |

### Collision guard (D-03 — non-negotiable)

`[must-fix]` / `[should-fix]` / `[nit]` is a **review-findings** vocabulary **only**.
It must never rename, parallel, or collide with the CLI machine surface — the
failure reason codes (signoff_required, backend_unavailable, model_rejected,
unit_exists, not_drafted, already_accepted, target_exists, bad_target,
bad_report, target_claimed, handoff_incomplete, undeclared_target,
multi_target_unsupported) or the progress states
(pending → sourced → drafted → reviewed). Those stay surfaced **verbatim** from
`--json` for run-status. The two
axes are orthogonal: a priority describes *a finding's urgency*; a reason or
progress word describes *the CLI operation's outcome*. This is the sanctioned D-03
revisit, kept deliberately on a different axis.

## Findings layout (in-conversation only)

Present the findings grouped by dimension. One line per finding: the priority tag
first, the observation quoting the offending draft text, then `→` and a concrete
suggested action. A clean dimension shows `(none)`; a skipped one shows
`(not assessed — <reason>)`. The block is presented in the conversation and is
**never written to a file** — only the reviewer's resulting verdict is recorded,
via `dogen review --verdict --note` (a fix/redraft verdict's note lands in the
steering stream automatically, so a finding phrased as a steering correction is
directly actionable).

```
## dogen-review — findings: <unit-id>

### source-fidelity
- [must-fix] <observation, quoting the offending draft text>
  → <suggested action: what to change, or "re-draft with steering: …">
- [nit] <observation> → <action>

### completeness
- [should-fix] <observation> → <action>

### structure-fit
- (none)

### clarity
- [nit] <observation> → <action>

Findings: N total — X must-fix, Y should-fix, Z nit.
(Priority = review findings, NOT the CLI run-status codes.)

Next: accept (the publishing commit is yours) · record fix/redraft — dogen-write re-drafts against the note
```

There are exactly TWO next steps: accept, or a recorded fix/redraft verdict that
routes to dogen-write. "Make the edit yourself" is not one of them — an
unrecorded correction steers nothing and is invisible to any future audit.
After the verdict is recorded, route off the result's `next_id` token translated
into the loop's language (the table lives in `../../README.md`); never parrot
the raw CLI `next` line to the TA.

## Code-dump binding (governed mirror — keep in sync)

source-fidelity's code-dumping check applies the writer's own boundary. The
canonical source is `dogen.core.authoring.REFERENCE_CODE_RUBRIC`; its per-block
heuristic is carried here verbatim so the reviewer and the writer apply the
**identical** rule:

> Per block, ask: would the reader themselves type, author, or invoke this exact text? If so, a minimal version may be shown; if instead it is how the machinery is implemented internally, reference it by qualified name and never show it.

This copy is **drift-guarded** (`tests/test_review_modes_keyphrases.py`, the
`-k canonical` tests) against `dogen.core.authoring.RUBRIC_HEURISTIC` — the third
governed mirror alongside the Copilot driver strings and the dogen-write passenger
prose. It must be kept byte-for-byte in sync with the core constant; edit the core
symbol and this copy together, never one alone.
`````

</details>


---

<sub>17m 32s</sub>

### Reasoning

*Now I have all the information I need. Let me:
1. Read the drafted page
2. Select the review mode (ask the user)

Actually per the workflow, I should first read the drafted page and the sidecars, then ask for the mode, then present the provenance summary.

Let me read the drafted page now.*

---

<sub>17m 34s</sub>

### Copilot

Good — unit is drafted. Let me read the page before asking for mode.

---

<sub>17m 36s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/workshop-definition.rst.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/workshop-definition.rst

<details>
<summary>304 lines</summary>

```
.. _ref_workshop_definition:

.. meta::
   :description: Reference for the workshop.yaml definition file. Covers
                 filename and location, top-level fields, SDK entries,
                 connections, actions, the JSON Schema, and worked examples.

Workshop definition
===================

.. @artefact workshop definition

The :file:`workshop.yaml` file is the workshop definition:
|ws_markup| reads it when it launches, refreshes, or restores a workshop.
You author it by hand in the project directory,
or generate a starting point with :command:`workshop init`.


Filename and location
---------------------

|ws_markup| looks for the definition in the project directory.
Three forms are accepted:

- :file:`workshop.yaml` — single-workshop form at the project root.
- :file:`.workshop.yaml` — alternate single-workshop form at the project root.
- :file:`.workshop/<NAME>.yaml` — named form in the :file:`.workshop/`
  directory.
  :command:`workshop init <NAME>` creates this form.
  When this form is used,
  the value of :samp:`name` in the file must match the file's base name.

All three forms are equivalent in capability;
the choice is a project convention.


Top-level fields
----------------

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`name`
     - string
     - yes
     - Workshop name.
       See :ref:`ref_workshop_definition_name`.

   * - :samp:`base`
     - string
     - yes
     - Base operating-system image.
       See :ref:`ref_workshop_definition_base`.

   * - :samp:`sdks`
     - list
     - no
     - Ordered list of SDK entries to install.
       See :ref:`ref_workshop_definition_sdks`.

   * - :samp:`connections`
     - list
     - no
     - Explicit plug-to-slot connections.
       See :ref:`ref_workshop_definition_connections`.

   * - :samp:`actions`
     - object
     - no
     - Named shell scripts, available via :command:`workshop run`.
       See :ref:`ref_workshop_definition_actions`.

No other keys are accepted.


.. _ref_workshop_definition_name:

Name
----

The :samp:`name` field is a string identifying the workshop.

Constraints:

- Must start with a lowercase letter.
- May contain lowercase letters, digits, and single hyphens between characters.
- At most 40 characters.
- Matches the pattern :regexp:`^[a-z](?:-?[a-z0-9])*$`.

Valid examples: :samp:`dev`, :samp:`go-dev`, :samp:`digits-cuda`.


.. _ref_workshop_definition_base:

Base
----

The :samp:`base` field names the Ubuntu release used as the container image.

Accepted values:

.. list-table::
   :header-rows: 1
   :width: 70
   :widths: 3 4

   * - Value
     - Ubuntu release

   * - :samp:`ubuntu@20.04`
     - Ubuntu 20.04 LTS (Focal Fossa)

   * - :samp:`ubuntu@22.04`
     - Ubuntu 22.04 LTS (Jammy Jellyfish)

   * - :samp:`ubuntu@24.04`
     - Ubuntu 24.04 LTS (Noble Numbat)

   * - :samp:`ubuntu@26.04`
     - Ubuntu 26.04 LTS (Plucky Puffin)

SDKs that declare a base must match the workshop base.
SDKs that do not declare a base are accepted on any workshop.


.. _ref_workshop_definition_sdks:

SDK entries
-----------

The :samp:`sdks` field is a list of SDK entries.
|ws_markup| installs them in declaration order, on top of the base image.
The system SDK is installed first automatically and does not need to be listed.
Each SDK name must appear at most once in the list.

Each entry has the following fields:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`name`
     - string
     - yes
     - SDK to install.
       See :ref:`ref_workshop_definition_sdk_name`.

   * - :samp:`channel`
     - string
     - no
     - Store channel used to retrieve and refresh the SDK.
       See :ref:`ref_workshop_definition_sdk_channel`.

   * - :samp:`plugs`
     - object
     - no
     - Plug definitions and bindings for this SDK entry.
       See :ref:`ref_workshop_definition_sdk_plugs`.

   * - :samp:`slots`
     - object
     - no
     - Additional slot definitions for this SDK entry.
       See :ref:`ref_workshop_definition_sdk_slots`.

No other keys are accepted within an SDK entry.


.. _ref_workshop_definition_sdk_name:

SDK name
~~~~~~~~

The :samp:`name` field identifies the SDK to install.
An optional prefix controls the source:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 3 5

   * - Form
     - Source

   * - :samp:`<name>` (no prefix)
     - SDK Store

   * - :samp:`try-<name>`
     - Locally tried SDK (from :command:`sdkcraft try`)

   * - :samp:`project-<name>`
     - In-project SDK under :file:`.workshop/<name>/`

The underlying :samp:`<name>` must:

- contain at least one lowercase letter,
- consist of lowercase letters, digits, and single hyphens between characters,
- not be :samp:`agent` (reserved),
- be at most 40 characters (44 with :samp:`try-`; 48 with :samp:`project-`).

The names :samp:`system` and :samp:`sketch` identify implicit SDKs
that |ws_markup| installs regardless of whether they appear in the list.
You may list them explicitly to attach per-workshop plug or slot definitions.


.. _ref_workshop_definition_sdk_channel:

Channel
~~~~~~~

The :samp:`channel` field selects the Store channel from which |ws_markup|
retrieves and refreshes the SDK.
Omitting it defaults to :samp:`latest/stable`.

The field has no effect on :samp:`try-`, :samp:`project-`, :samp:`system`,
or :samp:`sketch` entries, but must be well-formed when present.

Format: :samp:`[<track>/]<risk>[/<branch>]` or :samp:`<track>` alone.

Components:

- **risk**: one of :samp:`stable`, :samp:`candidate`, :samp:`beta`, :samp:`edge`.
- **track**: alphanumeric with underscores, hyphens, and dots as separators;
  at most 28 characters; must not equal a risk name.
- **branch**: alphanumeric with hyphens and dots as separators;
  at most 128 characters; must not equal a risk name.

Valid examples: :samp:`stable`, :samp:`edge`, :samp:`1.26`,
:samp:`1.26/stable`, :samp:`latest/stable/hotfix-123`.


.. _ref_workshop_definition_sdk_plugs:

Plugs
~~~~~

The :samp:`plugs` key maps plug names to plug definitions or plug bindings.

Plug names must start with a lowercase letter and contain only lowercase letters,
digits, and single hyphens between characters.

Each value takes one of the following forms:

**Inline plug definition**
   A mapping with an :samp:`interface` key and interface-specific attributes:

   .. code-block:: yaml

      plugs:
        cuda:
          interface: mount
          workshop-target: /usr/local/cuda/lib64

**Interface shorthand**
   A string naming the interface,
   or :samp:`null` to use the plug name as the interface name:

   .. code-block:: yaml

      plugs:
        ssh-agent: null    # interface is ssh-agent
        data: my-iface     # interface is my-iface

**Plug binding**
   A mapping with a single :samp:`bind` key whose value is a plug reference
   in the form :samp:`<sdk>:<plug>`:

   .. code-block:: yaml

      plugs:
        data:
          bind: go:mod-cache

   Constraints on plug bindings:

   - A bound plug must not define any other attributes alongside :samp:`bind`.
   - A bound plug must not also appear in :samp:`connections`.
   - The target plug must not itself be bound.
   - Neither the binding plug nor the target may belong to the system SDK.
   - The target SDK must be listed in the workshop's :samp:`sdks` entries
     or be :samp:`sketch`.

For interface-specific attributes accepted in inline definitions,
see :ref:`ref_sdk_definition_interfaces`.


.. _ref_workshop_definition_sdk_slots:

Slots
~~~~~

The :samp:`slots` key maps slot names to slot definitions.
These supplement the SDK's own slot definitions.

Slot names must start with a lowercase letter and contain only lowercase letters,
digits, and single hyphens between characters.

Each value takes one of the following forms:

**Inline slot definition**
   A mapping with an :samp:`interface` key and interface-specific attributes:

   .. code-block:: yaml

      slots:
        images:
          interface: mount
          workshop-source: $SDK/images

**Interface shorthand**
   A string naming the interface,
   or :samp:`null` to use the slot name as the interface name.

For interface-specific attributes, see :ref:`ref_sdk_definition_interfaces`.


.. _ref_workshop_definition_connections:

Connections
-----------

The :samp:`connections` field is a list of explicit plug-to-slot pairs,
applied in addition to any automatic connections.

Each entry requires both keys:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`plug`
     - string
     - yes
     - Plug reference in the form :samp:`<sdk>:<plug>`.
       The :samp:`<sdk>` portion may be empty
       (for example, :samp:`:ssh-agent`) to refer to the system SDK.

   * - :samp:`slot`
     - string
     - yes
     - Slot reference in the form :samp:`<sdk>:<slot>`.
       The :samp:`<sdk>` portion may be empty to refer to the system SDK.

No other keys are accepted within a connection entry.

Constraints:

- Both endpoints must reference an SDK that is listed in :samp:`sdks`
  or is an implicit SDK (:samp:`system`, :samp:`sketch`).
- A plug that is bound (see :ref:`ref_workshop_definition_sdk_plugs`)
  may not also appear in :samp:`connections`.


.. _ref_workshop_definition_actions:

Actions
-------

The :samp:`actions` field is a map of named shell scripts.
Each action is available via :command:`workshop run`.

Action names must start with a lowercase letter and contain only lowercase
letters, digits, and single hyphens between characters
(the same pattern as :ref:`workshop names <ref_workshop_definition_name>`).

Each value is a YAML string containing the script body.
YAML literal blocks (:samp:`|`) are the conventional form for multi-line scripts.

The script runs inside the workshop as a bash login shell
with :samp:`errexit` and :samp:`pipefail` set.
Positional parameters :samp:`$@`, :samp:`$1`, :samp:`$2`, and so on
receive any arguments passed to the action.


JSON Schema
-----------

.. @artefact workshop schema

The following JSON Schema describes the complete accepted structure of
:file:`workshop.yaml`:

.. dropdown:: Workshop definition schema

   .. literalinclude:: schema.json
      :language: json


Examples
--------

A minimal workshop with a single Store SDK and a pinned track:

.. literalinclude:: ../../examples/workshop-golang.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop with plug bindings across two SDK entries:

.. literalinclude:: ../../examples/workshop-go-dev.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop with explicit connections and inline plug and slot definitions:

.. literalinclude:: ../../examples/workshop-digits-cuda.yaml
   :language: yaml
   :caption: workshop.yaml


See also
--------

Explanation:

- :ref:`exp_workshop_concepts`
- :ref:`exp_workshop_definition`

Reference:

- :ref:`ref_sdk_definition`
- :ref:`ref_sdkcraft_definition`
- :ref:`ref_workshop_init`
- :ref:`ref_workshop_run`
```

</details>


---

<sub>17m 40s</sub>

### Reasoning

*Good, I've read the draft. Now I need to ask the reviewer which mode they want: record or review.*

---

<sub>17m 41s</sub>

### Copilot

Draft read. Now selecting mode:

---

<sub>19m 16s</sub>

### `ask_user`

**How would you like to proceed with reviewing the workshop...**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "review — show me findings first, then I'll give my verdict",
    "record — just show provenance and record my verdict"
  ],
  "question": "How would you like to proceed with reviewing the workshop-definition draft?"
}
```

</details>

```
User selected: review — show me findings first, then I'll give my verdict
```


---

<sub>19m 19s</sub>

### Reasoning

*The reviewer wants the full review mode. I need to:
1. Present the provenance summary
2. Run the four-dimension findings review
3. Elicit the verdict

Let me now present the provenance summary and findings.

For the findings, I need to check:

**Source-fidelity:**
1. Check claims against sources (workshop_file.go, schema.json, examples)
2. Check for code-dumping
3. Check for researcher register (stance leaks)
4. Check for runtime mechanics leaks

Let me go through the draft carefully:

1. **Filename and location section:**
   - "three forms are accepted" - confirmed from `workshop_file.go`: `Filenames = []string{"workshop.yaml", ".workshop.yaml"}` and `Directory = ".workshop"` with `filename(name)` function
   - "value of name in the file must match the file's base name" - this is in the schema.json description: "Must match the definition file basename if the workshop is stored under .workshop/." ✅

2. **Top-level fields:**
   - All five fields confirmed from the Go struct and schema.json ✅
   - "No other keys are accepted" - confirmed from schema `additionalProperties: false` ✅

3. **Name section:**
   - "Must start with a lowercase letter" ✅ from the regex pattern validating workshop names
   - "May contain lowercase letters, digits, and single hyphens between characters" ✅
   - "At most 40 characters" ✅ from the constant defining max workshop name length
   - Pattern validation confirmed ✅

4. **Base section:**
   - The four allowed base values are correct ✅ from the AllowedBases list: ubuntu@20.04, ubuntu@22.04, ubuntu@24.04, ubuntu@26.04
   - Checking the Ubuntu release names - Focal Fossa, Jammy Jellyfish, and Noble Numbat are confirmed, but I need to verify if ubuntu@26.04 is actually "Plucky Puffin"

Actually, I'm realizing the code and schema only list the version strings, not the codenames. The Ubuntu release names I included weren't sourced from the materials I reviewed - they're from general knowledge, which means I should be careful about grounding them properly.

For 26.04 LTS, I need to think through the naming pattern: 20.04 is F (Focal), 22.04 is J (Jammy), 24.04 is N (Noble), so 26.04 should follow the alphabetical sequence, but I don't have a confirmed source for what that codename actually is. The well-known LTS releases like 20.04 and 22.04 have established codenames, but 26.04's codename is uncertain since it may not be released yet. I realize I pulled these codenames from my training data rather than from the actual recorded sources I was analyzing, which is a source-fidelity problem I should flag. is incorrect since none of the sources actually confirm any Ubuntu codenames. I'm also verifying the other claims: the SDK section checks out—the system SDK is installed implicitly according to the workshop documentation and schema, and the channel defaults to `latest/stable` when omitted, which I can confirm from the channel configuration code that sets these values when empty. The script runs as a bash login shell with errexit and pipefail enabled, and positional parameters like $@, $1, $2 receive any arguments passed to the action. For the documentation structure, the schema.json file is referenced directly from the workshop definition docs, and the examples path needs to navigate up two levels from the docs directory into the examples folder.

I've verified all the "See also" cross-references—they're confirmed across concepts.rst, sdk-definition.rst, sdkcraft-definition.rst, workshop-init.rst, and workshop-run.rst. However, I'm noticing a source-fidelity issue: the Ubuntu codenames listed in the Base table aren't grounded in any documented source, particularly "Plucky Puff." I'm realizing the codenames are extra information not grounded in any of my sources, which creates a source-fidelity problem. The sibling documentation only lists the version numbers without codenames, so adding them introduces unsourced content that could be inaccurate. I should remove them to stay faithful to what's actually documented.

Looking at the outline coverage, I've hit all the major sections—filename, top-level fields, SDK entries with the bind shorthand, connections, actions, JSON schema, examples, and see also. The page appears complete. I'm now checking whether the steering requirement about documenting each field's type, required status, defaults, and constraints is being met across the page. Checking the RST heading hierarchy - the page uses `=` for the title, `-` for top-level sections like Name and Base, and `~` for subsections within SDK entries like SDK name and Channel. This structure looks consistent so far. Checking the directive indentation across the file to make sure everything uses 3 spaces consistently ✅

, and I'm noticing the page follows the sibling pattern with `.. @artefact` comments and stays true to reference documentation without drifting into tutorial territory. Now I'm examining whether the definition list syntax is correct—the bold-formatted terms like "**Inline plug definition**" followed by indented definitions appear to follow RST's standard definition list format. The dropdown directive is supported across the documentation, and while the intro uses some second-person phrasing like "You author it by hand," that's consistent with how the sibling pages handle context-setting. The RST syntax checks out—definition lists with bold terms and indented definitions are valid, and the literalinclude directive properly references the schema file. I'm documenting the Ubuntu LTS versions with their codenames, but I'm realizing the codenames for the newer versions like 26.04 aren't from my documented sources—they're from my training data, which means I need to be careful about accuracy here, especially for "Plucky Puffin." I should remove the codenames from the table entirely since they're not grounded in my training data and the sibling documentation doesn't include them anyway. The "Plucky Puffin" attribution to 26.04 is particularly problematic and needs to be flagged as a source-fidelity issue. The fix is to remove the "Ubuntu release" column entirely from the Base table to align with the sibling documentation and eliminate the unsourced codenames. I've confirmed there are no other source-fidelity gaps, and the `source` field was correctly omitted since it's not user-authored. Checking the validation logic more carefully - the code confirms that the target SDK must either be in the workshop's SDK list or be sketch, but explicitly rejects system SDKs before that check. The regex pattern in the schema also enforces this by excluding system but allowing sketch, so the documentation is accurate on this point ✅. Now let me review the intro sentence to make sure I haven't missed anything from the outline.

Actually, I'm noticing a potential issue with the restore behavior - the intro claims that |ws_markup| reads the workshop definition on launches, refreshes, *and* restores, but looking at the code and documentation, restore appears to just roll back the container filesystem to a snapshot without re-reading the definition. This might be an inaccuracy in how the intro describes the restore process. I'm second-guessing whether restore actually reads workshop.yaml at all. The documentation describes it as a pure filesystem rollback to the last snapshot, with no mention of re-reading the definition file. So claiming that Workshop "reads" the file during restore seems unsupported by what I've actually found in the sources—this is worth flagging as a potential inaccuracy in the intro description. I found two critical issues to fix. First, the Ubuntu codenames in the Base table aren't sourced anywhere—the recorded sources only list version strings, and "Plucky Puffin" is actually Ubuntu 25.04, not 26.04. I need to remove that column entirely and stick to version strings like the sibling documentation does. Second, the intro incorrectly claims workshop.yaml is read during restore, but the sources show restore is just a filesystem rollback that doesn't apply SDK changes, so I should remove that phrase and only mention launch and refresh.

The rest of the draft checks out—all outline items are present, the RST structure matches siblings, and the clarity is solid. Though I'm second-guessing the restore claim now—could restoring a workshop validate against the current workshop.yaml if it's been modified since the snapshot? I'm not certain, but since the sources don't explicitly confirm this happens, I should stick with what's documented. Looking at the indentation structure for code blocks nested inside definition lists — the directive itself sits at 3 spaces under the definition, and the code content indents another 3 spaces to 6 total, which appears correct for reStructuredText formatting.

I'm verifying the `literalinclude` paths resolve properly from the documentation files to the examples directory, and they all check out. Now I need to confirm whether the `.. dropdown::` directive requires a blank line separating it from the `literalinclude` content inside. I've identified the key issues to address: the Ubuntu codenames are inaccurate and ungrounded, particularly for version 26.04, and there's an unsupported claim about restoring workshops in the introduction. Everything else in the draft looks solid, so I'll organize these findings with the provenance summary for review.*

---

<sub>21m 30s</sub>

### Copilot

Now I'll verify the two source-grounding concerns before presenting findings.

---

<sub>21m 35s</sub>

### `bash`

**Check restore vs readWorkshop usage**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "restore\|readWorkshop\|Filenames\|workshop.yaml" internal/workshop/workshop_file.go | head -20

```
42:	Filenames = []string{"workshop.yaml", ".workshop.yaml"}
281:func readWorkshop(path string) (*File, error) {
<shellId: 30 completed with exit code 0>
```


---

<sub>21m 35s</sub>

### `bash`

**Find where readWorkshop is called**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -rn "readWorkshop\|ReadWorkshop\|workshop_file\|workshop\.yaml" internal/overlord/ --include="*.go" | grep -v "_test.go" | grep -v "No such" | head -20

```
internal/overlord/workshopstate/manager.go:147:	files, err := p.ReadWorkshops()
<shellId: 31 completed with exit code 0>
```


---

<sub>21m 35s</sub>

### `bash`

**Check sources for Ubuntu codenames**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "26.04\|Plucky\|codename\|release name" docs/reference/definition-files/sdk-definition.rst docs/reference/definition-files/sdkcraft-definition.rst internal/sdk/validate.go docs/reference/definition-files/schema.json 2>/dev/null | head -20

<details>
<summary>6 lines</summary>

```
docs/reference/definition-files/sdk-definition.rst:100:       or :samp:`ubuntu@26.04`.
docs/reference/definition-files/sdkcraft-definition.rst:68:       or :samp:`ubuntu@26.04`.
internal/sdk/validate.go:65:	AllowedBases = []string{"ubuntu@20.04", "ubuntu@22.04", "ubuntu@24.04", "ubuntu@26.04"}
docs/reference/definition-files/schema.json:22:        "ubuntu@26.04"
docs/reference/definition-files/schema.json:24:      "errorMessage": "The base must be one of the supported values: ubuntu@20.04, ubuntu@22.04, ubuntu@24.04, ubuntu@26.04."
<shellId: 32 completed with exit code 0>
```

</details>


---

<sub>21m 38s</sub>

### Reasoning

*Confirmed:
1. No source contains Ubuntu codenames — confirmed. The sibling pages just list version strings.
2. `readWorkshop` is used by `ReadWorkshops()` in `workshopstate/manager.go` which is for launching/managing workshops, not for restore. I cannot confirm workshop.yaml is read during restore from these reads.

Let me check one more thing - the `ReadWorkshops` function to see if it's called during restore operations.*

---

<sub>21m 41s</sub>

### `bash`

**Check if ReadWorkshops is called during restore**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "restore\|Restore" internal/overlord/workshopstate/manager.go | head -15

```
87:func FakeSnapshotCooldownTime(t time.Duration) (restore func()) {
<shellId: 33 completed with exit code 0>
```


---

<sub>21m 44s</sub>

### Reasoning

*The `ReadWorkshops` in `workshopstate/manager.go` is not called during restore - it's used for other operations. The restore handler is separate. Let me check more broadly.*

---

<sub>21m 46s</sub>

### `bash`

**All callers of readWorkshop**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -rn "ReadWorkshop\|readWorkshop" internal/ --include="*.go" | grep -v "_test.go" | head -15

<details>
<summary>8 lines</summary>

```
internal/workshop/workshop_file.go:281:func readWorkshop(path string) (*File, error) {
internal/workshop/project.go:67:		file, err := readWorkshop(path)
internal/workshop/project.go:79:	file, err := readWorkshop(path)
internal/workshop/project.go:91:func (w *Project) ReadWorkshops() (map[string]string, error) {
internal/workshop/project.go:98:		file, err := readWorkshop(path)
internal/workshop/project.go:117:			logger.Noticef("On ReadWorkshops: Cannot stat a workshop file %q: %v", f, err)
internal/overlord/workshopstate/manager.go:147:	files, err := p.ReadWorkshops()
<shellId: 34 completed with exit code 0>
```

</details>


---

<sub>21m 49s</sub>

### `bash`

**Check restore handlers in workshopstate**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && grep -n "restore\|Restore" internal/overlord/workshopstate/*.go | grep -v "_test.go" | head -20

<details>
<summary>15 lines</summary>

```
internal/overlord/workshopstate/manager.go:87:func FakeSnapshotCooldownTime(t time.Duration) (restore func()) {
internal/overlord/workshopstate/manifest.go:94:// given workshops. For --restore, these manifests are also used to refresh the
internal/overlord/workshopstate/manifest.go:117:	case conflict.RefreshRestore:
internal/overlord/workshopstate/request.go:155:		summary = fmt.Sprintf("Restore %q workshop from %q snapshot", file.Name, lastIntact)
internal/overlord/workshopstate/request.go:250:		if option == conflict.RefreshRestore || hasUpdates(current[i], latest[i]) {
internal/overlord/workshopstate/request.go:366:	saveSdks, restoreSdks := saveRestore(current.Sdks, latest.Sdks)
internal/overlord/workshopstate/request.go:441:	restoreState := runHooks(st, restoreSdks, 0, hookstate.RestoreState)
internal/overlord/workshopstate/request.go:442:	addTaskSet(restoreState)
internal/overlord/workshopstate/request.go:453:	if len(restoreSdks) > 0 {
internal/overlord/workshopstate/request.go:469:	// and fail to restore from the copy. We don't want that. Hence,
internal/overlord/workshopstate/request.go:489:func saveRestore(current, latest []sdk.Setup) (save, restore []sdk.Setup) {
internal/overlord/workshopstate/request.go:491:	var saveSdks, restoreSdks []sdk.Setup
internal/overlord/workshopstate/request.go:498:			restoreSdks = append(restoreSdks, sk)
internal/overlord/workshopstate/request.go:505:	return saveSdks, restoreSdks
<shellId: 35 completed with exit code 0>
```

</details>


---

<sub>21m 52s</sub>

### Reasoning

*Good. Line 94 in `manifest.go` says: "For --restore, these manifests are also used to refresh the..." - so it seems workshop.yaml IS read during a restore operation (because `manifest.go` uses it for restore). Let me read a bit more to confirm.

Looking at `manifest.go:94`: "For --restore, these manifests are also used to refresh the given workshops." This suggests that during `workshop restore`, the workshop definition IS read. 

And from `request.go:155`: `summary = fmt.Sprintf("Restore %q workshop from %q snapshot", file.Name, lastIntact)` - the `file.Name` here suggests the workshop file IS read for restore operations.
Now checking `request.go` line 250, which shows a conditional that might apply the current workshop definition during restore. The manifest comment about refreshing workshops during restore is making me reconsider whether the intro's phrasing about "or restores a workshop" might actually be accurate. Given how the restore logic interacts with the workshop definition, I should be more cautious about calling this a definitive error. So the manifest comment confirms that workshop.yaml is indeed read during restore to refresh the workshops, which means the intro sentence is accurate. I'll downgrade this concern to a minor note or drop it entirely since the evidence supports the original claim.

Now I'm compiling my findings, starting with source-fidelity issues like the Ubuntu codenames. The restore comment in the manifest code confirms that workshop.yaml is indeed read during restore operations, so that's not an issue worth flagging. Now I'm doing a final verification pass on the component descriptions — checking the track channel regex against the documented format of alphanumeric characters with underscores, hyphens, and dots as separators, which matches ✅. Moving on to verify the branch channel format next. The schema only lists the specific Ubuntu versions in the enum, so there's no codename information there either. I've got my findings ready to present now.*

---

<sub>22m 17s</sub>

### Copilot

Good — `manifest.go:94` confirms workshop.yaml IS read during restore, so the intro is grounded. My main finding is the codenames. Now presenting:

---

## dogen-review — findings: workshop-definition

### Provenance

- **Signoff:** Artem Konev at 2026-07-04T18:12 UTC — plan **fresh** (unit.md hashes to the signed-off plan)
- **Provider / mode / model:** host-harness / passenger / claude-sonnet-4.6 (host-asserted)
- **Declared sources** (3, all primary, at `5e3636a`):
  - `internal/workshop/workshop_file.go`
  - `docs/reference/definition-files/schema.json`
  - `docs/examples/workshop-golang.yaml`
- **Actually read** (18 origins, all at `25d76b7`): all 3 declared sources plus 15 discoveries — additional examples (`workshop-go-dev.yaml`, `workshop-try-go.yaml`, `workshop-digits-cuda.yaml`), SDK internals (`internal/sdk/validate.go`, `sdk.go`, `channel.go`), sibling reference pages, `docs/conf.py`, `docs/explanation/workshops/concepts.rst`, `.dogen/context/doc-style.md`. Declared sources are a subset of what was read — the gap is expected and appropriate.
- **Writer-declared gaps:** Merge/conflict resolution semantics when a workshop-level slot definition shares a name with an SDK's own definition — left out of the prose, grounded in schema description ("supplementary") but resolution order on collision not verified.
- **Steering stream:** 0 entries (seeded note only: "cover every field's type, required status, default, and constraints")
- **Progress:** drafted

---

### source-fidelity

- **[must-fix]** The Base table's second column lists Ubuntu release codenames ("Focal Fossa", "Jammy Jellyfish", "Noble Numbat", "Plucky Puffin") that appear in no recorded source. The last entry is factually wrong: "Plucky Puffin" is the Ubuntu 25.04 codename, not 26.04. The sibling pages (`sdk-definition.rst`, `sdkcraft-definition.rst`) and all recorded sources list only version strings. → Drop the "Ubuntu release" column from the Base table entirely; list only the four accepted version strings, matching the sibling convention.

### completeness

(none — all 9 outline items present; the slot name-collision gap is correctly recorded)

### structure-fit

(none — RST heading hierarchy consistent with siblings, directive indentation correct, all `literalinclude` and cross-reference paths resolve from the committed location, toctree slot matched)

### clarity

(none)

**Findings: 1 total — 1 must-fix, 0 should-fix, 0 nit.**
*(Priority = review findings, NOT the CLI run-status codes.)*

---

---

<sub>22m 38s</sub>

### `ask_user`

**What's your verdict on the workshop-definition draft?**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "fix — drop the codename column from the Base table",
    "accept — it's fine as-is",
    "redraft — full new pass"
  ],
  "question": "What's your verdict on the workshop-definition draft?"
}
```

</details>

```
User selected: fix — drop the codename column from the Base table
```


---

<sub>22m 45s</sub>

### `bash`

**Record fix verdict via dogen review**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen review "workshop-definition" \
  --verdict fix \
  --note "Drop the 'Ubuntu release' column from the Base table. The codenames are not grounded in any recorded source, and the entry for ubuntu@26.04 ('Plucky Puffin') is factually wrong — that is Ubuntu 25.04's codename. List only the four accepted version strings as a single-column table or inline list, matching the sibling sdk-definition.rst style." \
  --json 2>&1

```
git: committed 74ca0bd — dogen(workshop-definition): reviewed — review: fix
{"unit": "workshop-definition", "provider": null, "draft_path": null, "progress": "reviewed", "reason": null, "verdict": "fix", "next": "dogen draft workshop-definition  # re-draft per the recorded steering", "next_id": "draft", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad"}
<shellId: 36 completed with exit code 0>
```


---

<sub>22m 49s</sub>

### Copilot

### Verdict

**fix** — Drop the codename column from the Base table (wrong and ungrounded; see note above).
**Committed:** `74ca0bd` — `dogen(workshop-definition): reviewed — review: fix`

The fix note is now in the steering stream. **Invoke dogen-write to re-draft against the recorded steering.**

---

<sub>23m 42s</sub>

### User

/dogen-write

---

<sub>23m 46s</sub>

### Reasoning

*The user wants me to invoke the dogen-write skill again for the re-draft.*

---

<sub>23m 46s</sub>

### `skill`

**dogen-write**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "dogen-write"
}
```

</details>

```
Skill "dogen-write" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>23m 49s</sub>

### Reasoning

*This is a re-draft. Let me:
1. Read the unit state to confirm the fix steering entry is there
2. Probe the provider
3. Apply the fix: remove the Ubuntu codename column from the Base table

These can all be done in parallel.*

---

<sub>23m 54s</sub>

### `bash`

**Read unit state with steering**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen unit show "workshop-definition" --json --latest 2>&1

```
{"unit": {"schema_version": 1, "unit_id": "workshop-definition", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "title": "Workshop definition", "sources": [{"path": "internal/workshop/workshop_file.go", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/reference/definition-files/schema.json", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/examples/workshop-golang.yaml", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}], "sphinx_target": "reference/definition-files/workshop-definition.rst", "extra_targets": [], "steering_notes": "The page must give workshop users everything they need to get any field in workshop.yaml right without consulting another page; it should cover every field's type, whether it is required, its default, and its constraints (name format, accepted bases, valid action names), structured so it works both as a first-read introduction and a quick-lookup reference for experienced users arriving from elsewhere."}, "format": "rst", "progress": "reviewed", "signoff": {"author": "Artem Konev", "at": "2026-07-04T18:12:07.674646+00:00", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "plan_hash": "fe06b324249c9d5f9da3e9fa0aefed5ab5e45814fbe5b0a1dea423c0af0e3ece", "commit": "4f7b67d0dd7672c1265eccaed87f9481cb2d9b84"}, "steering": [{"author": "Artem Konev", "at": "2026-07-04T18:29:13.612012+00:00", "note": "Drop the 'Ubuntu release' column from the Base table. The codenames are not grounded in any recorded source, and the entry for ubuntu@26.04 ('Plucky Puffin') is factually wrong \u2014 that is Ubuntu 25.04's codename. List only the four accepted version strings as a single-column table or inline list, matching the sibling sdk-definition.rst style.", "origin": "review"}], "generations": [{"model": "claude-sonnet-4.6", "model_version": "", "effort": "medium", "tooling_version": "0.0.0", "sdk": "", "provider": "host-harness", "mode": "passenger", "context_origins": [{"path": "internal/workshop/workshop_file.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/reference/definition-files/schema.json", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-golang.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-go-dev.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-try-go.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "docs/examples/workshop-digits-cuda.yaml", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": ""}, {"path": "internal/sdk/validate.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "source of AllowedBases list and ValidateName constraints"}, {"path": "internal/sdk/sdk.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "source of Source enum, IsSystem, IsSketch"}, {"path": "internal/sdk/channel.go", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "source of ParseChannel, channel component constraints"}, {"path": "docs/reference/definition-files/sdk-definition.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "sibling page \u2014 used for heading conventions, list-table format, dropdown schema pattern, see-also structure"}, {"path": "docs/reference/definition-files/sdkcraft-definition.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "sibling page \u2014 checked anchor label ref_sdkcraft_definition and cross-ref to ref_workshop_definition"}, {"path": "docs/reference/definition-files/index.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed waiting toctree slot (workshop-definition), cross-refs to exp_workshop_definition and ref_workshop_definition"}, {"path": "docs/reference/cli/workshop-init.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed anchor label ref_workshop_init for see-also"}, {"path": "docs/reference/cli/workshop-run.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed anchor label ref_workshop_run for see-also"}, {"path": "docs/reference/workshops.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "checked for any existing workshop.yaml location documentation"}, {"path": "docs/conf.py", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed |ws_markup| and |sdk_markup| substitution definitions"}, {"path": ".dogen/context/doc-style.md", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "voice conventions; noted terminology drift between workshop.yaml and .workshop/NAME.yaml forms"}, {"path": "docs/explanation/workshops/concepts.rst", "commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "note": "confirmed anchor labels exp_workshop_concepts and exp_workshop_definition for see-also"}], "tools_used": ["view", "bash", "grep"], "gaps": ["Merge/conflict resolution semantics when a workshop-level slot definition shares a name with a slot already defined in the SDK's own definition \u2014 the schema describes them as supplementary but does not specify resolution order when names collide; this edge case is not documented in the page."], "gaps_note": "", "files": [{"path": "docs/reference/definition-files/workshop-definition.rst", "sha256": "853fb1d733f7a4399f4e9dff43a3e15ae9c119f74637561198486e4cc4440117"}], "run_id": "019f2e5e95df43cf40372955ffa393d7", "at": "2026-07-04T18:22:58.529270+00:00", "action": "draft", "draft_path": "docs/reference/definition-files/workshop-definition.rst", "draft_sha256": "853fb1d733f7a4399f4e9dff43a3e15ae9c119f74637561198486e4cc4440117", "handoff_path": ".dogen/staging/workshop-definition/handoff.rst", "source_commit": "25d76b730f865d52e824a862bab6c96103ce01a0", "steering_count": 0, "reviewer_edit_count": 0}], "generations_count": 1, "reviewer_edits": [{"at": "2026-07-04T18:29:13.611998+00:00", "reviewer": "Artem Konev", "summary": "Drop the 'Ubuntu release' column from the Base table. The codenames are not grounded in any recorded source, and the entry for ubuntu@26.04 ('Plucky Puffin') is factually wrong \u2014 that is Ubuntu 25.04's codename. List only the four accepted version strings as a single-column table or inline list, matching the sibling sdk-definition.rst style.", "verdict": "fix", "draft_sha256": "", "files": []}]}
<shellId: 38 completed with exit code 0>
```


---

<sub>23m 54s</sub>

### `bash`

**Probe provider**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen draft "workshop-definition" --resolve-only --json 2>&1

```
{"unit": "workshop-definition", "provider": "host-harness", "draft_path": null, "progress": null, "reason": null}
<shellId: 37 completed with exit code 0>
```


---

<sub>23m 57s</sub>

### Reasoning

*Good. Re-draft precondition confirmed:
- `generations_count` = 1 (this is a re-draft)
- `steering` has 1 entry (the fix verdict from the review, recorded at 2026-07-04T18:29, which is newer than the last generation at 2026-07-04T18:22)
- Provider is `host-harness` — passenger branch

The fix is targeted and surgical: drop the Ubuntu codename column from the Base table. I don't need to re-read all the sources again since the fix is a single, well-defined change to the existing draft. I need to:
1. Load the current draft
2. Remove the codename column from the Base table
3. Generate the updated handoff
4. Refresh the report
5. Submit the new draft through dogen

Generating markdown table... Replacing the table format with inline values... Finishing the accepted values list and noting that SDKs must match the workshop base or can work with any base if unspecified.*

---

<sub>24m 12s</sub>

### Copilot

Re-draft confirmed — 1 recorded steering entry (the fix verdict), `generations_count` = 1, provider = host-harness. The fix is surgical: drop the codename column from the Base table. I already have the full draft in context; I'll apply only that targeted change.

---

<sub>24m 14s</sub>

### `bash`

**Confirm current commit stamp**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && git rev-parse HEAD

```
74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad
<shellId: 39 completed with exit code 0>
```


---

<sub>24m 20s</sub>

### `edit`

**edit the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/handoff.rst.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/handoff.rst

```
File /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/handoff.rst updated with changes.
```


---

<sub>24m 23s</sub>

### Copilot

Now update the report — new commit stamp, preserve the gap, add gaps_note since the gap list is unchanged:

---

<sub>24m 49s</sub>

### `edit`

**edit the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/report.yaml.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/report.yaml

```
File /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/.dogen/staging/workshop-definition/report.yaml updated with changes.
```


---

<sub>24m 52s</sub>

### `bash`

**Record re-draft via dogen CLI**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen draft "workshop-definition" \
  --draft-file ".dogen/staging/workshop-definition/handoff.rst" \
  --report ".dogen/staging/workshop-definition/report.yaml" \
  --provider host-harness \
  --model "claude-sonnet-4.6" \
  --json 2>&1

```
19:31:19.734 dogen.draft
git: committed 0a6d153 — dogen(workshop-definition): drafted — draft #2 via host-harness
{"unit": "workshop-definition", "provider": "host-harness", "draft_path": "/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/workshop-definition.rst", "progress": "drafted", "reason": null, "stale_plan": false, "unsteered_redraft": false, "commit": "0a6d153716a45eb6a03fb31a02e6a6f2c2295f10"}
<shellId: 40 completed with exit code 0>
```


---

<sub>24m 55s</sub>

### Copilot

---

## dogen-write: workshop-definition

- **Provider:** host-harness (claude-sonnet-4.6)
- **Handoff:** `.dogen/staging/workshop-definition/handoff.rst`
- **Report:** `.dogen/staging/workshop-definition/report.yaml`
- **Recorded draft:** `docs/reference/definition-files/workshop-definition.rst`
- **Committed:** `0a6d153` — `dogen(workshop-definition): drafted — draft #2 via host-harness`
- **Progress:** drafted
- **Plan:** fresh

The only change: the Base section's two-column table (with ungrounded codenames) is replaced by an inline enumeration of the four version strings, matching the sibling `sdk-definition.rst` style.

**Next: invoke `dogen-review` to review the draft.**

---

<sub>28m 38s</sub>

### User

/dogen-review

---

<sub>28m 42s</sub>

### Reasoning

*The user wants me to invoke the dogen-review skill again.*

---

<sub>28m 42s</sub>

### `skill`

**dogen-review**

<details>
<summary>Arguments</summary>

```json
{
  "skill": "dogen-review"
}
```

</details>

```
Skill "dogen-review" loaded successfully. Follow the instructions in the skill context.
```


---

<sub>28m 45s</sub>

### Reasoning

*Let me follow the skill instructions. I need to:
1. Read the unit state
2. Read the drafted page
3. Ask for review mode
4. Present provenance summary
5. (If review mode) Run findings review
6. Elicit verdict and record it

Let me do steps 1 and 2 in parallel.*

---

<sub>28m 50s</sub>

### `bash`

**Read unit state**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen unit show "workshop-definition" --json --latest 2>&1

```
{"unit": {"schema_version": 1, "unit_id": "workshop-definition", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "title": "Workshop definition", "sources": [{"path": "internal/workshop/workshop_file.go", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/reference/definition-files/schema.json", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}, {"path": "docs/examples/workshop-golang.yaml", "ref": null, "commit": "5e3636a74be47e82b6a2586aa79674f9724c36ea", "role": "primary"}], "sphinx_target": "reference/definition-files/workshop-definition.rst", "extra_targets": [], "steering_notes": "The page must give workshop users everything they need to get any field in workshop.yaml right without consulting another page; it should cover every field's type, whether it is required, its default, and its constraints (name format, accepted bases, valid action names), structured so it works both as a first-read introduction and a quick-lookup reference for experienced users arriving from elsewhere."}, "format": "rst", "progress": "drafted", "signoff": {"author": "Artem Konev", "at": "2026-07-04T18:12:07.674646+00:00", "intent": "reference", "audience": "Workshop users who author workshop.yaml by hand \u2014 both first-time authors and experienced users arriving from other tools or projects", "plan_hash": "fe06b324249c9d5f9da3e9fa0aefed5ab5e45814fbe5b0a1dea423c0af0e3ece", "commit": "4f7b67d0dd7672c1265eccaed87f9481cb2d9b84"}, "steering": [{"author": "Artem Konev", "at": "2026-07-04T18:29:13.612012+00:00", "note": "Drop the 'Ubuntu release' column from the Base table. The codenames are not grounded in any recorded source, and the entry for ubuntu@26.04 ('Plucky Puffin') is factually wrong \u2014 that is Ubuntu 25.04's codename. List only the four accepted version strings as a single-column table or inline list, matching the sibling sdk-definition.rst style.", "origin": "review"}], "generations": [{"model": "claude-sonnet-4.6", "model_version": "", "effort": "medium", "tooling_version": "0.0.0", "sdk": "", "provider": "host-harness", "mode": "passenger", "context_origins": [{"path": "internal/workshop/workshop_file.go", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": ""}, {"path": "docs/reference/definition-files/schema.json", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": ""}, {"path": "docs/examples/workshop-golang.yaml", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": ""}, {"path": "docs/examples/workshop-go-dev.yaml", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": ""}, {"path": "docs/examples/workshop-try-go.yaml", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": ""}, {"path": "docs/examples/workshop-digits-cuda.yaml", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": ""}, {"path": "internal/sdk/validate.go", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "source of AllowedBases list and ValidateName constraints"}, {"path": "internal/sdk/sdk.go", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "source of Source enum, IsSystem, IsSketch"}, {"path": "internal/sdk/channel.go", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "source of ParseChannel, channel component constraints"}, {"path": "docs/reference/definition-files/sdk-definition.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "sibling page \u2014 used for heading conventions, list-table format, dropdown schema pattern, see-also structure; inline enumeration style used for base values"}, {"path": "docs/reference/definition-files/sdkcraft-definition.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "sibling page \u2014 checked anchor label ref_sdkcraft_definition and cross-ref to ref_workshop_definition"}, {"path": "docs/reference/definition-files/index.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "confirmed waiting toctree slot (workshop-definition), cross-refs to exp_workshop_definition and ref_workshop_definition"}, {"path": "docs/reference/cli/workshop-init.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "confirmed anchor label ref_workshop_init for see-also"}, {"path": "docs/reference/cli/workshop-run.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "confirmed anchor label ref_workshop_run for see-also"}, {"path": "docs/reference/workshops.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "checked for any existing workshop.yaml location documentation"}, {"path": "docs/conf.py", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "confirmed |ws_markup| and |sdk_markup| substitution definitions"}, {"path": ".dogen/context/doc-style.md", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "voice conventions; noted terminology drift between workshop.yaml and .workshop/NAME.yaml forms"}, {"path": "docs/explanation/workshops/concepts.rst", "commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "note": "confirmed anchor labels exp_workshop_concepts and exp_workshop_definition for see-also"}], "tools_used": ["view", "bash", "grep", "edit"], "gaps": ["Merge/conflict resolution semantics when a workshop-level slot definition shares a name with a slot already defined in the SDK's own definition \u2014 the schema describes them as supplementary but does not specify resolution order when names collide; this edge case is not documented in the page."], "gaps_note": "", "files": [{"path": "docs/reference/definition-files/workshop-definition.rst", "sha256": "f5db8f264a36ed3b65d26cfb514bc5da7c8228859303c870ce2f3d2257bbfb3d"}], "run_id": "019f2e663bb66a261a8bd87bacfd988c", "at": "2026-07-04T18:31:19.735740+00:00", "action": "draft", "draft_path": "docs/reference/definition-files/workshop-definition.rst", "draft_sha256": "f5db8f264a36ed3b65d26cfb514bc5da7c8228859303c870ce2f3d2257bbfb3d", "handoff_path": ".dogen/staging/workshop-definition/handoff.rst", "source_commit": "74ca0bd8d0a43ff8faac7d084dbf2a427fb70bad", "steering_count": 1, "reviewer_edit_count": 1}], "generations_count": 2, "reviewer_edits": [{"at": "2026-07-04T18:29:13.611998+00:00", "reviewer": "Artem Konev", "summary": "Drop the 'Ubuntu release' column from the Base table. The codenames are not grounded in any recorded source, and the entry for ubuntu@26.04 ('Plucky Puffin') is factually wrong \u2014 that is Ubuntu 25.04's codename. List only the four accepted version strings as a single-column table or inline list, matching the sibling sdk-definition.rst style.", "verdict": "fix", "draft_sha256": "", "files": []}]}
<shellId: 41 completed with exit code 0>
```


---

<sub>28m 50s</sub>

### `view`

**view the file at /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/workshop-definition.rst.**

/home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot/docs/reference/definition-files/workshop-definition.rst

<details>
<summary>291 lines</summary>

```
.. _ref_workshop_definition:

.. meta::
   :description: Reference for the workshop.yaml definition file. Covers
                 filename and location, top-level fields, SDK entries,
                 connections, actions, the JSON Schema, and worked examples.

Workshop definition
===================

.. @artefact workshop definition

The :file:`workshop.yaml` file is the workshop definition:
|ws_markup| reads it when it launches, refreshes, or restores a workshop.
You author it by hand in the project directory,
or generate a starting point with :command:`workshop init`.


Filename and location
---------------------

|ws_markup| looks for the definition in the project directory.
Three forms are accepted:

- :file:`workshop.yaml` — single-workshop form at the project root.
- :file:`.workshop.yaml` — alternate single-workshop form at the project root.
- :file:`.workshop/<NAME>.yaml` — named form in the :file:`.workshop/`
  directory.
  :command:`workshop init <NAME>` creates this form.
  When this form is used,
  the value of :samp:`name` in the file must match the file's base name.

All three forms are equivalent in capability;
the choice is a project convention.


Top-level fields
----------------

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`name`
     - string
     - yes
     - Workshop name.
       See :ref:`ref_workshop_definition_name`.

   * - :samp:`base`
     - string
     - yes
     - Base operating-system image.
       See :ref:`ref_workshop_definition_base`.

   * - :samp:`sdks`
     - list
     - no
     - Ordered list of SDK entries to install.
       See :ref:`ref_workshop_definition_sdks`.

   * - :samp:`connections`
     - list
     - no
     - Explicit plug-to-slot connections.
       See :ref:`ref_workshop_definition_connections`.

   * - :samp:`actions`
     - object
     - no
     - Named shell scripts, available via :command:`workshop run`.
       See :ref:`ref_workshop_definition_actions`.

No other keys are accepted.


.. _ref_workshop_definition_name:

Name
----

The :samp:`name` field is a string identifying the workshop.

Constraints:

- Must start with a lowercase letter.
- May contain lowercase letters, digits, and single hyphens between characters.
- At most 40 characters.
- Matches the pattern :regexp:`^[a-z](?:-?[a-z0-9])*$`.

Valid examples: :samp:`dev`, :samp:`go-dev`, :samp:`digits-cuda`.


.. _ref_workshop_definition_base:

Base
----

The :samp:`base` field names the Ubuntu release used as the container image.

Accepted values: :samp:`ubuntu@20.04`, :samp:`ubuntu@22.04`,
:samp:`ubuntu@24.04`, or :samp:`ubuntu@26.04`.

SDKs that declare a base must match the workshop base.
SDKs that do not declare a base are accepted on any workshop.


.. _ref_workshop_definition_sdks:

SDK entries
-----------

The :samp:`sdks` field is a list of SDK entries.
|ws_markup| installs them in declaration order, on top of the base image.
The system SDK is installed first automatically and does not need to be listed.
Each SDK name must appear at most once in the list.

Each entry has the following fields:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`name`
     - string
     - yes
     - SDK to install.
       See :ref:`ref_workshop_definition_sdk_name`.

   * - :samp:`channel`
     - string
     - no
     - Store channel used to retrieve and refresh the SDK.
       See :ref:`ref_workshop_definition_sdk_channel`.

   * - :samp:`plugs`
     - object
     - no
     - Plug definitions and bindings for this SDK entry.
       See :ref:`ref_workshop_definition_sdk_plugs`.

   * - :samp:`slots`
     - object
     - no
     - Additional slot definitions for this SDK entry.
       See :ref:`ref_workshop_definition_sdk_slots`.

No other keys are accepted within an SDK entry.


.. _ref_workshop_definition_sdk_name:

SDK name
~~~~~~~~

The :samp:`name` field identifies the SDK to install.
An optional prefix controls the source:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 3 5

   * - Form
     - Source

   * - :samp:`<name>` (no prefix)
     - SDK Store

   * - :samp:`try-<name>`
     - Locally tried SDK (from :command:`sdkcraft try`)

   * - :samp:`project-<name>`
     - In-project SDK under :file:`.workshop/<name>/`

The underlying :samp:`<name>` must:

- contain at least one lowercase letter,
- consist of lowercase letters, digits, and single hyphens between characters,
- not be :samp:`agent` (reserved),
- be at most 40 characters (44 with :samp:`try-`; 48 with :samp:`project-`).

The names :samp:`system` and :samp:`sketch` identify implicit SDKs
that |ws_markup| installs regardless of whether they appear in the list.
You may list them explicitly to attach per-workshop plug or slot definitions.


.. _ref_workshop_definition_sdk_channel:

Channel
~~~~~~~

The :samp:`channel` field selects the Store channel from which |ws_markup|
retrieves and refreshes the SDK.
Omitting it defaults to :samp:`latest/stable`.

The field has no effect on :samp:`try-`, :samp:`project-`, :samp:`system`,
or :samp:`sketch` entries, but must be well-formed when present.

Format: :samp:`[<track>/]<risk>[/<branch>]` or :samp:`<track>` alone.

Components:

- **risk**: one of :samp:`stable`, :samp:`candidate`, :samp:`beta`, :samp:`edge`.
- **track**: alphanumeric with underscores, hyphens, and dots as separators;
  at most 28 characters; must not equal a risk name.
- **branch**: alphanumeric with hyphens and dots as separators;
  at most 128 characters; must not equal a risk name.

Valid examples: :samp:`stable`, :samp:`edge`, :samp:`1.26`,
:samp:`1.26/stable`, :samp:`latest/stable/hotfix-123`.


.. _ref_workshop_definition_sdk_plugs:

Plugs
~~~~~

The :samp:`plugs` key maps plug names to plug definitions or plug bindings.

Plug names must start with a lowercase letter and contain only lowercase letters,
digits, and single hyphens between characters.

Each value takes one of the following forms:

**Inline plug definition**
   A mapping with an :samp:`interface` key and interface-specific attributes:

   .. code-block:: yaml

      plugs:
        cuda:
          interface: mount
          workshop-target: /usr/local/cuda/lib64

**Interface shorthand**
   A string naming the interface,
   or :samp:`null` to use the plug name as the interface name:

   .. code-block:: yaml

      plugs:
        ssh-agent: null    # interface is ssh-agent
        data: my-iface     # interface is my-iface

**Plug binding**
   A mapping with a single :samp:`bind` key whose value is a plug reference
   in the form :samp:`<sdk>:<plug>`:

   .. code-block:: yaml

      plugs:
        data:
          bind: go:mod-cache

   Constraints on plug bindings:

   - A bound plug must not define any other attributes alongside :samp:`bind`.
   - A bound plug must not also appear in :samp:`connections`.
   - The target plug must not itself be bound.
   - Neither the binding plug nor the target may belong to the system SDK.
   - The target SDK must be listed in the workshop's :samp:`sdks` entries
     or be :samp:`sketch`.

For interface-specific attributes accepted in inline definitions,
see :ref:`ref_sdk_definition_interfaces`.


.. _ref_workshop_definition_sdk_slots:

Slots
~~~~~

The :samp:`slots` key maps slot names to slot definitions.
These supplement the SDK's own slot definitions.

Slot names must start with a lowercase letter and contain only lowercase letters,
digits, and single hyphens between characters.

Each value takes one of the following forms:

**Inline slot definition**
   A mapping with an :samp:`interface` key and interface-specific attributes:

   .. code-block:: yaml

      slots:
        images:
          interface: mount
          workshop-source: $SDK/images

**Interface shorthand**
   A string naming the interface,
   or :samp:`null` to use the slot name as the interface name.

For interface-specific attributes, see :ref:`ref_sdk_definition_interfaces`.


.. _ref_workshop_definition_connections:

Connections
-----------

The :samp:`connections` field is a list of explicit plug-to-slot pairs,
applied in addition to any automatic connections.

Each entry requires both keys:

.. list-table::
   :header-rows: 1
   :width: 95
   :widths: 2 1 1 6

   * - Key
     - Type
     - Required
     - Description

   * - :samp:`plug`
     - string
     - yes
     - Plug reference in the form :samp:`<sdk>:<plug>`.
       The :samp:`<sdk>` portion may be empty
       (for example, :samp:`:ssh-agent`) to refer to the system SDK.

   * - :samp:`slot`
     - string
     - yes
     - Slot reference in the form :samp:`<sdk>:<slot>`.
       The :samp:`<sdk>` portion may be empty to refer to the system SDK.

No other keys are accepted within a connection entry.

Constraints:

- Both endpoints must reference an SDK that is listed in :samp:`sdks`
  or is an implicit SDK (:samp:`system`, :samp:`sketch`).
- A plug that is bound (see :ref:`ref_workshop_definition_sdk_plugs`)
  may not also appear in :samp:`connections`.


.. _ref_workshop_definition_actions:

Actions
-------

The :samp:`actions` field is a map of named shell scripts.
Each action is available via :command:`workshop run`.

Action names must start with a lowercase letter and contain only lowercase
letters, digits, and single hyphens between characters
(the same pattern as :ref:`workshop names <ref_workshop_definition_name>`).

Each value is a YAML string containing the script body.
YAML literal blocks (:samp:`|`) are the conventional form for multi-line scripts.

The script runs inside the workshop as a bash login shell
with :samp:`errexit` and :samp:`pipefail` set.
Positional parameters :samp:`$@`, :samp:`$1`, :samp:`$2`, and so on
receive any arguments passed to the action.


JSON Schema
-----------

.. @artefact workshop schema

The following JSON Schema describes the complete accepted structure of
:file:`workshop.yaml`:

.. dropdown:: Workshop definition schema

   .. literalinclude:: schema.json
      :language: json


Examples
--------

A minimal workshop with a single Store SDK and a pinned track:

.. literalinclude:: ../../examples/workshop-golang.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop with plug bindings across two SDK entries:

.. literalinclude:: ../../examples/workshop-go-dev.yaml
   :language: yaml
   :caption: workshop.yaml

A workshop with explicit connections and inline plug and slot definitions:

.. literalinclude:: ../../examples/workshop-digits-cuda.yaml
   :language: yaml
   :caption: workshop.yaml


See also
--------

Explanation:

- :ref:`exp_workshop_concepts`
- :ref:`exp_workshop_definition`

Reference:

- :ref:`ref_sdk_definition`
- :ref:`ref_sdkcraft_definition`
- :ref:`ref_workshop_init`
- :ref:`ref_workshop_run`
```

</details>


---

<sub>28m 54s</sub>

### Reasoning

*Good. The draft is confirmed at progress = `drafted`. The fix has been applied: the Base section now uses inline enumeration instead of the two-column table with codenames. Let me now ask for the review mode.*

---

<sub>28m 55s</sub>

### Copilot

Draft #2 confirmed. Fix applied cleanly — Base section now uses inline enumeration.

---

<sub>29m 6s</sub>

### `ask_user`

**How would you like to review draft #2 of workshop-definit...**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "record — just show provenance and record my verdict",
    "review — full findings review first"
  ],
  "question": "How would you like to review draft #2 of workshop-definition?"
}
```

</details>

```
User selected: review — full findings review first
```


---

<sub>29m 9s</sub>

### Reasoning

*Full review mode again. The draft is very similar to the previous one, just with the Base table replaced by inline enumeration. Let me do a thorough review of the current draft.

Main things to check:
1. **Source-fidelity**: Is the fix correctly applied? Yes - the Base section now says "Accepted values: :samp:`ubuntu@20.04`, :samp:`ubuntu@22.04`, :samp:`ubuntu@24.04`, or :samp:`ubuntu@26.04`." - clean, matches the sibling style. No more codenames.

2. All the other claims are unchanged from the previous draft which I already reviewed. The only change is the Base section.
3. Now sweeping through all four dimensions again. Source-fidelity checks out with the Base section now showing only version strings in the same style as the SDK definition. Completeness is intact with all outline items and the gap about slot name-conflict resolution still properly noted. Structure-fit looks good so far with the RST formatting holding up after the Base section change from table to inline text.

The new Base section uses inline text with sample markup for each version string, which is valid RST and actually cleaner than the previous format. All other structural elements remain unchanged, and I'm not seeing any new clarity issues either. This draft appears ready to move forward.*

---

<sub>29m 19s</sub>

### Copilot

---

## dogen-review — findings: workshop-definition

### Provenance

- **Signoff:** Artem Konev at 2026-07-04T18:12 UTC — plan **fresh**
- **Provider / mode / model:** host-harness / passenger / claude-sonnet-4.6 (host-asserted)
- **Declared sources** (3, all primary, at `5e3636a`):
  `internal/workshop/workshop_file.go`, `docs/reference/definition-files/schema.json`, `docs/examples/workshop-golang.yaml`
- **Actually read** (18 origins, all at `74ca0bd`): all 3 declared sources plus 15 discoveries — same set as draft #1, with the sibling note updated to reflect the inline enumeration style sourced from `sdk-definition.rst`
- **Writer-declared gaps:** Slot name-collision semantics when workshop-level and SDK-level definitions share a name — correctly left out of prose, grounded in schema's "supplementary" description
- **Steering stream:** 1 entry (the fix verdict, origin=review): *"Drop the 'Ubuntu release' column from the Base table…"* — applied in this pass
- **Progress:** drafted (draft #2, `generations_count` = 2)

---

### source-fidelity

(none — fix applied correctly; Base section now reads `Accepted values: :samp:\`ubuntu@20.04\`, :samp:\`ubuntu@22.04\`, :samp:\`ubuntu@24.04\`, or :samp:\`ubuntu@26.04\`.` with no codenames; all other claims unchanged from the previously-verified pass)

### completeness

(none — all 9 outline items present; recorded gap unchanged and appropriate)

### structure-fit

(none — RST well-formed; inline enumeration in the Base section is valid; all heading levels, directive indentation, and relative paths unchanged and correct)

### clarity

(none)

**Findings: 0 total.**
*(Priority = review findings, NOT the CLI run-status codes.)*

---

---

<sub>30m 27s</sub>

### `ask_user`

**What's your verdict on draft #2?**

<details>
<summary>Arguments</summary>

```json
{
  "choices": [
    "accept",
    "fix — I have a correction",
    "redraft — full new pass"
  ],
  "question": "What's your verdict on draft #2?"
}
```

</details>

```
User selected: accept
```


---

<sub>30m 35s</sub>

### `bash`

**Record accept verdict**

$ cd /home/artem.konev@canonical.com/Documents/DOCPR-2845/smoke-copilot && dogen review "workshop-definition" \
  --verdict accept \
  --note "All outline items present, claims grounded in recorded sources, RST well-formed, fix applied correctly." \
  --json 2>&1

```
git: committed 15a7cb0 — dogen(workshop-definition): reviewed — review: accept
{"unit": "workshop-definition", "provider": null, "draft_path": null, "progress": "reviewed", "reason": null, "verdict": "accept", "next": "accepted \u2014 the publishing commit/PR is yours", "next_id": "publish", "commit": "15a7cb071b4519efcdc4e2f9db1dfbdd459f60d0"}
<shellId: 42 completed with exit code 0>
```


---

<sub>30m 40s</sub>

### Copilot

### Verdict

**accept** — draft sealed.
**Committed:** `15a7cb0` — `dogen(workshop-definition): reviewed — review: accept`

The exact draft text is now sealed by its SHA-256 on the review record. **The publishing commit is yours.**

---

<sub>Generated by [GitHub Copilot CLI](https://github.com/features/copilot/cli)</sub>
