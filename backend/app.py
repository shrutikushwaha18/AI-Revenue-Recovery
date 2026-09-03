import hashlib
import hmac
import json
import os
import random

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

SIMULATION_SEED = "recoverai-v1"
SIMULATION_VERSION = "1.0"
SIMULATION_KEY_VERSION = "v1"

from database import get_db, get_transaction_by_id, init_db
from razorpay_service import create_payment_link, generate_reference_id
from llm_reasoner import reason_transaction
from recovery_agent import apply_policy_override, decide_recovery_action, observe_transaction, policy_guard
from seed import seed_db

load_dotenv()

app = Flask(__name__)
CORS(app)

init_db()
seed_db()

BATCH_FAILURE_TYPES = [
    "bank_decline",
    "insufficient_funds",
    "network_error",
    "timeout",
    "abandoned_checkout",
    "expired_payment",
    "unknown_failure",
]


def generate_batch_transactions():
    random_seed = random.Random(42)
    transactions = []
    for index in range(1, 101):
        transaction_id = f"BATCH{index:03d}"
        amount = round(random_seed.uniform(250, 12000), 2)
        failure_reason = random_seed.choice(BATCH_FAILURE_TYPES)
        retry_count = random_seed.randint(0, 2)
        transactions.append(
            (
                transaction_id,
                f"Customer {index}",
                f"customer{index}@example.com",
                f"987654{str(index).zfill(4)}",
                amount,
                "failed",
                failure_reason,
                retry_count,
                "pending",
                None,
                0.0,
                1,
            )
        )
    return transactions


