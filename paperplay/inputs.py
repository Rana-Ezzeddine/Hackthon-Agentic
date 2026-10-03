"""Case loading and flexible excerpt discovery."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from .config import MAX_INPUT_BYTES

EXCERPT_KEYS = ("excerpt", "paper_excerpt", "source_excerpt", "excerpt_text", "source_text", "paper_text", "source_material", "content")

@dataclass
class Case:
    source_url: str
    focus: str
    audience: str
    excerpt: str = ""
    hints: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

def _strings(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(v, str): yield k, v

def load_case(path: Path, trace=None) -> Case:
    if path.stat().st_size > MAX_INPUT_BYTES: raise ValueError("Input exceeds 2 MB.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict): raise ValueError("Input must be a JSON object.")
    vals = {}
    for key, cap in (("source_url", 10_000), ("focus", 10_000), ("audience", 1_000)):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip(): raise ValueError("'%s' must be a non-empty string." % key)
        vals[key] = value.strip()[:cap]
    parsed = urlparse(vals["source_url"])
    if parsed.scheme not in ("http", "https") or not parsed.netloc: raise ValueError("'source_url' must be HTTP(S).")
    candidates = []
    for key in EXCERPT_KEYS:
        if isinstance(data.get(key), str): candidates.append((100, data[key]))
    for parent in ("paper", "source", "document"):
        for key, value in _strings(data.get(parent)):
            if key in EXCERPT_KEYS or len(value) > 200: candidates.append((90, value))
    if isinstance(data.get("excerpts"), list):
        for item in data["excerpts"]:
            if isinstance(item, str): candidates.append((95, item))
            elif isinstance(item, dict): candidates.extend((85, v) for _, v in _strings(item))
    for key, value in data.items():
        if key not in {"source_url", "focus", "audience"} and isinstance(value, str) and len(value) > 200: candidates.append((50, value))
    excerpt = max(candidates, key=lambda x: (x[0], len(x[1])))[1].strip() if candidates else ""
    hints = {k: v.strip() for k, v in data.items() if isinstance(v, str) and k not in {"source_url", "focus", "audience"} and len(v) <= 200}
    case = Case(excerpt=excerpt, hints=hints, raw=data, **vals)
    if trace: trace.log("input", "validate", "ok", fields=sorted(data), excerpt_chars=len(excerpt))
    return case

