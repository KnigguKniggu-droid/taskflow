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


def init_db(database):
    """Create the schema in ``database`` if it does not exist yet.

    Also backfills any pre-migration rows whose ``completed`` column is NULL
    to 0, so that existing databases are corrected without a full rebuild.
    """
    conn = connect(database)
    try:
        conn.executescript(SCHEMA)
        # Backfill rows created before the NOT NULL DEFAULT 0 migration.
        # Safe to run on a fresh database (no rows → no-op).
        with conn:
            conn.execute("UPDATE tasks SET completed = 0 WHERE completed IS NULL")
    finally:
        conn.close()


def init_app(app):
    """Create the app's schema and close connections when each app context ends."""
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
