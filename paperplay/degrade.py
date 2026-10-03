"""Conservative field-level degradation."""
from __future__ import annotations

def degrade(spec,failures,trace):
    out=dict(spec); notices=[]; ids={f["check"] for f in failures}
    if "C9" in ids:
        out["custom_svg"]=""; out["views"]=[v for v in out.get("views",[]) if v.get("type")!="custom"]
        notices.append("A broken optional custom diagram was removed.")
    if "C10" in ids:
        claims=[]
        for c in out.get("claims",[]):
            if c.get("source")=="paper": c={**c,"source":"simplification","text":"Unverified simplification: "+c.get("text","")}
            claims.append(c)
        out["claims"]=claims; notices.append("Unanchored claims are visibly marked as simplifications.")
    trace.log("degrade","safe_degradation","applied" if notices else "none",notices=notices)
    return out,notices

