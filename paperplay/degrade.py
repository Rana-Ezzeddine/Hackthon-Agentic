"""Conservative field-level degradation."""
from __future__ import annotations

def degrade(spec,failures,trace):
    out=dict(spec); notices=[]; ids={f["check"] for f in failures}
    if "C9" in ids:
        out["custom_svg"]=""
        out["steps"]=[{**step,"components":[c for c in step.get("components",[]) if c.get("type")!="custom_svg"] or [{"type":"value_readout","title":"Current values","bind":"values","caption":"The unsafe optional diagram was removed."}]} for step in out.get("steps",[])]
        notices.append("A broken optional custom diagram was removed.")
    if "C10" in ids:
        claims=[]
        for c in out.get("claims",[]):
            if c.get("source")=="paper": c={**c,"source":"simplification","text":"Unverified simplification: "+c.get("text","")}
            claims.append(c)
        out["claims"]=claims; notices.append("Unanchored claims are visibly marked as simplifications.")
    trace.log("degrade","safe_degradation","applied" if notices else "none",notices=notices)
    return out,notices
