"""Render a self-contained explorable lesson from a validated LessonSpec."""
from __future__ import annotations
import html,json,os,re
from pathlib import Path
from .design import normalize_design
from .figures import data_uri

ROOT=Path(__file__).resolve().parent.parent
def _json(value): return re.sub(r"</script",r"<\\/script",json.dumps(value,ensure_ascii=False,separators=(",",":"),default=str),flags=re.I).replace("<!--","<\\!--")
def _script_source(value): return re.sub(r"</script",r"<\\/script",value if isinstance(value,str) else "",flags=re.I)
def _clean_name(value):
    value=re.sub(r"\bfootnotemark\b\s*:?\s*\d*","",str(value),flags=re.I)
    value=re.sub(r"(?:^|\s)\d+(?=\s|$)"," ",value)
    return re.sub(r"\s+"," ",value).strip(" ,;·")
def _year(meta):
    text=" ".join(meta.get("dates",{}).get("history",[])) if isinstance(meta.get("dates"),dict) else str(meta.get("dates",""))
    match=re.search(r"\b(19|20)\d{2}\b",text);return match.group(0) if match else ""
def _dates(meta):
    values=meta.get("dates",{}).get("history",[]) if isinstance(meta.get("dates"),dict) else []
    clean=[]
    for value in values:
        match=re.search(r"v\d+\]\s*(.+?)(?:\s*\(|$)",str(value))
        clean.append(match.group(1).strip() if match else re.sub(r"^Submission history\s*","",str(value)).strip())
    return [x for x in clean if x]

def render(spec,record,prepared,notices=None):
    normalize_design(spec);template=(ROOT/"templates"/"page.html").read_text(encoding="utf-8");meta=record.meta
    authors=[]
    for author in meta.get("authors",[]):
        if not isinstance(author,dict):continue
        name=_clean_name(author.get("name",""));aff=[_clean_name(x) for x in author.get("affiliations",[]) if _clean_name(x)]
        if name:authors.append({"name":name,"affiliations":aff})
    selected={s.anchor:s for s in record.sections if s.anchor in set(prepared.selected_anchors)}
    cited={key for section in selected.values() for key in section.cite_keys}
    references=[r for r in record.references if r.get("key") in cited]
    urls=dict(meta.get("urls",{}));first_anchor=next(iter(selected),"")
    if first_anchor and urls.get("html"):urls["section"]=urls["html"]+"#"+first_anchor
    categories=meta.get("categories",{});categories=categories.get("all",[]) if isinstance(categories,dict) else categories
    paper={"title":meta.get("title",""),"authors":authors,"year":_year(meta),"arxiv_id":meta.get("arxiv_id",""),"version":meta.get("version",""),"dates":_dates(meta),"categories":categories or [],"doi":meta.get("doi",""),"journal_ref":meta.get("journal_ref",""),"license":meta.get("license",""),"urls":urls,"references":references,"mode":record.mode}
    roles={f.get("id"):f for f in spec.get("lesson_plan",{}).get("figures",[]) if isinstance(f,dict)};figures=[]
    for figure in prepared.gated_figures:
        role=roles.get(figure.get("id"),{})
        if role.get("use"):figures.append({"number":figure.get("number"),"caption":figure.get("caption",""),"role":role.get("role",""),"step_id":role.get("step_id",""),"data":data_uri(figure)})
    title=spec.get("concept",{}).get("title") or paper["title"] or "Explorable lesson"
    draw=spec.get("custom_svg") if isinstance(spec.get("custom_svg"),str) else "";draw=draw or "function draw(){return '<svg viewBox=\"0 0 600 320\"></svg>'; }"
    compute=spec.get("compute") if isinstance(spec.get("compute"),str) else "function(){return {values:{},series:{},matrices:{},notes:[]}}"
    return template.replace("__TITLE__",html.escape(title)).replace("__SPEC__",_json(spec)).replace("__PAPER__",_json(paper)).replace("__EXTRA__",_json({"figures":figures,"notices":notices or []})).replace("__COMPUTE__",_script_source(compute)).replace("__DRAW__",_script_source(draw))

def write_atomic(path:Path,text:str):
    tmp=path.with_name(path.name+".tmp");tmp.write_text(text,encoding="utf-8");os.replace(str(tmp),str(path))

def fallback_page(case,error):
    focus=html.escape(getattr(case,"focus","Generation error"));source=html.escape(getattr(case,"source_url",""),quote=True);msg=html.escape(str(error)[:300])
    return '<!doctype html><meta charset="utf-8"><title>Paper to Playground</title><style>body{font:18px/1.6 system-ui;max-width:48rem;margin:auto;padding:3rem}</style><h1>%s</h1><p>A complete lesson could not be generated.</p><p>%s</p><p><a href="%s">Source</a></p>'%(focus,msg,source)
