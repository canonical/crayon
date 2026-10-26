#!/usr/bin/env bash
# states.sh: record what the real tool prints in each state lane B replays.
#
# Usage: bash validation/evals/fixtures/states.sh OUT.jsonl   (from the repository root)
#
# Lane B shows a model a history of `crayon` calls and asks for the next action.
# That history must be what the tool really prints, byte for byte, so it is
# recorded here and never typed by hand. Each scenario builds one state in a
# hermetic temp repo from tests/lib.sh (the one definition site for that
# fixture), copies in the toyq project, drives the real verbs, and appends one
# JSON line per recorded command:
#
#   {"state": ..., "label": ..., "cmd": "crayon ...", "exit": N, "output": "..."}
#
# `cmd` is the command as an agent types it (`crayon ...`). `output` is stdout and
# stderr together, as a shell tool shows them. `validation/evals/record_states.py`
# folds these lines into cases/decision/states.json, and tests/test_evals.py
# re-records and compares, so a change in the tool's output turns the gate red
# rather than leaving lane B replaying stale bytes.
#
# With SNAPDIR set, `snap NAME` also copies the whole temp repo (skills installed,
# history and all) to $SNAPDIR/NAME: the real tree a lane B episode runs its
# read-only commands in, so what a model sees when it looks is what the recorded
# outputs describe.

set -u

OUT="${1:?usage: states.sh OUT.jsonl}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
: >"$OUT"
export CRAYON="$ROOT/crayon.py"
# shellcheck source=../../../tests/lib.sh
source "$ROOT/tests/lib.sh"

UNIT=cfg
TARGET=reference/config.md
PAGE="docs/$TARGET"

# rec STATE LABEL ARGS... : run `crayon ARGS...`, record it as typed.
rec() {
    local state="$1" label="$2" out rc
    shift 2
    out=$("$CRAYON" "$@" 2>&1)
    rc=$?
    python3 -c '
import json, shlex, sys
state, label, rc, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
cmd = " ".join(["crayon"] + [shlex.quote(arg) for arg in sys.argv[5:]])
print(json.dumps({"state": state, "label": label, "cmd": cmd, "exit": rc, "output": out}))
' "$state" "$label" "$rc" "$out" "$@" >>"$OUT"
}

# rec_unit STATE UNIT : the unit's plan and ledger, as a model reading the repo sees them.
rec_unit() {
    rec_file "$1" ".crayon/units/$2/unit.md"
    rec_file "$1" ".crayon/units/$2/ledger.jsonl"
}

# rec_file STATE PATH : record a file's bytes for the case's virtual tree.
rec_file() {
    python3 -c '
import json, sys
print(json.dumps({"state": sys.argv[1], "label": "file:" + sys.argv[2], "cmd": None,
                  "exit": 0, "output": open(sys.argv[2], encoding="utf-8").read()}))
' "$1" "$2" >>"$OUT"
}

# rec_in STATE LABEL BODY ARGS... : run `crayon ARGS...` with BODY (a printf %b
# format) on stdin, and record it as an agent types it: `printf '%b' BODY | crayon ...`.
rec_in() {
    local state="$1" label="$2" body="$3" out rc
    shift 3
    out=$(printf '%b' "$body" | "$CRAYON" "$@" 2>&1)
    rc=$?
    python3 -c '
import json, shlex, sys
state, label, body, rc, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
cmd = "printf %s %s | " % (shlex.quote("%b"), shlex.quote(body))
cmd += " ".join(["crayon"] + [shlex.quote(arg) for arg in sys.argv[6:]])
print(json.dumps({"state": state, "label": label, "cmd": cmd, "exit": rc, "output": out}))
' "$state" "$label" "$body" "$rc" "$out" "$@" >>"$OUT"
}

# snap NAME : keep this moment of the repo as lane B's sandbox NAME.
snap() {
    [ -n "${SNAPDIR:-}" ] || return 0
    rm -rf "${SNAPDIR:?}/$1"
    cp -a . "$SNAPDIR/$1"
}

# The three onboarding artefacts, as crayon-onboard would stage them for toyq after
# walking README.md, docs/index.md and src/toyq: what they say is true of the project.
DOC_STYLE='# Doc style\n\nFrom README.md, the only prose so far.\n\n- Impersonal, present tense, short sentences.\n- Commands in fenced bash blocks, one command per line.\n- Settings, files and commands named in backticks: `toyq.toml`, `toyq run`.\n'
GLOSSARY='# Glossary\n\n- **job**: one queued shell command.\n- **attempt**: one run of a job; `toyq status` counts them.\n- **retry**: a re-run of a failed job, up to `max_retries` times.\n- **backoff**: the wait between attempts, `retry_backoff_seconds`.\n'
STRUCTURE='# Structure\n\n## 1. Documentation topology\n\n- docs/index.md is the only page: a one-line landing page whose toctree is empty.\n- README.md carries install and use, the only task prose.\n\n## 2. Diataxis coverage and balance\n\n- No tutorial, how-to, reference or explanation page yet.\n\n## 3. Coverage gaps\n\n- [CODE↔DOCS GAP] Config keys in src/toyq/config.py (max_retries, retry_backoff_seconds, job_timeout_seconds, log_level, db_path) and their TOYQ_* variables have no reference page.\n- [CODE↔DOCS GAP] CLI commands in src/toyq/cli.py (init, add, run, status, and init --force-dir) are named only in README.md.\n\n## 4. Risks\n\n- README.md points to a configuration reference that does not exist.\n\n## 5. Prioritized improvements\n\n- [CODE↔DOCS GAP] Add a configuration reference under docs/reference/.\n- [CODE↔DOCS GAP] Add a commands reference, and list both in the toctree.\n'

