#!/usr/bin/env bash
# runmeta.sh — the RUN metadata a validation leg is measured from.
#
# Usage: bash validation/runmeta.sh begin --leg <leg> --repo <dir>
#                                         [--baseline-ref <ref>] [--harness <name>]
#                                         [--model <id>]
#        bash validation/runmeta.sh end   --leg <leg> --repo <dir> --unit <id> [--unit <id>]…
#                                         [--transcript-file <path>]
#                                         --metric <key>=<value> … [--attribute <item>=<account>]…
#
# (run from anywhere; paths resolve from $0)
#
# The boundary, stated once: this script writes into and runs git against ANOTHER repository —
# the target documentation repo holding the unit under measurement — not against a hermetic
# temp tree. It therefore does NOT source `tests/lib.sh`: that file pins
# `CRAYON="$REPO_ROOT/crayon.py"` at the in-tree executable and its `setup_repo` exports
# `CRAYON_TEST_HOOKS=1`, and either one would make a measurement of the target repo a
# measurement of this one. The guards worth copying from `tests/lib.sh:191-199` — the
# three-check `mktemp -d` and the pinned git config — are copied below; nothing else is.
#
# What it writes: `<repo>/validation/RUN-<leg>.json`. The `sphinx` key is a
# plain non-empty STRING because `crayon`'s `sphinx_result()` (dogen:7209-7243) accepts nothing
# else — it scans `RUN-*.json` in sorted NAME order, takes the first usable one, collapses the
# value to 120 characters and renders it. The structured `sphinx_before` / `sphinx_after` /
# `sphinx_attribution` siblings are invisible to the tool and belong entirely to
# `validation/score.py`'s `[sphinx]` line. That shape is why the RUN file costs `crayon` zero
# lines, and it is why there must be exactly ONE RUN file per working tree: with two, the tool
# would silently pick one by name order and say nothing.
#
# THE TWO-STEP TRANSCRIPT RULE — load-bearing, and not to be "fixed":
# `end` writes the transcript's resolved PATH and `"sha256": null`. The AUTHOR fills the sha
# from OUTSIDE the session, before the RUN file is committed. A sha taken by a tool call inside
# the session being measured is stale the moment that tool call is itself appended to the
# transcript, so a self-sha here would be a fabricated measurement rather than a weak one. A
# later reader must not collapse the two steps into one. `score.py protocol`'s second check is
# what refuses a RUN whose sha is still null.
#
# The six session metrics have exactly ONE authoring site, and it is this file's `metrics`
# object. They arrive as `--metric key=value` flags supplied by the AUTHOR at `end`, not by the
# agent mid-run: three of the six — avoidable questions, help requests, and whether `resume`
# needed the author — are judgements about the session rather than counters a script can read.
# A session record and a leg's checklist POINT at this file and do not
# restate the values; a second place where the numbers are typed is drift, not redundancy.
#
# The Sphinx diff is NOT computed here. This script records both builds' exit codes and their
# FULL diagnostics text, never filtered by filename, and writes a human one-line `sphinx`
# summary naming both halves. The normalise-diff-and-attribute bookkeeping is `score.py`'s
# `[sphinx]` line, which is the one place it is computed — a second computation in bash, over
# un-normalised text, is exactly the drift that would let two readings of one build pair
# disagree.
#
# Every JSON read and write goes through `python3`, never `jq`: `jq`
# is not a documented prerequisite of this repository and is not guaranteed on the runner, so
# a single `jq` call would make the RUN file unwritable precisely where it matters most. Every
# `git`, `crayon` and `sphinx-build` call uses a list-form argument vector with `-C <dir>` and
# never a shell string.
#
# Exit codes follow the project's 0/1/2 lint contract (tests/check_traces.py, and
# tests/install_smoke.sh for the bash side):
#   0  the RUN file was written
#   1  refused — a bad argument, a repo that is not a git work tree, a RUN file for another
#      leg, an unresolvable baseline ref, or a missing session metric. Each names what it found.
#   2  NOTHING was written — no subcommand was given. A script that silently defaulted to
#      `begin` would overwrite a RUN file someone meant to `end`.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Pinned OUTSIDE every git call below, the way `tests/install_smoke.sh` pins them: a
# developer-side or runner-side global identity — `commit.gpgsign` above all — must not reach
# a repository this script only reads.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

