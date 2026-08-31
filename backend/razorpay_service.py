import os
import uuid

import razorpay
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def _safe_note_value(value, default=""):
    if value is None:
        return default
    return str(value)


def generate_reference_id(transaction_id):
    return f"REC_{transaction_id}_{uuid.uuid4().hex[:8]}"


def create_payment_link(transaction, reference_id=None):
    if client is None:
        raise RuntimeError(
            "Razorpay credentials missing. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend/.env"
        )

    amount_in_paise = int(float(transaction["amount"]) * 100)

    if reference_id is None:
        reference_id = generate_reference_id(transaction["transaction_id"])

    transaction_id = _safe_note_value(transaction.get("transaction_id"), "unknown")
    failure_reason = _safe_note_value(transaction.get("failure_reason") or "unknown")
    recovery_action = _safe_note_value(
        transaction.get("recovery_action") or transaction.get("next_action") or "payment_link"
    )
    retry_count = _safe_note_value(transaction.get("retry_count", 0))

    data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": f"RecoverAI revenue recovery for {transaction_id}",
        "customer": {
            "name": transaction["customer_name"],
            "email": transaction["email"],
            "contact": transaction["phone"],
        },
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "reference_id": reference_id,
        "notes": {
            "recoverai_transaction_id": transaction_id,
            "failure_reason": failure_reason,
            "recovery_action": recovery_action,
            "workflow": "revenue_recovery",
            "source": "RecoverAI",
            "retry_count": retry_count,
            "mode": "live_test_recovery",
        },
    }

    return client.payment_link.create(data)
