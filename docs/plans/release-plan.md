# TaskFlow — PythonAnywhere Release Plan

## Context

The earlier `deploy-demo-plan.md` targeted Render (ephemeral disk, long-running process).
PythonAnywhere free tier differs in two key ways:

1. **Persistent disk** — files in `~/` survive across reloads and account restarts, so SQLite
   data is durable (no need for ephemeral-reset mitigations).
2. **WSGI hosting** — the web process is managed by PythonAnywhere; there is no `Procfile` or
   `gunicorn` invocation to write.  The platform imports a WSGI file we provide.

### What carries over from the Render plan

- `wsgi.py` — still needed; PythonAnywhere imports it directly.
- Environment-variable DB path (`TASKFLOW_DATABASE`) — still the right mechanism; the path
  changes to a PythonAnywhere home-directory path.
- `requirements.txt` — no change; Flask is the only runtime dependency.
- Smoke test concept — reused as `smoke_test.py` (stdlib only, no bash dependency).

### What is dropped

- `render.yaml`, `runtime.txt`, `Procfile`, Gunicorn dependency — not needed.

---

## Deliverables

| # | File | Purpose |
|---|---|---|
| 1 | `wsgi.py` | WSGI entry point; reads `TASKFLOW_DATABASE` from env or falls back to `~/taskflow-data/taskflow.sqlite`; `DEBUG=False` |
| 2 | `GET /health` in `app/routes.py` | Lightweight health endpoint: `{"status": "ok"}` |
| 3 | `smoke_test.py` | Stdlib-only smoke test; accepts `--base-url`; exercises all main API flows |
| 4 | `.github/workflows/ci.yml` | GitHub Actions: install deps, run full test suite, run regression check |
| 5 | `README.md` updated | PythonAnywhere deploy steps, update procedure |

---

## Implementation Steps

### Step 1 — Health endpoint + `wsgi.py`

**Health endpoint** (`GET /health`):
- Returns `200 {"status": "ok"}` — no DB query, so it passes even if the database is not yet
  initialised.
- Used by the smoke test's first probe; lets a load balancer or monitor verify the process is
  alive without touching application state.

**`wsgi.py`**:
- Calls `create_app()` with no arguments (production defaults).
- Exposes `application` (WSGI standard name) so PythonAnywhere's WSGI runner can import it.
- No hardcoded secrets; DB path comes from `TASKFLOW_DATABASE` env var or the default.
- `DEBUG` is never `True` in this file.

**PythonAnywhere WSGI file** (not committed — configured through the web UI):
```python
import sys, os
sys.path.insert(0, '/home/<username>/taskflow')
os.environ.setdefault('TASKFLOW_DATABASE',
                      '/home/<username>/taskflow-data/taskflow.sqlite')
from wsgi import application
```

### Step 2 — Smoke test (`smoke_test.py`)

- Pure Python standard library (`urllib.request`, `json`).
- Accepts `BASE_URL` as a CLI argument (`--base-url`) or environment variable; defaults to
  `http://127.0.0.1:5000`.
- Checks:
  1. `GET /health` → 200
  2. `POST /users` → 201, capture `user_id`
  3. `POST /tasks` (with `due_date` yesterday, `assignee_id`) → 201, capture `task_id`
  4. `GET /tasks` → 200, `tasks` key present
  5. `GET /tasks?assignee_id=<id>` → 200, result non-empty
  6. `GET /tasks/overdue` → 200, `task_id` in results
  7. `GET /tasks/<task_id>` → 200, correct id
  8. `PATCH /tasks/<task_id>` → 200
  9. `POST /tasks/<task_id>/complete` → 200
  10. `GET /tasks/stats` → 200, `total >= 1`
  11. `GET /tasks/<nonexistent>` → 404
- Exits with code 0 if all pass, 1 otherwise.

### Step 3 — GitHub Actions CI

Trigger: `push` and `pull_request` on all branches.

Jobs:
1. **test** — Ubuntu latest, Python 3.11:
   - `pip install -r requirements.txt`
   - `python -m unittest tests.test_tasks -v`
   - Run regression check script (`.bob/skills/taskflow-regression-check/regression_check.py`)

No secrets required; the regression check uses an in-memory test client.

### Step 4 — README deployment documentation

Add a **Deploying to PythonAnywhere** section covering:
1. Clone the repo in a Bash console.
2. Create a virtualenv and install requirements.
3. Set the `TASKFLOW_DATABASE` environment variable in the web app's settings.
4. Paste the WSGI file contents into PythonAnywhere's WSGI configuration editor.
5. Reload the web app.
6. How to update after a `git pull`.

---

## Commit Strategy

| Commit | Contents |
|---|---|
| `feat: add health endpoint and wsgi.py for PythonAnywhere` | `app/routes.py` (health), `wsgi.py`, `docs/plans/release-plan.md` |
| `feat: add stdlib smoke test` | `smoke_test.py` |
| `feat: add GitHub Actions CI and PythonAnywhere deployment docs` | `.github/workflows/ci.yml`, `README.md` |

Each commit runs the full test suite and regression check before being made.

---

## Production Safety Checklist

- [ ] `DEBUG=False` in `wsgi.py` (Flask default when not set; confirmed in factory)
- [ ] No secrets in committed files
- [ ] `TASKFLOW_DATABASE` path is outside the source tree on the server
- [ ] `MAX_CONTENT_LENGTH=64 KiB` already enforced by `create_app()`
- [ ] No long-running background processes (PythonAnywhere free tier does not allow them)
- [ ] Health endpoint does not expose internal state
