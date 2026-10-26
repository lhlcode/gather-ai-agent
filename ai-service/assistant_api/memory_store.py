import json

from pydantic import BaseModel, ConfigDict, Field

from assistant_api.context_budget import (
    MAX_SUMMARY_BUDGET,
    estimate_history,
)
from assistant_api.conversation_store import ConversationStore, utc_now
from assistant_api.memory_policy import AnswerStyle

SUMMARY_LIMIT = 4
QUOTE_LIMIT = 160
SUMMARY_SCAN_LIMIT = 100
PREVIEW_RECENT_TURNS = 8


class MemoryIntegrityError(Exception):
    pass


class SummaryQuote(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    source_turn: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=QUOTE_LIMIT)


class SummaryView(BaseModel):
    thread_id: str
    before_turn_id: int | None = None
    items: list[SummaryQuote] = Field(default_factory=list, max_length=SUMMARY_LIMIT)
    scanned_turns: int = 0
    updated_at: str | None = None


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    answer_style: AnswerStyle


class PreferenceView(BaseModel):
    answer_style: AnswerStyle | None = None
    updated_at: str | None = None


class MemoryStore:
    def __init__(self, conversations: ConversationStore):
        self.conversations = conversations
        with conversations.connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    thread_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    before_turn_id INTEGER,
                    items_json TEXT NOT NULL,
                    scanned_turns INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES conversations(thread_id)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id INTEGER PRIMARY KEY,
                    answer_style TEXT NOT NULL
                        CHECK(answer_style IN ('concise', 'plain')),
                    updated_at TEXT NOT NULL
                )
            """)

    def get_preference(self, user_id):
        with self.conversations.connection() as connection:
            row = connection.execute(
                "SELECT answer_style, updated_at FROM user_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        try:
            return PreferenceView.model_validate(dict(row)) if row else PreferenceView()
        except ValueError:
            raise MemoryIntegrityError("用户偏好数据未通过校验。") from None

    def set_preference(self, user_id, style):
        body = PreferenceUpdate(answer_style=style)
        now = utc_now()
        with self.conversations.connection() as connection:
            connection.execute("""
                INSERT INTO user_preferences(user_id, answer_style, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    answer_style = excluded.answer_style,
                    updated_at = excluded.updated_at
            """, (user_id, body.answer_style, now))
        return PreferenceView(answer_style=body.answer_style, updated_at=now)

    def clear_preference(self, user_id):
        with self.conversations.connection() as connection:
            connection.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
        return PreferenceView()

    def refresh_summary(self, thread_id, user_id, before_turn_id=None):
        with self.conversations.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.conversations.require_owner(connection, thread_id, user_id)

            if before_turn_id is None:
                recent = connection.execute("""
                    SELECT turn_id FROM conversation_turns
                    WHERE thread_id = ? ORDER BY turn_id DESC LIMIT ?
                """, (thread_id, PREVIEW_RECENT_TURNS)).fetchall()
                before_turn_id = min(row["turn_id"] for row in recent) if recent else None
            else:
                source = connection.execute("""
                    SELECT 1 FROM conversation_turns
                    WHERE thread_id = ? AND turn_id = ?
                """, (thread_id, before_turn_id)).fetchone()
                if source is None:
                    raise MemoryIntegrityError("摘要边界不属于当前会话。")

            rows = connection.execute("""
                SELECT turn_id, user_message FROM conversation_turns
                WHERE thread_id = ? AND turn_id < ?
                ORDER BY turn_id DESC LIMIT ?
            """, (thread_id, before_turn_id or 0, SUMMARY_SCAN_LIMIT)).fetchall()

            selected = []
            for row in rows:
                text = row["user_message"]
                if not text.strip() or len(text) > QUOTE_LIMIT:
                    continue
                item = SummaryQuote(source_turn=row["turn_id"], quote=text)
                candidate = [item, *selected]
                if estimate_history([q.model_dump() for q in candidate]) > MAX_SUMMARY_BUDGET:
                    continue
                selected = candidate
                if len(selected) == SUMMARY_LIMIT:
                    break

            now = utc_now()
            connection.execute("""
                INSERT INTO conversation_summaries(
                    thread_id, user_id, before_turn_id, items_json,
                    scanned_turns, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    before_turn_id = excluded.before_turn_id,
                    items_json = excluded.items_json,
                    scanned_turns = excluded.scanned_turns,
                    updated_at = excluded.updated_at
            """, (
                thread_id, user_id, before_turn_id,
                json.dumps([item.model_dump() for item in selected], ensure_ascii=False),
                len(rows), now,
            ))
            return SummaryView(
                thread_id=thread_id, before_turn_id=before_turn_id,
                items=selected, scanned_turns=len(rows), updated_at=now,
            )

    def get_summary(self, thread_id, user_id):
        with self.conversations.connection() as connection:
            self.conversations.require_owner(connection, thread_id, user_id)
            row = connection.execute("""
                SELECT * FROM conversation_summaries
                WHERE thread_id = ? AND user_id = ?
            """, (thread_id, user_id)).fetchone()
            if row is None:
                return SummaryView(thread_id=thread_id)
            try:
                items = [SummaryQuote.model_validate(q) for q in json.loads(row["items_json"])]
                boundary = row["before_turn_id"]
                if boundary is not None and connection.execute(
                    "SELECT 1 FROM conversation_turns WHERE thread_id = ? AND turn_id = ?",
                    (thread_id, boundary),
                ).fetchone() is None:
                    raise ValueError("摘要边界不属于当前会话。")
                if not 0 <= row["scanned_turns"] <= SUMMARY_SCAN_LIMIT:
                    raise ValueError("摘要扫描范围不合法。")
                if estimate_history([q.model_dump() for q in items]) > MAX_SUMMARY_BUDGET:
                    raise ValueError("摘要超过预算。")
                ids = [item.source_turn for item in items]
                if ids != sorted(set(ids)):
                    raise ValueError("摘要来源轮次重复或顺序不合法。")
                for item in items:
                    source = connection.execute("""
                        SELECT user_message FROM conversation_turns
                        WHERE thread_id = ? AND turn_id = ?
                    """, (thread_id, item.source_turn)).fetchone()
                    if (
                        source is None
                        or source["user_message"] != item.quote
                        or row["before_turn_id"] is None
                        or item.source_turn >= row["before_turn_id"]
                    ):
                        raise ValueError("摘要不是当前会话的完整用户原话。")
                return SummaryView(
                    thread_id=thread_id, before_turn_id=row["before_turn_id"],
                    items=items, scanned_turns=row["scanned_turns"],
                    updated_at=row["updated_at"],
                )
            except (ValueError, TypeError):
                raise MemoryIntegrityError("摘要来源校验失败，请重新生成摘要。") from None

    def clear_summary(self, thread_id, user_id):
        with self.conversations.connection() as connection:
            self.conversations.require_owner(connection, thread_id, user_id)
            connection.execute(
                "DELETE FROM conversation_summaries WHERE thread_id = ? AND user_id = ?",
                (thread_id, user_id),
            )
