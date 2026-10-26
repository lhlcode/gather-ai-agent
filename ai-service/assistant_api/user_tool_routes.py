from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from assistant_api.identity_routes import bearer, get_current_user
from assistant_api.identity_service import CurrentUser
from assistant_api.user_tools import (
    BookingRequest,
    BookingResult,
    MyOrdersResult,
    UserToolError,
    UserTools,
)
import sqlite3

from fastapi import Query
from starlette.concurrency import run_in_threadpool

from assistant_api.booking_operation_store import (
    BookingOperationRecord,
    BookingOperationStore,
    BookingTargetConflict,
)
router = APIRouter()

async def get_booking_store(
    request: Request,
) -> BookingOperationStore:
    return request.app.state.booking_operation_store
async def get_user_tools(
    request: Request,
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
) -> UserTools:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="请先登录。",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserTools(
        current_user=current_user,
        client=request.app.state.backend_client,
        access_token=credentials.credentials,
    )

@router.get(
    "/tools/my-orders",
    response_model=MyOrdersResult,
    tags=["个人业务工具"],
)
async def get_my_orders(
    tools: Annotated[UserTools, Depends(get_user_tools)],
) -> MyOrdersResult:
    try:
        return await tools.list_my_orders()
    except UserToolError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
            headers=(
                {"WWW-Authenticate": "Bearer"}
                if error.status_code == 401
                else None
            ),
        ) from None

@router.post(
    "/tools/bookings",
    response_model=BookingResult,
    tags=["个人业务工具"],
)
async def create_booking(
    body: BookingRequest,
    tools: Annotated[UserTools, Depends(get_user_tools)],
    store: Annotated[
        BookingOperationStore,
        Depends(get_booking_store),
    ],
) -> BookingResult:
    try:
        # 先提交本地操作记录，再请求 Java。
        await run_in_threadpool(
            store.register,
            tools.current_user.userId,
            body,
        )

        return await tools.book_event(
            body.event_id,
            body.operation_id,
        )

    except BookingTargetConflict:
        raise HTTPException(
            status_code=409,
            detail="同一操作编号不能更换活动。",
        ) from None

    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="操作记录暂时不可用，请保留并复用原操作编号。",
        ) from None

    except UserToolError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
            headers=(
                {"WWW-Authenticate": "Bearer"}
                if error.status_code == 401
                else None
            ),
        ) from None


@router.get(
    "/tools/booking-operations",
    response_model=list[BookingOperationRecord],
    tags=["个人业务工具"],
)
def list_booking_operations(
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
    store: Annotated[
        BookingOperationStore,
        Depends(get_booking_store),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    try:
        return store.recent(current_user.userId, limit)

    except sqlite3.Error:
        raise HTTPException(
            status_code=503,
            detail="操作记录暂时不可用。",
        ) from None
