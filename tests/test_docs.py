from __future__ import annotations

import re
import html
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "web" / "static" / "docs"
CORE_PAGES = (
    "index.html",
    "create.html",
    "compose.html",
    "fields.html",
    "plot.html",
    "tessellations.html",
)
ALL_PAGES = tuple(path.name for path in sorted(DOCS.glob("*.html")))


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.main_count = 0
        self.main_depth = 0
        self.scripts: list[str] = []
        self.descriptions: list[str] = []
        self.article_tags_outside_main: list[str] = []
        self.footers_inside_main = 0
        self.div_depth = 0
        self.unclosed_divs_at_main_end = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if tag == "div":
            self.div_depth += 1
        if tag == "main":
            self.main_count += 1
            self.main_depth += 1
        elif tag in {"h2", "h3", "figure", "footer"}:
            if self.main_depth == 0:
                self.article_tags_outside_main.append(tag)
            elif tag == "footer":
                self.footers_inside_main += 1
        elif tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        elif tag == "meta" and values.get("name") == "description":
            self.descriptions.append(values.get("content", "").strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "div":
            self.div_depth -= 1
        elif tag == "main" and self.main_depth:
            self.unclosed_divs_at_main_end = self.div_depth
            self.main_depth -= 1


def parse_page(name: str) -> PageParser:
    parser = PageParser()
    parser.feed((DOCS / name).read_text(encoding="utf-8"))
    return parser


def test_core_manual_pages_use_the_shared_accessible_shell():
    descriptions = []
    for name in CORE_PAGES:
        page = parse_page(name)
        assert page.main_count == 1, name
        assert "docs.js" in page.scripts, name
        assert len(page.descriptions) == 1, name
        assert len(page.descriptions[0]) >= 50, name
        descriptions.extend(page.descriptions)
    assert len(descriptions) == len(set(descriptions))


def test_shared_shell_exposes_navigation_search_toc_and_keyboard_access():
    source = (DOCS / "docs.js").read_text(encoding="utf-8")
    for contract in (
        "window.PLOTTER_DOCS_PAGES",
        "docs-sidebar",
        "docs-search-dialog",
        "docs-toc",
        "aria-current",
        "skip-link",
        'event.key === "/"',
        ".focus()",
    ):
        assert contract in source

    assert 'main.classList.contains("reference-page")' in source

    registered = set(re.findall(r'href:\s*"([^"]+\.html)"', source))
    assert set(CORE_PAGES) <= registered


def test_shell_styles_cover_focus_responsive_and_print_modes():
    css = (DOCS / "docs.css").read_text(encoding="utf-8")
    for contract in (
        ":focus-visible",
        ".docs-shell",
        ".docs-sidebar",
        ".docs-search-dialog",
        "@media (max-width: 900px)",
        "@media print",
    ):
        assert contract in css


def page_text(name: str) -> str:
    class TextParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    parser = TextParser()
    parser.feed((DOCS / name).read_text(encoding="utf-8"))
    return " ".join(" ".join(parser.parts).split())


def test_flagship_tutorials_are_reproducible_from_source_to_preflight():
    text = page_text("tutorials.html")
    for contract in (
        "Download the tutorial source",
        "Photo → Voronoi Stippling → SVG",
        "Generator → multi-pen poster",
        "Image → Shape Dither",
        "Exact settings",
        "Checkpoint",
        "Expected result",
        "Export SVG",
        "Estimate",
        "Pre-flight",
        "If your result differs",
    ):
        assert contract in text
    assert (DOCS / "img" / "tutorial-source.png").is_file()


def test_style_guide_recommends_by_goal_medium_and_plotting_cost():
    text = page_text("choose-a-style.html")
    for contract in (
        "Portraits",
        "Bold markers",
        "Single continuous line",
        "Geometric posters",
        "Multiple pens",
        "Reduce plotting time",
        "Pen width",
        "Fast",
        "Slow",
    ):
        assert contract in text


def test_generated_reference_contains_every_builtin_pfm_once():
    from engine.pfm import REGISTRY
    from tools.build_docs_reference import builtin_pfms, render_reference

    rendered = render_reference()
    assert rendered == render_reference()
    catalog_pfms = builtin_pfms(REGISTRY)
    for pfm in catalog_pfms:
        assert rendered.count(f'id="pfm-{pfm.id}"') == 1
        assert html.escape(pfm.name) in rendered
    assert rendered.count('class="pfm-entry"') == len(catalog_pfms)


def test_every_registered_pfm_has_a_picker_preview():
    from PIL import Image

    from engine.pfm import REGISTRY
    from tools.build_docs_reference import PREVIEWS, builtin_pfms, render_reference

    missing = []
    for pfm in builtin_pfms(REGISTRY):
        pfm_id = pfm.id
        preview = PREVIEWS / f"{pfm_id}.png"
        if not preview.is_file():
            missing.append(pfm_id)
            continue
        with Image.open(preview) as image:
            assert image.size == (440, 621), pfm_id
            assert image.convert("L").getextrema() == (0, 255), pfm_id

    assert missing == []
    assert "Preview pending" not in render_reference()


def test_generated_reference_excludes_runtime_custom_pfms():
    from dataclasses import replace

    from engine.pfm import REGISTRY
    from tools.build_docs_reference import render_reference

    custom_id = "shape_dither_custom_docs_test"
    REGISTRY[custom_id] = replace(
        REGISTRY["shape_dither"], id=custom_id, name="Documentation test shape"
    )
    try:
        rendered = render_reference()
    finally:
        REGISTRY.pop(custom_id, None)

    assert custom_id not in rendered
    assert "Documentation test shape" not in rendered


def test_generated_reference_includes_complete_parameter_metadata():
    from engine.pfm import REGISTRY
    from tools.build_docs_reference import builtin_pfms, render_reference

    rendered = render_reference()
    for pfm in builtin_pfms(REGISTRY):
        start = rendered.index(f'id="pfm-{pfm.id}"')
        end = rendered.find('class="pfm-entry"', start + 20)
        section = rendered[start:end if end >= 0 else None]
        for param in pfm.params:
            assert f'data-param="{param.name}"' in section
            assert html.escape(param.label) in section
            assert html.escape(param.group) in section
            assert html.escape(param.type) in section
            assert html.escape(str(param.default)) in section
            assert html.escape(param.help) in section


def test_checked_in_reference_matches_the_registry():
    from tools.build_docs_reference import render_reference

    assert (DOCS / "reference.html").read_text(encoding="utf-8") == render_reference()


def test_reference_generator_cli_writes_output(tmp_path):
    from tools.build_docs_reference import main

    output = tmp_path / "reference.html"
    assert main(["--output", str(output)]) == 0
    assert output.is_file()


def test_troubleshooting_is_symptom_led_and_covers_the_real_failure_modes():
    text = page_text("troubleshooting.html")
    for contract in (
        "Unsupported file",
        "EXIF orientation",
        "Empty output",
        "Dense or slow output",
        "SAM setup incomplete",
        "GPU fallback",
        "Clipped output",
        "Serial port",
        "Bridge conflict",
        "Homing",
        "Pen up and down heights",
        "Jam or lost steps",
        "Stop / Resume",
        "Collect diagnostics",
    ):
        assert contract in text


def test_operator_guide_has_a_physical_calibration_and_preflight_sequence():
    text = page_text("plot.html")
    for contract in (
        "First-plot calibration",
        "scrap paper",
        "Home",
        "Pen up",
        "Pen down",
        "dry run",
        "Pre-flight",
    ):
        assert contract in text


def test_whats_new_orients_users_to_recent_workflow_changes():
    text = page_text("whats-new.html")
    for contract in (
        "Transformable raster layers",
        "Shape Dither",
        "EXIF orientation",
        "Fit and Fill",
        "Compatibility notes",
        "Documentation version",
    ):
        assert contract in text


def test_readme_routes_artists_operators_and_developers_separately():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for contract in ("For artists", "For plotter operators", "For developers"):
        assert contract in readme


def test_every_manual_page_uses_the_shared_accessible_shell():
    for name in ALL_PAGES:
        page = parse_page(name)
        assert page.main_count == 1, name
        assert "docs.js" in page.scripts, name
        assert len(page.descriptions) == 1, name
        assert len(page.descriptions[0]) >= 50, name


def test_complete_manual_articles_remain_inside_main():
    failures = {}
    for name in ALL_PAGES:
        page = parse_page(name)
        if (
            page.article_tags_outside_main
            or page.footers_inside_main != 1
            or page.unclosed_divs_at_main_end != 0
        ):
            failures[name] = {
                "outside": page.article_tags_outside_main,
                "footers_inside": page.footers_inside_main,
                "unclosed_divs": page.unclosed_divs_at_main_end,
            }
    assert failures == {}


def test_manual_footer_is_the_final_article_element():
    for name in ALL_PAGES:
        source = (DOCS / name).read_text(encoding="utf-8")
        assert re.search(r"</footer>\s*</main>", source), name


def test_documentation_health_checker_reports_no_drift():
    from tools.check_docs import check_docs

    assert check_docs() == []


def test_manual_home_keeps_the_complete_getting_started_guide_in_main():
    source = (DOCS / "index.html").read_text(encoding="utf-8")
    assert source.index("Under the hood") < source.rindex("</main>")
