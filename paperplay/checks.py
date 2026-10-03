"""C0-C17 deterministic structural, grounding, and JavaScript checks."""
from __future__ import annotations
import json, math, random, re
from difflib import SequenceMatcher
from .spec import validate_schema

def _result(check,ok,msg="",fields=None): return {"check":check,"ok":bool(ok),"msg":msg,"fields":fields or []}
def _defaults(spec): return {c["id"]:c.get("default") for c in spec.get("controls",[]) if isinstance(c,dict) and c.get("id")}
def _eval(spec,p,expr=None):
    import quickjs
    ctx=quickjs.Context(); ctx.set_time_limit(.5); ctx.set_memory_limit(32*1024*1024)
    code="'use strict';const compute=(%s);const p=Object.freeze(%s);const r=compute(p);%s"%(spec["compute"],json.dumps(p,separators=(",",":")),"JSON.stringify(r)" if expr is None else "Boolean("+expr+")")
    return ctx.eval(code)
def _finite(value):
    if isinstance(value,float): return math.isfinite(value)
    if isinstance(value,dict): return all(_finite(v) for v in value.values())
    if isinstance(value,list): return all(_finite(v) for v in value)
    return value is not None
def _path(obj,path):
    for key in path.split("."):
        if not isinstance(obj,dict) or key not in obj:return None
        obj=obj[key]
    return obj
def _grounded(anchor,context):
    clean=lambda s:re.sub(r"[^a-z0-9_]+"," ",str(s).lower()).strip()
    a,c=clean(anchor),clean(context)
    if not a:return False
    if a in c:return True
    aw,cw=a.split(),c.split()
    if not aw:return False
    for size in range(max(1,len(aw)-2),len(aw)+3):
        for i in range(max(0,len(cw)-size+1)):
            if SequenceMatcher(None,a," ".join(cw[i:i+size])).ratio()>=.85:return True
    return False