# The Sphinx binary and the tool, both indirections rather than fixed paths. `SPHINX_BUILD` is
# what lets the fixtures point at a stub and lets CI — which has no Sphinx and no
# `docs/.venv` — run them at all; `CRAYON` is what `score.py` already reads, because `crayon` is
# not checked into a documentation repository. The fallback order is `score.py`'s own
# (`_crayon_executable`): the environment, then this kit's in-tree file, then PATH.
if [ -n "${CRAYON:-}" ]; then
    CRAYON_BIN="$CRAYON"
elif [ -f "$REPO_ROOT/crayon.py" ]; then
    CRAYON_BIN="$REPO_ROOT/crayon.py"
else
    CRAYON_BIN="crayon"
fi

# The six session metric keys, in the session template's own order
# This tuple is the definition; nothing below re-types it.
METRIC_KEYS=(install time_to_usable_draft avoidable_questions
             manual_crayon_commands help_requests resume_invocations)

# A conservative leg name, validated BEFORE it becomes a filename. A leg is a
# pre-registered file under `validation/legs/`, so the alphabet is the one those names use.
LEG_RE='^[A-Za-z0-9][A-Za-z0-9._-]*$'

# Both temporary trees this script makes: `WORK_DIR` for a Sphinx build's HTML output and its
# captured streams, `LIST_DIR` for the list files handed to the JSON writer. Named, guarded on
# non-empty, and removed by one trap — `rm -rf ""` on an unset variable is the accident the
# guards exist against (see `cleanup` in tests/install_smoke.sh).
WORK_DIR=""
LIST_DIR=""

cleanup() {
    if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        rm -rf "$WORK_DIR"
    fi
    if [ -n "$LIST_DIR" ] && [ -d "$LIST_DIR" ]; then
        rm -rf "$LIST_DIR"
    fi
    return 0
}
trap cleanup EXIT

usage() {
    cat >&2 <<'USAGE'
usage: runmeta.sh begin --leg <leg> --repo <dir> [--baseline-ref <ref>]
                        [--harness <name>] [--model <id>]
       runmeta.sh end   --leg <leg> --repo <dir> --unit <id> [--unit <id>]...
                        --metric <key>=<value> ... [--attribute <item>=<account>]...
                        [--transcript-file <path>]

  begin  writes <repo>/validation/RUN-<leg>.json with the harness, model, tool, skills and
         baseline records plus the BEFORE Sphinx build.
  end    adds the AFTER Sphinx build, the origins digests, the transcript record and the
         six session metrics. Use --transcript-file when the harness has no
         automatic transcript resolver (for example, Copilot CLI).
USAGE
}

refuse() {
    printf 'runmeta: %s\n' "$1" >&2
    exit 1
}

# `cd ""` SUCCEEDS in bash and leaves the shell where it is, so `cd "$X" || exit 1` is not a
# guard on its own. With an unchecked `mktemp -d` — a full or read-only /tmp, a
# restrictive TMPDIR — the Sphinx build below would write its HTML into the CURRENT directory.
# The three checks make the failure loud instead.
make_work_dir() {
    WORK_DIR=$(mktemp -d) || refuse "could not create a temporary directory for the build output"
    [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ] ||
        refuse "mktemp -d returned something that is not a directory"
}

make_list_dir() {
    LIST_DIR=$(mktemp -d) || refuse "could not create a temporary directory for the lists"
    [ -n "$LIST_DIR" ] && [ -d "$LIST_DIR" ] ||
        refuse "mktemp -d returned something that is not a directory"
}

# --- shared argument parsing ---------------------------------------------------------------

