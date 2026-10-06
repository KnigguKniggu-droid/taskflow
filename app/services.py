"""Business logic for users and tasks.

Routes translate HTTP requests into calls to these functions; nothing in this
module knows about HTTP.
"""

import re
from datetime import date, datetime, timezone

from .db import get_db

MAX_ID = 2**63 - 1  # largest value an SQLite INTEGER column can hold
MAX_NAME_LENGTH = 100
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_TAGS = 10
TAG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
DUE_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
USER_FIELDS = frozenset({"name"})
TASK_FIELDS = frozenset({"title", "description", "tags", "due_date", "assignee_id", "status"})

VALID_STATUSES = frozenset({"open", "in_progress", "blocked", "completed"})

# Valid transitions: {from_status: frozenset of allowed to_statuses}
VALID_TRANSITIONS = {
    "open":        frozenset({"in_progress", "blocked", "completed"}),
    "in_progress": frozenset({"open", "blocked", "completed"}),
    "blocked":     frozenset({"open", "in_progress", "completed"}),
    "completed":   frozenset({"open"}),
}

SELECT_TASKS = (
    "SELECT id, title, description, tags, due_date, assignee_id, completed, status, created_at"
    " FROM tasks"
)


class ValidationError(Exception):
    """Client-supplied data is invalid; the message is safe to return to the client."""


class NotFoundError(Exception):
    """The requested resource does not exist."""


class TransitionError(Exception):
    """The requested status transition is not permitted."""


def create_user(data):
    """Create a user from a request payload and return it."""
    _reject_unknown_fields(data, USER_FIELDS)
    name = _required_text(data, "name", MAX_NAME_LENGTH)
    db = get_db()
    with db:
        cursor = db.execute("INSERT INTO users (name) VALUES (?)", (name,))
    return {"id": cursor.lastrowid, "name": name}


