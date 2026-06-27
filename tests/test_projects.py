import queue
import tempfile
import unittest
from pathlib import Path

from engine import project as project_mod
import web.server as server


class AliveThread:
    def is_alive(self):
        return True


class ProjectsApiTest(unittest.TestCase):
    """Exercises the project endpoints against a throwaway projects dir."""

    def setUp(self):
        self._orig_dir = project_mod.PROJECTS_DIR
        self._orig_project = server._project
        self._orig_process_thread = server._process_thread
        self._orig_plot_thread = server._plot_thread
        self._orig_subscribers = server._subscribers
        self._orig_last_events = server._last_events
        self._tmp = tempfile.TemporaryDirectory()
        project_mod.PROJECTS_DIR = Path(self._tmp.name)
        # Start on a fresh project inside the temp workspace.
        server._project = project_mod.create_project("Start")
        server._process_thread = None
        server._plot_thread = None
        server._subscribers = set()
        server._last_events = {}
        self.client = server.app.test_client()

    def tearDown(self):
        project_mod.PROJECTS_DIR = self._orig_dir
        server._project = self._orig_project
        server._process_thread = self._orig_process_thread
        server._plot_thread = self._orig_plot_thread
        server._subscribers = self._orig_subscribers
        server._last_events = self._orig_last_events
        self._tmp.cleanup()

    def test_create_open_rename_delete_flow(self):
        a = self.client.post("/api/projects", json={"name": "Alpha"}).get_json()
        self.assertEqual(a["current"]["name"], "Alpha")
        aid = a["current"]["id"]

        b = self.client.post("/api/projects", json={"name": "Beta"}).get_json()
        bid = b["current"]["id"]
        self.assertEqual(b["current"]["name"], "Beta")
        self.assertGreaterEqual(len(b["projects"]), 2)

        # Open Alpha again.
        opened = self.client.post(f"/api/projects/{aid}/open").get_json()
        self.assertEqual(opened["current"]["id"], aid)
        self.assertEqual(server._project.id, aid)

        # Rename current.
        renamed = self.client.patch(f"/api/projects/{aid}", json={"name": "Alpha2"}).get_json()
        self.assertEqual(renamed["current"]["name"], "Alpha2")

        # Delete current → switches to another existing project.
        deleted = self.client.delete(f"/api/projects/{aid}").get_json()
        self.assertNotEqual(deleted["current"]["id"], aid)
        ids = [p["id"] for p in deleted["projects"]]
        self.assertNotIn(aid, ids)
        self.assertIn(bid, ids)

    def test_open_unknown_project_404s(self):
        server._process_thread = AliveThread()
        self.assertEqual(self.client.post("/api/projects/nope/open").status_code, 404)

    def test_create_is_blocked_while_processing(self):
        current_id = server._project.id
        project_ids = [project["id"] for project in project_mod.list_projects()]
        server._process_thread = AliveThread()

        response = self.client.post("/api/projects", json={"name": "Blocked"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(server._project.id, current_id)
        self.assertEqual(
            [project["id"] for project in project_mod.list_projects()],
            project_ids,
        )

    def test_open_is_blocked_while_plotting(self):
        current_id = server._project.id
        target = project_mod.create_project("Target")
        server._plot_thread = AliveThread()

        response = self.client.post(f"/api/projects/{target.id}/open")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(server._project.id, current_id)

    def test_switch_resets_transient_state(self):
        server._current_svg = b"<svg/>"
        self.client.post("/api/projects", json={"name": "Fresh"})
        self.assertIsNone(server._current_svg)

    def test_switch_clears_transient_events(self):
        subscriber = server._subscribe_events()
        server.emit("proc", state="running")
        server.emit("state", state="drawing")

        self.client.post("/api/projects", json={"name": "Fresh"})

        self.assertEqual(server._last_events, {})
        with self.assertRaises(queue.Empty):
            subscriber.get_nowait()


if __name__ == "__main__":
    unittest.main()