LEG=""
REPO=""
BASELINE_REF="validation-base-v6"
HARNESS="claude-code"
MODEL=""
UNITS=()
METRICS=()
ATTRIBUTES=()
TRANSCRIPT_FILE=""
TRANSCRIPT_FILE_GIVEN=0

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --leg)          [ "$#" -ge 2 ] || refuse "--leg needs a value"; LEG="$2"; shift 2 ;;
            --repo)         [ "$#" -ge 2 ] || refuse "--repo needs a value"; REPO="$2"; shift 2 ;;
            --baseline-ref) [ "$#" -ge 2 ] || refuse "--baseline-ref needs a value"; BASELINE_REF="$2"; shift 2 ;;
            --harness)      [ "$#" -ge 2 ] || refuse "--harness needs a value"; HARNESS="$2"; shift 2 ;;
            --model)        [ "$#" -ge 2 ] || refuse "--model needs a value"; MODEL="$2"; shift 2 ;;
            --unit)         [ "$#" -ge 2 ] || refuse "--unit needs a value"; UNITS+=("$2"); shift 2 ;;
            --metric)       [ "$#" -ge 2 ] || refuse "--metric needs a key=value"; METRICS+=("$2"); shift 2 ;;
            --attribute)    [ "$#" -ge 2 ] || refuse "--attribute needs an item=account"; ATTRIBUTES+=("$2"); shift 2 ;;
            --transcript-file) [ "$#" -ge 2 ] && [ -n "$2" ] || refuse "--transcript-file needs a nonempty path"; TRANSCRIPT_FILE="$2"; TRANSCRIPT_FILE_GIVEN=1; shift 2 ;;
            *)              refuse "unknown argument: $1" ;;
        esac
    done
}

# `--repo` resolved to an absolute path and asserted to be a git work tree, and `--leg`
# validated before it becomes a filename. Every write below is under `<repo>/validation/`, and
# nothing is ever written to $HOME or to this repository.
resolve_target() {
    [ -n "$LEG" ] || refuse "--leg is required"
    [ -n "$REPO" ] || refuse "--repo is required"
    # The DECLARED regex, enforced. The check used to be
    # `case "$LEG" in *[!A-Za-z0-9._-]* | "" )`, which does not anchor the FIRST character, so
    # `--leg ..`, `--leg -x` and `--leg .hidden` all passed a refusal message naming a regex the
    # check did not implement. No traversal followed — `/` is excluded and the value is only
    # ever a filename component — but this guard is cited on `score.py`'s side as the reason a
    # leg name is trustworthy, and a name trusted there unchecked reads outside the tree. The
    # value goes in on STDIN, so a leading `-` is data and never an option. One place, one
    # expression.
    printf '%s' "$LEG" | grep -Eq "$LEG_RE" ||
        refuse "--leg $LEG does not match $LEG_RE"
    [ -d "$REPO" ] || refuse "--repo $REPO is not a directory"
    REPO="$(cd "$REPO" && pwd)"
    git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
        refuse "--repo $REPO is not a git work tree"
    RUN_DIR="$REPO/validation"
    RUN_PATH="$RUN_DIR/RUN-${LEG}.json"
}

# --- the pieces `begin` records -------------------------------------------------------------

# One Sphinx build, from `<repo>/docs`, with its exit code in `SPHINX_EXIT` and its FULL stderr
# in the file named by `SPHINX_DIAGNOSTICS`. Never `make -C docs html`: that also provisions the
# venv and emits sitemap artefacts, and is not the reproducible form. Nothing here filters the
# diagnostics — by filename, by severity or by text. Filtering the evidence to make a claim
# come out clean is the exact failure the Sphinx rule exists against.
run_sphinx() {
    local build="${SPHINX_BUILD:-$REPO/docs/.venv/bin/sphinx-build}"
    [ -d "$REPO/docs" ] || refuse "$REPO/docs does not exist; there is no Sphinx source to build"
    make_work_dir
    SPHINX_DIAGNOSTICS="$WORK_DIR/diagnostics.txt"
    ( cd "$REPO/docs" && "$build" -c . -b html . "$WORK_DIR/html" ) \
        >"$WORK_DIR/stdout.txt" 2>"$SPHINX_DIAGNOSTICS"
    SPHINX_EXIT=$?
    # A build that could not be EXECUTED is refused here; any other non-zero exit is recorded
    # and left for `score.py`'s `[sphinx]` line to gate. The split is deliberate: a
    # build that ran and failed is evidence, and a build that never ran is not — and 127 with
    # an empty diagnostics file is exactly what a missing `docs/.venv` or a typo'd
    # `SPHINX_BUILD` produces, which used to be recorded as a build that emitted nothing.
    [ "$SPHINX_EXIT" -ne 127 ] ||
        refuse "$build could not be executed (exit 127); set SPHINX_BUILD to a sphinx-build"
    return 0
}

