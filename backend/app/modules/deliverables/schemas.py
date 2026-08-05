"""Schemas for the deliverables module."""
from datetime import datetime

from pydantic import BaseModel


class SubmissionIn(BaseModel):
    """What a creator hands in.

    Every bound worth stating is checked in the service rather than here, so
    the refusal names the RULE ("a submission needs a link or a file") instead
    of naming a field — the same call DisputeIn makes. What stays here is the
    shape.
    """

    contract_id: str
    link_url: str | None = None
    note: str | None = None
    media_ids: list[str] = []


class ReviewIn(BaseModel):
    """The brand's answer when it wants the work redone.

    `note` is typed as optional and required by the service, which is not a
    contradiction: a blank string passes a `str` field and would produce
    "changes requested: " with nothing after it. The service checks the
    stripped text and refuses with a sentence about why a reason is needed.
    """

    note: str | None = None


class SubmissionOut(BaseModel):
    id: str
    contract_id: str
    submitted_by_user_id: str
    link_url: str | None = None
    note: str | None = None
    status: str
    review_note: str | None = None
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    # Serving urls for the attached files, in the order they were attached —
    # the same /profiles/media/{id} shape every other surface uses.
    attachments: list[str] = []
