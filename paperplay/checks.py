"""C0-C17 checks for lesson structure, mathematics, bindings, and grounding."""
from __future__ import annotations
import json,math,random,re
from difflib import SequenceMatcher
from .design import lesson_components,lesson_controls
from .spec import validate_schema

def _result(check,ok,msg="",fields=None): return {"check":check,"ok":bool(ok),"msg":msg,"fields":fields or []}
def _defaults(spec): return {c["id"]:c.get("default") for c in lesson_controls(spec) if c.get("id")}
def _eval(spec,p,expr=None):
    import quickjs
    ctx=quickjs.Context();ctx.set_time_limit(.5);ctx.set_memory_limit(32*1024*1024)
    tail="JSON.stringify(r)" if expr is None else "Boolean("+expr+")"
    return ctx.eval("'use strict';const compute=(%s);const p=Object.freeze(%s);const r=compute(p);%s"%(spec["compute"],json.dumps(p,separators=(",",":")),tail))
def _finite(value):
    if isinstance(value,float): return math.isfinite(value)
    if isinstance(value,dict): return all(_finite(v) for v in value.values())
    if isinstance(value,list): return all(_finite(v) for v in value)
    return value is not None
def _path(obj,path):
    for key in str(path or "").split("."):
        if not isinstance(obj,dict) or key not in obj:return None
        obj=obj[key]
    return obj
def _grounded(anchor,context):
    clean=lambda s:re.sub(r"[^a-z0-9_]+"," ",str(s).lower()).strip()
    a,c=clean(anchor),clean(context)
    if not a:return False
    if a in c:return True
    aw,cw=a.split(),c.split()
    for size in range(max(1,len(aw)-2),len(aw)+3):
        for i in range(max(0,len(cw)-size+1)):
            if SequenceMatcher(None,a," ".join(cw[i:i+size])).ratio()>=.85:return True
    return False
def _changed(control,value):
    kind=control.get("type")
    if kind in ("slider","number"): return control.get("max") if value!=control.get("max") else control.get("min")
    if kind=="toggle": return not bool(value)
    if kind=="select": return next((x.get("value",x) if isinstance(x,dict) else x for x in control.get("options",[]) if (x.get("value",x) if isinstance(x,dict) else x)!=value),value)
    if kind in ("vector_editor","distribution_editor") and isinstance(value,list) and value:
        out=list(value);out[0]=(float(out[0]) if out else 0)+1;return out
    if kind=="matrix_editor" and isinstance(value,list) and value:
        out=json.loads(json.dumps(value));out[0][0]=float(out[0][0])+1;return out
    return value
def _component_binds(component):
    kind=component.get("type"); binds=[]
    if component.get("bind"): binds.append(component["bind"])
    if kind=="equation_live": binds += [x.get("bind") for x in component.get("bindings",[]) if isinstance(x,dict)]
    if kind=="flow_diagram": binds += [x.get("bind") for x in component.get("nodes",[]) if isinstance(x,dict) and x.get("bind")]
    if kind=="compare_ab": binds += [component.get(side,{}).get("bind") for side in ("left","right")]
    if kind=="step_through": binds += [x.get("bind") for x in component.get("operations",[]) if isinstance(x,dict)]
    if kind=="sweep_plot" and component.get("bind"): binds.append(component["bind"])
    return [x for x in binds if x]

