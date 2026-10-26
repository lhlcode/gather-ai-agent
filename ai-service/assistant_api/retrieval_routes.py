from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from assistant_api.retrieval_service import RetrievalService


router = APIRouter(tags=["知识检索"])


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=2, ge=1, le=3)


class RetrievedChunk(BaseModel):
    chunk_id: str
    title: str
    text: str
    rerank_score: float


class RetrievalResponse(BaseModel):
    source: str
    index_version: str
    device: str
    chunks: list[RetrievedChunk]


async def get_retrieval_service(request: Request) -> RetrievalService:
    return request.app.state.retrieval_service


@router.post("/retrieval", response_model=RetrievalResponse)
def retrieve(
    body: RetrievalRequest,
    service: Annotated[
        RetrievalService,
        Depends(get_retrieval_service),
    ],
) -> RetrievalResponse:
    try:
        result = service.search(body.question, body.top_k)
        return RetrievalResponse.model_validate(result)
    except Exception as error:
        print("知识检索失败，异常类型：", type(error).__name__)

        raise HTTPException(
            status_code=503,
            detail="知识检索暂时不可用。",
        ) from None