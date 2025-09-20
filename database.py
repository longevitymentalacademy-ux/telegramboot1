import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

DB_PATH = Path(__file__).with_name("bot.db")


def initialize_database() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                source TEXT,
                joined_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schedules (
                user_id INTEGER,
                day_index INTEGER,
                scheduled_at TEXT,
                sent_at TEXT,
                PRIMARY KEY (user_id, day_index),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            """
        )


@contextmanager
def get_conn():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        yield conn


def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str], source: Optional[str]) -> None:
    now_iso = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, first_name, last_name, source, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                source=COALESCE(users.source, excluded.source),
                joined_at=COALESCE(users.joined_at, excluded.joined_at)
            """,
            (user_id, username, first_name, last_name, source, now_iso),
        )


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row


def get_next_day_to_send(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(day_index) AS max_day FROM schedules WHERE user_id = ? AND sent_at IS NOT NULL",
            (user_id,),
        ).fetchone()
        if row is None or row["max_day"] is None:
            return 0
        return int(row["max_day"]) + 1


def mark_scheduled(user_id: int, day_index: int, scheduled_at_iso: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO schedules (user_id, day_index, scheduled_at, sent_at)
            VALUES (?, ?, ?, NULL)
            ON CONFLICT(user_id, day_index) DO UPDATE SET
                scheduled_at = excluded.scheduled_at
            """,
            (user_id, day_index, scheduled_at_iso),
        )


def mark_sent(user_id: int, day_index: int) -> None:
    now_iso = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE schedules SET sent_at = ? WHERE user_id = ? AND day_index = ?",
            (now_iso, user_id, day_index),
        )


def get_pending_to_reschedule(current_time_iso: str) -> List[sqlite3.Row]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.user_id, s.day_index
            FROM schedules s
            LEFT JOIN users u ON u.user_id = s.user_id
            WHERE s.sent_at IS NULL
            """
        ).fetchall()
        return rows


def clear_all_schedules_from_db():
    """Deletes all records from the schedules table."""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedules")
        conn.commit()
        print("All schedules cleared from the database.")



