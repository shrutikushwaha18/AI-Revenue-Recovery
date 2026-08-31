from database import DB_PATH, get_db, init_db

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
]


def seed_db():
    init_db()
    print("SQLite DB path:", DB_PATH)
    conn = get_db()

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
    transaction_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    print("Startup transaction count:", transaction_count)
    print("Synthetic transactions seeded if missing.")


if __name__ == "__main__":
    seed_db()
