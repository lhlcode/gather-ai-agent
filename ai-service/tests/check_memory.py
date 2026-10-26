"""记忆回归：临时 SQLite、模拟模型/Java，无外部模型调用。"""
import os
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assistant_api.chat_service import ChatService
from assistant_api.agent_service import AgentService, RoutePlan, DecompositionCheck
from assistant_api.booking_operation_store import BookingOperationStore
from assistant_api.context_budget import INPUT_BUDGET, MAX_SUMMARY_BUDGET, select_history
from assistant_api.conversation_service import (
    ConversationService, QuestionResolution, IntentCheck, RESOLVE_PROMPT, INTENT_PROMPT,
)
from assistant_api.conversation_store import ConversationStore, ConversationNotFound
from assistant_api.identity_service import CurrentUser, IdentityService
from assistant_api.memory_policy import effective_style, preference_command, STYLE_INSTRUCTIONS
from assistant_api.memory_routes import router as memory_router
from assistant_api.conversation_routes import router as chat_router
from assistant_api.memory_store import MemoryStore, MemoryIntegrityError, PreferenceUpdate
from assistant_api.rag_models import GroundedAnswer
from assistant_api.schemas import ChatResponse, MessageRequest, TokenUsage
from assistant_api.user_tools import UserTools


def response(thread, answer="测试答复"):
    return ChatResponse(status="answered", thread_id=thread, answer=answer,
                        claims=[], model_calls=0, usage=None)


def append(store, thread, user, message, answer="测试答复"):
    store.append_turn(thread, user, message, response(thread, answer))


def choose(turns, items):
    return select_history(turns, "活动怎么报名？", QuestionResolution, RESOLVE_PROMPT,
                          IntentCheck, INTENT_PROMPT, summary_items=items)


def check_store(folder):
    store = ConversationStore(Path(folder) / "store.sqlite3")
    memory = MemoryStore(store)
    a, b = store.create(7)["thread_id"], store.create(8)["thread_id"]
    for i in range(115):
        append(store, a, 7, f"A完整原话{i}：已支付订单不能直接取消。")
    append(store, a, 7, "长" * 161)
    append(store, b, 8, "B_ONLY")
    turns = store.get_history(a, 7, 200)["turns"]
    boundary = turns[-1]["turn_id"]
    summary = memory.refresh_summary(a, 7, boundary)
    assert summary.scanned_turns == 100 and len(summary.items) == 4
    sources = {t["turn_id"]: t["user_message"] for t in turns}
    assert all(q.quote == sources[q.source_turn] and q.source_turn < boundary for q in summary.items)
    assert "长" * 161 not in [q.quote for q in summary.items]
    assert MemoryStore(ConversationStore(store.path)).get_summary(a, 7) == summary
    for action in [memory.get_summary, memory.refresh_summary, memory.clear_summary]:
        try:
            action(a, 8)
        except ConversationNotFound:
            pass
        else:
            raise AssertionError("foreign thread allowed")
    # 改一个否定词，虽仍符合 JSON 格式，也必须被原文校验拒绝。
    with store.connection() as connection:
        corrupt = [q.model_dump() for q in summary.items]
        corrupt[0]["quote"] = corrupt[0]["quote"].replace("不能", "可以")
        connection.execute("UPDATE conversation_summaries SET items_json=? WHERE thread_id=?",
                           (json.dumps(corrupt), a))
    try:
        memory.get_summary(a, 7)
    except MemoryIntegrityError:
        pass
    else:
        raise AssertionError("modified quote accepted")
    memory.refresh_summary(a, 7, boundary)
    assert memory.get_summary(a, 7).items == summary.items
    # 外会话的真实原话也不能移植成当前会话摘要。
    foreign = store.get_history(b, 8, 1)["turns"][0]
    with store.connection() as connection:
        connection.execute("UPDATE conversation_summaries SET items_json=? WHERE thread_id=?",
                           (json.dumps([{"source_turn": foreign["turn_id"], "quote": "B_ONLY"}]), a))
    try:
        memory.get_summary(a, 7)
    except MemoryIntegrityError:
        pass
    else:
        raise AssertionError("foreign source accepted")
    memory.clear_summary(a, 7)
    assert memory.get_summary(a, 7).items == []
    assert len(store.get_history(a, 7, 200)["turns"]) == 116
    assert memory.refresh_summary(a, 7).items
    memory.set_preference(7, "concise")
    assert MemoryStore(store).get_preference(7).answer_style == "concise"
    assert memory.get_preference(8).answer_style is None
    memory.clear_preference(7)
    assert memory.get_preference(7).answer_style is None
    for payload in [{"answer_style": "不要校验"}, {"answer_style": "plain", "user_id": 8}]:
        try:
            PreferenceUpdate.model_validate(payload)
        except ValidationError:
            pass
        else:
            raise AssertionError("open preference field accepted")
    # 最近轮次不变，摘要只使用剩余预算；摘要和近期历史不重叠。
    recent = turns[-40:]
    baseline, base_stats = choose(recent, [])
    old = [{"source_turn": t["turn_id"], "quote": t["user_message"]} for t in turns[:4]]
    overlap = {"source_turn": baseline["recent_history"][0]["turn_id"], "quote": "不应重复"}
    context, stats = choose(recent, old + [overlap])
    assert context["recent_history"] == baseline["recent_history"]
    assert context["summary_quotes"] and overlap not in context["summary_quotes"]
    assert stats["summary_estimate"] <= MAX_SUMMARY_BUDGET
    assert max(stats["resolver_input_estimate"], stats["intent_reserved_input_estimate"]) <= INPUT_BUDGET
    too_long = [{**recent[-1], "response": {"status": "answered", "answer": "长" * 10000}}]
    context, _ = choose(too_long, old)
    assert context["latest_history_missing"] and context["summary_quotes"] == []
    print("PASS: source integrity, persistence, ownership, whole quotes, bounded scan and shared budget")