# stage_context NAME BODY : stage one context artefact through the tool.
stage_context() {
    # shellcheck disable=SC2059 # the bodies are printf formats on purpose
    printf "$2" | "$CRAYON" context stage "$1" --body-file - >/dev/null 2>&1 ||
        { echo "setup failed: context stage $1" >&2; exit 1; }
}

# base_bare [PROJECT] : a fixture project (toyq unless named) with the skills
# installed, and no context yet.
base_bare() {
    local project="${1:-toyq}"
    setup_repo
    python3 - "$ROOT" "$project" <<'PY' || { echo "setup failed: copy $project and the skills" >&2; exit 1; }
import os
from pathlib import Path
import shutil
import subprocess
import sys

source = Path(sys.argv[1])
tracked = subprocess.check_output([
    "git", "-C", str(source), "ls-files", "-z", "--",
    "validation/evals/fixtures/" + sys.argv[2], "skills/crayon-*",
])
for name in tracked.split(b"\0"):
    if not name:
        continue
    path = Path(os.fsdecode(name))
    target = (Path(".agents") / path if path.parts[0] == "skills"
              else Path(*path.parts[4:]))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / path, target)
PY
    printf '.crayon/staging/\n' >.gitignore
    git add -A || { echo "setup failed: git add the $project project" >&2; exit 1; }
    git commit -q -m "$project project, crayon skills installed" ||
        { echo "setup failed: commit the $project project" >&2; exit 1; }
}

# base : base_bare plus a recorded context, so a unit session grounds without
# being routed to onboarding first.
base() {
    base_bare
    stage_context doc-style.md "$DOC_STYLE"
    stage_context glossary.md "$GLOSSARY"
    stage_context structure.md "$STRUCTURE"
    "$CRAYON" context record --note "toyq context" >/dev/null 2>&1 ||
        { echo "setup failed: context record" >&2; exit 1; }
}

