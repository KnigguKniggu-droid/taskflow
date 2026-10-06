# TaskFlow Web UI — Task Board Plan

## Overview

Add a self-contained, server-rendered-friendly web interface to the existing TaskFlow Flask application. The goal is to turn the JSON API into a usable team task board with no new frameworks, no build tools, and no external JS dependencies.

**Architecture decision:** Vanilla HTML + CSS + ES-module JS served as Flask static files from a single `app/static/` directory. Flask serves `index.html` at `/` via an explicit route. All data traffic goes through the existing JSON API on the same origin, so CORS is a non-issue. No bundler, no transpiler, no React/Vue/Angular — the existing Flask dev server is sufficient.

The JS is split into four ES modules loaded with `<script type="module">`:

| Module | Responsibility |
|---|---|
| `api.js` | All `fetch` calls to the TaskFlow API — `get`, `post`, `patch` helpers; reads `{"error"}` on non-2xx and rejects with the message string |
| `render.js` | Pure DOM-building functions — `renderTask(task, usersMap)`, `renderStatCards(stats)`, `populateUserSelect(users, selectEl)` — no I/O, no side effects |
| `modal.js` | Dialog lifecycle — `openModal(dialog, returnFocusEl)`, `closeModal(dialog)`, focus-trap logic; imported by app.js |
| `app.js` | Entry point and coordinator — `DOMContentLoaded` handler, wires events, calls api.js and render.js, holds `currentFilter` and `usersMap` state |

**Constraints honoured:**
- Existing API behaviour, tests, and documentation are unchanged.
- All business logic stays in `services.py`; the UI calls the API, not the DB.
- Two small additions to the server are required (see M1) — one new route (`GET /users`) and one new route (`GET /tasks/stats`) — justified below.

---

## API Gap Analysis

| UI need | Current API | Gap |
|---|---|---|
| Populate assignee dropdown | — | `GET /users` missing; must be added |
| Summary counts (total / open / completed / overdue) | — | No single endpoint; client-side aggregation is fragile because `GET /tasks` and `GET /tasks/overdue` have no counts and require two round-trips that can race; a `GET /tasks/stats` endpoint is cleaner |
| Combined `?assignee_id=&tag=` filter | `GET /tasks` | Already works |
| All other CRUD | Implemented | — |

### Justified additions

**`GET /users`**
Returns `{"users": [{"id": int, "name": str}, ...]}` ordered by id. Required so the Create Task form and filter bar can present a dropdown of users instead of asking for a raw integer. Without this the UI cannot fulfil the "assign users" requirement.

**`GET /tasks/stats`**
Returns `{"total": int, "open": int, "completed": int, "overdue": int}`. Counts are computed in a single SQL query with conditional aggregation (`SUM(CASE WHEN …)`), which avoids the dual-request race condition and keeps the summary card accurate with one fetch. Overdue count is: open tasks whose `due_date < today`.

---

## Files Added or Changed

### Server (Python)

| File | Change |
|---|---|
| `app/services.py` | Add `list_users()` and `get_task_stats(today)` functions |
| `app/routes.py` | Add `GET /users` and `GET /tasks/stats` routes |
| `tests/test_tasks.py` | Add test cases for the two new routes |

### Frontend (new files, no existing files modified)

| File | Purpose |
|---|---|
| `app/static/index.html` | Single-page shell: header, filter bar, summary cards, task list, modals |
| `app/static/style.css` | Responsive layout, accessible focus styles, state classes |
| `app/static/api.js` | Thin `fetch` wrapper — `get(path)`, `post(path, body)`, `patch(path, body)`; rejects with error string on non-2xx |
| `app/static/render.js` | Pure DOM-building functions — `renderTask`, `renderStatCards`, `populateUserSelect` |
| `app/static/modal.js` | Dialog open/close + focus trap; exported as `openModal` / `closeModal` |
| `app/static/app.js` | Entry-point coordinator — imports the above, wires events, holds `currentFilter` and `usersMap` state |
| `app/routes.py` | Add `GET /` route that serves `index.html` (one line) |

---

## Milestones

---

### M1 — Add Missing Server Endpoints

**Intent:** Provide the two API endpoints the UI needs before a single line of frontend code is written. Keeps server and client work independent; the test suite can verify correctness before the UI exists.