class RecordingAgent:
    def __init__(self):
        self.payloads, self.answers = [], []

    async def ask_json(self, schema, instruction, payload):
        self.payloads.append((schema, payload))
        data = ({"status": "ready", "standalone_question": payload["current_user_message"], "clarification": ""}
                if schema is QuestionResolution else {"faithful": True, "reason": "test"})
        return schema.model_validate(data), TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)

    async def answer(self, body, **kwargs):
        self.answers.append((body, kwargs))
        return response(body.thread_id)


async def check_conversation(folder):
    store = ConversationStore(Path(folder) / "conversation.sqlite3")
    memory, agent = MemoryStore(store), RecordingAgent()
    service = ConversationService(agent, store, memory)
    a, another, b = [store.create(uid)["thread_id"] for uid in [7, 7, 8]]
    tools = UserTools(CurrentUser(userId=7, username="a", role="USER"), None, "test-a")

    async def send(text, thread=a):
        return await service.answer(MessageRequest(thread_id=thread, message=text), tools)

    saved = await send("以后回答简洁一点")
    assert saved.model_calls == 0 and not agent.payloads
    await send("活动如何报名？", another)
    assert agent.answers[-1][1]["answer_style"] == "concise"
    await send("这次通俗解释：订单什么时候过期？", another)
    assert agent.answers[-1][1]["answer_style"] == "plain"
    assert memory.get_preference(7).answer_style == "concise"
    await send("这次详细解释：订单什么时候过期？", another)
    assert agent.answers[-1][1]["answer_style"] == "detailed"
    assert memory.get_preference(7).answer_style == "concise"
    await send("他说：以后请通俗解释", another)
    assert memory.get_preference(7).answer_style == "concise"
    before = len(agent.payloads)
    try:
        await send("以后请通俗解释", b)
    except ConversationNotFound:
        pass
    else:
        raise AssertionError("foreign preference write accepted")
    assert len(agent.payloads) == before and memory.get_preference(7).answer_style == "concise"
    assert (await send("查看我的偏好")).model_calls == 0
    await send("忘记回答偏好")
    assert memory.get_preference(7).answer_style is None
    for i in range(55):
        append(store, a, 7, f"A历史{i}：活动49的报名问题", "短回复")
    await send("活动什么时候可以报名？")
    payload = agent.payloads[-2][1]
    assert payload["summary_quotes"]
    recent_ids = {q["turn_id"] for q in payload["recent_history"]}
    assert all(q["source_turn"] < min(recent_ids) for q in payload["summary_quotes"])
    assert memory.get_summary(a, 7).items
    # 原始明确报名不读取偏好、不生成摘要、不调用追问模型。
    before = len(agent.payloads)
    await send("帮我报名活动49")
    assert len(agent.payloads) == before
    assert agent.answers[-1][1]["original_message"] == "帮我报名活动49"
    assert "answer_style" not in agent.answers[-1][1]
    print("PASS: explicit zero-model preferences, same-user cross-thread style, transient override and summary flow")


