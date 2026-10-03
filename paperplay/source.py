"""Source acquisition orchestration."""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from .abs_reader import read_abs
from .config import MAX_HTML_BYTES, MAX_PDF_BYTES, NO_FETCH
from .fetch import fetch, FetchError
from .html_reader import read_html
from .inputs import Case
from .pdf_reader import read_pdf
from .record import PaperRecord, merge_metadata
from .text_reader import read_text

ARXIV_RE=re.compile(r"arxiv\.org/(?:abs|pdf|html)/([\w.\-/]+?)(v\d+)?(?:\.pdf)?(?:[#?].*)?$",re.I)
def normalize_arxiv(url):
    m=ARXIV_RE.search(url)
    if not m:return None
    core=m.group(1).rstrip("/"); version=m.group(2) or ""
    return core+version

def _usable(record, focus):
    text=" ".join(s.text for s in record.sections)
    return len(text)>200 and not any("5%" in w for w in record.warnings)

def acquire_and_parse(case: Case, trace) -> PaperRecord:
    arxiv_id=normalize_arxiv(case.source_url); meta_future=None; pool=ThreadPoolExecutor(max_workers=2)
    if arxiv_id and not NO_FETCH:
        meta_future=pool.submit(fetch,"https://arxiv.org/abs/"+arxiv_id,MAX_HTML_BYTES)
    errors=[]; record=None; abs_meta={}
    if meta_future:
        try:
            data,_,_=meta_future.result(timeout=10)
            abs_meta=read_abs(data)
            trace.log("parse","arxiv_metadata","ok")
        except Exception as exc: trace.log("parse","arxiv_metadata","fail",error=type(exc).__name__)
    if not NO_FETCH:
        attempts=[]
        if arxiv_id:
            advertised_html=abs_meta.get("urls",{}).get("html", "")
            same_paper=normalize_arxiv(advertised_html)
            same_base=same_paper and re.sub(r"v\d+$","",same_paper)==re.sub(r"v\d+$","",arxiv_id)
            requested_version=re.search(r"v\d+$",arxiv_id)
            html_url=advertised_html if same_base and (not requested_version or same_paper==arxiv_id) else "https://arxiv.org/html/"+arxiv_id
            attempts += [("arxiv_html",html_url,"html"),("ar5iv_html","https://ar5iv.labs.arxiv.org/html/"+arxiv_id,"html"),("pdf_markdown","https://arxiv.org/pdf/"+arxiv_id+".pdf","pdf")]
        else:
            kind="pdf" if urlparse(case.source_url).path.lower().endswith(".pdf") else "html"; attempts=[("pdf_markdown" if kind=="pdf" else "web_html",case.source_url,kind)]
        for mode,url,kind in attempts:
            try:
                data,ctype,final=fetch(url,MAX_PDF_BYTES if kind=="pdf" else MAX_HTML_BYTES)
                if kind=="html" and arxiv_id and mode in ("arxiv_html","ar5iv_html") and not urlparse(final).path.startswith("/html/"):
                    raise ValueError("HTML request did not return a full-text paper")
                candidate=read_pdf(data) if kind=="pdf" else read_html(data,final,mode)
                trace.log("source",mode,"ok",url=final,size=len(data))
                if _usable(candidate,case.focus): record=candidate; break
                errors.append(mode+": insufficient meaningful content")
            except Exception as exc:
                errors.append(mode+": "+str(exc)[:180]); trace.log("source",mode,"fail",url=url,error=type(exc).__name__)
    if record is None:
        record=read_text(case.focus,case.hints,"brief_only"); record.warnings.extend(errors or ["Source text unavailable."])
        trace.log("source","brief_only","fallback",errors=errors)
    record.meta.setdefault("urls",{}); record.meta["urls"]["source"]=case.source_url
    if arxiv_id:
        record.meta["arxiv_id"]=re.sub(r"v\d+$","",arxiv_id); record.meta["version"]=(re.search(r"v\d+$",arxiv_id) or [""])[0]
        record.meta["urls"].update({"abs":"https://arxiv.org/abs/"+arxiv_id,"html":"https://arxiv.org/html/"+arxiv_id,"pdf":"https://arxiv.org/pdf/"+arxiv_id+".pdf"})
    if abs_meta: merge_metadata(record,abs_meta)
    if arxiv_id and record.mode=="arxiv_html":
        record.meta["urls"]["html"]=html_url
        resolved_id=normalize_arxiv(html_url)
        if resolved_id: record.meta["version"]=(re.search(r"v\d+$",resolved_id) or [""])[0]
    pool.shutdown(wait=False)
    trace.log("parse","paper_record","ok",mode=record.mode,sections=len(record.sections),equations=len(record.equations),figures=len(record.figures),references=len(record.references),warnings=record.warnings)
    return record