def ensure_batch_seeded():
    conn = get_db()
    existing = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE transaction_id LIKE 'BATCH%'"
    ).fetchone()[0]

    if existing == 0:
        batch_transactions = generate_batch_transactions()
        for row in batch_transactions:
            conn.execute(
                """
                INSERT OR IGNORE INTO transactions (
                    transaction_id,
                    customer_name,
                    email,
                    phone,
                    amount,
                    status,
                    failure_reason,
                    retry_count,
                    recovery_status,
                    recovery_action,
                    recovered_amount,
                    is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.commit()
    conn.close()


def deterministic_recovery_score(transaction_id, failure_reason, recovery_action, simulation_version=SIMULATION_KEY_VERSION):
    key = f"{transaction_id}:{failure_reason}:{recovery_action}:{simulation_version}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    value = int(digest[:16], 16) / float(16 ** 16)
    return value


def recovery_probability_for(reason, action):
    probabilities = {
        "retry": {"network_error": 0.80, "timeout": 0.75},
        "payment_link": {"bank_decline": 0.65, "abandoned_checkout": 0.70, "expired_payment": 0.70},
        "payment_link_later": {"insufficient_funds": 0.50},
    }
    return probabilities.get(action, {}).get(reason, 0.0)


def safe_batch_decision(transaction):
    reason = transaction.get("failure_reason", "unknown_failure")
    retries = int(transaction.get("retry_count", 0))
    amount = float(transaction.get("amount", 0))
    opted_out = int(transaction.get("customer_opted_out", 0))

    if transaction.get("recovery_status") == "successful":
        return {"action": "stop", "reason": "Already recovered; no further action", "blocked": True}

    if amount > 10000:
        return {
            "action": "human_review",
            "reason": "High-value payment exceeds safe automation threshold",
            "blocked": True,
        }

    if reason == "unknown_failure":
        return {
            "action": "human_review",
            "reason": "Unknown failure reason requires manual review",
            "blocked": True,
        }

    if retries >= 2:
        return {
            "action": "human_review",
            "reason": "Maximum automatic retry limit reached",
            "blocked": True,
        }

    if opted_out == 1:
        return {
            "action": "stop",
            "reason": "Customer opted out of recovery attempts",
            "blocked": True,
        }

    action_map = {
        "network_error": ("retry", "Temporary network issue detected; retry is allowed"),
        "timeout": ("retry", "Temporary timeout detected; retry is allowed"),
        "bank_decline": ("payment_link", "Issuer decline suggests safer payment-link retry"),
        "insufficient_funds": ("payment_link_later", "Customer likely needs time before retrying"),
        "abandoned_checkout": ("payment_link", "Customer abandoned checkout; payment link is the safe next step"),
        "expired_payment": ("payment_link", "Payment expired; resend the payment link"),
    }

    if reason in action_map:
        action, description = action_map[reason]
        return {"action": action, "reason": description, "blocked": False}

    return {
        "action": "human_review",
        "reason": "No safe automatic action recognized",
        "blocked": True,
    }


def simulate_batch_recovery(transaction, action):
    reason = transaction.get("failure_reason", "unknown_failure")
    chance = recovery_probability_for(reason, action)
    if chance == 0:
        return {"recovery_success": 0, "recovered_amount": 0.0, "recovery_status": "pending"}

    deterministic_value = deterministic_recovery_score(
        transaction.get("transaction_id", "UNKNOWN"),
        reason,
        action,
        SIMULATION_KEY_VERSION,
    )

    if deterministic_value <= chance:
        return {
            "recovery_success": 1,
            "recovered_amount": float(transaction.get("amount", 0) or 0),
            "recovery_status": "successful",
        }

    return {
        "recovery_success": 0,
        "recovered_amount": 0.0,
        "recovery_status": "pending",
    }


def normalize_recovery_outcome(row):
    final_status = (row.get("final_recovery_status") or row.get("recovery_status") or "").strip().lower()
    if final_status in {"successful", "recovered"}:
        return "recovered"
    if final_status == "human_review":
        return "human_review"
    if final_status == "stopped":
        return "stopped"
    if final_status == "failed":
        return "failed"
    return "pending"


def build_agent_decision(transaction, historical_execution=False):
    deterministic_decision = decide_recovery_action(transaction)
    if historical_execution and transaction.get("recovery_action"):
        recommended_decision = {
            "action": transaction.get("recovery_action"),
            "reason": "Previously recorded recovery decision",
            "confidence": None,
            "confidence_type": "historical decision record",
            "risk_level": "low",
            "requires_human_review": False,
            "reasoning_source": "deterministic_fallback",
            "recommended_action": transaction.get("recovery_action"),
        }
    else:
        recommended_decision = reason_transaction(transaction, deterministic_decision)

    guarded_decision = apply_policy_override(transaction, recommended_decision, historical_execution=historical_execution)
    guarded_decision["final_guarded_action"] = guarded_decision["action"]
    guarded_decision["guarded_reason"] = guarded_decision["reason"]
    return guarded_decision


def get_or_create_agent_decision(transaction):
    if int(transaction.get("is_synthetic") or 0) == 1:
        return {
            "transaction_id": transaction.get("transaction_id"),
            "reasoning_source": "deterministic_fallback",
            "recommended_action": "stop",
            "final_guarded_action": "stop",
            "action": "stop",
            "reason": "Synthetic batch transactions do not persist agent decisions",
            "guarded_reason": "Synthetic batch transactions do not persist agent decisions",
            "risk_level": "low",
            "requires_human_review": False,
            "policy_override": False,
            "policy_override_reason": None,
            "confidence": None,
            "confidence_type": "synthetic batch decision",
            "decision_reused": False,
        }

    transaction_id = str(transaction.get("transaction_id") or "").strip()
    if not transaction_id:
        decision = build_agent_decision(transaction)
        decision["decision_reused"] = False
        return decision

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM agent_decisions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()

    if row is not None:
        payload = dict(row)
        payload["decision_reused"] = True
        payload["policy_override"] = bool(payload.get("policy_override"))
        payload["requires_human_review"] = bool(payload.get("requires_human_review"))
        payload["action"] = payload.get("final_guarded_action") or payload.get("action")
        payload["final_guarded_action"] = payload.get("final_guarded_action") or payload.get("action")
        conn.close()
        return payload

    decision = build_agent_decision(transaction)
    conn.execute(
        """
        INSERT INTO agent_decisions (
            transaction_id,
            reasoning_source,
            recommended_action,
            final_guarded_action,
            action,
            reason,
            guarded_reason,
            risk_level,
            requires_human_review,
            policy_override,
            policy_override_reason,
            confidence,
            confidence_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transaction_id,
            decision.get("reasoning_source"),
            decision.get("recommended_action"),
            decision.get("final_guarded_action") or decision.get("action"),
            decision.get("action"),
            decision.get("reason"),
            decision.get("guarded_reason") or decision.get("reason"),
            decision.get("risk_level"),
            int(bool(decision.get("requires_human_review"))),
            int(bool(decision.get("policy_override"))),
            decision.get("policy_override_reason"),
            decision.get("confidence"),
            decision.get("confidence_type"),
        ),
    )
    conn.commit()
    conn.close()

    decision["decision_reused"] = False
    return decision