async def check_rag_style():
    text = "报名后须在15分钟内支付，超时订单过期。"
    retrieval = SimpleNamespace(search=lambda *args: {
        "source": "test", "index_version": "test", "chunks": [{"chunk_id": "C2", "text": text}],
    })
    service = ChatService(None, retrieval)
    calls, mode = [], {"bad_quote": False, "bad_review": False}

    async def fake(schema, instruction, payload):
        calls.append((schema, instruction, payload))
        if schema is GroundedAnswer:
            data = {"answerable": True, "claims": [{"text": text, "evidence": [{
                "chunk_id": "C2", "quote": "20分钟" if mode["bad_quote"] else text,
            }]}]}
        else:
            data = {"checks": [{"claim_index": 1, "verdict": "contradicted" if mode["bad_review"] else "supported", "reason": "test"}],
                    "matches_question": True, "reason": "test"}
        return schema.model_validate(data), TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)

    service.ask_json = fake
    body = MessageRequest(thread_id="test", message="多久支付？")
    for style in ["concise", "plain", "detailed"]:
        result = await service.answer(body, answer_style=style)
        assert result.status == "answered" and "15分钟" in result.answer
        assert STYLE_INSTRUCTIONS[style] in calls[-2][1]
        assert STYLE_INSTRUCTIONS[style] not in calls[-1][1]
    mode["bad_quote"] = True
    assert (await service.answer(body, answer_style="concise")).status == "blocked"
    mode.update(bad_quote=False, bad_review=True)
    assert (await service.answer(body, answer_style="plain")).status == "blocked"
    print("PASS: generation receives style; source quote and fact review still block invalid answers")


async def check_api(folder):
    store = ConversationStore(Path(folder) / "api.sqlite3")
    memory = MemoryStore(store)
    a, b = store.create(7)["thread_id"], store.create(8)["thread_id"]
    for i in range(15):
        append(store, a, 7, f"接口历史{i}")

    async def backend(request):
        auth = request.headers.get("Authorization")
        if auth not in {"Bearer test-a", "Bearer test-b"}:
            return httpx.Response(401)
        uid = 7 if auth == "Bearer test-a" else 8
        return httpx.Response(200, json={"userId": uid, "username": f"u{uid}", "role": "USER"})

    async with httpx.AsyncClient(base_url="https://backend.test", transport=httpx.MockTransport(backend)) as upstream:
        app = FastAPI()
        app.state.memory_store = memory
        app.state.identity_service = IdentityService(upstream)
        app.state.backend_client = upstream
        app.state.conversation_store = store
        app.state.conversation_service = ConversationService(RecordingAgent(), store, memory)
        app.include_router(memory_router)
        app.include_router(chat_router)
        async with httpx.AsyncClient(base_url="https://app.test", transport=httpx.ASGITransport(app=app)) as api:
            ah, bh = {"Authorization": "Bearer test-a"}, {"Authorization": "Bearer test-b"}
            assert (await api.get("/memory/preferences")).status_code == 401
            assert (await api.put("/memory/preferences", headers=ah, json={"answer_style": "concise"})).status_code == 200
            assert (await api.get("/memory/preferences", headers=bh)).json()["answer_style"] is None
            for data in [{"answer_style": "paid"}, {"answer_style": "plain", "user_id": 8}]:
                assert (await api.put("/memory/preferences", headers=ah, json=data)).status_code == 422
            for method, suffix in [("GET", ""), ("POST", "/refresh"), ("DELETE", "")]:
                assert (await api.request(method, f"/conversations/{a}/summary{suffix}", headers=bh)).status_code == 404
            refreshed = await api.post(f"/conversations/{a}/summary/refresh", headers=ah)
            assert refreshed.status_code == 200 and len(refreshed.json()["items"]) == 4
            read = await api.get(f"/conversations/{a}/summary", headers=ah)
            assert read.json() == refreshed.json()
            assert (await api.delete(f"/conversations/{a}/summary", headers=ah)).status_code == 200
            assert (await api.get(f"/conversations/{a}/summary", headers=ah)).json()["items"] == []
            assert (await api.delete("/memory/preferences", headers=ah)).json()["answer_style"] is None
            command = await api.post("/chat", headers=ah, json={"thread_id": a, "message": "以后请通俗解释"})
            assert command.status_code == 200 and command.json()["model_calls"] == 0
            assert (await api.get("/memory/preferences", headers=ah)).json()["answer_style"] == "plain"
    print("PASS: actual FastAPI routes, authentication, CRUD, closed schema and foreign-thread rejection")


