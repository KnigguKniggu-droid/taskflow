# Changelog

All notable changes to TaskFlow are recorded here.

---

## [Unreleased] — Bob session (2026-10)

### Fixed

- **Overdue query broken by NULL `completed` values** — The `completed` column
  was defined as `INTEGER` (nullable) with no `DEFAULT`. SQLite stores `NULL`
  when a value is omitted from an `INSERT`; the overdue query filters
  `WHERE completed = 0`, and `NULL = 0` evaluates to `NULL` (falsy), so every
  newly created task was silently excluded from `GET /tasks/overdue`.

  Two complementary fixes were applied:

  1. The schema was updated to `completed INTEGER NOT NULL DEFAULT 0`, and
     `init_db` now runs a backfill `UPDATE tasks SET completed = 0 WHERE
     completed IS NULL` so that any rows created before the migration are
     corrected when the application next starts.

  2. `create_task` in `services.py` now always supplies `completed = 0`
     explicitly in the `INSERT` column list. This ensures the stored value is
     always `0` even on databases created with the old nullable schema, where
     `CREATE TABLE IF NOT EXISTS` cannot retroactively add the `DEFAULT`.

### Added

- **Tag filter for `GET /tasks`** — A new `?tag=<tag>` query parameter filters
  the task list to tasks that carry the given tag as an exact, whole-token
  match. Partial matches are rejected: `?tag=back` does not match a task tagged
  `backend`. Matching is case-insensitive (the value is normalised to lowercase
  before comparison). A blank value is treated as no filter; an invalid value
  returns `400`. The filter combines with the existing `?assignee_id=` filter.

  Implementation:
  - `parse_tag_param(raw)` in `services.py` validates and normalises the query
    parameter.
  - `list_tasks(tag=)` in `services.py` applies an exact-match SQL `LIKE` with
    comma-delimiters and an `ESCAPE` clause to prevent `_` and `%` in tag names
    from acting as SQLite wildcards.
  - `GET /tasks` in `routes.py` reads the `?tag=` parameter and forwards it to
    `list_tasks`.

### Tests

- **`TagFilterTestCase`** (15 tests) — covers the happy path, exact-match
  semantics, substring false-positive guards, underscore wildcard escaping,
  combined `assignee_id + tag` filtering, blank/whitespace/invalid parameter
  handling, and case normalisation.
- **`SchemaInitTestCase`** (2 tests) — tests `db.init_db` directly: verifies
  that a fresh database stores `0` for `completed` by default, and that the
  backfill `UPDATE` zeroes any `NULL` rows in a pre-migration database.
- **`OldSchemaRegressionTestCase`** (2 tests) — end-to-end regression for the
  existing-database defect: seeds a temp file with the old nullable schema,
  starts the app, creates a task, and asserts both that the raw stored value is
  `0` (not `NULL`) and that the task appears in `GET /tasks/overdue`.
- Additional assertions in `TaskApiTestCase`: completed tasks are excluded from
  the overdue list; tasks without a due date never appear in the overdue list;
  new tasks report `completed: false` at the API boundary.

### Bob project tooling (`.bob/`)

The following IBM Bob project files were added under `.bob/` to support
ongoing AI-assisted development of this repository:

- **`.bob/skills/taskflow-api-review/SKILL.md`** — Checklist-driven skill for
  reviewing TaskFlow route, service, and SQL changes against project conventions
  (parameterised SQL, validation placement, JSON error format, status codes,
  exact tag matching, test coverage).
- **`.bob/skills/taskflow-regression-check/SKILL.md`** and
  **`regression_check.py`** — Skill and script that run the full `unittest`
  suite and smoke-test every API endpoint in-process, then report a pass/fail
  summary.
- **`.bob/skills/verify-taskflow/SKILL.md`** — Skill for running a parallel
  four-axis review (API correctness, test quality, documentation consistency,
  security/SQL) via subagents, then accepting or rejecting findings and
  committing fixes.
- **`.bob/commands/verify-taskflow.md`** — Bob slash-command that activates the
  regression-check skill and runs the full regression check.
- **`.bob/custom_modes.yaml`** — Defines the `TaskFlow Reviewer` Bob mode: a
  read-only reviewer persona that lists findings with file and line references
  but never edits source files.
