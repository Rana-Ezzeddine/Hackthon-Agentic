"""Step 2 scaffold for the Paper to Playground generator.

This file runs source-grounded planning but does not yet create an interactive
scientific explanation. Calculation, visuals, and checks follow in Step 3.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from paperplay.openrouter import ModelCallError, complete
from paperplay.prompts import planning_messages
from paperplay.schema import parse_plan, validate_plan


def log_event(trace_path: Path, started: float, stage: str, action: str, result: object) -> None:
    event = {
        "stage": stage,
        "action": action,
        "result": result,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_case(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        case = json.load(handle)
    if not isinstance(case, dict):
        raise ValueError("The input must be a JSON object.")
    for field in ("source_url", "focus", "audience"):
        if not isinstance(case.get(field), str) or not case[field].strip():
            raise ValueError(f"'{field}' must be a nonempty string.")
    parsed = urlparse(case["source_url"])
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("'source_url' must be an HTTP(S) URL.")
    # Keep additional fields intact until the instructor confirms the schema.
    return case


def get_excerpt(case: dict) -> str:
    # Provisional name until the instructor supplies the complete input schema.
    excerpt = case.get("excerpt")
    if not isinstance(excerpt, str) or not excerpt.strip():
        raise ValueError("Step 2 needs a nonempty 'excerpt' field in the input JSON.")
    return excerpt.strip()


def scaffold_page(case: dict, plan: dict) -> str:
    """Temporary page proving the output interface; replaced in Step 3."""
    title = html.escape(case["focus"])
    audience = html.escape(case["audience"])
    source = html.escape(case["source_url"], quote=True)
    plan_title = html.escape(plan["concept"]["title"])
    controls = "".join(f"<li>{html.escape(item['label'])}</li>" for item in plan["controls"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Paper to Playground — scaffold</title>
  <style>
    body {{ font: 18px/1.55 system-ui, sans-serif; max-width: 48rem;
           padding: 2rem; margin: auto; color: #172339; background: #f7f9fc; }}
    main {{ padding: 2rem; background: white; border-radius: 1rem; }}
    .notice {{ padding: 1rem; background: #fff4d8; border-radius: .5rem; }}
  </style>
</head>
<body><main>
  <h1>{title}</h1>
  <p>Intended audience: {audience}</p>
  <p>Source: <a href="{source}">{source}</a></p>
  <p class="notice">Step 2 planning preview only. This is not an interactive
  explanation; calculations, visuals, and checks still need implementation.</p>
  <h2>Planned concept: {plan_title}</h2>
  <p>Planned controls:</p><ul>{controls}</ul>
</main></body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a paper explanation")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    started = time.monotonic()
    args.output.mkdir(parents=True, exist_ok=True)
    trace_path = args.output / "trace.jsonl"
    trace_path.write_text("", encoding="utf-8")
    log_event(trace_path, started, "startup", "parse_arguments", {"model": args.model})
    try:
        case = load_case(args.input)
        excerpt = get_excerpt(case)
        log_event(trace_path, started, "input", "validate", {
            "status": "passed", "fields": sorted(case.keys()), "excerpt_chars": len(excerpt)
        })
        log_event(trace_path, started, "planning", "model_request", {"request_number": 1})
        completion = complete(args.model, planning_messages(case, excerpt))
        log_event(trace_path, started, "planning", "model_response", {
            "request_number": 1,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
            "call_elapsed_seconds": round(completion.elapsed_seconds, 3),
            "response_id": completion.response_id,
        })
        plan = parse_plan(completion.content)
        validate_plan(plan, excerpt)
        log_event(trace_path, started, "planning", "validate_plan", {"status": "passed"})
        (args.output / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        page_path = args.output / "index.html"
        page_path.write_text(scaffold_page(case, plan), encoding="utf-8")
        log_event(trace_path, started, "output", "write_scaffold", {
            "status": "planning_preview_only", "path": "index.html"
        })
        return 0
    except (OSError, ValueError, json.JSONDecodeError, ModelCallError) as exc:
        log_event(trace_path, started, "failure", "abort", {
            "error_type": type(exc).__name__, "message": str(exc)
        })
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
