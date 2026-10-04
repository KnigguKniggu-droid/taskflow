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

Request and response bodies are JSON. Errors come back as `{"error": "<message>"}` with a
4xx status code.

| Method | Path | Description |
|---|---|---|
| `POST` | `/users` | Create a user. Body: `{"name": "..."}`. Returns `201`. |
| `POST` | `/tasks` | Create a task (fields below). Returns `201`. |
| `GET` | `/tasks` | List tasks. Optional filter: `?assignee_id=<id>`. |
| `GET` | `/tasks/<id>` | Get one task; `404` if it does not exist. |
| `POST` | `/tasks/<id>/complete` | Mark a task as completed; `404` if it does not exist. |
| `GET` | `/tasks/overdue` | List open tasks whose due date is before today. |

### Task fields

| Field | Type | Notes |
|---|---|---|
| `title` | string | Required, up to 200 characters. |
| `description` | string | Optional, up to 2000 characters. |
| `tags` | list of strings, or one comma-separated string | Optional. Stored lowercase and de-duplicated. A tag uses letters, digits, `-` or `_` (up to 32 characters); at most 10 tags. |
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

List endpoints return `{"tasks": [...]}`, ordered by id (`/tasks/overdue` is ordered by due date).

### Examples

```bash
curl -X POST http://127.0.0.1:5000/users -H "Content-Type: application/json" -d '{"name": "Ada"}'
curl -X POST http://127.0.0.1:5000/tasks -H "Content-Type: application/json" \
  -d '{"title": "Prepare release notes", "tags": ["backend", "docs"], "due_date": "2026-10-10", "assignee_id": 1}'
curl "http://127.0.0.1:5000/tasks?assignee_id=1"
curl -X POST http://127.0.0.1:5000/tasks/1/complete
curl http://127.0.0.1:5000/tasks/overdue
```

Windows PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/users -ContentType "application/json" -Body '{"name": "Ada"}'
Invoke-RestMethod http://127.0.0.1:5000/tasks/overdue
```

## Testing

```bash
python -m unittest tests.test_tasks -v
```

Each test runs against its own temporary database.

## Feature status

Filtering tasks by tag (`GET /tasks?tag=<tag>`) is planned but not implemented yet;
`GET /tasks` currently ignores a `tag` parameter.

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
```
