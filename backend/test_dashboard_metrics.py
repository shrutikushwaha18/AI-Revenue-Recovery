from app import app
from database import get_db


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