def run_checks(spec,record,prepared,html,trace):
    results=[]
    controls=[c for c in spec.get("controls",[]) if isinstance(c,dict)] if isinstance(spec.get("controls",[]),list) else []
    views=[v for v in spec.get("views",[]) if isinstance(v,dict)] if isinstance(spec.get("views",[]),list) else []
    intermediates=[x for x in spec.get("intermediates",[]) if isinstance(x,dict)] if isinstance(spec.get("intermediates",[]),list) else []
    claims=[c for c in spec.get("claims",[]) if isinstance(c,dict)] if isinstance(spec.get("claims",[]),list) else []
    ids={c.get("id") for c in controls if isinstance(c.get("id"),str)}; valid_refs={"control:"+x for x in ids}|{"view:"+str(i) for i in range(len(views))}|{"exploration:0","exploration:1","exploration:2"}
    bad=[]
    plan=spec.get("plan") if isinstance(spec.get("plan"),dict) else {}
    outcomes=plan.get("learning_outcomes",[]) if isinstance(plan.get("learning_outcomes",[]),list) else []
    for item in outcomes:
        if not isinstance(item,dict): bad.append("malformed outcome"); continue
        refs=item.get("covered_by",[]); bad.extend(x for x in refs if x not in valid_refs)
        if not refs: bad.append("uncovered outcome")
    results.append(_result("C0",not bad,"unknown coverage IDs: "+", ".join(map(str,bad)),["plan"]))
    errs=validate_schema(spec); results.append(_result("C1",not errs,"; ".join(errs),list({e.split()[-1] for e in errs})))
    try:
        if re.search(r"</script",spec.get("compute",""),re.I): raise ValueError("script-closing sequence")
        _eval({**spec,"compute":spec.get("compute","")},_defaults(spec)); syntax=True; msg=""
    except Exception as exc: syntax=False; msg=str(exc)[:180]
    results.append(_result("C2",syntax,msg,["compute","custom_svg"]))
    default_obj=None
    try: default_obj=json.loads(_eval(spec,_defaults(spec))); ok=_finite(default_obj)
    except Exception as exc: ok=False; msg=str(exc)[:180]
    results.append(_result("C3",ok,"default compute produced invalid output" if not ok else "",["compute","controls"]))
    fuzz_ok=syntax
    if syntax:
        rng=random.Random(17)
        samples=[]
        for _ in range(20):
            p=_defaults(spec)
            for c in controls:
                if c.get("type") in ("slider","number"): p[c["id"]]=rng.uniform(float(c.get("min",0)),float(c.get("max",1)))
            samples.append(p)
        for c in controls:
            if c.get("type") in ("slider","number"):
                for x in (c.get("min",0),c.get("max",1),0): q=_defaults(spec);q[c["id"]]=x;samples.append(q)
        try:
            fuzz_ok=all(_finite(json.loads(_eval(spec,p))) for p in samples)
        except Exception:fuzz_ok=False
    results.append(_result("C4",fuzz_ok,"fuzz/edge input threw or produced non-finite output",["compute","controls"]))
    matter=True
    if default_obj is not None:
        for c in controls:
            if c.get("role")=="view_toggle":continue
            q=_defaults(spec)
            if c.get("type") in ("slider","number"):q[c["id"]]=c.get("max") if q.get(c["id"])!=c.get("max") else c.get("min")
            elif c.get("type")=="toggle":q[c["id"]]=not q.get(c["id"])
            elif c.get("type")=="select" and c.get("options"):q[c["id"]]=next((x for x in c["options"] if x!=q.get(c["id"])),q.get(c["id"]))
            elif c.get("type")=="matrix" and isinstance(q.get(c["id"]),list) and q[c["id"]]:
                q[c["id"]]=json.loads(json.dumps(q[c["id"]]))
                if isinstance(q[c["id"]][0],list) and q[c["id"]][0]: q[c["id"]][0][0]=float(q[c["id"]][0][0])+1
                elif q[c["id"]]: q[c["id"]][0]=float(q[c["id"]][0])+1
            try:
                if json.loads(_eval(spec,q))==default_obj:matter=False
            except Exception:matter=False
    results.append(_result("C5",matter,"one or more controls do not change output",["controls","compute"]))
    def expressions(items,key):
        if not isinstance(items,list) or any(not isinstance(x,dict) for x in items): return False
        try:return all(_eval(spec,{**_defaults(spec),**x.get("inputs",x.get("preset",{}))},x.get(key,"false")) for x in items)
        except Exception:return False
    results.append(_result("C6",expressions(spec.get("tests",[]),"assert"),"a mathematical test failed",["tests","compute"]))
    results.append(_result("C7",expressions(spec.get("explorations",[]),"expect"),"an exploration expectation failed",["explorations","compute"]))
    bindings=True
    if default_obj is not None:
        bindings=all(_path(default_obj,v.get("bind","")) is not None for v in views if v.get("bind")) and all(_path(default_obj,x.get("key","")) is not None for x in intermediates)
    results.append(_result("C8",bindings,"view or intermediate binding is absent",["views","intermediates","compute"]))
    svg_ok=True
    if spec.get("custom_svg"):
        try:
            import quickjs
            ctx=quickjs.Context(); code="const draw=(%s);draw(%s,%s)"%(spec["custom_svg"],json.dumps(_defaults(spec)),json.dumps(default_obj or {})); svg=ctx.eval(code)
            svg_ok=isinstance(svg,str) and svg.lstrip().startswith("<svg") and not re.search(r"<script|</script|<foreignObject|<iframe|<object|<embed|\son\w+=|(?:href|xlink:href)=[\"'](?:https?:|//)",svg,re.I)
        except Exception:svg_ok=False
    results.append(_result("C9",svg_ok,"custom SVG is unsafe or invalid",["custom_svg"]))
    norm=lambda s:re.sub(r"\s+"," ",str(s)).strip().lower(); context=norm(prepared.context); grounding=True
    for claim in claims:
        if claim.get("source")=="paper":
            anchor=norm(claim.get("anchor","")); grounding &= _grounded(anchor,context)
    results.append(_result("C10",grounding,"paper claim lacks a source anchor",["claims"]))
    brief_ok=prepared.mode!="brief_only" or all(c.get("source")!="paper" for c in claims)
    results.append(_result("C11",brief_ok,"brief-only output contains paper claims",["claims","citation"]))
    symbols={str(s.get("symbol","")).lower() for s in spec.get("symbols",[]) if isinstance(s,dict)} if isinstance(spec.get("symbols",[]),list) else set()
    def supported_variable(control):
        variable=str(control.get("paper_variable","")).lower()
        return any(symbol and (symbol==variable or symbol in variable) for symbol in symbols)
    provenance=all(c.get("role") in ("paper_variable","result_selector","view_toggle") and (c.get("role")!="paper_variable" or supported_variable(c)) for c in controls)
    results.append(_result("C12",provenance,"control provenance is incomplete",["controls","symbols"]))
    mechanism=spec.get("mechanism",{}) if isinstance(spec.get("mechanism",{}),dict) else {}; calc=mechanism.get("calculation_scope"); kind=mechanism.get("kind"); scope_ok=calc in ("paper_equation","display_transform","none") and kind in ("paper_equation","reported_results","conceptual_process") and not (kind=="conceptual_process" and calc=="paper_equation")
    results.append(_result("C13",scope_ok,"mechanism and calculation scope conflict",["mechanism","compute"]))
    figure_items=plan.get("figures",[]) if isinstance(plan.get("figures",[]),list) else []; entries={f.get("id"):f for f in figure_items if isinstance(f,dict)}; fig_ok=all(f.get("id") in entries and 0<len(entries[f.get("id")].get("role","").split())<=30 for f in prepared.gated_figures)
    results.append(_result("C14",fig_ok,"figure candidate is missing a concise role",["plan"]))
    meta=record.meta; citation_ok=bool(meta.get("title") or spec.get("title")) and bool(meta.get("authors") or prepared.mode=="brief_only") and bool(meta.get("urls",{}).get("source"))
    results.append(_result("C15",citation_ok,"required source metadata is missing",["title","citation"]))
    offline=not re.search(r"<script[^>]+src=|<link[^>]+href=|@import|\bfetch\s*\(|XMLHttpRequest|\bimport\s*\(|url\s*\(\s*['\"]?https?",html,re.I)
    results.append(_result("C16",offline,"page contains a network dependency",["render"]))
    size=0<len(html.encode("utf-8"))<=4*1024*1024; results.append(_result("C17",size,"HTML is empty or larger than 4 MB",["render"]))
    for r in results: trace.log("check",r["check"],"ok" if r["ok"] else "fail",msg=r["msg"],fields=r["fields"])
    return results

def page_usable(fails): return not any(x["check"] in {"C1","C2","C3","C5","C8","C16","C17"} for x in fails)
