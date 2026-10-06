# A browser check of the lifecycle UI (4 tasks: one in_progress and past due, one blocked, one open, one completed) found these problems:
1. The in-progress task that is past due shows only an "Overdue" badge, in the list and in the detail dialog ("Status: Overdue"), so its real status (in progress) is not visible anywhere.
2. The activity timeline shows "assigned to user 2" instead of the user's name.
3. The "Open" summary card shows 3 while only one task has status open; it counts every non-completed task, which is confusing next to the "In progress" and "Blocked" cards.
4. The six summary cards wrap so that "Completed" sits alone on a second row at desktop width.
Fix what is genuinely wrong without breaking API compatibility for existing clients, keep all tests passing, add tests for any server-side change, run the full test suite and the taskflow-regression-check skill, then commit with a clear message whose last line is: Generated-by: IBM Bob

---

**Status:** active  **Date:** 2026-10-06

---

### 👤 User

A browser check of the lifecycle UI (4 tasks: one in_progress and past due, one blocked, one open, one completed) found these problems:
1. The in-progress task that is past due shows only an "Overdue" badge, in the list and in the detail dialog ("Status: Overdue"), so its real status (in progress) is not visible anywhere.
2. The activity timeline shows "assigned to user 2" instead of the user's name.
3. The "Open" summary card shows 3 while only one task has status open; it counts every non-completed task, which is confusing next to the "In progress" and "Blocked" cards.
4. The six summary cards wrap so that "Completed" sits alone on a second row at desktop width.
Fix what is genuinely wrong without breaking API compatibility for existing clients, keep all tests passing, add tests for any server-side change, run the full test suite and the taskflow-regression-check skill, then commit with a clear message whose last line is: Generated-by: IBM Bob

---

### 🤖 Assistant

> 🔧 called: use_skill, list_files



> 🔧 **use_skill** — taskflow-regression-check

> 🔧 **list_files** — app/static

### 🤖 Assistant

> 🔧 called: update_todo_list



> 🔧 **update_todo_list** — [-] Investigate the codebase (services.py, routes.py, render.js, style.css, app.js) to understand the current implementation
[ ] Fix issue 1: in-progress+overdue tasks show only "Overdue" badge — show both statuses
[ ] Fix issue 2: activity timeline shows "user 2" instead of user name — fetch user name
[ ] Fix issue 3: "Open" summary card counts all non-completed tasks — should count only status=open
[ ] Fix issue 4: six summary cards wrap on desktop — fix layout so all 6 fit on one row
[ ] Add server-side tests for any server-side changes
[ ] Run full test suite and regression check
[ ] Commit with standardised message


### 🤖 Assistant

> 🔧 called: read_file, read_file



> 🔧 **read_file** — app/static/render.js

> 🔧 **read_file** — app/static/style.css

### 🤖 Assistant

> 🔧 called: read_file, read_file

Now let me look at the services.py and routes.py to understand the `stats` endpoint and `activity` endpoint:

> 🔧 **read_file** — app/services.py

> 🔧 **read_file** — app/routes.py

### 🤖 Assistant

> 🔧 called: read_file, read_file

Now let me read the app.js file to understand how activity is used in the UI:

> 🔧 **read_file** — app/static/index.html

> 🔧 **read_file** — app/static/app.js

### 🤖 Assistant

> 🔧 called: read_file

Now let me look at the tests to understand the existing structure:

> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: read_file



> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: read_file



> 🔧 **read_file** — tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: update_todo_list

Now I have a complete picture. Let me analyze all four issues:

**Issue 1**: In `render.js`, `_statusBadgeEl()` (line 62-75) and `renderTaskDetail()` (lines 160-166) replace the status badge entirely with "Overdue" when a task is overdue. It should show both the actual status badge AND the overdue badge.

**Issue 2**: In `services.py` line 280, the activity detail says `f"assigned to user {assignee_id}"` — it records the numeric ID, not the name. The fix should look up the user name and use it in the detail string. Since this is server-side, we need to add a `_get_user_name` helper and update the detail string.

