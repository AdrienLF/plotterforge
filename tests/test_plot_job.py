import tempfile
import unittest
from pathlib import Path

import web.server as server


class PlotJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = server.PLOT_JOB_PATH
        self.old_cache_path = server.PLOT_PATHS_CACHE
        self.old_thread = server._plot_thread
        self.old_stop_state = server._stop_event.is_set()
        server.PLOT_JOB_PATH = Path(self.tmp.name) / "plot-job.json"
        server.PLOT_PATHS_CACHE = Path(self.tmp.name) / "plot-paths.pkl"
        server._plot_thread = None
        server._stop_event.clear()

    def tearDown(self):
        server.PLOT_JOB_PATH = self.old_path
        server.PLOT_PATHS_CACHE = self.old_cache_path
        server._plot_thread = self.old_thread
        if self.old_stop_state:
            server._stop_event.set()
        else:
            server._stop_event.clear()
        self.tmp.cleanup()

    def test_create_plot_job_persists_svg_settings_and_placement(self):
        job = server._create_plot_job(
            b"<svg></svg>",
            {"copies": 2, "speed_pendown": 1234},
            {"x": 10.5, "y": 2.25},
        )

        loaded = server._load_plot_job()

        self.assertEqual(loaded["id"], job["id"])
        self.assertEqual(server._plot_job_svg_bytes(loaded), b"<svg></svg>")
        self.assertEqual(loaded["settings"]["speed_pendown"], 1234)
        self.assertEqual(loaded["placement"], {"x": 10.5, "y": 2.25})
        self.assertEqual(loaded["next_copy"], 0)
        self.assertEqual(loaded["next_path"], 0)
        self.assertEqual(loaded["status"], "queued")

    def test_checkpoint_records_next_unfinished_path(self):
        job = server._create_plot_job(b"<svg></svg>", {"copies": 1}, {"x": 0, "y": 0})

        server._checkpoint_plot_job(
            job,
            status="running",
            total_paths=4,
            total_segments=40,
            total_shapes=4,
            next_copy=0,
            next_path=2,
            completed_shapes=2,
            completed_segments=20,
        )

        loaded = server._load_plot_job()
        self.assertEqual(loaded["next_copy"], 0)
        self.assertEqual(loaded["next_path"], 2)
        self.assertEqual(loaded["completed_shapes"], 2)
        self.assertEqual(loaded["completed_segments"], 20)
        self.assertTrue(server._plot_job_public(loaded)["resumable"])

    def test_running_job_is_reported_as_crashed_after_restart(self):
        job = server._create_plot_job(b"<svg></svg>", {"copies": 1}, {"x": 0, "y": 0})
        server._checkpoint_plot_job(
            job,
            status="running",
            total_paths=3,
            total_segments=30,
            total_shapes=3,
            next_copy=0,
            next_path=1,
            completed_shapes=1,
            completed_segments=10,
        )

        client = server.app.test_client()
        response = client.get("/api/plot/job")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["status"], "crashed")
        self.assertTrue(payload["resumable"])
        self.assertEqual(payload["shapes_remaining"], 2)

    def test_cancelled_parse_never_populates_the_paths_cache(self):
        svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
          <path d="M0 0 L10 0"/>
          <path d="M0 10 L10 10"/>
        </svg>"""
        settings = {"curve_step_mm": 0.5, "reordering": "none"}
        placement = {"x": 0.0, "y": 0.0}

        def stop_before_second(done, _total):
            if done == 1:
                server._stop_event.set()

        try:
            partial = server._resolve_polylines(
                svg, settings, placement, on_progress=stop_before_second
            )
        except RuntimeError as exc:
            self.assertEqual(str(exc), "__stopped__")
        else:
            self.fail(
                f"cancelled parse returned {len(partial)} paths; "
                f"cache_exists={server.PLOT_PATHS_CACHE.exists()}"
            )

        self.assertFalse(server.PLOT_PATHS_CACHE.exists())

        server._stop_event.clear()
        polylines = server._resolve_polylines(svg, settings, placement)

        self.assertEqual(len(polylines), 2)
        signature = server._paths_signature(svg, settings, placement)
        self.assertEqual(len(server._load_cached_polylines(signature)), 2)


if __name__ == "__main__":
    unittest.main()
