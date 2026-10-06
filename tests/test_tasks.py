import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app
from app.db import connect, init_db


class TaskApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_user(self, name="Ada"):
        response = self.client.post("/users", json={"name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def create_task(self, **fields):
        response = self.client.post("/tasks", json={"title": "Write report", **fields})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def overdue_ids(self):
        response = self.client.get("/tasks/overdue")
        self.assertEqual(response.status_code, 200)
        return [task["id"] for task in response.get_json()["tasks"]]

    def test_create_task(self):
        user = self.create_user()
        task = self.create_task(
            description="Quarterly numbers",
            tags=["Backend", " database ", "backend"],
            due_date="2030-01-15",
            assignee_id=user["id"],
        )
        self.assertEqual(task["title"], "Write report")
        self.assertEqual(task["description"], "Quarterly numbers")
        self.assertEqual(task["tags"], ["backend", "database"])
        self.assertEqual(task["due_date"], "2030-01-15")
        self.assertEqual(task["assignee_id"], user["id"])
        self.assertFalse(task["completed"])
        self.assertEqual(task["status"], "open", task)

        response = self.client.get(f"/tasks/{task['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), task)

    def test_complete_task(self):
        task = self.create_task()

        response = self.client.post(f"/tasks/{task['id']}/complete")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["completed"])
        self.assertTrue(self.client.get(f"/tasks/{task['id']}").get_json()["completed"])

    def test_overdue_task_is_detected(self):
        task = self.create_task(due_date=(date.today() - timedelta(days=3)).isoformat())

        self.assertIn(task["id"], self.overdue_ids())

    def test_future_task_not_listed_as_overdue(self):
        task = self.create_task(due_date=(date.today() + timedelta(days=30)).isoformat())

        self.assertNotIn(task["id"], self.overdue_ids())

    def test_completed_overdue_task_excluded(self):
        # A task that is past due but already completed must NOT appear in the
        # overdue list.  This is a correctness guard: a completed task should
        # never resurface in the overdue list regardless of its due date.
        # (The regression guard for the NULL/0 schema bug is the separate
        # test_new_task_completed_field_is_false and SchemaInitTestCase tests.)
        past = (date.today() - timedelta(days=1)).isoformat()
        task = self.create_task(due_date=past)
        self.client.post(f"/tasks/{task['id']}/complete")

        self.assertNotIn(task["id"], self.overdue_ids())

    def test_overdue_excludes_tasks_without_due_date(self):
        # Tasks with no due_date must never appear in the overdue list.
        task = self.create_task()

        self.assertNotIn(task["id"], self.overdue_ids())

    def test_new_task_completed_field_is_false(self):
        # Newly created tasks must report completed=False (not NULL coerced).
        # This guards the schema DEFAULT 0 invariant at the API boundary.
        task = self.create_task()

        self.assertFalse(task["completed"])
        fetched = self.client.get(f"/tasks/{task['id']}").get_json()
        self.assertFalse(fetched["completed"])
        self.assertIs(fetched["completed"], False)

    def test_overdue_includes_in_progress_and_blocked_tasks(self):
        """GET /tasks/overdue must include past-due tasks regardless of status.

        A task with status 'in_progress' or 'blocked' that is past its due date
        is still overdue — only 'completed' tasks are excluded.  This guards
        against a regression where the query uses ``status = 'open'`` instead of
        ``status != 'completed'``, which would silently drop in_progress and
        blocked tasks from the overdue list.
        """
        past = (date.today() - timedelta(days=1)).isoformat()

        # Create tasks in each non-completed status with a past due date.
        t_open        = self.create_task(due_date=past)
        t_in_progress = self.create_task(due_date=past)
        t_blocked     = self.create_task(due_date=past)

        # Advance statuses via PATCH.
        r1 = self.client.patch(f"/tasks/{t_in_progress['id']}", json={"status": "in_progress"})
        self.assertEqual(r1.status_code, 200, r1.get_json())
        r2 = self.client.patch(f"/tasks/{t_blocked['id']}", json={"status": "blocked"})
        self.assertEqual(r2.status_code, 200, r2.get_json())

        overdue = self.overdue_ids()
        self.assertIn(t_open["id"],        overdue, "open past-due task missing from overdue list")
        self.assertIn(t_in_progress["id"], overdue,
                      "in_progress past-due task missing from overdue list")
        self.assertIn(t_blocked["id"],     overdue,
                      "blocked past-due task missing from overdue list")


class TagFilterTestCase(unittest.TestCase):
    """Tests for GET /tasks?tag=<tag> filtering."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def _create_user(self, name="Ada"):
        r = self.client.post("/users", json={"name": name})
        self.assertEqual(r.status_code, 201)
        return r.get_json()

    def _create_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def _list_ids(self, **params):
        r = self.client.get("/tasks", query_string=params)
        self.assertEqual(r.status_code, 200, r.get_json())
        return [t["id"] for t in r.get_json()["tasks"]]

    # --- basic tag filter ---

    def test_tag_filter_returns_matching_tasks(self):
        t1 = self._create_task(tags=["backend", "database"])
        t2 = self._create_task(tags=["backend"])
        t3 = self._create_task(tags=["frontend"])

        ids = self._list_ids(tag="backend")
        self.assertIn(t1["id"], ids, ids)
        self.assertIn(t2["id"], ids, ids)
        self.assertNotIn(t3["id"], ids, ids)

    def test_tag_filter_excludes_tasks_with_no_tags(self):
        t_no_tags = self._create_task()
        t_tagged = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="backend")
        self.assertIn(t_tagged["id"], ids)
        self.assertNotIn(t_no_tags["id"], ids)

    def test_tag_filter_no_match_returns_empty(self):
        self._create_task(tags=["frontend"])

        ids = self._list_ids(tag="backend")
        self.assertEqual(ids, [])

    # --- exact membership, not substring ---

    def test_tag_filter_is_not_substring_match(self):
        """'end' must NOT match a task tagged 'backend'."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="end")
        self.assertNotIn(t["id"], ids, "'end' matched 'backend' (substring false positive)")

    def test_tag_filter_prefix_is_not_substring_match(self):
        """'back' must NOT match a task tagged 'backend'."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="back")
        self.assertNotIn(t["id"], ids, "'back' matched 'backend' (prefix false positive)")

    def test_tag_filter_middle_tag_exact_match(self):
        """A tag stored in the middle of the comma list is found exactly."""
        t = self._create_task(tags=["alpha", "beta", "gamma"])

        self.assertIn(t["id"], self._list_ids(tag="beta"))
        self.assertNotIn(t["id"], self._list_ids(tag="bet"))
        self.assertNotIn(t["id"], self._list_ids(tag="eta"))

    def test_underscore_in_tag_is_not_like_wildcard(self):
        """tag=a_b must NOT match a task whose only tag is 'axb'.

        SQLite LIKE treats '_' as a single-character wildcard; without escaping,
        ?tag=a_b would match 'axb', 'a-b', 'a0b', etc.  This is the regression
        test for the ESCAPE fix.
        """
        t_axb = self._create_task(tags=["axb"])   # should NOT match a_b
        t_a_b = self._create_task(tags=["a-b"])   # should NOT match a_b either
        t_exact = self._create_task(tags=["a_b"]) # should match

        ids = self._list_ids(tag="a_b")
        self.assertNotIn(t_axb["id"], ids, "a_b wildcard matched axb (underscore not escaped)")
        self.assertNotIn(t_a_b["id"], ids, "a_b wildcard matched a-b (underscore not escaped)")
        self.assertIn(t_exact["id"], ids, "a_b did not match a_b (exact tag missing)")

    # --- combined assignee + tag filter ---

    def test_combined_filter_assignee_and_tag(self):
        u1 = self._create_user("Alice")
        u2 = self._create_user("Bob")

        t1 = self._create_task(tags=["backend"], assignee_id=u1["id"])
        t2 = self._create_task(tags=["backend"], assignee_id=u2["id"])
        t3 = self._create_task(tags=["frontend"], assignee_id=u1["id"])

        ids = self._list_ids(tag="backend", assignee_id=u1["id"])
        self.assertIn(t1["id"], ids, ids)
        self.assertNotIn(t2["id"], ids, ids)  # wrong assignee
        self.assertNotIn(t3["id"], ids, ids)  # wrong tag

    def test_combined_filter_no_match_returns_empty(self):
        u = self._create_user()
        self._create_task(tags=["backend"])          # no assignee
        self._create_task(assignee_id=u["id"])       # no tag

        ids = self._list_ids(tag="backend", assignee_id=u["id"])
        self.assertEqual(ids, [])

    # --- assignee-only filter still works ---

    def test_assignee_only_filter_unchanged(self):
        u = self._create_user()
        t_assigned = self._create_task(assignee_id=u["id"])
        t_unassigned = self._create_task()

        ids = self._list_ids(assignee_id=u["id"])
        self.assertIn(t_assigned["id"], ids)
        self.assertNotIn(t_unassigned["id"], ids)

    # --- edge cases: empty and invalid tag parameter ---

    def test_empty_tag_param_returns_all_tasks(self):
        """A blank tag= query param is treated as 'no filter'."""
        t1 = self._create_task(tags=["backend"])
        t2 = self._create_task(tags=["frontend"])

        ids = self._list_ids(tag="")
        self.assertIn(t1["id"], ids)
        self.assertIn(t2["id"], ids)

    def test_whitespace_only_tag_param_returns_all_tasks(self):
        """A whitespace-only tag= param is treated as 'no filter'."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="   ")
        self.assertIn(t["id"], ids)

    def test_invalid_tag_param_returns_400(self):
        """A tag value that violates the tag pattern returns 400."""
        r = self.client.get("/tasks", query_string={"tag": "INVALID TAG!"})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_invalid_tag_with_spaces_returns_400(self):
        r = self.client.get("/tasks", query_string={"tag": "has space"})
        self.assertEqual(r.status_code, 400, r.get_json())

    def test_very_long_invalid_tag_error_is_truncated(self):
        """A very long invalid tag value must not be reflected verbatim in the error.

        parse_tag_param truncates the displayed value to 50 characters so an
        attacker cannot inflate the error response body arbitrarily.
        """
        long_tag = "X" * 200  # 200-char invalid tag (uppercase, > 32 chars)
        r = self.client.get("/tasks", query_string={"tag": long_tag})
        self.assertEqual(r.status_code, 400, r.get_json())
        error_msg = r.get_json()["error"]
        # The raw 200-char string must not appear verbatim in the response.
        self.assertNotIn(long_tag, error_msg, "full 200-char input was reflected in error")
        # The displayed excerpt must be at most 50 chars (plus surrounding quotes).
        # Find the quoted excerpt between the first pair of ' characters.
        import re as _re
        match = _re.search(r"'([^']*)'", error_msg)
        self.assertIsNotNone(match, f"no quoted excerpt found in error message: {error_msg!r}")
        self.assertLessEqual(len(match.group(1)), 50,
                             f"reflected excerpt is longer than 50 chars: {match.group(1)!r}")

    def test_tag_param_is_case_insensitive(self):
        """tag=Backend (uppercase) normalises to 'backend' and matches."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="Backend")
        self.assertIn(t["id"], ids)


class SchemaInitTestCase(unittest.TestCase):
    """Direct tests of db.init_db — below the Flask/HTTP layer.

    These guard the schema migration (completed NOT NULL DEFAULT 0) and the
    NULL-backfill that repairs rows created before that migration.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)

    def tearDown(self):
        os.remove(self.db_path)

    def test_schema_completed_default_is_zero_not_null(self):
        """INSERT without a completed value must store 0, not NULL.

        This fails if the schema definition is reverted to 'completed INTEGER'
        (nullable with no DEFAULT), because SQLite would then store NULL and
        bool(None) at the API layer would silently coerce it to False, masking
        the bug from all HTTP-level assertions.
        """
        init_db(self.db_path)
        conn = connect(self.db_path)
        try:
            with conn:
                conn.execute(
                    "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
                    ("t", "2024-01-01T00:00:00+00:00"),
                )
            row = conn.execute("SELECT completed FROM tasks WHERE title = 't'").fetchone()
        finally:
            conn.close()

        # Must be the integer 0 — not NULL, not False.
        self.assertIsNotNone(row["completed"], "completed is NULL: DEFAULT 0 is missing from schema")
        self.assertEqual(row["completed"], 0, f"completed={row['completed']!r}, expected 0")

    def test_init_db_backfills_null_completed_rows(self):
        """init_db must UPDATE pre-migration rows where completed IS NULL to 0.

        This verifies that the backfill statement
        'UPDATE tasks SET completed = 0 WHERE completed IS NULL'
        in init_db runs and zeroes any legacy NULL rows.

        Note: SQLite's 'CREATE TABLE IF NOT EXISTS' does not ALTER an existing
        table's column definition, so this test cannot verify that the
        'NOT NULL DEFAULT 0' constraint was applied to the pre-existing column.
        That invariant is checked for fresh databases in
        test_schema_completed_default_is_zero_not_null.
        """
        # Step 1: Bootstrap with the old (nullable) schema using raw SQL so that
        # we can insert a row with completed = NULL without triggering the
        # NOT NULL constraint of the current schema.
        conn = connect(self.db_path)
        try:
            conn.executescript(
                """
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
                    completed INTEGER,
                    created_at TEXT NOT NULL
                );
                """
            )
            with conn:
                conn.execute(
                    "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
                    ("legacy", "2024-01-01T00:00:00+00:00"),
                )
            # Confirm the row really is NULL before migration.
            row = conn.execute("SELECT completed FROM tasks WHERE title = 'legacy'").fetchone()
            self.assertIsNone(row["completed"], "pre-condition: legacy row should have NULL completed")
        finally:
            conn.close()

        # Step 2: Run init_db (the migration + backfill).
        init_db(self.db_path)

        # Step 3: The legacy row must now have completed = 0, not NULL.
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT completed FROM tasks WHERE title = 'legacy'").fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row["completed"], "backfill missing: completed is still NULL after init_db")
        self.assertEqual(row["completed"], 0, f"backfill wrong: completed={row['completed']!r}, expected 0")

    def test_init_db_adds_status_column_to_new_db(self):
        """A fresh database created by init_db must have a 'status' column on tasks."""
        init_db(self.db_path)
        conn = connect(self.db_path)
        try:
            rows = conn.execute("PRAGMA table_info(tasks)").fetchall()
            col_names = [r["name"] for r in rows]
        finally:
            conn.close()
        self.assertIn("status", col_names, "status column missing from fresh database")

    def test_init_db_creates_task_activity_table(self):
        """A fresh database must have a task_activity table after init_db."""
        init_db(self.db_path)
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_activity'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "task_activity table missing after init_db on fresh database")

    def test_init_db_backfills_status_for_completed_rows(self):
        """init_db must set status='completed' for rows where completed=1."""
        # Build a pre-lifecycle database with the old schema (no status column)
        conn = connect(self.db_path)
        try:
            conn.executescript(
                """
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
                """
            )
            with conn:
                conn.execute(
                    "INSERT INTO tasks (title, completed, created_at) VALUES (?, ?, ?)",
                    ("done-task", 1, "2024-01-01T00:00:00+00:00"),
                )
                conn.execute(
                    "INSERT INTO tasks (title, completed, created_at) VALUES (?, ?, ?)",
                    ("open-task", 0, "2024-01-01T00:00:00+00:00"),
                )
        finally:
            conn.close()

        # Run migration
        init_db(self.db_path)

        conn = connect(self.db_path)
        try:
            done_row = conn.execute("SELECT status FROM tasks WHERE title='done-task'").fetchone()
            open_row = conn.execute("SELECT status FROM tasks WHERE title='open-task'").fetchone()
        finally:
            conn.close()

        self.assertEqual(done_row["status"], "completed",
                         "completed=1 row was not backfilled to status='completed'")
        self.assertEqual(open_row["status"], "open",
                         "completed=0 row should have status='open'")


class OldSchemaRegressionTestCase(unittest.TestCase):
    """Regression tests for databases created with the pre-migration schema.

    The old schema had ``completed INTEGER`` (nullable, no DEFAULT).  SQLite's
    ``CREATE TABLE IF NOT EXISTS`` does not ALTER an existing table, so ``init_db``
    cannot apply the ``NOT NULL DEFAULT 0`` constraint to such a database.

    The fix is to include ``completed = 0`` explicitly in the ``INSERT`` inside
    ``create_task``, so that every new row always stores 0 regardless of whether
    the column has a DEFAULT defined.
    """

    # The pre-migration schema — completed is nullable with no default.
    _OLD_SCHEMA = (
        "CREATE TABLE IF NOT EXISTS users "
        "    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS tasks ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    title TEXT NOT NULL,"
        "    description TEXT NOT NULL DEFAULT '',"
        "    tags TEXT NOT NULL DEFAULT '',"
        "    due_date TEXT,"
        "    assignee_id INTEGER REFERENCES users (id),"
        "    completed INTEGER,"
        "    created_at TEXT NOT NULL"
        ");"
    )

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        # Seed the database with the OLD schema (completed nullable, no DEFAULT).
        conn = connect(self.db_path)
        try:
            conn.executescript(self._OLD_SCHEMA)
        finally:
            conn.close()
        # Now start the app against that old-schema database, exactly as a
        # real upgrade would.  init_db runs CREATE TABLE IF NOT EXISTS (no-op
        # for the existing table) and the backfill UPDATE (no rows yet → no-op).
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def test_new_task_on_old_schema_stores_completed_zero_not_null(self):
        """POST /tasks on an old-schema database must store completed=0, not NULL.

        Fails if create_task relies solely on the column DEFAULT instead of
        supplying 0 explicitly in the INSERT.  On the old schema the column has
        no DEFAULT, so omitting completed from the INSERT stores NULL.
        """
        r = self.client.post("/tasks", json={"title": "t"})
        self.assertEqual(r.status_code, 201, r.get_json())

        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT completed FROM tasks").fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(
            row["completed"],
            "completed is NULL on old-schema database: INSERT must supply completed=0 explicitly",
        )
        self.assertEqual(row["completed"], 0, f"completed={row['completed']!r}, expected 0")

    def test_new_task_on_old_schema_appears_in_overdue(self):
        """A past-due task created on an old-schema database must appear in GET /tasks/overdue.

        This is the end-to-end reproduction of the original defect: with a NULL
        completed value, ``WHERE completed = 0`` evaluates to NULL (falsy) and
        silently excludes every open task from the overdue list.
        """
        past = (date.today() - timedelta(days=1)).isoformat()
        r = self.client.post("/tasks", json={"title": "overdue", "due_date": past})
        self.assertEqual(r.status_code, 201, r.get_json())
        task_id = r.get_json()["id"]

        r2 = self.client.get("/tasks/overdue")
        self.assertEqual(r2.status_code, 200, r2.get_json())
        overdue_ids = [t["id"] for t in r2.get_json()["tasks"]]

        self.assertIn(
            task_id,
            overdue_ids,
            f"task {task_id} missing from /tasks/overdue — completed was likely stored as NULL",
        )

    def test_old_schema_db_gets_status_and_activity_after_init(self):
        """After init_db, old-schema databases must have status column and task_activity table."""
        conn = connect(self.db_path)
        try:
            # Verify status column was added by setUp's create_app (which calls init_db)
            col_names = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
            self.assertIn("status", col_names, "status column missing after upgrade")

            table_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_activity'"
            ).fetchone()
            self.assertIsNotNone(table_row, "task_activity table missing after upgrade")
        finally:
            conn.close()


