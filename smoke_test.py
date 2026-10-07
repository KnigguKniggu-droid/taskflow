#!/usr/bin/env python3
"""Smoke test for the TaskFlow API.

Exercises the main API flows against a running server.  Uses only the Python
standard library so it works anywhere Python 3.10+ is installed.

Usage::

    # Against the local dev server (default)
    python smoke_test.py

    # Against a deployed instance
    python smoke_test.py --base-url https://<username>.pythonanywhere.com

    # Via environment variable
    BASE_URL=https://<username>.pythonanywhere.com python smoke_test.py

Exit code: 0 if all checks pass, 1 if any fail.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request(method: str, url: str, body=None):
    """Issue an HTTP request and return (status_code, parsed_json_or_None)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = None
        return exc.code, payload


def _get(base, path):
    return _request("GET", base.rstrip("/") + path)


def _post(base, path, body=None):
    return _request("POST", base.rstrip("/") + path, body)


def _patch(base, path, body):
    return _request("PATCH", base.rstrip("/") + path, body)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

class SmokeRunner:
    def __init__(self, base_url: str):
        self.base = base_url
        self._passed = 0
        self._failed = 0

    def check(self, name: str, ok: bool, detail: str = ""):
        if ok:
            self._passed += 1
            print(f"  ✓ [PASS] {name}")
        else:
            self._failed += 1
            print(f"  ✗ [FAIL] {name}" + (f" → {detail}" if detail else ""))

    def summary(self):
        total = self._passed + self._failed
        print()
        print(f"{self._passed} passed, {self._failed} failed out of {total} checks.")
        return self._failed == 0

    def run(self):
        _is_local = self.base.startswith("http://127.") or self.base.startswith("http://localhost")
        if not _is_local:
            print(
                "NOTE: running against a remote server. The smoke test creates a user\n"
                "and tasks that will remain in the target database after the run.\n"
                "Do not run this against a production instance you want to keep clean.\n"
            )
        print(f"Smoke-testing {self.base}\n")

        # 1. Health
        status, body = _get(self.base, "/health")
        self.check("GET /health → 200", status == 200, f"status={status}")
        self.check(
            'GET /health body {"status":"ok"}',
            isinstance(body, dict) and body.get("status") == "ok",
            f"body={body}",
        )

        # 2. Create a user
        status, body = _post(self.base, "/users", {"name": "Smoke Tester"})
        self.check("POST /users → 201", status == 201, f"status={status}")
        user_id = body.get("id") if isinstance(body, dict) else None
        self.check("POST /users returns id", user_id is not None, f"body={body}")

        if user_id is None:
            print("\nCannot continue without a user id.")
            self.summary()
            return False

        # 3. Create an overdue task
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        status, body = _post(
            self.base,
            "/tasks",
            {
                "title": "Smoke test task",
                "due_date": yesterday,
                "assignee_id": user_id,
                "tags": ["smoke"],
            },
        )
        self.check("POST /tasks → 201", status == 201, f"status={status}")
        task_id = body.get("id") if isinstance(body, dict) else None
        self.check("POST /tasks returns id", task_id is not None, f"body={body}")

        if task_id is None:
            print("\nCannot continue without a task id.")
            self.summary()
            return False

        # 4. List tasks
        status, body = _get(self.base, "/tasks")
        self.check("GET /tasks → 200", status == 200, f"status={status}")
        self.check(
            "GET /tasks has 'tasks' key",
            isinstance(body, dict) and "tasks" in body,
            f"body={body}",
        )

        # 5. Filter by assignee
        status, body = _get(self.base, f"/tasks?assignee_id={user_id}")
        self.check(
            "GET /tasks?assignee_id → 200", status == 200, f"status={status}"
        )
        ids = [t.get("id") for t in body.get("tasks", [])]
        self.check(
            "GET /tasks?assignee_id contains task",
            task_id in ids,
            f"ids={ids}",
        )

        # 6. Filter by tag
        status, body = _get(self.base, "/tasks?tag=smoke")
        self.check("GET /tasks?tag=smoke → 200", status == 200, f"status={status}")
        ids = [t.get("id") for t in body.get("tasks", [])]
        self.check("GET /tasks?tag=smoke contains task", task_id in ids, f"ids={ids}")

        # 7. Overdue tasks
        status, body = _get(self.base, "/tasks/overdue")
        self.check("GET /tasks/overdue → 200", status == 200, f"status={status}")
        ids = [t.get("id") for t in body.get("tasks", [])]
        self.check(
            "GET /tasks/overdue contains task", task_id in ids, f"ids={ids}"
        )

        # 8. Get single task
        status, body = _get(self.base, f"/tasks/{task_id}")
        self.check(
            f"GET /tasks/{task_id} → 200", status == 200, f"status={status}"
        )
        self.check(
            "GET /tasks/<id> returns correct id",
            isinstance(body, dict) and body.get("id") == task_id,
            f"body={body}",
        )

        # 9. Patch task
        status, body = _patch(
            self.base, f"/tasks/{task_id}", {"title": "Smoke test task (updated)"}
        )
        self.check(f"PATCH /tasks/{task_id} → 200", status == 200, f"status={status}")

        # 10. Stats
        status, body = _get(self.base, "/tasks/stats")
        self.check("GET /tasks/stats → 200", status == 200, f"status={status}")
        self.check(
            "GET /tasks/stats total >= 1",
            isinstance(body, dict) and body.get("total", 0) >= 1,
            f"body={body}",
        )

        # 11. Complete task
        status, body = _post(self.base, f"/tasks/{task_id}/complete")
        self.check(
            f"POST /tasks/{task_id}/complete → 200", status == 200, f"status={status}"
        )
        self.check(
            "complete response completed=true",
            isinstance(body, dict) and body.get("completed") is True,
            f"body={body}",
        )

        # 12. 404 for unknown task
        status, body = _get(self.base, "/tasks/999999")
        self.check("GET /tasks/999999 → 404", status == 404, f"status={status}")

        return self.summary()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TaskFlow API smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BASE_URL", "http://127.0.0.1:5000"),
        help="Base URL of the TaskFlow server (default: http://127.0.0.1:5000)",
    )
    args = parser.parse_args()

    runner = SmokeRunner(args.base_url)
    ok = runner.run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
