"""Append-only, privacy-safe JSONL tracing."""
from __future__ import annotations
import json, time
from pathlib import Path

class Trace:
    def __init__(self, path: Path, started: float):
        self.path, self.started = path, started
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def log(self, stage: str, action: str, result: str, **details) -> None:
        event = {"t": round(time.monotonic() - self.started, 3), "stage": stage,
                 "action": action, "result": result, **details}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

