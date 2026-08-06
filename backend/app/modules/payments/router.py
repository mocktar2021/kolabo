"""Epic G (KOL-7): Payments and Escrow."""
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin.router import get_current_admin
from app.modules.auth.deps import get_current_user_id
from app.modules.auth.models import User
from app.modules.payments import disputes, earnings, resolution, schemas, service, spend
from app.modules.payments.filters import StatementFilter

router = APIRouter()


def get_case_viewer(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> tuple[str, bool]:
    """Who is reading this case: one of the two parties, or an admin.

    Both are the same credential now — a bearer token — so this is one lookup
    rather than two branches. It used to accept an X-Admin-Id header as the
    admin half, which meant any string at all was enough to read anybody's
    dispute thread and every image filed as evidence in it. See
    app.modules.auth.admins for what replaced that and why.

    An admin who is ALSO a party to the case reads it as an admin, which is
    the wider of the two views and the right one to give somebody holding both
    claims.
    """
    user = db.query(User).filter(User.id == user_id).first()
    return user_id, bool(user and user.is_admin)


def get_statement_filter(
    year: int | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    campaign_id: str | None = Query(default=None),
    counterparty_id: str | None = Query(default=None),
) -> StatementFilter:
    """The four narrowings both statement screens understand.

    One dependency for both endpoints so the parameter names, the types and
    the semantics cannot drift between them: a brand and a creator filtering
    the same contract to the same month must be asking the same question.

    from_date and to_date are typed as dates, so an unparseable one is a 422
    from FastAPI before any of our code runs. That is the right answer for a
    malformed date — it is a client bug, not a rule the user broke, and it
    needs no sentence about what is allowed. An INVERTED range is not an error
    at all: it matches nothing and the screens answer zero, which is the
    honest reading of "between the 5th and the 1st".
    """
    return StatementFilter(
        year=year,
        from_date=from_date,
        to_date=to_date,
        campaign_id=campaign_id,
        counterparty_id=counterparty_id,
    )


@router.post("/escrow/fund", response_model=schemas.EscrowOut, status_code=status.HTTP_201_CREATED)
def fund_escrow(
    payload: schemas.FundIn,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Fund an escrow via Mobile Money for a fully signed contract. KOL-28."""
    return service.fund_escrow(db, business_user_id, payload.contract_id)


@router.get("/earnings", response_model=schemas.EarningsOut)
def my_earnings(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    statement_filter: StatementFilter = Depends(get_statement_filter),
):
    """What the caller has earned, is waiting on, and has frozen in a dispute.

    Three totals, each grouped by currency and each NET of commission — the
    gross is a number that never reaches a wallet, and quoting it would
    overstate every line. Disputed is kept separate from pending because
    frozen money is not money on its way.

    Optional filters: year, from_date, to_date (ISO dates, both inclusive),
    campaign_id and counterparty_id — the counterparty being the buyer on this
    side. EVERY ONE OF THEM NARROWS THE TOTALS AND THE LIST TOGETHER: a
    filtered statement under an all-time total is how a creator adds up the
    rows, gets a different number, and concludes the screen is lying. year and
    a date range compose as an intersection (see payments/filters.py), so
    year=2025 with a March window means March 2025 and a contradictory pair
    honestly answers zero.

    Creator side only. A business gets empty totals: what a buyer wants here
    is spend, which is a different question with the opposite sign, and it has
    its own endpoint at GET /payments/spend.
    """
    return earnings.my_earnings(db, user_id, filters=statement_filter)


@router.get("/spend", response_model=schemas.SpendOut)
def my_spend(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    statement_filter: StatementFilter = Depends(get_statement_filter),
):
    """What the caller has spent, has committed, and has had come back.

    The mirror of /payments/earnings and deliberately a separate endpoint,
    because the same words mean different things on the buyer's side: nothing
    here is net of commission (the platform's cut comes off the creator's
    release, not the brand's payment), refunds are a real line rather than
    money that never arrived, and "pending" is money already gone from the
    wallet rather than money on its way into one. One endpoint answering both
    would make every field mean two opposite things depending on who asked.

    Takes the same filters as /earnings, from the same dependency, with
    counterparty_id meaning the creator on this side.

    Buyer side only. A creator gets empty figures, for the same reason a
    business gets them from /earnings.
    """
    return spend.my_spend(db, user_id, filters=statement_filter)


@router.post("/escrow/{escrow_id}/release", response_model=schemas.EscrowOut)
def release_escrow(
    escrow_id: str,
    db: Session = Depends(get_db),
    business_user_id: str = Depends(get_current_user_id),
):
    """Business confirms delivery and releases the escrow, commission deducted. KOL-36."""
    return service.release_escrow(db, business_user_id, escrow_id)


@router.post(
    "/escrow/{escrow_id}/dispute",
    response_model=schemas.DisputeOut,
    status_code=status.HTTP_201_CREATED,
)
def dispute_escrow(
    escrow_id: str,
    payload: schemas.DisputeIn,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Open a dispute, which freezes the escrow and starts the response window.

    Requires a reason from the closed set, a written statement, and optionally
    the ids of images you uploaded as evidence. The other party is notified
    and gets the first word; only if they do not use it does an admin see the
    case. KOL-37.
    """
    return disputes.raise_dispute(db, actor_user_id, escrow_id, payload)


@router.post("/disputes/escalate")
def escalate_disputes(
    db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)
):
    """Send disputes whose response window has closed to the admin queue.

    Admin-triggered and on demand, mirroring /payments/escrow/auto-release and
    /campaigns/orders/expire. That makes three jobs with no scheduler behind
    them, and this is the one that keeps frozen money from staying frozen.
    """
    return {"escalated": disputes.escalate_stale_disputes(db)}


# Declared before /disputes/{dispute_id}: FastAPI matches in declaration
# order, so the literal path has to come first or "mine" is read as an id.
@router.get("/disputes/mine")
def my_disputes(
    db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)
):
    """Every dispute the caller is a party to, newest first."""
    return disputes.list_my_disputes(db, user_id)


@router.post("/disputes/{dispute_id}/messages", status_code=status.HTTP_201_CREATED)
def post_dispute_message(
    dispute_id: str,
    payload: schemas.DisputeMessageIn,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """Either party answers, with optional evidence.

    Open during the response window and after the case has queued: an admin
    reading it benefits from both sides continuing to explain.
    """
    return disputes.post_message(db, actor_user_id, dispute_id, payload)


@router.post("/disputes/{dispute_id}/withdraw", response_model=schemas.DisputeOut)
def withdraw_dispute(
    dispute_id: str,
    db: Session = Depends(get_db),
    actor_user_id: str = Depends(get_current_user_id),
):
    """The party who raised it drops it; the escrow goes back to held."""
    return disputes.withdraw_dispute(db, actor_user_id, dispute_id)


@router.get("/disputes/{dispute_id}")
def get_dispute(
    dispute_id: str,
    db: Session = Depends(get_db),
    viewer: tuple[str, bool] = Depends(get_case_viewer),
):
    """The whole case: claim, thread with evidence urls, and the escrow."""
    viewer_id, is_admin = viewer
    return disputes.get_dispute(db, viewer_id, is_admin, dispute_id)


@router.get("/escrow/by-contract/{contract_id}", response_model=schemas.EscrowOut)
def escrow_by_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Find the escrow for a contract, if it has been funded."""
    return service.get_escrow_by_contract(db, user_id, contract_id)


@router.get("/escrow/{escrow_id}", response_model=schemas.EscrowOut)
def get_escrow(
    escrow_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return service.get_escrow(db, user_id, escrow_id)


@router.post("/escrow/{escrow_id}/resolve", response_model=schemas.DisputeOut)
def resolve_dispute(
    escrow_id: str,
    payload: schemas.ResolveIn,
    db: Session = Depends(get_db),
    admin_id: str = Depends(get_current_admin),
):
    """Admin settles a disputed escrow by splitting it, logged. KOL-37.

    released_amount and refunded_amount must add up to the escrow exactly.
    Either may be zero. Commission is charged on the released part only.
    Returns the closed dispute with the settled escrow on it.
    """
    return resolution.resolve_dispute(db, admin_id, escrow_id, payload)


@router.post("/escrow/auto-release")
def run_auto_release(db: Session = Depends(get_db), admin_id: str = Depends(get_current_admin)):
    """Release escrows past their auto release deadline. Runs the timeout path for KOL-36."""
    count = service.run_due_auto_releases(db)
    return {"released": count}
