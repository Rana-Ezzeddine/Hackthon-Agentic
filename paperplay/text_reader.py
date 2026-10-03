"""Plain text and Markdown excerpt parser."""
from __future__ import annotations
import re
from .record import PaperRecord, Section

def read_text(text: str, hints=None, mode="supplied_excerpt") -> PaperRecord:
    record = PaperRecord(mode=mode)
    hints = hints or {}; record.meta["title"] = hints.get("title", "")
    authors = hints.get("authors") or hints.get("author")
    if authors: record.meta["authors"] = [{"name": x.strip(), "affiliations": []} for x in re.split(r",|\band\b", authors) if x.strip()]
    heading_re = re.compile(r"^(#{1,4})\s+(.+)$", re.M)
    matches = list(heading_re.finditer(text))
    if not matches:
        record.sections = [Section(anchor="excerpt", heading=hints.get("section", "Provided excerpt"), text=text.strip())]
    else:
        for i, match in enumerate(matches):
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            heading = match.group(2).strip(); number = (re.match(r"([A-Z]?\d+(?:\.\d+)*)", heading) or [None, ""])[1]
            record.sections.append(Section(anchor="sec-%d" % (i+1), number=number, level=len(match.group(1)), heading=heading, text=text[match.end():end].strip()))
    _extract_equations(record)
    return record

def _extract_equations(record):
    for section in record.sections:
        for i, match in enumerate(re.finditer(r"(?:Eq(?:uation)?\.?\s*\(?([\w.-]+)\)?[^\n]*?[:=]\s*)?\$([^$]{2,300})\$", section.text, re.I)):
            num = match.group(1) or str(len(record.equations)+1); eid = "eq-%s" % num
            record.equations.append({"id":eid,"number":num,"latex":match.group(2),"section":section.number or section.heading}); section.eq_ids.append(eid)

