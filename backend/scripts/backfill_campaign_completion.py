"""One-off: finish the briefs that finished before `completed` existed.

WHY THIS EXISTS. #123 gave a campaign a terminal `completed` status and a hook,
campaigns.completion.maybe_complete_campaign, called from every place a
contract reaches an ending — an escrow released or refunded, a contract
cancelled, a dispute resolved. THE HOOK IS PROSPECTIVE ONLY: it runs when an
ending HAPPENS, and every ending that happened before it shipped happened with
nothing watching. Those briefs are still `published` — still on the board,
still accepting proposals, still able to invite a creator to price work that
was delivered and paid for months ago — and nothing will ever move them,
because the events that would have moved them are in the past.

So this walks the published campaigns once and puts each one that already
satisfies the completion rule through the same code path a live ending would
have taken. It is a BACKFILL AND NOT A REPAIR: it deletes nothing, sets no
status by hand, and re-derives no rule. Every number it reports and every row
it writes comes from campaigns.completion.

DELETE THIS FILE ONCE IT HAS RUN. A campaign that finishes from now on needs no
backfill — the hook fires on its ending by itself, which was the point of #123
— so a second run finds nothing. Left in the tree this reads like maintenance
somebody is supposed to run on a schedule, and it is not that.

DRY RUN IS THE DEFAULT; --apply is required to write anything. The other shape
— mutate first, then decide whether to keep it — is not available here even in
principle, and it is worth being explicit about why so nobody tries it later:
maybe_complete_campaign COMMITS, deliberately, because its callers have already
committed the ending it reacts to. Wrapping it in a transaction and rolling
back would not undo it. So the dry run never calls it. It asks completion's
predicate and completion's own read helpers instead, which are pure reads.

RUN IT from deploy/, the directory holding docker-compose.prod.yml:

    docker compose -f docker-compose.prod.yml exec backend \\
        python scripts/backfill_campaign_completion.py

    docker compose -f docker-compose.prod.yml exec backend \\
        python scripts/backfill_campaign_completion.py --apply

Re-running is safe. maybe_complete_campaign is idempotent and moves a campaign
only out of PUBLISHED, so a second --apply finds no candidates and writes
nothing. Exit status is 0 on success — including a run with nothing to do — and
non-zero if anything fails or a candidate unexpectedly refuses to move.
"""
import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

# `python scripts/backfill_campaign_completion.py` puts THIS directory on
# sys.path, not the working directory, so `import app` fails from here even
# though the process starts in /app where the app package sits. The parent of
# scripts/ is that tree (the image copies backend/ to /app). Hence the import
# of anything under `app` comes after this line rather than with the others.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal, import_all_models  # noqa: E402
from app.modules.campaigns import completion, models  # noqa: E402

# How many non-qualifying published campaigns to name before summarising the
# rest. They are listed at all so the output records what was CONSIDERED and
# not only what was chosen; past a screenful that stops being readable, and
# this output is meant to be pasted somewhere as the record of the run.
SKIP_PREVIEW = 20


@dataclass
class Survey:
    """One campaign as this script reads it. Nothing here writes anything."""

    id: str
    title: str
    status: str
    is_direct: bool
    contract_statuses: list[str]
    escrow_statuses: list[str | None]
    live_chains: int
    open_invitations: int
    completed: bool

    @property
    def notifications(self) -> int:
        """How many creators get told, if this campaign completes.

        One per live chain: close_open_offers sends exactly one "this brief has
        been filled" message per chain it rejects, and the completion path
        passes tell_creators=True (the cancellation path is the one that passes
        False). Derived rather than counted separately so the two numbers in
        the report cannot drift apart from each other.
        """
        return self.live_chains


def published_ids(db: Session) -> list[str]:
    """The campaigns this run may touch, oldest first.

    PUBLISHED ONLY, and this filter is the most important line in the file. A
    `cancelled` brief can have ended contracts and settled escrows under it and
    would satisfy the predicate, and #123 decided ON PURPOSE that cancelled
    stays cancelled: it is a brief that was called off, not one that finished,
    and overwriting it here would destroy that distinction permanently for the
    handful of rows this touches. A `draft` has shown nobody anything.

    maybe_complete_campaign refuses both as well, so this is the outer of two
    locks rather than the only one — but the dry run has to agree with the
    apply run about what a candidate is, and the dry run does not call it.
    """
    return [
        row[0]
        for row in db.query(models.Campaign.id)
        .filter(models.Campaign.status == models.PUBLISHED)
        .order_by(models.Campaign.created_at)
        .all()
    ]


def survey(db: Session, campaign_id: str) -> Survey | None:
    """Read-only picture of one campaign and of what completing it would touch.

    THE COMPLETION RULE IS NOT RESTATED HERE. `completed` below is
    completion.campaign_is_completed, called directly, and the counts come from
    completion's own read helpers — so the rows this reports are the rows
    close_open_offers would actually write. Those helpers are underscore
    private to that module and this reaches past that on purpose: a one-off
    that re-implemented their two queries could report a number the cascade
    then disagreed with, and a number that disagrees with what happened is the
    one thing this output must never produce.

    The open-invitation count is the exception, because completion has no
    helper for it — the query below is close_open_offers' own second query with
    .count() in place of .all(), down to reading models.INVITED rather than a
    string, so the same rows are counted that would be withdrawn.

    Returns None for a campaign that is not there, which only happens if a row
    is deleted between the survey and the re-read after --apply.
    """
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if campaign is None:
        return None

    endings = completion._contract_endings(db, campaign.id)
    live_chains = [
        proposal
        for proposal in completion._live_versions(db, campaign.id)
        if proposal.status == models.SUBMITTED
    ]
    open_invitations = (
        db.query(models.CampaignInvitation)
        .filter(
            models.CampaignInvitation.campaign_id == campaign.id,
            models.CampaignInvitation.status == models.INVITED,
        )
        .count()
    )
    return Survey(
        id=campaign.id,
        title=campaign.title,
        status=campaign.status,
        is_direct=campaign.is_direct,
        contract_statuses=[contract_status for contract_status, _escrow in endings],
        escrow_statuses=[escrow_status for _contract, escrow_status in endings],
        live_chains=len(live_chains),
        open_invitations=open_invitations,
        completed=completion.campaign_is_completed(db, campaign.id),
    )


