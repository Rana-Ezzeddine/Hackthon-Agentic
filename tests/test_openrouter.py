import time

from paperplay.budget import Budget
from paperplay.openrouter import OpenRouter
from paperplay.trace import Trace


class Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "id": "generation-test",
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2,
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        }


def test_json_calls_disable_reasoning_to_avoid_truncation(monkeypatch, tmp_path):
    captured = {}

    def post(_url, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("paperplay.openrouter.requests.post", post)
    started = time.monotonic()
    client = OpenRouter("deepseek/deepseek-v4.1-flash", Budget(started),
                        Trace(tmp_path / "trace.jsonl", started))
    result = client.complete([{"role": "user", "content": "JSON"}], action="generate")
    assert result.content == "{}"
    assert captured["reasoning"] == {"effort": "none"}
    assert captured["response_format"] == {"type": "json_object"}
