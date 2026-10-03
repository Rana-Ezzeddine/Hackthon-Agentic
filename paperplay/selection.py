"""Focus parsing, deterministic section ranking, and context assembly."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

STOP={"the","and","for","with","that","this","from","into","what","why","how","show","explain","using","understand"}
@dataclass
class PreparedSource:
    context: str; selected_anchors: list[str]; chars: int; mode: str
    retrieval_errors: list[str]=field(default_factory=list); gated_figures: list[dict]=field(default_factory=list)
    gated_tables: list[dict]=field(default_factory=list)

def parse_focus(text):
    secs=re.findall(r"(?:section|sec\.?|§)\s*([A-Z]?\d+(?:\.\d+)*)",text,re.I)
    eqs=re.findall(r"(?:equation|eq\.?)\s*\(?([\w.-]+)\)?",text,re.I)
    figs=re.findall(r"(?:figure|fig\.?)\s*(\d+)",text,re.I)
    words=[w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_^-]*",text) if w.lower() not in STOP and len(w)>1]
    phrases=[" ".join(words[i:i+n]) for n in (2,3,4) for i in range(max(0,len(words)-n+1))]
    return {"sections":secs,"equations":eqs,"figures":figs,"keywords":set(words),"phrases":phrases}

def _score(section, wanted, record, focus):
    head=section.heading.lower(); body=section.text.lower(); score=0
    if any(section.number.startswith(x) for x in wanted["sections"]): score+=20
    nums={str(e.get("number","")) for e in record.equations if e.get("id") in section.eq_ids}
    if nums & set(wanted["equations"]): score+=15
    score += 8*any(p in head for p in wanted["phrases"]) + 5*any(p in body for p in wanted["phrases"])
    score += sum(3 for w in wanted["keywords"] if w in head) + min(10,sum(1 for w in wanted["keywords"] if w in body))
    if section.eq_ids and re.search(r"calcul|equation|derive|value",focus,re.I):score+=4
    return score

def select(record, case, trace):
    wanted=parse_focus(case.focus); ranked=sorted(enumerate(record.sections),key=lambda x:_score(x[1],wanted,record,case.focus),reverse=True)
    chosen={i for i,s in ranked[:5] if i==ranked[0][0] or _score(s,wanted,record,case.focus)>0} if ranked else set()
    if not chosen and record.sections:chosen={0}
    ordered=[s for i,s in enumerate(record.sections) if i in chosen]
    blocks=[]
    title=record.meta.get("title") or case.hints.get("title") or "Source"
    author=((record.meta.get("authors") or [{}])[0].get("name") or "Unknown author")
    blocks.append("[SOURCE METADATA] %s · %s · %s"%(title,author,record.mode))
    blocks.append("[SELECTED SOURCE MATERIAL]")
    for s in ordered:
        block="[§%s %s] %s"%(s.number or "?",s.heading,s.text)
        if sum(map(len,blocks))+len(block)>10000: continue
        blocks.append(block)
        for eq in record.equations:
            if eq.get("id") in s.eq_ids: blocks.append("[Eq. (%s)] $%s$"%(eq.get("number",""),eq.get("latex","")))
    selected={s.anchor for s in ordered}
    gated_tables=[]
    for table in record.tables:
        hay=(str(table.get("caption",""))+" "+str(table.get("markdown",""))).lower()
        relevant=table.get("section") in selected or sum(1 for word in wanted["keywords"] if word in hay)>=2
        if relevant:
            gated_tables.append(table)
            block="[TABLE %s · %s] %s\n%s"%(table.get("id",""),table.get("number",""),table.get("caption",""),table.get("markdown",""))
            if len("\n".join(blocks))+len(block)<12000: blocks.append(block)
    cited={key for section in ordered for key in section.cite_keys}
    for ref in record.references:
        if ref.get("key") in cited and len("\n".join(blocks))+len(ref.get("text",""))<12000: blocks.append("[REFERENCE %s] %s"%(ref.get("number",""),ref.get("text","")))
    context="\n".join(blocks)[:12000]
    gated=[]
    for fig in record.figures:
        cap=fig.get("caption","").lower(); n=str(fig.get("number",""))
        if n in wanted["figures"] or sum(1 for w in wanted["keywords"] if w in cap)>=2: gated.append(fig)
    result=PreparedSource(context,[s.anchor for s in ordered],len(context),record.mode,gated_figures=gated[:2],gated_tables=gated_tables[:3])
    trace.log("select","rank_sections","ok",selected=result.selected_anchors,chars=result.chars,figure_candidates=[f.get("id") for f in result.gated_figures],table_candidates=[t.get("id") for t in result.gated_tables])
    return result
