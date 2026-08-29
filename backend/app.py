import hashlib
import hmac
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database import get_db, init_db
from razorpay_service import create_payment_link
from recovery_agent import decide_recovery_action

load_dotenv()

app = Flask(__name__)
CORS(app)

init_db()


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

    try:
        response = create_payment_link(transaction)
        short_url = response.get("short_url") or response.get("url") or "not_available"

        conn.execute(
            """
            UPDATE transactions
            SET payment_link = ?, recovery_status = ?
            WHERE transaction_id = ?
            """,
            (short_url, "recovery_started", transaction_id),
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
                "decision": decision,
            }
        )

    except Exception as exc:
        conn.close()
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


@app.route("/api/webhook", methods=["POST"])
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
        transaction_id = reference_id.replace("REC_", "")

        conn = get_db()
        row = conn.execute(
            "SELECT amount FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()

        if row is not None:
            conn.execute(
                """
                UPDATE transactions
                SET status = 'recovered', recovery_status = 'successful', recovered_amount = amount
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
