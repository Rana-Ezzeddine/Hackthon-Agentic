"""The CLI should prepare source material without making model calls."""

import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import agent
from PIL import Image
from paperplay.source import PreparedPaper
from paperplay.visuals import PageSheet


class PreparationCLITest(unittest.TestCase):
    def test_writes_complete_model_input_with_unchanged_inputs_and_no_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case = {
                "source_url": "https://arxiv.org/abs/1706.03762",
                "focus": "Explain why attention is scaled",
                "audience": "Engineering undergraduate",
            }
            source = root / "case.json"
            source.write_text(json.dumps(case), encoding="utf-8")
            picture = BytesIO()
            Image.new("RGB", (40, 40), "white").save(picture, format="JPEG")
            paper = PreparedPaper("Full paper text with Figure 1 and a table.",
                                  "source_url", "html_fetch",
                                  figure_sheets=(PageSheet((1,), picture.getvalue()),))
            argv = ["agent.py", "--input", str(source), "--output", str(root / "out"),
                    "--model", "deepseek/deepseek-v4.1-flash"]
            with patch.object(sys, "argv", argv), \
                 patch.object(agent, "prepare_paper", return_value=paper), \
                 patch("paperplay.openrouter.complete") as model:
                self.assertEqual(agent.main(), 0)
                model.assert_not_called()
            out = root / "out"
            payload = json.loads((out / "model_input.json").read_text())
            self.assertEqual(payload["source_url"], case["source_url"])
            self.assertEqual(payload["focus"], case["focus"])
            self.assertEqual(payload["audience"], case["audience"])
            self.assertEqual(payload["paper_text"], paper.text)
            self.assertEqual(payload["images"][0]["item_numbers"], [1])
            self.assertTrue(payload["images"][0]["image_url"].startswith("data:image/jpeg;base64,"))
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(manifest["model_requests_used"], 0)
            self.assertEqual(manifest["html_figures"], 1)
            self.assertTrue(manifest["fits_one_image_request"])
            self.assertFalse((out / "plan.json").exists())
            self.assertFalse((out / "index.html").exists())

    def test_retrieval_failure_does_not_write_model_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "case.json"
            source.write_text(json.dumps({"source_url": "https://arxiv.org/abs/1706.03762",
                                          "focus": "attention", "audience": "student"}))
            argv = ["agent.py", "--input", str(source), "--output", str(root / "out"),
                    "--model", "demo/model"]
            with patch.object(sys, "argv", argv), \
                 patch.object(agent, "prepare_paper", side_effect=ValueError("fetch failed")):
                self.assertEqual(agent.main(), 1)
            self.assertFalse((root / "out" / "model_input.json").exists())


if __name__ == "__main__":
    unittest.main()