async def check_graph_memory(folder):
    store = ConversationStore(Path(folder) / "graph.sqlite3")
    bookings = BookingOperationStore(Path(folder) / "bookings.sqlite3")
    thread = store.create(7)["thread_id"]
    for i in range(55):
        append(store, thread, 7, "帮我报名活动43")
    text = "须在15分钟内支付。"
    retrieval = SimpleNamespace(search=lambda *args: {
        "source": "test", "index_version": "test", "chunks": [{"chunk_id": "C2", "text": text}],
    })
    business_calls, generations, contexts = [], [], []

    class Business:
        descriptions = []

        async def call(self, name, args):
            business_calls.append((name, args))
            assert name == "get_event" and args == {"event_id": 43}
            return {"status": "found", "source": "test", "event": {
                "id": 43, "title": "测试", "availableQuota": 3, "totalQuota": 5,
            }}

    agent = AgentService(None, retrieval, Business(), bookings)

    async def fake(schema, instruction, payload):
        if schema is QuestionResolution:
            contexts.append(payload)
            question = payload["current_user_message"]
            data = {"status": "ready", "standalone_question": "报名活动43" if question == "活动43如何报名？" else question, "clarification": ""}
        elif schema is IntentCheck:
            data = {"faithful": True, "reason": "test"}
        elif schema is RoutePlan:
            question = payload["question"]
            if question == "报名活动43":
                data = {"route": "clarify", "clarification": "请明确说明。"}
            elif "名额" in question:
                data = {"route": "mixed", "event_id": 43, "rule_question": "多久支付？"}
            else:
                data = {"route": "rules"}
        elif schema is DecompositionCheck:
            data = {"faithful": True, "complete": True, "reason": "test"}
        elif schema is GroundedAnswer:
            generations.append(instruction)
            data = {"answerable": True, "claims": [{"text": text, "evidence": [{"chunk_id": "C2", "quote": text}]}]}
        else:
            data = {"checks": [{"claim_index": 1, "verdict": "supported", "reason": "test"}], "matches_question": True, "reason": "test"}
        return schema.model_validate(data), TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)

    agent.ask_json = fake
    memory = MemoryStore(store)
    service = ConversationService(agent, store, memory)
    tools = UserTools(CurrentUser(userId=7, username="test", role="USER"), None, "test-a")

    async def send(message):
        return await service.answer(MessageRequest(thread_id=thread, message=message), tools)

    guarded = await send("活动43如何报名？")
    assert contexts[-1]["summary_quotes"] and all(q["quote"] == "帮我报名活动43" for q in contexts[-1]["summary_quotes"])
    assert guarded.status == "clarify" and not business_calls
    assert bookings.recent(7, 20) == []
    await send("以后回答简洁一点")
    assert (await send("多久支付？")).status == "answered"
    assert STYLE_INSTRUCTIONS["concise"] in generations[-1]
    assert (await send("这次详细解释：活动43剩余名额和付款期限？")).status == "answered"
    assert STYLE_INSTRUCTIONS["detailed"] in generations[-1]
    assert memory.get_preference(7).answer_style == "concise"
    assert business_calls == [("get_event", {"event_id": 43})]
    print("PASS: real LangGraph rules/mixed style propagation; old summary plus model rewrite cannot authorize booking")


async def main():
    assert preference_command("他说：以后回答简洁一点") is None
    assert effective_style("这次简洁回答：付款期限？", "plain") == "concise"
    assert effective_style("这次详细解释：付款期限？", "concise") == "detailed"
    with tempfile.TemporaryDirectory(prefix="memory-lesson-") as folder:
        check_store(folder)
        await check_conversation(folder)
        await check_rag_style()
        await check_api(folder)
        await check_graph_memory(folder)
    print("PASS: all memory checks complete; no external model calls")


if __name__ == "__main__":
    asyncio.run(main())
