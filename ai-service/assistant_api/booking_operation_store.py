import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from assistant_api.user_tools import BookingRequest


DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "booking_operations.sqlite3"
)


class BookingTargetConflict(Exception):
    pass


class BookingOperationRecord(BaseModel):
    operation_id: str
    event_id: int
    created_at: str


class BookingOperationStore:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS booking_actions (
                    user_id INTEGER NOT NULL,
                    operation_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, operation_id)
                )
            """)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
        )
        connection.row_factory = sqlite3.Row

        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def register(self, user_id: int, body: BookingRequest):
        created_at = datetime.now(timezone.utc).isoformat(
            timespec="milliseconds",
        )

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                INSERT INTO booking_actions (
                    user_id, operation_id, event_id, created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, operation_id) DO NOTHING
                """,
                (
                    user_id,
                    body.operation_id,
                    body.event_id,
                    created_at,
                ),
            )

            row = connection.execute(
                """
                SELECT event_id
                FROM booking_actions
                WHERE user_id = ? AND operation_id = ?
                """,
                (user_id, body.operation_id),
            ).fetchone()

            if row is None:
                raise RuntimeError("报名操作记录不存在。")

            if row["event_id"] != body.event_id:
                raise BookingTargetConflict()

        # 离开 with 时已提交；此后才可以请求 Java。

    def recent(self, user_id: int, limit: int = 20):
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT operation_id, event_id, created_at
                FROM booking_actions
                WHERE user_id = ?
                ORDER BY created_at DESC, operation_id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [dict(row) for row in rows]

    def find(self, user_id: int, operation_id: str):
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT operation_id, event_id, created_at
                FROM booking_actions
                WHERE user_id = ? AND operation_id = ?
                """,
                (user_id, operation_id),
            ).fetchone()
        return dict(row) if row is not None else None
