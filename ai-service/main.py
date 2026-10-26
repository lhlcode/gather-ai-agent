import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from mcp import Client, StdioServerParameters
from openai import AsyncOpenAI

from assistant_api.agent_service import AgentService
from assistant_api.business_client import BusinessClient
from assistant_api.config import DEEPSEEK_BASE_URL, load_api_key
from assistant_api.conversation_routes import (
    router as conversation_router,
)
from assistant_api.conversation_service import ConversationService
from assistant_api.conversation_store import ConversationStore
from assistant_api.identity_routes import router as identity_router
from assistant_api.identity_service import IdentityService
from assistant_api.retrieval_routes import router as retrieval_router
from assistant_api.retrieval_service import RetrievalService
from assistant_api.routes import router
from assistant_api.memory_store import MemoryStore
from assistant_api.memory_routes import router as memory_router
from assistant_api.user_tool_routes import router as user_tool_router
from assistant_api.booking_operation_store import BookingOperationStore
SERVER_PATH = Path(__file__).resolve().parent / "business_mcp_server.py"


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_key = load_api_key()
    conversation_store = ConversationStore()
    memory_store = MemoryStore(conversation_store)
    retrieval_service = RetrievalService()
    booking_store = BookingOperationStore()
    server = StdioServerParameters(
        command=sys.executable,
        args=["-X", "utf8", str(SERVER_PATH)],
    )

    try:
        async with (
            AsyncOpenAI(
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=60.0,
                max_retries=0,
            ) as model_client,
            httpx.AsyncClient(
                base_url="http://127.0.0.1:9091",
                timeout=httpx.Timeout(10.0, connect=3.0),
                follow_redirects=False,
            ) as backend_client,
        ):
            async with Client(server) as mcp_client:
                business = BusinessClient(mcp_client)
                await business.initialize()

                agent_service = AgentService(
                    model_client,
                    retrieval_service,
                    business,
                    booking_store,
                )

                app.state.conversation_store = conversation_store
                app.state.conversation_service = ConversationService(
                    agent_service,
                    conversation_store,
                    memory_store,
                )
                app.state.memory_store = memory_store
                app.state.retrieval_service = retrieval_service
                app.state.booking_operation_store = booking_store
                app.state.identity_service = IdentityService(
                    backend_client,
                )
                app.state.backend_client = backend_client

                print("Agent、RAG、MCP 和登录身份服务已初始化。")
                yield
    finally:
        retrieval_service.close()
        print("知识索引连接已关闭。")


app = FastAPI(
    title="活动报名 AI 助手",
    version="0.9.0",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(retrieval_router)
app.include_router(conversation_router)
app.include_router(identity_router)
app.include_router(user_tool_router)
app.include_router(memory_router)