**Expected Outcomes:**
- `GET /users` returns `{"users": [...]}` 200, empty list when no users exist.
- `GET /tasks/stats` returns `{"total": int, "open": int, "completed": int, "overdue": int}` 200 with correct values after creates and completes.
- All existing tests still pass.
- New tests cover both endpoints.

**Todo list:**
1. In `services.py`, add `list_users()`: `SELECT id, name FROM users ORDER BY id` returning list of dicts.
2. In `services.py`, add `get_task_stats(today: date)`: single SQL using `COUNT(*)`, `SUM(CASE WHEN completed=0 THEN 1 ELSE 0 END)`, `SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END)`, `SUM(CASE WHEN completed=0 AND due_date IS NOT NULL AND due_date < ? THEN 1 ELSE 0 END)` — returns `{"total", "open", "completed", "overdue"}`.
3. In `routes.py`, add `GET /users` → `list_users()` → 200 + JSON.
4. In `routes.py`, add `GET /tasks/stats` → `get_task_stats(date.today())` → 200 + JSON.
5. In `tests/test_tasks.py`, add `UsersEndpointTestCase`: empty list, create user appears, multiple users ordered by id.
6. In `tests/test_tasks.py`, add `StatsEndpointTestCase`: zero state, after creates, after complete, overdue counting.

**Relevant context:**
- `list_tasks()` in `services.py` is the SQL pattern to follow for `list_users()`.
- `list_overdue_tasks()` in `services.py` shows how `today` is injected for testability — mirror the same pattern.
- Route pattern in `routes.py`: `@bp.route("/users", methods=["POST"])` — add a `GET` sibling.
- Test pattern: `TaskApiTestCase` in `tests/test_tasks.py` — follow the same `setUp`/`tearDown` and helper style.

**Verification:**
```
python -m unittest tests.test_tasks -v
```
All tests pass, including the new `UsersEndpointTestCase` and `StatsEndpointTestCase`.

**Status:** [ ] pending

---

### M2 — Static File Serving and Page Shell

**Intent:** Wire Flask to serve the frontend. Establish the HTML skeleton and CSS foundation before adding any JS logic — this lets layout and accessibility be validated in isolation.

**Expected Outcomes:**
- `GET /` returns `index.html` (200, `text/html`).
- The page renders a visible, keyboard-navigable shell: header, filter bar (assignee select + tag input + Apply/Clear buttons), four summary cards (Total / Open / Overdue / Completed), an empty task list area with an empty-state message, a floating "New Task" button, and a modal dialog outline.
- The page is responsive (single-column on mobile, multi-column on desktop, no horizontal scroll at 320 px width).
- All interactive controls are reachable with Tab and have visible focus rings.
- No JS errors in the browser console (JS file may be empty or a stub at this point).

**Todo list:**
1. In `app/routes.py`, add `GET /` route: `return current_app.send_static_file("index.html")`.
2. Create `app/static/index.html`: semantic HTML5 shell — `<header>`, `<main>`, filter `<form>` with `<select id="filter-assignee">` and `<input id="filter-tag">`, summary cards `<section id="stats">` with four `<dl>` items, `<ul id="task-list">`, `<button id="btn-new-task">`, `<dialog id="modal-create-task">` with form fields for title, description, tags, due_date, assignee_id. Load JS with `<script type="module" src="/static/app.js">`.
3. Add `aria-label` / `aria-live="polite"` on the task list region; `role="status"` on each summary card value; `aria-modal="true"` and `aria-labelledby` on the dialog.
4. Create `app/static/style.css`: CSS custom properties for colours and spacing; CSS Grid for card row; Flexbox for filter bar; `@media (max-width: 600px)` breakpoint for single-column; `:focus-visible` ring (2px offset); `.is-loading`, `.is-empty`, `.is-error` state classes.
5. Create `app/static/api.js` as an ES module stub with exported `get`, `post`, `patch` placeholders.
6. Create `app/static/render.js` as an ES module stub with exported `renderTask`, `renderStatCards`, `populateUserSelect` placeholders.
7. Create `app/static/modal.js` as an ES module stub with exported `openModal`, `closeModal` placeholders.
8. Create `app/static/app.js` as an ES module that imports from the three stubs and adds a `DOMContentLoaded` listener.

**Relevant context:**
- Flask `send_static_file` serves from `app/static/` by default when the app is created with the standard factory in `app/__init__.py`.
- `MAX_CONTENT_LENGTH` only applies to request bodies; static file serving is unaffected.

