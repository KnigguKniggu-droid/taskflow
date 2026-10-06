# TaskFlow

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
mode and the IDE's built-in `/review`, fixed what those reviews found, and updated this
documentation. Every commit Bob made says so in its message ("Generated-by: IBM Bob").

At the participant's direction, Claude Code operated both sessions: Bob Shell through its Agent
Client Protocol interface, and Bob IDE through Windows UI automation. It wrote the prompts, handled
Bob's approval requests, and checked each stage independently. Its follow-up prompts reported
observed failures, not fixes. Claude Code also wrote this provenance section and the
[`bob_sessions/`](bob_sessions/README.md) records, which hold the prompts, Bob's answers and the
Bob task ids.