@app.route("/")
def home():
    return jsonify({"message": "RecoverAI backend running"})


@app.route("/api/transactions", methods=["GET"])
def transactions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM transactions").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/analyze/<transaction_id>", methods=["POST"])
def analyze_transaction(transaction_id):
    normalized_transaction_id = (transaction_id or "").strip()
    transaction = get_transaction_by_id(normalized_transaction_id)

    if not transaction:
        return jsonify({"error": "Transaction not found"}), 404

    transaction = dict(transaction)
    decision = build_agent_decision(transaction)

    conn = get_db()
    try:
        conn.execute(
            "UPDATE transactions SET recovery_action = ? WHERE transaction_id = ?",
            (decision["action"], normalized_transaction_id),
        )

        existing_audit = conn.execute(
            """
            SELECT 1
            FROM audit_logs
            WHERE transaction_id = ?
              AND action = ?
              AND reason = ?
            LIMIT 1
            """,
            (normalized_transaction_id, decision["action"], decision["reason"]),
        ).fetchone()

        if existing_audit is None:
            conn.execute(
                "INSERT INTO audit_logs (transaction_id, action, reason) VALUES (?, ?, ?)",
                (normalized_transaction_id, decision["action"], decision["reason"]),
            )

        conn.commit()
    finally:
        conn.close()

    return jsonify({"transaction": normalized_transaction_id, "decision": decision})


@app.route("/api/agent/trace/<transaction_id>", methods=["GET"])
def agent_trace(transaction_id):
    normalized_transaction_id = (transaction_id or "").strip()
    conn = get_db()
    transaction_row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (normalized_transaction_id,),
    ).fetchone()

    if transaction_row is None:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    transaction = dict(transaction_row)
    audit_rows = conn.execute(
        "SELECT * FROM audit_logs WHERE transaction_id = ? ORDER BY created_at ASC",
        (normalized_transaction_id,),
    ).fetchall()
    audit_logs = [dict(row) for row in audit_rows]
    conn.close()

    payment_link_audit = next(
        (item for item in audit_logs if item.get("action") == "payment_link_created"),
        None,
    )
    revenue_recovered = any(item.get("action") == "revenue_recovered" for item in audit_logs)
    decision = get_or_create_agent_decision(transaction)
    decision_reused = bool(decision.get("decision_reused"))

    guardrails = policy_guard(transaction, decision, historical_execution=bool(payment_link_audit))
    execution = {
        "executed": bool(transaction.get("recovery_attempted")),
        "action": transaction.get("recovery_action"),
        "payment_link_created": bool(transaction.get("payment_link_id")),
        "payment_link_id": transaction.get("payment_link_id"),
        "razorpay_reference_id": transaction.get("razorpay_reference_id"),
        "external_tool": "Razorpay Payment Link" if transaction.get("payment_link_id") else None,
    }
    outcome = {
        "status": transaction.get("status"),
        "recovery_status": transaction.get("recovery_status"),
        "recovered": revenue_recovered and str(transaction.get("status") or "").lower() == "recovered",
        "recovered_amount": transaction.get("recovered_amount"),
        "recovered_at": transaction.get("recovered_at"),
        "signed_webhook": revenue_recovered,
    }

    return jsonify({
        "transaction_id": normalized_transaction_id,
        "observation": observe_transaction(transaction),
        "decision": decision,
        "decision_reused": decision_reused,
        "guardrails": guardrails,
        "execution": execution,
        "outcome": outcome,
    })


