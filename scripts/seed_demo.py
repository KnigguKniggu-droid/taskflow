#!/usr/bin/env python3
"""
seed_demo.py — Load a deterministic, realistic demo dataset into a TaskFlow instance.

Usage:
    python scripts/seed_demo.py [--base-url URL]

Options:
    --base-url URL    Base URL of a running TaskFlow server.
                      Defaults to http://127.0.0.1:5000
    --help            Show this help message and exit.

Examples:
    # Seed the local dev server
    python scripts/seed_demo.py

    # Seed a deployed PythonAnywhere instance
    python scripts/seed_demo.py --base-url https://kltamu.pythonanywhere.com

The script is idempotent in its own run but does NOT check for pre-existing data.
Run it against a fresh (empty) database for best results.  See README.md for how
to reset the database on PythonAnywhere before seeding.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Demo dataset definition
# ---------------------------------------------------------------------------

USERS = [
    "Alice Chen",
    "Bob Okafor",
    "Carla Díaz",
    "Dan Park",
]

# today() is called once per run so relative dates stay stable
def _today():
    return date.today()

def _iso(d):
    return d.isoformat()

def _tasks(today, user_ids):
    alice, bob, carla, dan = user_ids

    return [
        # ── Open tasks (not yet started) ─────────────────────────────────
        {
            "title": "Write API documentation for v2 endpoints",
            "description": (
                "Document all new endpoints introduced in v2, including request "
                "and response shapes, error codes, and example curl commands."
            ),
            "tags": ["docs", "api", "backend"],
            "due_date": _iso(today + timedelta(days=7)),
            "assignee_id": alice,
        },
        {
            "title": "Add rate-limiting middleware",
            "description": "Prevent API abuse by capping requests per IP per minute.",
            "tags": ["backend", "security"],
            "due_date": _iso(today + timedelta(days=14)),
            "assignee_id": bob,
        },
        {
            "title": "Design new onboarding flow",
            "description": "Wireframes and copy for the 3-step onboarding wizard.",
            "tags": ["design", "ux"],
            "due_date": _iso(today + timedelta(days=10)),
            "assignee_id": carla,
        },

        # ── In-progress tasks ────────────────────────────────────────────
        {
            "title": "Migrate CI pipeline to GitHub Actions",
            "description": (
                "Replace the legacy Jenkins setup with GitHub Actions workflows for "
                "lint, test, and deploy stages."
            ),
            "tags": ["devops", "ci"],
            "due_date": _iso(today + timedelta(days=3)),
            "assignee_id": dan,
            "_status": "in_progress",
        },
        {
            "title": "Implement tag-autocomplete in the UI",
            "description": "Show previously used tags as suggestions when typing in the tag field.",
            "tags": ["frontend", "ux"],
            "due_date": _iso(today + timedelta(days=5)),
            "assignee_id": alice,
            "_status": "in_progress",
        },

        # ── Blocked tasks ────────────────────────────────────────────────
        {
            "title": "Integrate payment gateway",
            "description": (
                "Connect Stripe for subscription billing.  "
                "Blocked on legal approval of ToS update."
            ),
            "tags": ["backend", "billing"],
            "due_date": _iso(today + timedelta(days=21)),
            "assignee_id": bob,
            "_status": "blocked",
        },

        # ── Overdue tasks (open, past due date) ──────────────────────────
        {
            "title": "Fix CSV export encoding bug",
            "description": "Non-ASCII characters are garbled in exported CSV files on Windows.",
            "tags": ["bug", "backend"],
            "due_date": _iso(today - timedelta(days=3)),
            "assignee_id": carla,
        },
        {
            "title": "Update privacy policy page",
            "description": "Reflect GDPR/CCPA changes agreed with legal team last quarter.",
            "tags": ["legal", "frontend"],
            "due_date": _iso(today - timedelta(days=8)),
            "assignee_id": dan,
        },
        {
            "title": "Resolve flaky integration test in auth module",
            "description": (
                "test_token_refresh intermittently fails under load.  "
                "Suspected race condition in the token store."
            ),
            "tags": ["testing", "backend"],
            "due_date": _iso(today - timedelta(days=1)),
            "assignee_id": alice,
        },

        # ── Overdue + in-progress ────────────────────────────────────────
        {
            "title": "Refactor database connection pool",
            "description": "Replace per-request connections with a thread-safe pool to improve throughput.",
            "tags": ["backend", "performance"],
            "due_date": _iso(today - timedelta(days=5)),
            "assignee_id": bob,
            "_status": "in_progress",
        },

        # ── Completed tasks ──────────────────────────────────────────────
        {
            "title": "Set up production monitoring",
            "description": "Configure uptime alerts and error-rate dashboards in Grafana.",
            "tags": ["devops", "monitoring"],
            "due_date": _iso(today - timedelta(days=10)),
            "assignee_id": dan,
            "_status": "completed",
        },
        {
            "title": "Write regression test suite for tag filter",
            "description": "Cover exact-match, case-normalisation, combined filter, and false-positive guard.",
            "tags": ["testing", "backend"],
            "due_date": _iso(today - timedelta(days=7)),
            "assignee_id": alice,
            "_status": "completed",
        },
        {
            "title": "Deploy v1.0 to PythonAnywhere",
            "description": "First production deployment including WSGI config and health check.",
            "tags": ["devops"],
            "assignee_id": carla,
            "_status": "completed",
        },
    ]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _request(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        try:
            detail = json.loads(body_bytes).get("error", body_bytes.decode())
        except Exception:
            detail = body_bytes.decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {detail}") from exc


def post(base, path, body):
    return _request("POST", base.rstrip("/") + path, body)


def patch(base, path, body):
    return _request("PATCH", base.rstrip("/") + path, body)


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------

def seed(base_url):
    print(f"Seeding demo data → {base_url}")

    # ── 1. Health check ──────────────────────────────────────────────────
    try:
        _request("GET", base_url.rstrip("/") + "/health")
        print("  ✓ Server is up")
    except Exception as exc:
        print(f"  ✗ Server health check failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── 2. Create users ──────────────────────────────────────────────────
    print(f"  Creating {len(USERS)} users …")
    user_ids = []
    for name in USERS:
        # API returns the user object directly: {"id": ..., "name": ...}
        result = post(base_url, "/users", {"name": name})
        uid = result["id"]
        user_ids.append(uid)
        print(f"    + User #{uid}: {name}")

    # ── 3. Create tasks ──────────────────────────────────────────────────
    today = _today()
    task_specs = _tasks(today, user_ids)
    print(f"  Creating {len(task_specs)} tasks …")

    for spec in task_specs:
        # Separate internal control key from API fields
        desired_status = spec.pop("_status", None)

        # API returns the task object directly: {"id": ..., "title": ..., ...}
        result = post(base_url, "/tasks", spec)
        task = result
        tid = task["id"]
        print(f"    + Task #{tid}: {task['title']!r}")

        # ── 4. Advance status if needed ──────────────────────────────────
        if desired_status and desired_status != "open":
            # Drive through the lifecycle in a sensible sequence
            transitions = _status_path("open", desired_status)
            for target in transitions:
                if target == "completed":
                    # Use the dedicated complete endpoint so the activity
                    # log records a 'completed' event (not just status_changed)
                    post(base_url, f"/tasks/{tid}/complete", {})
                else:
                    patch(base_url, f"/tasks/{tid}", {"status": target})
                print(f"      → {target}")

    print(f"\nDone — {len(USERS)} users, {len(task_specs)} tasks seeded.")


def _status_path(src, dst):
    """Return the shortest ordered list of status values to reach `dst` from `src`."""
    # All valid one-step transitions (mirrors server VALID_TRANSITIONS)
    edges = {
        "open":        {"in_progress", "blocked", "completed"},
        "in_progress": {"open", "blocked", "completed"},
        "blocked":     {"open", "in_progress", "completed"},
        "completed":   {"open"},
    }
    if dst in edges.get(src, set()):
        return [dst]
    # BFS for longer paths (shouldn't be needed given the current graph)
    from collections import deque
    queue = deque([[src]])
    while queue:
        path = queue.popleft()
        for nxt in edges.get(path[-1], set()):
            new_path = path + [nxt]
            if nxt == dst:
                return new_path[1:]  # drop the source
            queue.append(new_path)
    raise ValueError(f"No transition path from {src!r} to {dst!r}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Seed a deterministic demo dataset into a TaskFlow instance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5000",
        help="Base URL of the TaskFlow server (default: http://127.0.0.1:5000)",
    )
    args = parser.parse_args()
    seed(args.base_url)


if __name__ == "__main__":
    main()
