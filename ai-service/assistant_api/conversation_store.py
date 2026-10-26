import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from assistant_api.schemas import ChatResponse


DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "conversations.sqlite3"
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds",
    )


class ConversationNotFound(Exception):
    pass


class ConversationStore:
    def __init__(self, path=DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.connection() as connection:
            # 将检查和迁移放进同一个写事务。
            connection.execute("BEGIN IMMEDIATE")

            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    thread_id TEXT PRIMARY KEY,
                    user_id INTEGER CHECK (user_id > 0),
                    created_at TEXT NOT NULL
                )
            """)

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(conversations)"
                )
            }

            if "user_id" not in columns:
                connection.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN user_id INTEGER
                    CHECK (user_id > 0)
                """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (thread_id)
                        REFERENCES conversations(thread_id)
                )
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_turns_thread
                ON conversation_turns(thread_id, turn_id)
            """)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
        )
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("PRAGMA foreign_keys = ON")

            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, user_id: int):
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("用户编号必须是正整数。")

        thread_id = uuid4().hex
        created_at = utc_now()

        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO conversations (
                    thread_id,
                    user_id,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (thread_id, user_id, created_at),
            )

        return {
            "thread_id": thread_id,
            "created_at": created_at,
        }

    def require_owner(
        self,
        connection,
        thread_id: str,
        user_id: int,
    ):
        row = connection.execute(
            """
            SELECT 1
            FROM conversations
            WHERE thread_id = ?
              AND user_id = ?
            """,
            (thread_id, user_id),
        ).fetchone()

        if row is None:
            raise ConversationNotFound()

    def append_turn(
        self,
        thread_id: str,
        user_id: int,
        user_message: str,
        response: ChatResponse,
    ):
        if response.thread_id != thread_id:
            raise ValueError("响应与待保存会话不一致。")

        with self.connection() as connection:
            # 只有会话属于当前用户时，才插入记录。
            cursor = connection.execute(
                """
                INSERT INTO conversation_turns (
                    thread_id,
                    user_message,
                    response_json,
                    created_at
                )
                SELECT thread_id, ?, ?, ?
                FROM conversations
                WHERE thread_id = ?
                  AND user_id = ?
                """,
                (
                    user_message,
                    response.model_dump_json(),
                    utc_now(),
                    thread_id,
                    user_id,
                ),
            )

            if cursor.rowcount != 1:
                raise ConversationNotFound()

    def get_history(
        self,
        thread_id: str,
        user_id: int,
        limit: int,
    ):
        with self.connection() as connection:
            self.require_owner(
                connection,
                thread_id,
                user_id,
            )

            rows = connection.execute(
                """
                SELECT
                    t.turn_id,
                    t.user_message,
                    t.response_json,
                    t.created_at
                FROM conversation_turns AS t
                JOIN conversations AS c
                  ON c.thread_id = t.thread_id
                WHERE c.thread_id = ?
                  AND c.user_id = ?
                ORDER BY t.turn_id DESC
                LIMIT ?
                """,
                (thread_id, user_id, limit),
            ).fetchall()

        return {
            "thread_id": thread_id,
            "turns": [
                {
                    "turn_id": row["turn_id"],
                    "user_message": row["user_message"],
                    "response": json.loads(
                        row["response_json"],
                    ),
                    "created_at": row["created_at"],
                }
                for row in reversed(rows)
            ],
        }