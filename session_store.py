import sqlite3
import json
from typing import Optional


class SessionStore:
    def __init__(self, db_path: str = "session_store.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
            """)

    def set(self, session_id: str, data: dict):
        with self.conn:
            self.conn.execute("""
                INSERT INTO sessions (session_id, data)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET data=excluded.data
            """, (session_id, json.dumps(data)))

    def get(self, session_id: str) -> Optional[dict]:
        cursor = self.conn.execute("""
            SELECT data FROM sessions WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None

    def update(self, session_id: str, updates: dict):
        current_data = self.get(session_id) or {}
        current_data.update(updates)
        self.set(session_id, current_data)

    def delete(self, session_id: str):
        with self.conn:
            self.conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def close(self):
        self.conn.close()