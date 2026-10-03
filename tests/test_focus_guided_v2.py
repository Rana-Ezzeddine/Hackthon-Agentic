"""The complete-paper path and template edit must stay connected."""
from types import SimpleNamespace
from copy import deepcopy
import json

from paperplay.checks import run_checks
from paperplay.full_source import prepare_full_paper
from paperplay.prompts import generation_messages
from paperplay.record import PaperRecord, Section
from paperplay.render import render
from paperplay.spec import validate_schema


class Trace:
    def log(self, *args, **kwargs):
        pass


def sample():
    record = PaperRecord(mode="arxiv_html")
    record.meta.update({"title": "Example Paper", "authors": [{"name": "Researcher"}],
                        "urls": {"source": "https://arxiv.org/abs/1234.5678"}})
    record.sections = [
        Section(anchor="sec-1", heading="Background", text="The first mechanism changes a quantity."),
        Section(anchor="sec-2", heading="Method", text="The second mechanism scales the result."),
    ]
    prepared = prepare_full_paper(record, Trace())
    case = SimpleNamespace(source_url=record.meta["urls"]["source"],
                           focus="Explain the second mechanism", audience="Students")
    spec = {
        "format": "focus-guided-v2", "title": "Understand the mechanism",
        "focus_statement": "How does the second mechanism scale a result?",
        "summary_html": "<p>Follow the calculation.</p>",
        "coverage": [{"need": "scale the result", "unit_id": "scale"}],
        "unsupported_scope": [],
        "units": [{"id": "scale", "title": "Scaling", "question": "What changes?",
                   "orientation_html": "<p>Start with a value, then change its scale.</p>",
                   "interpretation_html": "<p>The bar shows the product.</p>",
                   "source_refs": ["sec-2"],
                   "interaction": {"visual_reference": "curve inspired, custom calculation",
                                   "caption": "Illustrative input and scale, not paper data.",
                                   "controls": [
                                       {"id": "x", "label": "Input", "type": "slider", "min": 0, "max": 10, "step": 1, "default": 2},
                                       {"id": "scale", "label": "Scale", "type": "slider", "min": 0, "max": 3, "step": 1, "default": 1},
                                   ],
                                   "compute": "function compute(p){const y=p.x*p.scale;return {values:{y},series:{bars:[p.x,y]},matrices:{},notes:['Current product: '+y]};}",
                                   "views": [{"type": "bar", "bind": "series.bars", "title": "Bars", "caption": "Input and product"},
                                             {"type": "custom", "bind": "values.y", "title": "Custom", "caption": "Paper-specific diagram"}],
                                   "draw": "function draw(p,r){return '<svg viewBox=\"0 0 100 50\"><circle cx=\"'+(20+r.values.y)+'\" cy=\"25\" r=\"8\"/></svg>';}",
                                   "css": ".custom-note{color:#3159c5}",
                                   "metrics": [{"key": "values.y", "label": "Product", "fmt": 1}]},
                   "explorations": [
                       {"title": "Zero input", "prediction": "What if x is zero?", "preset": {"x": 0},
                        "observe": "The product is zero", "why": "Zero times a scale is zero", "expect": "r.values.y===0"},
                       {"title": "Double scale", "prediction": "What if scale doubles?", "preset": {"scale": 2},
                        "observe": "The product doubles", "why": "The rule multiplies by scale", "expect": "r.values.y===4"},
                   ], "after_html": "<p>Return to the original question.</p>"}],
        "synthesis_html": "<p>The result changes with scale.</p>",
        "transfer_question": "What if scale is three?",
        "limitations_html": "<p>This is a toy model.</p>",
        "claims": [{"text": "The mechanism scales the result", "anchor": "scales the result", "source_ref": "sec-2"}],
        "tests": [
            {"unit_id": "scale", "name": "zero", "inputs": {"x": 0}, "assert": "r.values.y===0"},
            {"unit_id": "scale", "name": "identity", "inputs": {"x": 3}, "assert": "r.values.y===3"},
            {"unit_id": "scale", "name": "double", "inputs": {"scale": 2}, "assert": "r.values.y===4"},
        ],
    }
    return case, record, prepared, spec


def test_full_paper_prompt_does_not_filter_by_focus():
    case, record, prepared, _ = sample()
    assert "The first mechanism" in prepared.context
    assert "The second mechanism" in prepared.context
    message = generation_messages(case, prepared, record)[1]["content"]
    assert "The first mechanism" in message and "The second mechanism" in message
    assert "VISUAL INSPIRATION" in generation_messages(case, prepared, record)[0]["content"]


def test_focus_template_renders_units_with_shared_guidance():
    _, record, prepared, spec = sample()
    html = render(spec, record, prepared)
    results = run_checks(spec, record, prepared, html, Trace())
    assert all(result["ok"] for result in results), results
    assert 'id="learning-path"' in html
    assert 'id="synthesis"' in html
    assert 'GUIDED EXPLORATIONS' in html
    assert "#unit-0 .custom-note" in html


def test_rich_html_drops_executable_markup():
    _, record, prepared, spec = sample()
    spec["units"][0]["orientation_html"] = '<p class="custom-note" onclick="evil()">Safe</p><script>evil()</script>'
    html = render(spec, record, prepared)
    assert "onclick=" not in html
    assert "<script>evil()" not in html
    assert 'class=\\"custom-note\\"' in html


def test_multiple_units_and_inline_paper_visual():
    _, record, prepared, spec = sample()
    second = deepcopy(spec["units"][0])
    second["id"] = "followup"
    second["title"] = "Follow-up idea"
    second["source_refs"] = ["fig-1"]
    spec["units"].append(second)
    spec["coverage"].append({"need": "follow-up idea", "unit_id": "followup"})
    record.figures.append({"id": "fig-1", "caption": "Paper diagram",
                           "inline_svg": '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="5"/></svg>',
                           "image_bytes": None})
    html = render(spec, record, prepared)
    assert 'id="unit-1"' in html or 'unit-1' in html
    assert 'Paper diagram' in html and 'circle' in html
    assert all(result["ok"] for result in run_checks(spec, record, prepared, html, Trace()))


def test_custom_view_requires_drawing_function():
    _, _, _, spec = sample()
    spec["units"][0]["interaction"]["draw"] = ""
    assert "custom view needs draw" in validate_schema(spec)


def test_cli_writes_focus_guided_page_without_live_model(monkeypatch, tmp_path):
    import agent
    _, record, _, spec = sample()
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps({"source_url": "https://arxiv.org/abs/1234.5678",
                                     "focus": "Explain the second mechanism", "audience": "Students"}))
    monkeypatch.setattr(agent, "acquire_and_parse", lambda _case, _trace: record)
    monkeypatch.setattr(agent, "prepare_figures", lambda _prepared, _trace: None)
    monkeypatch.setattr(agent, "generate_spec", lambda *_args: spec)
    out = tmp_path / "out"
    assert agent.main(["--input", str(case_path), "--output", str(out), "--model", "test/model"]) == 0
    html = (out / "index.html").read_text()
    assert 'id="learning-path"' in html and "Scaling" in html
    assert json.loads((out / "trace.jsonl").read_text().splitlines()[-1])["exit_status"] == 0
