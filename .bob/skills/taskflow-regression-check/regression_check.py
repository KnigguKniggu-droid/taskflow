"""
TaskFlow regression check script.

Runs the full unittest suite, then smoke-tests every endpoint in-process
using Flask's test client and reports PASS/FAIL for each check.

Usage (from the repository root, with the venv active):
    python .bob/skills/taskflow-regression-check/regression_check.py
"""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO_ROOT)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    mark = "✓" if condition else "✗"
    print(f"  {mark} [{status}] {name}" + (f"  → {detail}" if detail else ""))
    return condition


# ---------------------------------------------------------------------------
# Section 1 — full unittest suite
# ---------------------------------------------------------------------------

def run_unittest_suite():
    print("\n=== Section 1: unittest suite ===")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_tasks", "-v"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    passed = result.returncode == 0
    detail = ""
    if not passed:
        # Surface just the last few lines of stderr which contain the failure summary.
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        detail = " | ".join(lines[-5:])
    check("unittest suite (all tests)", passed, detail)


# ---------------------------------------------------------------------------
# Section 2 — in-process smoke tests via Flask test client
# ---------------------------------------------------------------------------

def run_smoke_tests():
    print("\n=== Section 2: endpoint smoke tests ===")

    # Import here so the path insertion above takes effect first.
    from app import create_app  # noqa: PLC0415

    fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        app = create_app({"TESTING": True, "DATABASE": db_path})
        client = app.test_client()

        # -- POST /users -------------------------------------------------------
        r = client.post("/users", json={"name": "Alice"})
        ok = check("POST /users → 201", r.status_code == 201, f"status={r.status_code}")
        if not ok:
            return
        alice = r.get_json()

        r2 = client.post("/users", json={"name": "Bob"})
        check("POST /users (second user) → 201", r2.status_code == 201)
        bob = r2.get_json()

        # -- POST /tasks -------------------------------------------------------
        r = client.post("/tasks", json={
            "title": "Backend task",
            "tags": ["backend", "database"],
            "due_date": (date.today() - timedelta(days=2)).isoformat(),
            "assignee_id": alice["id"],
        })
        ok = check("POST /tasks → 201", r.status_code == 201, f"status={r.status_code}")
        if not ok:
            return
        task_be = r.get_json()
        check("POST /tasks returns completed=false",
              task_be.get("completed") is False)

        r = client.post("/tasks", json={
            "title": "Frontend task",
            "tags": ["frontend"],
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "assignee_id": bob["id"],
        })
        check("POST /tasks (future task) → 201", r.status_code == 201)
        task_fe = r.get_json()

        r = client.post("/tasks", json={
            "title": "Shared backend",
            "tags": ["backend"],
            "assignee_id": bob["id"],
        })
        check("POST /tasks (no due_date) → 201", r.status_code == 201)
        task_shared = r.get_json()

        # -- GET /tasks/<id> ---------------------------------------------------
        r = client.get(f"/tasks/{task_be['id']}")
        check("GET /tasks/<id> → 200", r.status_code == 200)
        check("GET /tasks/<id> body matches",
              r.get_json()["id"] == task_be["id"])

        r = client.get("/tasks/999999")
        check("GET /tasks/<id> 404 for missing task",
              r.status_code == 404 and "error" in r.get_json())

        # -- GET /tasks --------------------------------------------------------
        r = client.get("/tasks")
        all_ids = [t["id"] for t in r.get_json()["tasks"]]
        check("GET /tasks → 200 and contains all tasks",
              r.status_code == 200 and task_be["id"] in all_ids and task_fe["id"] in all_ids)

        # -- GET /tasks?assignee_id= -------------------------------------------
        r = client.get("/tasks", query_string={"assignee_id": alice["id"]})
        alice_ids = [t["id"] for t in r.get_json()["tasks"]]
        check("GET /tasks?assignee_id filters correctly",
              task_be["id"] in alice_ids and task_fe["id"] not in alice_ids)

        # -- GET /tasks?tag= ---------------------------------------------------
        r = client.get("/tasks", query_string={"tag": "backend"})
        tag_ids = [t["id"] for t in r.get_json()["tasks"]]
        check("GET /tasks?tag=backend returns matching tasks",
              task_be["id"] in tag_ids and task_shared["id"] in tag_ids)
        check("GET /tasks?tag=backend excludes non-matching tasks",
              task_fe["id"] not in tag_ids)

        # -- substring false positive ------------------------------------------
        r = client.get("/tasks", query_string={"tag": "end"})
        sub_ids = [t["id"] for t in r.get_json()["tasks"]]
        check("GET /tasks?tag=end does NOT match 'backend' (no substring false positive)",
              task_be["id"] not in sub_ids and task_fe["id"] not in sub_ids)

        # -- combined assignee + tag filter ------------------------------------
        r = client.get("/tasks", query_string={"tag": "backend", "assignee_id": alice["id"]})
        combo_ids = [t["id"] for t in r.get_json()["tasks"]]
        check("GET /tasks?tag=backend&assignee_id=alice returns only alice's backend task",
              task_be["id"] in combo_ids
              and task_shared["id"] not in combo_ids   # bob's backend task excluded
              and task_fe["id"] not in combo_ids)

        # -- GET /tasks/overdue ------------------------------------------------
        r = client.get("/tasks/overdue")
        overdue_ids = [t["id"] for t in r.get_json()["tasks"]]
        check("GET /tasks/overdue → 200", r.status_code == 200)
        check("GET /tasks/overdue contains past-due task",
              task_be["id"] in overdue_ids)
        check("GET /tasks/overdue excludes future task",
              task_fe["id"] not in overdue_ids)
        check("GET /tasks/overdue excludes task without due_date",
              task_shared["id"] not in overdue_ids)

        # -- POST /tasks/<id>/complete -----------------------------------------
        r = client.post(f"/tasks/{task_be['id']}/complete")
        check("POST /tasks/<id>/complete → 200",
              r.status_code == 200 and r.get_json().get("completed") is True)

        # completed task must leave overdue list
        r = client.get("/tasks/overdue")
        overdue_after = [t["id"] for t in r.get_json()["tasks"]]
        check("Completed task removed from /tasks/overdue",
              task_be["id"] not in overdue_after)

        r = client.post("/tasks/999999/complete")
        check("POST /tasks/<id>/complete 404 for missing task",
              r.status_code == 404 and "error" in r.get_json())

    finally:
        os.remove(db_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("TaskFlow Regression Check")
    print("=" * 40)
    run_unittest_suite()
    run_smoke_tests()

    print("\n=== Summary ===")
    passed = sum(1 for s, _, _ in results if s == PASS)
    failed = sum(1 for s, _, _ in results if s == FAIL)
    for status, name, detail in results:
        if status == FAIL:
            print(f"  FAIL  {name}" + (f"  → {detail}" if detail else ""))
    print(f"\n{passed} passed, {failed} failed out of {len(results)} checks.")
    sys.exit(0 if failed == 0 else 1)