# declare_cfg [NOTES] : the reference unit cfg, declared. NOTES, when given, are
# the author's intake notes, passed as --notes; without them the declaration is
# the one every earlier state recorded.
declare_cfg() {
    local notes=()
    [ $# -gt 0 ] && notes=(--notes "$1")
    printf '%s\n' \
        '# Plan' '' \
        'A reference page for every toyq setting: its key in toyq.toml, its TOYQ_*' \
        'environment override, its type and its default, and the precedence rule' \
        '(defaults, then toyq.toml, then the environment).' '' \
        '- One table of settings.' \
        '- Precedence, stated once.' \
        '- The validation rule for max_retries.' |
        "$CRAYON" unit new "$UNIT" --intent reference \
            --audience "operators configuring toyq on a server" \
            --title "Configuration reference" --target "$TARGET" \
            --source src/toyq/config.py ${notes[@]+"${notes[@]}"} --body-file - >/dev/null 2>&1 ||
        { echo "setup failed: unit new $UNIT" >&2; exit 1; }
}

stage_page() {
    stage_draft "$UNIT" "$TARGET" "$1"
}

PAGE_V1='# Configuration reference\n\ntoyq reads its settings from defaults, then `toyq.toml`, then `TOYQ_*` environment variables; the last one wins.\n\n| Setting | Variable | Type | Default |\n|---|---|---|---|\n| `db_path` | `TOYQ_DB_PATH` | string | `toyq.sqlite` |\n| `max_retries` | `TOYQ_MAX_RETRIES` | integer | `3` |\n| `retry_backoff_seconds` | `TOYQ_RETRY_BACKOFF` | float | `5.0` |\n| `job_timeout_seconds` | `TOYQ_JOB_TIMEOUT` | integer | `600` |\n| `log_level` | `TOYQ_LOG_LEVEL` | string | `info` |\n\n`max_retries` must be 0 or more.\n'
PAGE_V2='# Configuration reference\n\nSettings come from defaults, then `toyq.toml`, then `TOYQ_*` variables.\n'

drafted() {
    base
    declare_cfg
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $UNIT" >&2; exit 1; }
    stage_page "$PAGE_V1"
    "$CRAYON" draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" >/dev/null 2>&1 ||
        { echo "setup failed: draft $UNIT" >&2; exit 1; }
}

scenario_declared() {
    base
    rec tool version_json version --json
    declare_cfg
    rec declared show_json show "$UNIT" --json
    rec declared show show "$UNIT"
    rec_unit declared "$UNIT"
    snap declared
    stage_page "$PAGE_V1"
    rec declared draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
    rec declared signoff_json signoff "$UNIT" --json
}

scenario_signed() {
    base
    declare_cfg
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $UNIT" >&2; exit 1; }
    rec signed show_json show "$UNIT" --json
    rec signed show show "$UNIT"
    rec_unit signed "$UNIT"
    # The declared source, so a history that grounds a draft replays its real bytes.
    rec_file signed src/toyq/config.py
    snap signed
    stage_page "$PAGE_V1"
    rec signed draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
}

scenario_drafted() {
    drafted
    rec drafted show_json show "$UNIT" --json
    rec drafted show show "$UNIT"
    rec drafted summary summary "$UNIT"
    rec_unit drafted "$UNIT"
    rec_file drafted "$PAGE"
    snap drafted
    stage_page "$PAGE_V2"
    rec drafted redraft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
    rec drafted fix_json review "$UNIT" --verdict fix --note "Explain what happens when max_retries is exceeded." --json
    rec drafted steering_show_json show "$UNIT" --json
    snap fixed
    rec drafted steering_accept_json review "$UNIT" --verdict accept --note "Looks right." --json
}

scenario_accepted() {
    drafted
    "$CRAYON" review "$UNIT" --verdict accept --note "Accurate and complete." >/dev/null 2>&1 ||
        { echo "setup failed: accept $UNIT" >&2; exit 1; }
    rec accepted show_json show "$UNIT" --json
    rec_unit accepted "$UNIT"
    rec_file accepted "$PAGE"
    snap accepted
    # Bare, as an author's "accept it" is recorded: no note the author did not give.
    rec accepted accept_again_json review "$UNIT" --verdict accept --json
}

# An accept on a page the docs tree already links, with nothing left open: the
# closing turn reads the handover from `show --json` after the accept.
scenario_closing_linked() {
    drafted
    python3 -c '
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
if ":maxdepth: 1\n" not in text:
    sys.exit("no toctree to list the page in")
text = text.replace(":maxdepth: 1\n", ":maxdepth: 1\n\nreference/config\n", 1)
open(path, "w", encoding="utf-8").write(text)
' docs/index.md || { echo "setup failed: list the page in the toctree" >&2; exit 1; }
    git add docs/index.md || { echo "setup failed: git add docs/index.md" >&2; exit 1; }
    git commit -q -m "list the configuration reference in the toctree" ||
        { echo "setup failed: commit the toctree entry" >&2; exit 1; }
    rec closing_linked show_json show "$UNIT" --json
    rec closing_linked summary summary "$UNIT"
    rec closing_linked accept review "$UNIT" --verdict accept
    rec closing_linked handover_json show "$UNIT" --json
    snap closing_linked
}

# An accept on a page listed only by a relative toctree entry: docs/index.md lists
# reference/index, and docs/reference/index.md lists the page as plain `config`.
# Neither `reference/config` nor `config.md` appears anywhere, yet the page is linked.
scenario_closing_nested() {
    drafted
    python3 -c '
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
if ":maxdepth: 1\n" not in text:
    sys.exit("no toctree to list the section in")
text = text.replace(":maxdepth: 1\n", ":maxdepth: 1\n\nreference/index\n", 1)
open(path, "w", encoding="utf-8").write(text)
' docs/index.md || { echo "setup failed: list the section in the toctree" >&2; exit 1; }
    printf '# Reference\n\n```{toctree}\n:maxdepth: 1\n\nconfig\n```\n' >docs/reference/index.md
    git add docs/index.md docs/reference/index.md ||
        { echo "setup failed: git add the toctree entries" >&2; exit 1; }
    git commit -q -m "list the reference section and the configuration page in it" ||
        { echo "setup failed: commit the toctree entries" >&2; exit 1; }
    rec closing_nested show_json show "$UNIT" --json
    rec closing_nested summary summary "$UNIT"
    rec closing_nested accept review "$UNIT" --verdict accept
    rec closing_nested handover_json show "$UNIT" --json
    snap closing_nested
}

# An accept carrying the reviewer's own words, on a page no toctree lists yet:
# nothing is open on the record, so what is open comes from the history.
scenario_closing() {
    drafted
    rec closing show_json show "$UNIT" --json
    rec closing summary summary "$UNIT"
    rec closing accept review "$UNIT" --verdict accept \
        --note "The max_retries default really is 3, so leave that line."
    rec closing handover_json show "$UNIT" --json
    snap closing
}

# The page shows plain `toyq init`: the deviation the walk recorded (it needed
# --force-dir) is genuinely absent from it, so the closure's question is real.
INSTALL_PAGE='# Install toyq\n\nInstall toyq from the checkout:\n\n```console\n$ python3 -m pip install /srv/toyq\n```\n\nCreate the configuration:\n\n```console\n$ toyq init\n```\n\nQueue and run a first job:\n\n```console\n$ toyq add "echo hi" && toyq run --once\n```\n'

# walked_install : the one definition of the walked how-to. The unit `install`,
# declared and signed off, walked with one passing step, one deviated step
# (`init`) and one skipped step (`first-job`), and drafted. Both
# scenario_closing_walk and scenario_walk_drafted start here.
walked_install() {
    base
    declare_install
    printf '%s' '[{"id":"install","text":"Install toyq from the checkout: python3 -m pip install /srv/toyq","mode":"agent","stateful":false},{"id":"init","text":"Create the configuration: toyq init","mode":"agent","stateful":false},{"id":"first-job","text":"Queue and run a job: toyq add \"echo hi\" && toyq run --once","mode":"ta","stateful":false}]' |
        "$CRAYON" plan-steps install --steps-file - >/dev/null 2>&1 ||
        { echo "setup failed: plan-steps install" >&2; exit 1; }
    local seq
    seq=$(last_plan_seq install)
    [ -n "$seq" ] || { echo "setup failed: read the step plan's seq" >&2; exit 1; }
    record_step install install "$seq" pass "Successfully installed toyq\n" >/dev/null 2>&1 ||
        { echo "setup failed: step install" >&2; exit 1; }
    record_step install init "$seq" deviated "Created toyq.toml\n" agent \
        "toyq init needed --force-dir on a fresh checkout" >/dev/null 2>&1 ||
        { echo "setup failed: step init" >&2; exit 1; }
    skip_step install first-job "$seq" "no network in CI" >/dev/null 2>&1 ||
        { echo "setup failed: step first-job" >&2; exit 1; }
    stage_draft install how-to/install.md "$INSTALL_PAGE"
    "$CRAYON" draft install "$(draft_path install how-to/install.md)" >/dev/null 2>&1 ||
        { echo "setup failed: draft install" >&2; exit 1; }
}

# A walked how-to accepted with one deviated step, one skipped step and one
# request the reviewer judged without a redraft: four things open at handover
# once the reader's arrival is counted.
scenario_closing_walk() {
    local request
    walked_install
    "$CRAYON" review install --verdict fix \
        --note "Say which Python version toyq needs." >/dev/null 2>&1 ||
        { echo "setup failed: fix install" >&2; exit 1; }
    request=$(tail -n 1 .crayon/units/install/ledger.jsonl | json_field seq)
    [ -n "$request" ] || { echo "setup failed: read the fix request's seq" >&2; exit 1; }
    rec closing_walk show_json show install --json
    rec closing_walk accept review install --verdict accept --resolves "$request"
    rec closing_walk handover_json show install --json
    rec closing_walk summary_md summary install --md
    snap closing_walk
}

# A walked how-to drafted and not yet reviewed: its routed `next` is `review`,
# and both the deviated and the skipped step are in `handover.steps` before any
# accept. walk_accepted is the same unit after a bare accept, with no request
# pending, so a closure on it has only the steps and the reader's arrival open.
scenario_walk_drafted() {
    walked_install
    rec walk_drafted show_json show install --json
    rec walk_drafted summary summary install
    snap walk_drafted
    rec walk_accepted accept review install --verdict accept
    rec walk_accepted handover_json show install --json
    snap walk_accepted
}

# The author's intake notes for the reported states: where the reader arrives
# from, and what the page leaves out.
REPORTED_NOTES='They have just installed toyq and opened toyq.toml.
Leave out db_path; storage gets its own page.'

# The writer's context report, with one gap recorded, and its twin with none.
REPORT_GAPS='{"origins": ["src/toyq/config.py"], "gaps": ["No source lists the accepted log_level values; the page gives only the default."]}'
REPORT_CLEAN='{"origins": ["src/toyq/config.py"], "gaps": [], "gaps_note": "Every setting on the page is read from src/toyq/config.py."}'

# The first page less the one row REPORTED_NOTES leaves out, so a writer's own
# draft can honour its notes. Derived, not typed: PAGE_V1 is its one definition.
PAGE_NOTED=${PAGE_V1/'| `db_path` | `TOYQ_DB_PATH` | string | `toyq.sqlite` |\n'/}

# reported_unit STATE REPORT [PAGE] : a reference unit drafted by a named model
# with intake notes and a context report, so review can weigh who drafted it and
# write can voice its gaps. reported keeps the row the notes leave out, which
# review is to find; reported_noted and reported_clean carry PAGE_NOTED, the
# writer's own draft as its notes ask, with one gap reported and with none.
reported_unit() {
    local state="$1" report="$2" page="${3:-$PAGE_V1}" staged=".crayon/staging/$UNIT/report.json"
    base
    declare_cfg "$REPORTED_NOTES"
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $UNIT" >&2; exit 1; }
    rec "$state" signed_show_json show "$UNIT" --json
    rec_file "$state" ".crayon/units/$UNIT/unit.md"
    stage_page "$page"
    printf '%s\n' "$report" >"$staged"
    rec_file "$state" "$staged"
    rec "$state" draft draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" \
        --model example/drafting-model-1 --model-origin session --report "$staged"
    rec_file "$state" "$PAGE"
    rec "$state" show_json show "$UNIT" --json
    rec "$state" summary summary "$UNIT"
    snap "$state"
}

scenario_reported() {
    reported_unit reported "$REPORT_GAPS"
}

# A writer's own draft with no gap: it honours the notes, so its report has nothing to say.
scenario_reported_clean() {
    reported_unit reported_clean "$REPORT_CLEAN" "$PAGE_NOTED"
}

scenario_reported_noted() {
    [ "$PAGE_NOTED" != "$PAGE_V1" ] ||
        { echo "setup failed: PAGE_NOTED left the db_path row in" >&2; exit 1; }
    reported_unit reported_noted "$REPORT_GAPS" "$PAGE_NOTED"
}

scenario_edited() {
    drafted
    printf '\nDefaults apply when a setting appears nowhere else.\n' >>"$PAGE"
    rec edited show_json show "$UNIT" --json
    rec_unit edited "$UNIT"
    rec_file edited "$PAGE"
    snap edited
    rec edited show_diff show "$UNIT" --diff
}

scenario_missing() {
    drafted
    rm "$PAGE"
    rec missing show_json show "$UNIT" --json
    rec_unit missing "$UNIT"
    snap missing
    rec missing accept_json review "$UNIT" --verdict accept --json
}

scenario_target_exists() {
    base
    declare_cfg
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $UNIT" >&2; exit 1; }
    mkdir -p "$(dirname "$PAGE")"
    printf '# Configuration\n\nHand-written notes.\n' >"$PAGE"
    rec target_exists show_json show "$UNIT" --json
    stage_page "$PAGE_V1"
    snap target_exists
    rec target_exists draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
}

scenario_stale() {
    base
    declare_cfg
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $UNIT" >&2; exit 1; }
    "$CRAYON" unit edit "$UNIT" --audience "operators and developers configuring toyq" \
        >/dev/null 2>&1 || { echo "setup failed: unit edit $UNIT" >&2; exit 1; }
    rec stale show_json show "$UNIT" --json
    rec_unit stale "$UNIT"
    snap stale
    stage_page "$PAGE_V1"
    rec stale draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
}

scenario_retired() {
    base
    declare_cfg
    "$CRAYON" unit retire "$UNIT" --note "Superseded by the settings guide." >/dev/null 2>&1 ||
        { echo "setup failed: unit retire $UNIT" >&2; exit 1; }
    rec retired show_json show "$UNIT" --json
    rec_unit retired "$UNIT"
    snap retired
}

# declare_install : the how-to unit `install`, declared and signed off.
declare_install() {
    printf '%s\n' '# Plan' '' 'Install toyq and queue a first job.' |
        "$CRAYON" unit new install --intent how-to \
            --audience "operators installing toyq for the first time" \
            --title "Install toyq" --target how-to/install.md \
            --source README.md --body-file - >/dev/null 2>&1 ||
        { echo "setup failed: unit new install" >&2; exit 1; }
    "$CRAYON" signoff install >/dev/null 2>&1 ||
        { echo "setup failed: signoff install" >&2; exit 1; }
}

scenario_walk() {
    base
    declare_install
    printf '%s' '[{"id":"install","text":"Install toyq from the checkout: python3 -m pip install /srv/toyq","mode":"agent","stateful":true},{"id":"init","text":"Create the configuration: toyq init","mode":"agent","stateful":true},{"id":"first-job","text":"Queue and run a job: toyq add \"echo hi\" && toyq run --once","mode":"agent","stateful":true}]' |
        "$CRAYON" plan-steps install --steps-file - >/dev/null 2>&1 ||
        { echo "setup failed: plan-steps install" >&2; exit 1; }
    rec walk show_json show install --json
    rec walk show show install
    rec_unit walk install
    snap walk
}

scenario_crashed() {
    base
    declare_cfg
    # The crash IS the state: this signoff fails on purpose, so its exit is not checked.
    CRAYON_CRASH_AT=append "$CRAYON" signoff "$UNIT" >/dev/null 2>&1
    rec crashed show_json show "$UNIT" --json
    rec_unit crashed "$UNIT"
    snap crashed
    stage_page "$PAGE_V1"
    rec crashed draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
    rec crashed resume_dry resume "$UNIT" --dry-run
}

# A committed ledger line rewritten in git history: the record no longer
# matches HEAD (ledger_diverged).
scenario_diverged() {
    drafted
    local ledger=".crayon/units/$UNIT/ledger.jsonl" saved
    saved=$(mktemp)
    cp "$ledger" "$saved"
    python3 -c '
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines(True)
lines[1] = lines[1].replace("reference", "referenc3", 1)
open(path, "w", encoding="utf-8").write("".join(lines))
' "$ledger"
    git commit -q -a --amend -m "crayon: drafted $UNIT" ||
        { echo "setup failed: amend the drafted commit" >&2; exit 1; }
    cp "$saved" "$ledger"
    rm -f "$saved"
    rec diverged show_json show "$UNIT" --json
    snap diverged
}

# The last event taken out of the commit and left behind uncommitted, with no
# manifest to resume from (recovery_unsupported, detail no_material).
scenario_no_material() {
    drafted
    local ledger=".crayon/units/$UNIT/ledger.jsonl" saved
    saved=$(mktemp)
    cp "$ledger" "$saved"
    python3 -c '
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines(True)
open(path, "w", encoding="utf-8").write("".join(lines[:-1]))
' "$ledger"
    git commit -q -a --amend -m "crayon: drafted $UNIT" ||
        { echo "setup failed: amend the drafted commit" >&2; exit 1; }
    cp "$saved" "$ledger"
    rm -f "$saved"
    rec no_material show_json show "$UNIT" --json
    rec no_material resume_json resume "$UNIT" --json
    snap no_material
}

# The docs root replaced by a link to a directory outside the repository
# (bad_write_path). The sandbox rebuilds the same layout from the drafted
# snapshot (sandbox.TRANSFORMS), so no link target is baked into a snapshot.
scenario_docs_outside() {
    drafted
    mv docs "$TEST_DIR-outside"
    ln -s "$TEST_DIR-outside" docs
    rec docs_outside show_json show "$UNIT" --json
    rm -rf "$TEST_DIR-outside"
}

scenario_context() {
    base_bare
    rec context_empty show_json context show --json
    snap context_empty
    # What an onboarding walk reads, and the three stage calls it makes, as recorded
    # steps: a history that says it walked and staged shows it doing so.
    rec_file context_recorded README.md
    rec_file context_recorded docs/index.md
    rec_file context_recorded src/toyq/config.py
    rec_file context_recorded src/toyq/cli.py
    rec_in context_recorded stage_doc_style "$DOC_STYLE" context stage doc-style.md --body-file -
    rec context_staged show_json context show --json
    snap context_staged
    rec_in context_recorded stage_glossary "$GLOSSARY" context stage glossary.md --body-file -
    rec_in context_recorded stage_structure "$STRUCTURE" context stage structure.md --body-file -
    rec context_recorded record context record --note "toyq context"
    rec context_recorded show_json context show --json
    snap context_recorded
    rec_file context_recorded .crayon/context/doc-style.md
    rec_file context_recorded .crayon/context/glossary.md
    rec_file context_recorded .crayon/context/structure.md
}

# scenario_triage : a change to toyq lands after the context was recorded, and the
# author asks whether it needs documentation. The repository has not turned triage
# collection on, so `triage record` writes nothing.
scenario_triage() {
    base
    python3 - <<'PY' || { echo "setup failed: add max_queue_size" >&2; exit 1; }
from pathlib import Path
path = Path("src/toyq/config.py")
text = path.read_text(encoding="utf-8")
for old, new in (
    ('    "log_level": "info",\n}', '    "log_level": "info",\n    "max_queue_size": 1000,\n}'),
    ('    "log_level": "TOYQ_LOG_LEVEL",\n}',
     '    "log_level": "TOYQ_LOG_LEVEL",\n    "max_queue_size": "TOYQ_MAX_QUEUE_SIZE",\n}'),
    ("    log_level: str\n", "    log_level: str\n    max_queue_size: int\n"),
):
    assert text.count(old) == 1, old
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
PY
    git commit -q -am "Add max_queue_size: refuse new jobs past this many queued" ||
        { echo "setup failed: commit max_queue_size" >&2; exit 1; }
    rec triage_change show_json context show --json
    snap triage_change
    rec triage_change record_off triage record --base HEAD~1 --head HEAD --needs-docs yes \
        --page reference/config.md --type reference --unit-id cfg \
        --note 'max_queue_size is a new setting and no page documents the settings'
}

# --- the second project: tidewatch ------------------------------------------
#
# A larger, Sphinx-shaped project (validation/evals/fixtures/tidewatch), so the
# critical rules are also checked away from toyq. Its states carry the `tw_`
# prefix and serve one critical case per rule (cases/decision/tidewatch.json).

TW_UNIT=settings
TW_TARGET=reference/configuration.md
TW_PAGE="docs/$TW_TARGET"
TW_DOC_STYLE='# Doc style\n\nSecond person, present tense. Commands go in console blocks.\n'
TW_GLOSSARY='# Glossary\n\n- **watch**: a directory tidewatch polls, with its command.\n- **hook**: the command a watch runs when something in it changes.\n'
TW_STRUCTURE='# Structure\n\n- docs/tutorial/: learning by doing.\n- docs/how-to/: task guides.\n- docs/reference/: commands, hooks, events, variables.\n- docs/explanation/: background.\n\n## Coverage gaps\n\n- The settings in src/tidewatch/config.py have no reference page; docs/reference/environment.md lists only their variables.\n'
TW_PAGE_V1='# Configuration reference\n\ntidewatch reads its settings from defaults, then `tidewatch.toml`, then `TIDEWATCH_*` environment variables; the last one wins.\n\n| Setting | Variable | Type | Default |\n|---|---|---|---|\n| `poll_interval_seconds` | `TIDEWATCH_POLL_INTERVAL` | float | `2.0` |\n| `debounce_ms` | `TIDEWATCH_DEBOUNCE_MS` | integer | `250` |\n| `max_hooks_in_flight` | `TIDEWATCH_MAX_HOOKS` | integer | `4` |\n| `hook_timeout_seconds` | `TIDEWATCH_HOOK_TIMEOUT` | integer | `300` |\n| `follow_symlinks` | `TIDEWATCH_FOLLOW_SYMLINKS` | boolean | `false` |\n| `log_format` | `TIDEWATCH_LOG_FORMAT` | string | `text` |\n| `state_dir` | `TIDEWATCH_STATE_DIR` | path | `~/.local/state/tidewatch` |\n\n`tidewatch check` reports every setting that breaks a rule: `poll_interval_seconds` must be more than 0, `debounce_ms` 0 or more, `max_hooks_in_flight` 1 or more, and `log_format` one of `text` or `json`.\n'
TW_HOWTO_PAGE='# Rebuild the docs when they change\n\nInstall tidewatch from the checkout:\n\n```console\n$ python3 -m pip install /srv/tidewatch\n```\n\nWatch the docs, ignoring the build output:\n\n```console\n$ tidewatch add docs --on-change "python3 -m sphinx docs docs/_build/html" --ignore "*/_build/*"\n```\n\nRun one poll to check it:\n\n```console\n$ tidewatch run --once\n```\n'

# tw_base : tidewatch with the skills installed and its context recorded.
tw_base() {
    base_bare tidewatch
    stage_context doc-style.md "$TW_DOC_STYLE"
    stage_context glossary.md "$TW_GLOSSARY"
    stage_context structure.md "$TW_STRUCTURE"
    "$CRAYON" context record --note "tidewatch context" >/dev/null 2>&1 ||
        { echo "setup failed: context record (tidewatch)" >&2; exit 1; }
}

# tw_declare : the reference unit `settings`, declared.
tw_declare() {
    printf '%s\n' \
        '# Plan' '' \
        'A reference page for every tidewatch setting: its key in tidewatch.toml, its' \
        'TIDEWATCH_* variable, its type, its default and the rule tidewatch check' \
        'enforces, and the precedence (defaults, then tidewatch.toml, then the' \
        'environment).' '' \
        '- One table of settings.' \
        '- Precedence, stated once.' \
        '- The rules, as tidewatch check reports them.' |
        "$CRAYON" unit new "$TW_UNIT" --intent reference \
            --audience "people running tidewatch on a workstation or a server" \
            --title "Configuration reference" --target "$TW_TARGET" \
            --source src/tidewatch/config.py --body-file - >/dev/null 2>&1 ||
        { echo "setup failed: unit new $TW_UNIT" >&2; exit 1; }
}

tw_drafted() {
    tw_base
    tw_declare
    "$CRAYON" signoff "$TW_UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $TW_UNIT" >&2; exit 1; }
    stage_draft "$TW_UNIT" "$TW_TARGET" "$TW_PAGE_V1"
    "$CRAYON" draft "$TW_UNIT" "$(draft_path "$TW_UNIT" "$TW_TARGET")" >/dev/null 2>&1 ||
        { echo "setup failed: draft $TW_UNIT" >&2; exit 1; }
}

