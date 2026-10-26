from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )


class Evidence(StrictModel):
    chunk_id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=350)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=400)
    evidence: list[Evidence] = Field(min_length=1, max_length=3)


class GroundedAnswer(StrictModel):
    answerable: bool
    claims: list[Claim] = Field(max_length=3)


class ClaimCheck(StrictModel):
    claim_index: int = Field(ge=1, le=3)
    verdict: Literal[
        "supported",
        "contradicted",
        "insufficient",
    ]
    reason: str = Field(min_length=1, max_length=200)


class AnswerReview(StrictModel):
    checks: list[ClaimCheck] = Field(max_length=3)
    matches_question: bool
    reason: str = Field(min_length=1, max_length=200)


def validate_quotes(draft, context):
    if not draft.answerable:
        return not draft.claims

    if not draft.claims:
        return False

    for claim in draft.claims:
        if not claim.text.strip():
            return False

        for evidence in claim.evidence:
            if evidence.chunk_id not in context:
                return False

            quote = evidence.quote.strip()
            if not quote or quote not in context[evidence.chunk_id]:
                return False

    return True


def review_passed(review, claim_count):
    expected = list(range(1, claim_count + 1))
    actual = sorted(
        check.claim_index
        for check in review.checks
    )

    # 每条结论必须恰好检查一次。
    if actual != expected:
        return False

    return (
        review.matches_question
        and all(
            check.verdict == "supported"
            for check in review.checks
        )
    )