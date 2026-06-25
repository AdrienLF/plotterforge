import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GpuLaunchTest(unittest.TestCase):
    def test_web_run_uses_gpu_extra_by_default(self):
        run_sh = (ROOT / "web/run.sh").read_text()

        self.assertIn("uv run --extra gpu", run_sh)

    def test_readme_studio_command_uses_gpu_extra_by_default(self):
        readme = (ROOT / "README.md").read_text()

        self.assertIn("uv sync --extra gpu", readme)
        self.assertIn("uv run --extra gpu python -m web.server", readme)


if __name__ == "__main__":
    unittest.main()
