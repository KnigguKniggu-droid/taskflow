# Task Lifecycle and Activity History — Implementation Plan

## Overview

TaskFlow tasks currently carry a single boolean `completed` column. This plan evolves
the domain model to a four-state lifecycle (`open`, `in_progress`, `blocked`,
`completed`) and adds an immutable `task_activity` table that records every meaningful
change to a task. The activity log is displayed as a timeline in the task detail view
of the web UI.

### Goals
- Replace the boolean with an explicit status that is still expressed as `"completed": true/false` to old clients.
- Record every meaningful mutation (create, status change, reassign, due-date change,
  tags/description edit, complete, reopen) as an immutable row in `task_activity`.
- Show the timeline in the task detail modal without a separate API call where possible.
- Enforce valid transitions server-side; reject invalid ones explicitly.

### Non-goals
- No authentication, no per-user activity attribution (actor is omitted).
- No pagination, search, or filtering of activity history.
- No workflow engine, SLA tracking, or project-hierarchy features.
- No removal of the `completed` column or the `POST /tasks/<id>/complete` endpoint.

### Constraints
1. **No destructive migration.** Existing SQLite databases are upgraded safely by
   `init_db` on next startup with no data loss.
2. **Backward compatibility.** Every existing API consumer continues to work:
   - `completed` field present on every task response (`bool`).
   - `POST /tasks/<id>/complete` continues to work and transitions status to
     `completed`.
3. **Overdue logic unchanged.** Tasks in any non-completed status whose due date is
   past are overdue.
4. **Tag-filter correctness preserved.**
5. **Invalid transitions rejected.** `409 Conflict` is returned when a status value
   is valid but the transition from the task's current state is not permitted.
   `400 Bad Request` is returned for malformed input such as an unknown status value.
6. **Activity records reflect actual changes.** A failed request writes nothing to
   `task_activity`.

---

## Current State (reference)

| Artefact | Key detail |
|---|---|
| `app/db.py` `SCHEMA` | `tasks` table has `completed INTEGER NOT NULL DEFAULT 0`; `init_db` backfills old NULL rows |
| `app/services.py` | `SELECT_TASKS` selects 8 columns incl. `completed`; `_task_to_dict` converts `completed` to `bool`; `TASK_FIELDS` whitelist for PATCH excludes `completed` |
| `app/routes.py` | `POST /tasks/<id>/complete` calls `complete_task()`; PATCH rejects `completed` field |
| `tests/test_tasks.py` | `SchemaInitTestCase` and `OldSchemaRegressionTestCase` guard the existing NULL-backfill migration; `FilteredStatsConsistencyTestCase` checks `completed` and `due_date` in filtered responses |
| Web UI (`render.js`) | Three badge states derived from `task.completed` + due-date comparison; "Mark Complete" button shown when `!isCompleted` |
| Web UI (`app.js`) | Status changed only via `POST .../complete`; PATCH body never contains `completed` |

---

## Data Model

### New column on `tasks`

```
status TEXT NOT NULL DEFAULT 'open'
```

Added via `ALTER TABLE` in `init_db`. Allowed values: `open`, `in_progress`,
`blocked`, `completed`. The existing `completed` column is **kept** and **kept in
sync**: every write that changes `status` also writes `completed` (1 when
`status = 'completed'`, 0 otherwise). This means old readers of the column continue
to work, and the NULL-backfill migration already in `init_db` stays untouched.

### New table: `task_activity`

```sql
CREATE TABLE IF NOT EXISTS task_activity (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   INTEGER NOT NULL REFERENCES tasks (id),
    event     TEXT NOT NULL,
    detail    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_activity_task_id ON task_activity (task_id);
```

`event` is a short machine-readable label. Initial set:

| event | when recorded |
|---|---|
| `created` | task first inserted |
| `status_changed` | `status` column changes (includes `POST /tasks/<id>/complete`) |
| `reassigned` | `assignee_id` changes (including cleared to NULL) |
| `due_date_changed` | `due_date` changes (including cleared) |
| `details_edited` | `title`, `description`, or `tags` changed via PATCH |

`detail` carries a human-readable summary string, e.g. `"open → in_progress"` or
`"due date set to 2025-12-31"`. It is never parsed by any code — it is display text
only.

### Migration strategy

`init_db` already uses idempotent `CREATE TABLE IF NOT EXISTS` and a backfill UPDATE.
The same pattern is extended:

