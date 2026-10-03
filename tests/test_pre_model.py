"""Pre-model stages must work without OpenRouter or network access."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
from PIL import Image

from paperplay.budget import Budget, BudgetError, MAX_COMPLETION_TOKENS, MAX_REQUESTS
from paperplay.pdf_reader import PaperPage, pages_as_text, read_pdf
from paperplay.source import (
    PreparedPaper, _HTMLText, _prepare_html, html_url_for_source, load_case,
    prepare_paper, retrieve_source_url,
)
from paperplay.visuals import make_page_sheets, visual_batches
from io import BytesIO


def case_with(text, field="excerpt"):
    return {
        "source_url": "https://example.org/paper",
        "focus": "Explain discrete entropy and probability distribution",
        "audience": "Engineering undergraduate",
        field: text,
    }


class PreModelTest(unittest.TestCase):
    def test_short_excerpt_is_preserved_exactly(self):
        text = "Entropy is H = -sum p log2(p).\n\nAt p=0 the contribution is zero."
        paper = prepare_paper(case_with(text))
        self.assertEqual(paper.text, text.strip())
        self.assertEqual(paper.field, "excerpt")

    def test_nested_and_list_source_fields(self):
        case = case_with("ignored")
        del case["excerpt"]
        case["paper"] = {"excerpts": [{"text": "Section 2: H = -sum p log2(p)."}]}
        paper = prepare_paper(case)
        self.assertEqual(paper.field, "paper.excerpts")
        self.assertIn("Section 2", paper.text)

    def test_long_source_is_not_filtered(self):
        noise = "A different unrelated mechanism operates here. " * 500
        useful = "Discrete entropy for a probability distribution is H = -sum p log2(p)."
        text = noise + "\n\n" + useful + "\n\n" + noise
        case = case_with(text)
        paper = prepare_paper(case)
        self.assertEqual(paper.text, text.strip())

    def test_paper_representation_is_independent_of_focus_and_audience(self):
        noise = "Other entropy discussion. " * 250
        section_six = "6. CHOICE AND ENTROPY\nH = -sum p log2(p). " + "Definition. " * 150
        section_twenty = "20. CONTINUOUS ENTROPY\n" + "Entropy and probability. " * 200
        text = noise + "\n\n" + section_six + "\n\n" + noise + "\n\n" + section_twenty
        first = case_with(text)
        second = dict(first, focus="Explain the main idea", audience="High school student")
        self.assertEqual(prepare_paper(first), prepare_paper(second))
        self.assertIn("6. CHOICE AND ENTROPY", prepare_paper(first).text)
        self.assertIn("20. CONTINUOUS ENTROPY", prepare_paper(first).text)

    def test_missing_source_uses_url(self):
        case = case_with("x")
        del case["excerpt"]
        fetched = PreparedPaper("A paper's entropy equation is H = -sum p log2(p).",
                                "source_url", "url_fetch")
        with patch("paperplay.source.retrieve_source_url", return_value=fetched) as fetch:
            selected = prepare_paper(case)
        fetch.assert_called_once_with("https://example.org/paper")
        self.assertEqual(selected.method, "url_fetch")

    def test_pdf_representation_preserves_text_table_image_and_page_render(self):
        image_bytes = BytesIO()
        Image.new("RGB", (20, 20), "red").save(image_bytes, format="PNG")
        document = pymupdf.open()
        page = document.new_page(width=400, height=500)
        page.insert_text((50, 50), "Entropy mechanism")
        for y in (100, 130, 160):
            page.draw_line((50, y), (250, y))
        for x in (50, 150, 250):
            page.draw_line((x, 100), (x, 160))
        for x, y, text in ((60, 120, "A"), (160, 120, "B"),
                           (60, 150, "1"), (160, 150, "2")):
            page.insert_text((x, y), text)
        page.insert_image(pymupdf.Rect(50, 200, 150, 300), stream=image_bytes.getvalue())
        pages = read_pdf(document.tobytes())
        document.close()
        self.assertEqual(len(pages), 1)
        self.assertIn("Entropy mechanism", pages_as_text(pages))
        self.assertEqual(pages[0].tables[0], (("A", "B"), ("1", "2")))
        self.assertEqual(len(pages[0].embedded_images), 1)
        self.assertTrue(pages[0].rendered_jpeg.startswith(b"\xff\xd8"))
        sheets = make_page_sheets(pages)
        self.assertEqual(sheets[0].page_numbers, (1,))
        self.assertEqual(len(visual_batches(sheets)), 1)

    def test_visual_batches_cover_every_page_within_four_calls(self):
        picture = BytesIO()
        Image.new("RGB", (40, 40), "white").save(picture, format="JPEG")
        pages = tuple(PaperPage(i, "text", (), (), 0, picture.getvalue())
                      for i in range(1, 56))
        batches = visual_batches(make_page_sheets(pages))
        seen = [number for batch in batches for sheet in batch
                for number in sheet.page_numbers]
        self.assertEqual(seen, list(range(1, 56)))
        self.assertLessEqual(len(batches), 4)
        self.assertTrue(all(len(batch) <= 8 for batch in batches))

    def test_html_extraction_skips_navigation_and_scripts(self):
        parser = _HTMLText()
        parser.feed("<nav>Menu</nav><main><h1>Entropy</h1><p>H = -sum p log2(p)</p>"
                    "<script>bad()</script></main>")
        extracted = "".join(parser.parts)
        self.assertIn("Entropy", extracted)
        self.assertIn("H = -sum", extracted)
        self.assertNotIn("Menu", extracted)
        self.assertNotIn("bad()", extracted)

    def test_html_paper_preserves_text_and_all_figure_images(self):
        picture = BytesIO()
        Image.new("RGB", (40, 40), "red").save(picture, format="PNG")
        body = ("<html><body><nav>Menu</nav><article><h1>Entropy</h1>"
                "<section><h2>Method</h2><p>H = -sum p log2(p). "
                + "Explanation. " * 25 + "</p></section>"
                "<figure><img src='fig1.png' alt='Entropy curve'>"
                "<figcaption>Figure 1: Entropy curve</figcaption></figure>"
                "<figure><img src='fig2.png' alt='Probability bars'>"
                "<figcaption>Figure 2: Probability bars</figcaption></figure>"
                "<table><tr><th>Setting</th><th>Value</th></tr>"
                "<tr><td>A</td><td>2</td></tr></table>"
                "</article></body></html>")
        with patch("paperplay.source._download", return_value=(picture.getvalue(), "image/png", "https://arxiv.org/html/fig1.png")) as fetch:
            paper = _prepare_html(body.encode(), "https://arxiv.org/html/1234.5678")
        self.assertEqual(paper.method, "html_fetch")
        self.assertIn("H = -sum p log2(p)", paper.text)
        self.assertIn("Figure 1: Entropy curve", paper.text)
        self.assertNotIn("Menu", paper.text)
        self.assertEqual([s.page_numbers for s in paper.figure_sheets], [(1,), (2,)])
        self.assertEqual(paper.html_tables, 1)
        self.assertIn("| Setting | Value", paper.text)
        self.assertEqual(fetch.call_count, 2)

    def test_arxiv_html_is_tried_before_pdf_and_pdf_is_fallback(self):
        source = "https://arxiv.org/abs/1706.03762"
        self.assertEqual(html_url_for_source(source), "https://arxiv.org/html/1706.03762")
        html_paper = PreparedPaper("full paper text", "source_url", "html_fetch")
        pdf_paper = PreparedPaper("PDF paper text", "source_url", "pdf_fetch")
        with patch("paperplay.source._prepare_url", return_value=html_paper) as fetch:
            self.assertIs(retrieve_source_url(source), html_paper)
        fetch.assert_called_once_with("https://arxiv.org/html/1706.03762")
        with patch("paperplay.source._prepare_url", side_effect=[ValueError("HTML missing"), pdf_paper]) as fetch:
            self.assertIs(retrieve_source_url(source), pdf_paper)
        self.assertEqual([call.args[0] for call in fetch.call_args_list],
                         ["https://arxiv.org/html/1706.03762", "https://arxiv.org/pdf/1706.03762"])

    def test_validates_required_fields_and_url(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "case.json"
            path.write_text('{"source_url":"file:///tmp/paper","focus":"x","audience":"y"}')
            with self.assertRaisesRegex(ValueError, "HTTP"):
                load_case(path)

    def test_budget_counts_attempts_and_usage(self):
        budget = Budget()
        allowance = budget.allowance(1000)
        self.assertEqual(allowance.request_number, 1)
        budget.record_usage(250, 400)
        self.assertEqual(budget.snapshot()["completion_tokens"], 400)
        for _ in range(MAX_REQUESTS - 1):
            budget.allowance(1000)
        with self.assertRaisesRegex(BudgetError, "request"):
            budget.allowance()

    def test_budget_caps_completion_and_time(self):
        budget = Budget()
        budget.record_usage(0, MAX_COMPLETION_TOKENS - 7)
        self.assertEqual(budget.allowance(1000).max_completion_tokens, 7)
        with patch("paperplay.budget.time.monotonic", return_value=700.0):
            expired = Budget(started=0.0)
            with self.assertRaisesRegex(BudgetError, "time"):
                expired.allowance()


if __name__ == "__main__":
    unittest.main()
