import sqlite3
from typing import Annotated
from assistant_api.user_tool_routes import get_user_tools
from assistant_api.user_tools import UserTools
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
)
from pydantic import BaseModel

from assistant_api.chat_service import ModelServiceError
from assistant_api.conversation_service import ConversationService
from assistant_api.conversation_store import (
    ConversationNotFound,
    ConversationStore,
)
from assistant_api.identity_routes import get_current_user
from assistant_api.identity_service import CurrentUser
from assistant_api.schemas import ChatResponse, MessageRequest


router = APIRouter()


class ConversationCreated(BaseModel):
    thread_id: str
    created_at: str


class ConversationTurn(BaseModel):
    turn_id: int
    user_message: str
    response: ChatResponse
    created_at: str


class ConversationHistory(BaseModel):
    thread_id: str
    turns: list[ConversationTurn]


async def get_store(request: Request) -> ConversationStore:
    return request.app.state.conversation_store


async def get_service(request: Request) -> ConversationService:
    return request.app.state.conversation_service


@router.post(
    "/conversations",
    response_model=ConversationCreated,
    status_code=201,
    tags=["会话"],
)
def create_conversation(
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    store: Annotated[
        ConversationStore,
        Depends(get_store),
    ],
) -> ConversationCreated:
    try:
        return ConversationCreated.model_validate(
            store.create(current_user.userId),
        )
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="会话存储暂时不可用。",
        ) from None


@router.get(
    "/conversations/{thread_id}/history",
    response_model=ConversationHistory,
    tags=["会话"],
)
def get_history(
    thread_id: Annotated[
        str,
        Path(min_length=1, max_length=64),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    store: Annotated[
        ConversationStore,
        Depends(get_store),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationHistory:
    try:
        return ConversationHistory.model_validate(
            store.get_history(
                thread_id,
                current_user.userId,
                limit,
            ),
        )
    except ConversationNotFound:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或不可访问。",
        ) from None
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="会话存储暂时不可用。",
        ) from None

@router.post(
    "/chat",
    response_model=ChatResponse,
    tags=["聊天"],
)
async def chat(
    body: MessageRequest,
    user_tools: Annotated[
        UserTools,
        Depends(get_user_tools),
    ],
    service: Annotated[
        ConversationService,
        Depends(get_service),
    ],
) -> ChatResponse:
    try:
        return await service.answer(
            body,
            user_tools,
        )
    except ConversationNotFound:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或不可访问。",
        ) from None
    except ModelServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
            headers=(
                {"WWW-Authenticate": "Bearer"}
                if error.status_code == 401
                else None
            ),
        ) from None
    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="会话存储暂时不可用。",
        ) from None