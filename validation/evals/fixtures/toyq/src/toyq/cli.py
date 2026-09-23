"""toyq's command line: init, add, run, status."""

import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(prog="toyq")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create toyq.toml and the job database")
    add = sub.add_parser("add", help="queue a shell command as a job")
    add.add_argument("job")
    run = sub.add_parser("run", help="run queued jobs until the queue is empty")
    run.add_argument("--once", action="store_true", help="run one job, then stop")
    sub.add_parser("status", help="list jobs and their states")
    return parser.parse_args(argv)