# The `(path, sha256)` listing under a directory, rendered sorted and digested once. Used for
# the skills root; the origins digests below render the same way with git's blob shas.
digest_tree() {
    python3 -c '
import hashlib, os, sys
root = sys.argv[1]
rows = []
for base, _, names in os.walk(root):
    for name in sorted(names):
        path = os.path.join(base, name)
        with open(path, "rb") as handle:
            rows.append("%s  %s" % (
                hashlib.sha256(handle.read()).hexdigest(),
                os.path.relpath(path, root),
            ))
print(hashlib.sha256("\n".join(sorted(rows)).encode("utf-8")).hexdigest())
' "$1"
}

# --- the origins digests --------------------------------------------------------------------
#
# `baseline` is sha256 over the sorted `(blob-sha, path)` listing of every path the units'
# generations name in `origins[]`, taken from the baseline tag's tree; `context` is that same
# list recomputed from the WORKING TREE at `end`. `protocol`'s fourth check asserts the two are
# equal. A HEAD comparison is deliberately not used: every crayon verb commits, so the target's
# HEAD at `end` necessarily differs from its HEAD at `begin` and the comparison could never
# hold. `origins[]` entries are plain STRINGS in v2.0 (dogen:4832-4856), which is why the
# digest is over the paths they name rather than over per-read commit stamps.

# The union of every named unit's LATEST generation `origins[]`, sorted and deduplicated.
collect_origins() {
    local unit
    for unit in "${UNITS[@]}"; do
        local ledger="$REPO/.crayon/units/$unit/ledger.jsonl"
        [ -f "$ledger" ] || refuse "no ledger for unit $unit: expected a file at $ledger"
        python3 -c '
import json, sys
latest = None
for line in open(sys.argv[1], encoding="utf-8").read().split("\n"):
    if not line:
        continue
    try:
        event = json.loads(line)
    except ValueError:
        continue
    if isinstance(event, dict) and event.get("kind") == "generation":
        latest = event
for entry in (latest or {}).get("origins") or []:
    print(entry)
' "$ledger"
    done | LC_ALL=C sort -u
}

# `<blob-sha>  <path>` for one path at a git tree-ish, or `absent` when the tree has no such
# path. The COMMIT sha is what is passed, never the ref name: the baseline branch and tag share
# a name in the target repo, and a bare reference emits `warning: refname … is ambiguous`.
origins_digest_at() {
    local treeish="$1" path sha rows=""
    while IFS= read -r path; do
        [ -n "$path" ] || continue
        sha=$(git -C "$REPO" rev-parse --quiet --verify "${treeish}:${path}" 2>/dev/null) || sha=""
        [ -n "$sha" ] || sha="absent"
        rows="${rows}${sha}  ${path}"$'\n'
    done <"$ORIGINS_FILE"
    printf '%s' "$rows" | LC_ALL=C sort | python3 -c '
import hashlib, sys
print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())
'
}

# The same listing, recomputed from the working tree. `git hash-object` produces the identical
# blob sha git would record, so the two sides of the comparison are the same instrument.
origins_digest_worktree() {
    local path sha rows=""
    while IFS= read -r path; do
        [ -n "$path" ] || continue
        if [ -f "$REPO/$path" ]; then
            sha=$(git -C "$REPO" hash-object -- "$path" 2>/dev/null) || sha="absent"
        else
            sha="absent"
        fi
        rows="${rows}${sha}  ${path}"$'\n'
    done <"$ORIGINS_FILE"
    printf '%s' "$rows" | LC_ALL=C sort | python3 -c '
import hashlib, sys
print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())
'
}

