"""Collapse a burst of events on one watch into one hook run."""

import time


class Pending:
    def __init__(self, debounce_ms):
        self.window = debounce_ms / 1000.0
        self.items = {}

    def add(self, watch, event, path):
        self.items[watch["id"]] = (watch, event, path, time.monotonic())

    def ready(self):
        now = time.monotonic()
        due = [item for item in self.items.values() if now - item[3] >= self.window]
        for watch, _, _, _ in due:
            del self.items[watch["id"]]
        return due
