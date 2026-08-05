"""Who is an admin, and where that fact comes from.

THE HEADER WAS NOT AUTHENTICATION. Until now `get_current_admin` accepted any
non-empty `X-Admin-Id` header and returned it as an identity. That gate was
the only thing in front of splitting a disputed escrow — which moves real
money — as well as approving identity documents and enabling countries.
Anyone who could reach the API could set a header. The code called it a
deliberate pilot placeholder, and it was; it simply must not meet real Mobile
Money.

An admin is now a USER with `is_admin` set, proving it the same way everyone
else does: a bearer token from a real login, with a password, a phone that
receives an OTP, and a reset path. Nothing new to build, and the audit trail
stops recording a string somebody typed and starts recording a person.

WHY THE SETTING IS THE SOURCE OF TRUTH, and not a flag an admin sets on
another account through the UI.

A grant endpoint is the obvious next feature and is deliberately not here.
The first admin has to come from somewhere, and every way of bootstrapping one
through the API is a hole: an endpoint that promotes the first caller is a
race anybody can win, and one that trusts a shared secret is the header again
wearing a longer name. Deployment configuration is the one channel an attacker
who has reached the API does not automatically have.

So `admin_phones` is a comma separated list of phone numbers, and this
function makes the database agree with it on every boot:

  * a listed phone with an account is granted, if it is not already;
  * an account holding is_admin whose phone is NOT listed has it REVOKED.

The revoke half is the important one and is why this is a sync rather than a
seed. Without it the setting only ever adds, so removing somebody means
remembering to also go and edit a row — and the day you most want to remove an
admin is the day you least want to be hand-editing production data. Deleting
the phone and redeploying is the whole procedure.

A listed phone with NO account is not an error and not created here. Admins
register like anyone else; listing a number before that person has signed up
simply means they become an admin at the next boot after they do. Creating a
passwordless user from a config file would be a worse hole than the one this
closes.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import User

logger = logging.getLogger(__name__)


def admin_phones() -> set[str]:
    """The configured list, split and cleaned.

    Empty by default, and an empty list means NO admins — every admin endpoint
    answers 403 to everybody. That is the right default for a system where the
    alternative default is "everybody": a deployment that forgot to configure
    this locks the admin surface rather than opening it.
    """
    return {phone.strip() for phone in settings.admin_phones.split(",") if phone.strip()}


def sync_admins(db: Session) -> dict:
    """Make is_admin match the configured phone list. Returns what changed."""
    wanted = admin_phones()

    granted = []
    if wanted:
        for user in db.query(User).filter(User.phone.in_(wanted), User.is_admin.is_(False)):
            user.is_admin = True
            granted.append(user.phone)

    revoked = []
    holders = db.query(User).filter(User.is_admin.is_(True))
    for user in holders:
        if user.phone not in wanted:
            user.is_admin = False
            revoked.append(user.phone)

    if granted or revoked:
        db.commit()
        # Logged at INFO because it is a privilege change, and the one thing
        # somebody reading boot output should be able to find afterwards.
        logger.info("Admin sync: granted %s, revoked %s", granted, revoked)

    missing = sorted(wanted - {u.phone for u in db.query(User).filter(User.phone.in_(wanted))})
    if missing:
        # Not an error: they may simply not have registered yet, and they will
        # be picked up at the next boot after they do. Said out loud because
        # the alternative is somebody wondering for an afternoon why the admin
        # page 403s at a number they are certain they configured.
        logger.warning("Admin phones with no account yet: %s", missing)

    return {"granted": len(granted), "revoked": len(revoked), "no_account": len(missing)}
