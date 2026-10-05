import os
import tempfile
import unittest
from datetime import date, timedelta

from app import create_app


class TaskApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def create_user(self, name="Ada"):
        response = self.client.post("/users", json={"name": name})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def create_task(self, **fields):
        response = self.client.post("/tasks", json={"title": "Write report", **fields})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def overdue_ids(self):
        response = self.client.get("/tasks/overdue")
        self.assertEqual(response.status_code, 200)
        return [task["id"] for task in response.get_json()["tasks"]]

    def test_create_task(self):
        user = self.create_user()
        task = self.create_task(
            description="Quarterly numbers",
            tags=["Backend", " database ", "backend"],
            due_date="2030-01-15",
            assignee_id=user["id"],
        )
        self.assertEqual(task["title"], "Write report")
        self.assertEqual(task["description"], "Quarterly numbers")
        self.assertEqual(task["tags"], ["backend", "database"])
        self.assertEqual(task["due_date"], "2030-01-15")
        self.assertEqual(task["assignee_id"], user["id"])
        self.assertFalse(task["completed"])

        response = self.client.get(f"/tasks/{task['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), task)

    def test_complete_task(self):
        task = self.create_task()

        response = self.client.post(f"/tasks/{task['id']}/complete")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["completed"])
        self.assertTrue(self.client.get(f"/tasks/{task['id']}").get_json()["completed"])

    def test_overdue_task_is_detected(self):
        task = self.create_task(due_date=(date.today() - timedelta(days=3)).isoformat())

        self.assertIn(task["id"], self.overdue_ids())

    def test_future_task_not_listed_as_overdue(self):
        task = self.create_task(due_date=(date.today() + timedelta(days=30)).isoformat())

        self.assertNotIn(task["id"], self.overdue_ids())

    def test_completed_overdue_task_excluded(self):
        # A task that is past due but already completed must NOT appear in the
        # overdue list.  This is the regression test for the NULL/0 bug: before
        # the fix, *no* task (completed or not) appeared because newly created
        # tasks had completed=NULL, which made `completed = 0` evaluate to NULL
        # and silently exclude every row.
        past = (date.today() - timedelta(days=1)).isoformat()
        task = self.create_task(due_date=past)
        self.client.post(f"/tasks/{task['id']}/complete")

        self.assertNotIn(task["id"], self.overdue_ids())

    def test_overdue_excludes_tasks_without_due_date(self):
        # Tasks with no due_date must never appear in the overdue list.
        task = self.create_task()

        self.assertNotIn(task["id"], self.overdue_ids())

    def test_new_task_completed_field_is_false(self):
        # Newly created tasks must report completed=False (not NULL coerced).
        # This guards the schema DEFAULT 0 invariant at the API boundary.
        task = self.create_task()

        self.assertFalse(task["completed"])
        fetched = self.client.get(f"/tasks/{task['id']}").get_json()
        self.assertFalse(fetched["completed"])
        self.assertIs(fetched["completed"], False)


