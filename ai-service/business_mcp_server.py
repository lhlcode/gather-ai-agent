import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="[Business MCP] %(message)s",
)

logger = logging.getLogger(__name__)

BACKEND_URL = "http://127.0.0.1:9091"


class EventData(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="ignore",
    )

    id: int = Field(gt=0)
    title: str = Field(min_length=1)
    totalQuota: int = Field(ge=0)
    availableQuota: int = Field(ge=0)
    registrationStartAtUtc: str
    registrationEndAtUtc: str

    @model_validator(mode="after")
    def check_quota(self):
        if self.availableQuota > self.totalQuota:
            raise ValueError("剩余名额不能超过总名额。")

        return self


EVENT_LIST = TypeAdapter(list[EventData])


def queried_at():
    return datetime.now(timezone.utc).isoformat(
        timespec="milliseconds",
    )


@asynccontextmanager
async def lifespan(server):
    async with httpx.AsyncClient(
        base_url=BACKEND_URL,
        timeout=httpx.Timeout(10.0, connect=3.0),
        follow_redirects=False,
    ) as client:
        logger.info("Java 业务客户端已初始化")
        yield {"http": client}

    logger.info("Java 业务客户端已关闭")


mcp = MCPServer(
    "booking-business",
    lifespan=lifespan,
)


async def request_backend(
    ctx: Context,
    path: str,
    allow_not_found: bool = False,
):
    client = ctx.request_context.lifespan_context["http"]

    try:
        response = await client.get(path)

        if allow_not_found and response.status_code == 404:
            return response

        response.raise_for_status()
        return response

    except httpx.TimeoutException:
        raise ToolError(
            "Java 业务接口请求超时，不能确定查询结果。"
        ) from None

    except httpx.RequestError:
        raise ToolError(
            "无法连接 Java 业务接口，不能确定查询结果。"
        ) from None

    except httpx.HTTPStatusError as error:
        logger.warning(
            "Java 接口返回错误，状态码：%s",
            error.response.status_code,
        )

        raise ToolError(
            "Java 业务接口返回错误，不能确定查询结果。"
        ) from None


@mcp.tool(structured_output=True)
async def list_events(ctx: Context) -> dict[str, Any]:
    """查询公开的已发布活动列表。

    返回接口提供的活动编号、标题、名额和报名时间。
    空列表只表示本次没有查到公开的已发布活动。
    是否报名成功，仍以后端报名接口的处理结果为准。
    """
    response = await request_backend(ctx, "/events")

    try:
        events = EVENT_LIST.validate_python(response.json())
    except ValueError:
        raise ToolError(
            "Java 活动列表的数据格式不符合约定。"
        ) from None

    return {
        "status": "ok",
        "source": "GET /events",
        "queried_at": queried_at(),
        "events": [
            event.model_dump(mode="json")
            for event in events
        ],
    }


@mcp.tool(structured_output=True)
async def get_event(
    event_id: Annotated[
        int,
        Field(
            strict=True,
            gt=0,
            le=9223372036854775807,
            description="活动编号，可以从 list_events 获取",
        ),
    ],
    ctx: Context,
) -> dict[str, Any]:
    """根据活动编号查询公开活动详情和接口返回的剩余名额。

    名额为零不代表活动不存在。
    not_found 表示未找到可查询的已发布活动，
    不能据此断言数据库中完全不存在该活动。
    接口失败不等于活动不存在。
    """
    path = f"/events/{event_id}"

    response = await request_backend(
        ctx,
        path,
        allow_not_found=True,
    )

    if response.status_code == 404:
        return {
            "status": "not_found",
            "requested_event_id": event_id,
            "source": f"GET {path}",
            "queried_at": queried_at(),
            "event": None,
            "message": "未找到可查询的已发布活动。",
        }

    try:
        event = EventData.model_validate(response.json())
    except ValueError:
        raise ToolError(
            "Java 活动详情的数据格式不符合约定。"
        ) from None

    if event.id != event_id:
        raise ToolError(
            "Java 返回的活动编号与请求不一致。"
        )

    return {
        "status": "found",
        "requested_event_id": event_id,
        "source": f"GET {path}",
        "queried_at": queried_at(),
        "event": event.model_dump(mode="json"),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
