from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CurrentUser(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )

    userId: int = Field(gt=0)
    username: str = Field(min_length=1)
    role: Literal["USER", "ADMIN"]


class IdentityServiceError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class IdentityService:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def get_current_user(self, token: str) -> CurrentUser:
        try:
            response = await self.client.get(
                "/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                },
            )
        except httpx.TimeoutException:
            raise IdentityServiceError(
                "登录验证超时，请稍后重试。",
                status_code=504,
            ) from None
        except httpx.RequestError:
            raise IdentityServiceError(
                "登录验证服务暂时不可用。",
                status_code=503,
            ) from None

        if response.status_code == 401:
            raise IdentityServiceError(
                "登录凭证无效或已过期，请重新登录。",
                status_code=401,
            )

        if response.status_code == 403:
            raise IdentityServiceError(
                "当前用户无法访问身份接口。",
                status_code=403,
            )

        if response.status_code != 200:
            raise IdentityServiceError(
                "登录验证服务返回异常。",
                status_code=502,
            )

        try:
            return CurrentUser.model_validate(response.json())
        except (ValueError, ValidationError):
            raise IdentityServiceError(
                "登录验证服务返回的数据格式异常。",
                status_code=502,
            ) from None