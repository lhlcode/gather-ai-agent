import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters
from mcp.types import TextContent


SERVER_PATH = (
    Path(__file__).resolve().parent
    / "business_mcp_server.py"
)


class ToolCheckError(RuntimeError):
    """已知的工具失败，在退出 MCP 连接前处理。"""


def show_result(label, result):
    print(f"\n===== {label} =====")

    if result.is_error:
        for block in result.content:
            if isinstance(block, TextContent):
                print(block.text)

        raise ToolCheckError("MCP 业务工具执行失败。")

    data = result.structured_content

    if not isinstance(data, dict):
        raise ToolCheckError("没有收到预期的结构化工具结果。")

    print(json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ))

    return data


async def check_tools(client, requested_event_id):
    listed = await client.list_tools()

    print("发现业务工具：")
    for tool in listed.tools:
        print("-", tool.name)

    result = await client.call_tool(
        "list_events",
        {},
        read_timeout_seconds=20,
    )

    data = show_result("真实活动列表", result)

    if requested_event_id is not None:
        event_id = requested_event_id
    elif data["events"]:
        # 使用真实返回的编号，不假设活动101一定存在。
        event_id = data["events"][0]["id"]
    else:
        print("\n列表为空，本次跳过详情查询。")
        return

    result = await client.call_tool(
        "get_event",
        {"event_id": event_id},
        read_timeout_seconds=20,
    )

    show_result("真实活动详情", result)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", type=int)
    args = parser.parse_args()

    server = StdioServerParameters(
        command=sys.executable,
        args=["-X", "utf8", str(SERVER_PATH)],
    )

    async with Client(server) as client:
        try:
            await check_tools(client, args.event_id)
        except ToolCheckError as error:
            # 先处理已知失败，再正常退出连接，避免被任务组层层包装。
            print(f"\n检查未通过：{error}")
            return 1

    print("\n业务 MCP 查询检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
