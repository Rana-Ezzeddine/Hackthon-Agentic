"""Render a self-contained explorable lesson from a validated LessonSpec."""
from __future__ import annotations
import html,json,os,re
from html.parser import HTMLParser
from pathlib import Path
from .design import normalize_design
from .figures import data_uri, sanitize_svg

ROOT=Path(__file__).resolve().parent.parent

class _RichHTML(HTMLParser):
    """Allow flexible explanatory structure without executable markup."""
    TAGS={"p","div","span","strong","b","em","i","small","h2","h3","h4","h5","ul","ol","li","table","thead","tbody","tr","th","td","blockquote","code","pre","br","hr","sup","sub","details","summary","a"}
    def __init__(self): super().__init__(convert_charrefs=True);self.parts=[];self.stack=[]
    def handle_starttag(self,tag,attrs):
        if tag not in self.TAGS:self.stack.append(None);return
        if tag not in {"br","hr"}:self.stack.append(tag)
        safe=[]
        for key,value in attrs:
            if tag=="a" and key=="href" and isinstance(value,str) and re.match(r"^https://(?:arxiv\.org|doi\.org|papers\.neurips\.cc)/",value):safe.append(' href="'+html.escape(value,quote=True)+'" rel="noopener noreferrer"')
            if key=="class" and isinstance(value,str) and re.fullmatch(r"[A-Za-z0-9 _-]{1,120}",value):safe.append(' class="'+html.escape(value,quote=True)+'"')
        self.parts.append("<"+tag+"".join(safe)+">")
    def handle_endtag(self,tag):
        if not self.stack:return
        last=self.stack.pop()
        if last==tag and tag not in {"br","hr"}:self.parts.append("</"+tag+">")
    def handle_data(self,data):self.parts.append(html.escape(data))
    def get(self):return "".join(self.parts)

def _safe_html(value):
    parser=_RichHTML();parser.feed(value if isinstance(value,str) else "");return parser.get()

_FORBIDDEN_JS=re.compile(r"</?script|\b(?:document|window|globalThis|fetch|XMLHttpRequest|WebSocket|import|require|eval|constructor|__proto__|localStorage|sessionStorage|navigator|location|setTimeout|setInterval)\b|new\s+Function\b|Math\.random|\bDate\b",re.I)
def _safe_function(value,name):
    if not isinstance(value,str) or not value.strip() or _FORBIDDEN_JS.search(value):raise ValueError("unsafe or missing "+name+" function")
    return value

def _scoped_css(css,index):
    if not isinstance(css,str) or not css.strip():return ""
    if re.search(r"@|url\s*\(|</style|expression\s*\(|position\s*:\s*fixed|:root|\b(?:html|body)\b",css,re.I):raise ValueError("unsafe interaction CSS")
    result=[]
    for block in css.split("}"):
        if not block.strip():continue
        if "{" not in block:raise ValueError("malformed interaction CSS")
        selectors,declarations=block.split("{",1)
        if "{" in declarations:raise ValueError("nested interaction CSS")
        names=["#unit-%d %s"%(index,s.strip()) for s in selectors.split(",") if s.strip()]
        if not names:raise ValueError("empty interaction CSS selector")
        result.append(",".join(names)+"{"+declarations+"}")
    return "\n".join(result)

def _render_v2(spec,record):
    source=(ROOT/"templates"/"focus_page.html").read_text(encoding="utf-8")
    css=(ROOT/"templates"/"focus_style.css").read_text(encoding="utf-8")
    copy=json.loads(json.dumps(spec,ensure_ascii=False,default=str))
    for key in ("summary_html","synthesis_html","limitations_html"):
        copy[key]=_safe_html(copy.get(key,""))
    functions=[];unit_css=[];used=set()
    for index,unit in enumerate(copy.get("units",[])):
        for key in ("orientation_html","interpretation_html","after_html"):
            unit[key]=_safe_html(unit.get(key,""))
        interaction=unit.get("interaction",{})
        compute=_safe_function(interaction.pop("compute",None),"compute")
        draw=interaction.pop("draw","")
        draw=_safe_function(draw,"draw") if draw else "function draw(){return '';}"
        unit_css.append(_scoped_css(interaction.pop("css",""),index))
        functions.append("{compute:(%s),draw:(%s)}"%(compute,draw))
        used.update(unit.get("source_refs",[]))
    figures={}
    for fig in record.figures:
        fid=fig.get("id")
        if fid in used and fig.get("image_bytes"):
            figures[fid]={"caption":fig.get("caption", ""),"data":data_uri(fig)}
        elif fid in used and fig.get("inline_svg"):
            figures[fid]={"caption":fig.get("caption", ""),"svg":sanitize_svg(fig["inline_svg"])}
    authors=[a.get("name","") for a in record.meta.get("authors",[]) if isinstance(a,dict)]
    paper={"title":record.meta.get("title") or spec.get("title",""),"authors":authors,"url":record.meta.get("urls",{}).get("source","")}
    return (source.replace("__TITLE__",html.escape(paper["title"]))
            .replace("__BASE_CSS__",css+"\n"+"\n".join(unit_css))
            .replace("__SPEC__",_json(copy)).replace("__PAPER__",_json(paper))
            .replace("__FIGURES__",_json(figures)).replace("__FUNCTIONS__","["+",".join(functions)+"]"))
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
    if spec.get("format")=="focus-guided-v2":
        return _render_v2(spec,record)
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
