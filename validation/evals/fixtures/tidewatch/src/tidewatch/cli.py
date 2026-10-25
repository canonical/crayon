"""The tidewatch command."""

import argparse
import sys

from tidewatch import __version__, config, store, watcher


def build_parser():
    parser = argparse.ArgumentParser(prog="tidewatch")
    verbs = parser.add_subparsers(dest="verb", required=True)
    add = verbs.add_parser("add", help="watch a directory")
    add.add_argument("path")
    add.add_argument("--on-change", required=True, help="the command to run")
    add.add_argument("--ignore", action="append", default=[], help="a glob to ignore")
    verbs.add_parser("list", help="list the watches")
    remove = verbs.add_parser("remove", help="stop watching")
    remove.add_argument("watch_id")
    run = verbs.add_parser("run", help="watch until interrupted")
    run.add_argument("--once", action="store_true", help="one poll, then exit")
    verbs.add_parser("check", help="validate the settings and exit")
    verbs.add_parser("version", help="print the version")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.verb == "version":
        print(__version__)
        return 0
    try:
        settings = config.load(config_file_values())
    except ValueError as exc:
        print("tidewatch: %s" % exc, file=sys.stderr)
        return 2
    if args.verb == "check":
        print("settings: ok")
        return 0
    watches = store.Store(settings.state_dir)
    if args.verb == "add":
        print(watches.add(args.path, args.on_change, args.ignore))
    elif args.verb == "list":
        for row in watches.rows():
            print("%(id)s  %(path)s  %(command)s" % row)
    elif args.verb == "remove":
        watches.remove(args.watch_id)
    elif args.verb == "run":
        return watcher.run(watches.rows(), settings, once=args.once)
    return 0


def config_file_values():
    try:
        import tomllib
    except ImportError:
        return {}
    try:
        with open("tidewatch.toml", "rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        return {}