# tw_declare_howto : the how-to unit `rebuild-docs`, declared and signed off.
tw_declare_howto() {
    printf '%s\n' '# Plan' '' 'Set up tidewatch to rebuild the docs whenever a page changes.' |
        "$CRAYON" unit new rebuild-docs --intent how-to \
            --audience "contributors editing the tidewatch docs" \
            --title "Rebuild the docs when they change" --target how-to/rebuild-docs.md \
            --source README.md --body-file - >/dev/null 2>&1 ||
        { echo "setup failed: unit new rebuild-docs" >&2; exit 1; }
    "$CRAYON" signoff rebuild-docs >/dev/null 2>&1 ||
        { echo "setup failed: signoff rebuild-docs" >&2; exit 1; }
}

# tw_steps STATEFUL : the step plan of `rebuild-docs`, every step stateful or none.
tw_steps() {
    printf '[{"id":"install","text":"Install tidewatch from the checkout: python3 -m pip install /srv/tidewatch","mode":"agent","stateful":%s},{"id":"watch","text":"Watch the docs: tidewatch add docs --on-change \\"python3 -m sphinx docs docs/_build/html\\"","mode":"agent","stateful":%s},{"id":"poll","text":"Run one poll: tidewatch run --once","mode":"ta","stateful":%s}]' \
        "$1" "$1" "$1" |
        "$CRAYON" plan-steps rebuild-docs --steps-file - >/dev/null 2>&1 ||
        { echo "setup failed: plan-steps rebuild-docs" >&2; exit 1; }
}

