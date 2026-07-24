"""Schemas for the trust and safety module."""
from pydantic import BaseModel, Field


class ReviewIn(BaseModel):
    escrow_id: str
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewOut(BaseModel):
    id: str
    reviewer_user_id: str
    reviewee_user_id: str
    stars: int
    comment: str | None
    revealed: bool


class PublicReview(BaseModel):
    reviewer_user_id: str
    stars: int
    comment: str | None


class UserReviewsOut(BaseModel):
    user_id: str
    average_stars: float | None
    count: int
    reviews: list[PublicReview]


class ReportIn(BaseModel):
    target_type: str
    target_id: str
    reason_code: str
    details: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    id: str
    target_type: str
    target_id: str
    reason_code: str
    status: str


class ResolveReportIn(BaseModel):
    decision: str  # reviewed or dismissed
