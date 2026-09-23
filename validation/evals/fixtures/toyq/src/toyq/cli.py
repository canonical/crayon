"""toyq's command line: init, add, run, status."""

import argparse
import os
import sqlite3
import subprocess
import sys

from toyq.config import DEFAULTS, load

CONFIG_FILE = "toyq.toml"


def _read_toml(path):
    """The flat ``key = value`` lines of toyq.toml; values keep their default's type."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            key, sep, value = line.partition("=")
            key = key.strip()
            if sep and key in DEFAULTS:
                values[key] = type(DEFAULTS[key])(value.strip().strip('"'))
    return values


def _connect(config):
    db = sqlite3.connect(config.db_path)
    db.execute("CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, command TEXT, "
               "state TEXT DEFAULT 'queued', attempts INTEGER DEFAULT 0)")
    return db


def init(config):
    if os.path.exists(CONFIG_FILE):
        print("%s already exists" % CONFIG_FILE)
    else:
        with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
            for key, value in DEFAULTS.items():
                handle.write('%s = "%s"\n' % (key, value) if isinstance(value, str)
                             else "%s = %s\n" % (key, value))
        print("wrote %s" % CONFIG_FILE)
    _connect(config).close()
    print("job database: %s" % config.db_path)


def add(config, job):
    with _connect(config) as db:
        job_id = db.execute("INSERT INTO jobs (command) VALUES (?)", (job,)).lastrowid
    print("queued job %d: %s" % (job_id, job))


def run(config, once):
    with _connect(config) as db:
        while True:
            row = db.execute("SELECT id, command FROM jobs WHERE state = 'queued' "
                             "ORDER BY id LIMIT 1").fetchone()
            if row is None:
                print("queue empty")
                return
            job_id, command = row
            code = subprocess.call(command, shell=True, timeout=config.job_timeout_seconds)
            state = "done" if code == 0 else "failed"
            db.execute("UPDATE jobs SET state = ?, attempts = attempts + 1 WHERE id = ?",
                       (state, job_id))
            print("job %d %s (exit %d)" % (job_id, state, code))
            if once:
                return


def status(config):
    with _connect(config) as db:
        for job_id, command, state, attempts in db.execute(
                "SELECT id, command, state, attempts FROM jobs ORDER BY id"):
            print("%d  %-7s  %d  %s" % (job_id, state, attempts, command))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="toyq")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create toyq.toml and the job database")
    add_cmd = sub.add_parser("add", help="queue a shell command as a job")
    add_cmd.add_argument("job")
    run_cmd = sub.add_parser("run", help="run queued jobs until the queue is empty")
    run_cmd.add_argument("--once", action="store_true", help="run one job, then stop")
    sub.add_parser("status", help="list jobs and their states")
    args = parser.parse_args(argv)
    config = load(_read_toml(CONFIG_FILE), os.environ)
    if args.command == "init":
        init(config)
    elif args.command == "add":
        add(config, args.job)
    elif args.command == "run":
        run(config, args.once)
    else:
        status(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
