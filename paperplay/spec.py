"""Spec parsing, normalization, validation, and patch merge."""
from __future__ import annotations
import json,re
from .design import normalize_design,validate_design

def parse_json(text):
    value=text.strip()
    if value.startswith("```"): value=re.sub(r"^```(?:json)?\s*|\s*```$","",value,flags=re.I)
    obj=json.loads(value)
    if not isinstance(obj,dict): raise ValueError("model output is not an object")
    return obj

def patch_merge(spec,patch):
    out=dict(spec)
    for key,value in patch.items(): out[key]=value
    return out

def normalize_spec(spec,prepared):
    """Normalize harmless model formatting variance without changing mathematics."""
    plan=spec.get("plan") if isinstance(spec.get("plan"),dict) else {}
    figures=plan.get("figures",[])
    if isinstance(figures,list):
        normalized=[]
        for index,item in enumerate(figures):
            if isinstance(item,dict): normalized.append(item); continue
            if isinstance(item,str) and index<len(prepared.gated_figures):
                candidate=prepared.gated_figures[index]
                normalized.append({"id":candidate.get("id"),"role":" ".join(item.split()[:30]),"use":False,"placement":"after_intro","informs_custom_svg":False})
        plan["figures"]=normalized
    spec["plan"]=plan
    symbols={str(s.get("symbol","")).lower() for s in spec.get("symbols",[]) if isinstance(s,dict)} if isinstance(spec.get("symbols",[]),list) else set()
    for control in spec.get("controls",[]) if isinstance(spec.get("controls",[]),list) else []:
        if not isinstance(control,dict): continue
        role=control.get("role")
        variable=str(control.get("paper_variable","")).lower()
        supported=any(symbol and (symbol==variable or symbol in variable) for symbol in symbols)
        if role not in ("paper_variable","result_selector","view_toggle") or (role=="paper_variable" and not supported):
            control["role"]="result_selector"; control["paper_variable"]=""
    return normalize_design(spec)

def validate_schema(spec):
    errors=[]; required=("plan","title","citation","intro","mechanism","symbols","controls","compute","views","intermediates","explorations","limitation","claims","tests","design")
    for key in required:
        if key not in spec: errors.append("missing "+key)
    controls=spec.get("controls",[]) if isinstance(spec.get("controls",[]),list) else []
    explorations=spec.get("explorations",[]) if isinstance(spec.get("explorations",[]),list) else []
    tests=spec.get("tests",[]) if isinstance(spec.get("tests",[]),list) else []
    if len(controls)<2: errors.append("need at least 2 controls")
    if len(explorations)!=2: errors.append("need exactly 2 explorations")
    if len(tests)<3: errors.append("need at least 3 tests")
    if not isinstance(spec.get("compute"),str): errors.append("compute must be text")
    if not isinstance(spec.get("custom_svg",""),str): errors.append("custom_svg must be text")
    ids=[]
    for c in controls:
        if not isinstance(c,dict):
            errors.append("control must be an object"); continue
        cid=c.get("id")
        if not isinstance(cid,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",cid): errors.append("invalid control id")
        elif cid in ids: errors.append("duplicate control id "+cid)
        else: ids.append(cid)
        if c.get("type") not in ("slider","number","toggle","select","matrix"): errors.append("invalid control type")
        if c.get("role") not in ("paper_variable","result_selector","view_toggle"): errors.append("invalid control role")
    errors.extend(validate_design(spec))
    return errors
