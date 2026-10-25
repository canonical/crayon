"""Run each watch's command, at most max_hooks_in_flight at a time."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor


def run_one(watch, event, path, timeout):
    env = dict(os.environ, TIDEWATCH_EVENT=event, TIDEWATCH_PATH=path)
    try:
        return subprocess.run(watch["command"], shell=True, env=env, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        return 124


def run_ready(ready, settings):
    with ThreadPoolExecutor(max_workers=settings.max_hooks_in_flight) as pool:
        for watch, event, path, _ in ready:
            pool.submit(run_one, watch, event, path, settings.hook_timeout_seconds)
