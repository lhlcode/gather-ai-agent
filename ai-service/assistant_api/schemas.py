from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from assistant_api.rag_models import Claim


class MessageRequest(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    thread_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    operation_id: str | None = Field(
        default=None,
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
    )


class MessageResponse(BaseModel):
    status: Literal["received"]
    thread_id: str
    message: str
    character_count: int


class TokenUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class ChatResponse(BaseModel):
    status: Literal[
        "answered",
        "insufficient",
        "blocked",
        "clarify",
        "partial",
        "unknown",
    ]
    thread_id: str
    answer: str
    claims: list[Claim]

    source: str | None = None
    index_version: str | None = None
    resolved_question: str | None = None
    tool_results: list[dict[str, Any]] = Field(default_factory=list)

    part_statuses: dict[str, str] = Field(default_factory=dict)

    model_calls: int = Field(ge=0)
    usage: TokenUsage | None

class EventResponse(BaseModel):
    source: Literal["demo"] = "demo"
    id: int
    title: str
    available_quota: int = Field(ge=0)