# --- the transcript record (the PATH half of the two-step rule) ------------------------------
#
# The transcript's home depends on the harness the RUN file records. Claude Code keeps it at
# `~/.claude/projects/<slug>/<session-uuid>.jsonl`, where
# `<slug>` is the project's absolute path with EVERY character outside [A-Za-z0-9-] replaced
# by `-` — not just `/` and `.`. A `@` in a home directory (`/home/user@example.com/...`) is
# the case that proved it: mapping only `/` and `.` yields `-home-user@example-com-...`, a
# directory that never exists, so the resolver silently reported "searched, found nothing"
# for a transcript that was sitting in `-home-user-example-com-...`. When the glob
# matches nothing the DIRECTORY that was searched is recorded and the path is left `null`,
# rather than a guess: naming what was searched is the courtesy every other vacuous-result
# guard in this tree extends.
#
# Every arm is NAMED and the unknown one is refused rather than swallowed. The `case`
# had exactly one named arm and a catch-all `*)` that searched Claude Code's tree, so a RUN
# file recording `copilot-cli`, `cursor`, a typo or the empty string was searched in the wrong
# tree, found nothing, and recorded `{"path": null, "searched": "~/.claude/projects/<slug>"}` —
# "searched, found nothing", the exact vacuous reading commit c572e64 was written to eliminate
# for the opposite harness. `searched` made it legible only to a reader who noticed the
# directory belonged to a harness that did not run. Now the RUN file records WHY nothing was
# found.
resolve_transcript() {
    if [ -n "$TRANSCRIPT_FILE" ]; then
        [ -f "$TRANSCRIPT_FILE" ] && [ -r "$TRANSCRIPT_FILE" ] ||
            refuse "--transcript-file $TRANSCRIPT_FILE is not a readable file"
        TRANSCRIPT_PATH=$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$TRANSCRIPT_FILE") ||
            refuse "could not resolve --transcript-file $TRANSCRIPT_FILE"
        TRANSCRIPT_DIR="explicit --transcript-file"
        return 0
    fi

    # The RUN file already records WHICH harness drove the leg, so the resolver honours it
    # rather than assuming one. `begin` is the authoring site for `harness`; reading it back
    # here keeps a single source of truth, and an `end` run against a RUN file written by a
    # different harness cannot silently search the wrong tree.
    local harness="$HARNESS"
    if [ -f "$RUN_PATH" ]; then
        harness=$(python3 -c '
import json, sys
try:
    print(json.loads(open(sys.argv[1], encoding="utf-8").read()).get("harness") or "")
except Exception:
    print("")
' "$RUN_PATH") || harness="$HARNESS"
        [ -n "$harness" ] || harness="$HARNESS"
    fi

    TRANSCRIPT_PATH=""
    case "$harness" in
        codex-cli)
            # Codex rollouts are date-sharded under ~/.codex/sessions and are NOT namespaced by
            # project, so "newest file" would happily return an unrelated session. Line 0 is a
            # `session_meta` record carrying the session's own `cwd`; match on that, then take
            # the newest of the matches. A run with no match records the directory it searched.
            TRANSCRIPT_DIR="${HOME}/.codex/sessions"
            if [ -d "$TRANSCRIPT_DIR" ]; then
                TRANSCRIPT_PATH=$(python3 -c '
import json, os, sys
root, repo = sys.argv[1], os.path.realpath(sys.argv[2])
best = (-1.0, "")
for dirpath, _dirnames, filenames in os.walk(root):
    for name in filenames:
        if not (name.startswith("rollout-") and name.endswith(".jsonl")):
            continue
        path = os.path.join(dirpath, name)
        try:
            with open(path, encoding="utf-8") as fh:
                first = fh.readline()
            meta = json.loads(first)
        except Exception:
            continue
        if meta.get("type") != "session_meta":
            continue
        cwd = (meta.get("payload") or {}).get("cwd")
        if not cwd or os.path.realpath(cwd) != repo:
            continue
        mtime = os.path.getmtime(path)
        if mtime > best[0]:
            best = (mtime, path)
print(best[1])
' "$TRANSCRIPT_DIR" "$REPO" 2>/dev/null) || TRANSCRIPT_PATH=""
            fi
            ;;
        claude-code|claude)
            TRANSCRIPT_DIR="${HOME}/.claude/projects/$(printf '%s' "$REPO" | sed 's/[^A-Za-z0-9-]/-/g')"
            if [ -d "$TRANSCRIPT_DIR" ]; then
                # `find … -printf` is GNU-only: on a BSD/macOS `find` it fails, the path comes
                # back empty, and the result is "searched, found nothing" again. python3 is
                # what the rest of this file already uses for every other parse.
                TRANSCRIPT_PATH=$(python3 -c '
import os, sys
root = sys.argv[1]
best = (-1.0, "")
for name in os.listdir(root):
    if not name.endswith(".jsonl"):
        continue
    path = os.path.join(root, name)
    if not os.path.isfile(path):
        continue
    mtime = os.path.getmtime(path)
    if mtime > best[0]:
        best = (mtime, path)
print(best[1])
' "$TRANSCRIPT_DIR" 2>/dev/null) || TRANSCRIPT_PATH=""
            fi
            ;;
        *)
            # Not a directory anybody searched: a harness this script cannot resolve a
            # transcript for records WHY, so a later reader is not left inferring it from a
            # path belonging to a harness that did not run.
            TRANSCRIPT_DIR="(no transcript resolver for harness: $harness)"
            TRANSCRIPT_PATH=""
            ;;
    esac
    return 0
}

