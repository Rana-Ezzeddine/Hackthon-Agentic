"""PDF-to-record adapter with a text-only fallback."""
from __future__ import annotations
import re
from .text_reader import read_text

def read_pdf(data: bytes):
    import fitz, pymupdf4llm
    doc=fitz.open(stream=data,filetype="pdf")
    try:
        meta=dict(doc.metadata or {})
        try: text=pymupdf4llm.to_markdown(doc,ignore_images=True)
        except Exception: text="\n".join(p.get_text("text") for p in doc)
    finally: doc.close()
    record=read_text(text,{"title":meta.get("title","")},"pdf_markdown")
    record.warnings.append("PDF equations were extracted as flattened text; verify notation.")
    header=text.split("Abstract",1)[0][:3000]
    if not record.meta.get("title"): record.meta["title"]=(header.splitlines() or [""])[0].strip()
    refs=re.split(r"\n\s*References\s*\n",text,flags=re.I)
    if len(refs)>1:
        for m in re.finditer(r"(?:^|\n)\s*\[?(\d+)\]?\s+(.+?)(?=\n\s*\[?\d+\]?\s+|\Z)",refs[-1],re.S): record.references.append({"key":m.group(1),"number":m.group(1),"text":re.sub(r"\s+"," ",m.group(2)).strip()})
    return record
