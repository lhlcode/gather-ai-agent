from datetime import datetime
from typing import Literal

from assistant_api.chat_service import ModelServiceError

EventFilter = Literal["all", "not_ended", "open"]
PREVIEW_LIMIT = 3


def aware_time(value):
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("missing timezone")
        return instant
    except (AttributeError, TypeError, ValueError):
        raise ModelServiceError("活动时间数据异常，暂时无法判断报名状态。") from None


def prepare_event_list(data, event_filter: EventFilter):
    events = data["events"]
    if event_filter != "all":
        now = aware_time(data["queried_at"])
        selected = []
        for event in events:
            start = aware_time(event["registrationStartAtUtc"])
            end = aware_time(event["registrationEndAtUtc"])
            if start >= end:
                raise ModelServiceError("活动报名时间范围异常。")
            if end > now and (
                event_filter == "not_ended"
                or (start <= now and event["availableQuota"] > 0)
            ):
                selected.append(event)
        events = selected

    label = {"all": "已发布", "not_ended": "报名未截止", "open": "当前可报名"}[event_filter]
    if not events:
        answer = f"暂时没有{label}的活动。"
    else:
        lines = [f"• {event['title']}（活动{event['id']}），剩余{event['availableQuota']}个名额。"
                 for event in events[:PREVIEW_LIMIT]]
        answer = f"找到{len(events)}场{label}的活动：\n" + "\n".join(lines)
        if len(events) > PREVIEW_LIMIT:
            answer += f"\n还有{len(events) - PREVIEW_LIMIT}场，可展开查看。"
    return {
        **data,
        "event_filter": event_filter,
        "total_count": len(events),
        "events": events,
    }, answer
