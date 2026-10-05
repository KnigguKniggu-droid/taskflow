# Stage 9a - review in the custom TaskFlow Reviewer mode

- Bob task (ACP session) id: `091565b2b3810fd6b97d932852274caa`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `taskflow-reviewer`
- Started (UTC): 2026-10-05T04:14:47+00:00 - duration 81.6 s - stop reason: end_turn
- Tool calls: 17; permission requests: 11 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
Review the complete change set between the pre-bob-baseline tag and HEAD using the taskflow-api-review skill, and run the test suite. Report findings only, each with severity, file and line, and say which you consider real defects versus acceptable choices. Do not change any files.
```

## Tool calls by Bob

- `other` Using skill taskflow-api-review - completed
- `execute` git diff pre-bob-baseline HEAD --stat - failed
- `execute` & "C:\Program Files\Git\bin\git.exe" diff pre-bob-baseline HEAD --stat - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" diff pre-bob-baseline HEAD -- app/services.py app/routes.py app/db.py tests/test_tasks.py - completed
- `read` Reading file <repo>\app\services.py - completed
- `read` Reading file <repo>\app\routes.py - completed
- `read` Reading file <repo>\app\db.py - completed
- `execute` & "<repo>\.venv\Scripts\python.exe" -m unittest tests.test_tasks -v 2>&1 - failed
- `read` Searching files in <repo>\app\services.py for "TAG_PATTERN" - completed
- `execute` & "<repo>\.venv\Scripts\python.exe" -c "
import re
TAG_PATTERN = re.compile(r'[a-z0-9][a-z0-9_-]{0,31}')

# a single-character tag: just one letter
print('singl - failed
- `execute` & "<repo>\.venv\Scripts\python.exe" -c @"
import re, sqlite3

TAG_PATTERN = re.compile(r'[a-z0-9][a-z0-9_-]{0,31}')
print('single char a:', bool(TAG_PATTERN.ful - failed
- `execute` $script = @'
import re, sqlite3

TAG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
print("single char a:", bool(TAG_PATTERN.fullmatch("a")))
print("empty st - completed
- `execute` $script = @'
# Check what Python string literal produces for the ESCAPE clause
sql = "(',' || tags || ',') LIKE ('%,' || ? || ',%') ESCAPE '\\'"
# Inspect the a - completed
- `execute` $script = @'
# Confirm: in the Python string "'\\'" how many chars between the outer quotes?
s = "(',' || tags || ',') LIKE ('%,' || ? || ',%') ESCAPE '\\'"
# F - completed
- `execute` $script = @'
import re
TAG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
# single char tag is valid (second group has 0 repetitions)
print("1-char valid:",  - completed
- `read` Searching files in <repo>\tests\test_tasks.py for "parse_tag_param|tag.*400|400.*tag|dash|hyphen|single.char|1.char"" - completed
- `read` Reading file <repo>\tests\test_tasks.py (1, 70) - completed

## Bob's answer (verbatim)

Now let me read the full current state of the changed files:Now let me run the test suite:All 24 tests pass. Now let me check the one subtle issue I spotted — the `TAG_PATTERN` regex anchor and its interaction with `parse_tag_param` — and also carefully audit the `ESCAPE '\\'` string literal correctness:This is a real finding. The `ESCAPE '\\'` clause in the SQL string sends two characters (`\\`) to SQLite instead of the one character (`\`) it requires. Let me confirm exactly what Python string is produced:The `'\\'` Python string literal is a single backslash (`\`) — exactly one character — so SQLite receives the correct single-character escape. This is **not** a defect; `'\\'` in Python is the string `\`. The test `test_underscore_in_tag_is_not_like_wildcard` also confirms this works correctly.

Now let me do a final check on the one-character tag pattern (single character tags are valid by regex — `{0,31}` means the second char class is optional), and check if there are any missing test scenarios:All the relevant code has been examined. Here is the full review report.

---

## Review Report: `pre-bob-baseline` → HEAD

**Test suite:** 24/24 passed ✓

---

### Convention 1 — Parameterized SQL

✓ **No issues.** Every query in the diff uses `?` placeholders. The new dynamic `WHERE` clause in [`list_tasks()`](app/services.py:105) builds its clause list from constants and appends values to a `params` list; no string interpolation is used. The backfill [`UPDATE tasks SET completed = 0 WHERE completed IS NULL`](app/db.py:62) has no user-supplied input and is safe.

---

### Convention 2 — Input validation belongs in `services.py` only

✓ **No issues.** [`routes.py:44`](app/routes.py:44) calls `services.parse_tag_param()` — the route delegates to the service layer without doing any field-level checking itself. This is consistent with how `parse_id_param` was already used.

---

### Convention 3 — JSON error format and correct status codes

✓ **No issues.** No new routes or error handlers were added. The existing `handle_validation_error` (→ 400) and `handle_not_found` (→ 404) handlers cover all new code paths.

---

### Convention 4 — Exact tag matching, no substring false positives

✓ **No issues.** [`services.py:102`](app/services.py:102) uses the prescribed pattern:

```python
"(',' || tags || ',') LIKE ('%,' || ? || ',%') ESCAPE '\\'"
```

The Python string literal `'\\'` is a **single backslash**, so SQLite receives the correct one-character ESCAPE argument. The escaping sequence on [line 101](app/services.py:101) correctly handles `\`, `%`, and `_` in that order (backslash first, to avoid double-escaping). The `test_underscore_in_tag_is_not_like_wildcard` test confirms end-to-end correctness.

---

### Convention 5 — Unknown-field rejection

✓ **No issues.** `parse_tag_param` is a query-string parser, not a JSON-payload handler, so `_reject_unknown_fields` does not apply. No new service function that accepts a JSON payload was added.

---

### Convention 6 — `SELECT_TASKS` constant used for all task queries

✓ **No issues.** The new dynamic query in [`list_tasks()`](app/services.py:105) starts with `query = SELECT_TASKS` and appends only the `WHERE` clause and `ORDER BY`. No column list is hardcoded.

---

### Convention 7 — Test coverage

**1 finding (minor):**

> **Finding 1**
> **Convention:** Test coverage
> **Severity:** Low
> **File:** [`tests/test_tasks.py`](tests/test_tasks.py) — no line, gap in `TagFilterTestCase`
> **What was found:** There is no test for `?tag=` combined with a percent-sign (`%`) in the tag value. Tags containing `%` are rejected by `TAG_PATTERN` (which only allows `[a-z0-9_-]`), so this combination cannot actually reach the SQL. However, the analogous `_` escape path _is_ tested (`test_underscore_in_tag_is_not_like_wildcard`) while the `%` escape path is not.
> **Why it matters:** This is a superficial gap — `TAG_PATTERN` makes it structurally impossible for `%` to reach the LIKE clause, so there is no observable risk. It is also consistent with the project's existing style of not testing inputs that are rejected before they reach SQL. This is an **acceptable choice**, not a defect.

---

### Additional observation (not a convention violation)

> **Finding 2**
> **Severity:** Low / informational
> **File:** [`app/db.py:58`](app/db.py:58)
> **What was found:** `init_db` calls `conn.executescript(SCHEMA)` which issues an implicit `COMMIT` before running (SQLite `executescript` always commits any open transaction first). This means the backfill `UPDATE` on [line 62](app/db.py:62) runs in a separate transaction from the schema creation. On a brand-new database this is harmless, but on an existing database the window between the `executescript` and the `with conn:` block is not atomic with respect to concurrent writers.
> **Why it matters:** This is an **acceptable choice** for TaskFlow's single-process, single-writer SQLite deployment. It is not a bug in any realistic usage scenario; it would only matter if two processes called `init_db` on the same database file simultaneously, which the project does not do.

---

### Verdict

**1 minor finding** — no real defects. Both findings are acceptable choices given the project's scope and constraints. The ESCAPE literal, the escaping order, and the `SELECT_TASKS` usage are all correct. All 24 tests pass.
