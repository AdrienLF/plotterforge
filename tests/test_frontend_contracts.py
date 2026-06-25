import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractsTest(unittest.TestCase):
    def test_svg_upload_does_not_trigger_plot_estimate(self):
        api_ts = (ROOT / "frontend/src/lib/api.ts").read_text()
        match = re.search(
            r"async uploadSvg\(file: File\) \{(?P<body>.*?)\n  \},",
            api_ts,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        self.assertNotIn("refreshEstimate", match.group("body"))

    def test_export_menu_uses_visible_layers_not_stats(self):
        menu = (ROOT / "frontend/src/components/MenuBar.svelte").read_text()

        self.assertIn("disabled={!studio.hasVisibleLayers}", menu)
        self.assertNotIn("disabled={!studio.stats}", menu)


if __name__ == "__main__":
    unittest.main()
