"""Minimal deterministic validation for the planning handoff."""

from __future__ import annotations

import json
import re


def parse_plan(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    plan = json.loads(text)
    if not isinstance(plan, dict):
        raise ValueError("Plan must be a JSON object.")
    return plan


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be nonempty text.")
    return value.strip()


def validate_plan(plan: dict, excerpt: str) -> None:
    source = plan.get("source")
    concept = plan.get("concept")
    visual = plan.get("visual")
    if not all(isinstance(x, dict) for x in (source, concept, visual)):
        raise ValueError("source, concept, and visual must be objects.")
    _text(source.get("title"), "source.title")
    _text(source.get("location"), "source.location")
    evidence = _text(source.get("evidence"), "source.evidence")
    if " ".join(evidence.split()) not in " ".join(excerpt.split()):
        raise ValueError("source.evidence is not an exact span of the excerpt.")
    for field in ("title", "why_it_matters"):
        _text(concept.get(field), f"concept.{field}")
    symbols = concept.get("symbols")
    if not isinstance(symbols, list):
        raise ValueError("concept.symbols must be a list.")
    for i, symbol in enumerate(symbols):
        if not isinstance(symbol, dict):
            raise ValueError(f"symbols[{i}] must be an object.")
        _text(symbol.get("symbol"), f"symbols[{i}].symbol")
        _text(symbol.get("meaning"), f"symbols[{i}].meaning")
    controls = plan.get("controls")
    if not isinstance(controls, list) or len(controls) < 2:
        raise ValueError("At least two controls are required.")
    ids = set()
    for i, control in enumerate(controls):
        if not isinstance(control, dict):
            raise ValueError(f"controls[{i}] must be an object.")
        control_id = _text(control.get("id"), f"controls[{i}].id")
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", control_id) or control_id in ids:
            raise ValueError("Control IDs must be unique JavaScript identifiers.")
        ids.add(control_id)
        _text(control.get("label"), f"controls[{i}].label")
        kind = control.get("type")
        if kind not in ("number", "toggle", "select"):
            raise ValueError(f"Unsupported control type: {kind!r}.")
        if "default" not in control:
            raise ValueError(f"controls[{i}].default is missing.")
        if kind == "number":
            lower, upper, default = (control.get(k) for k in ("min", "max", "default"))
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in (lower, upper, default)):
                raise ValueError(f"controls[{i}] numeric bounds/default are invalid.")
            if not lower < upper or not lower <= default <= upper:
                raise ValueError(f"controls[{i}] default is outside its bounds.")
        if kind == "toggle" and not isinstance(control["default"], bool):
            raise ValueError(f"controls[{i}] toggle default must be boolean.")
        if kind == "select":
            options = control.get("options")
            if not isinstance(options, list) or len(options) < 2 or control["default"] not in options:
                raise ValueError(f"controls[{i}] select options/default are invalid.")
    if visual.get("kind") not in ("bar", "curve", "matrix", "process"):
        raise ValueError("visual.kind must be bar, curve, matrix, or process.")
    _text(visual.get("explanation"), "visual.explanation")
    explorations = plan.get("explorations")
    if not isinstance(explorations, list) or len(explorations) != 2:
        raise ValueError("Exactly two guided explorations are required.")
    for i, exploration in enumerate(explorations):
        if not isinstance(exploration, dict) or not isinstance(exploration.get("settings"), dict):
            raise ValueError(f"explorations[{i}] needs settings.")
        if not set(exploration["settings"]).issubset(ids):
            raise ValueError(f"explorations[{i}] refers to an unknown control.")
        _text(exploration.get("observe"), f"explorations[{i}].observe")
        _text(exploration.get("why"), f"explorations[{i}].why")
    _text(plan.get("limitation"), "limitation")
    checks = plan.get("checks")
    if not isinstance(checks, list) or len(checks) < 2:
        raise ValueError("At least two planned checks are required.")
    for i, check in enumerate(checks):
        if not isinstance(check, dict) or not isinstance(check.get("inputs"), dict):
            raise ValueError(f"checks[{i}] needs inputs.")
        if not set(check["inputs"]).issubset(ids):
            raise ValueError(f"checks[{i}] refers to an unknown control.")
        _text(check.get("expected_behavior"), f"checks[{i}].expected_behavior")
