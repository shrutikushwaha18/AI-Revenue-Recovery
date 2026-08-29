from database import get_db, init_db

init_db()

transactions = [
    (
        "TXN001",
        "Aditi Sharma",
        "aditi@example.com",
        "9876543210",
        2499,
        "failed",
        "bank_decline",
        "pending",
    ),
    (
        "TXN002",
        "Rahul Verma",
        "rahul@example.com",
        "9876543211",
        1299,
        "failed",
        "network_error",
        "pending",
    ),
    (
        "TXN003",
        "Priya Singh",
        "priya@example.com",
        "9876543212",
        4999,
        "failed",
        "insufficient_funds",
        "pending",
    ),
    (
        "TXN004",
        "Aman Gupta",
        "aman@example.com",
        "9876543213",
        899,
        "failed",
        "timeout",
        "pending",
    ),
]

conn = get_db()

for transaction in transactions:
    try:
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
                recovery_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            transaction,
        )
    except Exception:
        pass

conn.commit()
conn.close()

print("Synthetic transactions inserted.")