class TagFilterTestCase(unittest.TestCase):
    """Tests for GET /tasks?tag=<tag> filtering."""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def _create_user(self, name="Ada"):
        r = self.client.post("/users", json={"name": name})
        self.assertEqual(r.status_code, 201)
        return r.get_json()

    def _create_task(self, **fields):
        r = self.client.post("/tasks", json={"title": "Task", **fields})
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()

    def _list_ids(self, **params):
        r = self.client.get("/tasks", query_string=params)
        self.assertEqual(r.status_code, 200, r.get_json())
        return [t["id"] for t in r.get_json()["tasks"]]

    # --- basic tag filter ---

    def test_tag_filter_returns_matching_tasks(self):
        t1 = self._create_task(tags=["backend", "database"])
        t2 = self._create_task(tags=["backend"])
        t3 = self._create_task(tags=["frontend"])

        ids = self._list_ids(tag="backend")
        self.assertIn(t1["id"], ids, ids)
        self.assertIn(t2["id"], ids, ids)
        self.assertNotIn(t3["id"], ids, ids)

    def test_tag_filter_excludes_tasks_with_no_tags(self):
        t_no_tags = self._create_task()
        t_tagged = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="backend")
        self.assertIn(t_tagged["id"], ids)
        self.assertNotIn(t_no_tags["id"], ids)

    def test_tag_filter_no_match_returns_empty(self):
        self._create_task(tags=["frontend"])

        ids = self._list_ids(tag="backend")
        self.assertEqual(ids, [])

    # --- exact membership, not substring ---

    def test_tag_filter_is_not_substring_match(self):
        """'end' must NOT match a task tagged 'backend'."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="end")
        self.assertNotIn(t["id"], ids, "'end' matched 'backend' (substring false positive)")

    def test_tag_filter_prefix_is_not_substring_match(self):
        """'back' must NOT match a task tagged 'backend'."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="back")
        self.assertNotIn(t["id"], ids, "'back' matched 'backend' (prefix false positive)")

    def test_tag_filter_middle_tag_exact_match(self):
        """A tag stored in the middle of the comma list is found exactly."""
        t = self._create_task(tags=["alpha", "beta", "gamma"])

        self.assertIn(t["id"], self._list_ids(tag="beta"))
        self.assertNotIn(t["id"], self._list_ids(tag="bet"))
        self.assertNotIn(t["id"], self._list_ids(tag="eta"))

    def test_underscore_in_tag_is_not_like_wildcard(self):
        """tag=a_b must NOT match a task whose only tag is 'axb'.

        SQLite LIKE treats '_' as a single-character wildcard; without escaping,
        ?tag=a_b would match 'axb', 'a-b', 'a0b', etc.  This is the regression
        test for the ESCAPE fix.
        """
        t_axb = self._create_task(tags=["axb"])   # should NOT match a_b
        t_a_b = self._create_task(tags=["a-b"])   # should NOT match a_b either
        t_exact = self._create_task(tags=["a_b"]) # should match

        ids = self._list_ids(tag="a_b")
        self.assertNotIn(t_axb["id"], ids, "a_b wildcard matched axb (underscore not escaped)")
        self.assertNotIn(t_a_b["id"], ids, "a_b wildcard matched a-b (underscore not escaped)")
        self.assertIn(t_exact["id"], ids, "a_b did not match a_b (exact tag missing)")

    # --- combined assignee + tag filter ---

    def test_combined_filter_assignee_and_tag(self):
        u1 = self._create_user("Alice")
        u2 = self._create_user("Bob")

        t1 = self._create_task(tags=["backend"], assignee_id=u1["id"])
        t2 = self._create_task(tags=["backend"], assignee_id=u2["id"])
        t3 = self._create_task(tags=["frontend"], assignee_id=u1["id"])

        ids = self._list_ids(tag="backend", assignee_id=u1["id"])
        self.assertIn(t1["id"], ids, ids)
        self.assertNotIn(t2["id"], ids, ids)  # wrong assignee
        self.assertNotIn(t3["id"], ids, ids)  # wrong tag

    def test_combined_filter_no_match_returns_empty(self):
        u = self._create_user()
        self._create_task(tags=["backend"])          # no assignee
        self._create_task(assignee_id=u["id"])       # no tag

        ids = self._list_ids(tag="backend", assignee_id=u["id"])
        self.assertEqual(ids, [])

    # --- assignee-only filter still works ---

    def test_assignee_only_filter_unchanged(self):
        u = self._create_user()
        t_assigned = self._create_task(assignee_id=u["id"])
        t_unassigned = self._create_task()

        ids = self._list_ids(assignee_id=u["id"])
        self.assertIn(t_assigned["id"], ids)
        self.assertNotIn(t_unassigned["id"], ids)

    # --- edge cases: empty and invalid tag parameter ---

    def test_empty_tag_param_returns_all_tasks(self):
        """A blank tag= query param is treated as 'no filter'."""
        t1 = self._create_task(tags=["backend"])
        t2 = self._create_task(tags=["frontend"])

        ids = self._list_ids(tag="")
        self.assertIn(t1["id"], ids)
        self.assertIn(t2["id"], ids)

    def test_whitespace_only_tag_param_returns_all_tasks(self):
        """A whitespace-only tag= param is treated as 'no filter'."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="   ")
        self.assertIn(t["id"], ids)

    def test_invalid_tag_param_returns_400(self):
        """A tag value that violates the tag pattern returns 400."""
        r = self.client.get("/tasks", query_string={"tag": "INVALID TAG!"})
        self.assertEqual(r.status_code, 400, r.get_json())
        self.assertIn("error", r.get_json())

    def test_invalid_tag_with_spaces_returns_400(self):
        r = self.client.get("/tasks", query_string={"tag": "has space"})
        self.assertEqual(r.status_code, 400, r.get_json())

    def test_tag_param_is_case_insensitive(self):
        """tag=Backend (uppercase) normalises to 'backend' and matches."""
        t = self._create_task(tags=["backend"])

        ids = self._list_ids(tag="Backend")
        self.assertIn(t["id"], ids)


if __name__ == "__main__":
    unittest.main()