1. `CREATE TABLE IF NOT EXISTS task_activity (...)` — no-op on new DBs, creates table on old ones.
2. `ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'open'` — guarded by an
   explicit column-existence check: query `PRAGMA table_info(tasks)` first and only
   issue the `ALTER TABLE` when `status` is absent. This avoids catching a broad
   `OperationalError` that could silently mask unrelated database errors.
3. Backfill: `UPDATE tasks SET status = 'completed' WHERE completed = 1` — sets the
   `status` column to `completed` for every row that was already marked done, so
   history is consistent. Safe no-op on a fresh database (no rows).
4. No backfill of `task_activity` rows for pre-existing tasks — activity history starts
   from the moment of upgrade. The UI will simply show an empty timeline for tasks
   created before the upgrade.

No `schema_version` table is introduced; the idempotent pattern is sufficient for the
scale of this project.

### Valid transitions

```
open        → in_progress, blocked, completed
in_progress → open, blocked, completed
blocked     → open, in_progress, completed
completed   → open   (reopen)
```

Any other attempted transition returns `400 Bad Request` with
`{"error": "invalid status transition: <from> → <to>"}`.

---

## API Changes

### Task response shape (extended, backward-compatible)

Every task response gains one new field:

```json
{
  "id": 1,
  "title": "...",
  "status": "in_progress",
  "completed": false,
  ...existing fields unchanged...
}
```

`completed` continues to be derived as `status == "completed"` and serialised as a
boolean, so no existing client breaks.

### New field accepted by `PATCH /tasks/<id>`

`status` is added to `TASK_FIELDS` (the PATCH whitelist). Validation:
- Value must be a string and one of the four allowed values; otherwise `400`.
- The transition from the task's current `status` to the requested `status` must be
  valid; otherwise `409 Conflict` with `{"error": "invalid status transition: <from> → <to>"}`.
- `completed` remains forbidden in PATCH (unchanged).
- On a successful status change, one `status_changed` activity row is written **inside
  the same DB transaction** as the UPDATE.

Other PATCH fields continue to behave exactly as now; the only addition is that each
successful field change records an activity row in the same transaction (except `status`,
activity rows for field edits are coalesced: a single PATCH that changes title + tags +
description writes one `details_edited` row, not three).

### `POST /tasks/<id>/complete`

Behaviour unchanged from the client's perspective: it marks the task completed and
returns the full task with `"completed": true`. Internally it now sets `status =
'completed'` (and `completed = 1` as before) and writes a `status_changed` activity
row. It does **not** raise an error when called on an already-completed task (current
behaviour is preserved — idempotent success).

### New endpoint: `GET /tasks/<id>/activity`

Returns the activity log for one task, oldest-first.

```
GET /tasks/<id>/activity
200 OK
{
  "activity": [
    { "id": 1, "event": "created",        "detail": "",                         "created_at": "2025-06-01T10:00:00+00:00" },
    { "id": 2, "event": "status_changed", "detail": "open → in_progress",       "created_at": "2025-06-02T09:15:00+00:00" },
    { "id": 3, "event": "reassigned",     "detail": "assigned to user 3",       "created_at": "2025-06-02T11:00:00+00:00" },
    { "id": 4, "event": "details_edited", "detail": "title, tags updated",      "created_at": "2025-06-03T14:30:00+00:00" }
  ]
}
404 if task does not exist
```

The UI fetches this endpoint when opening the task detail modal.

### `GET /tasks/stats`

The stats endpoint currently returns `open` and `completed` counts. It is extended to
return per-status counts while keeping the original keys:

```json
{
  "total": 10,
  "open": 4,
  "in_progress": 2,
  "blocked": 1,
  "completed": 3,
  "overdue": 2
}
```

The `open` key retains its current meaning (tasks that are not completed), so its value
becomes `in_progress + blocked + open`. This keeps any existing client that reads only
`open` and `completed` unbroken, while exposing the richer breakdown for new clients.

---

## UI Changes

### Status badge

The three-way badge logic in `render.js` becomes a four-way lookup:

| status | CSS class | label |
|---|---|---|
| `open` | `badge-open` | Open |
| `in_progress` | `badge-in-progress` | In Progress |
| `blocked` | `badge-blocked` | Blocked |
| `completed` | `badge-completed` | Completed |

Overdue is overlaid independently: a task is displayed as overdue when its status is not
`completed` and its due date is in the past. No CSS class is removed.

### Task action area

"Mark Complete" is replaced by a compact **Status** dropdown in the task detail modal
(read-only view, not the edit form). The dropdown lists only the currently valid next
states. Selecting a value sends `PATCH /tasks/<id>` with `{"status": "<new>"}`.

