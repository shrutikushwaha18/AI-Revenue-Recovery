from database import get_db, init_db, using_postgres

TRANSACTIONS = [
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
    (
        "TXN005",
        "Neha Sharma",
        "neha@example.com",
        "9876543214",
        3499,
        "failed",
        "bank_decline",
        "pending",
    ),
    (
        "TXN006",
        "Riya Verma",
        "riya@example.com",
        "9876543215",
        1999,
        "failed",
        "bank_decline",
        "pending",
    ),
    (
        "TXN007",
        "Ananya Singh",
        "ananya@example.com",
        "9876543216",
        2499,
        "failed",
        "bank_decline",
        "pending",
    ),
]


def seed_db():
    init_db()
    print(f"Database backend: {'PostgreSQL' if using_postgres() else 'SQLite'}")
    conn = get_db()
    try:
        for transaction in TRANSACTIONS:
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

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_db()
