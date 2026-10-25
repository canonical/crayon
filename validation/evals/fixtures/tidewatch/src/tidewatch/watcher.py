"""Polling: compare snapshots of each watched tree and hand changes to the hooks."""

import fnmatch
import os
import time

from tidewatch import debounce, hooks


def snapshot(root, ignore, follow_symlinks):
    seen = {}
    for directory, _, files in os.walk(root, followlinks=follow_symlinks):
        for name in files:
            path = os.path.join(directory, name)
            if any(fnmatch.fnmatch(path, pattern) for pattern in ignore):
                continue
            try:
                seen[path] = os.stat(path).st_mtime_ns
            except FileNotFoundError:
                continue
    return seen


def changes(before, after):
    for path in after.keys() - before.keys():
        yield "created", path
    for path in before.keys() - after.keys():
        yield "deleted", path
    for path in after.keys() & before.keys():
        if after[path] != before[path]:
            yield "modified", path


def run(watches, settings, once=False):
    snapshots = {w["id"]: snapshot(w["path"], w["ignore"], settings.follow_symlinks)
                 for w in watches}
    pending = debounce.Pending(settings.debounce_ms)
    while True:
        time.sleep(settings.poll_interval_seconds)
        for watch in watches:
            after = snapshot(watch["path"], watch["ignore"], settings.follow_symlinks)
            for event, path in changes(snapshots[watch["id"]], after):
                pending.add(watch, event, path)
            snapshots[watch["id"]] = after
        hooks.run_ready(pending.ready(), settings)
        if once:
            return 0