@app.route("/api/recover/<transaction_id>", methods=["POST"])
def recover_transaction(transaction_id):
    normalized_transaction_id = (transaction_id or "").strip()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (normalized_transaction_id,),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    transaction = dict(row)
    decision = get_or_create_agent_decision(transaction)
    decision_reused = bool(decision.get("decision_reused"))
    guardrails = policy_guard(transaction, decision)

    if int(transaction.get("is_synthetic") or 0) == 1:
        conn.close()
        return jsonify(
            {
                "success": False,
                "executed": False,
                "reason": "Synthetic transactions cannot trigger Razorpay recovery",
                "decision": decision,
                "decision_reused": decision_reused,
                "guardrails": guardrails,
            }
        )

    if str(transaction.get("status") or "").lower() == "recovered" or str(transaction.get("recovery_status") or "").lower() == "successful":
        recovered_amount = transaction.get("recovered_amount")
        conn.close()
        return jsonify(
            {
                "success": True,
                "already_recovered": True,
                "transaction_id": normalized_transaction_id,
                "recovered_amount": recovered_amount,
                "message": "Transaction already recovered",
                "decision": decision,
                "decision_reused": decision_reused,
                "guardrails": guardrails,
            }
        )

    final_guarded_action = decision["final_guarded_action"]
    if final_guarded_action == "retry" and transaction.get("recovery_status") == "retry_scheduled":
        conn.close()
        return jsonify(
            {
                "success": True,
                "executed": True,
                "transaction_id": normalized_transaction_id,
                "execution": {
                    "action": "retry",
                    "external_tool": None,
                    "retry_scheduled": True,
                },
                "decision": decision,
                "decision_reused": decision_reused,
                "guardrails": guardrails,
            }
        )

    if final_guarded_action not in ["retry", "payment_link", "payment_link_later"]:
        conn.close()
        return jsonify({"decision": decision, "guardrails": guardrails, "executed": False})

    if not all(check["passed"] for check in guardrails):
        conn.close()
        return jsonify({"decision": decision, "guardrails": guardrails, "executed": False})

    if final_guarded_action == "retry":
        next_retry_count = int(transaction.get("retry_count") or 0) + 1
        conn.execute(
            """
            UPDATE transactions
            SET retry_count = ?,
                recovery_attempted = 1,
                recovery_action = 'retry',
                recovery_status = 'retry_scheduled',
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (next_retry_count, normalized_transaction_id),
        )
        conn.execute(
            """
            INSERT INTO audit_logs (transaction_id, action, reason)
            VALUES (?, 'retry_scheduled', 'Retry scheduled for bounded recovery workflow')
            """,
            (normalized_transaction_id,),
        )
        conn.commit()
        conn.close()
        return jsonify(
            {
                "success": True,
                "executed": True,
                "transaction_id": normalized_transaction_id,
                "execution": {
                    "action": "retry",
                    "external_tool": None,
                    "retry_scheduled": True,
                },
                "decision": decision,
                "decision_reused": decision_reused,
                "guardrails": guardrails,
            }
        )

    existing_payment_link = transaction.get("payment_link")
    existing_payment_link_id = transaction.get("payment_link_id")
    existing_reference_id = transaction.get("razorpay_reference_id")
    if (
        transaction.get("recovery_status") == "recovery_started"
        and existing_payment_link
        and existing_payment_link_id
    ):
        conn.close()
        return jsonify(
            {
                "success": True,
                "reused_existing_link": True,
                "transaction_id": normalized_transaction_id,
                "payment_link": existing_payment_link,
                "payment_link_id": existing_payment_link_id,
                "razorpay_reference_id": existing_reference_id,
                "recovery_status": transaction.get("recovery_status"),
                "message": "Existing active recovery payment link returned",
                "decision": decision,
                "decision_reused": decision_reused,
            }
        )

    try:
        reference_id = generate_reference_id(normalized_transaction_id)
        response = create_payment_link(transaction, reference_id=reference_id)
        short_url = response.get("short_url") or response.get("url") or "not_available"
        payment_link_id = response.get("id") or None
        metadata = {
            "failure_reason": str(transaction.get("failure_reason") or "unknown"),
            "recovery_action": str(decision.get("final_guarded_action") or decision.get("action") or "payment_link"),
            "workflow": "revenue_recovery",
            "source": "RecoverAI",
        }

        conn.execute(
            """
            UPDATE transactions
            SET payment_link = ?,
                payment_link_id = ?,
                razorpay_reference_id = ?,
                recovery_action = ?,
                recovery_status = ?,
                recovery_attempted = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (
                short_url,
                payment_link_id,
                reference_id,
                str(decision.get("final_guarded_action") or decision.get("action") or "payment_link"),
                "recovery_started",
                normalized_transaction_id,
            ),
        )

        audit_exists = conn.execute(
            """
            SELECT 1
            FROM audit_logs
            WHERE transaction_id = ? AND action = 'payment_link_created'
            LIMIT 1
            """,
            (normalized_transaction_id,),
        ).fetchone()

        if audit_exists is None:
            conn.execute(
                """
                INSERT INTO audit_logs (transaction_id, action, reason)
                VALUES (?, ?, ?)
                """,
                (
                    normalized_transaction_id,
                    "payment_link_created",
                    "Razorpay recovery payment link generated with RecoverAI metadata",
                ),
            )

        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "transaction_id": normalized_transaction_id,
                "payment_link": short_url,
                "payment_link_id": payment_link_id,
                "razorpay_reference_id": reference_id,
                "decision": decision,
                "decision_reused": decision_reused,
                "metadata_sent_to_razorpay": metadata,
            }
        )

    except Exception as exc:
        conn.close()
        message = str(exc).lower()
        if "reference_id" in message and "already exists" in message:
            return jsonify({
                "success": False,
                "error": "Duplicate Razorpay reference_id. Please retry with a new attempt.",
                "decision": decision,
                "decision_reused": decision_reused,
            }), 409
        return jsonify({
            "success": False,
            "error": str(exc),
            "decision": decision,
            "decision_reused": decision_reused,
        }), 500


