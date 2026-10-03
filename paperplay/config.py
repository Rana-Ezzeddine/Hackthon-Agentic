"""Runtime limits. Environment flags are intentionally small and explicit."""
from __future__ import annotations
import os

MAX_REQUESTS = 10
MAX_COMPLETION = 30_000
DEADLINE_S = 540
GEN_TOKENS = 12_000
REPAIR_TOKENS = 7_000
PARSE_REPAIR_TOKENS = 5_000
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_HTML_BYTES = 12 * 1024 * 1024
MAX_PDF_BYTES = 25 * 1024 * 1024
VISION = os.getenv("VISION", "auto").lower()
NO_FETCH = os.getenv("NO_FETCH", "0").lower() in {"1", "true", "yes"}
