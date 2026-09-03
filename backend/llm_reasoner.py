import json
import os
import re

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
    if len(reason.split()) > 20:
        raise ValueError("LLM reason is too long")
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


def _parse_json_content(content):
    content_type = type(content).__name__
    print(f"[LLM] content_type={content_type}")
    content_present = isinstance(content, str) and bool(content.strip())
    print(f"[LLM] content_present={str(content_present).lower()}")
    if not isinstance(content, str):
        print("[LLM] json_parse_success=false")
        print("[LLM] fallback_reason=unsupported_content_type")
        raise ValueError("LLM content must be a string")
    if not content_present:
        print("[LLM] json_parse_success=false")
        print("[LLM] fallback_reason=empty_content")
        raise ValueError("LLM returned empty content")

    content_text = content.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content_text, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        content_text = fenced_match.group(1).strip()

    if not content_text:
        print("[LLM] json_parse_success=false")
        print("[LLM] fallback_reason=empty_content")
        raise ValueError("LLM returned empty content")

    try:
        parsed = json.loads(content_text)
        print("[LLM] json_parse_success=true")
        return parsed
    except json.JSONDecodeError:
        print("[LLM] json_parse_success=false")
        print("[LLM] fallback_reason=invalid_json")
        raise


def _request_llm(context):
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("[LLM] fallback_reason=no_api_key")
        raise RuntimeError("LLM_API_KEY is not configured")

    api_url = os.getenv("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    print("[LLM] provider=openrouter")
    print(f"[LLM] model={model}")
    print(f"[LLM] api_url={api_url}")
    print(f"[LLM] api_key_configured={bool(api_key)}")
    system_prompt = (
        'Return only the JSON object. No markdown. No explanation. '
        'Reason must be at most 20 words. Use exactly these fields: '
        '{"recommended_action":"retry|payment_link|payment_link_later|human_review|stop",'
        '"reason":"one short sentence","risk_level":"low|medium|high",'
        '"requires_human_review":false}'
    )
    request_payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 700,
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
    }
    try:
        response = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=request_payload,
            timeout=5,
        )
    except requests.Timeout:
        print("[LLM] fallback_reason=request_timeout")
        raise
    except requests.RequestException:
        print("[LLM] fallback_reason=request_exception")
        raise

    print(f"[LLM] status={response.status_code}")
    if response.status_code == 429:
        print("[LLM] fallback_reason=http_429")
    elif response.status_code == 404:
        print("[LLM] fallback_reason=http_404")

    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        print("[LLM] fallback_reason=invalid_json")
        raise ValueError("LLM response must be an object")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        print("[LLM] fallback_reason=invalid_json")
        raise ValueError("LLM response contains no choices")

    choice = choices[0]
    if not isinstance(choice, dict):
        print("[LLM] fallback_reason=invalid_json")
        raise ValueError("LLM response choice is invalid")
    finish_reason = choice.get("finish_reason")
    print(f"[LLM] finish_reason={finish_reason}")
    if finish_reason == "length":
        print("[LLM] response_truncated=true")
        print("[LLM] retrying_truncated_response=true")
        retry_payload = dict(request_payload)
        retry_payload["max_tokens"] = 700
        retry_payload["messages"] = [
            {
                "role": "system",
                "content": "Return only JSON. No markdown or explanation. Reason <=20 words.",
            },
            request_payload["messages"][1],
        ]
        try:
            response = requests.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=retry_payload,
                timeout=5,
            )
        except requests.Timeout:
            print("[LLM] fallback_reason=request_timeout")
            raise
        except requests.RequestException:
            print("[LLM] fallback_reason=request_exception")
            raise

        print(f"[LLM] status={response.status_code}")
        if response.status_code == 429:
            print("[LLM] fallback_reason=http_429")
        elif response.status_code == 404:
            print("[LLM] fallback_reason=http_404")
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") if isinstance(data, dict) else None
        retry_choice = choices[0] if isinstance(choices, list) and choices else None
        if not isinstance(retry_choice, dict):
            print("[LLM] fallback_reason=invalid_json")
            raise ValueError("LLM response choice is invalid")
        print(f"[LLM] finish_reason={retry_choice.get('finish_reason')}")
        if retry_choice.get("finish_reason") == "length":
            print("[LLM] response_truncated=true")
            print("[LLM] fallback_reason=response_truncated_after_retry")
            raise ValueError("LLM response was truncated after retry")
        choice = retry_choice

    message = choice.get("message")
    if not isinstance(message, dict):
        print("[LLM] fallback_reason=invalid_json")
        raise ValueError("LLM response message is invalid")

    parsed = _parse_json_content(message.get("content"))

    if not isinstance(parsed, dict):
        print("[LLM] fallback_reason=invalid_json")
        raise ValueError("LLM response must be an object")

    recommended_action = parsed.get("recommended_action")
    print(f"[LLM] recommended_action={recommended_action}")
    if recommended_action not in ALLOWED_ACTIONS:
        print("[LLM] fallback_reason=invalid_action")
        raise ValueError("LLM returned an unsupported action")

    validation_success = False
    try:
        validated = _validate_response(parsed)
        validation_success = True
        print(f"[LLM] validation_success={str(validation_success).lower()}")
        return validated
    except ValueError:
        print(f"[LLM] validation_success={str(validation_success).lower()}")
        print("[LLM] fallback_reason=validation_failed")
        raise


def _fallback(deterministic_decision):
    fallback = dict(deterministic_decision)
    fallback["reasoning_source"] = "deterministic_fallback"
    fallback["recommended_action"] = fallback.get("action")
    return fallback


def reason_transaction(transaction, deterministic_decision, deterministic_only=False):
    if deterministic_only:
        print("[LLM] fallback_reason=deterministic_only")
        return _fallback(deterministic_decision)

    if not os.getenv("LLM_API_KEY"):
        print("[LLM] fallback_reason=no_api_key")
        return _fallback(deterministic_decision)

    try:
        result = _request_llm(safe_transaction_context(transaction))
        return result
    except (
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        requests.RequestException,
        json.JSONDecodeError,
    ) as exc:
        if isinstance(exc, RuntimeError) and str(exc) == "LLM_API_KEY is not configured":
            print("[LLM] fallback_reason=no_api_key")
        elif isinstance(exc, requests.Timeout):
            print("[LLM] fallback_reason=request_timeout")
        elif isinstance(exc, requests.RequestException):
            print("[LLM] fallback_reason=request_exception")
        elif isinstance(exc, json.JSONDecodeError):
            print("[LLM] fallback_reason=invalid_json")
        elif isinstance(exc, ValueError):
            message = str(exc)
            if "truncated after retry" in message.lower():
                print("[LLM] fallback_reason=response_truncated_after_retry")
            elif "empty content" in message.lower():
                print("[LLM] fallback_reason=empty_content")
            elif "unsupported action" in message.lower():
                print("[LLM] fallback_reason=invalid_action")
            else:
                print("[LLM] fallback_reason=validation_failed")
        else:
            print("[LLM] fallback_reason=validation_failed")
        return _fallback(deterministic_decision)
