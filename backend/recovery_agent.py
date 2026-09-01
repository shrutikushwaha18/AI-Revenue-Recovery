def decide_recovery_action(transaction):
    reason = transaction.get("failure_reason", "unknown")
    retries = int(transaction.get("retry_count", 0))
    amount = float(transaction.get("amount", 0))

    if str(transaction.get("status") or "").lower() == "recovered" or str(transaction.get("recovery_status") or "").lower() == "successful":
        return {
            "action": "stop",
            "reason": "Revenue is already recovered",
            "confidence": 1.0,
            "confidence_type": "deterministic policy outcome",
            "risk_level": "low",
            "requires_human_review": False,
        }

    if int(transaction.get("customer_opted_out") or 0) == 1:
        return {
            "action": "stop",
            "reason": "Customer opted out of recovery",
            "confidence": 1.0,
            "confidence_type": "deterministic policy outcome",
            "risk_level": "low",
            "requires_human_review": False,
        }

    if retries >= 2:
        return {
            "action": "human_review",
            "reason": "Maximum retry limit reached",
            "confidence": 1.0,
            "confidence_type": "deterministic policy outcome",
            "risk_level": "high",
            "requires_human_review": True,
        }

    if amount > 10000:
        return {
            "action": "human_review",
            "reason": "High-value payment requires approval",
            "confidence": 1.0,
            "confidence_type": "deterministic policy outcome",
            "risk_level": "high",
            "requires_human_review": True,
        }

    if reason == "network_error":
        return {
            "action": "retry",
            "reason": "Temporary network failure detected",
            "confidence": 0.95,
            "confidence_type": "heuristic score, not ML probability",
            "risk_level": "medium",
            "requires_human_review": False,
        }

    if reason == "timeout":
        return {
            "action": "retry",
            "reason": "Temporary timeout detected",
            "confidence": 0.92,
            "confidence_type": "heuristic score, not ML probability",
            "risk_level": "medium",
            "requires_human_review": False,
        }

    if reason == "bank_decline":
        return {
            "action": "payment_link",
            "reason": "Immediate retry may repeat issuer decline",
            "confidence": 0.9,
            "confidence_type": "heuristic score, not ML probability",
            "risk_level": "low",
            "requires_human_review": False,
        }

    if reason == "insufficient_funds":
        return {
            "action": "payment_link_later",
            "reason": "Customer may need time before retrying payment",
            "confidence": 0.88,
            "confidence_type": "heuristic score, not ML probability",
            "risk_level": "low",
            "requires_human_review": False,
        }

    return {
        "action": "human_review",
        "reason": "Failure reason not safely recognised",
        "confidence": 0.6,
        "confidence_type": "heuristic score, not ML probability",
        "risk_level": "high",
        "requires_human_review": True,
    }


def observe_transaction(transaction):
    return {
        "transaction_id": transaction.get("transaction_id"),
        "amount": transaction.get("amount"),
        "failure_reason": transaction.get("failure_reason"),
        "retry_count": transaction.get("retry_count"),
        "status": transaction.get("status"),
        "recovery_status": transaction.get("recovery_status"),
        "customer_opted_out": transaction.get("customer_opted_out"),
        "is_synthetic": transaction.get("is_synthetic"),
        "previous_recovery": {
            "recovery_action": transaction.get("recovery_action"),
            "recovery_attempted": transaction.get("recovery_attempted"),
            "recovery_success": transaction.get("recovery_success"),
            "recovered_amount": transaction.get("recovered_amount"),
            "payment_link": transaction.get("payment_link"),
            "payment_link_id": transaction.get("payment_link_id"),
            "razorpay_reference_id": transaction.get("razorpay_reference_id"),
            "recovered_at": transaction.get("recovered_at"),
        },
    }


def policy_guard(transaction, decision, historical_execution=False):
    is_recovered = str(transaction.get("status") or "").lower() == "recovered" or str(transaction.get("recovery_status") or "").lower() == "successful"
    checks = [
        {
            "name": "synthetic_transaction",
            "passed": int(transaction.get("is_synthetic") or 0) == 0,
            "reason": "Transaction is non-synthetic; external recovery actions are allowed."
            if int(transaction.get("is_synthetic") or 0) == 0
            else "Synthetic transaction detected; external Razorpay actions are blocked.",
        },
        {
            "name": "customer_opted_out",
            "passed": int(transaction.get("customer_opted_out") or 0) == 0,
            "reason": "Customer has not opted out of recovery",
        },
        {
            "name": "already_recovered",
            "passed": not is_recovered or historical_execution,
            "reason": "Revenue was not already recovered before execution" if historical_execution else "Revenue is not already recovered",
        },
        {
            "name": "retry_limit",
            "passed": int(transaction.get("retry_count") or 0) < 2,
            "reason": "Retry count is below the automatic limit."
            if int(transaction.get("retry_count") or 0) < 2
            else "Maximum automatic retry limit reached; human review required.",
        },
        {
            "name": "amount_limit",
            "passed": float(transaction.get("amount") or 0) <= 10000,
            "reason": "Amount is within the automatic recovery limit",
        },
        {
            "name": "known_failure_reason",
            "passed": str(transaction.get("failure_reason") or "unknown").lower() in {
                "network_error",
                "timeout",
                "bank_decline",
                "insufficient_funds",
                "abandoned_checkout",
                "expired_payment",
            },
            "reason": "Failure reason is recognized by the recovery policy",
        },
    ]
    allowed = all(check["passed"] for check in checks) and decision.get("action") not in {"human_review", "stop"}
    return checks + [{
        "name": "execution_allowed",
        "passed": allowed,
        "reason": "Policy guard allows the selected action" if allowed else "Policy guard blocks external execution",
    }]


def apply_policy_override(transaction, decision, historical_execution=False):
    guarded = dict(decision)
    guarded["policy_override"] = False
    guarded["policy_override_reason"] = None
    failure_reason = str(transaction.get("failure_reason") or "unknown").lower()
    is_recovered = str(transaction.get("status") or "").lower() == "recovered" or str(transaction.get("recovery_status") or "").lower() == "successful"
    recommended_action = str(guarded.get("recommended_action") or guarded.get("action") or "").lower()

    if int(transaction.get("is_synthetic") or 0) == 1 or int(transaction.get("customer_opted_out") or 0) == 1 or (is_recovered and not historical_execution):
        guarded["action"] = "stop"
        guarded["reason"] = "Policy guard stopped external recovery"
        guarded["risk_level"] = "low"
        guarded["requires_human_review"] = False
    elif int(transaction.get("retry_count") or 0) >= 2 or float(transaction.get("amount") or 0) > 10000 or failure_reason not in {
        "network_error",
        "timeout",
        "bank_decline",
        "insufficient_funds",
        "abandoned_checkout",
        "expired_payment",
    }:
        guarded["action"] = "human_review"
        guarded["reason"] = "Policy guard requires human review"
        guarded["risk_level"] = "high"
        guarded["requires_human_review"] = True
    elif failure_reason == "bank_decline" and recommended_action == "retry":
        guarded["action"] = "payment_link"
        guarded["reason"] = "Immediate retry may repeat the issuer decline; policy selected a payment link instead."
        guarded["risk_level"] = "low"
        guarded["requires_human_review"] = False
        guarded["policy_override"] = True
        guarded["policy_override_reason"] = "Bank decline policy blocks immediate retry."

    guarded["final_guarded_action"] = guarded["action"]
    if not guarded.get("policy_override"):
        guarded.pop("policy_override_reason", None)
    return guarded
