from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from assistant_api.identity_service import (
    CurrentUser,
    IdentityService,
    IdentityServiceError,
)


router = APIRouter()

bearer = HTTPBearer(
    auto_error=False,
    description="填写 Java 登录接口返回的 accessToken。",
)


async def get_identity_service(
    request: Request,
) -> IdentityService:
    return request.app.state.identity_service


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
    service: Annotated[
        IdentityService,
        Depends(get_identity_service),
    ],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="请先登录，并携带 Bearer token。",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return await service.get_current_user(
            credentials.credentials,
        )
    except IdentityServiceError as error:
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
    "/identity/me",
    response_model=CurrentUser,
    tags=["登录身份"],
)
async def get_my_identity(
    current_user: Annotated[
        CurrentUser,
        Depends(get_current_user),
    ],
) -> CurrentUser:
    return current_user