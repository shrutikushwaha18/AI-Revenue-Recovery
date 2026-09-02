import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "recoverai.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_transaction_by_id(transaction_id):
    normalized = (transaction_id or "").strip()
    print(f"[DEBUG] database path={DB_PATH}")
    print(f"[DEBUG] repr(transaction_id)={repr(transaction_id)}")

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?",
            (normalized,),
        ).fetchone()
        print(f"[DEBUG] transaction_found={row is not None}")
        return row
    finally:
        conn.close()


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
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_synthetic INTEGER DEFAULT 0,
            recovery_attempted INTEGER DEFAULT 0,
            recovery_success INTEGER DEFAULT 0,
            recovery_reason TEXT,
            final_recovery_status TEXT,
            recovered_at TIMESTAMP,
            customer_opted_out INTEGER DEFAULT 0
        )
        """
    )

    transaction_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
    }

    for column_name, column_type in {
        "payment_link_id": "TEXT",
        "razorpay_reference_id": "TEXT",
        "is_synthetic": "INTEGER DEFAULT 0",
        "recovery_attempted": "INTEGER DEFAULT 0",
        "recovery_success": "INTEGER DEFAULT 0",
        "recovery_reason": "TEXT",
        "final_recovery_status": "TEXT",
        "recovered_at": "TIMESTAMP",
        "customer_opted_out": "INTEGER DEFAULT 0",
    }.items():
        if column_name not in transaction_columns:
            conn.execute(
                f"ALTER TABLE transactions ADD COLUMN {column_name} {column_type}"
            )

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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT UNIQUE,
            reasoning_source TEXT,
            recommended_action TEXT,
            final_guarded_action TEXT,
            action TEXT,
            reason TEXT,
            guarded_reason TEXT,
            risk_level TEXT,
            requires_human_review INTEGER DEFAULT 0,
            policy_override INTEGER DEFAULT 0,
            policy_override_reason TEXT,
            confidence REAL,
            confidence_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()
