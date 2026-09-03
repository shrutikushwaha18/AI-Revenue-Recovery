import hashlib
import hmac
import json
import os

import app as app_module
from database import PostgresCursor
from database import get_db
from recovery_agent import apply_policy_override
from seed import seed_db


def test_postgres_cursor_execute_without_parameters_preserves_literal_percent():
    class FakeCursor:
        def __init__(self):
            self.calls = []

        def execute(self, *args):
            self.calls.append(args)

    raw_cursor = FakeCursor()
    cursor = PostgresCursor(raw_cursor)

    cursor.execute("SELECT COUNT(*) FROM transactions WHERE transaction_id LIKE 'BATCH%'")

    assert raw_cursor.calls == [
        ("SELECT COUNT(*) FROM transactions WHERE transaction_id LIKE 'BATCH%'",)
    ]


def test_payment_link_paid_webhook_sets_successful_recovery_state_and_is_idempotent():
    secret = "test-webhook-secret"
    original_secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
    os.environ["RAZORPAY_WEBHOOK_SECRET"] = secret

    try:
        with app_module.app.test_client() as client:
            conn = get_db()
            original_amount = conn.execute(
                "SELECT amount FROM transactions WHERE transaction_id = 'TXN005'"
            ).fetchone()["amount"]
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
            assert tx["recovered_amount"] == original_amount
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


