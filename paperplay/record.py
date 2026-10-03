"""Normalized paper representation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Section:
    anchor: str = ""; number: str = ""; level: int = 1; heading: str = ""; text: str = ""
    eq_ids: list = field(default_factory=list); fig_ids: list = field(default_factory=list); tab_ids: list = field(default_factory=list)
    cite_keys: list = field(default_factory=list); footnotes: list = field(default_factory=list)
@dataclass
class PaperRecord:
    mode: str = "brief_only"
    meta: dict[str, Any] = field(default_factory=lambda: {"title":"", "authors":[], "affiliations":[], "dates":{}, "categories":{}, "urls":{}})
    sections: list[Section] = field(default_factory=list)
    equations: list[dict] = field(default_factory=list); figures: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list); algorithms: list[dict] = field(default_factory=list)
    theorems: list[dict] = field(default_factory=list); references: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

def merge_metadata(record: PaperRecord, other: dict) -> None:
    for key, value in other.items():
        if value in (None, "", [], {}): continue
        if key in {"dates", "categories", "doi", "license"} or not record.meta.get(key): record.meta[key] = value

