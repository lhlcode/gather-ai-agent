import sqlite3
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from assistant_api.conversation_store import ConversationNotFound
from assistant_api.identity_routes import get_current_user
from assistant_api.identity_service import CurrentUser
from assistant_api.memory_store import (
    MemoryIntegrityError,
    MemoryStore,
    PreferenceUpdate,
    PreferenceView,
    SummaryView,
)

router = APIRouter(tags=["记忆"])
User = Annotated[CurrentUser, Depends(get_current_user)]


async def get_memory(request: Request) -> MemoryStore:
    return request.app.state.memory_store


Memory = Annotated[MemoryStore, Depends(get_memory)]
ThreadId = Annotated[str, Path(min_length=1, max_length=64)]


def memory_call(action: Callable):
    try:
        return action()
    except ConversationNotFound:
        raise HTTPException(404, "会话不存在或不可访问。") from None
    except MemoryIntegrityError as error:
        raise HTTPException(409, str(error)) from None
    except sqlite3.Error:
        raise HTTPException(503, "记忆存储暂时不可用。") from None


@router.get("/memory/preferences", response_model=PreferenceView)
def get_preferences(user: User, memory: Memory):
    return memory_call(lambda: memory.get_preference(user.userId))


@router.put("/memory/preferences", response_model=PreferenceView)
def set_preferences(body: PreferenceUpdate, user: User, memory: Memory):
    return memory_call(
        lambda: memory.set_preference(user.userId, body.answer_style)
    )


@router.delete("/memory/preferences", response_model=PreferenceView)
def clear_preferences(user: User, memory: Memory):
    return memory_call(lambda: memory.clear_preference(user.userId))


@router.get("/conversations/{thread_id}/summary", response_model=SummaryView)
def get_summary(thread_id: ThreadId, user: User, memory: Memory):
    return memory_call(lambda: memory.get_summary(thread_id, user.userId))


@router.post(
    "/conversations/{thread_id}/summary/refresh",
    response_model=SummaryView,
)
def refresh_summary(thread_id: ThreadId, user: User, memory: Memory):
    return memory_call(lambda: memory.refresh_summary(thread_id, user.userId))


@router.delete("/conversations/{thread_id}/summary")
def clear_summary(thread_id: ThreadId, user: User, memory: Memory):
    memory_call(lambda: memory.clear_summary(thread_id, user.userId))
    return {"status": "cleared"}
