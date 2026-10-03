"""Assessment limits shared by all current and future model stages."""

from __future__ import annotations

import time
from dataclasses import dataclass


MAX_SECONDS = 600.0
MAX_REQUESTS = 10
MAX_COMPLETION_TOKENS = 30_000
OUTPUT_RESERVE_SECONDS = 15.0


class BudgetError(RuntimeError):
    pass


@dataclass(frozen=True)
class CallAllowance:
    request_number: int
    timeout_seconds: float
    max_completion_tokens: int


class Budget:
    def __init__(self, started: float | None = None) -> None:
        self.started = time.monotonic() if started is None else started
        self.requests = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def allowance(self, desired_completion_tokens: int = 2500) -> CallAllowance:
        remaining_time = MAX_SECONDS - (time.monotonic() - self.started) - OUTPUT_RESERVE_SECONDS
        remaining_tokens = MAX_COMPLETION_TOKENS - self.completion_tokens
        if self.requests >= MAX_REQUESTS:
            raise BudgetError("The 10-request limit has been reached.")
        if remaining_tokens <= 0:
            raise BudgetError("The 30,000 completion-token limit has been reached.")
        if remaining_time <= 5:
            raise BudgetError("The generation time budget is exhausted.")
        self.requests += 1  # Count the attempt, including a failed API request.
        return CallAllowance(
            request_number=self.requests,
            timeout_seconds=min(90.0, remaining_time),
            max_completion_tokens=min(desired_completion_tokens, remaining_tokens),
        )

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        if prompt_tokens < 0 or completion_tokens < 0:
            raise BudgetError("Model usage counts must be nonnegative.")
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        if self.completion_tokens > MAX_COMPLETION_TOKENS:
            raise BudgetError("Model usage exceeded the completion-token limit.")

    def snapshot(self) -> dict:
        return {
            "requests": self.requests,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "elapsed_seconds": round(time.monotonic() - self.started, 3),
            "limits": {
                "seconds": MAX_SECONDS,
                "requests": MAX_REQUESTS,
                "completion_tokens": MAX_COMPLETION_TOKENS,
            },
        }
