import tempfile
import unittest
from pathlib import Path

from engine import project as project_mod
import web.server as server


class ProjectsApiTest(unittest.TestCase):
    """Exercises the project endpoints against a throwaway projects dir."""

    def setUp(self):
        self._orig_dir = project_mod.PROJECTS_DIR
        self._orig_project = server._project
        self._tmp = tempfile.TemporaryDirectory()
        project_mod.PROJECTS_DIR = Path(self._tmp.name)
        # Start on a fresh project inside the temp workspace.
        server._project = project_mod.create_project("Start")
        self.client = server.app.test_client()

    def tearDown(self):
        project_mod.PROJECTS_DIR = self._orig_dir
        server._project = self._orig_project
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
        self.assertEqual(self.client.post("/api/projects/nope/open").status_code, 404)

    def test_switch_resets_transient_state(self):
        server._current_svg = b"<svg/>"
        self.client.post("/api/projects", json={"name": "Fresh"})
        self.assertIsNone(server._current_svg)


if __name__ == "__main__":
    unittest.main()
