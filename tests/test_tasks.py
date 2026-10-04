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


if __name__ == "__main__":
    unittest.main()
