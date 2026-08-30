import hashlib
import hmac
import os
import random

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database import get_db, init_db
from razorpay_service import create_payment_link, generate_reference_id
from recovery_agent import decide_recovery_action
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


def simulate_batch_recovery(transaction, action, rng):
    reason = transaction.get("failure_reason", "unknown_failure")
    probabilities = {
        "retry": {"network_error": 0.9, "timeout": 0.85},
        "payment_link": {"bank_decline": 0.8, "abandoned_checkout": 0.7, "expired_payment": 0.75},
        "payment_link_later": {"insufficient_funds": 0.6},
    }

    chance = probabilities.get(action, {}).get(reason, 0.0)
    if chance == 0:
        return {"recovery_success": 0, "recovered_amount": 0.0, "recovery_status": "pending"}

    success = rng.random() < chance
    if success:
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
    conn = get_db()
    transaction = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()

    if not transaction:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    transaction = dict(transaction)
    decision = decide_recovery_action(transaction)

    conn.execute(
        "UPDATE transactions SET recovery_action = ? WHERE transaction_id = ?",
        (decision["action"], transaction_id),
    )

    conn.execute(
        "INSERT INTO audit_logs (transaction_id, action, reason) VALUES (?, ?, ?)",
        (transaction_id, decision["action"], decision["reason"]),
    )

    conn.commit()
    conn.close()

    return jsonify({"transaction": transaction_id, "decision": decision})


@app.route("/api/recover/<transaction_id>", methods=["POST"])
def recover_transaction(transaction_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM transactions WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    transaction = dict(row)
    decision = decide_recovery_action(transaction)

    if decision["action"] not in ["payment_link", "payment_link_later"]:
        conn.close()
        return jsonify({"decision": decision, "executed": False})

    existing_payment_link = transaction.get("payment_link")
    if transaction.get("recovery_status") == "recovery_started" and existing_payment_link:
        conn.close()
        return jsonify(
            {
                "success": True,
                "transaction_id": transaction_id,
                "payment_link": existing_payment_link,
                "reused_existing_payment_link": True,
                "decision": decision,
            }
        )

    try:
        reference_id = generate_reference_id(transaction_id)
        response = create_payment_link(transaction, reference_id=reference_id)
        short_url = response.get("short_url") or response.get("url") or "not_available"
        payment_link_id = response.get("id") or None

        conn.execute(
            """
            UPDATE transactions
            SET payment_link = ?,
                payment_link_id = ?,
                razorpay_reference_id = ?,
                recovery_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (short_url, payment_link_id, reference_id, "recovery_started", transaction_id),
        )

        conn.execute(
            """
            INSERT INTO audit_logs (transaction_id, action, reason)
            VALUES (?, ?, ?)
            """,
            (
                transaction_id,
                "payment_link_created",
                "Razorpay recovery payment link generated",
            ),
        )

        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "transaction_id": transaction_id,
                "payment_link": short_url,
                "payment_link_id": payment_link_id,
                "razorpay_reference_id": reference_id,
                "decision": decision,
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
            }), 409
        return jsonify({
            "success": False,
            "error": str(exc),
            "decision": decision,
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


@app.route("/api/batch/analyze", methods=["POST"])
def batch_analyze():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_synthetic = 1 AND status = 'failed' ORDER BY id"
    ).fetchall()
    batch_rng = random.Random(42)
    summary = []

    for row in rows:
        transaction = dict(row)
        decision = safe_batch_decision(transaction)
        action = decision["action"]
        reason = decision["reason"]
        recovery_attempted = 0
        recovery_success = 0
        recovered_amount = 0.0
        final_status = "pending"

        if not decision["blocked"]:
            recovery_attempted = 1
            result = simulate_batch_recovery(transaction, action, batch_rng)
            recovery_success = result["recovery_success"]
            recovered_amount = result["recovered_amount"]
            final_status = result["recovery_status"]

            if recovery_success:
                final_status = "successful"
                status_value = "recovered"
            else:
                status_value = "failed"
        else:
            final_status = "human_review" if action == "human_review" else "stopped"
            status_value = "failed"

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
                final_status,
                status_value,
                transaction["transaction_id"],
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
    return jsonify({"synthetic_simulation": True, "processed": len(summary), "results": summary})


@app.route("/api/dashboard/metrics", methods=["GET"])
def dashboard_metrics():
    ensure_batch_seeded()
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE is_synthetic = 1"
    ).fetchall()

    total_transactions = len(rows)
    total_revenue_at_risk = sum(float(row["amount"]) for row in rows)
    recovered_transactions = sum(
        1 for row in rows if int(row["recovery_success"] or 0) == 1 or row["final_recovery_status"] == "successful"
    )
    total_revenue_recovered = sum(
        float(row["recovered_amount"] or 0) for row in rows if int(row["recovery_success"] or 0) == 1
    )
    failed_recoveries = sum(
        1 for row in rows if int(row["recovery_attempted"] or 0) == 1 and int(row["recovery_success"] or 0) == 0
    )
    human_escalations = sum(1 for row in rows if row["recovery_action"] == "human_review")
    stopped_by_policy = sum(1 for row in rows if row["final_recovery_status"] == "stopped")
    pending_recoveries = sum(
        1 for row in rows if row["final_recovery_status"] in (None, "pending", "human_review", "stopped")
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
            "synthetic_simulation": True,
        }
    )


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
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    signature = request.headers.get("X-Razorpay-Signature")
    body = request.get_data()

    if webhook_secret:
        expected_signature = hmac.new(
            webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

        if signature is None or not hmac.compare_digest(signature, expected_signature):
            return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json(silent=True) or {}
    event = data.get("event")

    if event == "payment_link.paid":
        payment_link = data.get("payload", {}).get("payment_link", {}).get("entity", {})
        reference_id = payment_link.get("reference_id", "")
        transaction_id = reference_id.replace("REC_", "", 1).split("_", 1)[0]

        conn = get_db()
        row = conn.execute(
            "SELECT amount FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()

        if row is not None:
            conn.execute(
                """
                UPDATE transactions
                SET status = 'recovered',
                    recovery_status = 'successful',
                    recovered_amount = amount,
                    updated_at = CURRENT_TIMESTAMP,
                    recovered_at = CURRENT_TIMESTAMP
                WHERE transaction_id = ?
                """,
                (transaction_id,),
            )
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
            conn.commit()

        conn.close()

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