scenario_tw_context() {
    tw_base
    rec tw_context_recorded show_json context show --json
    snap tw_context_recorded
}

scenario_tw_declared() {
    tw_base
    tw_declare
    rec tw_declared show_json show "$TW_UNIT" --json
    rec tw_declared show show "$TW_UNIT"
    rec_unit tw_declared "$TW_UNIT"
    snap tw_declared
}

scenario_tw_signed() {
    tw_base
    tw_declare
    "$CRAYON" signoff "$TW_UNIT" >/dev/null 2>&1 || { echo "setup failed: signoff $TW_UNIT" >&2; exit 1; }
    rec tw_signed show_json show "$TW_UNIT" --json
    rec_unit tw_signed "$TW_UNIT"
    rec_file tw_signed src/tidewatch/config.py
    snap tw_signed
}

scenario_tw_drafted() {
    tw_drafted
    rec tw_drafted show_json show "$TW_UNIT" --json
    rec tw_drafted summary summary "$TW_UNIT"
    rec_unit tw_drafted "$TW_UNIT"
    rec_file tw_drafted "$TW_PAGE"
    snap tw_drafted
}

scenario_tw_accepted() {
    tw_drafted
    "$CRAYON" review "$TW_UNIT" --verdict accept --note "Matches what tidewatch check enforces." \
        >/dev/null 2>&1 || { echo "setup failed: accept $TW_UNIT" >&2; exit 1; }
    rec tw_accepted show_json show "$TW_UNIT" --json
    rec_unit tw_accepted "$TW_UNIT"
    snap tw_accepted
    rec tw_accepted accept_again_json review "$TW_UNIT" --verdict accept --json
}

