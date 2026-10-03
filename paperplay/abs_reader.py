"""arXiv abstract-page metadata reader."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

def read_abs(data: bytes) -> dict:
    soup=BeautifulSoup(data,"html.parser"); meta={"authors":[],"dates":{},"categories":{},"urls":{}}
    def metas(name): return [x.get("content","").strip() for x in soup.select('meta[name="%s"]' % name) if x.get("content")]
    meta["title"] = (metas("citation_title") or [""])[0]
    meta["authors"] = [{"name":x,"affiliations":[]} for x in metas("citation_author")]
    meta["abstract"] = (metas("citation_abstract") or [""])[0]
    meta["doi"] = (metas("citation_doi") or [""])[0]
    pdf=(metas("citation_pdf_url") or [""])[0]
    if pdf: meta["urls"]["pdf"]=pdf
    subjects=soup.select_one("td.tablecell.subjects")
    if subjects:
        codes=re.findall(r"\(([^)]+)\)",subjects.get_text(" ",strip=True)); meta["categories"]={"primary":codes[0] if codes else "","all":codes}
    for selector,key in ((".jref","journal_ref"),(".comments","comments")):
        node=soup.select_one(selector)
        if node: meta[key]=node.get_text(" ",strip=True).split(":",1)[-1].strip()
    lic=soup.select_one(".abs-license a[href]")
    if lic: meta["license"]=lic.get("href","")
    hist=soup.select_one(".submission-history")
    if hist: meta["dates"]={"history":[x.strip() for x in hist.get_text("\n").splitlines() if x.strip()]}
    return meta

