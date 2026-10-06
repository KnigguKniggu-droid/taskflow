"""SQLite connection handling and schema setup for TaskFlow."""

import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    assignee_id INTEGER REFERENCES users (id),
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_assignee_id ON tasks (assignee_id);

CREATE TABLE IF NOT EXISTS task_activity (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   INTEGER NOT NULL REFERENCES tasks (id),
    event     TEXT NOT NULL,
    detail    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_activity_task_id ON task_activity (task_id);
"""


def connect(database):
    """Open a connection configured the way every TaskFlow connection is."""
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Return the current app context's connection, opening it on first use."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exception=None):
    """Close the app context's connection if one was opened."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _add_column_if_missing(conn, table, column, definition):
    """Add ``column`` to ``table`` if it is not already present.

    Uses PRAGMA table_info to check existence so that an unrelated
    OperationalError from the ALTER TABLE is never silently swallowed.
    """
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(row["name"] == column for row in rows):
        return  # already present — idempotent no-op
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(database):
    """Create the schema in ``database`` if it does not exist yet.

    Also backfills any pre-migration rows whose ``completed`` column is NULL
    to 0, so that existing databases are corrected without a full rebuild.

    For databases that predate the lifecycle feature:
    - Adds the ``status`` column to ``tasks`` if absent (DEFAULT 'open').
    - Adds the ``task_activity`` table if absent.
    - Backfills ``status = 'completed'`` for rows where ``completed = 1``.
    """
    conn = connect(database)
    try:
        conn.executescript(SCHEMA)
        # executescript() issues an implicit COMMIT before running, which
        # resets connection-level PRAGMAs (including foreign_keys) back to
        # their SQLite defaults.  Re-enable foreign key enforcement so that
        # subsequent DML in this connection is fully guarded.
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            # Backfill rows created before the NOT NULL DEFAULT 0 migration.
            # Safe to run on a fresh database (no rows → no-op).
            conn.execute("UPDATE tasks SET completed = 0 WHERE completed IS NULL")

            # Add status column if this is a pre-lifecycle database.
            _add_column_if_missing(
                conn, "tasks", "status", "TEXT NOT NULL DEFAULT 'open'"
            )

            # Backfill status for rows already marked completed.
            conn.execute(
                "UPDATE tasks SET status = 'completed' WHERE completed = 1 AND status = 'open'"
            )
    finally:
        conn.close()


def init_app(app):
    """Create the app's schema and close connections when each app context ends."""
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
