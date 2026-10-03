"""Prepare the complete paper representation for a future model request.

This stage makes no model calls and makes no decisions about which paper
material is relevant to the focus or audience.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from paperplay.budget import Budget
from paperplay.source import load_case, prepare_paper
from paperplay.visuals import (
    MAX_IMAGES_PER_CALL, make_page_sheets, sheet_data_url, visual_batches,
)


def log_event(trace_path: Path, started: float, stage: str, action: str, result: object) -> None:
    event = {
        "stage": stage,
        "action": action,
        "result": result,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an arXiv paper for a model")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", required=True, help="Reserved for the later model stage")
    args = parser.parse_args()

    started = time.monotonic()
    budget = Budget(started)
    args.output.mkdir(parents=True, exist_ok=True)
    trace_path = args.output / "trace.jsonl"
    trace_path.write_text("", encoding="utf-8")
    log_event(trace_path, started, "startup", "parse_arguments", {"model": args.model})
    log_event(trace_path, started, "budget", "initialize", budget.snapshot())
    try:
        case = load_case(args.input)
        log_event(trace_path, started, "input", "validate", {
            "status": "passed", "fields": sorted(case.keys())
        })
        paper = prepare_paper(case)
        sheets = make_page_sheets(paper.pages) if paper.pages else paper.figure_sheets
        visual_kind = "PDF page" if paper.pages else "HTML figure"
        images = [
            {
                "kind": visual_kind,
                "item_numbers": list(sheet.page_numbers),
                "image_url": sheet_data_url(sheet),
            }
            for sheet in sheets
        ]
        payload = {
            "source_url": case["source_url"],
            "focus": case["focus"],
            "audience": case["audience"],
            "paper_text": paper.text,
            "images": images,
        }
        (args.output / "model_input.json").write_text(
            json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (args.output / "paper.txt").write_text(paper.text + "\n", encoding="utf-8")
        manifest = {
            "source_method": paper.method,
            "paper_chars": len(paper.text),
            "pdf_pages": len(paper.pages),
            "html_figures": sum(len(sheet.page_numbers) for sheet in paper.figure_sheets),
            "detected_tables": paper.html_tables + sum(len(page.tables) for page in paper.pages),
            "embedded_pdf_images": sum(len(page.embedded_images) for page in paper.pages),
            "visual_sheets": len(sheets),
            "fits_one_image_request": len(sheets) <= MAX_IMAGES_PER_CALL,
            "visual_batches_if_needed": len(visual_batches(sheets)) if len(sheets) > MAX_IMAGES_PER_CALL else 0,
            "model_requests_used": 0,
        }
        (args.output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        log_event(trace_path, started, "source", "prepare_model_input", manifest)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        log_event(trace_path, started, "failure", "abort", {
            "error_type": type(exc).__name__, "message": str(exc),
            "budget": budget.snapshot(),
        })
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
