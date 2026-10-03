"""Contract tests that do not need a paid API call."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent
from paperplay.openrouter import Completion


EXCERPT = "For probabilities p_i, entropy is H = -sum p_i log2(p_i) bits."
PLAN = {
    "source": {"title": "Synthetic note", "location": "excerpt", "evidence": EXCERPT},
    "concept": {"title": "Entropy", "why_it_matters": "Measures uncertainty.",
                "symbols": [{"symbol": "p_i", "meaning": "Outcome probability"}]},
    "controls": [
        {"id": "p", "label": "Probability", "type": "number", "min": 0, "max": 1, "default": 0.5},
        {"id": "count", "label": "Outcomes", "type": "number", "min": 2, "max": 6, "default": 4},
    ],
    "visual": {"kind": "bar", "explanation": "Show probabilities and contributions."},
    "explorations": [
        {"settings": {"p": 1}, "observe": "Entropy falls.", "why": "Certainty removes uncertainty."},
        {"settings": {"count": 4}, "observe": "Compare equal outcomes.", "why": "More choices can increase entropy."},
    ],
    "limitation": "A toy distribution is not a measured dataset.",
    "checks": [
        {"inputs": {"p": 1}, "expected_behavior": "Certainty gives zero bits."},
        {"inputs": {"count": 4}, "expected_behavior": "Four equal outcomes give two bits."},
    ],
}


class PlanningContractTest(unittest.TestCase):
    def test_cli_writes_plan_usage_and_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "case.json"
            source.write_text(json.dumps({"source_url": "https://example.org/note",
                                          "focus": "entropy", "audience": "undergraduate",
                                          "excerpt": EXCERPT}), encoding="utf-8")
            completion = Completion(json.dumps(PLAN), 120, 240, 0.25, "mock-id")
            argv = ["agent.py", "--input", str(source), "--output", str(root / "out"),
                    "--model", "deepseek/deepseek-v4.1-flash"]
            with patch.object(sys, "argv", argv), patch.object(agent, "complete", return_value=completion):
                self.assertEqual(agent.main(), 0)
            out = root / "out"
            self.assertEqual(json.loads((out / "plan.json").read_text()), PLAN)
            self.assertIn("planning preview", (out / "index.html").read_text().lower())
            events = [json.loads(row) for row in (out / "trace.jsonl").read_text().splitlines()]
            self.assertEqual(events[3]["result"]["prompt_tokens"], 120)
            self.assertEqual(events[3]["result"]["completion_tokens"], 240)
            self.assertEqual(events[4]["result"]["status"], "passed")

    def test_missing_excerpt_fails_before_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "case.json"
            source.write_text(json.dumps({"source_url": "https://example.org/note",
                                          "focus": "entropy", "audience": "undergraduate"}))
            argv = ["agent.py", "--input", str(source), "--output", str(root / "out"),
                    "--model", "demo/model"]
            with patch.object(sys, "argv", argv), patch.object(agent, "complete") as model:
                self.assertEqual(agent.main(), 1)
                model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
