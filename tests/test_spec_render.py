from types import SimpleNamespace
from agent import fallback_spec
from paperplay.checks import run_checks
from paperplay.record import PaperRecord
from paperplay.render import render
from paperplay.spec import normalize_spec

class Trace:
    def log(self,*a,**k):pass

def objects():
    case=SimpleNamespace(focus="Teach a transform",source_url="https://example.org",audience="student")
    prepared=SimpleNamespace(mode="brief_only",context="Teach a transform",gated_figures=[])
    record=PaperRecord(mode="brief_only");record.meta.update({"title":"Example","urls":{"source":case.source_url}})
    return case,prepared,record

def test_render_is_offline_and_checks_pass():
    case,prepared,record=objects();spec=fallback_spec(case,prepared);html=render(spec,record,prepared)
    results=run_checks(spec,record,prepared,html,Trace())
    assert next(x for x in results if x["check"]=="C16")["ok"]
    assert len(html)>5000 and "Illustrative toy model" in html

def test_offline_check_rejects_runtime_request():
    case,prepared,record=objects();spec=fallback_spec(case,prepared);html=render(spec,record,prepared)+"<script>fetch('https://example.org')</script>"
    results=run_checks(spec,record,prepared,html,Trace())
    assert not next(x for x in results if x["check"]=="C16")["ok"]

def test_malformed_model_figure_entry_becomes_repairable_failure():
    case,prepared,record=objects();prepared.gated_figures=[{"id":"S3.F2","number":"2","caption":"Attention","image_bytes":None}]
    spec=fallback_spec(case,prepared);spec["plan"]["figures"]=["S3.F2"]
    html=render(spec,record,prepared)
    results=run_checks(spec,record,prepared,html,Trace())
    assert not next(x for x in results if x["check"]=="C14")["ok"]

def test_model_aliases_are_normalized_before_checks():
    case,prepared,record=objects();prepared.gated_figures=[{"id":"S3.F2","number":"2","caption":"Attention","image_bytes":None}]
    spec=fallback_spec(case,prepared);spec["plan"]["figures"]=["Figure 2: attention structure"]
    spec["controls"][0]["role"]="exploration";spec["controls"][0]["paper_variable"]=""
    normalize_spec(spec,prepared)
    assert spec["plan"]["figures"][0]["id"]=="S3.F2"
    assert spec["controls"][0]["role"]=="result_selector"
