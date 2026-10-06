# For a three-minute demo audience of developers who have never seen this code: explain in plain language what was wrong with the overdue task list before the fixes on this branch, why SQL's handling of NULL caused it, and how the current code keeps both new and existing databases correct. Then explain in two sentences why the tag filter wraps the stored tags in commas and escapes LIKE wildcards. Keep the whole answer under 200 words and cite the files involved.

---

**Status:** active  **Date:** 2026-10-06

---

### 👤 User

For a three-minute demo audience of developers who have never seen this code: explain in plain language what was wrong with the overdue task list before the fixes on this branch, why SQL's handling of NULL caused it, and how the current code keeps both new and existing databases correct. Then explain in two sentences why the tag filter wraps the stored tags in commas and escapes LIKE wildcards. Keep the whole answer under 200 words and cite the files involved.

---

### 🤖 Assistant

> 🔧 called: spawn_subagent



> 🔧 **spawn_subagent** — explore

### 🤖 Assistant

Here's the plain-language demo explanation, under 200 words:

---

## What broke, why, and how it's fixed

**The overdue bug** ([`app/services.py`](app/services.py), [`app/db.py`](app/db.py)): The original schema declared `completed INTEGER` with no default. When a task was inserted without that column, SQLite stored `NULL`. The overdue query filters with `WHERE completed = 0` — but in SQL, `NULL = 0` evaluates to `NULL`, not `TRUE` or `FALSE`. It's *unknown*, not falsy. So every open task was silently dropped from `GET /tasks/overdue`.

**Two-pronged fix**: The schema now declares [`completed INTEGER NOT NULL DEFAULT 0`](app/db.py:13). But `CREATE TABLE IF NOT EXISTS` is a no-op on existing databases, so old rows stay broken. At startup, [`init_db()`](app/db.py:62) runs `UPDATE tasks SET completed = 0 WHERE completed IS NULL` to backfill legacy rows. New inserts also supply [`completed = 0`](app/services.py:63) explicitly, so old-schema databases are safe before migration runs.

**The tag filter comma-wrap** ([`app/services.py`](app/services.py:101)): Tags are stored as `"backend,api"`. Without wrapping, `LIKE '%api%'` would falsely match a tag called `"legacy-api-v2"`. Wrapping both sides with commas forces a full-token match. Escaping `_` and `%` prevents those characters — legal in tag names — from acting as LIKE wildcards.