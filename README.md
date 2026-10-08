# TaskFlow

## Quick start — for judges and new visitors

**What it is:** TaskFlow is a team task-board: a JSON REST API backed by SQLite with a
single-page web UI.  Users can create tasks, assign them, track them through an
open → in_progress → blocked → completed lifecycle, tag and filter them, and view
a per-task activity history.

**Live demo:** <https://kltamu.pythonanywhere.com>

**Run it locally:**

```bash
git clone https://github.com/KnigguKniggu-droid/taskflow.git
cd taskflow
python -m venv .venv
# Windows: .venv\Scripts\activate  |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py          # → http://127.0.0.1:5000
```

**Run the tests:**

```bash
python -m unittest tests.test_tasks -v
```

Each test uses a temporary database; there is no shared state.

**IBM Bob session records:** [`bob_sessions/README.md`](bob_sessions/README.md)
contains the full session index — prompts, Bob's answers, task IDs, durations,
and commit references for all 31 tasks across three Bob sessions.

---

TaskFlow is a small JSON API for tracking tasks and the people they are assigned to.
It is a Flask application backed by SQLite, with no other runtime dependencies.

## Requirements

- Python 3.10 or newer

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Running

```bash
python run.py
```

The server listens on <http://127.0.0.1:5000>; set `PORT` (and `HOST`) to change that.
The SQLite database is created on first start at `instance/taskflow.sqlite`; set
`TASKFLOW_DATABASE` to use a different file.

## API

Request and response bodies are JSON. Unknown fields in a request body are rejected, and bodies
larger than 64 KiB are refused with `413`. Errors come back as `{"error": "<message>"}` with a
4xx status code.

| Method | Path | Description |
|---|---|---|
| `POST` | `/users` | Create a user. Body: `{"name": "..."}`. Returns `201`. |
| `POST` | `/tasks` | Create a task (fields below). Returns `201`. |
| `GET` | `/tasks` | List tasks. Optional filters: `?assignee_id=<id>` and/or `?tag=<tag>`. |
| `GET` | `/tasks/<id>` | Get one task; `404` if it does not exist. |
| `POST` | `/tasks/<id>/complete` | Mark a task as completed; `404` if it does not exist. |
| `GET` | `/tasks/overdue` | List open tasks whose due date is before today. |

### Task fields

| Field | Type | Notes |
|---|---|---|
| `title` | string | Required, up to 200 characters. |
| `description` | string | Optional, up to 2000 characters. |
| `tags` | list of strings, or one comma-separated string | Optional. Stored lowercase and de-duplicated. A tag starts with a letter or digit and uses only `a-z`, `0-9`, `-` or `_` (up to 32 characters); at most 10 tags. |
| `due_date` | string | Optional, `YYYY-MM-DD`. |
| `assignee_id` | integer | Optional; the id of an existing user. |

A task is returned like this:

```json
{
  "id": 1,
  "title": "Prepare release notes",
  "description": "",
  "tags": ["backend", "docs"],
  "due_date": "2026-10-10",
  "assignee_id": 1,
  "completed": false,
  "created_at": "2026-10-03T18:30:00+00:00"
}
```

List endpoints return `{"tasks": [...]}`, ordered by id (`/tasks/overdue` is ordered by due date, then id).

### Filtering tasks

`GET /tasks` accepts two independent, combinable query parameters:

| Parameter | Behaviour |
|---|---|
| `?assignee_id=<id>` | Return only tasks assigned to that user id. |
| `?tag=<tag>` | Return only tasks that carry that exact tag. |

**Tag filter details:**

- Matching is exact — `?tag=back` does **not** match a task tagged `backend`.
- The value is normalised to lowercase before matching, so `?tag=Backend` and
  `?tag=backend` return the same results — uppercase input is accepted and treated
  as its lowercase equivalent.
- A blank value (`?tag=` or `?tag=   `) is treated as "no filter" and returns all tasks.
- A value that is invalid after lowercasing (e.g. spaces, `@`, or other characters
  outside `[a-z0-9_-]`, or longer than 32 characters) returns `400 {"error": "..."}`.