**Verification:**
- `python run.py`, open `http://127.0.0.1:5000/` in a browser — page loads, no console errors.
- Tab through all controls — all focusable, focus ring visible.
- Resize to 320 px width — no horizontal scroll.

**Status:** [ ] pending

---

### M3 — Summary Cards and Task List (Read Path)

**Intent:** Implement the full read path: fetch stats, fetch tasks (with combined filter), and render them. This is the first milestone with real data on screen.

**Expected Outcomes:**
- On page load, `GET /tasks/stats` is fetched and the four summary cards show live counts.
- On page load, `GET /tasks` is fetched and tasks render in a `<ul>` with each task's title, status badge (Open / Overdue / Completed), tags as chips, due date, and assignee name (resolved from the cached users list).
- Overdue open tasks are visually distinguished (e.g. red due-date text).
- The assignee dropdown in the filter bar is populated from `GET /users`.
- Applying the filter calls `GET /tasks?assignee_id=X&tag=Y` with whichever params are non-empty.
- Clearing the filter resets both inputs and reloads with no params.
- Loading state: skeleton / spinner shown while fetches are in flight.
- Empty state: "No tasks yet" message when the list is empty.
- Error state: `<p role="alert">` with the API's `{"error": "..."}` message if a fetch fails.
- The overdue count on the summary card matches `GET /tasks/stats`, not a client-side re-count.

**Todo list:**
1. In `api.js`, implement `get(path)`, `post(path, body)`, `patch(path, body)` using `fetch`; always parse JSON; on non-2xx read `{"error"}` and reject with the message string.
2. In `render.js`, implement `renderTask(task, usersMap)`: returns an `<li>` with title `<button>` (opens detail), status badge, tags as `<span class="tag">` chips, due date (formatted, red class if overdue and open), assignee name (from `usersMap`, fallback "Unassigned").
3. In `render.js`, implement `renderStatCards(stats)`: writes `stats.total`, `stats.open`, `stats.overdue`, `stats.completed` into the four summary `<dd>` elements.
4. In `render.js`, implement `populateUserSelect(users, selectEl)`: clears the `<select>`, prepends `<option value="">— All —</option>` (or "Unassigned" for form selects), appends one option per user.
5. In `app.js`, implement `loadUsers()`: calls `api.get("/users")`, stores result in module-level `usersMap` (`Map<id, name>`), calls `populateUserSelect` on both the filter select and any open form selects.
6. In `app.js`, implement `loadStats()`: calls `api.get("/tasks/stats")`, calls `render.renderStatCards(stats)`.
7. In `app.js`, implement `loadTasks(params)`: calls `api.get("/tasks?" + query)`, calls `render.renderTask` for each result, replaces `#task-list` content, shows empty or error state as appropriate.
8. Wire filter form `submit` event in `app.js`: read `filter-assignee` and `filter-tag` values, store as `currentFilter`, call `loadTasks(currentFilter)` omitting blank values.
9. Wire "Clear" button in `app.js`: reset form, set `currentFilter = {}`, call `loadTasks({})`.
10. In `app.js`, `DOMContentLoaded`: call `loadUsers()` then `Promise.all([loadStats(), loadTasks({})])`.
11. Add `.is-loading` CSS class to `#task-list` during fetch; CSS-only spinner animation (no image file).
12. Overdue display rule: a task is overdue if `!task.completed && task.due_date && task.due_date < todayISO`; this is for visual display only — the authoritative count comes from `GET /tasks/stats`.

**Relevant context:**
- Tag exact-match filter: the API already enforces exact match in SQL. The UI sends the tag value verbatim; no client-side validation needed for the filter input (server returns 400 on bad tag format, which the error handler displays).
- `task.assignee_id` is null when unassigned; users cache is a `Map` keyed by integer id.
- `task.created_at` is an ISO 8601 UTC string suitable for `new Date(task.created_at).toLocaleDateString()`.

**Verification:**
- `python run.py`, seed data via `curl` or the existing test helpers, open the board — cards and tasks appear.
- Filter by tag, by assignee, by both — list updates correctly.
- Disconnect network / stop Flask — error banner appears.

**Status:** [ ] pending

---

### M4 — Create Task Modal

**Intent:** Implement the write path for task creation, including all validation feedback.

