from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)

from assistant_api.identity_service import CurrentUser


class OrderSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")

    id: int = Field(gt=0)
    eventId: int = Field(gt=0)
    eventTitle: str = Field(min_length=1)
    status: Literal["UNPAID", "PAID", "CANCELLED", "EXPIRED"]
    expiresAtUtc: str = Field(min_length=1)


class MyOrdersResult(BaseModel):
    status: Literal["ok"] = "ok"
    source: Literal["GET /orders"] = "GET /orders"
    queried_at: str
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    truncated: bool
    orders: list[OrderSnapshot]

class BookingRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event_id: int = Field(gt=0, le=9223372036854775807)
    operation_id: str = Field(
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
    )


class BookingReceipt(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    operationId: str = Field(
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
    )
    orderId: int = Field(gt=0)
    eventId: int = Field(gt=0)
    status: Literal["UNPAID", "PAID", "CANCELLED", "EXPIRED"]
    replayed: bool


class BookingResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    status: Literal["created", "replayed", "rejected", "unknown"]
    operation_id: str = Field(
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
    )
    event_id: int = Field(gt=0)
    order_id: int | None = Field(default=None, gt=0)
    order_status: Literal[
        "UNPAID", "PAID", "CANCELLED", "EXPIRED"
    ] | None = None
    source: str
    checked_at: str
    message: str

    @model_validator(mode="after")
    def check_result(self):
        if self.status in {"created", "replayed"}:
            if self.order_id is None or self.order_status is None:
                raise ValueError("确认成功的操作必须包含订单凭据。")

            if self.status == "created" and self.order_status != "UNPAID":
                raise ValueError("新订单应为待支付状态。")

        elif self.order_id is not None or self.order_status is not None:
            raise ValueError("结果未确认时，不应返回成功凭据。")

        return self
ORDER_LIST = TypeAdapter(list[OrderSnapshot])
DISPLAY_LIMIT = 20


class UserToolError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class UserTools:
    current_user: CurrentUser
    client: httpx.AsyncClient = field(repr=False)
    access_token: str = field(repr=False)
    async def book_event(
        self,
        event_id: int,
        operation_id: str,
    ) -> BookingResult:
        try:
            request = BookingRequest(
                event_id=event_id,
                operation_id=operation_id,
            )
        except ValueError:
            raise UserToolError(
                "活动编号或操作编号不合法。",
                status_code=422,
            ) from None

        path = f"/events/{request.event_id}/booking-operations"

        def make_result(status, message, receipt=None):
            return BookingResult(
                status=status,
                operation_id=request.operation_id,
                event_id=request.event_id,
                order_id=receipt.orderId if receipt else None,
                order_status=receipt.status if receipt else None,
                source=f"POST {path}",
                checked_at=datetime.now(timezone.utc).isoformat(
                    timespec="milliseconds",
                ),
                message=message,
            )

        unknown_message = (
            "报名结果尚未确认。恢复请求时请继续使用操作编号"
            f"{request.operation_id}，不要换编号重试。"
        )

        try:
            response = await self.client.post(
                path,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Idempotency-Key": request.operation_id,
                },
            )
        except (httpx.TimeoutException, httpx.RequestError):
            return make_result("unknown", unknown_message)

        if response.status_code in {401, 403}:
            raise UserToolError(
                "登录凭证已失效或当前账户无权报名。",
                status_code=response.status_code,
            )

        if response.status_code == 409:
            return make_result(
                "rejected",
                "后端拒绝本次请求，请核对活动、已有有效订单"
                "或操作编号绑定的目标。",
            )

        if response.status_code not in {200, 201}:
            return make_result("unknown", unknown_message)

        try:
            receipt = BookingReceipt.model_validate(response.json())

            if (
                receipt.operationId != request.operation_id
                or receipt.eventId != request.event_id
            ):
                raise ValueError("返回凭据与请求不一致。")

            if response.status_code == 201:
                if receipt.replayed or receipt.status != "UNPAID":
                    raise ValueError("首次创建的返回不符合约定。")

            elif not receipt.replayed:
                raise ValueError("重放返回缺少重放标记。")

        except ValueError:
            return make_result(
                "unknown",
                "报名响应未通过校验。" + unknown_message,
            )

        if receipt.replayed:
            names = {
                "UNPAID": "待支付",
                "PAID": "已支付",
                "CANCELLED": "已取消",
                "EXPIRED": "已过期",
            }

            return make_result(
                "replayed",
                f"该操作已关联订单{receipt.orderId}，"
                f"本次查询状态为{names[receipt.status]}，"
                "没有再次创建订单。",
                receipt,
            )

        return make_result(
            "created",
            f"已创建待支付订单{receipt.orderId}，尚未支付。",
            receipt,
        )
    async def list_my_orders(self) -> MyOrdersResult:
        try:
            response = await self.client.get(
                "/orders",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                },
            )
        except httpx.TimeoutException:
            raise UserToolError(
                "订单查询超时，当前无法确定订单情况。",
                status_code=504,
            ) from None
        except httpx.RequestError:
            raise UserToolError(
                "订单查询服务暂时不可用。",
                status_code=503,
            ) from None

        if response.status_code == 401:
            raise UserToolError(
                "登录凭证无效或已过期，请重新登录。",
                status_code=401,
            )

        if response.status_code == 403:
            raise UserToolError(
                "当前账户无权执行订单查询。",
                status_code=403,
            )

        if response.status_code != 200:
            raise UserToolError(
                "订单接口返回异常，当前无法确定订单情况。",
                status_code=502,
            )

        try:
            orders = ORDER_LIST.validate_python(response.json())
        except ValueError:
            raise UserToolError(
                "订单接口的数据未通过校验。",
                status_code=502,
            ) from None

        # Java 当前按订单编号倒序返回。
        # 这里只向调用者提供前 20 条，避免历史消息无限增大。
        shown = orders[:DISPLAY_LIMIT]

        return MyOrdersResult(
            queried_at=datetime.now(timezone.utc).isoformat(
                timespec="milliseconds",
            ),
            total_count=len(orders),
            returned_count=len(shown),
            truncated=len(orders) > len(shown),
            orders=shown,
        )