def list_users():
    """Return all users ordered by id."""
    rows = get_db().execute("SELECT id, name FROM users ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def get_task_stats(today):
    """Return task counts: total, open, in_progress, blocked, completed, overdue.

    ``today`` is a ``datetime.date`` used to determine the overdue cutoff.
    A task is overdue when it has a non-completed status, has a due_date, and
    that date is before ``today``.

    The ``open`` key retains its historical meaning (tasks that are not
    completed) so existing clients that only read ``open`` and ``completed``
    are unaffected.  New clients can read the per-status breakdown.
    """
    row = get_db().execute(
        "SELECT"
        " COUNT(*) AS total,"
        " SUM(CASE WHEN status = 'open'        THEN 1 ELSE 0 END) AS cnt_open,"
        " SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) AS cnt_in_progress,"
        " SUM(CASE WHEN status = 'blocked'     THEN 1 ELSE 0 END) AS cnt_blocked,"
        " SUM(CASE WHEN status = 'completed'   THEN 1 ELSE 0 END) AS cnt_completed,"
        " SUM(CASE WHEN status != 'completed' AND due_date IS NOT NULL AND due_date < ?"
        "          THEN 1 ELSE 0 END) AS overdue"
        " FROM tasks",
        (today.isoformat(),),
    ).fetchone()
    cnt_open        = row["cnt_open"]        or 0
    cnt_in_progress = row["cnt_in_progress"] or 0
    cnt_blocked     = row["cnt_blocked"]     or 0
    cnt_completed   = row["cnt_completed"]   or 0
    return {
        "total":       row["total"] or 0,
        # "open" = all non-completed (backward-compatible)
        "open":        cnt_open + cnt_in_progress + cnt_blocked,
        "in_progress": cnt_in_progress,
        "blocked":     cnt_blocked,
        "completed":   cnt_completed,
        "overdue":     row["overdue"] or 0,
    }


def create_task(data):
    """Validate a request payload, store the task and return it."""
    _reject_unknown_fields(data, TASK_FIELDS)
    title = _required_text(data, "title", MAX_TITLE_LENGTH)
    description = _optional_text(data, "description", MAX_DESCRIPTION_LENGTH)
    tags = normalize_tags(data.get("tags"))
    due_date = parse_due_date(data.get("due_date"))
    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        assignee_id = parse_id(assignee_id, "assignee_id")
        if not _user_exists(assignee_id):
            raise ValidationError("assignee_id does not match an existing user")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    db = get_db()
    with db:
        cursor = db.execute(
            "INSERT INTO tasks (title, description, tags, due_date, assignee_id, completed, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, 0, 'open', ?)",
            (title, description, tags, due_date, assignee_id, created_at),
        )
        task_id = cursor.lastrowid
        db.execute(
            "INSERT INTO task_activity (task_id, event, detail, created_at) VALUES (?, ?, ?, ?)",
            (task_id, "created", "", created_at),
        )
    return get_task(task_id)


def get_task(task_id):
    """Return one task, or raise NotFoundError."""
    row = None
    if 0 < task_id <= MAX_ID:
        row = get_db().execute(SELECT_TASKS + " WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"task {task_id} not found")
    return _task_to_dict(row)


def list_tasks(assignee_id=None, tag=None):
    """Return all tasks, optionally filtered by ``assignee_id`` and/or ``tag``.

    ``tag`` is matched as exact tag membership: a task must contain the tag as a
    whole token in its comma-separated ``tags`` column, not as a substring of
    another tag.
    """
    conditions = []
    params = []
    if assignee_id is not None:
        conditions.append("assignee_id = ?")
        params.append(assignee_id)
    if tag is not None:
        # Wrap both sides with commas so every stored tag has a leading and
        # trailing comma delimiter regardless of its position in the list.
        # e.g. tags="backend,database" → ",backend,database," LIKE "%,backend,%"
        #
        # SQLite LIKE treats '_' as a single-character wildcard and '%' as a
        # multi-character wildcard.  Tags may legally contain '_' (TAG_PATTERN
        # allows it), so we must escape both metacharacters in the tag value
        # before embedding it in the pattern.  We use '\' as the escape char.
        escaped_tag = tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append("(',' || tags || ',') LIKE ('%,' || ? || ',%') ESCAPE '\\'")
        params.append(escaped_tag)

    query = SELECT_TASKS
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    return [_task_to_dict(row) for row in get_db().execute(query, params)]


def update_task(task_id, data):
    """Partially update a task and return it, or raise NotFoundError / ValidationError.

    Only keys present in *data* are updated.  Passing ``{"due_date": null}``
    explicitly clears the due date; omitting the key leaves it unchanged.
    ``completed`` and ``created_at`` are not accepted (rejected by
    _reject_unknown_fields).
    """
    if not 0 < task_id <= MAX_ID:
        raise NotFoundError(f"task {task_id} not found")

    _reject_unknown_fields(data, TASK_FIELDS)

    if not data:
        # No-op: validate the task exists then return unchanged.
        return get_task(task_id)

    db = get_db()

    # Fetch the current task to validate transitions and build activity detail.
    current_row = db.execute(SELECT_TASKS + " WHERE id = ?", (task_id,)).fetchone()
    if current_row is None:
        raise NotFoundError(f"task {task_id} not found")
    current = _task_to_dict(current_row)

    columns = []
    values = []
    activity_rows = []  # list of (event, detail) tuples
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # --- status ---
    if "status" in data:
        new_status = data["status"]
        if not isinstance(new_status, str) or new_status not in VALID_STATUSES:
            raise ValidationError(
                f"status must be one of: {', '.join(sorted(VALID_STATUSES))}"
            )
        old_status = current["status"]
        if new_status != old_status:
            allowed = VALID_TRANSITIONS.get(old_status, frozenset())
            if new_status not in allowed:
                raise TransitionError(
                    f"invalid status transition: {old_status} → {new_status}"
                )
            columns.append("status = ?")
            values.append(new_status)
            # Keep completed in sync
            columns.append("completed = ?")
            values.append(1 if new_status == "completed" else 0)
            activity_rows.append(("status_changed", f"{old_status} → {new_status}"))

    # --- details (title, description, tags) ---
    details_changed = []

    if "title" in data:
        new_val = _required_text(data, "title", MAX_TITLE_LENGTH)
        if new_val != current["title"]:
            columns.append("title = ?")
            values.append(new_val)
            details_changed.append("title")

    if "description" in data:
        new_val = _optional_text(data, "description", MAX_DESCRIPTION_LENGTH)
        if new_val != current["description"]:
            columns.append("description = ?")
            values.append(new_val)
            details_changed.append("description")

    if "tags" in data:
        new_val = normalize_tags(data["tags"])
        if new_val != current_row["tags"]:
            columns.append("tags = ?")
            values.append(new_val)
            details_changed.append("tags")

    if details_changed:
        activity_rows.append(("details_edited", ", ".join(details_changed) + " updated"))

    # --- due_date ---
    if "due_date" in data:
        if data["due_date"] is None:
            new_val = None
        else:
            new_val = parse_due_date(data["due_date"])
        if new_val != current["due_date"]:
            columns.append("due_date = ?")
            values.append(new_val)
            if new_val is None:
                activity_rows.append(("due_date_changed", "due date cleared"))
            else:
                activity_rows.append(("due_date_changed", f"due date set to {new_val}"))

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

    if not columns:
        # All supplied values were identical to existing — still a no-op.
        return get_task(task_id)

    values.append(task_id)
    sql = "UPDATE tasks SET " + ", ".join(columns) + " WHERE id = ?"

    with db:
        cursor = db.execute(sql, values)
        if cursor.rowcount == 0:
            raise NotFoundError(f"task {task_id} not found")
        for event, detail in activity_rows:
            db.execute(
                "INSERT INTO task_activity (task_id, event, detail, created_at) VALUES (?, ?, ?, ?)",
                (task_id, event, detail, now),
            )
    return get_task(task_id)


def complete_task(task_id):
    """Mark a task as completed and return it, or raise NotFoundError."""
    if not 0 < task_id <= MAX_ID:
        raise NotFoundError(f"task {task_id} not found")
    db = get_db()

    current_row = db.execute(
        "SELECT status FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if current_row is None:
        raise NotFoundError(f"task {task_id} not found")

    old_status = current_row["status"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with db:
        cursor = db.execute(
            "UPDATE tasks SET completed = 1, status = 'completed' WHERE id = ?",
            (task_id,),
        )
        if cursor.rowcount == 0:
            raise NotFoundError(f"task {task_id} not found")
        # Write activity only when the status actually changed.
        if old_status != "completed":
            db.execute(
                "INSERT INTO task_activity (task_id, event, detail, created_at) VALUES (?, ?, ?, ?)",
                (task_id, "status_changed", f"{old_status} → completed", now),
            )
    return get_task(task_id)


def get_task_activity(task_id):
    """Return activity rows for a task (oldest first), or raise NotFoundError."""
    if not 0 < task_id <= MAX_ID:
        raise NotFoundError(f"task {task_id} not found")
    db = get_db()
    # Verify the task exists
    row = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"task {task_id} not found")
    rows = db.execute(
        "SELECT id, event, detail, created_at FROM task_activity"
        " WHERE task_id = ? ORDER BY id ASC",
        (task_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_overdue_tasks(today):
    """Return open tasks whose due date is before ``today`` (a ``datetime.date``)."""
    rows = get_db().execute(
        SELECT_TASKS + " WHERE due_date < ? AND status != 'completed' ORDER BY due_date, id",
        (today.isoformat(),),
    )
    return [_task_to_dict(row) for row in rows]


def normalize_tags(raw):
    """Return tags as comma-joined text: trimmed, lowercased and de-duplicated.

    Accepts a list of strings or a single comma-separated string.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        items = raw
    else:
        raise ValidationError("tags must be a list of strings or a comma-separated string")

    tags = []
    for item in items:
        tag = item.strip().lower()
        if not tag:
            continue
        if not TAG_PATTERN.fullmatch(tag):
            raise ValidationError(
                f"invalid tag {item.strip()!r}: a tag starts with a letter or digit and uses "
                "only a-z, 0-9, '-' or '_' (at most 32 characters)"
            )
        if tag not in tags:
            tags.append(tag)
            if len(tags) > MAX_TAGS:
                raise ValidationError(f"a task can have at most {MAX_TAGS} tags")
    return ",".join(tags)


def parse_due_date(raw):
    """Validate an optional YYYY-MM-DD due date and return it in that form."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not DUE_DATE_PATTERN.fullmatch(raw):
        raise ValidationError("due_date must be a date in YYYY-MM-DD format")
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise ValidationError("due_date must be a valid calendar date") from None


def parse_id(value, field):
    """Validate an id supplied in a JSON payload."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= MAX_ID:
        raise ValidationError(f"{field} must be a positive integer")
    return value


def parse_id_param(raw, field):
    """Validate an optional id supplied as a query-string value."""
    if raw is None:
        return None
    # The length check keeps int() away from huge digit strings.
    if not (raw.isascii() and raw.isdigit()) or len(raw) > len(str(MAX_ID)):
        raise ValidationError(f"{field} must be a positive integer")
    return parse_id(int(raw), field)


def parse_tag_param(raw):
    """Validate an optional tag supplied as a query-string value.

    Returns the normalised tag string, or ``None`` if the parameter was absent
    or blank (blank → treat as "no filter").  Raises ``ValidationError`` for a
    non-blank value that is not a valid tag.
    """
    if raw is None:
        return None
    tag = raw.strip().lower()
    if not tag:
        return None
    if not TAG_PATTERN.fullmatch(tag):
        display = raw.strip()[:50]
        raise ValidationError(
            f"invalid tag {display!r}: a tag starts with a letter or digit and uses "
            "only a-z, 0-9, '-' or '_' (at most 32 characters)"
        )
    return tag


def _user_exists(user_id):
    row = get_db().execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
    return row is not None


def _get_user_name(user_id):
    """Return the name of a user by id, or a fallback string if not found."""
    row = get_db().execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["name"] if row else f"user {user_id}"


def _reject_unknown_fields(data, allowed):
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValidationError("unknown field(s): " + ", ".join(unknown[:5]))


def _required_text(data, field, max_length):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required and must be a non-empty string")
    return _checked_text(value.strip(), field, max_length)


def _optional_text(data, field, max_length):
    value = data.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    return _checked_text(value.strip(), field, max_length)


def _checked_text(value, field, max_length):
    if len(value) > max_length:
        raise ValidationError(f"{field} must be at most {max_length} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        # JSON can carry lone surrogate escapes, which cannot be encoded as UTF-8 for SQLite.
        raise ValidationError(f"{field} must be valid Unicode text") from None
    return value


def _task_to_dict(row):
    status = row["status"] if "status" in row.keys() else "open"
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "tags": row["tags"].split(",") if row["tags"] else [],
        "due_date": row["due_date"],
        "assignee_id": row["assignee_id"],
        "status": status,
        "completed": status == "completed",
        "created_at": row["created_at"],
    }
