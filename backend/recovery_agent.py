def decide_recovery_action(transaction):
    reason = transaction.get("failure_reason", "unknown")
    retries = int(transaction.get("retry_count", 0))
    amount = float(transaction.get("amount", 0))

    if retries >= 2:
        return {
            "action": "escalate",
            "reason": "Maximum retry limit reached",
            "confidence": 1.0,
        }

    if amount > 10000:
        return {
            "action": "human_review",
            "reason": "High-value payment requires approval",
            "confidence": 1.0,
        }

    if reason == "network_error":
        return {
            "action": "retry",
            "reason": "Temporary network failure detected",
            "confidence": 0.95,
        }

    if reason == "timeout":
        return {
            "action": "retry",
            "reason": "Temporary timeout detected",
            "confidence": 0.92,
        }

    if reason == "bank_decline":
        return {
            "action": "payment_link",
            "reason": "Immediate retry may repeat issuer decline",
            "confidence": 0.9,
        }

    if reason == "insufficient_funds":
        return {
            "action": "payment_link_later",
            "reason": "Customer may need time before retrying payment",
            "confidence": 0.88,
        }

    return {
        "action": "human_review",
        "reason": "Failure reason not safely recognised",
        "confidence": 0.6,
    }
