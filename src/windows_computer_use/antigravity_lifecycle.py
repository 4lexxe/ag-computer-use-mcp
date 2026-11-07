"""Read Antigravity's local run status without reading conversation contents."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path


def default_databases():
    override = os.environ.get("WINDOWS_COMPUTER_USE_ANTIGRAVITY_DB")
    if override:
        return [Path(override).expanduser().resolve()]
    return [
        Path.home() / ".gemini" / product / "conversation_summaries.db"
        for product in ("antigravity", "antigravity-ide", "antigravity-cli")
    ]


class AntigravityRunMonitor:
    def __init__(self, databases=None):
        self.databases = default_databases() if databases is None else databases
        self.owner = None
        self.baseline = self._runs()
        self._bind([key for key, row in self.baseline.items() if self._running(row)])
        inherited_db = os.environ.get("WINDOWS_COMPUTER_USE_RUN_DB")
        inherited_id = os.environ.get("WINDOWS_COMPUTER_USE_RUN_ID")
        if databases is None and inherited_db and inherited_id:
            self.owner = (inherited_db, inherited_id)
            if Path(inherited_db) not in self.databases:
                self.databases.append(Path(inherited_db))

    @staticmethod
    def _running(row):
        return not row[3] and (bool(row[2]) or row[1].endswith("_RUNNING"))

    def _runs(self):
        runs = {}
        for path in self.databases:
            if not path.is_file():
                continue
            try:
                # mode=ro prevents creating or modifying the application's DB.
                with closing(
                    sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.05)
                ) as connection:
                    rows = connection.execute(
                        "SELECT conversation_id, status, not_fully_idle, killed, last_user_input_time "
                        "FROM conversation_summaries WHERE nesting_depth = 0 "
                        "ORDER BY last_user_input_time DESC LIMIT 64"
                    ).fetchall()
                    for row in rows:
                        runs[(str(path), row[0])] = row
            except (sqlite3.Error, OSError):
                continue  # Other clients and unsupported schemas use idle cleanup.
        return runs

    def _bind(self, candidates):
        # Do not guess which chat owns the indicator when several are running.
        if len(candidates) == 1:
            self.owner = candidates[0]

    def finished(self):
        runs = self._runs()
        if self.owner is None:
            changed = [
                key
                for key, row in runs.items()
                if key not in self.baseline or row[4] != self.baseline[key][4]
            ]
            self._bind(changed)
            if self.owner is None:
                self.baseline = runs
                return False
        row = runs.get(self.owner)
        return bool(row and (row[3] or (row[1].endswith("_IDLE") and not row[2])))
