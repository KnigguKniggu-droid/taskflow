# TaskFlow Public Demo Deployment Plan

## Top-Level Overview

**Goal:** Deploy the TaskFlow Flask app to a free, publicly reachable hosting tier so that
judges can call the live API.  No existing code logic changes are required.  The only
repository additions are small configuration files (WSGI entry point, `Procfile`/platform
manifest, `requirements.txt` amendment for the WSGI server, and a `runtime.txt`).

**Scope:** Deployment infrastructure only — no feature changes, no schema migrations.

**Not in scope:** TLS termination (handled by the hosting platform), authentication, CI/CD
pipeline, persistent data across deploys.

---

## Platform Comparison

### Option A — Render (render.com)

| Factor | Detail |
|---|---|
| Free tier | 750 instance-hours/month; spins down after 15 min of inactivity |
| Runtime | Python 3.x managed buildpack; auto-detects `requirements.txt` |
| Start command | Configured in `render.yaml` or dashboard; Gunicorn works out-of-the-box |
| Port | Platform injects `PORT` env var — matches what `run.py` already reads |
| Disk | **Ephemeral.** The SQLite file is lost on every deploy and on spin-down/restart |
| Config files needed | `render.yaml`, `wsgi.py`, `Procfile` (optional if using render.yaml) |
| Ease | Dashboard + YAML; zero Docker knowledge needed |
| Cold start | ~30 s after 15 min idle |

### Option B — Railway (railway.app)

| Factor | Detail |
|---|---|
| Free tier | $5 of credit/month (enough for low-traffic demo); no sleep on inactivity |
| Runtime | Nixpacks auto-detects Python; or custom Dockerfile |
| Start command | Set in dashboard or `railway.toml`; Gunicorn works |
| Port | Platform injects `PORT` — already read by `run.py` |
| Disk | **Ephemeral** by default (SQLite resets on deploy); persistent Volume available but counted against credit |
| Config files needed | `railway.toml` (optional), `Procfile`, `wsgi.py` |
| Ease | `railway up` CLI or GitHub push; slightly faster iteration than Render |
| Cold start | None — stays warm while credit lasts |

### Option C — Fly.io (fly.io)

| Factor | Detail |
|---|---|
| Free tier | 3 shared-CPU VMs free forever; no auto-sleep |
| Runtime | Docker-based; must write a `Dockerfile` or use `flyctl launch` buildpack |
| Start command | Defined in `fly.toml` CMD or Dockerfile |
| Port | `fly.toml` internal_port maps to 443 publicly; app must bind `0.0.0.0` |
| Disk | Ephemeral by default; persistent Volumes free up to 3 GB |
| Config files needed | `fly.toml`, `Dockerfile` (or equivalent), `wsgi.py` |
| Ease | Most steps, requires `flyctl` CLI and Docker knowledge |
| Cold start | None on free tier (VM stays up) |

---

## Recommendation — **Render**

Render is the best fit for a short-lived judge demo:

- Zero Docker knowledge required.
- A single `render.yaml` file makes the whole setup reproducible from git.
- `PORT` is already read by `run.py`, so host/port binding requires no code changes.
- The free spin-down is acceptable for a demo (cold start is ~30 s; judges can simply
  send one warm-up request first).
- The SQLite ephemerality is the main trade-off, but for a stateless demo API it is
  acceptable — the schema is recreated automatically on every cold start, and judges
  populate it themselves via the API.

---

## SQLite Ephemerality — What Happens on Restarts

On Render's free tier the container filesystem is ephemeral:

- **On deploy:** old container is replaced; the SQLite file is gone.
- **On spin-down / wake-up:** same container resumes (file survives the idle period but
  NOT a new deploy).
- **On any deploy:** `init_db()` in `app/db.py` runs automatically inside
  `create_app()`, recreating the `users` and `tasks` tables if they do not exist.
  The database starts empty but structurally correct.

**Implication for judges:** Any data they POST will survive the demo session as long as no
new deploy is triggered.  The API is fully functional from a cold start; the smoke test
populates seed data.

---

## Sub-Tasks

---

### Sub-Task 1 — Add Gunicorn to requirements.txt

**Intent:** The Flask dev server (`run.py`) is not safe for production.  Gunicorn is the
standard production WSGI server for Python web apps.  It must be listed as a dependency so
the platform installs it during build.

**Expected Outcomes:**
- `requirements.txt` contains `gunicorn` (pinned to a specific version, e.g. `gunicorn==23.0.0`).
- `pip install -r requirements.txt` installs both Flask and Gunicorn.

**Todo List:**
1. Append `gunicorn==23.0.0` to `requirements.txt`.

**Relevant Context:**
- [`requirements.txt`](requirements.txt) — currently only `Flask==3.1.3`.

**Status:** [ ] pending

---

### Sub-Task 2 — Add wsgi.py entry point

**Intent:** Gunicorn needs a Python module that exposes the WSGI callable.  The standard
convention is `wsgi.py` at the project root exporting an `application` (or `app`) object.
The app factory `create_app()` in [`app/__init__.py`](app/__init__.py) is called here with
no arguments so it uses the production configuration.

**Expected Outcomes:**
- `wsgi.py` exists at the project root.
- `gunicorn wsgi:app` resolves and imports the Flask application without error.

**Todo List:**
1. Create `wsgi.py` that imports `create_app` from `app` and assigns `app = create_app()`.

**Relevant Context:**
- [`app/__init__.py`](app/__init__.py) — `create_app(test_config=None)` factory.
- `gunicorn wsgi:app --bind 0.0.0.0:$PORT` is the start command used in Sub-Task 3.