def _join(values: list) -> str:
    """A status list for the report. NULL escrow is spelled out.

    "unfunded" rather than "None", because a null escrow is a real state with a
    meaning — nobody has paid into that contract — and printing it as None
    invites the reader to think the field failed to load.
    """
    if not values:
        return "none"
    return ", ".join("unfunded" if value is None else str(value) for value in values)


def _print_candidate(item: Survey) -> None:
    print(f"  {item.id}  {item.title}")
    print(f"    status              {item.status}")
    print(f"    direct order        {'yes' if item.is_direct else 'no'}")
    print(f"    contracts           {len(item.contract_statuses)}")
    print(f"    contract statuses   {_join(item.contract_statuses)}")
    print(f"    escrow statuses     {_join(item.escrow_statuses)}")
    print("    predicate holds     yes")
    print(f"    would close         {item.live_chains} live proposal chain(s) -> rejected")
    print(f"    would withdraw      {item.open_invitations} open invitation(s)")
    print(f"    would notify        {item.notifications} creator(s)")


def _print_skipped(skipped: list[Survey]) -> None:
    if not skipped:
        return
    print(f"Published campaigns the predicate does not hold for: {len(skipped)}")
    for item in skipped[:SKIP_PREVIEW]:
        print(
            f"  {item.id}  {item.title}"
            f"  (contracts {len(item.contract_statuses)}, escrows {_join(item.escrow_statuses)})"
        )
    if len(skipped) > SKIP_PREVIEW:
        print(f"  ... and {len(skipped) - SKIP_PREVIEW} more, all left as they are")
    print()


def _print_totals(candidates: list[Survey]) -> None:
    print("Totals")
    print(f"  campaigns to complete      {len(candidates)}")
    print(f"  proposal chains to close   {sum(item.live_chains for item in candidates)}")
    print(f"  invitations to withdraw    {sum(item.open_invitations for item in candidates)}")
    print(f"  notifications to send      {sum(item.notifications for item in candidates)}")
    print()


def run(db: Session, *, apply: bool) -> int:
    """Survey, report, and — only with apply — complete. Returns the exit code."""
    print(f"Campaign completion backfill  ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print(f"Mode: {'APPLY (writes)' if apply else 'DRY RUN (reads only)'}")
    print()

    surveyed = [survey(db, campaign_id) for campaign_id in published_ids(db)]
    surveys = [item for item in surveyed if item is not None]
    candidates = [item for item in surveys if item.completed]
    skipped = [item for item in surveys if not item.completed]

    print(f"Published campaigns examined: {len(surveys)}")
    print()
    if candidates:
        print(f"Campaigns that already satisfy the completion rule: {len(candidates)}")
        for item in candidates:
            _print_candidate(item)
        print()
    _print_skipped(skipped)
    _print_totals(candidates)

    if not candidates:
        print("Nothing to do.")
        return 0
    if not apply:
        print("DRY RUN. Nothing was written. Re-run with --apply to commit the above.")
        return 0

    # maybe_complete_campaign commits per campaign, so a failure part way
    # through leaves the campaigns already moved moved. That is safe rather
    # than untidy: each one went through the shipped path in full, and a second
    # run picks up whatever is left.
    print("Applying.")
    moved: list[Survey] = []
    refused: list[Survey] = []
    for item in candidates:
        if completion.maybe_complete_campaign(db, item.id):
            moved.append(item)
        else:
            refused.append(item)
        after = survey(db, item.id)
        print(f"  {item.id}  {item.title}")
        print(
            f"    before  {item.status}  "
            f"{item.live_chains} live chain(s)  {item.open_invitations} open invitation(s)"
        )
        if after is None:
            print("    after   row is gone")
        else:
            print(
                f"    after   {after.status}  "
                f"{after.live_chains} live chain(s)  {after.open_invitations} open invitation(s)"
            )
    print()

    print(f"Completed: {len(moved)} of {len(candidates)}")
    if refused:
        # Only reachable if the database changed under the run, since nothing
        # else here writes. Worth failing on rather than reporting quietly: the
        # numbers printed above then describe a run that did not happen.
        print("These satisfied the predicate but did not move. Investigate before re-running:")
        for item in refused:
            print(f"  {item.id}  {item.title}")
        return 1
    print("Re-run without --apply to confirm the next run finds no candidates.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Complete the published campaigns that already finished, for the ones whose "
            "contracts ended before the completion hook existed. Reports only unless --apply."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the changes. Without it the script only reports what it would do.",
    )
    args = parser.parse_args(argv)

    # The API process does this at startup and this one never imports app.main,
    # so without it SQLAlchemy does not know about every table it is asked to
    # query. app/jobs/sweeps.py calls it for the same reason.
    import_all_models()

    db = SessionLocal()
    try:
        return run(db, apply=args.apply)
    finally:
        db.close()


if __name__ == "__main__":
    # An unhandled exception is left to propagate: Python exits 1 and prints
    # the traceback, which tells whoever ran this far more than a swallowed
    # error and a tidy message would.
    sys.exit(main())