scenario_tw_missing() {
    tw_drafted
    rm "$TW_PAGE"
    rec tw_missing show_json show "$TW_UNIT" --json
    snap tw_missing
    rec tw_missing accept_json review "$TW_UNIT" --verdict accept --json
}

scenario_tw_crashed() {
    tw_base
    tw_declare
    # The crash IS the state: this signoff fails on purpose, so its exit is not checked.
    CRAYON_CRASH_AT=append "$CRAYON" signoff "$TW_UNIT" >/dev/null 2>&1
    rec tw_crashed show_json show "$TW_UNIT" --json
    snap tw_crashed
}

scenario_tw_diverged() {
    tw_drafted
    local ledger=".crayon/units/$TW_UNIT/ledger.jsonl" saved
    saved=$(mktemp)
    cp "$ledger" "$saved"
    python3 -c '
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines(True)
lines[1] = lines[1].replace("reference", "referenc3", 1)
open(path, "w", encoding="utf-8").write("".join(lines))
' "$ledger"
    git commit -q -a --amend -m "crayon: drafted $TW_UNIT" ||
        { echo "setup failed: amend the drafted commit (tidewatch)" >&2; exit 1; }
    cp "$saved" "$ledger"
    rm -f "$saved"
    rec tw_diverged show_json show "$TW_UNIT" --json
    snap tw_diverged
}

