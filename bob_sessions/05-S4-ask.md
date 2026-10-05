# Stage 4 - Ask mode: semantics and repair options

- Bob task (ACP session) id: `870e1654850d5883fafca581610d91ef`
- Bob: Bob 2.0.5 via `bob acp`
- Mode: `ask`
- Started (UTC): 2026-10-05T04:02:40+00:00 - duration 33.3 s - stop reason: end_turn
- Tool calls: 0; permission requests: 0 (denied: 0)

## Prompt (written by the Claude Code orchestrator)

```text
Explain the root cause you diagnosed as if teaching a junior developer, including the SQL and SQLite semantics involved. Then compare at least two safe ways to repair it, with their trade-offs (including what happens to rows already stored in an existing database), and recommend the approach that establishes the strongest invariant. Do not modify code.
```

## Tool calls by Bob


## Bob's answer (verbatim)

## Teaching the Root Cause

### What `NULL` means in SQL

In most programming languages, a variable either has a value or it raises an error if you try to use it uninitialized. SQL is different. Every column in every row can hold a third state beyond `TRUE` and `FALSE`: **`NULL`**, meaning *unknown* or *absent*. This is not zero, not an empty string, not `false` — it is the deliberate absence of a value.

SQLite follows the SQL standard here exactly. Whenever you compare anything to `NULL` using `=`, the result is not `TRUE` or `FALSE` — it is `NULL`:

```sql
NULL = 0    →  NULL
NULL = 1    →  NULL
NULL != 0   →  NULL
NULL IS NULL →  TRUE   ← the only safe way to test for NULL
```

This is called **three-valued logic**, and it has one critical consequence for `WHERE` clauses: **a row is only kept if the predicate evaluates to `TRUE`**. A `NULL` result is treated the same as `FALSE` — the row is silently dropped.

---

### How `NULL` gets into the `completed` column

Look at the schema in [`db.py`](app/db.py:13):

```sql
CREATE TABLE IF NOT EXISTS tasks (
    ...
    completed   INTEGER,   -- no DEFAULT, no NOT NULL
    ...
);
```

No `DEFAULT` clause means SQLite's rule is: *if you omit this column from an INSERT, store `NULL`.*

Now look at the INSERT in [`services.create_task()`](app/services.py:62):

```sql
INSERT INTO tasks (title, description, tags, due_date, assignee_id, created_at)
VALUES (?, ?, ?, ?, ?, ?)
```

`completed` is absent from the column list. SQLite dutifully stores `NULL` for every newly created task.

---

### Why the overdue query silently returns nothing

The query in [`services.list_overdue_tasks()`](app/services.py:110) is:

```sql
SELECT ...
FROM tasks
WHERE due_date < '2025-...'
  AND completed = 0
```

Step through what happens for a brand-new task:

| Predicate | Value stored | Result |
|---|---|---|
| `due_date < '2025-...'` | `'2025-...' - 3 days` | **TRUE** |
| `completed = 0` | `NULL` | **NULL** |
| `TRUE AND NULL` | — | **NULL** |

`TRUE AND NULL` is `NULL` in three-valued logic — not `TRUE`. The row fails the `WHERE` test and is discarded. The result set comes back empty. No error is raised. No warning is logged. The data is there in the table; the query simply can't see it.

---

## Two Safe Ways to Repair It

### Option A — Fix the schema: add `DEFAULT 0 NOT NULL`

Change the column definition to:

```sql
completed INTEGER NOT NULL DEFAULT 0
```

New rows that omit `completed` from their INSERT now receive `0` automatically. The existing query `WHERE completed = 0` works correctly because `0 = 0` is `TRUE`.

**What happens to already-stored rows?**
SQLite's `ALTER TABLE … ADD COLUMN` can add a column with a `DEFAULT`, and from SQLite 3.37.0 onward, the default is stored in the schema and applied to existing rows on read without rewriting the table. However, this is a new column addition — the existing column already exists. To change the default and `NOT NULL` constraint on an *existing* column, SQLite requires the [table-rebuild pattern](https://www.sqlite.org/lang_altertable.html#making_other_kinds_of_table_schema_changes): create a new table with the correct schema, copy all rows, drop the old table, rename the new one. During the copy, you can write `COALESCE(completed, 0)` to normalize any existing `NULL` values to `0`.

