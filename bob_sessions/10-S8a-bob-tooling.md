# Stage 8a - Bob project skills, command and custom mode

- Bob task (ACP session) id: `62a82ea9d1d74d2e08b35db7d26fdee1`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `agent`
- Started (UTC): 2026-10-05T04:12:04+00:00 - duration 120.2 s - stop reason: end_turn
- Tool calls: 26; permission requests: 18 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
Create reusable Bob project tooling for this repository, all under .bob/:
1. A project skill .bob/skills/taskflow-regression-check/SKILL.md that runs the full test suite with the project's virtual environment, then smoke-tests every endpoint in-process with Flask's test client (users, tasks, overdue, completion, assignee filter, tag filter including a substring false positive and a combined filter) and reports pass/fail per check. Put any helper script it needs next to the SKILL.md.
2. A project skill .bob/skills/taskflow-api-review/SKILL.md that reviews route/service/SQL changes against this project's conventions (parameterized SQL, input validation, JSON error format and status codes, exact tag matching, test coverage) and lists findings with file and line.
3. A project slash command .bob/commands/verify-taskflow.md that runs the taskflow-regression-check skill and summarizes the result.
4. A custom mode in .bob/custom_modes.yaml named "TaskFlow Reviewer" with slug taskflow-reviewer that can read files, run commands and use skills but cannot edit files; its role is to review diffs against this project's conventions and report findings only.
Use the formats Bob documents for project skills, commands and custom modes. Run the regression-check helper once to prove it works. Do not change application code or tests. Commit only these files with a clear message whose last line is: Generated-by: IBM Bob
```

## Tool calls by Bob

- `other` Updating todo list - completed
- `other` Using skill create-skill - completed
- `other` Using skill create-mode - completed
- `read` Listing files in <repo> - completed
- `read` Reading file <repo>\app\services.py - completed
- `read` Reading file <repo>\tests\test_tasks.py - completed
- `read` Reading file <repo>\app\routes.py - completed
- `read` Reading file <repo>\app\db.py - completed
- `read` Reading file <repo>\app\__init__.py - completed
- `other` Updating todo list - completed
- `edit` Writing file <repo>\.bob\skills\taskflow-regression-check\regression_check.py - completed
- `edit` Writing file <repo>\.bob\skills\taskflow-regression-check\SKILL.md - completed
- `other` Updating todo list - completed
- `edit` Writing file <repo>\.bob\skills\taskflow-api-review\SKILL.md - completed
- `other` Updating todo list - completed
- `edit` Writing file <repo>\.bob\commands\verify-taskflow.md - completed
- `other` Updating todo list - completed
- `edit` Writing file <repo>\.bob\custom_modes.yaml - completed
- `other` Updating todo list - completed
- `execute` .venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py - completed
- `other` Updating todo list - completed
- `execute` git add .bob/; git status - failed
- `execute` & "C:\Program Files\Git\bin\git.exe" add .bob/ - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" status - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" commit -m "Add Bob project tooling: regression-check skill, api-review skill, verify-taskflow command, TaskFlow Reviewer mo - completed
- `other` Updating todo list - completed

## Bob's answer (verbatim)

Now let me read the existing project structure and check for any existing `.bob/` config:Now let me read the app's `__init__.py` and `db.py` for full context:Now I have all the context I need. Let me create all the files:Now let's run the regression check script to prove it works:All 23 checks pass. Now commit:Everything is done. Here's a summary of what was created and committed:

---

## What was built

### [`regression_check.py`](.bob/skills/taskflow-regression-check/regression_check.py)
A standalone Python script (no new dependencies) that runs two sections:

1. **unittest suite** — invokes `python -m unittest tests.test_tasks -v` via subprocess and reports the exit code as a single PASS/FAIL check.
2. **23 endpoint smoke tests** — spins up Flask's test client in-process against a temporary SQLite file and exercises:
   - `POST /users` (two users)
   - `POST /tasks` (with due dates: past, future, none)
   - `GET /tasks/<id>` — found and 404
   - `GET /tasks` — unfiltered
   - `GET /tasks?assignee_id=` — assignee filter
   - `GET /tasks?tag=backend` — matching and non-matching
   - `GET /tasks?tag=end` — **substring false-positive guard** (must not match `backend`)
   - `GET /tasks?tag=backend&assignee_id=` — combined filter
   - `GET /tasks/overdue` — past-due in, future out, no-due-date out, completed out
   - `POST /tasks/<id>/complete` — success and 404

Ran clean: **23 passed, 0 failed**.

### [`SKILL.md` — taskflow-regression-check](.bob/skills/taskflow-regression-check/SKILL.md)
Auto-activates when you ask to run the regression check or verify endpoints. Instructs Bob to run the helper with the project venv and report totals + any failures.

### [`SKILL.md` — taskflow-api-review](.bob/skills/taskflow-api-review/SKILL.md)
Auto-activates for code reviews. Checks 7 conventions against any diff: parameterized SQL, validation placement in `services.py`, JSON error format/status codes, exact tag matching (no substring), unknown-field rejection, `SELECT_TASKS` constant usage, and test coverage. Reports each finding as `file:line — what — why`.

### [`verify-taskflow.md`](.bob/commands/verify-taskflow.md)
A `/verify-taskflow` slash command that activates the regression-check skill and outputs a concise summary.

### [`custom_modes.yaml`](.bob/custom_modes.yaml)
`taskflow-reviewer` mode — `read` + `execute` + `skill` permissions, **no `edit`** — a focused reviewer persona that can read files, run the test suite, and use skills, but cannot modify source.
