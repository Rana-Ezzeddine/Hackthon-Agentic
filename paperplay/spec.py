"""Lesson specification parsing, normalization, and validation."""
from __future__ import annotations
import json,re
from .design import lesson_controls,normalize_design,validate_design

def parse_json(text):
    value=text.strip()
    if value.startswith("```"): value=re.sub(r"^```(?:json)?\s*|\s*```$","",value,flags=re.I)
    obj=json.loads(value)
    if not isinstance(obj,dict): raise ValueError("model output is not an object")
    return obj

def patch_merge(spec,patch):
    out=dict(spec);out.update(patch);return out

def normalize_spec(spec,prepared):
    plan=spec.get("lesson_plan") if isinstance(spec.get("lesson_plan"),dict) else {}
    figures=plan.get("figures",[])
    if isinstance(figures,list):
        normalized=[]
        for index,item in enumerate(figures):
            if isinstance(item,dict): normalized.append(item);continue
            if isinstance(item,str) and index<len(prepared.gated_figures):
                candidate=prepared.gated_figures[index]
                normalized.append({"id":candidate.get("id"),"role":" ".join(item.split()[:30]),"use":False,"step_id":""})
        plan["figures"]=normalized
    spec["lesson_plan"]=plan
    normalize_design(spec)
    symbols={str(s.get("symbol","")).lower() for s in spec.get("concept",{}).get("symbols",[]) if isinstance(s,dict)} if isinstance(spec.get("concept"),dict) else set()
    for control in lesson_controls(spec):
        role=control.get("role"); variable=str(control.get("paper_variable","")).lower()
        supported=any(symbol and (symbol==variable or symbol in variable or variable in symbol) for symbol in symbols)
        if role not in ("paper_variable","result_selector","view_toggle") or (role=="paper_variable" and not supported):
            control["role"]="result_selector";control["paper_variable"]=""
    return spec

def validate_schema(spec):
    errors=[]
    for key in ("lesson_plan","concept","citation","mechanism","compute","steps","recap","claims","limitation","tests"):
        if key not in spec: errors.append("missing "+key)
    plan=spec.get("lesson_plan",{}); outcomes=plan.get("outcomes",[]) if isinstance(plan,dict) else []
    steps=spec.get("steps",[]) if isinstance(spec.get("steps"),list) else []
    recap=spec.get("recap",[]) if isinstance(spec.get("recap"),list) else []
    outcome_ids=[o.get("id") for o in outcomes if isinstance(o,dict)]
    step_outcomes=[s.get("outcome_id") for s in steps if isinstance(s,dict)]
    recap_outcomes=[r.get("outcome_id") for r in recap if isinstance(r,dict)]
    if not outcome_ids or len(outcome_ids)!=len(set(outcome_ids)): errors.append("invalid lesson outcomes")
    if sorted(outcome_ids)!=sorted(step_outcomes): errors.append("steps must cover every outcome exactly once")
    if sorted(outcome_ids)!=sorted(recap_outcomes): errors.append("recap must cover every outcome exactly once")
    concept=spec.get("concept",{})
    if not isinstance(concept,dict) or not concept.get("title"): errors.append("missing concept title")
    if not isinstance(concept.get("what_it_is",[]),list) or not 2<=len(concept.get("what_it_is",[]))<=4: errors.append("what_it_is needs 2-4 sentences")
    if not isinstance(spec.get("compute"),str): errors.append("compute must be text")
    if not isinstance(spec.get("custom_svg",""),str): errors.append("custom_svg must be text")
    tests=spec.get("tests",[])
    if not isinstance(tests,list) or not 3<=len(tests)<=6: errors.append("tests need 3-6 cases")
    for c in lesson_controls(spec):
        cid=c.get("id")
        if not isinstance(cid,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*",cid): errors.append("invalid control id")
        if c.get("role") not in ("paper_variable","result_selector","view_toggle"): errors.append("invalid control role")
    mechanism=spec.get("mechanism",{})
    if not isinstance(mechanism,dict) or mechanism.get("kind") not in ("paper_equation","reported_results","conceptual_process"): errors.append("invalid mechanism kind")
    if not isinstance(mechanism,dict) or mechanism.get("calculation_scope") not in ("paper_equation","display_transform","none"): errors.append("invalid calculation scope")
    errors.extend(validate_design(spec))
    return errors
