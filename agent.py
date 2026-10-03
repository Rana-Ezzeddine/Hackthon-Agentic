"""Paper → Playground command-line agent."""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path
from paperplay.budget import Budget
from paperplay.checks import page_usable,run_checks
from paperplay.config import GEN_TOKENS,PARSE_REPAIR_TOKENS,REPAIR_TOKENS
from paperplay.degrade import degrade
from paperplay.figures import prepare_figures
from paperplay.inputs import load_case
from paperplay.openrouter import ModelCallError,OpenRouter
from paperplay.prompts import generation_messages,parse_repair_messages,repair_messages
from paperplay.render import fallback_page,render,write_atomic
from paperplay.selection import select
from paperplay.source import acquire_and_parse
from paperplay.spec import normalize_spec,parse_json,patch_merge
from paperplay.trace import Trace

def fallback_spec(case,prepared):
    anchor="brief" if prepared.mode=="brief_only" else "selected source"
    return {"plan":{"core_idea":case.focus,"source_anchor":anchor,"prerequisites":[],"learning_outcomes":[{"outcome":case.focus,"covered_by":["control:input","control:scale","view:0","exploration:1"]}],"key_insight_to_reveal":"How an input and scale change an illustrative output.","visual_idea":"A bar chart of the intermediate values.","controls_rationale":[{"id":"input","reveals":"Changes the illustrative input."},{"id":"scale","reveals":"Shows the effect of a display scale."}],"misconception":"This fallback is not a reconstruction of the paper.","simplifications":["A generic display transform is used because generation failed."],"figures":[{"id":f.get("id"),"role":"Candidate source figure; omitted from the fallback explanation.","use":False,"placement":"after_intro","informs_custom_svg":False} for f in prepared.gated_figures]},"title":case.focus[:100],"citation":{"section":"","equation":"","figure_refs":[]},"intro":{"idea":"The requested mechanism could not be generated automatically.","why_it_matters":"The source and focus remain available for inspection.","key_equation":"illustrative output = input × scale"},"mechanism":{"kind":"conceptual_process","calculation_scope":"display_transform","source_anchor":anchor,"toy_model_notice":"Illustrative fallback only; it does not reproduce the paper's experiments."},"symbols":[{"symbol":"input","meaning":"Illustrative input, not a paper variable","source_anchor":"simplification"},{"symbol":"scale","meaning":"Illustrative display scale","source_anchor":"simplification"}],"controls":[{"id":"input","label":"Illustrative input","type":"slider","min":0,"max":10,"step":1,"default":2,"options":[],"rows":0,"cols":0,"help":"Fallback control","role":"paper_variable","paper_variable":"input"},{"id":"scale","label":"Display scale","type":"slider","min":0,"max":3,"step":0.25,"default":1,"options":[],"rows":0,"cols":0,"help":"Fallback display transform","role":"paper_variable","paper_variable":"scale"}],"compute":"function compute(p){const x=Number(p.input)||0,s=Number(p.scale)||0;return {values:{input:x,scale:s,output:x*s},series:{bars:[x,s,x*s]},matrices:{},notes:[]};}","views":[{"type":"bar","bind":"series.bars","title":"Fallback transform","x_label":"quantity","y_label":"value","caption":"Generic fallback values; not paper results."}],"custom_svg":"","intermediates":[{"key":"values.input","label":"Input","fmt":2},{"key":"values.output","label":"Output","fmt":2}],"explorations":[{"title":"Zero input","preset":{"input":0},"do":"Set input to zero.","observe":"The output becomes zero.","why":"The fallback uses multiplication.","expect":"r.values.output===0"},{"title":"Double scale","preset":{"input":2,"scale":2},"do":"Set both values to two.","observe":"The output becomes four.","why":"This is only a display transform.","expect":"r.values.output===4"}],"limitation":{"kind":"limitation","text":"Automatic generation failed, so this generic fallback does not explain the paper mechanism."},"claims":[{"text":"This is an unverified generic display example.","source":"simplification","anchor":""}],"tests":[{"name":"zero","inputs":{"input":0},"assert":"r.values.output===0"},{"name":"identity","inputs":{"input":3,"scale":1},"assert":"r.values.output===3"},{"name":"finite","inputs":{"input":10,"scale":3},"assert":"Number.isFinite(r.values.output)"}]}

