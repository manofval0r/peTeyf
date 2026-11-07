"""Inspect the actual matplotlib figure and final raster size, not PDF spans."""
import base64
import copy
import io
import re
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.text import Text

from pdfstudio import charts
from pdfstudio.content import ChartRequest
from pdfstudio.tokens import FontPair, THEMES

ARTIFACTS = Path(__file__).resolve().parents[1] / "out/skill-upgrade/asset-tests"


@contextmanager
def capture_figures():
    figures = []
    original = Figure.savefig

    def save(figure, *args, **kwargs):
        figures.append(figure)
        return original(figure, *args, **kwargs)

    with patch.object(Figure, "savefig", new=save):
        yield figures


def raster(html):
    data = re.search(r"data:image/png;base64,([^\"]+)", html)
    return Image.open(io.BytesIO(base64.b64decode(data.group(1))))


def rendered_text(figure):
    return [text for text in figure.findobj(Text) if text.get_visible() and text.get_text().strip()]


class ChartDesignTests(unittest.TestCase):
    def setUp(self):
        self.ds = copy.deepcopy(THEMES["editorial"])
        self.ds.fonts = FontPair("'Space Grotesk', sans-serif", "'Source Serif 4', serif")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)

    def test_chart_fonts_follow_effective_theme(self):
        req = ChartRequest("chart", "bar", labels=["One", "Two"], series=[[2, 3], [1, 2]], series_names=["A", "B"])
        with capture_figures() as figures:
            charts.make_chart(req, self.ds)
        figure = figures[0]
        for text in figure.axes[0].get_xticklabels() + figure.axes[0].get_yticklabels():
            self.assertEqual(Path(text.get_fontproperties().get_file()).name, "SourceSerif4.ttf")
        for text in figure.axes[0].texts:
            self.assertEqual(Path(text.get_fontproperties().get_file()).name, "SpaceGrotesk.ttf")
        for text in figure.axes[0].get_legend().get_texts():
            self.assertEqual(Path(text.get_fontproperties().get_file()).name, "SourceSerif4.ttf")

    def test_layout_width_passed_to_chart(self):
        req = ChartRequest("chart", "bar", labels=["A", "B"], series=[[2, 3]])
        for width, height in ((3.1, 2.8), (6.4, 3.4)):
            with capture_figures() as figures:
                html = charts.make_chart(req, self.ds, width=width, height=height)
            self.assertAlmostEqual(figures[0].get_size_inches()[0], width)
            self.assertAlmostEqual(figures[0].get_size_inches()[1], height)
            self.assertEqual(raster(html).size, (round(width * 200), round(height * 200)))
            self.assertIn(f'width:{width:g}in', html)

    def test_labels_remain_9pt_at_final_width(self):
        for kind in ("bar", "hbar", "line", "area", "stacked", "pie", "donut"):
            req = ChartRequest("chart", kind, labels=["A", "B", "C"], series=[[12, 18, 20], [4, 6, 10]], series_names=["First", "Second"])
            with self.subTest(kind=kind), capture_figures() as figures:
                html = charts.make_chart(req, self.ds, width=3.2, height=3.4)
            figure = figures[0]
            effective_scale = 3.2 * 200 / raster(html).width
            for text in rendered_text(figure):
                self.assertGreaterEqual(text.get_fontsize() * effective_scale, 9.0, f"{kind}: {text.get_text()}")

    def test_stacked_labels_choose_contrast(self):
        self.ds.palette.accent = "#F7EDB8"
        self.ds.palette.accent2 = "#17324D"
        req = ChartRequest("chart", "stacked", labels=["Q1", "Q2"], series=[[30, 40], [20, 25]], series_names=["Light fill", "Dark fill"])
        with capture_figures() as figures:
            html = charts.make_chart(req, self.ds, width=5, height=3.4)
        texts = figures[0].axes[0].texts
        self.assertEqual([text.get_color().lower() for text in texts[:2]], ["#000000", "#000000"])
        self.assertEqual([text.get_color().lower() for text in texts[2:]], ["#ffffff", "#ffffff"])
        raster(html).save(ARTIFACTS / "stacked-light-dark.png")

    def test_long_category_labels_do_not_overlap(self):
        labels = ["Regional distribution and wholesale partners", "Direct to consumer online sales", "Independent specialist retail stores", "Institutional procurement partnerships"]
        req = ChartRequest("chart", "bar", labels=labels, series=[[12, 18, 20, 16]])
        with capture_figures() as figures:
            html = charts.make_chart(req, self.ds, width=3.2, height=4.6)
        figure = figures[0]
        FigureCanvasAgg(figure).draw()
        renderer = figure.canvas.get_renderer()
        boxes = [label.get_window_extent(renderer) for label in figure.axes[0].get_yticklabels()]
        for i, first in enumerate(boxes):
            self.assertGreaterEqual(first.x0, 0)
            self.assertLessEqual(first.x1, figure.bbox.width)
            for second in boxes[i + 1:]:
                self.assertFalse(first.overlaps(second), "category labels collide at final physical size")
        raster(html).save(ARTIFACTS / "long-labels-column.png")

    def test_impossible_geometry_uses_readable_table_not_shrunk_raster(self):
        req = ChartRequest("chart", "bar", labels=["A long category label " * 3] * 20, series=[list(range(20))])
        html = charts.make_chart(req, self.ds, width=2.4, height=1.5)
        self.assertIn("chart--fallback", html)
        self.assertNotIn("data:image/png", html)

    def test_missing_brand_font_falls_back_without_network(self):
        font = charts._font("'Not Installed', serif", 9)
        self.assertGreaterEqual(font.get_size_in_points(), 9)
        self.assertTrue(font.get_file() or font.get_family())


if __name__ == "__main__":
    unittest.main()
