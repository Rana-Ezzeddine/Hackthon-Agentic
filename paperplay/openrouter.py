"""One OpenRouter chat-completions call with verifiable usage accounting."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


@dataclass(frozen=True)
class Completion:
    content: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_seconds: float
    response_id: str | None


class ModelCallError(RuntimeError):
    pass


def complete(model_id: str, messages: list[dict[str, str]], *, timeout: float = 90.0) -> Completion:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ModelCallError("OPENROUTER_API_KEY is not set.")
    payload = {
        "model": model_id,
        "messages": messages,
        "max_completion_tokens": 2500,
        "temperature": 0.2,
        "stream": False,
    }
    request = Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as exc:
        # Do not log raw response bodies: they can contain sensitive request data.
        raise ModelCallError(f"OpenRouter returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError) as exc:
        raise ModelCallError(f"OpenRouter request failed: {type(exc).__name__}.") from None
    elapsed = time.monotonic() - started
    try:
        content = data["choices"][0]["message"]["content"]
        usage = data["usage"]
        prompt_tokens = int(usage["prompt_tokens"])
        completion_tokens = int(usage["completion_tokens"])
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty model response")
        return Completion(content, prompt_tokens, completion_tokens, elapsed, data.get("id"))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ModelCallError(f"OpenRouter response was incomplete: {type(exc).__name__}.") from None
