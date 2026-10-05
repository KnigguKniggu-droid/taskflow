# Stage 3 - reproduce and diagnose (no edits)

- Bob task (ACP session) id: `870e1654850d5883fafca581610d91ef`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `agent`
- Started (UTC): 2026-10-05T04:02:01+00:00 - duration 21.4 s - stop reason: end_turn
- Tool calls: 1; permission requests: 1 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
Use the existing virtual environment in .venv. Run the full test suite exactly as the README describes and show me the output. For each failing test, trace the behavior through the request, the route, the service function, the SQL that runs, and the schema. Distinguish the symptom from the root cause and explain precisely why the expected task is missing. Do not modify any files.
```

## Tool calls by Bob

- `execute` .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1 - failed

## Bob's answer (verbatim)

One test fails. Here is the complete trace from the assertion back to the schema.

---

## Test output

```
test_complete_task ... ok
test_create_task ... ok
test_future_task_not_listed_as_overdue ... ok
test_overdue_task_is_detected ... FAIL

AssertionError: 1 not found in []
```

Three tests pass. One fails.

---

## Failing test: `test_overdue_task_is_detected`

### What the test does

[`test_overdue_task_is_detected`](tests/test_tasks.py:61):

```python
task = self.create_task(due_date=(date.today() - timedelta(days=3)).isoformat())
self.assertIn(task["id"], self.overdue_ids())
```

It creates a task whose `due_date` is three days in the past, then asserts that task's `id` appears in the list returned by `GET /tasks/overdue`. The list is empty (`[]`), so `id=1` is not in it, and the assertion fails.

---

## Full trace: from HTTP request to the missing row

### Step 1 — Route layer

[`list_overdue_tasks()`](app/routes.py:49):

```python
@bp.get("/tasks/overdue")
def list_overdue_tasks():
    return jsonify({"tasks": services.list_overdue_tasks(date.today())})
```

`date.today()` is evaluated here and passed into the service. Nothing wrong at this layer.

---

### Step 2 — Service layer

[`services.list_overdue_tasks(today)`](app/services.py:107):

```python
def list_overdue_tasks(today):
    rows = get_db().execute(
        SELECT_TASKS + " WHERE due_date < ? AND completed = 0 ORDER BY due_date, id",
        (today.isoformat(),),
    )
    return [_task_to_dict(row) for row in rows]
```

The full SQL that executes is:

```sql
SELECT id, title, description, tags, due_date, assignee_id, completed, created_at
FROM tasks
WHERE due_date < '2025-...'   -- today's date
  AND completed = 0
ORDER BY due_date, id
```

The `due_date < ?` predicate is satisfied — the task's due date is three days ago. That part is fine.

The second predicate is `completed = 0`. This is where the failure originates.

---

### Step 3 — Schema and INSERT

[`db.py` schema](app/db.py:13):

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    due_date    TEXT,
    assignee_id INTEGER REFERENCES users (id),
    completed   INTEGER,          -- ← no DEFAULT, no NOT NULL
    created_at  TEXT NOT NULL
);
```

`completed` has **no `DEFAULT` clause** and **no `NOT NULL` constraint**.

[`services.create_task()`](app/services.py:62) inserts a new task:

```sql
INSERT INTO tasks (title, description, tags, due_date, assignee_id, created_at)
VALUES (?, ?, ?, ?, ?, ?)
```

`completed` is **not listed** in the column list. Because the column has no DEFAULT, SQLite stores `NULL` for it automatically.

---

### Step 4 — SQL three-way logic (the root cause)

SQLite (like all SQL databases) uses **three-valued logic**: every comparison returns `TRUE`, `FALSE`, or `NULL`. When either operand of `=` is `NULL`, the result is `NULL`, not `TRUE` or `FALSE`.

```
NULL = 0   →   NULL   (not TRUE, not FALSE)
```

A `WHERE` clause only keeps rows where the predicate evaluates to `TRUE`. A `NULL` result is treated the same as `FALSE` — the row is discarded.

So:

| Task row | `due_date < today` | `completed` value | `completed = 0` | Row included? |
|---|---|---|---|---|
| Newly created task | `TRUE` (past date) | `NULL` | `NULL` | **No** |
| Explicitly completed task | `TRUE` | `1` | `FALSE` | No |
| Hypothetical task with `completed = 0` | `TRUE` | `0` | `TRUE` | Yes |

A freshly created task **cannot** satisfy `completed = 0` because its `completed` column is `NULL`, and `NULL = 0` evaluates to `NULL`, which is falsy.

---

## Symptom vs. Root Cause

| | Description |
|---|---|
| **Symptom** | `GET /tasks/overdue` returns an empty list even when tasks with past due dates exist. The test assertion `assertIn(task["id"], self.overdue_ids())` fails with `1 not found in []`. |
| **Root Cause** | The `completed` column in the schema has no `DEFAULT` and is not included in the `INSERT` column list, so new tasks are stored with `completed = NULL`. The `WHERE` filter in `list_overdue_tasks` uses `completed = 0`, which evaluates to `NULL` (not `TRUE`) under SQL three-valued logic for any row where `completed IS NULL`. Those rows are silently excluded from the result set. |

The fix would be either:
- Change the schema to `completed INTEGER NOT NULL DEFAULT 0` so new tasks store `0` instead of `NULL` (making `completed = 0` match them), **or**
- Change the SQL predicate to `completed IS NOT 1` or `(completed IS NULL OR completed = 0)` to correctly capture the "not completed" state regardless of `NULL`.

But as requested, no files have been modified.