@app.route("/api/audit/<transaction_id>", methods=["GET"])
def audit(transaction_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audit_logs WHERE transaction_id = ? ORDER BY created_at ASC",
        (transaction_id,),
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/live-recovery/<transaction_id>", methods=["GET"])
def live_recovery(transaction_id):
    conn = get_db()
    transaction = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()

    if transaction is None:
        conn.close()
        return jsonify({"transaction": None, "audit": [], "verified": False})

    transaction_data = dict(transaction)
    audit_rows = conn.execute(
        "SELECT * FROM audit_logs WHERE transaction_id = ? ORDER BY created_at ASC",
        (transaction_id,),
    ).fetchall()
    audit_data = [dict(row) for row in audit_rows]

    verified = (
        str(transaction_data.get("status") or "").lower() == "recovered"
        and str(transaction_data.get("recovery_status") or "").lower() == "successful"
        and float(transaction_data.get("recovered_amount") or 0) > 0
        and any(str(item.get("action") or "").lower() == "revenue_recovered" for item in audit_data)
    )

    conn.close()
    return jsonify({
        "transaction": transaction_data,
        "audit": audit_data,
        "verified": verified,
    })


def reset_batch_transactions():
    conn = get_db()
    conn.execute(
        """
        UPDATE transactions
        SET status = 'failed',
            recovery_status = 'pending',
            recovery_action = NULL,
            recovery_reason = NULL,
            recovery_attempted = 0,
            recovery_success = 0,
            recovered_amount = 0,
            final_recovery_status = NULL,
            recovered_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE transaction_id LIKE 'BATCH%' AND is_synthetic = 1
        """
    )
    conn.execute(
        "DELETE FROM audit_logs WHERE transaction_id LIKE 'BATCH%'"
    )
    conn.commit()
    conn.close()


@app.route("/api/batch/reset", methods=["POST"])
def batch_reset():
    reset_batch_transactions()
    return jsonify({
        "synthetic_simulation": True,
        "reset": True,
        "simulation_seed": SIMULATION_SEED,
        "simulation_version": SIMULATION_VERSION,
        "reproducible": True,
    })


@app.route("/api/batch/analyze", methods=["POST"])
def batch_analyze():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_synthetic = 1 ORDER BY id"
    ).fetchall()
    summary = []

    for row in rows:
        transaction = dict(row)
        existing_audit = conn.execute(
            """
            SELECT 1
            FROM audit_logs
            WHERE transaction_id = ? AND action = 'batch_recovery_simulated'
            LIMIT 1
            """,
            (transaction["transaction_id"],),
        ).fetchone()
        if existing_audit is not None:
            summary.append(
                {
                    "transaction_id": transaction["transaction_id"],
                    "action": transaction.get("recovery_action"),
                    "reason": transaction.get("recovery_reason"),
                    "recovery_attempted": transaction.get("recovery_attempted") or 0,
                    "recovery_success": transaction.get("recovery_success") or 0,
                    "recovered_amount": transaction.get("recovered_amount") or 0.0,
                    "final_recovery_status": transaction.get("final_recovery_status") or "pending",
                    "synthetic_simulation": True,
                }
            )
            continue

        reset_row = {
            "status": "failed",
            "recovery_status": "pending",
            "recovery_action": None,
            "recovery_reason": None,
            "recovery_attempted": 0,
            "recovery_success": 0,
            "recovered_amount": 0.0,
            "final_recovery_status": None,
            "recovered_at": None,
            "updated_at": "CURRENT_TIMESTAMP",
        }
        conn.execute(
            """
            UPDATE transactions
            SET status = ?,
                recovery_status = ?,
                recovery_action = ?,
                recovery_reason = ?,
                recovery_attempted = ?,
                recovery_success = ?,
                recovered_amount = ?,
                final_recovery_status = ?,
                recovered_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (
                reset_row["status"],
                reset_row["recovery_status"],
                reset_row["recovery_action"],
                reset_row["recovery_reason"],
                reset_row["recovery_attempted"],
                reset_row["recovery_success"],
                reset_row["recovered_amount"],
                reset_row["final_recovery_status"],
                reset_row["recovered_at"],
                transaction["transaction_id"],
            ),
        )

        decision = safe_batch_decision(transaction)
        action = decision["action"]
        reason = decision["reason"]
        recovery_attempted = 0
        recovery_success = 0
        recovered_amount = 0.0
        final_status = "pending"

        if not decision["blocked"]:
            recovery_attempted = 1
            result = simulate_batch_recovery(transaction, action)
            recovery_success = result["recovery_success"]
            recovered_amount = result["recovered_amount"]
            final_status = result["recovery_status"]

            if recovery_success:
                final_status = "successful"
                status_value = "recovered"
                recovery_status = "successful"
            else:
                status_value = "failed"
                recovery_status = "pending"
        else:
            final_status = "human_review" if action == "human_review" else "stopped"
            status_value = "failed"
            recovery_status = final_status

        conn.execute(
            """
            UPDATE transactions
            SET recovery_action = ?,
                recovery_reason = ?,
                recovery_attempted = ?,
                recovery_success = ?,
                recovered_amount = ?,
                final_recovery_status = ?,
                recovery_status = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (
                action,
                reason,
                recovery_attempted,
                recovery_success,
                recovered_amount,
                final_status,
                recovery_status,
                status_value,
                transaction["transaction_id"],
            ),
        )

        conn.execute(
            """
            INSERT INTO audit_logs (transaction_id, action, reason)
            VALUES (?, ?, ?)
            """,
            (
                transaction["transaction_id"],
                "batch_recovery_simulated",
                f"{action}: {reason}",
            ),
        )

        summary.append(
            {
                "transaction_id": transaction["transaction_id"],
                "action": action,
                "reason": reason,
                "recovery_attempted": recovery_attempted,
                "recovery_success": recovery_success,
                "recovered_amount": recovered_amount,
                "final_recovery_status": final_status,
                "synthetic_simulation": True,
            }
        )

    conn.commit()
    conn.close()
    return jsonify({
        "synthetic_simulation": True,
        "processed": len(summary),
        "results": summary,
        "simulation_seed": SIMULATION_SEED,
        "simulation_version": SIMULATION_VERSION,
        "reproducible": True,
    })