def run_checks(spec,record,prepared,html,trace):
    results=[];controls=lesson_controls(spec);components=lesson_components(spec);defaults=_defaults(spec)
    plan=spec.get("lesson_plan",{}) if isinstance(spec.get("lesson_plan"),dict) else {};outcomes=plan.get("outcomes",[]) if isinstance(plan.get("outcomes"),list) else []
    outcome_ids=[x.get("id") for x in outcomes if isinstance(x,dict)];step_ids=[x.get("outcome_id") for x in spec.get("steps",[]) if isinstance(x,dict)];recap_ids=[x.get("outcome_id") for x in spec.get("recap",[]) if isinstance(x,dict)]
    coverage=bool(outcome_ids) and sorted(outcome_ids)==sorted(step_ids)==sorted(recap_ids) and len(outcome_ids)==len(set(outcome_ids))
    results.append(_result("C0",coverage,"every outcome needs exactly one step and recap line",["lesson_plan","steps","recap"]))
    errs=validate_schema(spec);results.append(_result("C1",not errs,"; ".join(errs),["lesson_plan","concept","steps","recap"]))
    try:
        if re.search(r"</script",spec.get("compute",""),re.I): raise ValueError("script-closing sequence")
        _eval(spec,defaults);syntax=True;msg=""
    except Exception as exc:syntax=False;msg=str(exc)[:180]
    results.append(_result("C2",syntax,msg,["compute","custom_svg"]))
    default_obj=None
    try:default_obj=json.loads(_eval(spec,defaults));valid=_finite(default_obj)
    except Exception:valid=False
    results.append(_result("C3",valid,"default compute produced invalid output",["compute","steps"]))
    fuzz_ok=syntax
    if syntax:
        rng=random.Random(17);samples=[]
        for _ in range(16):
            q=dict(defaults)
            for c in controls:
                if c.get("type") in ("slider","number"):q[c["id"]]=rng.uniform(float(c.get("min",0)),float(c.get("max",1)))
            samples.append(q)
        for c in controls:
            q=dict(defaults);q[c.get("id")]=_changed(c,q.get(c.get("id")));samples.append(q)
        try:fuzz_ok=all(_finite(json.loads(_eval(spec,q))) for q in samples)
        except Exception:fuzz_ok=False
    results.append(_result("C4",fuzz_ok,"edge input threw or produced non-finite output",["compute","steps"]))
    matter=default_obj is not None
    if matter:
        for c in controls:
            if c.get("role")=="view_toggle":continue
            q=dict(defaults);q[c["id"]]=_changed(c,q.get(c["id"]))
            try:matter &= json.loads(_eval(spec,q))!=default_obj
            except Exception:matter=False
    results.append(_result("C5",matter,"one or more lesson controls do not change output",["steps","compute"]))
    try:tests_ok=all(_eval(spec,{**defaults,**x.get("inputs",{})},x.get("assert","false")) for x in spec.get("tests",[]) if isinstance(x,dict))
    except Exception:tests_ok=False
    results.append(_result("C6",tests_ok,"a mathematical test failed",["tests","compute"]))
    guides=[]
    for step in spec.get("steps",[]):
        if isinstance(step,dict) and isinstance(step.get("guide"),dict):guides.append(step["guide"])
    try:guides_ok=len(guides)==len(spec.get("steps",[])) and all(g.get("preset") and any(defaults.get(k)!=v for k,v in g.get("preset",{}).items()) and "r." in str(g.get("expect","")) and _eval(spec,{**defaults,**g.get("preset",{})},g.get("expect","false")) and _path(json.loads(_eval(spec,{**defaults,**g.get("preset",{})})),g.get("evidence_bind")) is not None for g in guides)
    except Exception:guides_ok=False
    results.append(_result("C7",guides_ok,"a guide does not verify its claimed observation",["steps","compute"]))
    bindings=default_obj is not None and all(_path(default_obj,b) is not None for c in components for b in _component_binds(c))
    results.append(_result("C8",bindings,"a lesson component binding is absent",["steps","compute"]))
    svg_ok=True
    if any(c.get("type")=="custom_svg" for c in components):
        try:
            import quickjs
            ctx=quickjs.Context();svg=ctx.eval("const draw=(%s);draw(%s,%s)"%(spec.get("custom_svg",""),json.dumps(defaults),json.dumps(default_obj or {})))
            svg_ok=isinstance(svg,str) and svg.lstrip().startswith("<svg") and not re.search(r"<script|</script|<foreignObject|<iframe|<object|<embed|\son\w+=|(?:href|xlink:href)=[\"'](?:https?:|//)",svg,re.I)
        except Exception:svg_ok=False
    results.append(_result("C9",svg_ok,"custom SVG is unsafe or invalid",["custom_svg","steps"]))
    context=re.sub(r"\s+"," ",prepared.context).strip().lower();claims=spec.get("claims",[]) if isinstance(spec.get("claims"),list) else []
    grounding=all(c.get("source")!="paper" or _grounded(c.get("anchor",""),context) for c in claims if isinstance(c,dict))
    results.append(_result("C10",grounding,"paper claim lacks a source anchor",["claims"]))
    brief_ok=prepared.mode!="brief_only" or all(c.get("source")!="paper" for c in claims if isinstance(c,dict))
    results.append(_result("C11",brief_ok,"brief-only lesson contains paper claims",["claims","citation"]))
    symbols={str(s.get("symbol","")).lower() for s in spec.get("concept",{}).get("symbols",[]) if isinstance(s,dict)} if isinstance(spec.get("concept"),dict) else set()
    provenance=all(c.get("role") in ("paper_variable","result_selector","view_toggle") and (c.get("role")!="paper_variable" or any(s and (s==str(c.get("paper_variable","")).lower() or s in str(c.get("paper_variable","")).lower() or str(c.get("paper_variable","")).lower() in s) for s in symbols)) for c in controls)
    results.append(_result("C12",provenance,"control provenance is incomplete",["steps","concept"]))
    mechanism=spec.get("mechanism",{}) if isinstance(spec.get("mechanism"),dict) else {};scope_ok=mechanism.get("calculation_scope") in ("paper_equation","display_transform","none") and mechanism.get("kind") in ("paper_equation","reported_results","conceptual_process") and not (mechanism.get("kind")=="conceptual_process" and mechanism.get("calculation_scope")=="paper_equation")
    results.append(_result("C13",scope_ok,"mechanism and calculation scope conflict",["mechanism","compute"]))
    figure_items=plan.get("figures",[]) if isinstance(plan.get("figures"),list) else [];entries={f.get("id"):f for f in figure_items if isinstance(f,dict)};fig_ok=all(f.get("id") in entries and 1<=len(entries[f.get("id")].get("role","").split())<=30 for f in prepared.gated_figures)
    results.append(_result("C14",fig_ok,"figure candidate is missing a concise teaching role",["lesson_plan"]))
    meta=record.meta;citation_ok=bool(meta.get("title") or spec.get("concept",{}).get("title")) and bool(meta.get("authors") or prepared.mode=="brief_only") and bool(meta.get("urls",{}).get("source"))
    results.append(_result("C15",citation_ok,"required source metadata is missing",["concept","citation"]))
    offline=not re.search(r"<script[^>]+src=|<link[^>]+href=|@import|\bfetch\s*\(|XMLHttpRequest|\bimport\s*\(|url\s*\(\s*['\"]?https?",html,re.I)
    results.append(_result("C16",offline,"page contains a network dependency",["render"]))
    size=0<len(html.encode("utf-8"))<=4*1024*1024;results.append(_result("C17",size,"HTML is empty or larger than 4 MB",["render"]))
    for result in results:trace.log("check",result["check"],"ok" if result["ok"] else "fail",msg=result["msg"],fields=result["fields"])
    return results

def page_usable(fails): return not any(x["check"] in {"C0","C1","C2","C3","C5","C7","C8","C16","C17"} for x in fails)
