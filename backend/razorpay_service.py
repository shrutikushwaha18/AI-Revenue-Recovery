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

    data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": f"Recovery payment for {transaction['transaction_id']}",
        "customer": {
            "name": transaction["customer_name"],
            "email": transaction["email"],
            "contact": transaction["phone"],
        },
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "reference_id": reference_id,
    }

    return client.payment_link.create(data)
