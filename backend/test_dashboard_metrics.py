import hashlib
import hmac
import json
import os

from app import app
from database import get_db


def test_payment_link_paid_webhook_sets_successful_recovery_state_and_is_idempotent():
    secret = "test-webhook-secret"
    original_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    os.environ["RAZORPAY_WEBHOOK_SECRET"] = secret

    try:
        with app.test_client() as client:
            conn = get_db()
            conn.execute(
                """
                UPDATE transactions
                SET status = 'failed',
                    recovery_status = 'pending',
                    final_recovery_status = NULL,
                    recovery_attempted = 0,
                    recovery_success = 0,
                    recovered_amount = 0,
                    recovered_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE transaction_id = 'TXN005'
                """
            )
            conn.execute("DELETE FROM audit_logs WHERE transaction_id = 'TXN005' AND action = 'revenue_recovered'")
            conn.commit()

            payload = {
                "event": "payment_link.paid",
                "payload": {
                    "payment_link": {
                        "entity": {
                            "reference_id": "REC_TXN005_123"
                        }
                    }
                },
            }
            body = json.dumps(payload).encode("utf-8")
            signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

            response = client.post(
                "/api/webhook/razorpay",
                data=body,
                content_type="application/json",
                headers={"X-Razorpay-Signature": signature},
            )

            assert response.status_code == 200

            tx = conn.execute(
                "SELECT * FROM transactions WHERE transaction_id = 'TXN005'"
            ).fetchone()
            assert tx["status"] == "recovered"
            assert tx["recovery_status"] == "successful"
            assert tx["final_recovery_status"] == "successful"
            assert tx["recovery_attempted"] == 1
            assert tx["recovery_success"] == 1
            assert tx["recovered_amount"] == 3499
            assert tx["recovered_at"] is not None

            audit_actions = [
                row["action"]
                for row in conn.execute(
                    "SELECT action FROM audit_logs WHERE transaction_id = 'TXN005' ORDER BY created_at ASC"
                ).fetchall()
            ]
            assert audit_actions.count("revenue_recovered") == 1

            second_response = client.post(
                "/api/webhook/razorpay",
                data=body,
                content_type="application/json",
                headers={"X-Razorpay-Signature": signature},
            )
            assert second_response.status_code == 200

            audit_actions_after = [
                row["action"]
                for row in conn.execute(
                    "SELECT action FROM audit_logs WHERE transaction_id = 'TXN005' ORDER BY created_at ASC"
                ).fetchall()
            ]
            assert audit_actions_after.count("revenue_recovered") == 1

            conn.close()
    finally:
        if original_secret is None:
            os.environ.pop("RAZORPAY_WEBHOOK_SECRET", None)
        else:
            os.environ["RAZORPAY_WEBHOOK_SECRET"] = original_secret


def test_dashboard_metrics_are_mutually_exclusive():
    with app.test_client() as client:
        conn = get_db()
        conn.execute(
            "UPDATE transactions SET final_recovery_status = NULL, recovery_status = NULL, recovery_success = 0, recovery_attempted = 0, recovered_amount = 0, recovery_action = NULL, status = 'failed' WHERE is_synthetic = 1"
        )

        updates = [
            ("BATCH001", "successful", "successful", 1, 1, 100.0, "stop", "recovered"),
            ("BATCH002", "human_review", "human_review", 0, 0, 0.0, "human_review", "failed"),
            ("BATCH003", "failed", "failed", 0, 1, 0.0, "payment_link", "failed"),
            ("BATCH004", "stopped", "stopped", 0, 0, 0.0, "stop", "failed"),
            ("BATCH005", "pending", "pending", 0, 0, 0.0, "retry", "failed"),
        ]

        for transaction_id, final_status, recovery_status, recovery_success, recovery_attempted, recovered_amount, action, status in updates:
            conn.execute(
                """
                UPDATE transactions
                SET final_recovery_status = ?,
                    recovery_status = ?,
                    recovery_success = ?,
                    recovery_attempted = ?,
                    recovered_amount = ?,
                    recovery_action = ?,
                    status = ?
                WHERE transaction_id = ?
                """,
                (final_status, recovery_status, recovery_success, recovery_attempted, recovered_amount, action, status, transaction_id),
            )

        conn.commit()
        conn.close()

        response = client.get('/api/dashboard/metrics')
        payload = response.get_json()

        assert response.status_code == 200
        assert payload["recovered_transactions"] == 1
        assert payload["human_escalations"] == 1
        assert payload["failed_recoveries"] == 1
        assert payload["stopped_by_policy"] == 1
        assert payload["pending_recoveries"] == 1
        assert (
            payload["recovered_transactions"]
            + payload["human_escalations"]
            + payload["failed_recoveries"]
            + payload["stopped_by_policy"]
            + payload["pending_recoveries"]
            == payload["total_transactions"]
        )

        outcome_response = client.get('/api/dashboard/outcome-breakdown')
        outcome_payload = outcome_response.get_json()

        assert outcome_response.status_code == 200
        assert outcome_payload["successful"] == 1
        assert outcome_payload["human_review"] == 1
        assert outcome_payload["failed"] == 1
        assert outcome_payload["stopped"] == 1
        assert outcome_payload["pending"] == 1
        assert outcome_payload["synthetic_simulation"] is True
        assert (
            outcome_payload["successful"]
            + outcome_payload["human_review"]
            + outcome_payload["failed"]
            + outcome_payload["pending"]
            + outcome_payload["stopped"]
            == payload["total_transactions"]
        )
