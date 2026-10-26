from typing import Literal

from mcp import Client
from pydantic import BaseModel, ConfigDict, Field, model_validator

from assistant_api.chat_service import ModelServiceError


class EventSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    id: int = Field(gt=0)
    title: str = Field(min_length=1)
    totalQuota: int = Field(ge=0)
    availableQuota: int = Field(ge=0)
    registrationStartAtUtc: str
    registrationEndAtUtc: str

    @model_validator(mode="after")
    def validate_quota(self):
        if self.availableQuota > self.totalQuota:
            raise ValueError("剩余名额超过总名额。")
        return self


class EventListResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    status: Literal["ok"]
    source: Literal["GET /events"]
    queried_at: str
    events: list[EventSnapshot]


class EventDetailResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    status: Literal["found", "not_found"]
    requested_event_id: int
    source: str
    queried_at: str
    event: EventSnapshot | None


class BusinessClient:
    def __init__(self, client: Client):
        self.client = client
        self.descriptions = []

    async def initialize(self):
        listed = await self.client.list_tools()
        allowed = {"list_events", "get_event"}

        self.descriptions = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in listed.tools
            if tool.name in allowed
        ]

        found = {
            tool["name"]
            for tool in self.descriptions
        }

        if found != allowed:
            raise RuntimeError("MCP 业务工具不完整，服务启动失败。")

    async def call(self, name, arguments):
        if name not in {"list_events", "get_event"}:
            raise ModelServiceError("不支持的业务工具。")

        try:
            result = await self.client.call_tool(
                name,
                arguments,
                read_timeout_seconds=20,
            )
        except Exception as error:
            print("MCP 调用失败：", type(error).__name__)
            raise ModelServiceError(
                "业务查询暂时不可用，请稍后再试。",
                status_code=503,
            ) from None

        if result.is_error:
            raise ModelServiceError(
                "业务工具查询失败，当前无法确定结果。",
                status_code=503,
            )

        data = result.structured_content

        if not isinstance(data, dict):
            raise ModelServiceError("业务工具没有返回结构化结果。")

        try:
            if name == "list_events":
                parsed = EventListResult.model_validate(data)
            else:
                parsed = EventDetailResult.model_validate(data)
                event_id = arguments["event_id"]

                if (
                    parsed.requested_event_id != event_id
                    or parsed.source != f"GET /events/{event_id}"
                ):
                    raise ValueError("查询目标不一致。")

                if parsed.status == "found":
                    if parsed.event is None or parsed.event.id != event_id:
                        raise ValueError("活动详情不一致。")
                elif parsed.event is not None:
                    raise ValueError("未找到活动时不应返回活动详情。")

        except ValueError:
            raise ModelServiceError(
                "业务工具返回的数据未通过校验。",
            ) from None

        return parsed.model_dump(mode="json")