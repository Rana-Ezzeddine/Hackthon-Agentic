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
    if spec.get("format")=="focus-guided-v2":
        return spec
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
    if spec.get("format")=="focus-guided-v2":
        return _validate_v2(spec)
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


def _validate_v2(spec):
    errors=[]
    for key in ("title","focus_statement","summary_html","coverage","units","synthesis_html","limitations_html","claims","tests"):
        if key not in spec:errors.append("missing "+key)
    units=spec.get("units",[])
    if not isinstance(units,list) or not units:return errors+["need at least one learning unit"]
    ids=[];total_explorations=0
    for index,unit in enumerate(units):
        if not isinstance(unit,dict):errors.append("unit must be an object");continue
        uid=unit.get("id")
        if not isinstance(uid,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*",uid):errors.append("invalid unit id")
        elif uid in ids:errors.append("duplicate unit id")
        else:ids.append(uid)
        for field in ("title","question","orientation_html","interpretation_html"):
            if not isinstance(unit.get(field),str) or not unit[field].strip():errors.append("missing unit "+field)
        interaction=unit.get("interaction",{})
        if not isinstance(interaction,dict):errors.append("missing unit interaction");continue
        controls=interaction.get("controls",[]);views=interaction.get("views",[])
        if not isinstance(controls,list) or not controls:errors.append("unit needs controls");controls=[]
        if not isinstance(views,list) or not views:errors.append("unit needs views");views=[]
        cids=set()
        for control in controls:
            if not isinstance(control,dict):errors.append("invalid control");continue
            cid=control.get("id")
            if not isinstance(cid,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",cid) or cid in cids:errors.append("invalid or duplicate control id")
            else:cids.add(cid)
            if control.get("type") not in {"slider","number","toggle","select","matrix"}:errors.append("invalid control type")
            if "default" not in control:errors.append("control missing default")
        for view in views:
            if not isinstance(view,dict) or view.get("type") not in {"bar","line","heatmap","matrix","table","custom"}:errors.append("invalid view")
            elif view.get("type")!="custom" and not view.get("bind"):errors.append("view missing bind")
        if any(isinstance(view,dict) and view.get("type")=="custom" for view in views) and not interaction.get("draw"):
            errors.append("custom view needs draw")
        if not isinstance(interaction.get("compute"),str) or not interaction["compute"].strip():errors.append("missing unit compute")
        if not isinstance(interaction.get("draw",""),str):errors.append("invalid unit draw")
        steps=unit.get("explorations",[])
        if not isinstance(steps,list):errors.append("invalid explorations");continue
        total_explorations+=len(steps)
        for step in steps:
            if not isinstance(step,dict) or not all(isinstance(step.get(k),str) and step[k].strip() for k in ("title","prediction","observe","why","expect")):errors.append("incomplete exploration")
            if not isinstance(step,dict) or not isinstance(step.get("preset"),dict) or not set(step["preset"]).issubset(cids):errors.append("invalid exploration preset")
    if total_explorations<2:errors.append("need at least two guided explorations")
    coverage=spec.get("coverage",[])
    if not isinstance(coverage,list) or not coverage:errors.append("focus coverage is empty")
    else:
        for item in coverage:
            if not isinstance(item,dict) or not item.get("need") or item.get("unit_id") not in ids:errors.append("invalid focus coverage")
    if not isinstance(spec.get("claims"),list) or not spec["claims"]:
        errors.append("need paper-grounded claims")
    tests=spec.get("tests",[])
    if not isinstance(tests,list) or len(tests)<3:errors.append("need at least three tests")
    else:
        for test in tests:
            if not isinstance(test,dict) or test.get("unit_id") not in ids or not isinstance(test.get("inputs"),dict) or not isinstance(test.get("assert"),str):errors.append("invalid test")
    return errors