**Expected Outcomes:**
- Clicking "New Task" opens the `<dialog>` modal with focus trapped inside.
- The form has fields: Title (required text input), Description (optional textarea), Tags (optional text input, hint: comma-separated), Due Date (optional `<input type="date">`), Assignee (optional `<select>` populated from users cache).
- Submitting calls `POST /tasks` with the correct JSON body.
- On 201: modal closes, task list and stats both refresh.
- On 400: the API's `{"error": "..."}` message is displayed inside the modal (not an alert).
- The submit button shows a loading state and is disabled while the request is in flight to prevent double-submit.
- Pressing Escape closes the modal (native `<dialog>` behaviour).
- After modal closes, focus returns to "New Task" button.
- Tags field: value is sent as-is (string); API's `normalize_tags` handles splitting and validation.

**Todo list:**
1. In `modal.js`, implement `openModal(dialogEl, returnFocusEl)`: calls `dialogEl.showModal()`, stores `returnFocusEl` for later return.
2. In `modal.js`, implement `closeModal(dialogEl)`: calls `dialogEl.close()`, returns focus to stored `returnFocusEl`.
3. In `modal.js`, implement focus-trap: on `keydown Tab` inside `dialogEl`, wrap focus between first and last focusable child (query `:is(button, input, select, textarea, [href])`).
4. In `app.js`, implement `submitCreateTask(formData)`: extracts title, description, tags (string), due_date, assignee_id (int or omit if blank), calls `api.post("/tasks", body)`.
5. In `app.js`, wire the "New Task" button → `modal.openModal(createDialog, btnNewTask)`.
6. Wire modal form `submit` event in `app.js`; prevent default; call `submitCreateTask`.
7. On success: call `modal.closeModal(createDialog)`, then `Promise.all([loadStats(), loadTasks(currentFilter)])`.
8. On error: render `<p class="form-error" role="alert">{error}</p>` inside the modal.
9. Add Cancel button in `index.html` that calls `modal.closeModal(createDialog)`.
10. Populate assignee `<select>` in modal via `render.populateUserSelect(users, selectEl)` after `loadUsers()` resolves.

**Relevant context:**
- `<dialog>` is natively supported in all modern browsers; no polyfill needed.
- `assignee_id` must be omitted (not sent as null or empty string) if not selected, or the API will reject it. When the select value is `""`, exclude the field from the POST body.
- Tag format: the API accepts a comma-separated string, so send `"python, flask"` directly; `normalize_tags` strips, lowercases, deduplicates.
- Known validation errors: title required, title max 200, description max 2000, tags format, date format, assignee not found — all returned as `{"error": "..."}` and displayed verbatim.

**Verification:**
- Create a task with all fields — appears in list, stats increment.
- Submit empty title — API returns 400, error shown in modal.
- Submit invalid tag `"bad tag!"` — error shown in modal.
- Submit invalid date `"2024-13-01"` — error shown in modal.
- Double-click submit — only one POST fires (button disabled).
- Open modal, press Escape — modal closes, focus returns.

**Status:** [ ] pending

---

### M5 — Task Detail and Complete Action

**Intent:** Allow users to view full task details and mark a task as completed.

**Expected Outcomes:**
- Clicking a task title/row opens a detail view (either a second `<dialog>` or an inline panel; `<dialog>` preferred for accessibility).
- Detail view shows all task fields: title, description, tags, due date, assignee name, created date, completion status.
- If the task is open, a "Mark Complete" button is present.
- Clicking "Mark Complete" calls `POST /tasks/<id>/complete`, then refreshes the task list and stats.
- The "Mark Complete" button shows a loading state and is disabled during the request.
- If the task is already completed, the button is hidden/replaced with a "Completed" badge.
- On 404 (task deleted between page load and click): display `{"error": "task X not found"}` inside the detail dialog.

**Todo list:**
1. Add `<dialog id="modal-task-detail">` to `index.html` with placeholder structure.
2. In `render.js`, implement `renderTaskDetail(task, usersMap)`: populates the detail dialog's inner HTML with all task fields, formatted dates, tags as chips, assignee name, completion badge or "Mark Complete" button.
3. In `app.js`, implement `openTaskDetail(taskId)`: calls `api.get("/tasks/<id>")`, calls `render.renderTaskDetail(task, usersMap)`, then calls `modal.openModal(detailDialog, sourceButton)`.
4. Wire task list item title `<button>` click in `app.js` (set by `render.renderTask`): calls `openTaskDetail(task.id)` with the button as `returnFocusEl`.
5. Wire "Mark Complete" button inside detail dialog: calls `api.post("/tasks/<id>/complete", {})`, on 200 calls `modal.closeModal(detailDialog)` then `Promise.all([loadStats(), loadTasks(currentFilter)])`.
6. On error (including 404): render `<p class="form-error" role="alert">{error}</p>` inside the detail dialog.
7. The focus-trap and return-focus behaviour is already handled by `modal.js` — no duplication needed.