**Trade-offs:**

| | |
|---|---|
| ✅ Strengthens the invariant at the storage layer | Every row is guaranteed to have a non-null `completed` value, enforced by the database engine itself. No application code can accidentally insert a `NULL`. |
| ✅ The existing query logic stays correct | `WHERE completed = 0` continues to work as written. |
| ✅ Future queries written by anyone are safe | A new developer writing a query cannot be surprised by `NULL` in this column. |
| ⚠️ Requires a schema migration for live databases | Existing rows with `NULL` must be backfilled. In SQLite this means the table-rebuild pattern, which needs a maintenance window on large databases. |
| ⚠️ SQLite's `ALTER TABLE` cannot change column constraints in-place | You must use the create-copy-rename dance. |

---

### Option B — Fix the query predicate: use `IS NOT 1`

Change only the SQL filter:

```sql
WHERE due_date < ?
  AND completed IS NOT 1
```

`IS NOT` (or its equivalent `IS NOT 1`) is null-safe: it returns `TRUE` when `completed` is `NULL` and when `completed = 0`, and `FALSE` only when `completed = 1`. No schema change is needed.

**What happens to already-stored rows?**
Nothing at all — the table is untouched. Existing `NULL` rows are immediately visible to the corrected query the moment the code is deployed.

**Trade-offs:**

| | |
|---|---|
| ✅ No schema migration required | Safe to deploy to a live database with existing `NULL` rows instantly. |
| ✅ Minimal blast radius | One line of SQL changes; the schema and all other queries are unaffected. |
| ⚠️ The schema invariant is still broken | `completed` can still be `NULL`. Any future query that uses `completed = 0` (a completely natural thing to write) will silently exclude uncompleted tasks again. The bug is patched at one call site but the trap remains for the next developer. |
| ⚠️ The column's meaning is now implicit | Without a `NOT NULL DEFAULT 0` constraint, a reader of the schema cannot tell whether `NULL` is intentional or accidental. |
| ⚠️ `complete_task` still stores `1`, not `0` | This is fine, but `completed` now has three observable states (`NULL`, `0`, `1`) even though only two are semantically meaningful. |

---

### Option C (bonus) — Fix both the INSERT and add a `DEFAULT` without a full migration

A middle path: keep the schema as-is (avoiding a migration) but change the INSERT to supply `completed = 0` explicitly:

```sql
INSERT INTO tasks (title, description, tags, due_date, assignee_id, completed, created_at)
VALUES (?, ?, ?, ?, ?, 0, ?)
```

**Trade-offs:**

| | |
|---|---|
| ✅ No migration needed | Existing `NULL` rows stay as-is but new rows are written correctly. |
| ⚠️ Existing rows still have `NULL` | The live database still has the bug for any tasks already stored. |
| ⚠️ Schema still allows `NULL` | Future developers (or other INSERT paths) can accidentally create `NULL` rows again. |
| ⚠️ Weakest invariant of all three | Relies entirely on application-level discipline rather than a database-level guarantee. |

---

## Recommendation

**Option A — correct the schema with `NOT NULL DEFAULT 0`** establishes the strongest invariant.

Here is the reasoning: the purpose of a relational database schema is to make illegal states unrepresentable at the storage layer. A `completed` flag on a task is a boolean — it is either completed or it is not. `NULL` ("unknown whether completed") is not a valid business state for this application. Encoding that constraint in the schema means:

- The database engine enforces it on every INSERT from every path, now and in the future.
- Any developer writing a new query can use `= 0` and `= 1` without knowing about the `NULL` trap.
- The fix is self-documenting: `INTEGER NOT NULL DEFAULT 0` communicates intent directly in the schema.

Option B is a reasonable emergency patch when a migration cannot be scheduled — it fixes the symptom immediately with zero downtime — but it should be followed by the schema migration as soon as possible. Leaving the schema broken means the next query written against this table will silently reproduce the same bug.
