# Stage 9c - follow-up on an observed existing-database failure

- Bob task (ACP session) id: `72776e99c6aefa41cf6e9d26c43952dc`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `agent`
- Started (UTC): 2026-10-05T04:21:53+00:00 - duration 116.7 s - stop reason: end_turn
- Tool calls: 25; permission requests: 19 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
An independent check reproduced finding A-1 as an observable failure: with a database file created by the old schema (completed INTEGER, nullable, no default), start the current app, then create a task with a due date two days in the past. The stored completed value is NULL and GET /tasks/overdue does not list the task, so the original defect still occurs for existing databases after startup. Reconsider your decision on A-1, fix the cause, add a regression test that reproduces this exact scenario, run the full suite and show it passing, then commit only your changes with a clear message whose last line is: Generated-by: IBM Bob
```

## Tool calls by Bob

- `read` Reading file <repo>\app\db.py - completed
- `read` Reading file <repo>\app\__init__.py - completed
- `execute` .venv\Scripts\python.exe -c "
import tempfile, os, sqlite3
from datetime import date, timedelta

# Step 1: create an old-schema database (completed INTEGER, nul - completed
- `read` Reading file <repo>\app\services.py (46, 68) - completed
- `other` Updating todo list - failed
- `other` Updating todo list - completed
- `edit` Applying diff to <repo>\app\services.py - completed
- `execute` .venv\Scripts\python.exe -c "
import tempfile, os, sqlite3
from datetime import date, timedelta

# Step 1: create an old-schema database (completed INTEGER, nul - failed
- `execute` .venv\Scripts\python.exe -c @"
import tempfile, os, sqlite3
from datetime import date, timedelta

fd, db_path = tempfile.mkstemp(suffix='.sqlite')
os.close(fd)
 - failed
- `edit` Writing file <repo>\.bob\tmp\verify_fix.py - completed
- `execute` .venv\Scripts\python.exe .bob\tmp\verify_fix.py - failed
- `execute` .venv\Scripts\python.exe .bob\tmp\verify_fix.py - failed
- `execute` $env:PYTHONPATH = "<repo>"; .venv\Scripts\python.exe .bob\tmp\verify_fix.py - completed
- `read` Reading file <repo>\tests\test_tasks.py (265, 315) - completed
- `read` Reading file <repo>\tests\test_tasks.py (355, 365) - completed
- `read` Reading file <repo>\tests\test_tasks.py (1, 12) - completed
- `other` Updating todo list - completed
- `edit` Applying diff to <repo>\tests\test_tasks.py - completed
- `other` Updating todo list - completed
- `execute` .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1 - failed
- `execute` .venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" add app/services.py tests/test_tasks.py - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" diff --staged --stat - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" commit -m "Fix NULL completed on old-schema databases by writing 0 explicitly in INSERT

On databases created before the 'c - completed
- `other` Updating todo list - completed

## Bob's answer (verbatim)

Let me first verify the defect myself before writing any fix.Now let me reproduce the exact failure scenario to confirm the defect:Defect confirmed. The sequence is:
1. Old-schema DB has `completed INTEGER` (nullable, no default)
2. `init_db` runs `CREATE TABLE IF NOT EXISTS` — **no-op**, column stays nullable
3. The backfill `UPDATE … WHERE completed IS NULL` only fixes **existing** rows
4. `POST /tasks` inserts a **new** row — no `completed` supplied → SQLite stores `NULL`
5. `GET /tasks/overdue` queries `WHERE completed = 0` — `NULL = 0` is `NULL` (falsy) → task excluded

The fix must ensure new inserts always write `0` for `completed` on old-schema databases. Since `CREATE TABLE IF NOT EXISTS` can't change an existing column, the correct approach is to use `ALTER TABLE … ADD COLUMN` with `DEFAULT 0` if the column exists but lacks the default — or, simpler and fully portable: always include `completed` explicitly in `INSERT INTO tasks`, supplying `0` rather than relying on the column default.The root cause is clear: `create_task` omits `completed` from the `INSERT`, relying on the column `DEFAULT 0` — which only works on databases where the schema was created fresh with the new definition. On old-schema databases, the column is nullable with no default, so `NULL` is stored.

The minimal fix: include `completed = 0` explicitly in the `INSERT`, so it always writes `0` regardless of what the column definition says. This is the right fix because:
- It works on both old and new databases
- It doesn't require ALTER TABLE (which can't add `NOT NULL` without a default on SQLite without table recreation)
- It's minimal — one line change in `create_task`Now verify the fix resolves the defect:Fix confirmed — `raw DB completed: 0` and the task appears in `/tasks/overdue`. Now add the regression test. Let me read the end of the test file to place it correctly:Now I'll look at the top of the test file to see what imports are already there and what the existing `SchemaInitTestCase` looks like, so the new test class can follow the same pattern:Good — `connect` and `init_db` are already imported. Now I'll insert the new regression test class before `if __name__ == "__main__":`:Now run the full suite:All 26 tests pass. Now run the regression smoke test:26/26 unit tests · 23/23 smoke checks — all green. Now commit:## What changed and why

### Root cause (confirmed by reproduction)

With a database created under the old schema (`completed INTEGER`, nullable, no default), startup calls `init_db` → `CREATE TABLE IF NOT EXISTS` — a **no-op** for existing tables. The backfill `UPDATE … WHERE completed IS NULL` only fixes *pre-existing* rows. Every subsequent `POST /tasks` omitted `completed` from the `INSERT`, causing SQLite to store `NULL`. The overdue query `WHERE completed = 0` then evaluated `NULL = 0` → `NULL` (falsy), silently excluding every open task.

### Fix — [`app/services.py:62–65`](app/services.py:62)

```python
# Before
"INSERT INTO tasks (title, description, tags, due_date, assignee_id, created_at)"
" VALUES (?, ?, ?, ?, ?, ?)",

# After
"INSERT INTO tasks (title, description, tags, due_date, assignee_id, completed, created_at)"
" VALUES (?, ?, ?, ?, ?, 0, ?)",
```

Supply `completed = 0` explicitly in every `INSERT`, so the stored value is always `0` regardless of whether the column carries a `DEFAULT` in its definition.

### Tests — [`OldSchemaRegressionTestCase`](tests/test_tasks.py:362) (2 new tests)

| Test | What it guards |
|------|---------------|
| `test_new_task_on_old_schema_stores_completed_zero_not_null` | Raw SQLite value is `0`, not `NULL`, after `POST /tasks` on an old-schema database |
| `test_new_task_on_old_schema_appears_in_overdue` | End-to-end: a past-due task on an old-schema database **appears** in `GET /tasks/overdue` |

`setUp` seeds a fresh temp file with the old nullable schema, then calls `create_app` exactly as an upgrade would.

**26/26 unit tests · 23/23 regression checks — ALL PASSED · commit `768b9fb`**
