import sqlite3

from app.core.config import settings


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(settings.sqlite_path)


def init_db() -> None:
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta(key, value) VALUES (?, ?)",
            ("schema_version", "web2_skeleton_001"),
        )
        conn.commit()
