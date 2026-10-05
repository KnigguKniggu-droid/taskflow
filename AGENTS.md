# TaskFlow — Project Context for IBM Bob Sessions

## Purpose

TaskFlow is a small JSON REST API for tracking tasks and the people they are assigned to.
It is a Flask application backed by SQLite with no ORM and no runtime dependencies beyond Flask itself.

---

## Project Layout

```
taskflow-bob/
├── app/
│   ├── __init__.py   — application factory (create_app)
│   ├── db.py         — SQLite connection handling and schema creation
│   ├── services.py   — validation and business logic; no HTTP knowledge
│   └── routes.py     — Flask Blueprint; all HTTP routes and error handlers
├── tests/
│   └── test_tasks.py — unittest-based integration test suite
├── run.py            — development server entry point
├── requirements.txt  — single dependency: Flask==3.1.3
└── AGENTS.md         — this file
```

---

## Architecture

```
HTTP Request
    │
    ▼
routes.py  (Flask Blueprint)
    │  calls service functions; catches ValidationError / NotFoundError
    ▼
services.py  (business logic, HTTP-agnostic)
    │  calls get_db(); raises ValidationError (→ 400) or NotFoundError (→ 404)
    ▼
db.py  (SQLite via stdlib sqlite3)
    │  stores connection in Flask's g object; row_factory = sqlite3.Row
    ▼
instance/taskflow.sqlite  (created on first start)
```

### Key design points

- `create_app(test_config=None)` in `app/__init__.py` is a Flask application factory.
  Passing a `test_config` dict lets tests inject a temporary database path without
  touching the environment.
- `get_db()` opens (and caches in `g`) one SQLite connection per application context.
  `close_db()` is registered with `app.teardown_appcontext` so the connection is always
  closed at the end of the request.
- `services.py` has no Flask imports. Business logic is isolated there; routes only
  translate HTTP in/out.
- An `IdConverter` (subclass of Werkzeug's `IntegerConverter`) is registered as the
  `id` URL converter to ensure route `<id:task_id>` parameters accept ASCII digits only.
- Request bodies are capped at **64 KiB** (`MAX_CONTENT_LENGTH`). Any body that cannot
  be parsed as a JSON object returns `400`.

---

## Setup

Requires **Python 3.10 or newer**.

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Running

```bash
python run.py
```

The server listens on `http://127.0.0.1:5000` by default.
Override with environment variables:

| Variable            | Default          | Effect                            |
|---------------------|------------------|-----------------------------------|
| `HOST`              | `127.0.0.1`      | Bind address                      |
| `PORT`              | `5000`           | Bind port                         |
| `TASKFLOW_DATABASE` | `instance/taskflow.sqlite` | Path to the SQLite file  |

The SQLite database and its parent directory are created automatically on first start.

---

## API

All request and response bodies are JSON. Errors are returned as `{"error": "<message>"}`.

| Method | Path                     | Description                                              |
|--------|--------------------------|----------------------------------------------------------|
| POST   | `/users`                 | Create a user. Body: `{"name": "..."}`. Returns 201.     |
| POST   | `/tasks`                 | Create a task (fields below). Returns 201.               |
| GET    | `/tasks`                 | List tasks. Optional filters: `?assignee_id=<id>` and/or `?tag=<tag>`. |
| GET    | `/tasks/<id>`            | Get one task; 404 if not found.                          |
| POST   | `/tasks/<id>/complete`   | Mark a task completed; 404 if not found.                 |
| GET    | `/tasks/overdue`         | List open tasks whose due date is before today.          |

### Task fields

| Field         | Type                                    | Notes                                                         |
|---------------|-----------------------------------------|---------------------------------------------------------------|
| `title`       | string                                  | Required; up to 200 characters.                               |
| `description` | string                                  | Optional; up to 2000 characters.                              |
| `tags`        | list of strings or comma-separated string | Optional; lowercase, de-duplicated; max 10; each tag: `[a-z0-9][a-z0-9_-]{0,31}`. |
| `due_date`    | string                                  | Optional; `YYYY-MM-DD`.                                       |
| `assignee_id` | integer                                 | Optional; must match an existing user id.                     |

List endpoints return `{"tasks": [...]}` ordered by id; `/tasks/overdue` orders by due date then id.

---

## Testing

```bash
python -m unittest tests.test_tasks -v
```

Each test case creates a temporary SQLite file in `setUp` and removes it in `tearDown`,
so every test is fully isolated with no shared state.

---

## Coding Conventions

### Validation (`services.py`)

- All incoming data is validated in `services.py`, never in routes.
- `_reject_unknown_fields(data, allowed)` rejects any key not in the declared field set.
- `_required_text` / `_optional_text` enforce type, strip whitespace, and check length.
- `_checked_text` additionally ensures the value can be encoded as UTF-8 (guards against
  lone surrogate escapes that SQLite cannot store).
- IDs from JSON bodies go through `parse_id(value, field)` (checks int, not bool, positive,
  within SQLite INTEGER range). IDs from query strings go through `parse_id_param`.
- Tag query-string values go through `parse_tag_param`: strips whitespace, lowercases, validates
  against `TAG_PATTERN`, and returns `None` for blank input (treated as no filter).
- Tags: `normalize_tags(raw)` accepts a list or comma-separated string, strips and lowercases
  each item, validates against `TAG_PATTERN`, de-duplicates, and enforces the 10-tag limit.
  The result is stored in SQLite as a comma-joined string and split back on read.
- Due dates: validated with a regex then `date.fromisoformat` to catch impossible dates.

### Error responses

- `ValidationError` → HTTP 400, `{"error": "<message>"}`.
- `NotFoundError` → HTTP 404, `{"error": "<message>"}`.
- All `werkzeug.exceptions.HTTPException` (e.g. 405, 413) are caught by a Blueprint error
  handler and returned as JSON instead of HTML, preserving the original status code and
  headers (including `Allow` on 405).

### SQL style

- Raw SQL strings; no ORM.
- A shared `SELECT_TASKS` constant holds the column list to keep `SELECT` and `INSERT`
  in sync.
- All queries use `?` placeholders; no string interpolation.
- Writes run inside a `with db:` context manager so SQLite's implicit transaction commits
  on success or rolls back on exception.
- Foreign-key enforcement is enabled per-connection via `PRAGMA foreign_keys = ON`.

### Tests

- Plain `unittest.TestCase`; no third-party test framework.
- Helper methods (`create_user`, `create_task`, `overdue_ids`) keep individual test methods
  short and readable.
- Assertions include the response JSON as the failure message for easier debugging.

---

## Feature Status

| Feature                               | Status          |
|---------------------------------------|-----------------|
| Create / get / list tasks             | Implemented     |
| Complete a task                       | Implemented     |
| Overdue task listing                  | Implemented     |
| Filter tasks by assignee (`?assignee_id=`) | Implemented |
| Create users                          | Implemented     |
| Filter tasks by tag (`?tag=<tag>`)    | Implemented     |
