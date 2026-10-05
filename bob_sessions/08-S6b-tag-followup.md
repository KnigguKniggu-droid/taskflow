# Stage 6b - follow-up on an observed tag false positive

- Bob task (ACP session) id: `dbf247a01cb1111015f68ba571e74716`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `agent`
- Started (UTC): 2026-10-05T04:07:41+00:00 - duration 36.9 s - stop reason: end_turn
- Tool calls: 8; permission requests: 5 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
An independent acceptance check found a failure: GET /tasks?tag=a_b returns a task whose only tag is axb. Tags are allowed to contain underscores, so this violates exact tag membership. Fix the cause, add a regression test that reproduces this case, run the full suite and show it passing, then commit only your changes with a clear message whose last line is: Generated-by: IBM Bob
```

## Tool calls by Bob

- `read` Reading file <repo>\app\services.py (80-115) - completed
- `edit` Applying diff to <repo>\app\services.py - completed
- `None`  - failed
- `read` Reading file <repo>\tests\test_tasks.py (140-185) - completed
- `edit` Applying diff to <repo>\tests\test_tasks.py - completed
- `execute` .venv\Scripts\python.exe -m unittest tests.test_tasks -v 2>&1 - failed
- `execute` & "C:\Program Files\Git\bin\git.exe" add app/services.py tests/test_tasks.py - completed
- `execute` & "C:\Program Files\Git\bin\git.exe" commit -m "fix: escape LIKE metacharacters in tag filter

SQLite LIKE treats '_' as a single-character wildcard and '%'
as  - completed

## Bob's answer (verbatim)

Let me investigate the root cause before touching anything.The bug is clear. SQLite's `LIKE` operator treats `_` as a single-character wildcard (just like SQL standard). So `LIKE '%,a_b,%'` matches `,axb,`, `,a-b,`, `,azb,` — any single character in place of `_`. The fix is to escape the `_` (and `%`) in the tag value before handing it to `LIKE`, using SQLite's `ESCAPE` clause.Now add the regression test. I'll add it to the `TagFilterTestCase` class right after the existing substring false-positive tests:22/22 pass. Commit:### Root cause

SQLite's `LIKE` operator has two wildcard metacharacters: `%` (any sequence of characters) and `_` (any **single** character). The original condition:

```sql
(',' || tags || ',') LIKE ('%,' || ? || ',%')
```

passed the tag value directly into the LIKE pattern without escaping. Since `TAG_PATTERN` permits underscores in tag names, a query for `a_b` produced the pattern `%,a_b,%` where `_` acted as a wildcard — matching `,axb,`, `,a-b,`, `,a0b,`, etc.

### Fix in [`app/services.py`](app/services.py)

Before building the LIKE pattern, the tag value is escaped:

```python
escaped_tag = tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
conditions.append("(',' || tags || ',') LIKE ('%,' || ? || ',%') ESCAPE '\\'")
params.append(escaped_tag)
```

The `ESCAPE '\\'` clause tells SQLite to treat `\` as the escape character, so `\_` in the pattern matches a literal `_` instead of any character. The order of replacements — backslash first, then `%`, then `_` — ensures the escape character itself is not double-escaped.

### Regression test

`test_underscore_in_tag_is_not_like_wildcard` creates three tasks tagged `axb`, `a-b`, and `a_b`, then asserts `?tag=a_b` returns only the last one.

```
Ran 22 tests in 0.855s
OK
```