@app.route("/api/dashboard/metrics", methods=["GET"])
def dashboard_metrics():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_synthetic = 1"
    ).fetchall()

    total_transactions = len(rows)
    total_revenue_at_risk = sum(float(row["amount"]) for row in rows)

    outcome_counts = {
        "recovered": 0,
        "human_review": 0,
        "failed": 0,
        "stopped": 0,
        "pending": 0,
    }
    for row in rows:
        outcome = normalize_recovery_outcome(dict(row))
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

    recovered_transactions = outcome_counts["recovered"]
    human_escalations = outcome_counts["human_review"]
    failed_recoveries = outcome_counts["failed"]
    stopped_by_policy = outcome_counts["stopped"]
    pending_recoveries = outcome_counts["pending"]
    total_revenue_recovered = sum(
        float(row["recovered_amount"] or 0) for row in rows if normalize_recovery_outcome(dict(row)) == "recovered"
    )

    recovery_rate_by_amount = (
        (total_revenue_recovered / total_revenue_at_risk * 100) if total_revenue_at_risk else 0
    )
    recovery_rate_by_count = (
        (recovered_transactions / total_transactions * 100) if total_transactions else 0
    )

    conn.close()
    return jsonify(
        {
            "total_transactions": total_transactions,
            "total_revenue_at_risk": round(total_revenue_at_risk, 2),
            "recovered_transactions": recovered_transactions,
            "total_revenue_recovered": round(total_revenue_recovered, 2),
            "recovery_rate_by_amount": round(recovery_rate_by_amount, 2),
            "recovery_rate_by_count": round(recovery_rate_by_count, 2),
            "failed_recoveries": failed_recoveries,
            "human_escalations": human_escalations,
            "stopped_by_policy": stopped_by_policy,
            "pending_recoveries": pending_recoveries,
            "simulation_seed": SIMULATION_SEED,
            "simulation_version": SIMULATION_VERSION,
            "reproducible": True,
            "synthetic_simulation": True,
        }
    )


