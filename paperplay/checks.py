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
def _valid_v2_output(value,path=()):
    """A null matrix cell denotes a masked score; scalar results stay finite."""
    if value is None:return bool(path) and path[0]=="matrices"
    if isinstance(value,float):return math.isfinite(value)
    if isinstance(value,dict):return all(_valid_v2_output(item,path+(key,)) for key,item in value.items())
    if isinstance(value,list):return all(_valid_v2_output(item,path) for item in value)
    return True
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
    if spec.get("format")=="focus-guided-v2":
        return _run_checks_v2(spec,record,prepared,html,trace)
    results=[];controls=lesson_controls(spec);components=lesson_components(spec);defaults=_defaults(spec)
    plan=spec.get("lesson_plan",{}) if isinstance(spec.get("lesson_plan"),dict) else {};outcomes=plan.get("outcomes",[]) if isinstance(plan.get("outcomes"),list) else []
    outcome_ids=[x.get("id") for x in outcomes if isinstance(x,dict)];step_ids=[x.get("outcome_id") for x in spec.get("steps",[]) if isinstance(x,dict)];recap_ids=[x.get("outcome_id") for x in spec.get("recap",[]) if isinstance(x,dict)]
    coverage=bool(outcome_ids) and sorted(outcome_ids)==sorted(step_ids)==sorted(recap_ids) and len(outcome_ids)==len(set(outcome_ids))
    results.append(_result("C0",coverage,"every outcome needs exactly one step and recap line",["lesson_plan","steps","recap"]))
    errs=validate_schema(spec)
    schema_fields=set()
    for error in errs:
        if "outcome" in error or "recap" in error:schema_fields.update(("lesson_plan","steps","recap"))
        elif "concept" in error or "what_it_is" in error:schema_fields.add("concept")
        elif "compute" in error:schema_fields.add("compute")
        elif "test" in error:schema_fields.add("tests")
        elif "mechanism" in error or "scope" in error:schema_fields.add("mechanism")
        else:schema_fields.add("steps")
    results.append(_result("C1",not errs,"; ".join(errs),sorted(schema_fields)))
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
    ineffective=[]
    if default_obj is not None:
        seen=set()
        for c in controls:
            if c.get("id") in seen:continue
            seen.add(c.get("id"))
            if c.get("role")=="view_toggle":continue
            q=dict(defaults);q[c["id"]]=_changed(c,q.get(c["id"]))
            try:
                if json.loads(_eval(spec,q))==default_obj:ineffective.append(c["id"])
            except Exception:ineffective.append(c["id"])
    else:ineffective=[c.get("id","") for c in controls]
    results.append(_result("C5",not ineffective,"controls that do not change compute output: "+", ".join(ineffective),["steps","compute"]))
    bad_tests=[]
    for test in spec.get("tests",[]):
        if not isinstance(test,dict):bad_tests.append("malformed test");continue
        try:
            if not _eval(spec,{**defaults,**test.get("inputs",{})},test.get("assert","false")):bad_tests.append(str(test.get("name","unnamed"))+" returned false")
        except Exception as exc:bad_tests.append(str(test.get("name","unnamed"))+" threw "+type(exc).__name__)
    results.append(_result("C6",not bad_tests,"; ".join(bad_tests),["tests","compute"]))
    bad_guides=[]
    for step in spec.get("steps",[]):
        if not isinstance(step,dict) or not isinstance(step.get("guide"),dict):bad_guides.append(str(step.get("id","unknown")) if isinstance(step,dict) else "unknown");continue
        g=step["guide"]
        try:
            reasons=[];changed=bool(g.get("preset")) and any(defaults.get(k)!=v for k,v in g.get("preset",{}).items())
            if not changed:reasons.append("preset changes no default")
            if "r." not in str(g.get("expect","")):reasons.append("expect does not test r")
            elif not _eval(spec,{**defaults,**g.get("preset",{})},g.get("expect","false")):reasons.append("expect returned false")
            computed=json.loads(_eval(spec,{**defaults,**g.get("preset",{})}))
            if "expect returned false" in reasons: reasons[-1]+="; observed %s=%r"%(g.get("evidence_bind"),_path(computed,g.get("evidence_bind")))
            if _path(computed,g.get("evidence_bind")) is None:reasons.append("evidence_bind is missing")
            if reasons:bad_guides.append(str(step.get("id","unknown"))+": "+", ".join(reasons))
        except Exception as exc:bad_guides.append(str(step.get("id","unknown"))+": threw "+type(exc).__name__)
    results.append(_result("C7",not bad_guides,"; ".join(bad_guides),["steps"]))
    bad_bindings=[]
    if default_obj is None:bad_bindings.append("compute has no default result")
    else:
        for component in components:
            for bind in _component_binds(component):
                value=_path(default_obj,bind)
                if value is None:bad_bindings.append(component.get("type","")+" missing "+str(bind))
            if component.get("type")=="step_through" and component.get("bind") and not isinstance(_path(default_obj,component.get("bind")),list):
                bad_bindings.append("step_through bind must resolve to an array")
            if component.get("type")=="sweep_plot" and not isinstance(_path(default_obj,component.get("bind","")),(int,float)):
                bad_bindings.append("sweep_plot bind must be a scalar result path, not a precomputed series")
    results.append(_result("C8",not bad_bindings,"; ".join(bad_bindings),["steps","compute"]))
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

