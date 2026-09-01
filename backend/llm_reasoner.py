import json
import os

import requests


ALLOWED_ACTIONS = {
    "retry",
    "payment_link",
    "payment_link_later",
    "human_review",
    "stop",
}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}


def safe_transaction_context(transaction):
    return {
        "transaction_id": transaction.get("transaction_id"),
        "amount": transaction.get("amount"),
        "failure_reason": transaction.get("failure_reason"),
        "retry_count": transaction.get("retry_count"),
        "recovery_status": transaction.get("recovery_status"),
        "previous_recovery_attempts": {
            "recovery_attempted": transaction.get("recovery_attempted"),
            "recovery_action": transaction.get("recovery_action"),
            "recovery_success": transaction.get("recovery_success"),
            "recovered_amount": transaction.get("recovered_amount"),
        },
        "customer_opted_out": transaction.get("customer_opted_out"),
    }


def _validate_response(result):
    if not isinstance(result, dict):
        raise ValueError("LLM response must be an object")

    if set(result) != {
        "recommended_action",
        "reason",
        "risk_level",
        "requires_human_review",
    }:
        raise ValueError("LLM response must contain the exact required fields")

    action = result.get("recommended_action")
    risk_level = result.get("risk_level")
    reason = result.get("reason")
    requires_human_review = result.get("requires_human_review")

    if action not in ALLOWED_ACTIONS:
        raise ValueError("LLM returned an unsupported action")
    if risk_level not in ALLOWED_RISK_LEVELS:
        raise ValueError("LLM returned an unsupported risk level")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("LLM reason is missing")
    if not isinstance(requires_human_review, bool):
        raise ValueError("LLM human-review flag is invalid")

    return {
        "action": action,
        "reason": reason.strip(),
        "confidence": None,
        "confidence_type": "LLM recommendation, not a probability",
        "risk_level": risk_level,
        "requires_human_review": requires_human_review,
        "reasoning_source": "llm",
        "recommended_action": action,
    }


def _request_llm(context):
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not configured")

    api_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    system_prompt = (
        "You are a revenue recovery recommender. Return only strict JSON with keys "
        "recommended_action, reason, risk_level, requires_human_review. "
        "Allowed actions: retry, payment_link, payment_link_later, human_review, stop. "
        "Do not include markdown or extra keys. This is a recommendation only; "
        "a separate policy guard controls execution."
    )
    response = requests.post(
        api_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0,
            "max_tokens": 800,
            "provider": {
                "require_parameters": True,
            },
            "plugins": [
                {"id": "response-healing"},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "recovery_decision",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "recommended_action": {
                                "type": "string",
                                "enum": [
                                    "retry",
                                    "payment_link",
                                    "payment_link_later",
                                    "human_review",
                                    "stop",
                                ],
                            },
                            "reason": {"type": "string"},
                            "risk_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                            "requires_human_review": {"type": "boolean"},
                        },
                        "required": [
                            "recommended_action",
                            "reason",
                            "risk_level",
                            "requires_human_review",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(context, separators=(",", ":"))},
            ],
        },
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("LLM response must be an object")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response contains no choices")

    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("LLM response choice is invalid")
    if choice.get("finish_reason") == "length":
        raise ValueError("LLM response was truncated")

    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM response message is invalid")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned empty content")

    return json.loads(content)


def _fallback(deterministic_decision):
    fallback = dict(deterministic_decision)
    fallback["reasoning_source"] = "deterministic_fallback"
    fallback["recommended_action"] = fallback.get("action")
    return fallback


def reason_transaction(transaction, deterministic_decision, deterministic_only=False):
    if deterministic_only:
        return _fallback(deterministic_decision)

    if not os.getenv("LLM_API_KEY"):
        return _fallback(deterministic_decision)

    try:
        result = _request_llm(safe_transaction_context(transaction))
        return _validate_response(result)
    except (
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        requests.RequestException,
        json.JSONDecodeError,
    ):
        return _fallback(deterministic_decision)
