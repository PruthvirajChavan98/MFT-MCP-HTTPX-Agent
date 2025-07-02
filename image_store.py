import sqlite3
from typing import Optional

from session_store import SessionStore

session_store = SessionStore(db_path="session_store.db")

class ImageStore:
    def __init__(self, db_path: str = "image_store.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    image_ref TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    image_base64 TEXT NOT NULL
                )
            """)

    def save_image(self, image_base64: str, session_id: str) -> str:
        session_data = session_store.get(session_id=session_id)
        if not session_data:
            raise ValueError(f"No session data found for session_id: {session_id}")
        app_id = session_data.get("app_id")
        if not app_id:
            raise ValueError(f"No app_id found in session data for session_id: {session_id}")
        image_ref = f"{app_id}_{session_id}"
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO images (image_ref, app_id, session_id, image_base64) VALUES (?, ?, ?, ?)",
                (image_ref, app_id, session_id, image_base64)
            )
        return image_ref

    def get_image(self, image_ref: str) -> Optional[str]:
        """
        Retrieve the base64 image string by its reference.
        """
        cursor = self.conn.execute(
            "SELECT image_base64 FROM images WHERE image_ref = ?", (image_ref,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def cleanup_image(self, image_ref: str):
        """
        Delete the image record by its reference after processing is done.
        """
        with self.conn:
            self.conn.execute(
                "DELETE FROM images WHERE image_ref = ?", (image_ref,)
            )

    def close(self):
        self.conn.close()