"""Govern the lesson-shaped component library selected by the model."""
from __future__ import annotations
import re

INPUTS={"slider","number","toggle","select","matrix_editor","vector_editor","distribution_editor"}
DISPLAYS={"bar","line","heatmap","table","vector_view","value_readout","equation_live"}
EXPLANATORY={"flow_diagram","compare_ab","step_through","sweep_plot","custom_svg"}
COMPONENTS=DISPLAYS|EXPLANATORY

def lesson_controls(spec):
    return [c for step in spec.get("steps",[]) if isinstance(step,dict)
            for c in step.get("controls",[]) if isinstance(c,dict)]

def lesson_components(spec):
    return [c for step in spec.get("steps",[]) if isinstance(step,dict)
            for c in step.get("components",[]) if isinstance(c,dict)]

def normalize_design(spec):
    """Normalize harmless aliases while preserving the model's teaching decisions."""
    steps=spec.get("steps",[]) if isinstance(spec.get("steps"),list) else []
    for step in steps:
        if not isinstance(step,dict): continue
        controls=step.get("controls") if isinstance(step.get("controls"),list) else []
        for control in controls:
            if not isinstance(control,dict): continue
            if control.get("type")=="matrix": control["type"]="matrix_editor"
            control.setdefault("role","result_selector")
            control.setdefault("paper_variable","")
        step["controls"]=controls
        step["components"]=[c for c in step.get("components",[]) if isinstance(c,dict)] if isinstance(step.get("components"),list) else []
        explanation=step.get("explanation",[])
        if isinstance(explanation,str): explanation=[explanation]
        step["explanation"]=[str(x)[:900] for x in explanation[:3]]
    ids=[c.get("id") for step in steps if isinstance(step,dict) for c in step.get("controls",[]) if isinstance(c,dict) and isinstance(c.get("id"),str)]
    aliases={re.sub(r"[^a-z0-9]","",cid.lower()):cid for cid in ids}
    for step in steps:
        if not isinstance(step,dict):continue
        for component in step.get("components",[]):
            if isinstance(component,dict) and component.get("type")=="sweep_plot" and component.get("parameter") not in ids:
                alias=re.sub(r"[^a-z0-9]","",str(component.get("parameter","")).lower())
                if alias in aliases:component["parameter"]=aliases[alias]
    return spec

def _valid_id(value): return isinstance(value,str) and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*",value))

def validate_design(spec):
    errors=[]; control_defs={}; control_ids=set(); step_ids=set()
    steps=spec.get("steps")
    if not isinstance(steps,list) or not steps: return ["steps must be a non-empty list"]
    for step in steps:
        if not isinstance(step,dict): errors.append("step must be an object"); continue
        sid=step.get("id")
        if not _valid_id(sid) or sid in step_ids: errors.append("invalid or duplicate step id")
        else: step_ids.add(sid)
        controls=step.get("controls",[]); components=step.get("components",[])
        if not isinstance(controls,list): errors.append("step controls must be a list"); controls=[]
        if not isinstance(components,list) or not components: errors.append("step needs at least one component"); components=[]
        for control in controls:
            if not isinstance(control,dict): errors.append("control must be an object"); continue
            cid=control.get("id")
            if not _valid_id(cid): errors.append("invalid control id")
            else:
                signature=repr(tuple(control.get(k) for k in ("type","default","min","max","step","options","rows","cols","role","paper_variable")))
                if cid in control_defs and control_defs[cid]!=signature: errors.append("shared control has inconsistent definitions: "+cid)
                else: control_defs[cid]=signature;control_ids.add(cid)
            if control.get("type") not in INPUTS: errors.append("unknown input component")
            kind=control.get("type");default=control.get("default")
            if kind in {"slider","number"} and not all(isinstance(control.get(k), (int,float)) for k in ("default","min","max","step")): errors.append("numeric input missing bounds")
            if kind=="toggle" and not isinstance(default,bool): errors.append("toggle default must be boolean")
            if kind=="select" and (not isinstance(control.get("options"),list) or not control.get("options")): errors.append("select needs options")
            if kind=="matrix_editor" and (not isinstance(default,list) or not default or not all(isinstance(row,list) and row for row in default)): errors.append("matrix_editor needs a matrix default")
            if kind in {"vector_editor","distribution_editor"} and (not isinstance(default,list) or not default): errors.append(kind+" needs a vector default")
        for component in components:
            if not isinstance(component,dict) or component.get("type") not in COMPONENTS:
                errors.append("unknown display component"); continue
            if component.get("type") not in EXPLANATORY|{"equation_live"} and not component.get("bind"):
                errors.append("display component missing bind")
            if component.get("type")=="flow_diagram" and not isinstance(component.get("nodes"),list): errors.append("flow_diagram missing nodes")
            if component.get("type")=="flow_diagram" and not isinstance(component.get("edges",[]),list): errors.append("flow_diagram edges must be a list")
            if component.get("type")=="equation_live" and (not component.get("equation") or not isinstance(component.get("bindings"),list)): errors.append("equation_live is incomplete")
            if component.get("type")=="compare_ab":
                if not all(isinstance(component.get(x),dict) for x in ("left","right")): errors.append("compare_ab missing sides")
                elif not all(isinstance(component[x].get("preset"),dict) and component[x].get("bind") for x in ("left","right")): errors.append("compare_ab sides are incomplete")
            if component.get("type")=="step_through" and (not isinstance(component.get("operations"),list) or not component.get("operations") or any(not isinstance(x,dict) or not x.get("bind") for x in component.get("operations",[]))): errors.append("step_through missing operations")
            if component.get("type")=="sweep_plot" and (component.get("parameter") not in control_ids or not component.get("bind") or not all(isinstance(component.get(k),(int,float)) for k in ("min","max","points"))): errors.append("sweep_plot is incomplete")
            if component.get("type")=="custom_svg" and not str(spec.get("custom_svg","")).strip(): errors.append("custom_svg source is missing")
        guide=step.get("guide")
        if not isinstance(guide,dict) or not isinstance(guide.get("preset"),dict) or not guide.get("expect") or not guide.get("evidence_bind"):
            errors.append("step guide is incomplete")
        elif "r." not in str(guide.get("expect")):
            errors.append("step guide must assert a computed observation")
        elif any(key not in control_ids for key in guide.get("preset",{})):
            errors.append("step guide preset uses an unknown control")
    return errors
