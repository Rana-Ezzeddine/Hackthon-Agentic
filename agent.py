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
    control={"id":"input","label":"Illustrative input","type":"slider","min":0,"max":10,"step":1,"default":2,"help":"Fallback control","role":"result_selector","paper_variable":""}
    return {"lesson_plan":{"concept":case.focus,"source_anchor":anchor,"outcomes":[{"id":"o1","text":case.focus}],"prerequisites":[],"misconceptions":["This fallback is not a reconstruction of the paper."],"figures":[{"id":f.get("id"),"role":"Candidate source figure omitted because lesson generation failed.","use":False,"step_id":"fallback"} for f in prepared.gated_figures]},"concept":{"title":case.focus[:100],"what_it_is":["The requested lesson could not be generated automatically.","This safe fallback keeps the source and focus available for inspection."],"why_it_exists":["It confirms that the offline lesson renderer is working while avoiding invented paper claims."],"equation":"illustrative output = input × 2","symbols":[{"symbol":"input","meaning":"Illustrative input, not a paper variable","source_anchor":"simplification"}]},"citation":{"section":"","equation":"","year":""},"mechanism":{"kind":"conceptual_process","calculation_scope":"display_transform","source_anchor":anchor,"toy_model_notice":"Illustrative fallback only; it does not reproduce the paper's experiments."},"compute":"function compute(p){const x=Number(p.input)||0;return {values:{input:x,output:x*2},series:{bars:[x,x*2]},matrices:{},notes:[]};}","steps":[{"id":"fallback","outcome_id":"o1","heading":"A safe illustrative fallback","explanation":["Automatic lesson generation failed, so this example intentionally does not explain the paper's mechanism."],"source_anchor":anchor,"controls":[control],"components":[{"type":"bar","title":"Illustrative transform","bind":"series.bars","caption":"Generic values, not paper results."}],"guide":{"try":"Set the input to zero.","notice":"The illustrative output becomes zero.","why":"The fallback uses a simple deterministic transform.","preset":{"input":0},"evidence_bind":"values.output","expect":"r.values.output===0"},"takeaway":"This fallback is a renderer check, not a scientific explanation."}],"custom_svg":"","recap":[{"outcome_id":"o1","text":"The requested lesson still needs a successful model generation."}],"claims":[{"text":"This is an unverified generic display example.","source":"simplification","anchor":"","section":""}],"limitation":{"text":"Automatic generation failed, so this generic fallback does not explain the paper mechanism."},"tests":[{"name":"zero","inputs":{"input":0},"assert":"r.values.output===0"},{"name":"double","inputs":{"input":2},"assert":"r.values.output===4"},{"name":"finite","inputs":{"input":10},"assert":"Number.isFinite(r.values.output)"}]}

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
        trace.log("plan","lesson","ok",concept=spec.get("lesson_plan",{}).get("concept",""),outcomes=len(spec.get("lesson_plan",{}).get("outcomes",[])),steps=len(spec.get("steps",[])),source_anchor=spec.get("lesson_plan",{}).get("source_anchor",""))
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