For backward compatibility the "Mark Complete" button remains in the code path if
`status` is absent from the server response (graceful degradation for a server that
has not yet been upgraded).

### Edit form

No status selector is added to the PATCH edit form — status transitions are intentional
actions, not field edits. The current field set (title, description, tags, due_date,
assignee_id) is unchanged.

### Activity timeline in task detail modal

After the task fields section, the modal shows a `<section class="activity-timeline">`.
Each entry renders as:
```
● [label for event]  ·  [relative or absolute timestamp]
  [detail text]
```

The timeline section is populated by a `renderActivityTimeline(activities)` function in
`render.js`. `app.js` fetches `GET /tasks/<id>/activity` when opening the detail modal
(in parallel with or immediately after the task fetch) and passes the result to the
renderer.

### Stat cards

A new "In Progress" stat card and a "Blocked" stat card are added to `index.html`
alongside the existing Total / Open / Overdue / Completed cards. The existing cards'
semantics are preserved.

---

## Test Plan

### Existing tests

All existing tests must continue to pass without modification. Key tests that exercise
compatibility:
- `SchemaInitTestCase` — guards the NULL-backfill; will also gain coverage of the new
  `status` column backfill.
- `OldSchemaRegressionTestCase` — tests against a pre-migration DB (no `status` column,
  no `task_activity` table); will be extended to verify that after `init_db` both are
  present and the `completed = 1` rows are backfilled to `status = 'completed'`.
- `FilteredStatsConsistencyTestCase` — task response must still carry `completed` and
  `due_date` for client-side calculations; `status` must also be present.

### New test classes

#### `StatusLifecycleTestCase`
- New task starts with `status = "open"` and `completed = False`.
- Each valid transition succeeds, returns the updated task, records a `status_changed`
  activity row, and sets `completed` correctly.
- A well-formed but disallowed transition (e.g. `completed → in_progress`) returns
  `409` with a descriptive error message.
- An unknown status value (e.g. `"status": "pending"`) returns `400`.
- `POST /tasks/<id>/complete` on an open task sets `status = "completed"` and
  `completed = True`.
- `POST /tasks/<id>/complete` on an already-completed task succeeds idempotently
  (status stays `completed`).
- PATCH `{"status": "completed"}` behaves equivalently to `POST .../complete`.
- PATCH `{"status": "open"}` on a completed task reopens it (`completed = False`).
- PATCH `{"completed": true}` still returns `400` (unchanged guard).

#### `ActivityHistoryTestCase`
- Creating a task writes exactly one `created` activity row.
- PATCH that changes `status` writes exactly one `status_changed` row with the correct
  `detail` string.
- PATCH that changes `assignee_id` writes exactly one `reassigned` row.
- PATCH that changes `due_date` writes exactly one `due_date_changed` row.
- PATCH that changes any combination of `title`, `description`, `tags` writes exactly
  one `details_edited` row.
- PATCH that changes multiple categories (e.g. title + due_date + status) in one
  request writes the appropriate rows for each category.
- A failed PATCH (validation error) writes no activity rows.
- `GET /tasks/<id>/activity` returns rows in `created_at` ascending order.
- `GET /tasks/<id>/activity` returns `404` for a nonexistent task.
- Activity rows are correctly isolated between tasks.

#### `OldSchemaActivityRegressionTestCase`
- Simulates a pre-lifecycle database (no `status` column, no `task_activity` table,
  some tasks with `completed = 1`).
- After `init_db`, asserts:
  - `task_activity` table exists.
  - `status` column exists on `tasks`.
  - Tasks with `completed = 1` now have `status = 'completed'`.
  - Tasks with `completed = 0` have `status = 'open'`.
- Asserts that the app can create new tasks, transition their status, and retrieve
  activity on the upgraded database.

#### `StatsBreakdownTestCase`
- Verifies the `GET /tasks/stats` response includes `in_progress` and `blocked` keys.
- Verifies `open` remains the count of non-completed tasks (in_progress + blocked + open).
- Verifies `overdue` counts tasks in any non-completed status with a past due date.

---

## Milestones

### Milestone 1 — Data model and migration
**Scope:** `app/db.py` only.

- Add `task_activity` DDL to `SCHEMA`.
- Add `ALTER TABLE tasks ADD COLUMN status ...` helper function (`_add_column_if_missing`)
  that catches `OperationalError` for the duplicate-column case.
