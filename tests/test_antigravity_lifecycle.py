import sqlite3

from windows_computer_use.antigravity_lifecycle import AntigravityRunMonitor


def make_database(path):
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, "
            "status TEXT, not_fully_idle INTEGER, killed INTEGER, last_user_input_time TEXT, "
            "nesting_depth INTEGER)"
        )


def put(path, name, running, timestamp="1", background=False):
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT OR REPLACE INTO conversation_summaries VALUES (?, ?, ?, 0, ?, 0)",
            (
                name,
                "CASCADE_RUN_STATUS_RUNNING" if running else "CASCADE_RUN_STATUS_IDLE",
                int(running or background),
                timestamp,
            ),
        )


def test_tracks_running_chat_until_fully_idle(tmp_path):
    path = tmp_path / "summary.db"
    make_database(path)
    put(path, "owner", True)
    monitor = AntigravityRunMonitor([path])
    assert not monitor.finished()
    put(path, "owner", False, background=True)
    assert not monitor.finished()
    put(path, "owner", False)
    assert monitor.finished()


def test_old_finished_chats_do_not_close_new_indicator(tmp_path):
    path = tmp_path / "summary.db"
    make_database(path)
    put(path, "old", False)
    monitor = AntigravityRunMonitor([path])
    assert not monitor.finished()
    # A short run can start and finish entirely between two polling intervals.
    put(path, "new", False, timestamp="2")
    assert monitor.finished()


def test_does_not_close_for_another_chat(tmp_path):
    path = tmp_path / "summary.db"
    make_database(path)
    put(path, "owner", True)
    monitor = AntigravityRunMonitor([path])
    put(path, "other", False, timestamp="2")
    assert not monitor.finished()
    put(path, "owner", False)
    assert monitor.finished()


def test_ambiguous_runs_and_missing_database_are_not_guessed(tmp_path):
    path = tmp_path / "summary.db"
    make_database(path)
    put(path, "one", True)
    put(path, "two", True)
    monitor = AntigravityRunMonitor([path])
    put(path, "two", False)
    assert not monitor.finished()
    missing = tmp_path / "missing.db"
    assert not AntigravityRunMonitor([missing]).finished()
    assert not missing.exists()


def test_inherited_owner_closes_even_if_run_ended_before_overlay_started(tmp_path, monkeypatch):
    path = tmp_path / "summary.db"
    make_database(path)
    put(path, "owner", False)
    monkeypatch.setenv("WINDOWS_COMPUTER_USE_ANTIGRAVITY_DB", str(path))
    monkeypatch.setenv("WINDOWS_COMPUTER_USE_RUN_DB", str(path))
    monkeypatch.setenv("WINDOWS_COMPUTER_USE_RUN_ID", "owner")
    assert AntigravityRunMonitor().finished()