def test_seed_db_does_not_overwrite_existing_recovered_transaction():
    transaction_id = "TXN007"
    conn = get_db()
    original = dict(
        conn.execute(
            "SELECT status, recovery_status, recovery_success, recovered_amount, recovered_at FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
    )
    conn.execute(
        """
        UPDATE transactions
        SET status = 'recovered',
            recovery_status = 'successful',
            recovery_success = 1,
            recovered_amount = 2499,
            recovered_at = CURRENT_TIMESTAMP
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    )
    conn.commit()
    conn.close()

    try:
        seed_db()
        conn = get_db()
        recovered = conn.execute(
            "SELECT status, recovery_status, recovery_success, recovered_amount, recovered_at FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
        conn.close()

        assert recovered["status"] == "recovered"
        assert recovered["recovery_status"] == "successful"
        assert recovered["recovery_success"] == 1
        assert recovered["recovered_amount"] == 2499
        assert recovered["recovered_at"] is not None
    finally:
        conn = get_db()
        conn.execute(
            """
            UPDATE transactions
            SET status = ?, recovery_status = ?, recovery_success = ?,
                recovered_amount = ?, recovered_at = ?
            WHERE transaction_id = ?
            """,
            (
                original["status"],
                original["recovery_status"],
                original["recovery_success"],
                original["recovered_amount"],
                original["recovered_at"],
                transaction_id,
            ),
        )
        conn.commit()
        conn.close()


def test_bank_decline_retry_is_overridden_by_policy_guard():
    transaction = {
        "transaction_id": "TXN007",
        "amount": 2499,
        "failure_reason": "bank_decline",
        "retry_count": 0,
        "status": "failed",
        "recovery_status": "pending",
        "customer_opted_out": 0,
        "is_synthetic": 0,
    }

    decision = {
        "action": "retry",
        "reason": "Temporary network issue detected; retry is recommended",
        "risk_level": "medium",
        "requires_human_review": False,
        "reasoning_source": "llm",
        "recommended_action": "retry",
    }

    guarded = apply_policy_override(transaction, decision)

    assert guarded["action"] == "payment_link"
    assert guarded["final_guarded_action"] == "payment_link"
    assert guarded["reasoning_source"] == "llm"
    assert guarded["recommended_action"] == "retry"
    assert guarded["policy_override"] is True
    assert guarded["policy_override_reason"] == "Bank decline policy blocks immediate retry."
    assert "issuer decline" in guarded["reason"].lower()


def test_agent_decision_snapshot_is_reused_across_trace_and_recover(monkeypatch):
    original_reason_transaction = app_module.reason_transaction
    original_apply_policy_override = app_module.apply_policy_override
    original_create_payment_link = app_module.create_payment_link
    call_count = {"reason_transaction": 0}

    def fake_reason_transaction(transaction, deterministic_decision, deterministic_only=False):
        call_count["reason_transaction"] += 1
        return {
            "action": "retry",
            "reason": "Temporary network issue detected; retry is recommended",
            "confidence": None,
            "confidence_type": "LLM recommendation, not a probability",
            "risk_level": "medium",
            "requires_human_review": False,
            "reasoning_source": "llm",
            "recommended_action": "retry",
        }

    def fake_apply_policy_override(transaction, decision, historical_execution=False):
        guarded = dict(decision)
        guarded["action"] = "payment_link"
        guarded["final_guarded_action"] = "payment_link"
        guarded["guarded_reason"] = "Immediate retry may repeat the issuer decline; policy selected a payment link instead."
        guarded["policy_override"] = True
        guarded["policy_override_reason"] = "Bank decline policy blocks immediate retry."
        guarded["reason"] = guarded["guarded_reason"]
        guarded["risk_level"] = "low"
        guarded["requires_human_review"] = False
        return guarded

    def fake_create_payment_link(transaction, reference_id=None):
        return {
            "id": "plink_snapshot_123",
            "short_url": "https://rzp.io/i/recoverai-snapshot",
            "reference_id": reference_id,
        }

    monkeypatch.setattr(app_module, "reason_transaction", fake_reason_transaction)
    monkeypatch.setattr(app_module, "apply_policy_override", fake_apply_policy_override)
    monkeypatch.setattr(app_module, "create_payment_link", fake_create_payment_link)

    conn = get_db()
    conn.execute("DELETE FROM agent_decisions WHERE transaction_id = 'TXN007'")
    conn.commit()
    conn.close()

    with app_module.app.test_client() as client:
        trace_response = client.get('/api/agent/trace/TXN007')
        trace_payload = trace_response.get_json()

        assert trace_response.status_code == 200
        assert trace_payload["decision"]["reasoning_source"] == "llm"
        assert trace_payload["decision"]["recommended_action"] == "retry"
        assert trace_payload["decision"]["final_guarded_action"] == "payment_link"
        assert trace_payload["decision"]["policy_override"] is True
        assert trace_payload["decision_reused"] is False

        recover_response = client.post('/api/recover/TXN007')
        recover_payload = recover_response.get_json()

        assert recover_response.status_code == 200
        assert recover_payload["decision"]["reasoning_source"] == "llm"
        assert recover_payload["decision"]["recommended_action"] == "retry"
        assert recover_payload["decision"]["final_guarded_action"] == "payment_link"
        assert recover_payload["decision"]["policy_override"] is True
        assert recover_payload["decision"]["final_guarded_action"] == recover_payload["decision"]["action"]
        assert call_count["reason_transaction"] == 1

    monkeypatch.setattr(app_module, "reason_transaction", original_reason_transaction)
    monkeypatch.setattr(app_module, "apply_policy_override", original_apply_policy_override)
    monkeypatch.setattr(app_module, "create_payment_link", original_create_payment_link)


def test_stored_llm_retry_decision_schedules_retry(monkeypatch):
    transaction_id = "TXN004"
    conn = get_db()
    conn.execute(
        """
        UPDATE transactions
        SET retry_count = 0,
            recovery_status = 'pending',
            recovery_action = NULL,
            recovery_attempted = 0,
            recovery_success = 0,
            recovered_amount = 0,
            status = 'failed',
            payment_link = NULL,
            payment_link_id = NULL,
            razorpay_reference_id = NULL
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    )
    conn.execute("DELETE FROM agent_decisions WHERE transaction_id = ?", (transaction_id,))
    conn.execute("DELETE FROM audit_logs WHERE transaction_id = ?", (transaction_id,))
    conn.execute(
        """
        INSERT INTO agent_decisions (
            transaction_id, reasoning_source, recommended_action,
            final_guarded_action, action, reason, guarded_reason, risk_level,
            requires_human_review, policy_override, confidence_type
        ) VALUES (?, 'llm', 'retry', 'retry', 'retry', ?, ?, 'medium', 0, 0, ?)
        """,
        (
            transaction_id,
            "Temporary timeout detected",
            "Temporary timeout detected",
            "LLM recommendation, not a probability",
        ),
    )
    conn.commit()
    conn.close()

    try:
        with app_module.app.test_client() as client:
            response = client.post(f"/api/recover/{transaction_id}")
            payload = response.get_json()

        assert response.status_code == 200
        assert payload["success"] is True
        assert payload["executed"] is True
        assert payload["decision_reused"] is True
        assert payload["decision"]["final_guarded_action"] == "retry"
        assert payload["execution"] == {
            "action": "retry",
            "external_tool": None,
            "retry_scheduled": True,
        }

        conn = get_db()
        transaction = conn.execute(
            "SELECT retry_count, recovery_attempted, recovery_action, recovery_status, recovery_success, recovered_amount, status FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()
        audit = conn.execute(
            "SELECT action FROM audit_logs WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchall()
        conn.close()

        assert transaction["retry_count"] == 1
        assert transaction["recovery_attempted"] == 1
        assert transaction["recovery_action"] == "retry"
        assert transaction["recovery_status"] == "retry_scheduled"
        assert transaction["recovery_success"] == 0
        assert transaction["recovered_amount"] == 0
        assert transaction["status"] == "failed"
        assert [row["action"] for row in audit] == ["retry_scheduled"]

        second_response = client.post(f"/api/recover/{transaction_id}")
        second_payload = second_response.get_json()
        assert second_response.status_code == 200
        assert second_payload["executed"] is True
        assert second_payload["execution"]["retry_scheduled"] is True

        conn = get_db()
        retry_count = conn.execute(
            "SELECT retry_count FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        ).fetchone()["retry_count"]
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE transaction_id = ? AND action = 'retry_scheduled'",
            (transaction_id,),
        ).fetchone()[0]
        conn.close()
        assert retry_count == 1
        assert audit_count == 1
    finally:
        conn = get_db()
        conn.execute("DELETE FROM agent_decisions WHERE transaction_id = ?", (transaction_id,))
        conn.execute("DELETE FROM audit_logs WHERE transaction_id = ?", (transaction_id,))
        conn.execute(
            """
            UPDATE transactions
            SET retry_count = 0,
                recovery_status = 'pending',
                recovery_action = NULL,
                recovery_attempted = 0,
                recovery_success = 0,
                recovered_amount = 0,
                status = 'failed'
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        )
        conn.commit()
        conn.close()


def test_dashboard_metrics_are_mutually_exclusive():
    with app_module.app.test_client() as client:
        app_module.ensure_batch_seeded()
        conn = get_db()
        conn.execute(
            "UPDATE transactions SET final_recovery_status = NULL, recovery_status = NULL, recovery_success = 0, recovery_attempted = 0, recovered_amount = 0, recovery_action = NULL, status = 'failed' WHERE is_synthetic = 1"
        )
        conn.execute("DELETE FROM audit_logs WHERE transaction_id LIKE 'BATCH%'")

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
        assert payload["pending_recoveries"] == 96
        assert payload["simulation_seed"] == "recoverai-v1"
        assert payload["simulation_version"] == "1.0"
        assert payload["reproducible"] is True
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
        assert outcome_payload["pending"] == 96
        assert outcome_payload["synthetic_simulation"] is True
        assert (
            outcome_payload["successful"]
            + outcome_payload["human_review"]
            + outcome_payload["failed"]
            + outcome_payload["pending"]
            + outcome_payload["stopped"]
            == payload["total_transactions"]
        )


def test_batch_reset_and_analyze_are_reproducible_and_idempotent():
    with app_module.app.test_client() as client:
        reset_response = client.post('/api/batch/reset')
        assert reset_response.status_code == 200
        reset_payload = reset_response.get_json()
        assert reset_payload["reset"] is True
        assert reset_payload["simulation_seed"] == "recoverai-v1"
        assert reset_payload["simulation_version"] == "1.0"
        assert reset_payload["reproducible"] is True

        first_analyze = client.post('/api/batch/analyze')
        assert first_analyze.status_code == 200
        first_payload = first_analyze.get_json()
        assert first_payload["reproducible"] is True
        assert first_payload["simulation_seed"] == "recoverai-v1"
        assert first_payload["simulation_version"] == "1.0"

        first_metrics = client.get('/api/dashboard/metrics').get_json()
        first_count = len([
            row["action"] for row in client.get('/api/batch/transactions').get_json()["transactions"]
            if row["recovery_action"] == "batch_recovery_simulated"
        ])

        second_reset = client.post('/api/batch/reset')
        assert second_reset.status_code == 200

        second_analyze = client.post('/api/batch/analyze')
        assert second_analyze.status_code == 200
        second_metrics = client.get('/api/dashboard/metrics').get_json()

        assert first_metrics == second_metrics
        assert first_analyze.get_json() == second_analyze.get_json()

        batch_audit_rows = client.get('/api/audit/BATCH001').get_json()
        assert len(batch_audit_rows) == 1

        repeat_analyze = client.post('/api/batch/analyze')
        assert repeat_analyze.status_code == 200
        repeat_metrics = client.get('/api/dashboard/metrics').get_json()
        assert repeat_metrics == second_metrics

        batch_audit_after_repeat = client.get('/api/audit/BATCH001').get_json()
        assert len(batch_audit_after_repeat) == 1


def test_live_recovery_creates_razorpay_metadata_and_blocks_synthetic_transactions(monkeypatch):
    def fake_reason_transaction(transaction, deterministic_decision, deterministic_only=False):
        return {
            "action": "payment_link",
            "reason": "Bank decline should use a safer payment link.",
            "confidence": None,
            "confidence_type": "LLM recommendation, not a probability",
            "risk_level": "low",
            "requires_human_review": False,
            "reasoning_source": "llm",
            "recommended_action": "payment_link",
        }

    def fake_create_payment_link(transaction, reference_id=None):
        return {
            "id": "plink_123456",
            "short_url": "https://rzp.io/i/recoverai-demo",
            "reference_id": reference_id,
        }

    monkeypatch.setattr(app_module, "reason_transaction", fake_reason_transaction)
    monkeypatch.setattr(app_module, "create_payment_link", fake_create_payment_link)

    with app_module.app.test_client() as client:
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
                recovery_action = NULL,
                payment_link = NULL,
                payment_link_id = NULL,
                razorpay_reference_id = NULL
            WHERE transaction_id = 'TXN005'
            """
        )
        conn.execute("DELETE FROM audit_logs WHERE transaction_id = 'TXN005'")
        conn.execute("DELETE FROM agent_decisions WHERE transaction_id = 'TXN005'")
        conn.commit()

        response = client.post('/api/recover/TXN005')
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["transaction_id"] == "TXN005"
        assert payload["razorpay_reference_id"].startswith("REC_TXN005_")
        assert payload["metadata_sent_to_razorpay"]["failure_reason"] == "bank_decline"
        assert payload["metadata_sent_to_razorpay"]["workflow"] == "revenue_recovery"
        assert payload["metadata_sent_to_razorpay"]["source"] == "RecoverAI"

        tx = conn.execute(
            "SELECT recovery_status, recovery_action, razorpay_reference_id, payment_link_id FROM transactions WHERE transaction_id = 'TXN005'"
        ).fetchone()
        assert tx["recovery_status"] == "recovery_started"
        assert tx["recovery_action"] == "payment_link"
        assert tx["razorpay_reference_id"].startswith("REC_TXN005_")
        assert tx["payment_link_id"] == "plink_123456"

        audit_rows = conn.execute(
            "SELECT action, reason FROM audit_logs WHERE transaction_id = 'TXN005' ORDER BY created_at ASC"
        ).fetchall()
        assert [row["action"] for row in audit_rows] == ["payment_link_created"]
        assert audit_rows[0]["reason"] == "Razorpay recovery payment link generated with RecoverAI metadata"

        second_response = client.post('/api/recover/TXN005')
        assert second_response.status_code == 200
        second_payload = second_response.get_json()
        assert second_payload["reused_existing_link"] is True

        audit_rows_after_second = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE transaction_id = 'TXN005' AND action = 'payment_link_created'"
        ).fetchone()[0]
        assert audit_rows_after_second == 1

        batch_row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = 'BATCH001'"
        ).fetchone()
        if batch_row is not None:
            conn.execute("UPDATE transactions SET is_synthetic = 1 WHERE transaction_id = 'BATCH001'")
            conn.commit()

        synthetic_response = client.post('/api/recover/BATCH001')
        assert synthetic_response.status_code == 200
        synthetic_payload = synthetic_response.get_json()
        assert synthetic_payload["executed"] is False
        assert synthetic_payload["reason"] == "Synthetic transactions cannot trigger Razorpay recovery"

        conn.close()
