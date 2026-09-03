import os
import re
import sqlite3
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "recoverai.db"))
_postgres_pool = None
_postgres_pool_lock = threading.Lock()
_open_connections = threading.local()


def get_database_url():
    return os.getenv("DATABASE_URL")


def using_postgres():
    return bool(get_database_url())


class PostgresCursor:
    def __init__(self, cursor, owner=None):
        self._cursor = cursor
        self._owner = owner

    def close(self):
        try:
            self._cursor.close()
        finally:
            if self._owner is not None:
                self._owner._cursors.discard(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def execute(self, query, parameters=()):
        query = query.replace("?", "%s")
        query = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", query, flags=re.IGNORECASE)
        if query.lstrip().upper().startswith("INSERT INTO") and "ON CONFLICT" not in query.upper():
            query = f"{query.rstrip().rstrip(';')} ON CONFLICT DO NOTHING"
        self._cursor.execute(query, parameters)
        return self

    def fetchone(self):
        try:
            return self._cursor.fetchone()
        finally:
            self.close()

    def fetchmany(self, size=None):
        try:
            return self._cursor.fetchmany() if size is None else self._cursor.fetchmany(size)
        finally:
            self.close()

    def fetchall(self):
        try:
            return self._cursor.fetchall()
        finally:
            self.close()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class PostgresConnection:
    def __init__(self, connection, pool):
        self._connection = connection
        self._pool = pool
        self._cursors = set()
        self._closed = False
        _open_connections.connections = getattr(_open_connections, "connections", set())
        _open_connections.connections.add(self)

    def execute(self, query, parameters=()):
        cursor = PostgresCursor(self._connection.cursor(), self)
        self._cursors.add(cursor)
        return cursor.execute(query, parameters)

    def cursor(self):
        cursor = PostgresCursor(self._connection.cursor(), self)
        self._cursors.add(cursor)
        return cursor

    def close(self):
        if self._closed:
            return
        self._closed = True
        for cursor in list(self._cursors):
            try:
                cursor.close()
            except Exception:
                pass
        close_connection = False
        try:
            if not self._connection.closed:
                self._connection.rollback()
        except Exception:
            close_connection = True
        finally:
            try:
                self._pool.putconn(
                    self._connection,
                    close=close_connection or bool(self._connection.closed),
                )
            finally:
                _open_connections.connections.discard(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def __getattr__(self, name):
        return getattr(self._connection, name)


def get_db():
    database_url = get_database_url()
    if database_url:
        from psycopg2.extras import DictCursor
        from psycopg2.pool import ThreadedConnectionPool

        global _postgres_pool
        if _postgres_pool is None:
            with _postgres_pool_lock:
                if _postgres_pool is None:
                    _postgres_pool = ThreadedConnectionPool(
                        minconn=1,
                        maxconn=5,
                        dsn=database_url,
                        cursor_factory=DictCursor,
                    )
        return PostgresConnection(_postgres_pool.getconn(), _postgres_pool)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def close_open_connections():
    for connection in list(getattr(_open_connections, "connections", set())):
        connection.close()


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
    try:
        is_postgres = using_postgres()
        id_definition = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"

        conn.execute(
            f"""
        CREATE TABLE IF NOT EXISTS transactions (
            id {id_definition},
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

        if is_postgres:
            transaction_columns = {
                row["column_name"]
                for row in conn.execute(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'transactions'
                """
                ).fetchall()
            }
        else:
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
            f"""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id {id_definition},
            transaction_id TEXT,
            action TEXT,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        )

        conn.execute(
            f"""
        CREATE TABLE IF NOT EXISTS agent_decisions (
            id {id_definition},
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
    finally:
        conn.close()
