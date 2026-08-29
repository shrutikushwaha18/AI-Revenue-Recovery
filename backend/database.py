import sqlite3

DB_NAME = "recoverai.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT UNIQUE,
            customer_name TEXT,
            email TEXT,
            phone TEXT,
            amount REAL,
            status TEXT,
            failure_reason TEXT,
            recovery_status TEXT,
            recovery_action TEXT,
            retry_count INTEGER DEFAULT 0,
            payment_link TEXT,
            payment_link_id TEXT,
            razorpay_reference_id TEXT,
            recovered_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    transaction_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
    }

    if "payment_link_id" not in transaction_columns:
        conn.execute("ALTER TABLE transactions ADD COLUMN payment_link_id TEXT")
    if "razorpay_reference_id" not in transaction_columns:
        conn.execute("ALTER TABLE transactions ADD COLUMN razorpay_reference_id TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT,
            action TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()
