import hashlib
import hmac
import os

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
                recovery_status = ?
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
