# Stage 5 - Agent mode: root-cause repair + tests

- Bob task (ACP session) id: `870e1654850d5883fafca581610d91ef`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `agent`
- Started (UTC): 2026-10-05T04:03:30+00:00 - duration 74.6 s - stop reason: end_turn
- Tool calls: 18; permission requests: 16 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
Implement the repair you recommended. Fix the root cause rather than only the symptom, keep all existing behavior intact, add regression tests that would have caught this defect, run the full suite and show it passing. Then commit only your changes with a clear message whose last line is: Generated-by: IBM Bob
```

## Tool calls by Bob

- `other` Updating todo list - completed
- `read` Reading file <repo>\app\db.py - completed
- `edit` Applying diff to <repo>\app\db.py - completed
- `other` Updating todo list - completed
- `read` Reading file <repo>\tests\test_tasks.py - completed
- `edit` Applying diff to <repo>\tests\test_tasks.py - completed
- `other` Updating todo list - completed
- `execute` .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1 - failed
- `execute` .venv\Scripts\python.exe -m unittest tests.test_tasks -v; exit $LASTEXITCODE - completed
- `other` Updating todo list - completed
- `execute` git -C "<repo>" add app/db.py tests/test_tasks.py - failed
- `execute` where.exe git 2>&1; if (-not $?) { Get-Command git -ErrorAction SilentlyContinue } - failed
- `execute` $env:PATH -split ';' | Where-Object { $_ -ne '' } | Sort-Object - completed
- `execute` Get-ChildItem "C:\Program Files\Git\cmd\git.exe" -ErrorAction SilentlyContinue; Get-ChildItem "C:\Program Files (x86)\Git\cmd\git.exe" -ErrorAction SilentlyCont - failed
- `execute` $git = "C:\Program Files\Git\cmd\git.exe"; & $git -C "<repo>" add app/db.py tests/test_tasks.py; & $git -C "<repo>" status - completed
- `execute` $git = "C:\Program Files\Git\cmd\git.exe"
$msg = @"
fix: enforce completed NOT NULL DEFAULT 0 to repair overdue query

The `completed` column was declared as `I - completed
- `execute` $git = "C:\Program Files\Git\cmd\git.exe"; & $git -C "<repo>" show --stat HEAD - completed
- `other` Updating todo list - completed

## Bob's answer (verbatim)

The schema uses `CREATE TABLE IF NOT EXISTS`, so simply changing `completed INTEGER` to `completed INTEGER NOT NULL DEFAULT 0` in `SCHEMA` will only affect **new** databases. For existing databases that already have rows with `NULL` in `completed`, I need to add a migration step to `init_db` that:
1. Backfills existing `NULL` rows to `0`.
2. Cannot change the column constraint in-place (SQLite limitation), but with `DEFAULT 0` set via `ALTER TABLE … ADD COLUMN` not applicable here — the column already exists.

The correct approach: after running `SCHEMA` (which creates the table on new DBs with the right constraint), run an `UPDATE` to backfill any `NULL` values on existing DBs, and keep the `SCHEMA` change so all fresh databases get the constraint from the start. For existing databases where the column already exists without the constraint, the `UPDATE` handles correctness for existing rows, and `CREATE TABLE IF NOT EXISTS` won't re-create it (the constraint only applies to new databases). This is the minimal safe fix: the backfill `UPDATE` is idempotent, harmless on new DBs (no rows yet), and fixes existing DBs.Now add regression tests. I need to cover the three gaps identified in the analysis:
1. A completed task is **not** returned by the overdue endpoint (was never tested).
2. A task with no `due_date` is **not** returned by the overdue endpoint.
3. The original failing case: a newly created (never completed) task with a past due date **is** returned.All 7 tests pass (the exit code 1 with `NativeCommandError` is a PowerShell cosmetic — stderr output from a subprocess triggers it even when the process itself succeeds; the final line is `OK` with no failures). Let me verify the exit code cleanly:7/7 pass, exit code 0.Git is not on PATH. Let me find it:All done. Here is a summary of every change made.

---

## What was changed and why

### [`app/db.py`](app/db.py)

**Schema (`SCHEMA` constant, line 20)**
```diff
-    completed INTEGER,
+    completed INTEGER NOT NULL DEFAULT 0,
```
This is the root-cause fix. Every new database will enforce the invariant at the storage layer: the column can never be `NULL`, and rows that omit it from an `INSERT` receive `0` automatically.

**`init_db()` (lines 50–66)**  
A backfill `UPDATE` is executed immediately after `executescript(SCHEMA)`:
```python
with conn:
    conn.execute("UPDATE tasks SET completed = 0 WHERE completed IS NULL")
```
This handles existing databases where rows were stored before the schema change. On a fresh database it is a harmless no-op (no rows exist yet). The `with conn:` context manager commits the update or rolls it back on error.

---

### [`tests/test_tasks.py`](tests/test_tasks.py)

Three regression tests were added, each targeting a specific facet of the bug:

| Test | What it pins down |
|---|---|
| `test_completed_overdue_task_excluded` | A past-due task that has been completed must not appear in the overdue list. This is the direct regression for `completed = 0` vs. `completed IS NULL`. |
| `test_overdue_excludes_tasks_without_due_date` | A task with no `due_date` (so `due_date IS NULL`) must never appear. Guards against `NULL < date` accidentally becoming truthy. |
| `test_new_task_completed_field_is_false` | A freshly created task must return `False` (a strict `bool`) for `completed` at the API boundary, not a `NULL`-coerced falsy value. |

---

### Test run (7/7 pass)

```
test_complete_task                          ... ok
test_completed_overdue_task_excluded        ... ok   ← new
test_create_task                            ... ok
test_future_task_not_listed_as_overdue      ... ok
test_new_task_completed_field_is_false      ... ok   ← new
test_overdue_excludes_tasks_without_due_date ... ok  ← new
test_overdue_task_is_detected               ... ok   ← was FAIL, now ok

Ran 7 tests in 0.275s  OK
```