@app.route("/api/dashboard/outcome-breakdown", methods=["GET"])
def dashboard_outcome_breakdown():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_synthetic = 1"
    ).fetchall()

    outcome_counts = {
        "successful": 0,
        "human_review": 0,
        "failed": 0,
        "pending": 0,
        "stopped": 0,
    }
    for row in rows:
        outcome = normalize_recovery_outcome(dict(row))
        if outcome == "recovered":
            outcome_counts["successful"] += 1
        elif outcome in outcome_counts:
            outcome_counts[outcome] += 1

    conn.close()
    return jsonify({**outcome_counts, "synthetic_simulation": True})


@app.route("/api/dashboard/recovery-breakdown", methods=["GET"])
def dashboard_recovery_breakdown():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT recovery_action FROM transactions WHERE is_synthetic = 1"
    ).fetchall()
    breakdown = {"retry": 0, "payment_link": 0, "payment_link_later": 0, "human_review": 0, "stop": 0}
    for row in rows:
        action = row["recovery_action"]
        if action in breakdown:
            breakdown[action] += 1
    conn.close()
    return jsonify({"synthetic_simulation": True, "breakdown": breakdown})


@app.route("/api/batch/transactions", methods=["GET"])
def batch_transactions():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_synthetic = 1 ORDER BY id"
    ).fetchall()
    conn.close()
    return jsonify({"synthetic_simulation": True, "transactions": [dict(row) for row in rows]})