def _run_checks_v2(spec,record,prepared,html,trace):
    results=[];errors=validate_schema(spec)
    results.append(_result("V0",not errors,"; ".join(errors),["units","coverage","tests"]))
    units={u.get("id"):u for u in spec.get("units",[]) if isinstance(u,dict)}
    code_ok=True;state_ok=True;meaningful=True;bindings=True;tests_ok=True;guides_ok=True;draw_ok=True
    state_issues=[];control_issues=[];guide_issues=[];test_issues=[]
    forbidden=re.compile(r"</?script|\b(?:document|window|globalThis|fetch|XMLHttpRequest|WebSocket|import|require|eval|constructor|__proto__|localStorage|sessionStorage|navigator|location|setTimeout|setInterval)\b|new\s+Function\b|Math\.random|\bDate\b",re.I)
    visual_bad=re.compile(r"<script|</script|<iframe|<object|<embed|<foreignObject|\son\w+\s*=|javascript:|\b(?:href|src)\s*=\s*['\"](?:https?:|//)",re.I)
    for unit in units.values():
        interaction=unit.get("interaction",{}) if isinstance(unit.get("interaction"),dict) else {}
        compute=interaction.get("compute","");draw=interaction.get("draw","")
        if not isinstance(compute,str) or forbidden.search(compute) or not compute.strip():code_ok=False;continue
        if draw and (not isinstance(draw,str) or forbidden.search(draw)):code_ok=False;continue
        controls=[c for c in interaction.get("controls",[]) if isinstance(c,dict)]
        defaults={c.get("id"):c.get("default") for c in controls if c.get("id")}
        try:
            default=json.loads(_eval({"compute":compute},defaults))
            if not isinstance(default,dict) or not _valid_v2_output(default):
                state_ok=False;state_issues.append(unit.get("id", "unit")+": invalid default compute output")
            for control in controls:
                if control.get("type") not in {"slider","number","toggle","select","matrix"}:continue
                changed=dict(defaults);cid=control["id"]
                if control["type"] in {"slider","number"}:
                    changed[cid]=control.get("max") if defaults[cid]!=control.get("max") else control.get("min")
                elif control["type"]=="toggle":changed[cid]=not defaults[cid]
                elif control["type"]=="select":
                    options=[x.get("value") if isinstance(x,dict) else x for x in control.get("options",[])]
                    changed[cid]=next((x for x in options if x!=defaults[cid]),defaults[cid])
                else:
                    changed[cid]=json.loads(json.dumps(defaults[cid]));matrix=changed[cid]
                    if isinstance(matrix,list) and matrix:
                        if isinstance(matrix[0],list) and matrix[0]:matrix[0][0]=float(matrix[0][0])+1
                        else:matrix[0]=float(matrix[0])+1
                varied=json.loads(_eval({"compute":compute},changed))
                if varied==default or not _valid_v2_output(varied):
                    meaningful=False;control_issues.append("%s control %s: unchanged or nonfinite output at %r"%(unit.get("id"),cid,changed[cid]))
                if control["type"] in {"slider","number"}:
                    for edge in (control.get("min"),control.get("max")):
                        if edge is None:continue
                        probe={**defaults,cid:edge}
                        if not _valid_v2_output(json.loads(_eval({"compute":compute},probe))):
                            state_ok=False;state_issues.append("%s control %s: invalid output at boundary %r"%(unit.get("id"),cid,edge))
            for view in interaction.get("views",[]):
                if isinstance(view,dict) and view.get("type")!="custom":bindings &= _path(default,view.get("bind","")) is not None
            for metric in interaction.get("metrics",[]):
                if isinstance(metric,dict):bindings &= _path(default,metric.get("key","")) is not None
            for step in unit.get("explorations",[]):
                if isinstance(step,dict):
                    state={**defaults,**step.get("preset",{})}
                    try:passed=bool(_eval({"compute":compute},state,step.get("expect","false")))
                    except Exception as exc:passed=False;guide_issues.append("%s guide %r: expression error %s"%(unit.get("id"),step.get("title"),str(exc)[:80]))
                    if not passed:
                        guides_ok=False
                        if not any(step.get("title","") in item for item in guide_issues):
                            guide_issues.append("%s guide %r: false for preset %s; computed values %s"%(unit.get("id"),step.get("title"),json.dumps(step.get("preset",{})),json.dumps(json.loads(_eval({"compute":compute},state)).get("values",{}))[:400]))
            for test in spec.get("tests",[]):
                if isinstance(test,dict) and test.get("unit_id")==unit.get("id"):
                    state={**defaults,**test.get("inputs",{})}
                    try:passed=bool(_eval({"compute":compute},state,test.get("assert","false")))
                    except Exception as exc:passed=False;test_issues.append("%s test %r: expression error %s"%(unit.get("id"),test.get("name"),str(exc)[:80]))
                    if not passed:
                        tests_ok=False
                        if not any(test.get("name","") in item for item in test_issues):
                            test_issues.append("%s test %r: false for inputs %s; computed values %s"%(unit.get("id"),test.get("name"),json.dumps(test.get("inputs",{})),json.dumps(json.loads(_eval({"compute":compute},state)).get("values",{}))[:400]))
            if draw:
                import quickjs
                ctx=quickjs.Context();ctx.set_time_limit(.5);ctx.set_memory_limit(32*1024*1024)
                output=ctx.eval("const draw=(%s);draw(%s,%s)"%(draw,json.dumps(defaults),json.dumps(default)))
                draw_ok &= isinstance(output,str) and not visual_bad.search(output)
        except Exception as exc:
            state_ok=False;state_issues.append("%s: %s"%(unit.get("id"),str(exc)[:120]))
    results.extend([
        _result("V1",code_ok,"unsafe or absent compute/draw code",["units"]),
        _result("V2",state_ok,"; ".join(state_issues) if state_issues else "all default and boundary states are valid",["units"]),
        _result("V3",meaningful,"; ".join(control_issues) if control_issues else "all controls change the state",["units"]),
        _result("V4",bindings,"a view or metric binding is absent",["units"]),
        _result("V5",guides_ok,"; ".join(guide_issues) if guide_issues else "guided presets pass",["units"]),
        _result("V6",tests_ok,"; ".join(test_issues) if test_issues else "calculation tests pass",["tests"]),
        _result("V7",draw_ok,"custom visual output is unsafe",["units"]),
    ])
    context=prepared.context;grounded=True
    known_refs={s.anchor for s in record.sections}
    known_refs.update(str(item.get("id")) for collection in (record.equations,record.figures,record.tables,record.algorithms,record.theorems) for item in collection if item.get("id"))
    for unit in spec.get("units",[]):
        if not isinstance(unit,dict):grounded=False;continue
        refs=unit.get("source_refs",[])
        if not isinstance(refs,list) or not refs or any(ref not in known_refs for ref in refs):grounded=False
    for claim in spec.get("claims",[]):
        if not isinstance(claim,dict) or claim.get("source_ref") not in known_refs or not _grounded(claim.get("anchor",""),context):grounded=False
    results.append(_result("V8",grounded,"a paper claim lacks a source anchor",["claims"]))
    offline=not re.search(r"<script[^>]+src=|<link[^>]+href=|@import|\bfetch\s*\(|XMLHttpRequest|\bimport\s*\(|url\s*\(\s*['\"]?https?",html,re.I)
    results.append(_result("V9",offline,"page contains a network dependency",["render"]))
    results.append(_result("V10",0<len(html.encode("utf-8"))<=12*1024*1024,"HTML is empty or larger than 12 MB",["render"]))
    structure=all(x in html for x in ('id="learning-path"','id="synthesis"','id="coverage-list"','GUIDED EXPLORATIONS','Expand together'))
    results.append(_result("V11",structure,"base page structure was lost",["render"]))
    for result in results:trace.log("check",result["check"],"ok" if result["ok"] else "fail",msg=result["msg"],fields=result["fields"])
    return results


def page_usable(fails): return not any(x["check"].startswith("V") or x["check"] in {"C0","C1","C2","C3","C5","C7","C8","C16","C17"} for x in fails)