**Status:** [ ] pending

---

### Sub-Task 3 — Add render.yaml

**Intent:** A `render.yaml` Blueprint file makes the Render deployment fully reproducible
from the git repository.  It declares the service type, build command, start command, and
environment variables.  No dashboard clicking is required once the file is present.

**Expected Outcomes:**
- `render.yaml` exists at the project root.
- A Render account can connect the repository and create the web service with one click.
- The service starts Gunicorn binding `0.0.0.0:$PORT`.
- `TASKFLOW_DATABASE` is set to `/opt/render/project/src/instance/taskflow.sqlite`
  (a writable path within the ephemeral container) so SQLite does not try to write to
  a read-only directory.
- `PYTHON_VERSION` is set to `3.11` (or whichever minor version matches the dev environment).

**Todo List:**
1. Create `render.yaml` with:
   - `services` entry of type `web`, env `python`.
   - `buildCommand: pip install -r requirements.txt`.
   - `startCommand: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`.
   - `envVars` block: `TASKFLOW_DATABASE` and `PYTHON_VERSION`.
   - `plan: free`.

**Relevant Context:**
- Render Blueprint schema: https://render.com/docs/blueprint-spec
- [`app/__init__.py`](app/__init__.py) — `TASKFLOW_DATABASE` env var controls the DB path.
- [`app/db.py`](app/db.py) — `os.makedirs(..., exist_ok=True)` creates the directory
  automatically, so the path just needs to be writable.

**Status:** [ ] pending

---

### Sub-Task 4 — Add runtime.txt

**Intent:** Explicitly pin the Python runtime version so Render's buildpack does not
default to an unexpected version.  This avoids subtle incompatibilities between Python
3.10 (minimum required per AGENTS.md) and whatever the platform defaults to.

**Expected Outcomes:**
- `runtime.txt` exists at the project root containing exactly `python-3.11.x`
  (where x is a specific patch version available on Render).

**Todo List:**
1. Create `runtime.txt` with content `python-3.11.9` (latest 3.11 patch available on Render).

**Relevant Context:**
- AGENTS.md states Python 3.10 or newer is required.
- Render recognises `runtime.txt` in the Python buildpack.

**Status:** [ ] pending

---

### Sub-Task 5 — Smoke Test Script

**Intent:** Provide a self-contained shell/curl smoke test that judges (or the developer)
can run immediately after deploy to verify every route is reachable and returns the
expected status codes.  No test framework is needed — plain `curl` calls.

**Expected Outcomes:**
- `smoke_test.sh` exists at the project root.
- Running `BASE_URL=https://<your-app>.onrender.com bash smoke_test.sh` exercises all
  six routes and prints PASS/FAIL for each.

**Todo List:**
1. Create `smoke_test.sh` that:
   a. Sets `BASE_URL` from the first argument or the `BASE_URL` env var.
   b. POSTs to `/users` → expects HTTP 201, captures `user_id`.
   c. POSTs to `/tasks` with `title`, `due_date` (yesterday), `assignee_id` → expects 201, captures `task_id`.
   d. GETs `/tasks` → expects 200, body contains `"tasks"`.
   e. GETs `/tasks/overdue` → expects 200, body contains `"tasks"`.
   f. GETs `/tasks/$task_id` → expects 200, body contains `"id"`.
   g. POSTs to `/tasks/$task_id/complete` → expects 200.
   h. Prints a final summary of PASS/FAIL counts.
2. Make the script executable (`chmod +x smoke_test.sh` in the readme instructions;
   no file mode changes tracked in git needed on Windows).

**Relevant Context:**
- [`app/routes.py`](app/routes.py) — all six routes and their expected status codes.
- Due date set to yesterday ensures the task appears in `/tasks/overdue`.

**Status:** [ ] pending

---

## Main Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| SQLite file lost on every deploy | Certain | Document clearly; judges seed data via smoke test after each deploy |
| 30-second cold start on Render free tier | High | Advise judges to send a warm-up GET /tasks request first |
| Single Gunicorn worker creates request queue under load | Low for demo | Acceptable; increase `--workers` if needed |
| Render free tier removed or hours exhausted | Low | Keep Railway as fallback (Sub-Task 3 notes cover its differences) |
| Port binding to 127.0.0.1 instead of 0.0.0.0 | Would cause 502 | `render.yaml` start command explicitly passes `--bind 0.0.0.0:$PORT` |
| Python version mismatch on buildpack | Low | `runtime.txt` pins the version |
| `instance/` directory not writable on Render | Possible | `TASKFLOW_DATABASE` set to an explicit writable path in `render.yaml` |

---

## Files Added by This Plan

| File | Purpose |
|---|---|
| `requirements.txt` | Amended to add `gunicorn==23.0.0` |
| `wsgi.py` | WSGI entry point for Gunicorn |
| `render.yaml` | Render Blueprint — one-click reproducible deploy |
| `runtime.txt` | Pins Python 3.11.9 on the Render buildpack |
| `smoke_test.sh` | Curl-based smoke test for all six routes |

No existing source files are modified.

---

## Environment Variables (Production)

| Variable | Value on Render | Purpose |
|---|---|---|
| `PORT` | Injected by Render automatically | Gunicorn bind port |
| `TASKFLOW_DATABASE` | `/opt/render/project/src/instance/taskflow.sqlite` | Writable SQLite path inside container |
| `PYTHON_VERSION` | `3.11` | Buildpack Python selection |

`HOST` is not set — Gunicorn's `--bind 0.0.0.0:$PORT` argument makes it irrelevant;
`run.py` is not used in production.
