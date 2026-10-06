# An independent mutation check of the new lifecycle work found two behaviors that no test pins down: (1) if PATCH /tasks/<id> with {"status": "completed"} stopped setting the completed column (writing 0 instead of 1), every test still passes; (2) if the overdue list only included tasks whose status is open, dropping past-due tasks that are in_progress or blocked, every test still passes. Decide the intended behavior for each, add tests that would fail if it regressed, run the full test suite and the taskflow-regression-check skill and show both passing, then commit only your changes with a clear message whose last line is: Generated-by: IBM Bob

---

*Rendered by Claude Code from Bob's local task store because Bob's "Export Current Task"*
*command was not run for this task. User and assistant text is verbatim; tool calls are listed*
*by name and main argument; tool output and the system prompt are omitted.*

---

### 👤 User

An independent mutation check of the new lifecycle work found two behaviors that no test pins down: (1) if PATCH /tasks/<id> with {"status": "completed"} stopped setting the completed column (writing 0 instead of 1), every test still passes; (2) if the overdue list only included tasks whose status is open, dropping past-due tasks that are in_progress or blocked, every test still passes. Decide the intended behavior for each, add tests that would fail if it regressed, run the full test suite and the taskflow-regression-check skill and show both passing, then commit only your changes with a clear message whose last line is: Generated-by: IBM Bob

---

### 🤖 Assistant

> 🔧 **use_skill** — taskflow-regression-check

> 🔧 **read_file** — app/services.py

### 🤖 Assistant

Now let me read the existing tests to understand the current test structure:

> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

Now I have a complete picture. Let me analyze both mutation gaps:

**Gap 1 — PATCH `{"status": "completed"}` not setting `completed = 1`:**
Looking at `update_task` in `services.py` lines 219-223, the code correctly sets `completed = 1 if new_status == "completed" else 0`. The existing `test_patch_open_to_completed_sets_completed_true` (line 1023) checks that the *response* body has `completed=True`, but `_task_to_dict` derives `completed` from `status == "completed"` (line 487), not from the DB column. So if the DB write of `completed=1` was broken (writing 0 instead), `_task_to_dict` would still return `True` because it uses `status == "completed"`. **The test would still pass.** A test must read the raw DB value directly.

**Gap 2 — Overdue list excluding `in_progress`/`blocked` tasks:**
The docstring says "open tasks" but the SQL uses `status != 'completed'`, which correctly includes `in_progress` and `blocked`. The mutation would change that to `status = 'open'`. No test creates a past-due `in_progress` or `blocked` task and checks it appears in `/tasks/overdue`. 

Now I'll add the two pinning tests:

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

The file ends at line 1100. Now I'll append the two new tests. The first belongs in `StatusLifecycleTestCase` (it uses `patch_task` and the DB connection helper from that class). The second belongs in `TaskApiTestCase` (it uses `overdue_ids`). I'll add both at the end of their respective classes.

The `StatusLifecycleTestCase` ends at line 1100. I need to append a test there that reads the raw SQLite `completed` column after a PATCH. It needs `connect` from `app.db` which is already imported at line 7.

The overdue test will be a new method in `TaskApiTestCase` — I'll insert it right after the existing overdue tests (~line 89). Let me check exactly where `TaskApiTestCase` ends:

> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

The `TaskApiTestCase` last test ends at line 99, followed by a blank line and then `TagFilterTestCase` starts at line 102. I'll insert the new overdue test before line 101 (after `test_new_task_completed_field_is_false`).

Now let me add both tests:

> 🔧 **apply_diff** — tests/test_tasks.py

### 🤖 Assistant

The new overdue test passed. Now I'll add the second test — the raw DB check for `PATCH status=completed` writing `completed=1`. This goes at the end of `StatusLifecycleTestCase`:

> 🔧 **apply_diff** — tests/test_tasks.py

### 🤖 Assistant

Both tests pass. Let me now run the full unittest suite explicitly to confirm the exact count:

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **execute_command** — .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1

### 🤖 Assistant

93 tests, all pass. The exit code 1 from PowerShell is a false alarm from stderr being treated as an error by the shell — Python printed to stderr and the actual result is `OK`. Now run the regression check script explicitly:

> 🔧 **execute_command** — .venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py

### 🤖 Assistant

**ALL CHECKS PASSED** — 93 unittest tests + 23 regression checks. Now commit:

> 🔧 **update_todo_list** — 

### 🤖 Assistant

> 🔧 **execute_command** — git add tests/test_tasks.py; git commit -m "tests: pin two unguarded lifecycle mutation gaps

### 🤖 Assistant

> 🔧 **execute_command** — & "C:\Program Files\Git\bin\git.exe" add tests/test_tasks.py

### 🤖 Assistant

> 🔧 **execute_command** — & "C:\Program Files\Git\bin\git.exe" commit -m "tests: pin two unguarded lifecycle mutation gaps

### 🤖 Assistant

> 🔧 **update_todo_list** — 

### 🤖 Assistant

Done. Here's what was decided and added:

---

### Intended behaviour established

**Gap 1 — `PATCH {"status": "completed"}` and the `completed` column**

The intended behaviour is that setting `status` to `"completed"` via PATCH **must also write `completed = 1` to the DB column** (and write `0` when transitioning away from completed). The existing HTTP-level test [`test_patch_open_to_completed_sets_completed_true`](tests/test_tasks.py:1023) was blind to this because [`_task_to_dict`](app/services.py:477) derives the `completed` field from `status == "completed"` — not the column — so it would return `True` even if the column stored `0`.

**Gap 2 — Overdue list scope**

The intended behaviour is that **any non-completed task** (open, `in_progress`, or `blocked`) with a past due date appears in `/tasks/overdue`. The SQL already uses `status != 'completed'` but no test exercised `in_progress` or `blocked` tasks there.

---

### Tests added to [`tests/test_tasks.py`](tests/test_tasks.py)

| Test | Class | What it pins |
|---|---|---|
| `test_patch_status_completed_writes_completed_column_to_db` | `StatusLifecycleTestCase` | Raw SQLite `completed` column is `1` after PATCH `{status: completed}` |
| `test_patch_status_non_completed_writes_completed_zero_to_db` | `StatusLifecycleTestCase` | Raw SQLite `completed` column is `0` after transitioning back to `open` |
| `test_overdue_includes_in_progress_and_blocked_tasks` | `TaskApiTestCase` | `in_progress` and `blocked` past-due tasks both appear in `/tasks/overdue` |

---

### Results

- **unittest suite**: 93 tests, all `OK`
- **Regression check**: 23/23 checks passed — **ALL CHECKS PASSED**
- Committed as `ac7341f` on `bob-session`
