from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["基础"])
def health() -> dict[str, str]:
    return {"status": "ok"}