scenario_tw_walk() {
    tw_base
    tw_declare_howto
    tw_steps true
    rec tw_walk show_json show rebuild-docs --json
    rec tw_walk show show rebuild-docs
    snap tw_walk
}

scenario_tw_walk_drafted() {
    local seq
    tw_base
    tw_declare_howto
    tw_steps false
    seq=$(last_plan_seq rebuild-docs)
    [ -n "$seq" ] || { echo "setup failed: read the step plan's seq (tidewatch)" >&2; exit 1; }
    record_step rebuild-docs install "$seq" pass "Successfully installed tidewatch-1.4.2\n" \
        >/dev/null 2>&1 || { echo "setup failed: step install (tidewatch)" >&2; exit 1; }
    record_step rebuild-docs watch "$seq" deviated "3f9c2a1b\n" agent \
        "the build output re-triggered the watch until --ignore '*/_build/*' was added" \
        >/dev/null 2>&1 || { echo "setup failed: step watch (tidewatch)" >&2; exit 1; }
    skip_step rebuild-docs poll "$seq" "Sphinx is not installed on this machine" >/dev/null 2>&1 ||
        { echo "setup failed: step poll (tidewatch)" >&2; exit 1; }
    stage_draft rebuild-docs how-to/rebuild-docs.md "$TW_HOWTO_PAGE"
    "$CRAYON" draft rebuild-docs "$(draft_path rebuild-docs how-to/rebuild-docs.md)" >/dev/null 2>&1 ||
        { echo "setup failed: draft rebuild-docs" >&2; exit 1; }
    rec tw_walk_drafted show_json show rebuild-docs --json
    rec tw_walk_drafted summary summary rebuild-docs
    snap tw_walk_drafted
}

