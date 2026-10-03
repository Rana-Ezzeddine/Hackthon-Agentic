import json
from agent import main

def test_invalid_input_writes_error_page_and_trace(tmp_path):
    bad=tmp_path/"bad.json";bad.write_text(json.dumps({"source_url":"file:///tmp/a","focus":"x","audience":"y"}))
    out=tmp_path/"out"
    assert main(["--input",str(bad),"--output",str(out),"--model","test/model"])==1
    assert (out/"index.html").exists() and (out/"trace.jsonl").exists()
    assert json.loads((out/"trace.jsonl").read_text().splitlines()[-1])["exit_status"]==1
