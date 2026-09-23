#!/usr/bin/env bash
# states.sh: record what the real tool prints in each state lane B replays.
#
# Usage: bash validation/evals/fixtures/states.sh OUT.jsonl   (from the repository root)
#
# Lane B shows a model a history of `dogen` calls and asks for the next action.
# That history must be what the tool really prints, byte for byte, so it is
# recorded here and never typed by hand. Each scenario builds one state in a
# hermetic temp repo from tests/lib.sh (the one definition site for that
# fixture), copies in the toyq project, drives the real verbs, and appends one
# JSON line per recorded command:
#
#   {"state": ..., "label": ..., "cmd": "dogen ...", "exit": N, "output": "..."}
#
# `cmd` is the command as an agent types it (`dogen ...`). `output` is stdout and
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
FIXTURE="$ROOT/validation/evals/fixtures/toyq"
export DOGEN="$ROOT/dogen.py"
# shellcheck source=../../../tests/lib.sh
source "$ROOT/tests/lib.sh"

UNIT=cfg
TARGET=reference/config.md
PAGE="docs/$TARGET"

# rec STATE LABEL ARGS... : run `dogen ARGS...`, record it as typed.
rec() {
    local state="$1" label="$2" out rc
    shift 2
    out=$("$DOGEN" "$@" 2>&1)
    rc=$?
    python3 -c '
import json, shlex, sys
state, label, rc, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
cmd = " ".join(["dogen"] + [shlex.quote(arg) for arg in sys.argv[5:]])
print(json.dumps({"state": state, "label": label, "cmd": cmd, "exit": rc, "output": out}))
' "$state" "$label" "$rc" "$out" "$@" >>"$OUT"
}

# rec_unit STATE UNIT : the unit's plan and ledger, as a model reading the repo sees them.
rec_unit() {
    rec_file "$1" ".dogen/units/$2/unit.md"
    rec_file "$1" ".dogen/units/$2/ledger.jsonl"
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

base() {
    setup_repo
    cp -R "$FIXTURE/." .
    mkdir -p .agents/skills
    cp -R "$ROOT"/skills/dogen-* .agents/skills/
    printf '.dogen/staging/\n' >.gitignore
    git add -A
    git commit -q -m "toyq project, dogen skills installed"
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
        "$DOGEN" unit new "$UNIT" --intent reference \
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
    "$DOGEN" signoff "$UNIT" >/dev/null 2>&1
    stage_page "$PAGE_V1"
    "$DOGEN" draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" >/dev/null 2>&1
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
    "$DOGEN" signoff "$UNIT" >/dev/null 2>&1
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
    "$DOGEN" review "$UNIT" --verdict accept --note "Accurate and complete." >/dev/null 2>&1
    rec accepted show_json show "$UNIT" --json
    rec_unit accepted "$UNIT"
    rec_file accepted "$PAGE"
    snap accepted
    rec accepted accept_again_json review "$UNIT" --verdict accept --note "Accurate and complete." --json
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
    "$DOGEN" signoff "$UNIT" >/dev/null 2>&1
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
    "$DOGEN" signoff "$UNIT" >/dev/null 2>&1
    "$DOGEN" unit edit "$UNIT" --audience "operators and developers configuring toyq" >/dev/null 2>&1
    rec stale show_json show "$UNIT" --json
    rec_unit stale "$UNIT"
    snap stale
    stage_page "$PAGE_V1"
    rec stale draft_json draft "$UNIT" "$(draft_path "$UNIT" "$TARGET")" --json
}

scenario_retired() {
    base
    declare_cfg
    "$DOGEN" unit retire "$UNIT" --note "Superseded by the settings guide." >/dev/null 2>&1
    rec retired show_json show "$UNIT" --json
    rec_unit retired "$UNIT"
    snap retired
}

scenario_walk() {
    base
    printf '%s\n' '# Plan' '' 'Install toyq and queue a first job.' |
        "$DOGEN" unit new install --intent how-to \
            --audience "operators installing toyq for the first time" \
            --title "Install toyq" --target how-to/install.md \
            --source README.md --body-file - >/dev/null 2>&1
    "$DOGEN" signoff install >/dev/null 2>&1
    printf '%s' '[{"id":"install","text":"Install the package: pip install toyq","mode":"agent","stateful":true},{"id":"init","text":"Create the configuration: toyq init","mode":"agent","stateful":true},{"id":"first-job","text":"Queue and run a job: toyq add \"echo hi\" && toyq run --once","mode":"agent","stateful":true}]' |
        "$DOGEN" plan-steps install --steps-file - >/dev/null 2>&1
    rec walk show_json show install --json
    rec walk show show install
    rec_unit walk install
    snap walk
}

scenario_crashed() {
    base
    declare_cfg
    DOGEN_CRASH_AT=append "$DOGEN" signoff "$UNIT" >/dev/null 2>&1
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
    local ledger=".dogen/units/$UNIT/ledger.jsonl" saved
    saved=$(mktemp)
    cp "$ledger" "$saved"
    python3 -c '
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines(True)
lines[1] = lines[1].replace("reference", "referenc3", 1)
open(path, "w", encoding="utf-8").write("".join(lines))
' "$ledger"
    git commit -q -a --amend -m "dogen: drafted $UNIT"
    cp "$saved" "$ledger"
    rm -f "$saved"
    rec diverged show_json show "$UNIT" --json
    snap diverged
}

# The last event taken out of the commit and left behind uncommitted, with no
# manifest to resume from (recovery_unsupported, detail no_material).
scenario_no_material() {
    drafted
    local ledger=".dogen/units/$UNIT/ledger.jsonl" saved
    saved=$(mktemp)
    cp "$ledger" "$saved"
    python3 -c '
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().splitlines(True)
open(path, "w", encoding="utf-8").write("".join(lines[:-1]))
' "$ledger"
    git commit -q -a --amend -m "dogen: drafted $UNIT"
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
    base
    rec context_empty show_json context show --json
    snap context_empty
    printf '# Doc style\n\nImpersonal, present tense. Short sentences.\n' |
        "$DOGEN" context stage doc-style.md --body-file - >/dev/null 2>&1
    rec context_staged show_json context show --json
    snap context_staged
    printf '# Glossary\n\n- **job**: one queued shell command.\n- **retry**: a re-run of a failed job.\n' |
        "$DOGEN" context stage glossary.md --body-file - >/dev/null 2>&1
    printf '# Structure\n\n- docs/reference/: settings and commands.\n- docs/how-to/: task guides.\n' |
        "$DOGEN" context stage structure.md --body-file - >/dev/null 2>&1
    "$DOGEN" context record --note "toyq context" >/dev/null 2>&1
    rec context_recorded show_json context show --json
    snap context_recorded
    rec_file context_recorded .dogen/context/doc-style.md
    rec_file context_recorded .dogen/context/glossary.md
    rec_file context_recorded .dogen/context/structure.md
}

for scenario in declared signed drafted accepted edited missing target_exists stale \
    retired walk crashed diverged no_material docs_outside context; do
    ("scenario_$scenario"; cleanup)
done