# --- begin -----------------------------------------------------------------------------------

do_begin() {
    parse_args "$@"
    [ "$TRANSCRIPT_FILE_GIVEN" -eq 0 ] || refuse "--transcript-file is only valid with end"
    resolve_target

    # One RUN file per working tree is `dogen:7209-7243`'s constraint, not a convention: with
    # two present the tool picks the first by NAME order and says nothing about the other.
    if [ -d "$RUN_DIR" ]; then
        local existing
        while IFS= read -r existing; do
            [ -n "$existing" ] || continue
            if [ "$(basename "$existing")" != "RUN-${LEG}.json" ]; then
                refuse "$RUN_DIR already holds $(basename "$existing"), a RUN file for another leg; crayon scans RUN-*.json in sorted name order and would silently pick one of the two"
            fi
        done < <(find "$RUN_DIR" -maxdepth 1 -name 'RUN-*.json' | LC_ALL=C sort)
    fi

    local baseline_commit
    baseline_commit=$(git -C "$REPO" rev-parse --quiet --verify "refs/tags/${BASELINE_REF}^{commit}" 2>/dev/null) ||
        baseline_commit=""
    if [ -z "$baseline_commit" ]; then
        baseline_commit=$(git -C "$REPO" rev-parse --quiet --verify "${BASELINE_REF}^{commit}" 2>/dev/null) ||
            baseline_commit=""
    fi
    [ -n "$baseline_commit" ] ||
        refuse "the baseline ref $BASELINE_REF does not resolve to a commit in $REPO"

    local version_json tool_path tool_sha
    version_json=$("$CRAYON_BIN" version --json 2>/dev/null) || version_json=""
    [ -n "$version_json" ] || refuse "could not read $CRAYON_BIN version --json; set CRAYON to the tool"
    tool_path=$(command -v "$CRAYON_BIN" 2>/dev/null) || tool_path=""
    if [ -n "$tool_path" ] && [ -f "$tool_path" ]; then
        tool_sha=$(python3 -c '
import hashlib, sys
print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())
' "$tool_path")
    else
        tool_sha="null"
    fi

    # The skills digest covers `.agents/skills/`, the v2.0 discovery root, with the ROOT
    # recorded beside it so a later reader knows what was covered. An ABSENT root digests to
    # `null` rather than to a digest of nothing, and `protocol` FLAGs that RUN as incomplete —
    # the leg's whole premise is that the skills are installed.
    local skills_root=".agents/skills" skills_sha
    if [ -d "$REPO/$skills_root" ]; then
        skills_sha=$(digest_tree "$REPO/$skills_root")
    else
        skills_sha="null"
    fi

    run_sphinx
    local summary
    summary="before $(build_half "$SPHINX_EXIT" "$SPHINX_DIAGNOSTICS")"

    mkdir -p "$RUN_DIR"
    python3 -c '
import json, sys
(path, leg, harness, model, version_json, tool_sha, skills_root, skills_sha,
 baseline_ref, baseline_commit, sphinx_exit, diagnostics_path, summary) = sys.argv[1:]
version = json.loads(version_json)
with open(diagnostics_path, "r", encoding="utf-8", errors="replace") as handle:
    diagnostics = handle.read()
data = {
    "leg": leg,
    "harness": harness,
    "model": model,
    # `min_tool` is the tool own __version__, which `version --json` reports as `tool` —
    # exactly the pairing `tests/check_docs.py:584-590` already pins README COMPAT region
    # against, so `protocol` compares the same two numbers rather than a third opinion.
    "tool": {
        "version": version.get("tool"),
        "contract": version.get("contract"),
        "min_tool": version.get("tool"),
        "sha256": None if tool_sha == "null" else tool_sha,
    },
    "skills": {
        "root": skills_root,
        "sha256": None if skills_sha == "null" else skills_sha,
    },
    "baseline": {"ref": baseline_ref, "commit": baseline_commit},
    "sphinx": summary,
    "sphinx_before": {"exit": int(sphinx_exit), "diagnostics": diagnostics},
}
with open(path, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
' "$RUN_PATH" "$LEG" "$HARNESS" "$MODEL" "$version_json" "$tool_sha" \
  "$skills_root" "$skills_sha" "$BASELINE_REF" "$baseline_commit" \
  "$SPHINX_EXIT" "$SPHINX_DIAGNOSTICS" "$summary" ||
        refuse "could not write $RUN_PATH; the RUN file was NOT written"

    # The exit contract's `0  the RUN file was written` made literal. The script runs
    # under `set -u` alone, so an unguarded writer that died — a `version --json` that is
    # non-empty but not JSON makes `json.loads` raise — printed `wrote <path>` and exited 0
    # over a file that does not exist. The POST-CONDITION is asserted rather than the writer's
    # status alone, because those are two different claims.
    [ -f "$RUN_PATH" ] ||
        refuse "the writer reported success but $RUN_PATH is not there; nothing was recorded"

    printf 'runmeta: wrote %s (%s)\n' "$RUN_PATH" "$summary"
    return 0
}

# `exit <n>, <n> warn` for one build half. The warn count is the number of NON-EMPTY diagnostic
# lines, which is the reproducible measure: Sphinx's own "build succeeded, N warnings" sentence
# is on stdout and is a sentence, while the diagnostics themselves are one per line on stderr.
build_half() {
    local code="$1" diagnostics="$2" lines
    lines=$(grep -c '[^[:space:]]' "$diagnostics" 2>/dev/null) || lines=0
    printf 'exit %s, %s warn' "$code" "$lines"
}

# --- end ---------------------------------------------------------------------------------------

do_end() {
    parse_args "$@"
    resolve_target

    [ -f "$RUN_PATH" ] ||
        refuse "no RUN file at $RUN_PATH; run \`runmeta.sh begin --leg $LEG --repo $REPO\` first"
    local recorded_leg
    recorded_leg=$(python3 -c '
import json, sys
print(json.loads(open(sys.argv[1], encoding="utf-8").read()).get("leg"))
' "$RUN_PATH") ||
        refuse "$RUN_PATH cannot be read as JSON; it is not a RUN file this script wrote"
    [ "$recorded_leg" = "$LEG" ] ||
        refuse "$RUN_PATH was written for leg $recorded_leg, not $LEG"

    [ "${#UNITS[@]}" -gt 0 ] || refuse "--unit is required at least once"

    # The six session metrics, refused BY NAME so the author is told which measurement is absent
    # rather than that something is. This is the only authoring site for the six.
    local given=() entry key missing=()
    for entry in "${METRICS[@]}"; do
        case "$entry" in
            *=*) ;;
            *) refuse "--metric $entry is not a key=value pair" ;;
        esac
        given+=("${entry%%=*}")
    done
    for key in "${METRIC_KEYS[@]}"; do
        local found=0 name
        for name in "${given[@]}"; do
            if [ "$name" = "$key" ]; then found=1; fi
        done
        if [ "$found" -eq 0 ]; then missing+=("$key"); fi
    done
    if [ "${#missing[@]}" -gt 0 ]; then
        refuse "the RUN file needs all six session metrics; missing: ${missing[*]}"
    fi

    run_sphinx
    local after_half
    after_half=$(build_half "$SPHINX_EXIT" "$SPHINX_DIAGNOSTICS")

    make_list_dir
    ORIGINS_FILE="$LIST_DIR/origins.txt"
    collect_origins >"$ORIGINS_FILE"
    local baseline_commit baseline_sha context_sha
    baseline_commit=$(python3 -c '
import json, sys
print(json.loads(open(sys.argv[1], encoding="utf-8").read())["baseline"]["commit"])
' "$RUN_PATH") ||
        refuse "$RUN_PATH records no baseline.commit to digest the origins at; it is damaged, and this leg is not recorded"
    [ -n "$baseline_commit" ] ||
        refuse "$RUN_PATH records an empty baseline.commit; there is no tree to digest the origins at"
    baseline_sha=$(origins_digest_at "$baseline_commit")
    context_sha=$(origins_digest_worktree)

    resolve_transcript

    printf '%s\n' "${METRICS[@]}" >"$LIST_DIR/metrics.txt"
    printf '%s\n' "${ATTRIBUTES[@]}" >"$LIST_DIR/attributes.txt"

    # Rewritten ATOMICALLY: a sibling temp file, then a rename. A reader — `crayon summary`
    # included — never sees a half-written RUN file.
    python3 -c '
import json, os, sys
(path, sphinx_exit, diagnostics_path, after_half, baseline_sha, context_sha,
 origins_path, transcript_path, transcript_dir, metrics_path, attributes_path) = sys.argv[1:]

def lines(where):
    try:
        with open(where, encoding="utf-8") as handle:
            return [line for line in handle.read().split("\n") if line.strip()]
    except OSError:
        return []

with open(path, encoding="utf-8") as handle:
    data = json.load(handle)
with open(diagnostics_path, "r", encoding="utf-8", errors="replace") as handle:
    diagnostics = handle.read()

data["sphinx_after"] = {"exit": int(sphinx_exit), "diagnostics": diagnostics}
before = data.get("sphinx_before") or {}
before_half = "exit %s, %d warn" % (
    before.get("exit"),
    len([line for line in (before.get("diagnostics") or "").split("\n") if line.strip()]),
)
# Both halves, in one string that still says both after crayon 120-character collapse. The
# new/resolved bookkeeping is deliberately NOT restated here: `score.py` `[sphinx]` line is
# the one place it is computed, and a second computation over un-normalised text would drift.
data["sphinx"] = "before %s - after %s" % (before_half, after_half)

origins = lines(origins_path)
data["baseline"]["origins"] = origins
data["baseline"]["origins_sha256"] = baseline_sha
data["context"] = {"origins": origins, "origins_sha256": context_sha}

# The two-step rule: the PATH, and a null sha the author fills from OUTSIDE the session.
data["transcript"] = {
    "path": transcript_path or None,
    "sha256": None,
    "searched": transcript_dir,
}

metrics = {}
for entry in lines(metrics_path):
    key, _, value = entry.partition("=")
    metrics[key] = value
data["metrics"] = metrics

attribution = []
for entry in lines(attributes_path):
    item, _, account = entry.partition("=")
    attribution.append({"item": item, "account": account})
data["sphinx_attribution"] = attribution

temporary = path + ".tmp"
with open(temporary, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
os.replace(temporary, path)
' "$RUN_PATH" "$SPHINX_EXIT" "$SPHINX_DIAGNOSTICS" "$after_half" \
  "$baseline_sha" "$context_sha" "$ORIGINS_FILE" \
  "$TRANSCRIPT_PATH" "$TRANSCRIPT_DIR" "$LIST_DIR/metrics.txt" "$LIST_DIR/attributes.txt" ||
        refuse "could not complete $RUN_PATH; it is unchanged and this leg is not recorded"

    printf 'runmeta: completed %s (after %s)\n' "$RUN_PATH" "$after_half"
    printf 'runmeta: transcript.sha256 is null by design — fill it from OUTSIDE this session\n'
    return 0
}

# --- routing -----------------------------------------------------------------------------------

if [ "$#" -eq 0 ]; then
    usage
    exit 2
fi

SUBCOMMAND="$1"
shift
case "$SUBCOMMAND" in
    begin) do_begin "$@" ;;
    end)   do_end "$@" ;;
    *)
        printf 'runmeta: unknown subcommand: %s\n' "$SUBCOMMAND" >&2
        usage
        exit 2
        ;;
esac
