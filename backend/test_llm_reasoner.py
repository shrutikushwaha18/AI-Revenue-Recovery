import json

import llm_reasoner


class FakeResponse:
    def __init__(self, content, finish_reason="stop", status_code=200):
        self.status_code = status_code
        self._body = {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {"content": content},
                }
            ]
        }

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _context():
    return {"transaction_id": "TXN001", "failure_reason": "timeout"}


def _deterministic_decision():
    return {
        "action": "stop",
        "reason": "Deterministic policy stopped recovery.",
        "confidence": None,
        "confidence_type": "deterministic policy outcome",
    }


def test_valid_short_llm_json(monkeypatch):
    payload = {
        "recommended_action": "retry",
        "reason": "Temporary timeout may succeed on retry.",
        "risk_level": "low",
        "requires_human_review": False,
    }
    requests = []
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_reasoner.requests,
        "post",
        lambda *args, **kwargs: requests.append(kwargs["json"]) or FakeResponse(json.dumps(payload)),
    )

    result = llm_reasoner._request_llm(_context())

    assert result["recommended_action"] == "retry"
    assert result["confidence"] is None
    assert result["confidence_type"] == "LLM recommendation, not a probability"
    assert requests[0]["max_tokens"] == 700
    assert requests[0]["temperature"] == 0.1


def test_truncated_first_response_retries_with_short_prompt(monkeypatch):
    responses = iter(
        [
            FakeResponse('{"recommended_action":"retry"', finish_reason="length"),
            FakeResponse(
                '{"recommended_action":"stop","reason":"Repeated failure.",'
                '"risk_level":"high","requires_human_review":false}'
            ),
        ]
    )
    requests = []
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_reasoner.requests,
        "post",
        lambda *args, **kwargs: requests.append(kwargs["json"]) or next(responses),
    )

    result = llm_reasoner._request_llm(_context())

    assert result["recommended_action"] == "stop"
    assert len(requests) == 2
    assert requests[1]["max_tokens"] == 700
    assert requests[1]["messages"][0]["content"] == (
        "Return only JSON. No markdown or explanation. Reason <=20 words."
    )


def test_invalid_json_uses_deterministic_fallback(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_reasoner.requests,
        "post",
        lambda *args, **kwargs: FakeResponse("not json"),
    )

    result = llm_reasoner.reason_transaction(_context(), _deterministic_decision())

    assert result["reasoning_source"] == "deterministic_fallback"
    assert result["recommended_action"] == "stop"


def test_fenced_llm_json_keeps_confidence_null(monkeypatch):
    content = (
        "```json\n"
        '{"recommended_action":"human_review","reason":"Needs review.",'
        '"risk_level":"medium","requires_human_review":true}\n'
        "```"
    )
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        llm_reasoner.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(content),
    )

    result = llm_reasoner.reason_transaction(_context(), _deterministic_decision())

    assert result["confidence"] is None
    assert result["confidence_type"] == "LLM recommendation, not a probability"