@app.route("/api/webhook/razorpay", methods=["POST"])
def razorpay_webhook():
    raw_body = request.get_data()
    received_signature = request.headers.get("X-Razorpay-Signature")
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    app.logger.info("[WEBHOOK] endpoint reached")
    app.logger.info("[WEBHOOK] secret configured: %s", bool(webhook_secret))
    app.logger.info("[WEBHOOK] signature header present: %s", bool(received_signature))
    app.logger.info("[WEBHOOK] raw body length: %s", len(raw_body))

    if not webhook_secret:
        app.logger.warning("[WEBHOOK] webhook secret missing")
        return jsonify({"error": "Webhook configuration error"}), 500

    if not received_signature:
        app.logger.warning("[WEBHOOK] signature header missing")
        return jsonify({"error": "Missing signature"}), 400

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, received_signature):
        app.logger.warning("[WEBHOOK] signature mismatch")
        return jsonify({"error": "Invalid signature"}), 400

    app.logger.info("[WEBHOOK] signature verified")

    payload = json.loads(raw_body.decode("utf-8"))
    event = payload.get("event")
    app.logger.info("[WEBHOOK] event: %s", event)

    if event != "payment_link.paid":
        return jsonify({"status": "ok"})

    payment_link = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    reference_id = payment_link.get("reference_id", "")
    app.logger.info("[WEBHOOK] reference: %s", reference_id)

    parts = reference_id.split("_") if isinstance(reference_id, str) else []
    transaction_id = None
    if reference_id.startswith("REC_") and len(parts) >= 3:
        transaction_id = parts[1]

    app.logger.info("[WEBHOOK] extracted transaction: %s", transaction_id)

    conn = get_db()
    row = None
    if transaction_id:
        row = conn.execute(
            """
            SELECT transaction_id, amount, status, recovery_status, final_recovery_status,
                   recovery_attempted, recovery_success, recovered_amount
            FROM transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()

    app.logger.info("[WEBHOOK] transaction found: %s", bool(row))

    if row is not None:
        already_recovered = (
            row["status"] == "recovered"
            and row["recovery_status"] == "successful"
            and row["final_recovery_status"] == "successful"
            and int(row["recovery_attempted"] or 0) == 1
            and int(row["recovery_success"] or 0) == 1
            and float(row["recovered_amount"] or 0) > 0
        )

        if not already_recovered:
            conn.execute(
                """
                UPDATE transactions
                SET status = 'recovered',
                    recovery_status = 'successful',
                    final_recovery_status = 'successful',
                    recovery_attempted = 1,
                    recovery_success = 1,
                    recovered_amount = amount,
                    recovered_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE transaction_id = ?
                """,
                (transaction_id,),
            )

            audit_exists = conn.execute(
                """
                SELECT 1
                FROM audit_logs
                WHERE transaction_id = ? AND action = 'revenue_recovered'
                LIMIT 1
                """,
                (transaction_id,),
            ).fetchone()

            if audit_exists is None:
                conn.execute(
                    """
                    INSERT INTO audit_logs (transaction_id, action, reason)
                    VALUES (?, ?, ?)
                    """,
                    (
                        transaction_id,
                        "revenue_recovered",
                        "Payment Link successfully paid",
                    ),
                )

            app.logger.info("[WEBHOOK] database recovery update completed")

        conn.commit()

    conn.close()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