def generate_spec(llm,case,prepared,record,trace):
    try:
        raw=llm.complete(generation_messages(case,prepared,record),GEN_TOKENS,"generate").content
        try:return parse_json(raw)
        except Exception as exc:
            trace.log("spec","parse","fail",error=type(exc).__name__)
            if llm.budget.can_afford(PARSE_REPAIR_TOKENS): return parse_json(llm.complete(parse_repair_messages(raw,str(exc)),PARSE_REPAIR_TOKENS,"parse_repair").content)
            raise
    except Exception as exc:
        trace.log("spec","fallback","applied",error=type(exc).__name__,message=str(exc)[:180])
        return fallback_spec(case,prepared)

def main(argv=None):
    parser=argparse.ArgumentParser(description="Turn a paper and learning brief into one offline interactive page.")
    parser.add_argument("--input",required=True,type=Path);parser.add_argument("--output",required=True,type=Path);parser.add_argument("--model",required=True)
    args=parser.parse_args(argv);started=time.monotonic();args.output.mkdir(parents=True,exist_ok=True);trace=Trace(args.output/"trace.jsonl",started);budget=Budget(started);llm=OpenRouter(args.model,budget,trace);case=None
    try:
        case=load_case(args.input,trace);record=acquire_and_parse(case,trace);prepared=select(record,case,trace);prepare_figures(prepared,trace);spec=normalize_spec(generate_spec(llm,case,prepared,record,trace),prepared)
        trace.log("plan","design","ok",core_idea=spec.get("plan",{}).get("core_idea",""),source_anchor=spec.get("plan",{}).get("source_anchor",""))
        failures=[];checks=[];revisions=0
        for revision in range(3):
            html=render(spec,record,prepared);trace.log("render","page","ok",revision=revision,bytes=len(html.encode("utf-8")))
            checks=run_checks(spec,record,prepared,html,trace);failures=[x for x in checks if not x["ok"]]
            if not failures or revision==2 or not budget.can_afford(REPAIR_TOKENS):break
            try:
                patch=parse_json(llm.complete(repair_messages(spec,failures,prepared),REPAIR_TOKENS,"repair").content);spec=normalize_spec(patch_merge(spec,patch),prepared);revisions+=1;trace.log("repair","merge_patch","ok",fields=sorted(patch))
            except Exception as exc:
                trace.log("repair","merge_patch","fail",error=type(exc).__name__);break
        notices=[]
        if failures:
            spec,notices=degrade(spec,failures,trace);html=render(spec,record,prepared,notices);checks=run_checks(spec,record,prepared,html,trace);failures=[x for x in checks if not x["ok"]]
        write_atomic(args.output/"index.html",html);usable=page_usable(failures);status=0 if usable else 2
        trace.log("final","summary","ok" if not failures else ("partial" if usable else "fail"),**budget.totals(),seconds=round(time.monotonic()-started,2),checks_passed=sum(x["ok"] for x in checks),checks_failed=sum(not x["ok"] for x in checks),revisions=revisions,remaining_failures=[x["check"] for x in failures],exit_status=status)
        return status
    except Exception as exc:
        trace.log("final","error",type(exc).__name__,message=str(exc)[:300],**budget.totals(),seconds=round(time.monotonic()-started,2),exit_status=1)
        write_atomic(args.output/"index.html",fallback_page(case,exc));print("Error: %s"%exc,file=sys.stderr);return 1

if __name__=="__main__":raise SystemExit(main())
