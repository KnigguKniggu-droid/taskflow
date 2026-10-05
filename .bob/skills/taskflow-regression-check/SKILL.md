---
name: taskflow-regression-check
description: Use when the user wants to run the TaskFlow regression check, verify all endpoints work, or smoke-test the API after a change.
---

# TaskFlow Regression Check

Run the full TaskFlow test suite and smoke-test every endpoint in-process.
Follow these steps exactly.

## Step 1 — Locate the virtual environment

The project venv is at `.venv/` in the repository root. On Windows the Python
executable is `.venv/Scripts/python.exe`; on macOS/Linux it is `.venv/bin/python`.

## Step 2 — Run the helper script

Use `execute_command` to run the regression check script with the project's
virtual environment Python from the repository root:

```
# Windows
.venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py

# macOS / Linux
.venv/bin/python .bob/skills/taskflow-regression-check/regression_check.py
```

The script:
1. Runs the full `unittest` suite (`tests.test_tasks`) via subprocess.
2. Spins up the Flask test client in-process and exercises every endpoint:
   - `POST /users`
   - `POST /tasks`
   - `GET /tasks/<id>` (found and 404)
   - `GET /tasks` (unfiltered)
   - `GET /tasks?assignee_id=` (assignee filter)
   - `GET /tasks?tag=` (tag filter — exact match)
   - `GET /tasks?tag=` with a substring value that must **not** match
     (false-positive guard)
   - `GET /tasks?tag=&assignee_id=` (combined filter)
   - `GET /tasks/overdue` (past-due included, future excluded, no-due excluded,
     completed excluded)
   - `POST /tasks/<id>/complete` (success and 404)

## Step 3 — Report results

Parse the script's stdout:
- Each line starting with `✓ [PASS]` or `✗ [FAIL]` is one check.
- The final summary line reads `N passed, M failed out of T checks.`
- The script exits with code 0 if all checks pass, 1 if any fail.

Report to the user:
- Total counts (passed / failed / total).
- For any failing check, the check name and the detail string after `→`.
- A clear overall verdict: **ALL CHECKS PASSED** or **REGRESSION DETECTED**.
