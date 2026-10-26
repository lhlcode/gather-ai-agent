import re

BOOKING_PATTERN = re.compile(
    r"(?:请帮我|帮我|请)?\s*"
    r"(?P<verb>重新报名|重试报名|报名)\s*"
    r"活动\s*(?P<event_id>[1-9][0-9]{0,18})"
    r"[。！!]?"
)

def parse_booking_command(message: str) -> tuple[int, bool] | None:
    match = BOOKING_PATTERN.fullmatch(message.strip())
    if match is None:
        return None
    event_id = int(match.group("event_id"))
    if event_id > 9223372036854775807:
        return None
    return event_id, match.group("verb") == "重试报名"