Both parameters may be combined: `?tag=backend&assignee_id=1` returns tasks that have
the tag `backend` **and** are assigned to user 1.

### Examples

```bash
# Create a user
curl -X POST http://127.0.0.1:5000/users \
  -H "Content-Type: application/json" -d '{"name": "Ada"}'

# Create a task with tags and a due date
curl -X POST http://127.0.0.1:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Prepare release notes", "tags": ["backend", "docs"], "due_date": "2026-10-10", "assignee_id": 1}'

# Filter by assignee
curl "http://127.0.0.1:5000/tasks?assignee_id=1"

# Filter by tag
curl "http://127.0.0.1:5000/tasks?tag=backend"

# Combined filter: tag + assignee
curl "http://127.0.0.1:5000/tasks?tag=backend&assignee_id=1"

# Mark complete
curl -X POST http://127.0.0.1:5000/tasks/1/complete

# List overdue tasks
curl http://127.0.0.1:5000/tasks/overdue
```

Windows PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/users `
  -ContentType "application/json" -Body '{"name": "Ada"}'
Invoke-RestMethod "http://127.0.0.1:5000/tasks?tag=backend&assignee_id=1"
Invoke-RestMethod http://127.0.0.1:5000/tasks/overdue
```

## Testing

```bash
python -m unittest tests.test_tasks -v
```

Each test runs against its own temporary SQLite database; there is no shared state between tests.
The suite covers task creation, listing, overdue detection, tag filtering (exact match,
combined filters, edge cases), schema migration, and existing-database upgrade behaviour.

A smoke test script (`smoke_test.py`) exercises the full API against a running server:

```bash
# Against the local dev server
python smoke_test.py

# Against a deployed instance
python smoke_test.py --base-url https://<username>.pythonanywhere.com
```

Exit code is 0 if all checks pass, 1 otherwise.

> **Note:** the smoke test creates a user and several tasks that remain in the target
> database after the run (there is no delete endpoint).  Run it against a local dev
> server for routine checks; running it against a live instance is fine for a one-time
> deployment verification but will leave test records in the production database.

## Demo data

`scripts/seed_demo.py` is an admin-only command-line script that loads a
deterministic, realistic dataset into any running TaskFlow instance through its
public API. It creates four users and thirteen tasks that cover every status
(open, in_progress, blocked, completed), some overdue items, and a mix of tags
and assignees — so a fresh deployment is demo-ready in seconds.

**Prerequisites:** Python 3.10+ (no extra packages needed; the script uses the
stdlib `urllib` module only).

### Seeding the local dev server

```bash
# 1. Start the server in one terminal
python run.py

# 2. In another terminal, run the seed script
python scripts/seed_demo.py
```

### Seeding a deployed PythonAnywhere instance

```bash
python scripts/seed_demo.py --base-url https://<username>.pythonanywhere.com
```

### Resetting the database before a demo run

The seed script does **not** check for pre-existing data. Run it against an
empty database to avoid duplicate entries.

**Locally:**

```bash
# Stop the server, then delete the SQLite file and restart
rm instance/taskflow.sqlite
python run.py
python scripts/seed_demo.py
```

**On PythonAnywhere** (the database lives in persistent storage outside the
source tree):

1. Open a **Bash console** on PythonAnywhere.
2. Delete the SQLite file:

   ```bash
   rm ~/taskflow-data/taskflow.sqlite
   ```

3. **Reload the web app** in the PythonAnywhere Web tab so the app recreates
   the schema on the next request.

4. Seed the demo data:

   ```bash
   python ~/taskflow/scripts/seed_demo.py \
     --base-url https://<username>.pythonanywhere.com
   ```

> **Caution:** deleting the SQLite file permanently destroys all stored data.
> Only do this when you intentionally want a clean slate.

---

## Deploying to PythonAnywhere (free tier)

PythonAnywhere provides persistent disk and WSGI hosting configured through its web UI —
no long-running processes needed.

### First deploy

**1. Open a Bash console on PythonAnywhere and clone the repo:**

