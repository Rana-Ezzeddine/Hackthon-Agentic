"""Request, token, and wall-clock accounting."""
from __future__ import annotations
import time
from dataclasses import dataclass
from .config import DEADLINE_S, MAX_COMPLETION, MAX_REQUESTS

@dataclass
class Budget:
    started: float
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def remaining_s(self): return max(0.0, DEADLINE_S - (time.monotonic() - self.started))
    def can_afford(self, max_tokens: int) -> bool:
        return self.requests + 1 <= MAX_REQUESTS - 1 and self.completion_tokens + max_tokens <= MAX_COMPLETION - 1000 and self.remaining_s >= 45
    def record(self, prompt=0, completion=0, reasoning=0):
        self.prompt_tokens += int(prompt or 0); self.completion_tokens += int(completion or 0); self.reasoning_tokens += int(reasoning or 0)
    def totals(self):
        return {"requests": self.requests, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "reasoning_tokens": self.reasoning_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens}

