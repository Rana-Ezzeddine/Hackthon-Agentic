"""LaTeXML-aware and generic HTML reader."""
from __future__ import annotations
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .record import PaperRecord, Section

def _clean_text(node):
    clone=BeautifulSoup(str(node),"html.parser")
    for math in clone.select("math"):
        math.replace_with("$%s$" % (math.get("alttext") or math.get("aria-label") or math.get_text(" ",strip=True)))
    for bad in clone.select("script,style,nav,header,footer,noscript,form,.ltx_page_footer"): bad.decompose()
    return re.sub(r"\s+"," ",clone.get_text(" ",strip=True)).strip()

def _local_section_text(node):
    """Keep section content once, without repeating nested subsections."""
    copy=BeautifulSoup(str(node),"html.parser")
    root=copy.find("section")
    if root is None:return _clean_text(node)
    for child in root.find_all("section"):child.decompose()
    return _clean_text(root)

def read_html(data: bytes, base_url: str, mode="arxiv_html") -> PaperRecord:
    soup=BeautifulSoup(data,"html.parser"); record=PaperRecord(mode=mode)
    title=soup.select_one("h1.ltx_title_document") or soup.find("h1") or soup.find("title")
    record.meta["title"]=_clean_text(title) if title else ""
    for creator in soup.select(".ltx_creator.ltx_role_author"):
        person=creator.select_one(".ltx_personname"); name=_clean_text(person) if person else ""
        aff=[_clean_text(x) for x in creator.select(".ltx_role_affiliation")]
        email=creator.select_one(".ltx_role_email")
        if name: record.meta["authors"].append({"name":name,"affiliations":aff,"email":_clean_text(email) if email else ""})
    if not record.meta["authors"]:
        for node in soup.select('meta[name="citation_author"]'):
            if node.get("content"): record.meta["authors"].append({"name":node["content"].strip(),"affiliations":[]})
    abstract=soup.select_one(".ltx_abstract")
    if abstract: record.meta["abstract"]=_clean_text(abstract)
    errors=len(soup.select(".ltx_ERROR")); all_text=_clean_text(soup)
    if errors and errors/max(1,len(all_text.split()))>.05: record.warnings.append("More than 5% parser error nodes.")
    nodes=soup.select("section.ltx_section,section.ltx_subsection,section.ltx_subsubsection,section.ltx_paragraph")
    if nodes:
        for idx,node in enumerate(nodes):
            classes=" ".join(node.get("class",[])); level=4 if "paragraph" in classes else 3 if "subsubsection" in classes else 2 if "subsection" in classes else 1
            heading=node.select_one(":scope > [class*=ltx_title]")
            heading_text=_clean_text(heading) if heading else "Section %d"%(idx+1)
            num=(re.search(r"(?:^|\s)([A-Z]?\d+(?:\.\d+)*)",heading_text) or [None,""])[1]
            section=Section(anchor=node.get("id", "sec-%d"%(idx+1)),number=num,level=level,heading=heading_text,text=_local_section_text(node))
            record.sections.append(section)
    else:
        headings=soup.find_all(["h1","h2","h3","h4"])
        if headings:
            for idx,h in enumerate(headings):
                chunks=[]
                for sib in h.next_siblings:
                    if getattr(sib,"name",None) in ("h1","h2","h3","h4"): break
                    if getattr(sib,"get_text",None): chunks.append(_clean_text(sib))
                record.sections.append(Section(anchor=h.get("id","sec-%d"%(idx+1)), level=int(h.name[1]), heading=_clean_text(h), text=" ".join(chunks)))
        else: record.sections=[Section(anchor="document",heading=record.meta["title"] or "Document",text=all_text)]
    for idx,eq in enumerate(soup.select(".ltx_equation,.ltx_equationgroup")):
        tag=eq.select_one(".ltx_tag_equation"); num=_clean_text(tag).strip("()") if tag else str(idx+1)
        math=eq.select_one("math"); latex=(math.get("alttext") or math.get("aria-label") or _clean_text(math)) if math else _clean_text(eq)
        eid=eq.get("id","eq-%s"%num); parent=eq.find_parent("section"); section_id=parent.get("id","") if parent else ""
        record.equations.append({"id":eid,"number":num,"latex":latex,"section":section_id})
        for section in record.sections:
            if section.anchor==section_id: section.eq_ids.append(eid); break
    for idx,fig in enumerate(soup.select("figure.ltx_figure")):
        cap=fig.find("figcaption"); tag=fig.select_one(".ltx_tag_figure"); num=_clean_text(tag) if tag else str(idx+1); img=fig.find("img")
        fid=fig.get("id","fig-%d"%(idx+1)); parent=fig.find_parent("section"); section_id=parent.get("id","") if parent else ""
        record.figures.append({"id":fid,"number":num,"caption":_clean_text(cap) if cap else "","section":section_id,"src":urljoin(base_url+"/",img.get("src")) if img and img.get("src") else "","image_bytes":None,"mime":"","inline_svg":str(fig.find("svg")) if fig.find("svg") else None})
        for section in record.sections:
            if section.anchor==section_id: section.fig_ids.append(fid); break
    for idx,box in enumerate(soup.select("figure.ltx_table")):
        cap=box.find("figcaption"); rows=[]
        for tr in box.select("tr"): rows.append([_clean_text(cell) for cell in tr.select("th,td")])
        tid=box.get("id","table-%d"%(idx+1)); tag=box.select_one(".ltx_tag_table")
        record.tables.append({"id":tid,"number":_clean_text(tag) if tag else str(idx+1),"caption":_clean_text(cap) if cap else "","section":"","rows":rows,"markdown":"\n".join("|"+"|".join(r)+"|" for r in rows)})
    for node in soup.select(".ltx_float_algorithm,.ltx_listing"):
        record.algorithms.append({"id":node.get("id","") ,"caption":_clean_text(node.find("figcaption")) if node.find("figcaption") else "","text":_clean_text(node)})
    for node in soup.select(".ltx_theorem"):
        classes=" ".join(node.get("class",[])); kind=next((x.replace("ltx_theorem_","") for x in node.get("class",[]) if x.startswith("ltx_theorem_")),"theorem")
        record.theorems.append({"id":node.get("id","") ,"kind":kind,"number":"","text":_clean_text(node)})
    for link in soup.select('a[href^="#bib.bib"]'):
        parent=link.find_parent("section")
        if parent:
            for section in record.sections:
                if section.anchor==parent.get("id","") and link.get("href","")[1:] not in section.cite_keys: section.cite_keys.append(link.get("href","")[1:])
    for bib in soup.select(".ltx_bibitem"):
        tag=bib.select_one(".ltx_tag_bibitem"); text=_clean_text(bib)
        record.references.append({"key":bib.get("id",str(len(record.references)+1)),"number":_clean_text(tag).strip("[]") if tag else str(len(record.references)+1),"text":text})
    return record