**Issue 3**: In `render.js` line 148, `renderFilteredStats` sets `stat-open` to `open + in_progress + blocked`. The Open card should display only `open` count (strictly open tasks). BUT the API `get_task_stats` also returns `open` as the sum of all non-completed tasks (for backward compat). So we need to:
- In `renderStatCards`, display `stats.open` for the Open card (API already returns legacy definition there) — but the "Open" card label is misleading. However the user says the UI shows 3 while only 1 has status open. This means the UI currently shows the sum. The fix is to show only strictly-`open` tasks in the "Open" card.
- The API already returns `in_progress` and `blocked` separately. The UI should display `stats.open` as purely the "open" count. But right now `get_task_stats` sets `open` = sum of all non-completed. For backward compat we can add a separate `open_only` key... Actually, looking more carefully: the `renderStatCards` function at line 40-46 uses `stats.open` for the Open card. The `get_task_stats` service returns `open = cnt_open + cnt_in_progress + cnt_blocked`. The comment says this is for backward compat. The fix is to add a `open_only` key (or just fix the display in `renderStatCards` to use `stats.in_progress` for the In Progress card but then use `stats.open - stats.in_progress - stats.blocked` for "Open"). Actually, the simplest non-breaking approach: update `renderStatCards` in the JS to compute `stats.open - (stats.in_progress||0) - (stats.blocked||0)` for the Open card display, since `stats.in_progress` and `stats.blocked` are already in the response.

Similarly `renderFilteredStats` already correctly separates these counts — it just passes the wrong value to `stat-open`.

**Issue 4**: CSS grid with `repeat(auto-fit, minmax(140px, 1fr))` creates 6 cards of minimum 140px. At 900px max-width with padding 16px on each side = 868px usable. 6 × 140 = 840px, which should fit but 16px gaps (5 gaps × 16px = 80px) plus card widths means 840+80=920px which exceeds 868px. So the 6th card wraps. Fix: reduce minmax to `120px` or use `repeat(6, 1fr)` for desktop.

> 🔧 **update_todo_list** — [x] Investigate the codebase (services.py, routes.py, render.js, style.css, app.js) to understand the current implementation
[-] Fix issue 1: in-progress+overdue tasks show only "Overdue" badge — show both status + overdue badges
[-] Fix issue 2: activity timeline shows "user N" instead of user name — look up and store user name
[-] Fix issue 3: "Open" summary card counts all non-completed tasks — show only status=open count
[-] Fix issue 4: six summary cards wrap on desktop — fix grid layout
[ ] Add server-side tests for any server-side changes
[ ] Run full test suite and regression check
[ ] Commit with standardised message


### 🤖 Assistant

> 🔧 called: apply_diff

Now I'll implement all four fixes. Let me start with the JS/CSS fixes (issues 1, 3, 4) and the server-side fix (issue 2):

> 🔧 **apply_diff** — app/static/render.js

### 🤖 Assistant

> 🔧 called: apply_diff

Now fix the CSS grid (issue 4):

> 🔧 **apply_diff** — app/static/style.css

### 🤖 Assistant

> 🔧 called: apply_diff

Also need to update the small screens media query to not clobber the new grid:

> 🔧 **apply_diff** — <<<<<<< SEARCH
:start_line:533
-------
/* --- Responsive: small screens ------------------------------------ */
@media (max-width: 600px) {
  #stats {
    grid-template-columns: 1fr;
  }
=======
/* --- Responsive: small screens ------------------------------------ */
@media (max-width: 600px) {
  #stats {
    grid-template-columns: repeat(2, 1fr);
  }
>>>>>>> REPLACE


### 🤖 Assistant

> 🔧 called: apply_diff

Now fix issue 2 — the server-side activity detail for reassignment. Instead of "assigned to user N", we should look up the user name:

