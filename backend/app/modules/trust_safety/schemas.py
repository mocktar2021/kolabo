"""Schemas for the trust and safety module."""
from datetime import datetime

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


class BlockIn(BaseModel):
    """The optional body on a block.

    reason_code is carried only when the block arrived through the combined
    block-and-report action, so the two rows can be read together later. A
    plain block from a profile menu sends no body at all, which is why every
    field here is optional and the endpoint accepts a missing body.
    """

    reason_code: str | None = None


class BlockOut(BaseModel):
    """One row of a blocked-accounts list.

    Carries a name and a face because the list has to be readable: "you
    blocked 4f3a9c21" is not something anybody can act on. Nothing else about
    the person travels, and never a phone number, for the reason
    app.core.identity gives.
    """

    user_id: str
    display_name: str | None
    avatar_url: str | None
    reason_code: str | None
    created_at: datetime