**Relevant context:**
- `GET /tasks/<id>` returns the full task dict; no extra server work needed.
- `POST /tasks/<id>/complete` is idempotent by design (calling it on an already-completed task has no visible effect, same response).
- `IdConverter` in `routes.py` rejects non-digit path segments; client only passes integer ids so no client-side path sanitisation is needed.

**Verification:**
- Click a task — detail dialog opens with all fields.
- Click "Mark Complete" — task shows completed badge, stats update.
- Tab to a task row, press Enter — detail dialog opens (keyboard accessible).
- Simulate 404 (delete task via API then click) — error message shown in dialog.

**Status:** [ ] pending

---

### M6 — Edit Task (Assign User, Set Due Date, Set Tags)

**Intent:** Allow users to update assignee, due date, and tags on an existing task. This requires one new API endpoint.

**Note:** The current API has no `PATCH /tasks/<id>` or `PUT /tasks/<id>`. Updating task fields is a missing operation. Without it, the UI can only create tasks with their initial values, which does not meet the "assign users, set due dates, set tags" requirement for existing tasks. This is the only additional API endpoint beyond M1.

**New endpoint: `PATCH /tasks/<id>`**
- Accepts a partial JSON body with any subset of: `title`, `description`, `tags`, `due_date`, `assignee_id`.
- Unknown fields → 400. No-op if body is `{}` (returns current task, no DB write needed).
- Returns 200 + updated task dict.
- 404 if task id not found.
- Validation identical to `create_task` for each supplied field.
- SQL: `UPDATE tasks SET col = ? WHERE id = ?` for each supplied field, in a single `with db:` block.
- `completed` and `created_at` cannot be set via this endpoint.

**Expected Outcomes:**
- `PATCH /tasks/<id>` works for any combination of updatable fields.
- Supplying `completed` or `created_at` returns 400 (unknown fields guard).
- Test cases cover: update title only, update assignee only, clear due_date (set to null by passing `null`), update tags, combined, 404, validation errors.
- Edit button in the task detail dialog opens an edit form pre-populated with current values.
- Saving calls `PATCH /tasks/<id>`, closes the form, refreshes list and stats.

**Todo list:**
1. In `services.py`, add `update_task(task_id, data)`: validates data with `_reject_unknown_fields(data, TASK_FIELDS)`, applies field-level validation for each key present, builds a dynamic UPDATE SQL string with only the supplied columns, executes within `with db:`, returns updated task dict. Handle `due_date: null` (Python `None`) to clear the field.
2. In `routes.py`, add `PATCH /tasks/<id:task_id>` route calling `update_task`.
3. In `tests/test_tasks.py`, add `UpdateTaskTestCase` covering the scenarios above.
4. In `index.html`, add an "Edit" button inside the task detail dialog that switches the dialog to edit mode (show edit form, hide read-only view).
5. In `render.js`, implement `renderEditForm(task, usersMap)`: builds the edit form pre-populated with current values; exported so `app.js` can call it.
6. In `api.js`, confirm `patch(path, body)` is already implemented (done in M3 step 1).
7. In `app.js`, implement `submitUpdateTask(taskId, formData)`: builds a partial body containing only fields the user changed, calls `api.patch("/tasks/<id>", partialBody)`.
8. Wire edit form submit in `app.js` → on 200 re-render the detail view with `render.renderTaskDetail`, refresh task list and stats; on error show in-form error.

**Relevant context:**
- `_reject_unknown_fields` in `services.py` already protects against extra fields.
- `TASK_FIELDS` constant in `services.py` is `{"title", "description", "tags", "due_date", "assignee_id"}` — exactly the right set.
- SQL style: no ORM; build `SET col1 = ?, col2 = ?` dynamically from the keys present.
- `with db:` context manager for commit/rollback.
- `SELECT_TASKS` constant ensures the re-fetch after UPDATE uses the same column list.

**Verification:**
```
python -m unittest tests.test_tasks -v
```
All existing + new tests pass.
- UI: open a task, click Edit, change assignee and due date, save — board updates.
- Set `due_date` to empty string → clears due date (or send `null`; document chosen behaviour in code).