> 🔧 **apply_diff** — <<<<<<< SEARCH
:start_line:268
-------
    # --- assignee_id ---
    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None:
            assignee_id = parse_id(assignee_id, "assignee_id")
            if not _user_exists(assignee_id):
                raise ValidationError("assignee_id does not match an existing user")
        if assignee_id != current["assignee_id"]:
            columns.append("assignee_id = ?")
            values.append(assignee_id)
            if assignee_id is None:
                activity_rows.append(("reassigned", "assignee cleared"))
            else:
                activity_rows.append(("reassigned", f"assigned to user {assignee_id}"))
=======
    # --- assignee_id ---
    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None:
            assignee_id = parse_id(assignee_id, "assignee_id")
            if not _user_exists(assignee_id):
                raise ValidationError("assignee_id does not match an existing user")
        if assignee_id != current["assignee_id"]:
            columns.append("assignee_id = ?")
            values.append(assignee_id)
            if assignee_id is None:
                activity_rows.append(("reassigned", "assignee cleared"))
            else:
                user_name = _get_user_name(assignee_id)
                activity_rows.append(("reassigned", f"assigned to {user_name}"))
>>>>>>> REPLACE


### 🤖 Assistant

> 🔧 called: apply_diff

There are 2 test errors because I added `_get_user_name` but haven't defined the helper function yet. Let me add it:

> 🔧 **apply_diff** — <<<<<<< SEARCH
:start_line:439
-------
def _user_exists(user_id):
    row = get_db().execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None
=======
def _user_exists(user_id):
    row = get_db().execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None


def _get_user_name(user_id):
    """Return the name of a user by id, or a fallback string if not found."""
    row = get_db().execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["name"] if row else f"user {user_id}"
>>>>>>> REPLACE


### 🤖 Assistant

> 🔧 called: update_todo_list

All 23 checks pass. Now I need to add tests for the server-side change (the reassignment activity detail now stores user name). Let me add those tests:

> 🔧 **update_todo_list** — [x] Investigate the codebase (services.py, routes.py, render.js, style.css, app.js) to understand the current implementation
[x] Fix issue 1: in-progress+overdue tasks show only "Overdue" badge — show both status + overdue badges
[x] Fix issue 2: activity timeline shows "user N" instead of user name — look up and store user name
[x] Fix issue 3: "Open" summary card counts all non-completed tasks — show only status=open count
[x] Fix issue 4: six summary cards wrap on desktop — fix grid layout
[-] Add server-side tests for any server-side changes
[ ] Run full test suite and regression check
[ ] Commit with standardised message


### 🤖 Assistant

> 🔧 called: insert_content



> 🔧 **insert_content** — tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: execute_command

All 23 checks pass and the new tests are included. Let me run the full test suite explicitly to confirm the count:

> 🔧 **execute_command** — .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1 | tail -20

### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1 | Select-Object -Last 20

### 🤖 Assistant

> 🔧 called: update_todo_list

96 tests, all pass (previously 93, now 96 with our 3 new tests). Now commit:

> 🔧 **update_todo_list** — [x] Investigate the codebase (services.py, routes.py, render.js, style.css, app.js) to understand the current implementation
[x] Fix issue 1: in-progress+overdue tasks show only "Overdue" badge — show both status + overdue badges
[x] Fix issue 2: activity timeline shows "user N" instead of user name — look up and store user name
[x] Fix issue 3: "Open" summary card counts all non-completed tasks — show only status=open count
[x] Fix issue 4: six summary cards wrap on desktop — fix grid layout
[x] Add server-side tests for any server-side changes
[x] Run full test suite and regression check
[-] Commit with standardised message


### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — git add app/static/render.js app/static/style.css app/services.py tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — & git add app/static/render.js app/static/style.css app/services.py tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — $env:PATH += ";C:\Program Files\Git\bin;C:\Program Files\Git\cmd"; git add app/static/render.js app/static/style.css app/services.py tests/test_tasks.py

### 🤖 Assistant

> 🔧 called: execute_command



> 🔧 **execute_command** — $env:PATH += ";C:\Program Files\Git\bin;C:\Program Files\Git\cmd"; git commit -m "fix: lifecycle UI — dual status+overdue badge, user name in activity, Open card count, stat-card grid layout

