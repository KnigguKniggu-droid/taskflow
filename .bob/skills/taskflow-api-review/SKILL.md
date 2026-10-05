---
name: taskflow-api-review
description: Use when the user wants to review a TaskFlow route, service, or SQL change against the project's conventions — checks parameterized SQL, input validation placement, JSON error format, status codes, exact tag matching, and test coverage.
---

# TaskFlow API Review

Review a diff or a set of changed files in `app/` against this project's
coding conventions. Report every finding with file, line number, and a
short explanation. Do not suggest changes outside the scope of the diff.

## Conventions to check

Work through the checklist below. For each item, read the relevant file(s)
with `read_file` before forming a verdict. Report findings grouped by
convention, with **file:line** references.

---

### 1. Parameterized SQL — no string interpolation

Every SQL query must use `?` placeholders and pass values in a separate
tuple or list. Flag any query that embeds a variable directly into the SQL
string via f-string, `%` formatting, `.format()`, or concatenation.

Reference: [`app/services.py`](app/services.py) — all existing queries use `?` placeholders.

---

### 2. Input validation belongs in `services.py` only

HTTP routes in `app/routes.py` must not validate field values. They may
call `_json_body()`, `services.parse_id_param()`, and `services.parse_tag_param()`,
but field-level checks (type, length, format, presence) must live in
`services.py`.

Flag any validation logic added directly to a route function.

---

### 3. JSON error format and correct status codes

Every error response must be `{"error": "<message>"}` — no other keys.

Expected status codes:
- `ValidationError` → **400**
- `NotFoundError` → **404**
- `werkzeug.exceptions.HTTPException` (405, 413, …) → preserve the
  original code, convert to JSON via the `handle_http_exception` handler.
- Successful creation → **201**.
- Successful read / update → **200**.

Flag any route that returns a raw string, an HTML error, or a non-standard
status code.

---

### 4. Exact tag matching — no substring false positives

The `list_tasks` function in `app/services.py` must match tags as whole
tokens. The correct pattern wraps both sides with commas:

```python
"(',' || tags || ',') LIKE ('%,' || ? || ',%') ESCAPE '\\'"
```

and the tag value must be escaped for `%`, `_`, and `\` before embedding in
the pattern.

Flag any alternative that uses plain `LIKE '%tag%'` or `INSTR`, which
would allow substring matches.

---

### 5. Unknown-field rejection

Every service function that accepts a JSON payload must call
`_reject_unknown_fields(data, <ALLOWED_FIELDS>)` as its first validation
step. Flag any new service function that skips this call.

---

### 6. `SELECT_TASKS` constant used for all task queries

All `SELECT` and `INSERT … RETURNING` statements that return a full task
row must reference the `SELECT_TASKS` constant, not repeat the column list.
Flag any new query that hardcodes the column list instead.

---

### 7. Test coverage

Every new route or service function should have at least one corresponding
test in `tests/test_tasks.py`. Check whether the diff adds tests for:
- The happy path (valid input → expected response and body).
- At least one validation-error path (invalid input → 400).
- The 404 path where relevant.

Flag missing coverage by naming the untested scenario.

---

## Output format

List findings as a numbered list. Each item must include:
- **Convention** (from the section headings above)
- **File and line** (e.g. `app/routes.py:45`)
- **What was found** (one sentence)
- **Why it matters** (one sentence)

If no violations are found for a convention, write `✓ <Convention>: no issues`.

End with a one-line verdict:
- `No violations found.`
- `N violation(s) found — see above.`