**Status:** [ ] pending

---

### M7 — Final Polish: Error Handling, Accessibility Audit, Responsive Check

**Intent:** Harden all error paths, ensure the UI is fully keyboard navigable, and verify responsiveness. No new functionality; this milestone raises quality to production-ready.

**Expected Outcomes:**
- Every API call has a try/catch; all errors surface as `role="alert"` banners or inline messages.
- Global error banner auto-dismisses after 5 seconds or on user close (`×` button).
- Page-level loading spinner on initial data fetch; removed once all promises resolve.
- Empty states: "No tasks found." when filter returns no results vs "No tasks yet." on a genuinely empty board.
- `<title>` updates to reflect filter state (e.g. "TaskFlow — filtered by tag: python").
- All images/icons have `alt` or `aria-label`.
- All form inputs have visible `<label>` elements associated via `for`/`id`.
- Tab order is logical throughout; no focus traps outside intended modals.
- At 320 px, 768 px, and 1200 px widths the layout adapts cleanly.
- `prefers-color-scheme: dark` media query provides a dark theme.
- `prefers-reduced-motion` media query disables CSS animations.

**Todo list:**
1. Audit every `api.get`/`api.post`/`api.patch` call in `app.js` — confirm all have `.catch` handlers writing to the global error banner.
2. Implement global error banner in `index.html` + `style.css`: fixed position, `role="alert"`, `aria-live="assertive"`, auto-dismiss timer, close `×` button; controlled from `app.js`.
3. Add `aria-busy="true"` to `#task-list` during loading; remove on completion.
4. Test keyboard navigation: Tab through filter bar → Apply → task list items → New Task button; Enter/Space on task row title button opens detail dialog.
5. Add dark-mode CSS block (`@media (prefers-color-scheme: dark)`).
6. Add `@media (prefers-reduced-motion: reduce)` block that sets `animation: none` and `transition: none`.
7. Test at three breakpoints (320 px, 768 px, 1200 px) and fix any overflow.
8. Verify `<title>` updates programmatically in `app.js` when filters are applied.
9. Run WAVE or axe browser extension against the live page; fix any reported issues.

**Relevant context:**
- `aria-live="polite"` already placed on task list in M2; change to `aria-live="assertive"` only on the error banner.
- No new API changes; this milestone is purely frontend.

**Verification:**
- Tab-only navigation completes all user journeys (create, filter, complete).
- Chrome DevTools → Lighthouse Accessibility score ≥ 90.
- No JS console errors under normal use or when API returns errors.
- Responsive layout confirmed at all three breakpoints.

**Status:** [ ] pending

---

## Test Coverage Summary

| New test class | Covers |
|---|---|
| `UsersEndpointTestCase` | `GET /users` empty, after create, ordering |
| `StatsEndpointTestCase` | `GET /tasks/stats` zero state, totals, after complete, overdue count |
| `UpdateTaskTestCase` | `PATCH /tasks/<id>` field combinations, 404, validation, unknown fields, completed/created_at rejection |

All new tests follow the existing `setUp`/`tearDown` pattern and helper style from `tests/test_tasks.py`.

---

## Dependency and Risk Notes

- **No new Python packages.** Flask's built-in static file serving handles the frontend.
- **No build step.** `index.html` loads modules via `<script type="module">` with `/static/` paths; all four JS files are plain text, no transpilation.
- **ES module browser support.** Native ES modules (`import`/`export`) are baseline 2018; no compatibility concern.
- **`<dialog>` browser support.** Baseline 2022; supported in Chrome 98+, Firefox 98+, Safari 15.4+. No polyfill needed.
- **No pagination risk.** Current API returns all tasks; for a team task board with a realistic number of tasks this is acceptable. If the dataset grows large, a future milestone could add `?limit=&offset=` — that is out of scope here.
- **Tag filter UX.** The API enforces exact tag match (not substring). The filter input label must make this clear ("Filter by exact tag").
- **Assignee name resolution.** Because `GET /tasks` does not return assignee names, the UI fetches `GET /users` once on load and caches it. Stale-cache risk is low because user creation happens infrequently.
- **`PATCH /tasks/<id>` null handling.** Clearing `due_date` requires sending `null` in JSON. The implementation must distinguish `null` (clear the field) from the key being absent (do not touch the field). This distinction must be documented in the service function and tested.