class OldSchemaActivityRegressionTestCase(unittest.TestCase):
    """Tests against a pre-lifecycle database (no status column, no task_activity table).

    Simulates the upgrade path: seed the old schema with completed=1 rows,
    run init_db, and verify the migration results.
    """

    # Old schema: no status column, no task_activity table, completed nullable.
    _OLD_SCHEMA = (
        "CREATE TABLE IF NOT EXISTS users "
        "    (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL);"
        "CREATE TABLE IF NOT EXISTS tasks ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    title TEXT NOT NULL,"
        "    description TEXT NOT NULL DEFAULT '',"
        "    tags TEXT NOT NULL DEFAULT '',"
        "    due_date TEXT,"
        "    assignee_id INTEGER REFERENCES users (id),"
        "    completed INTEGER NOT NULL DEFAULT 0,"
        "    created_at TEXT NOT NULL"
        ");"
    )

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        # Seed the OLD schema with some data
        conn = connect(self.db_path)
        try:
            conn.executescript(self._OLD_SCHEMA)
            with conn:
                conn.execute(
                    "INSERT INTO tasks (title, completed, created_at) VALUES (?, ?, ?)",
                    ("done-before-upgrade", 1, "2024-01-01T00:00:00+00:00"),
                )
                conn.execute(
                    "INSERT INTO tasks (title, completed, created_at) VALUES (?, ?, ?)",
                    ("open-before-upgrade", 0, "2024-01-01T00:00:00+00:00"),
                )
        finally:
            conn.close()
        # Upgrade via create_app (which calls init_db)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def test_task_activity_table_exists_after_upgrade(self):
        """task_activity table must be created when upgrading from the old schema."""
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_activity'"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "task_activity table missing after upgrade")

    def test_status_column_exists_after_upgrade(self):
        """status column must be added to tasks when upgrading from old schema."""
        conn = connect(self.db_path)
        try:
            col_names = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        finally:
            conn.close()
        self.assertIn("status", col_names, "status column missing after upgrade")

    def test_completed_rows_backfilled_to_status_completed(self):
        """Rows with completed=1 must be backfilled to status='completed' after upgrade."""
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT status FROM tasks WHERE title='done-before-upgrade'"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["status"], "completed",
                         "completed=1 row was not backfilled to status='completed'")

    def test_open_rows_have_status_open_after_upgrade(self):
        """Rows with completed=0 must retain status='open' after upgrade."""
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT status FROM tasks WHERE title='open-before-upgrade'"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["status"], "open",
                         "completed=0 row should have status='open' after upgrade")

    def test_new_tasks_work_on_upgraded_database(self):
        """POST /tasks must work normally on an upgraded database."""
        r = self.client.post("/tasks", json={"title": "post-upgrade task"})
        self.assertEqual(r.status_code, 201, r.get_json())
        task = r.get_json()
        self.assertFalse(task["completed"])


class UsersEndpointTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_user(self, name="Ada"):
        response = self.client.post("/users", json={"name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_empty_list(self):
        response = self.client.get("/users")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json(), {"users": []})

    def test_user_appears_after_create(self):
        user = self.create_user("Ada")
        response = self.client.get("/users")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIn(user, response.get_json()["users"])

    def test_multiple_users_ordered_by_id(self):
        u1 = self.create_user("Alice")
        u2 = self.create_user("Bob")
        u3 = self.create_user("Carol")
        response = self.client.get("/users")
        self.assertEqual(response.status_code, 200, response.get_json())
        ids = [u["id"] for u in response.get_json()["users"]]
        self.assertEqual(ids, sorted(ids), f"users not ordered by id: {ids}")
        self.assertEqual(ids, [u1["id"], u2["id"], u3["id"]])


class StatsEndpointTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_task(self, **fields):
        response = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def get_stats(self):
        response = self.client.get("/tasks/stats")
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_zero_state(self):
        stats = self.get_stats()
        # Core keys must be present and zero — new per-status keys are also asserted.
        self.assertEqual(stats["total"],       0, stats)
        self.assertEqual(stats["open"],        0, stats)
        self.assertEqual(stats["completed"],   0, stats)
        self.assertEqual(stats["overdue"],     0, stats)
        self.assertEqual(stats["in_progress"], 0, stats)
        self.assertEqual(stats["blocked"],     0, stats)

    def test_counts_after_creates(self):
        self.create_task()
        self.create_task()
        stats = self.get_stats()
        self.assertEqual(stats["total"], 2, stats)
        self.assertEqual(stats["open"], 2, stats)
        self.assertEqual(stats["completed"], 0, stats)
        self.assertEqual(stats["overdue"], 0, stats)

    def test_completed_count(self):
        task = self.create_task()
        r_complete = self.client.post(f"/tasks/{task['id']}/complete")
        self.assertEqual(r_complete.status_code, 200, r_complete.get_json())
        stats = self.get_stats()
        self.assertEqual(stats["total"], 1, stats)
        self.assertEqual(stats["completed"], 1, stats)
        self.assertEqual(stats["open"], 0, stats)

    def test_overdue_count(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        task = self.create_task(due_date=yesterday)
        stats = self.get_stats()
        self.assertEqual(stats["overdue"], 1, stats)
        # Completing the task removes it from the overdue count.
        self.client.post(f"/tasks/{task['id']}/complete")
        stats_after = self.get_stats()
        self.assertEqual(stats_after["overdue"], 0, stats_after)


class UpdateTaskTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_user(self, name="Ada"):
        response = self.client.post("/users", json={"name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def create_task(self, **fields):
        response = self.client.post("/tasks", json={"title": "Original Title", **fields})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def patch_task(self, task_id, body):
        return self.client.patch(f"/tasks/{task_id}", json=body)

    def test_update_title(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"title": "B"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["title"], "B")

    def test_update_assignee(self):
        user = self.create_user()
        task = self.create_task()
        r = self.patch_task(task["id"], {"assignee_id": user["id"]})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["assignee_id"], user["id"])

    def test_update_tags(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"tags": ["python", "flask"]})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["tags"], ["python", "flask"])

    def test_update_due_date(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"due_date": "2030-06-15"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["due_date"], "2030-06-15")

    def test_clear_due_date(self):
        task = self.create_task(due_date="2030-01-01")
        r = self.patch_task(task["id"], {"due_date": None})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertIsNone(r.get_json()["due_date"])

    def test_update_multiple_fields(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {
            "title": "Updated",
            "tags": ["multi"],
            "due_date": "2031-03-10",
        })
        self.assertEqual(r.status_code, 200, r.get_json())
        data = r.get_json()
        self.assertEqual(data["title"], "Updated")
        self.assertEqual(data["tags"], ["multi"])
        self.assertEqual(data["due_date"], "2031-03-10")

    def test_empty_body_is_noop(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["title"], task["title"])

    def test_404(self):
        r = self.patch_task(99999, {"title": "Ghost"})
        self.assertEqual(r.status_code, 404, r.get_json())
        self.assertIn("error", r.get_json())

    def test_oversized_id_returns_404_not_500(self):
        """PATCH with a task_id larger than SQLite INTEGER max must return 404.

        99999999999999999999999 exceeds MAX_ID (2**63-1) so no such task can
        exist; update_task must raise NotFoundError before passing the value to
        SQLite (which would raise OverflowError and produce a 500).
        """
        r = self.client.patch("/tasks/99999999999999999999999", json={"title": "x"})
        self.assertEqual(r.status_code, 404, r.get_json())
        self.assertIn("error", r.get_json())

    def test_unknown_field_rejected(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"completed": True})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_invalid_title(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"title": ""})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_invalid_due_date(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"due_date": "not-a-date"})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_invalid_assignee(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"assignee_id": 99999})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("does not match an existing user", r.get_json()["error"])

    def test_completed_not_settable(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"completed": True})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_created_at_not_settable(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"created_at": "2020-01-01T00:00:00Z"})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_partial_update_isolation(self):
        """Updating one field must not wipe other fields."""
        user = self.create_user()
        task = self.create_task(
            tags=["original"],
            assignee_id=user["id"],
            due_date="2030-01-01",
        )
        r = self.patch_task(task["id"], {"title": "NewTitle"})
        self.assertEqual(r.status_code, 200, r.get_json())
        data = r.get_json()
        self.assertEqual(data["title"], "NewTitle", data)
        self.assertEqual(data["tags"], ["original"], data)
        self.assertEqual(data["assignee_id"], user["id"], data)
        self.assertEqual(data["due_date"], "2030-01-01", data)

    def test_completed_unchanged_after_patch(self):
        """PATCH must not accidentally flip the completed flag."""
        task = self.create_task()
        self.assertFalse(task["completed"])
        r = self.patch_task(task["id"], {"title": "Updated"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(r.get_json()["completed"], r.get_json())


class FilteredStatsConsistencyTestCase(unittest.TestCase):
    """Guard the server contract that makes client-side filtered stat counts correct.

    The UI derives summary counts (total/open/overdue/completed) from the task
    list returned by GET /tasks?tag=…  It does this by reading each task's
    ``completed`` and ``due_date`` fields.  This test verifies that those fields
    are present and accurate on filtered results, reproducing the exact scenario
    that exposed the stats-card/note disagreement bug:

      4 tasks total (3 open, 1 overdue among open, 1 completed);
      filter by tag "backend" → 2 tasks (1 overdue-open, 1 plain-open).

    If the server ever omitted ``completed`` or ``due_date`` from filtered
    responses, client-side counts would be wrong even with correct JS logic.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def _post_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "T", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def test_filtered_task_list_carries_fields_needed_for_client_counts(self):
        """Filtered GET /tasks response must carry completed and due_date so
        the client can derive accurate per-filter summary counts."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        # 4 tasks that mirror the reported scenario
        t_overdue_backend = self._post_task(tags=["backend"], due_date=yesterday)
        t_open_backend    = self._post_task(tags=["backend"])
        t_open_other      = self._post_task(tags=["frontend"])
        t_completed       = self._post_task(tags=["backend"])
        r_complete = self.client.post(f"/tasks/{t_completed['id']}/complete")
        self.assertEqual(r_complete.status_code, 200, r_complete.get_json())

        # Filter by tag=backend → should return 3 tasks (overdue, open, completed)
        r = self.client.get("/tasks?tag=backend")
        self.assertEqual(r.status_code, 200, r.get_json())
        tasks = r.get_json()["tasks"]
        self.assertEqual(len(tasks), 3, tasks)

        # Every task must carry the fields the client uses for counting
        for t in tasks:
            self.assertIn("completed", t, t)
            self.assertIn("due_date",  t, t)
            self.assertIn("status",    t, t)

        # Derive counts exactly as the client JS does
        today_iso = date.today().isoformat()
        client_total     = len(tasks)
        client_open      = sum(1 for t in tasks if not t["completed"])
        client_completed = sum(1 for t in tasks if t["completed"])
        client_overdue   = sum(
            1 for t in tasks
            if not t["completed"] and t["due_date"] and t["due_date"] < today_iso
        )

        self.assertEqual(client_total,     3, tasks)
        self.assertEqual(client_open,      2, tasks)
        self.assertEqual(client_completed, 1, tasks)
        self.assertEqual(client_overdue,   1, tasks)

        # The untagged task must NOT appear in the filtered list
        filtered_ids = {t["id"] for t in tasks}
        self.assertNotIn(t_open_other["id"], filtered_ids, tasks)


class StatusLifecycleTestCase(unittest.TestCase):
    """Tests for the four-state task lifecycle and status transition validation."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def patch_task(self, task_id, body):
        return self.client.patch(f"/tasks/{task_id}", json=body)

    def test_new_task_has_status_open_and_completed_false(self):
        task = self.create_task()
        self.assertEqual(task["status"], "open", task)
        self.assertFalse(task["completed"], task)

    def test_patch_open_to_in_progress(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"status": "in_progress"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["status"], "in_progress", body)
        self.assertFalse(body["completed"], body)

    def test_patch_open_to_blocked(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"status": "blocked"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["status"], "blocked")

    def test_patch_open_to_completed_sets_completed_true(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"status": "completed"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["status"], "completed", body)
        self.assertTrue(body["completed"], body)

    def test_patch_completed_to_open_reopens(self):
        task = self.create_task()
        self.patch_task(task["id"], {"status": "completed"})
        r = self.patch_task(task["id"], {"status": "open"})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["status"], "open", body)
        self.assertFalse(body["completed"], body)

    def test_patch_completed_to_in_progress_returns_409(self):
        """completed → in_progress is a disallowed transition → 409."""
        task = self.create_task()
        self.patch_task(task["id"], {"status": "completed"})
        r = self.patch_task(task["id"], {"status": "in_progress"})
        self.assertEqual(r.status_code, 409, r.get_json())
        self.assertIn("error", r.get_json())
        self.assertIn("→", r.get_json()["error"])

    def test_patch_same_status_is_noop_returns_200(self):
        """PATCH with the same status value as the current status must return 200, not 409."""
        task = self.create_task()
        self.assertEqual(task["status"], "open")
        r = self.patch_task(task["id"], {"status": "open"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["status"], "open", r.get_json())

    def test_patch_unknown_status_returns_400(self):
        task = self.create_task()
        r = self.patch_task(task["id"], {"status": "pending"})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_post_complete_sets_status_completed(self):
        task = self.create_task()
        r = self.client.post(f"/tasks/{task['id']}/complete")
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["status"], "completed", body)
        self.assertTrue(body["completed"], body)

    def test_post_complete_idempotent_on_already_completed(self):
        task = self.create_task()
        self.client.post(f"/tasks/{task['id']}/complete")
        r = self.client.post(f"/tasks/{task['id']}/complete")
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()
        self.assertEqual(body["status"], "completed", body)

    def test_patch_completed_field_still_rejected(self):
        """PATCH with 'completed' in the body must still return 400."""
        task = self.create_task()
        r = self.patch_task(task["id"], {"completed": True})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_patch_status_equivalent_to_post_complete(self):
        """PATCH {"status":"completed"} behaves like POST /complete."""
        task = self.create_task()
        r = self.patch_task(task["id"], {"status": "completed"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertTrue(r.get_json()["completed"], r.get_json())

    def test_in_progress_to_all_valid_targets(self):
        for target in ("open", "blocked", "completed"):
            # Fresh task each iteration
            t = self.create_task()
            self.patch_task(t["id"], {"status": "in_progress"})
            r = self.patch_task(t["id"], {"status": target})
            self.assertEqual(r.status_code, 200, f"in_progress→{target}: {r.get_json()}")

    def test_patch_status_completed_writes_completed_column_to_db(self):
        """PATCH {"status":"completed"} must write completed=1 to the DB column.

        The API response derives ``completed`` from ``status == 'completed'``
        (via _task_to_dict), so an HTTP-only assertion cannot detect a bug
        where the UPDATE omits the ``completed = 1`` clause.  This test reads
        the raw SQLite column value to pin the write-path independently.
        """
        task = self.create_task()

        r = self.patch_task(task["id"], {"status": "completed"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["status"], "completed", r.get_json())

        # Read the raw DB value — must be 1, not 0 or NULL.
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT completed FROM tasks WHERE id = ?", (task["id"],)
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row["completed"],
                             "completed column is NULL after PATCH status=completed")
        self.assertEqual(row["completed"], 1,
                         f"completed column is {row['completed']!r} after PATCH status=completed, "
                         "expected 1")

    def test_patch_status_non_completed_writes_completed_zero_to_db(self):
        """PATCH to a non-completed status must write completed=0 to the DB column.

        Symmetrically guards the path where a task transitions away from
        completed (e.g. completed → open): the completed column must be reset
        to 0, not left as 1.
        """
        task = self.create_task()

        # First complete the task, then reopen it.
        self.patch_task(task["id"], {"status": "completed"})
        r = self.patch_task(task["id"], {"status": "open"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(r.get_json()["completed"], r.get_json())

        # The DB column must now be 0.
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT completed FROM tasks WHERE id = ?", (task["id"],)
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row["completed"], 0,
                         f"completed column is {row['completed']!r} after reopening task, "
                         "expected 0")

    def test_blocked_to_all_valid_targets(self):
        for target in ("open", "in_progress", "completed"):
            t = self.create_task()
            self.patch_task(t["id"], {"status": "blocked"})
            r = self.patch_task(t["id"], {"status": target})
            self.assertEqual(r.status_code, 200, f"blocked→{target}: {r.get_json()}")


class ActivityHistoryTestCase(unittest.TestCase):
    """Tests for task_activity rows and GET /tasks/<id>/activity."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_user(self, name="Ada"):
        r = self.client.post("/users", json={"name": name})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def create_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def get_activity(self, task_id):
        r = self.client.get(f"/tasks/{task_id}/activity")
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["activity"]

    def patch_task(self, task_id, body):
        return self.client.patch(f"/tasks/{task_id}", json=body)

    def test_create_writes_exactly_one_created_row(self):
        task = self.create_task()
        rows = self.get_activity(task["id"])
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["event"], "created", rows)

    def test_patch_status_writes_status_changed_row(self):
        task = self.create_task()
        self.patch_task(task["id"], {"status": "in_progress"})
        rows = self.get_activity(task["id"])
        events = [r["event"] for r in rows]
        self.assertIn("status_changed", events, rows)
        status_row = next(r for r in rows if r["event"] == "status_changed")
        self.assertIn("open", status_row["detail"], status_row)
        self.assertIn("in_progress", status_row["detail"], status_row)

    def test_patch_assignee_writes_reassigned_row(self):
        user = self.create_user()
        task = self.create_task()
        self.patch_task(task["id"], {"assignee_id": user["id"]})
        rows = self.get_activity(task["id"])
        events = [r["event"] for r in rows]
        self.assertIn("reassigned", events, rows)

    def test_patch_due_date_writes_due_date_changed_row(self):
        task = self.create_task()
        self.patch_task(task["id"], {"due_date": "2030-12-31"})
        rows = self.get_activity(task["id"])
        events = [r["event"] for r in rows]
        self.assertIn("due_date_changed", events, rows)
        dd_row = next(r for r in rows if r["event"] == "due_date_changed")
        self.assertIn("2030-12-31", dd_row["detail"], dd_row)

    def test_patch_details_writes_single_details_edited_row(self):
        """Changing title + tags + description in one PATCH → exactly one details_edited row."""
        task = self.create_task()
        self.patch_task(task["id"], {
            "title": "New Title",
            "tags": ["a", "b"],
            "description": "new desc",
        })
        rows = self.get_activity(task["id"])
        details_rows = [r for r in rows if r["event"] == "details_edited"]
        self.assertEqual(len(details_rows), 1, rows)

    def test_patch_multi_category_writes_correct_rows(self):
        """PATCH that changes title + due_date + status writes one row per category."""
        task = self.create_task()
        self.patch_task(task["id"], {
            "title": "Changed",
            "due_date": "2030-01-01",
            "status": "in_progress",
        })
        rows = self.get_activity(task["id"])
        events = [r["event"] for r in rows]
        self.assertIn("details_edited",  events, events)
        self.assertIn("due_date_changed", events, events)
        self.assertIn("status_changed",  events, events)

    def test_failed_patch_writes_no_activity(self):
        """A validation error must not write any activity rows."""
        task = self.create_task()
        before = self.get_activity(task["id"])
        r = self.patch_task(task["id"], {"status": "pending"})  # invalid
        self.assertEqual(r.status_code, 400, r.get_json())
        after = self.get_activity(task["id"])
        self.assertEqual(len(before), len(after), f"activity grew after failed PATCH: {after}")

    def test_activity_rows_ordered_oldest_first(self):
        task = self.create_task()
        self.patch_task(task["id"], {"status": "in_progress"})
        self.patch_task(task["id"], {"status": "blocked"})
        rows = self.get_activity(task["id"])
        ids = [r["id"] for r in rows]
        self.assertEqual(ids, sorted(ids), f"activity not ordered by id asc: {ids}")

    def test_activity_404_for_nonexistent_task(self):
        r = self.client.get("/tasks/99999/activity")
        self.assertEqual(r.status_code, 404, r.get_json())
        self.assertIn("error", r.get_json())

    def test_activity_isolated_between_tasks(self):
        t1 = self.create_task(title="Task 1")
        t2 = self.create_task(title="Task 2")
        self.patch_task(t1["id"], {"status": "in_progress"})
        rows_t1 = self.get_activity(t1["id"])
        rows_t2 = self.get_activity(t2["id"])
        t1_events = [r["event"] for r in rows_t1]
        t2_events = [r["event"] for r in rows_t2]
        # t1 has created + status_changed; t2 has only created
        self.assertIn("status_changed", t1_events, t1_events)
        self.assertNotIn("status_changed", t2_events, t2_events)

    def test_post_complete_writes_status_changed_row(self):
        task = self.create_task()
        self.client.post(f"/tasks/{task['id']}/complete")
        rows = self.get_activity(task["id"])
        events = [r["event"] for r in rows]
        self.assertIn("status_changed", events, rows)

    def test_post_complete_idempotent_does_not_duplicate_activity(self):
        task = self.create_task()
        self.client.post(f"/tasks/{task['id']}/complete")
        before = self.get_activity(task["id"])
        self.client.post(f"/tasks/{task['id']}/complete")
        after = self.get_activity(task["id"])
        self.assertEqual(len(before), len(after),
                         f"double complete added extra activity rows: {after}")


class StatsBreakdownTestCase(unittest.TestCase):
    """Tests for the extended GET /tasks/stats response."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def get_stats(self):
        r = self.client.get("/tasks/stats")
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()

    def patch_task(self, task_id, body):
        return self.client.patch(f"/tasks/{task_id}", json=body)

    def test_stats_contains_in_progress_and_blocked_keys(self):
        stats = self.get_stats()
        self.assertIn("in_progress", stats, stats)
        self.assertIn("blocked", stats, stats)

    def test_open_equals_sum_of_non_completed(self):
        t1 = self.create_task()  # open
        t2 = self.create_task()  # in_progress
        t3 = self.create_task()  # blocked
        t4 = self.create_task()  # completed
        self.patch_task(t2["id"], {"status": "in_progress"})
        self.patch_task(t3["id"], {"status": "blocked"})
        self.patch_task(t4["id"], {"status": "completed"})

        stats = self.get_stats()
        # open = strictly open + in_progress + blocked
        self.assertEqual(stats["open"], 3, stats)
        self.assertEqual(stats["in_progress"], 1, stats)
        self.assertEqual(stats["blocked"], 1, stats)
        self.assertEqual(stats["completed"], 1, stats)
        self.assertEqual(stats["total"], 4, stats)

    def test_overdue_counts_any_non_completed_status(self):
        """Overdue is any non-completed task with a past due date, regardless of status."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        t_open     = self.create_task(due_date=yesterday)
        t_progress = self.create_task(due_date=yesterday)
        t_blocked  = self.create_task(due_date=yesterday)
        t_done     = self.create_task(due_date=yesterday)
        self.patch_task(t_progress["id"], {"status": "in_progress"})
        self.patch_task(t_blocked["id"],  {"status": "blocked"})
        self.patch_task(t_done["id"],     {"status": "completed"})

        stats = self.get_stats()
        # open + in_progress + blocked each have past due dates → 3 overdue
        self.assertEqual(stats["overdue"], 3, stats)


if __name__ == "__main__":
    unittest.main()


class ActivityReassignNameTestCase(unittest.TestCase):
    """Regression tests: reassign activity detail must record the user's name,
    not a raw user ID string like 'assigned to user 2'."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def _create_user(self, name):
        r = self.client.post("/users", json={"name": name})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def _create_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def _get_activity(self, task_id):
        r = self.client.get(f"/tasks/{task_id}/activity")
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()["activity"]

    def test_reassign_detail_contains_user_name_not_id(self):
        """Assigning a task must record the user's name in the activity detail,
        not the raw numeric ID (e.g. 'assigned to Alice' not 'assigned to user 2')."""
        user = self._create_user("Alice")
        task = self._create_task()

        r = self.client.patch(f"/tasks/{task['id']}", json={"assignee_id": user["id"]})
        self.assertEqual(r.status_code, 200, r.get_json())

        rows = self._get_activity(task["id"])
        reassign_rows = [row for row in rows if row["event"] == "reassigned"]
        self.assertEqual(len(reassign_rows), 1, rows)

        detail = reassign_rows[0]["detail"]
        self.assertIn("Alice", detail, f"user name missing from detail: {detail!r}")
        self.assertNotIn(f"user {user['id']}", detail,
                         f"raw user ID found in detail: {detail!r}")

    def test_reassign_detail_uses_current_user_name(self):
        """The stored detail must match the name of the user at the time of assignment."""
        user_bob   = self._create_user("Bob")
        user_carol = self._create_user("Carol")
        task = self._create_task()

        # Assign to Bob
        self.client.patch(f"/tasks/{task['id']}", json={"assignee_id": user_bob["id"]})
        # Reassign to Carol
        self.client.patch(f"/tasks/{task['id']}", json={"assignee_id": user_carol["id"]})

        rows = self._get_activity(task["id"])
        reassign_rows = [row for row in rows if row["event"] == "reassigned"]
        self.assertEqual(len(reassign_rows), 2, rows)

        details = [r["detail"] for r in reassign_rows]
        self.assertIn("Bob",   details[0], f"first reassign detail: {details[0]!r}")
        self.assertIn("Carol", details[1], f"second reassign detail: {details[1]!r}")

    def test_clear_assignee_still_records_cleared(self):
        """Removing the assignee must record 'assignee cleared', not a name."""
        user = self._create_user("Dana")
        task = self._create_task(assignee_id=user["id"])

        r = self.client.patch(f"/tasks/{task['id']}", json={"assignee_id": None})
        self.assertEqual(r.status_code, 200, r.get_json())

        rows = self._get_activity(task["id"])
        reassign_rows = [row for row in rows if row["event"] == "reassigned"]
        self.assertEqual(len(reassign_rows), 1, rows)
        self.assertEqual(reassign_rows[0]["detail"], "assignee cleared", reassign_rows[0])