- Add `ALTER TABLE task_activity` index DDL.
- Add backfill UPDATE for `status` in `init_db`.
- Add `SchemaInitTestCase` extensions and `OldSchemaActivityRegressionTestCase`.

**Verification:** All schema tests pass. A database created with the old schema (no
`status` column, no `task_activity` table) is accepted by `init_db` and emerges with
both present and the `status` backfill applied. All pre-existing tests still pass.

---

### Milestone 2 — Service layer: status lifecycle
**Scope:** `app/services.py`.

- Add `VALID_STATUSES` frozenset and `VALID_TRANSITIONS` dict.
- Extend `SELECT_TASKS` to include `status`.
- Extend `_task_to_dict` to include `"status"` (derives `completed` from
  `status == "completed"` instead of reading the column directly — the column is still
  written for compatibility).
- Add `status` to `TASK_FIELDS` (accepted by PATCH).
- Extend `create_task`: INSERT `status = 'open'` alongside `completed = 0`; write a
  `created` activity row in the same transaction.
- Extend `update_task`: validate and apply `status` transitions; write activity rows for
  each changed category in the same transaction.
- Extend `complete_task`: set `status = 'completed'` (and `completed = 1`); write
  `status_changed` activity row; keep idempotent behaviour.
- Add `get_task_activity(task_id)` service function.
- Extend `get_task_stats` to return per-status counts.

**Verification:** `StatusLifecycleTestCase` and `ActivityHistoryTestCase` pass. All
pre-existing tests still pass.

---

### Milestone 3 — Route layer
**Scope:** `app/routes.py`.

- Add `GET /tasks/<id>/activity` route that calls `get_task_activity`.
- Add a `TransitionError` exception class (subclass of the existing error hierarchy)
  that the service layer raises for disallowed transitions; the route layer maps it to
  `409 Conflict`. All other validation errors (unknown status value, wrong type, etc.)
  continue to map to `400` via `ValidationError`.
- Extend the stats route response (no route logic change needed if the service returns
  the new keys).

**Verification:** All API smoke tests pass. `GET /tasks/<id>/activity` returns `404`
for unknown tasks and `200` with the activity array for known ones. Stats response
includes new keys.

---

### Milestone 4 — Web UI
**Scope:** `app/static/` — `render.js`, `app.js`, `index.html`, `style.css`.

- `render.js`: Update badge logic for four statuses. Add `renderActivityTimeline`.
  Update `renderStats` to show new stat cards.
- `app.js`: Replace "Mark Complete" button with status dropdown that PATCHes
  `{"status": "<new>"}`. Fetch `GET /tasks/<id>/activity` when opening task detail.
  Update stat card rendering.
- `index.html`: Add activity timeline section to detail modal. Add stat card placeholders
  for In Progress and Blocked.
- `style.css`: Add CSS for `badge-in-progress`, `badge-blocked`, and the activity
  timeline layout.

**Verification:** The task board loads correctly. The four status badges render
correctly. Changing status via the dropdown updates the badge and refreshes the task.
The activity timeline appears in the task detail view. Completing a task via the status
dropdown shows "completed" badge and hides the dropdown (or shows only "reopen").
Existing stat cards still show correct counts.

---

### Milestone 5 — Regression sweep
**Scope:** `tests/test_tasks.py` — new test classes, extensions to existing ones.

- Add `StatusLifecycleTestCase`.
- Add `ActivityHistoryTestCase`.
- Add `OldSchemaActivityRegressionTestCase`.
- Add `StatsBreakdownTestCase`.
- Extend `SchemaInitTestCase` to assert `status` column and backfill.
- Extend `OldSchemaRegressionTestCase` to assert post-upgrade `status` values.
- Extend `FilteredStatsConsistencyTestCase` to assert `status` field present on each
  task in a filtered response.
- Run full test suite; all tests must pass with zero failures.

**Verification:** `python -m unittest tests.test_tasks -v` exits 0 with all tests
passing, including the old-schema regression tests against databases that have neither
`status` nor `task_activity`.

---

## Sub-task Summary

| # | Sub-task | Status |
|---|---|---|
| 1 | Data model and migration (`app/db.py` + schema tests) | [ ] pending |
| 2 | Service layer: status lifecycle and activity writes (`app/services.py`) | [ ] pending |
| 3 | Route layer: new activity endpoint, stats update (`app/routes.py`) | [ ] pending |
| 4 | Web UI: status badges, dropdown, activity timeline | [ ] pending |
| 5 | Regression sweep: new and extended test cases | [ ] pending |
