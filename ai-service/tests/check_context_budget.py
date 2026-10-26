"""上下文预算回归检查：临时 SQLite + 模拟模型，无外部 API 调用。"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, Field
from assistant_api.context_budget import (
    INPUT_BUDGET,
    MAX_HISTORY_BUDGET,
    OUTPUT_RESERVE,
    ContextBudgetExceeded,
    build_json_messages,
    estimate_history,
    estimate_messages,
    select_history,
)
from assistant_api.chat_service import ChatService, ModelServiceError
from assistant_api.conversation_service import (
    ConversationService, QuestionResolution, IntentCheck,
    RESOLVE_PROMPT, INTENT_PROMPT,
)
from assistant_api.conversation_store import ConversationStore, ConversationNotFound
from assistant_api.identity_service import CurrentUser
from assistant_api.schemas import ChatResponse, MessageRequest, TokenUsage
from assistant_api.user_tools import UserTools


def turn(number, user=None, answer="短回复", status="answered"):
    return {
        "turn_id": number,
        "user_message": user or f"第{number}轮问题",
        "response": {
            "status": status,
            "answer": answer,
            "resolved_question": None,
        },
    }


def choose(turns, question="已经付款的呢？"):
    return select_history(
        turns, question,
        QuestionResolution, RESOLVE_PROMPT,
        IntentCheck, INTENT_PROMPT,
    )


def check_selection():
    empty, stats = choose([])
    assert empty["recent_history"] == []
    assert not empty["latest_history_missing"]
    assert stats["resolver_input_estimate"] <= INPUT_BUDGET

    turns = [turn(i) for i in range(1, 13)]
    context, stats = choose(turns)
    ids = stats["selected_turn_ids"]
    assert len(ids) > 4, ids
    assert ids == list(range(13 - len(ids), 13)), ids
    assert stats["history_estimate"] <= MAX_HISTORY_BUDGET
    assert stats["resolver_input_estimate"] <= INPUT_BUDGET
    assert stats["intent_reserved_input_estimate"] <= INPUT_BUDGET

    latest_long = [turn(1, user="旧话题：吃面"), turn(2, user="新话题：找工作", answer="工作" * 10000)]
    context, stats = choose(latest_long, "接着刚才的话题")
    assert context["recent_history"] == []
    assert context["latest_history_missing"]
    assert context["history_truncated"]

    middle_long = [
        turn(1, user="旧话题：吃面"),
        turn(2, answer="很长" * 10000),
        turn(3, user="新话题：订单"),
        turn(4, user="订单后续"),
    ]
    context, stats = choose(middle_long)
    assert stats["selected_turn_ids"] == [3, 4]
    assert not context["latest_history_missing"]
    assert context["history_truncated"]

    context, _ = choose([turn(1, user="已支付订单不能取消。", answer="结果尚未确认", status="unknown")])
    assert context["recent_history"][0]["user_message"] == "已支付订单不能取消。"
    assert context["recent_history"][0]["assistant_reply"] == "结果尚未确认"
    context, _ = choose([turn(1, answer="不可信候选回答", status="blocked")])
    assert context["recent_history"][0]["assistant_reply"] == ""

    try:
        choose([], "超长问题" * 10000)
    except ContextBudgetExceeded:
        pass
    else:
        raise AssertionError("Oversized fixed input was accepted")
    print("PASS: selection, >4 short turns, contiguous suffix, missing latest, no clipping, status projection")


class TinyResult(BaseModel):
    value: str


class LargeSchema(BaseModel):
    value: str = Field(description="说明" * 10000)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create),
        )

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content='{"value":"ok"}'),
            )],
            usage=SimpleNamespace(
                prompt_tokens=23,
                completion_tokens=7,
                total_tokens=30,
            ),
        )


async def check_send_guard():
    client = FakeClient()
    service = ChatService(client, None)
    result, usage = await service.ask_json(TinyResult, "测试说明", {"question": "测试问题"})
    assert result.value == "ok"
    assert usage.input_tokens == 23
    assert client.calls[0]["max_tokens"] == OUTPUT_RESERVE
    assert client.calls[0]["messages"] == build_json_messages(TinyResult, "测试说明", {"question": "测试问题"})
    assert estimate_messages(client.calls[0]["messages"]) <= INPUT_BUDGET

    for schema, instruction, payload in [
        (TinyResult, "超长说明" * 10000, {}),
        (TinyResult, "说明", {"question": "问题" * 10000}),
        (LargeSchema, "说明", {}),
    ]:
        before = len(client.calls)
        try:
            await service.ask_json(schema, instruction, payload)
        except ModelServiceError as error:
            assert error.status_code == 413
        else:
            raise AssertionError("Over-budget request was sent")
        assert len(client.calls) == before
    print("PASS: shared send guard covers system/schema/payload; reserve matches max_tokens; actual usage retained")


class RecordingAgent:
    def __init__(self):
        self.payloads = []

    async def ask_json(self, schema, instruction, payload):
        self.payloads.append((schema, json.loads(json.dumps(payload))))
        await asyncio.sleep(0)
        if schema is QuestionResolution:
            result = {
                "status": "ready",
                "standalone_question": payload["current_user_message"],
                "clarification": "",
            }
        else:
            result = {"faithful": True, "reason": "test"}
        return schema.model_validate(result), TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)

    async def answer(self, body, **kwargs):
        return ChatResponse(
            status="answered",
            thread_id=body.thread_id,
            answer="模拟回答",
            claims=[],
            model_calls=0,
            usage=None,
        )


async def check_service_isolation():
    with tempfile.TemporaryDirectory(prefix="context-budget-test-") as folder:
        store = ConversationStore(Path(folder) / "conversations.sqlite3")
        a = store.create(7)["thread_id"]
        b = store.create(8)["thread_id"]
        for thread_id, user_id, marker in [(a, 7, "USER_A_ONLY"), (b, 8, "USER_B_ONLY")]:
            for i in range(45):
                response = ChatResponse(
                    status="answered", thread_id=thread_id,
                    answer=f"{marker}回复{i}", claims=[],
                    model_calls=0, usage=None,
                )
                store.append_turn(thread_id, user_id, f"{marker}问题{i}", response)

        agent = RecordingAgent()
        service = ConversationService(agent, store)
        tools_a = UserTools(CurrentUser(userId=7, username="a", role="USER"), None, "test-a")
        tools_b = UserTools(CurrentUser(userId=8, username="b", role="USER"), None, "test-b")
        responses = await asyncio.gather(
            service.answer(MessageRequest(thread_id=a, message="问A"), tools_a),
            service.answer(MessageRequest(thread_id=b, message="问B"), tools_b),
        )
        assert all(response.model_calls == 2 for response in responses)
        for schema, payload in agent.payloads:
            serialized = json.dumps(payload)
            if payload["current_user_message"] == "问A":
                assert "USER_A_ONLY" in serialized and "USER_B_ONLY" not in serialized
            else:
                assert "USER_B_ONLY" in serialized and "USER_A_ONLY" not in serialized
            assert estimate_messages(build_json_messages(
                schema,
                RESOLVE_PROMPT if schema is QuestionResolution else INTENT_PROMPT,
                payload,
            )) <= INPUT_BUDGET

        before = len(agent.payloads)
        try:
            await service.answer(MessageRequest(thread_id=a, message="问B"), tools_b)
        except ConversationNotFound:
            pass
        else:
            raise AssertionError("Foreign conversation accepted")
        assert len(agent.payloads) == before
    print("PASS: real conversation service uses per-user history; 40-turn lookback; foreign user rejected before model")


async def main():
    check_selection()
    await check_send_guard()
    await check_service_isolation()
    print("PASS: context budget checks complete; no external API calls")


if __name__ == "__main__":
    asyncio.run(main())
