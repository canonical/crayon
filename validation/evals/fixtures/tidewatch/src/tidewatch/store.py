"""The watches, kept as JSON under the state directory."""

import json
import os
import uuid


class Store:
    def __init__(self, state_dir):
        self.path = os.path.join(state_dir, "watches.json")

    def rows(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return []

    def add(self, path, command, ignore):
        rows = self.rows()
        watch_id = uuid.uuid4().hex[:8]
        rows.append({"id": watch_id, "path": path, "command": command, "ignore": ignore})
        self._write(rows)
        return watch_id

    def remove(self, watch_id):
        self._write([row for row in self.rows() if row["id"] != watch_id])

    def _write(self, rows):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2)
