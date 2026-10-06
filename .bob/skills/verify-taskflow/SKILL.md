---
name: verify-taskflow
description: >
  Run a parallel four-axis review of the TaskFlow changeset (API correctness,
  test quality, documentation consistency, security/SQL) using subagents, then
  accept or reject each finding, fix accepted code/test defects, run the full
  suite, and commit with a standardised message. Use when the user asks for a
  multi-axis review of a TaskFlow change or asks to verify a TaskFlow commit.
---

# Verify TaskFlow

Perform a structured multi-axis review of every TaskFlow code change between
two git refs (default: `pre-bob-baseline` → `HEAD`).

---

## Step 1 — Collect the diff

```powershell
git diff <base> HEAD --stat
git diff <base> HEAD -- app/db.py app/routes.py app/services.py tests/test_tasks.py
```

Read every changed source file with `read_file` **before** spawning subagents so
you can provide grounded context rather than asking each subagent to fetch it.

---

## Step 2 — Spawn four subagents in parallel

Each subagent receives the full diff and current file content as context.

| Axis | Focus |
|------|-------|
| **A — API correctness** | Logic bugs, edge cases, off-by-ones, SQL query correctness |
| **B — Test quality** | Coverage gaps, incorrect assertions, misleading comments/docstrings |
| **C — Documentation** | AGENTS.md / README inconsistencies vs. the actual code |
| **D — Security / SQL** | SQL injection, LIKE wildcard injection, input-validation bypass |

Use `fork_context: false` (each subagent gets its own focused prompt with the
necessary code inline). Parallel calls are safe here — subagents are independent.

---

## Step 3 — Summarize and decide

For each finding:

1. **State** the finding (file, line, what was found, why it matters).
2. **Verdict**: ACCEPT or REJECT (with reason).

Acceptance criteria for a code or test fix:
- It is a real, reproducible defect — not a theoretical concern or style nit.
- The fix is contained to `app/` or `tests/` (no documentation changes in this step).
- The fix does not introduce new behaviour beyond correcting the defect.

Reject:
- Findings that are inherent SQLite / platform limitations beyond the project's scope.
- Documentation inconsistencies (defer to a separate documentation-update step).
- Security "notes" that identify correct defensive code.

---

## Step 4 — Apply accepted fixes

Use `apply_diff` or `search_and_replace` for surgical edits.
Never use `write_file` for existing files unless a complete rewrite is required.

Common accepted fix types:
- Correcting misleading test docstrings/comments that claim more than the test verifies.
- Removing `assertIs(x, False)` that provides no protection beyond `assertFalse(x)`.
- Adding a missing `assertIsNotNone` / stronger type assertion at the HTTP boundary.

---

## Step 5 — Run the full suite

```powershell
# Unit tests
.venv\Scripts\python.exe -m unittest tests.test_tasks -v

# Regression smoke test (if .bob/skills/taskflow-regression-check exists)
.venv\Scripts\python.exe .bob\skills\taskflow-regression-check\regression_check.py
```

All tests must pass before committing. If any test fails, fix the root cause
before proceeding — do not suppress or skip tests.

---

## Step 6 — Commit

Stage all accepted fixes **plus** this skill file:

```powershell
git add app/ tests/ .bob/skills/verify-taskflow/SKILL.md
git commit -m "<subject line>

<body: one sentence per fix>

Generated-by: IBM Bob"
```

Rules for the commit message:
- Subject line: imperative mood, ≤72 characters, describes what was fixed.
- Body: one bullet or sentence per accepted finding.
- **Last line must be exactly:** `Generated-by: IBM Bob`
- If no code/test fix was warranted, commit only `.bob/skills/verify-taskflow/SKILL.md`
  with an appropriate subject line.

---

## Conventions to check per axis

### A — API correctness
- `TAG_PATTERN` regex correctly bounds tag length (1–32 chars via `[a-z0-9][a-z0-9_-]{0,31}`).
- SQLite `ESCAPE '\\' ` in Python string → `ESCAPE '\'` in SQL → escape char is `\`. Correct.
- Escaping order for LIKE metacharacters: `\` first, then `%`, then `_`.
- `CREATE TABLE IF NOT EXISTS` does **not** ALTER existing columns on existing databases —
  backfill UPDATE is the correct complementary fix for historical NULL rows.
- `complete_task` writes `completed = 1`; overdue query uses `completed = 0`.

### B — Test quality
- `assertIs(x, False)` is not stronger than `assertFalse(x)` when `_task_to_dict` already
  calls `bool(row["completed"])` — `bool(None)` is also the `False` singleton.
- Schema init tests using `CREATE TABLE IF NOT EXISTS` on pre-existing old-schema databases:
  the column definition does not change; only the `UPDATE` backfill runs. Test docstrings
  must not claim the schema was migrated.
- Every new route or service function needs: happy path, ≥1 validation-error path (400),
  and 404 path where applicable.

### C — Documentation (defer fixes to a separate step)
- AGENTS.md Feature Status table must reflect implemented vs. planned status.
- AGENTS.md API table for `GET /tasks` must list all accepted query parameters.
- AGENTS.md Coding Conventions must mention `parse_tag_param` alongside `parse_id_param`.

### D — Security / SQL
- All SQL values travel via `?` placeholders — no f-string or concatenation with user data.
- `TAG_PATTERN` is always applied with `.fullmatch()` (not `.match()` or `.search()`).
- `parse_id_param` uses `isdigit()` + length cap before `int()`.
- LIKE wildcard characters allowed by TAG_PATTERN: only `_`. Escaped correctly.