# A setting lands in tidewatch after the context was recorded, and the author asks
# whether it needs documentation.
scenario_tw_triage() {
    tw_base
    python3 - <<'PY' || { echo "setup failed: add max_event_age_seconds" >&2; exit 1; }
from pathlib import Path
path = Path("src/tidewatch/config.py")
text = path.read_text(encoding="utf-8")
for old, new in (
    ('    "state_dir": "~/.local/state/tidewatch",\n}',
     '    "state_dir": "~/.local/state/tidewatch",\n    "max_event_age_seconds": 60,\n}'),
    ('    "state_dir": "TIDEWATCH_STATE_DIR",\n}',
     '    "state_dir": "TIDEWATCH_STATE_DIR",\n    "max_event_age_seconds": "TIDEWATCH_MAX_EVENT_AGE",\n}'),
    ("    state_dir: str\n", "    state_dir: str\n    max_event_age_seconds: int\n"),
):
    assert text.count(old) == 1, old
    text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
PY
    git commit -q -am "Add max_event_age_seconds: drop events older than this when a poll is late" ||
        { echo "setup failed: commit max_event_age_seconds" >&2; exit 1; }
    rec tw_triage_change show_json context show --json
    snap tw_triage_change
}

# A setup step that fails exits its scenario's subshell 1, the temp repo is still
# cleaned up, and the recorder stops: a broken fixture never freezes a wrong
# baseline. record_states.py runs this with check=True.
for scenario in declared signed drafted accepted closing_linked closing_nested closing closing_walk \
    walk_drafted reported reported_clean reported_noted edited missing target_exists stale retired walk crashed \
    diverged no_material docs_outside context triage tw_context tw_declared tw_signed tw_drafted \
    tw_accepted tw_missing tw_crashed tw_diverged tw_walk tw_walk_drafted tw_triage; do
    (trap cleanup EXIT; "scenario_$scenario"; exit 0) ||
        { echo "setup failed: scenario $scenario" >&2; exit 1; }
done
