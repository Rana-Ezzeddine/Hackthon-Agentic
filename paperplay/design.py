"""Governed, subject-adaptive component composition."""
from __future__ import annotations
import re

THEMES={"blueprint","aurora","graphite","parchment","circuit","spectrum"}
TYPOGRAPHY={"technical","editorial","compact"}
COMPONENTS={
    "hero":{"split","statement","compact"},
    "source_strip":{"ribbon","card"},
    "concept":{"equation_focus","narrative","two_column"},
    "symbols":{"table","chips"},
    "paper_figure":{"framed","annotated"},
    "playground":{"studio","dashboard","canvas"},
    "explorations":{"cards","steps"},
    "limitation":{"callout","margin_note"},
    "evidence":{"ledger","timeline"},
    "appendix":{"accordions","bibliography"},
}
REQUIRED=("hero","concept","playground","explorations","limitation","evidence")

def _subject_defaults(spec):
    text=" ".join((str(spec.get("title","")),str(spec.get("plan",{}).get("core_idea","")))).lower()
    if re.search(r"attention|matrix|vector|neural|transformer",text): return "blueprint","technical","studio"
    if re.search(r"circuit|filter|signal|frequency|voltage",text): return "circuit","technical","canvas"
    if re.search(r"probab|entropy|bayes|information|distribution",text): return "spectrum","editorial","dashboard"
    if re.search(r"graph|network|page.?rank|node",text): return "aurora","technical","canvas"
    return "parchment","editorial","studio"

def normalize_design(spec):
    theme,typography,play_variant=_subject_defaults(spec)
    raw=spec.get("design") if isinstance(spec.get("design"),dict) else {}
    composition=raw.get("composition",[]) if isinstance(raw.get("composition",[]),list) else []
    clean=[];seen=set()
    for item in composition[:12]:
        if not isinstance(item,dict): continue
        name=item.get("component");variant=item.get("variant")
        if name not in COMPONENTS or name in seen: continue
        if variant not in COMPONENTS[name]: variant=sorted(COMPONENTS[name])[0]
        clean.append({"component":name,"variant":variant});seen.add(name)
    defaults=[
        {"component":"hero","variant":"split"},
        {"component":"source_strip","variant":"ribbon"},
        {"component":"concept","variant":"equation_focus"},
        {"component":"symbols","variant":"chips"},
        {"component":"paper_figure","variant":"framed"},
        {"component":"playground","variant":play_variant},
        {"component":"explorations","variant":"cards"},
        {"component":"limitation","variant":"callout"},
        {"component":"evidence","variant":"ledger"},
        {"component":"appendix","variant":"accordions"},
    ]
    fallback={x["component"]:x for x in defaults}
    for name in REQUIRED:
        if name not in seen: clean.append(fallback[name]);seen.add(name)
    # Only enforce dependencies: hero opens, evidence closes, explorations follow the lab.
    hero=next(x for x in clean if x["component"]=="hero")
    evidence=next(x for x in clean if x["component"]=="evidence")
    middle=[x for x in clean if x["component"] not in ("hero","evidence")]
    lab=next(i for i,x in enumerate(middle) if x["component"]=="playground")
    explore=next(i for i,x in enumerate(middle) if x["component"]=="explorations")
    if explore<lab:
        item=middle.pop(explore);lab=next(i for i,x in enumerate(middle) if x["component"]=="playground");middle.insert(lab+1,item)
    accent=raw.get("accent","")
    if not isinstance(accent,str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",accent): accent=""
    spec["design"]={"theme":raw.get("theme") if raw.get("theme") in THEMES else theme,
                    "typography":raw.get("typography") if raw.get("typography") in TYPOGRAPHY else typography,
                    "accent":accent,"rationale":str(raw.get("rationale", ""))[:240],
                    "composition":[hero]+middle+[evidence]}
    return spec

def validate_design(spec):
    design=spec.get("design")
    if not isinstance(design,dict): return ["design must be an object"]
    errors=[]
    if design.get("theme") not in THEMES: errors.append("invalid design theme")
    if design.get("typography") not in TYPOGRAPHY: errors.append("invalid typography")
    composition=design.get("composition")
    if not isinstance(composition,list): return errors+["composition must be a list"]
    names=[]
    for item in composition:
        if not isinstance(item,dict) or item.get("component") not in COMPONENTS: errors.append("unknown component");continue
        name=item["component"];names.append(name)
        if item.get("variant") not in COMPONENTS[name]: errors.append("invalid component variant")
    for name in REQUIRED:
        if names.count(name)!=1: errors.append("required component "+name)
    if names and names[0]!="hero": errors.append("hero must be first")
    if names and names[-1]!="evidence": errors.append("evidence must be last")
    return errors
