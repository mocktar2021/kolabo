"""Who is an admin, and where that fact comes from.

THE HEADER WAS NOT AUTHENTICATION. Until now `get_current_admin` accepted any
non-empty `X-Admin-Id` header and returned it as an identity. That gate was
the only thing in front of splitting a disputed escrow — which moves real
money — as well as approving identity documents and enabling countries.
Anyone who could reach the API could set a header. The code called it a
deliberate pilot placeholder, and it was; it simply must not meet real Mobile
Money.

An admin is now a USER with `is_admin` set, proving it the same way everyone
else does: a bearer token from a real login, with a password, a mailbox that
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

So `admin_emails` is a comma separated list of email addresses, and this
function makes the database agree with it on every boot:

  * a listed address with an account is granted, if it is not already;
  * an account holding is_admin whose address is NOT listed has it REVOKED.

The revoke half is the important one and is why this is a sync rather than a
seed. Without it the setting only ever adds, so removing somebody means
remembering to also go and edit a row — and the day you most want to remove an
admin is the day you least want to be hand-editing production data. Deleting
the address and redeploying is the whole procedure.

THE REVOKE HALF IS ALSO WHY THE RENAME FROM admin_phones HAD TO HAPPEN IN THE
SAME COMMIT AS THE MATCH ON User.email, AND WHY IT IS THE MOST DANGEROUS LINE
IN THE IDENTITY FLIP. A setting still holding phone numbers, matched against
addresses, does not raise anything: it matches nothing, grants nobody, and then
the loop below revokes is_admin from every admin there is. Nothing in the boot
log would look wrong beyond one warning, every admin endpoint would answer 403,
and nobody could resolve a disputed escrow or run the money sweeps until
somebody worked out why. Grant and revoke read the same column or this function
is a self-destruct.

A listed address with NO account is not an error and not created here. Admins
register like anyone else; listing an address before that person has signed up
simply means they become an admin at the next boot after they do. Creating a
passwordless user from a config file would be a worse hole than the one this
closes.

THE LIST IS NORMALISED THE SAME WAY A REGISTRATION IS, through core.emails, so
that an operator who writes Mocktar@Example.com in a .env file matches the row
stored as mocktar@example.com. Without that, the rename would have fixed the
column and left the same silent revoke waiting behind a capital letter. An
entry that is not an address at all is dropped and said out loud, because an
entry that is quietly discarded is one admin fewer than whoever edited the file
believes there is.
"""
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.emails import normalized_email
from app.modules.auth.models import User

logger = logging.getLogger(__name__)


def admin_emails() -> set[str]:
    """The configured list, split, normalised and cleaned.

    NORMALISED THROUGH THE SAME FUNCTION REGISTRATION USES, so a capital letter
    in a hand-edited .env file cannot mean "this person is not an admin". See
    the module docstring for why a quiet mismatch here is so expensive.

    An entry core.emails refuses is dropped and logged at WARNING rather than
    passed through as a literal. Passing it through would put a string in
    `wanted` that no row can ever equal, which is indistinguishable at the
    query from having configured nobody.

    Empty by default, and an empty list means NO admins — every admin endpoint
    answers 403 to everybody. That is the right default for a system where the
    alternative default is "everybody": a deployment that forgot to configure
    this locks the admin surface rather than opening it.
    """
    wanted: set[str] = set()
    unreadable: list[str] = []
    for raw in settings.admin_emails.split(","):
        if not raw.strip():
            continue
        email = normalized_email(raw)
        if email is None:
            unreadable.append(raw.strip())
            continue
        wanted.add(email)
    if unreadable:
        logger.warning("Admin entries that are not email addresses, ignored: %s", unreadable)
    return wanted


def sync_admins(db: Session) -> dict:
    """Make is_admin match the configured address list. Returns what changed.

    GRANT AND REVOKE READ THE SAME COLUMN, and that is the invariant this whole
    module turns on. See the note in the module docstring about what happens
    when they do not.
    """
    wanted = admin_emails()

    granted = []
    if wanted:
        for user in db.query(User).filter(User.email.in_(wanted), User.is_admin.is_(False)):
            user.is_admin = True
            granted.append(user.email)

    revoked = []
    holders = db.query(User).filter(User.is_admin.is_(True))
    for user in holders:
        if user.email not in wanted:
            user.is_admin = False
            revoked.append(user.email)

    if granted or revoked:
        db.commit()
        # Logged at INFO because it is a privilege change, and the one thing
        # somebody reading boot output should be able to find afterwards.
        logger.info("Admin sync: granted %s, revoked %s", granted, revoked)

    missing = sorted(wanted - {u.email for u in db.query(User).filter(User.email.in_(wanted))})
    if missing:
        # Not an error: they may simply not have registered yet, and they will
        # be picked up at the next boot after they do. Said out loud because
        # the alternative is somebody wondering for an afternoon why the admin
        # page 403s at an address they are certain they configured.
        logger.warning("Admin addresses with no account yet: %s", missing)

    return {"granted": len(granted), "revoked": len(revoked), "no_account": len(missing)}
