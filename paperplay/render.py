"""Fill the self-contained page template safely."""
from __future__ import annotations
import html,json,os,re
from pathlib import Path
from .design import normalize_design
from .figures import data_uri

ROOT=Path(__file__).resolve().parent.parent
def _json(value): return re.sub(r"</script",r"<\\/script",json.dumps(value,ensure_ascii=False,separators=(",",":"),default=str),flags=re.I).replace("<!--","<\\!--")
def _script_source(value): return re.sub(r"</script",r"<\\/script",value if isinstance(value,str) else "",flags=re.I)
def render(spec,record,prepared,notices=None):
    normalize_design(spec)
    template=(ROOT/"templates"/"page.html").read_text(encoding="utf-8")
    meta=record.meta; paper={"title":meta.get("title") or spec.get("title","Paper playground"),"authors":[a.get("name","") for a in meta.get("authors",[])],"arxiv_id":meta.get("arxiv_id","") ,"version":meta.get("version","") ,"dates":"; ".join(meta.get("dates",{}).get("history",[])) if isinstance(meta.get("dates"),dict) else str(meta.get("dates", "")),"categories":", ".join(meta.get("categories",{}).get("all",[])) if isinstance(meta.get("categories"),dict) else "","journal_ref":meta.get("journal_ref", ""),"license":meta.get("license", ""),"urls":meta.get("urls",{}),"abstract":meta.get("abstract", ""),"references":record.references,"figures":[{"number":f.get("number"),"caption":f.get("caption","")} for f in record.figures],"mode":record.mode}
    plan=spec.get("plan") if isinstance(spec.get("plan"),dict) else {}
    role_items=plan.get("figures",[]) if isinstance(plan.get("figures",[]),list) else []
    roles={f.get("id"):f for f in role_items if isinstance(f,dict)}; figures=[]
    for fig in prepared.gated_figures:
        role=roles.get(fig.get("id"),{})
        if role.get("use"):figures.append({"number":fig.get("number"),"caption":fig.get("caption", ""),"role":role.get("role", ""),"data":data_uri(fig)})
    draw=spec.get("custom_svg") if isinstance(spec.get("custom_svg"),str) else ""
    draw=draw or "function draw(){return '<svg viewBox=\"0 0 600 320\"></svg>'; }"
    compute=spec.get("compute") if isinstance(spec.get("compute"),str) else "function(){return {values:{},series:{},matrices:{},notes:[]}}"
    return template.replace("__TITLE__",html.escape(paper["title"])).replace("__SPEC__",_json(spec)).replace("__PAPER__",_json(paper)).replace("__EXTRA__",_json({"figures":figures,"notices":notices or []})).replace("__COMPUTE__",_script_source(compute)).replace("__DRAW__",_script_source(draw))

def write_atomic(path:Path,text:str):
    tmp=path.with_name(path.name+".tmp");tmp.write_text(text,encoding="utf-8");os.replace(str(tmp),str(path))

def fallback_page(case,error):
    focus=html.escape(getattr(case,"focus","Generation error")); source=html.escape(getattr(case,"source_url",""),quote=True); msg=html.escape(str(error)[:300])
    return '<!doctype html><meta charset="utf-8"><title>Paper to Playground</title><style>body{font:18px/1.6 system-ui;max-width:48rem;margin:auto;padding:3rem}</style><h1>%s</h1><p>A complete playground could not be generated.</p><p>%s</p><p><a href="%s">Source</a></p>'%(focus,msg,source)
