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

# snap NAME : keep this moment of the repo as lane B's sandbox NAME.
snap() {
    [ -n "${SNAPDIR:-}" ] || return 0
    rm -rf "${SNAPDIR:?}/$1"
    cp -a . "$SNAPDIR/$1"
}

# The three onboarding artefacts, as crayon-onboard would stage them for toyq.
DOC_STYLE='# Doc style\n\nImpersonal, present tense. Short sentences.\n'
GLOSSARY='# Glossary\n\n- **job**: one queued shell command.\n- **retry**: a re-run of a failed job.\n'
STRUCTURE='# Structure\n\n- docs/reference/: settings and commands.\n- docs/how-to/: task guides.\n'

# stage_context NAME BODY : stage one context artefact through the tool.
stage_context() {
    # shellcheck disable=SC2059 # the bodies are printf formats on purpose
    printf "$2" | "$CRAYON" context stage "$1" --body-file - >/dev/null 2>&1
}

# base_bare : the toyq project with the skills installed, and no context yet.
base_bare() {
    setup_repo
    python3 - "$ROOT" <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys

source = Path(sys.argv[1])
tracked = subprocess.check_output([
    "git", "-C", str(source), "ls-files", "-z", "--",
    "validation/evals/fixtures/toyq", "skills/crayon-*",
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
    git add -A
    git commit -q -m "toyq project, crayon skills installed"
}

# base : base_bare plus a recorded context, so a unit session grounds without
# being routed to onboarding first.
base() {
    base_bare
    stage_context doc-style.md "$DOC_STYLE"
    stage_context glossary.md "$GLOSSARY"
    stage_context structure.md "$STRUCTURE"
    "$CRAYON" context record --note "toyq context" >/dev/null 2>&1
}

declare_cfg() {
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
            --source src/toyq/config.py --body-file - >/dev/null 2>&1
}

stage_page() {
    stage_draft "$UNIT" "$TARGET" "$1"
}

PAGE_V1='# Configuration reference\n\ntoyq reads its settings from defaults, then `toyq.toml`, then `TOYQ_*` environment variables; the last one wins.\n\n| Setting | Variable | Type | Default |\n|---|---|---|---|\n| `db_path` | `TOYQ_DB_PATH` | string | `toyq.sqlite` |\n| `max_retries` | `TOYQ_MAX_RETRIES` | integer | `3` |\n| `retry_backoff_seconds` | `TOYQ_RETRY_BACKOFF` | float | `5.0` |\n| `job_timeout_seconds` | `TOYQ_JOB_TIMEOUT` | integer | `600` |\n| `log_level` | `TOYQ_LOG_LEVEL` | string | `info` |\n\n`max_retries` must be 0 or more.\n'
PAGE_V2='# Configuration reference\n\nSettings come from defaults, then `toyq.toml`, then `TOYQ_*` variables.\n'

drafted() {
    base
    declare_cfg
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1
    stage_page "$PAGE_V1"
    "$CRAYON" draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" >/dev/null 2>&1
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
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1
    rec signed show_json show "$UNIT" --json
    rec signed show show "$UNIT"
    rec_unit signed "$UNIT"
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
    "$CRAYON" review "$UNIT" --verdict accept --note "Accurate and complete." >/dev/null 2>&1
    rec accepted show_json show "$UNIT" --json
    rec_unit accepted "$UNIT"
    rec_file accepted "$PAGE"
    snap accepted
    rec accepted accept_again_json review "$UNIT" --verdict accept --note "Accurate and complete." --json
}

# An accept on a page the docs tree already links, with nothing left open: the
# closing turn reads the handover from `show --json` after the accept.
scenario_closing_linked() {
    drafted
    python3 -c '
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
text = text.replace(":maxdepth: 1\n", ":maxdepth: 1\n\nreference/config\n", 1)
open(path, "w", encoding="utf-8").write(text)
' docs/index.md
    git add docs/index.md
    git commit -q -m "list the configuration reference in the toctree"
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
text = text.replace(":maxdepth: 1\n", ":maxdepth: 1\n\nreference/index\n", 1)
open(path, "w", encoding="utf-8").write(text)
' docs/index.md
    printf '# Reference\n\n```{toctree}\n:maxdepth: 1\n\nconfig\n```\n' >docs/reference/index.md
    git add docs/index.md docs/reference/index.md
    git commit -q -m "list the reference section and the configuration page in it"
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

# A walked how-to accepted with one deviated step, one skipped step and one
# request the reviewer judged without a redraft: four things open at handover
# once the reader's arrival is counted.
scenario_closing_walk() {
    base
    declare_install
    printf '%s' '[{"id":"install","text":"Install toyq from the checkout: python3 -m pip install /srv/toyq","mode":"agent","stateful":false},{"id":"init","text":"Create the configuration: toyq init","mode":"agent","stateful":false},{"id":"first-job","text":"Queue and run a job: toyq add \"echo hi\" && toyq run --once","mode":"ta","stateful":false}]' |
        "$CRAYON" plan-steps install --steps-file - >/dev/null 2>&1
    local seq request
    seq=$(last_plan_seq install)
    record_step install install "$seq" pass "Successfully installed toyq\n" >/dev/null 2>&1
    record_step install init "$seq" deviated "Created toyq.toml\n" agent \
        "toyq init needed --force-dir on a fresh checkout" >/dev/null 2>&1
    skip_step install first-job "$seq" "no network in CI" >/dev/null 2>&1
    stage_draft install how-to/install.md "$INSTALL_PAGE"
    "$CRAYON" draft install "$(draft_path install how-to/install.md)" >/dev/null 2>&1
    "$CRAYON" review install --verdict fix \
        --note "Say which Python version toyq needs." >/dev/null 2>&1
    request=$(tail -n 1 .crayon/units/install/ledger.jsonl | json_field seq)
    rec closing_walk show_json show install --json
    rec closing_walk accept review install --verdict accept --resolves "$request"
    rec closing_walk handover_json show install --json
    rec closing_walk summary_md summary install --md
    snap closing_walk
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
    rec missing accept_json review "$UNIT" --verdict accept --note "Ship it." --json
}

scenario_target_exists() {
    base
    declare_cfg
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1
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
    "$CRAYON" signoff "$UNIT" >/dev/null 2>&1
    "$CRAYON" unit edit "$UNIT" --audience "operators and developers configuring toyq" >/dev/null 2>&1
    rec stale show_json show "$UNIT" --json
    rec_unit stale "$UNIT"
    snap stale
    stage_page "$PAGE_V1"
    rec stale draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
}

scenario_retired() {
    base
    declare_cfg
    "$CRAYON" unit retire "$UNIT" --note "Superseded by the settings guide." >/dev/null 2>&1
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
            --source README.md --body-file - >/dev/null 2>&1
    "$CRAYON" signoff install >/dev/null 2>&1
}

scenario_walk() {
    base
    declare_install
    printf '%s' '[{"id":"install","text":"Install toyq from the checkout: python3 -m pip install /srv/toyq","mode":"agent","stateful":true},{"id":"init","text":"Create the configuration: toyq init","mode":"agent","stateful":true},{"id":"first-job","text":"Queue and run a job: toyq add \"echo hi\" && toyq run --once","mode":"agent","stateful":true}]' |
        "$CRAYON" plan-steps install --steps-file - >/dev/null 2>&1
    rec walk show_json show install --json
    rec walk show show install
    rec_unit walk install
    snap walk
}

scenario_crashed() {
    base
    declare_cfg
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
    git commit -q -a --amend -m "crayon: drafted $UNIT"
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
    git commit -q -a --amend -m "crayon: drafted $UNIT"
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
    stage_context doc-style.md "$DOC_STYLE"
    rec context_staged show_json context show --json
    snap context_staged
    stage_context glossary.md "$GLOSSARY"
    stage_context structure.md "$STRUCTURE"
    rec context_recorded record context record --note "toyq context"
    rec context_recorded show_json context show --json
    snap context_recorded
    rec_file context_recorded .crayon/context/doc-style.md
    rec_file context_recorded .crayon/context/glossary.md
    rec_file context_recorded .crayon/context/structure.md
}

for scenario in declared signed drafted accepted closing_linked closing_nested closing closing_walk \
    edited missing target_exists stale retired walk crashed diverged no_material \
    docs_outside context; do
    ("scenario_$scenario"; cleanup)
done
