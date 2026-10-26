"""活动筛选、简短展示、真实图路由的模拟回归；不调用外部模型。"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

os.environ["LANGSMITH_TRACING"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assistant_api.agent_service import AgentService, RoutePlan
from assistant_api.booking_operation_store import BookingOperationStore
from assistant_api.chat_service import ModelServiceError
from assistant_api.event_listing import prepare_event_list
from assistant_api.schemas import MessageRequest, TokenUsage

NOW = "2026-10-26T08:00:00+00:00"


def event(number, start="2026-10-25T08:00:00Z", end="2026-10-27T08:00:00Z", quota=3):
    return {"id": number, "title": f"活动{number}", "totalQuota": 3,
            "availableQuota": quota, "registrationStartAtUtc": start, "registrationEndAtUtc": end}


DATA = {"source": "GET /events", "status": "ok", "queried_at": NOW, "events": [
    event(1), event(2, end=NOW), event(3, end="2026-10-26T07:00:00Z"),
    event(4, start="2026-10-27T08:00:00Z", end="2026-10-28T08:00:00Z"),
    event(5, quota=0), event(6, start=NOW),
]}


def check_filters():
    data, answer = prepare_event_list(DATA, "not_ended")
    assert [e["id"] for e in data["events"]] == [1, 4, 5, 6]
    assert data["total_count"] == 4 and data["event_filter"] == "not_ended"
    assert "还有1场" in answer and answer.count("•") == 3
    assert "活动2" not in answer and "活动3" not in answer
    assert len(DATA["events"]) == 6
    data, answer = prepare_event_list(DATA, "open")
    assert [e["id"] for e in data["events"]] == [1, 6]
    assert "当前可报名" in answer
    data, answer = prepare_event_list(DATA, "all")
    assert len(data["events"]) == 6 and answer.count("•") == 3
    data, answer = prepare_event_list({**DATA, "events": []}, "not_ended")
    assert data["events"] == [] and "暂时没有" in answer
    for bad in ["2026-10-26T08:00:00", "not a date", None]:
        try:
            prepare_event_list({**DATA, "queried_at": bad}, "not_ended")
        except ModelServiceError:
            pass
        else:
            raise AssertionError("ambiguous time accepted")
    _, _ = prepare_event_list({**DATA, "queried_at": "2026-10-26T16:00:00+08:00"}, "open")
    print("PASS: end boundary, future starts, sold-out distinction, timezones, invalid time, complete data plus 3-item preview")


async def check_graph():
    class Business:
        descriptions = []

        async def call(self, name, args):
            assert name == "list_events" and args == {}
            return DATA

    with tempfile.TemporaryDirectory() as folder:
        service = AgentService(None, None, Business(), BookingOperationStore(Path(folder) / "op.sqlite3"))
        async def mock(schema, prompt, payload):
            assert schema is RoutePlan
            assert "没过期" in prompt and "event_filter" in prompt
            return RoutePlan(route="list_events", event_filter="not_ended"), TokenUsage(input_tokens=1, output_tokens=1, total_tokens=2)
        service.ask_json = mock
        result = await service.answer(MessageRequest(thread_id="test", message="没过期的活动发出来"))
        assert [e["id"] for e in result.tool_results[0]["events"]] == [1, 4, 5, 6]
        assert result.model_calls == 1 and result.answer.count("•") == 3
        print("PASS: actual compiled LangGraph carries filter into deterministic event selection")


if __name__ == "__main__":
    check_filters()
    asyncio.run(check_graph())