Issue 1 (render.js): _statusBadgeEl and renderTaskDetail now always render
the real status badge first, then append a separate Overdue badge when the
task is also overdue.  An in-progress overdue task shows both badges.

Issue 2 (services.py): update_task now calls _get_user_name to resolve the
user name at assignment time and stores 'assigned to <name>' in the
task_activity detail, replacing the previous 'assigned to user <id>'.
New _get_user_name helper falls back to 'user <id>' if the row is missing.
Three tests added (ActivityReassignNameTestCase) to pin this behaviour.

Issue 3 (render.js): renderStatCards and renderFilteredStats now display
only the count of strictly-open tasks in the Open card.  renderStatCards
derives openOnly = stats.open - stats.in_progress - stats.blocked (API
backward compat is preserved — stats.open remains the non-completed sum).
renderFilteredStats already counted separately; was incorrectly passing the
aggregate sum to stat-open.

Issue 4 (style.css): #stats grid changed from repeat(auto-fit, minmax(140px,1fr))
to repeat(6, 1fr) so all six cards fit on one row at desktop width.
Small-screen breakpoint updated to repeat(2, 1fr).

All 96 tests pass; 23/23 regression-check smoke tests pass.

Generated-by: IBM Bob"

### 🤖 Assistant

> 🔧 called: update_todo_list



> 🔧 **update_todo_list** — [x] Investigate the codebase (services.py, routes.py, render.js, style.css, app.js) to understand the current implementation
[x] Fix issue 1: in-progress+overdue tasks show only "Overdue" badge — show both status + overdue badges
[x] Fix issue 2: activity timeline shows "user N" instead of user name — look up and store user name
[x] Fix issue 3: "Open" summary card counts all non-completed tasks — show only status=open count
[x] Fix issue 4: six summary cards wrap on desktop — fix grid layout
[x] Add server-side tests for any server-side changes
[x] Run full test suite and regression check
[x] Commit with standardised message


### 🤖 Assistant

All four issues fixed, 96/96 tests pass, 23/23 regression checks pass. Here's a summary of every change:

---

### Changes made

**[`app/static/render.js`](app/static/render.js)**

- **Issue 1 — dual-badge** (`_statusBadgeEl`, `renderTaskDetail`): previously an overdue task's badge replaced the status badge entirely with "Overdue". Now the real status badge is always rendered first; an "Overdue" badge is appended alongside it only when the task is also past-due. An in-progress overdue task now shows both `In Progress` and `Overdue`.

- **Issue 3 — Open card count** (`renderStatCards`, `renderFilteredStats`): the Open stat card now shows only tasks with `status = 'open'`. In `renderStatCards` this is derived as `stats.open − stats.in_progress − stats.blocked` (the API's `open` field keeps its backward-compatible definition of "all non-completed"). In `renderFilteredStats` the bug was simply passing the aggregate to `stat-open` instead of the separate `open` counter.

**[`app/static/style.css`](app/static/style.css)**

- **Issue 4 — card wrap**: changed `#stats` grid from `repeat(auto-fit, minmax(140px, 1fr))` to `repeat(6, 1fr)`. At 900 px max-width with 16 px gutters, `auto-fit` with a 140 px minimum couldn't fit all six columns without wrapping. The fixed six-column grid guarantees one row at desktop. Small-screen breakpoint updated to `repeat(2, 1fr)` (3×2 grid on phones) instead of the previous single column.

**[`app/services.py`](app/services.py)**

- **Issue 2 — user name in activity**: `update_task` now calls the new `_get_user_name(user_id)` helper to resolve the assignee's name at the time of assignment, storing `"assigned to Alice"` instead of `"assigned to user 2"`. Fallback is `"user <id>"` if the row is missing.

**[`tests/test_tasks.py`](tests/test_tasks.py)**

- **3 new tests** in `ActivityReassignNameTestCase`: verify the reassignment activity detail contains the user's name, that sequential reassignments record the correct name at each step, and that clearing the assignee still records `"assignee cleared"`.