```bash
git clone https://github.com/KnigguKniggu-droid/taskflow.git ~/taskflow
```

**2. Create a virtualenv and install dependencies:**

```bash
cd ~/taskflow
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Create the data directory** (outside the source tree so it survives updates):

```bash
mkdir -p ~/taskflow-data
```

**4. Configure the web app in the PythonAnywhere dashboard:**

- Go to **Web** → **Add a new web app** → **Manual configuration** → Python 3.11.
- Set **Source code** to `/home/<username>/taskflow`.
- Set **Virtualenv** to `/home/<username>/taskflow/.venv`.

**5. Configure the WSGI file:**

Click **WSGI configuration file** in the Web tab to open the editor.
Replace the entire contents with:

```python
import sys
import os

# Add the source tree to the Python path
sys.path.insert(0, '/home/<username>/taskflow')

# Point the database at persistent storage outside the source tree.
# Note: free-tier PythonAnywhere Web tabs do not have an
# "Environment variables" section; set the variable here instead.
os.environ.setdefault(
    'TASKFLOW_DATABASE',
    '/home/<username>/taskflow-data/taskflow.sqlite',
)

from wsgi import application  # noqa: E402  (must come after sys.path modification)
```

Replace `<username>` with your PythonAnywhere username.

**6. Click Reload** in the Web tab.

**7. Verify** with the smoke test:

```bash
python ~/taskflow/smoke_test.py --base-url https://<username>.pythonanywhere.com
```

### Updating after a git pull

```bash
cd ~/taskflow
git pull
# Reload the web app in the PythonAnywhere dashboard (Web → Reload)
```

No manual migration is needed.  The app upgrades existing databases in place on
startup: it adds any new columns and back-fills data so that existing records
remain valid.  **Do not delete the SQLite file** after a pull — that would
destroy all stored data.

### Health check

`GET /health` returns `{"status": "ok"}` with HTTP 200.  Use it to verify the process is alive:

```bash
curl https://<username>.pythonanywhere.com/health
```

## Project layout

```text
app/
  __init__.py   application factory
  db.py         SQLite connection handling and schema
  services.py   validation and business logic
  routes.py     HTTP routes and JSON error responses
tests/
  test_tasks.py
run.py          development server entry point
.bob/           IBM Bob project tooling (skills, modes, commands)
bob_sessions/   transcripts of the IBM Bob session (see below)
```

## Project provenance

TaskFlow was created during the Building with IBM Bob hackathon as the unfamiliar codebase for
Theme 1 (Explore, Fix, and Build). The starter, everything up to the `pre-bob-baseline` tag, was
generated with Claude Code (Anthropic). It deliberately contained one seeded defect and an
unimplemented tag-filter feature.

All code changes after that tag were made in IBM Bob, first in Bob Shell and then in Bob IDE. Bob
explored the code, diagnosed and fixed the defect (including databases created before the fix),
built the tag filter, wrote the regression tests, created the project tooling under `.bob/` (skills,
a command, a custom reviewer mode and a hook), reviewed the change set with subagents, the custom
mode and the IDE's built-in `/review`, and fixed what those reviews found. In a later IDE session it
built the web UI, the task lifecycle with its activity history and database upgrade path, the
release setup (WSGI entry point, health endpoint, smoke test, CI) and the deployment guide, and ran
an adversarial release review. It also wrote and updated this documentation. Every commit Bob made
says so in its message ("Generated-by: IBM Bob").

At the participant's direction, Claude Code operated the sessions: Bob Shell through its Agent
Client Protocol interface, and Bob IDE through Windows UI automation. It wrote the prompts, handled
Bob's approval requests, answered Bob's design questions, and checked each stage independently
(browser, mutation, upgrade and concurrency checks). Its follow-up prompts reported observed
failures, not fixes. Claude Code also deployed the app to PythonAnywhere following Bob's guide, and
wrote this provenance section, the [`bob_sessions/`](bob_sessions/README.md) records (prompts,
Bob's answers, Bob task ids) and the pitch deck in `docs/`.
