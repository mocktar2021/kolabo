"""Turning a Google ID token into an address we are willing to sign somebody in as.

WHAT THIS IS NOT. It is not the subsystem in app/modules/profiles/oauth.py.
That one asks a creator for permission to read their own Facebook Page and
stores a token belonging to THEM, against an account that is already signed in.
This one answers a different question entirely: who is at the door. Nothing
here is stored, nothing here is a credential of ours, and there is no redirect
uri, no callback route and no client secret, because there is no server side
code exchange. The client (a browser or a phone) gets an ID token from Google
and posts it; this module reads it.

WHY THE LIBRARY AND NOT A HAND ROLLED VERIFIER. google.oauth2.id_token is what
Google's own documentation points at, and the two obvious alternatives are both
worse. Hand rolling means fetching Google's signing certificates, caching them,
rotating them, and getting RS256 verification right, which is a lot of surface
for a thing that must never be nearly correct. The tokeninfo endpoint is
documented by Google as being for development and debugging, and it puts a
network round trip belonging to somebody else on the path of every sign in.

The absolute import below reaches the google-auth package, NOT this module.
Python 3 has no implicit relative imports, so a module named google.py inside
app/modules/auth can sit beside `from google.oauth2 import id_token` without
shadowing it. It is worth knowing before somebody renames the file to be safe.

WHAT VERIFICATION HAS TO ESTABLISH, and why each one is load bearing:

  * THE SIGNATURE IS GOOGLE'S. Without it a token is a JSON object anybody can
    type, and every other check below is being run against text the caller
    wrote themselves. The library fetches and caches Google's certificates and
    checks RS256 for us.
  * `aud` IS ONE OF OUR CLIENT IDS. A valid, correctly signed Google ID token
    issued to SOMEBODY ELSE'S application is trivially obtainable: sign in to
    their app and read it off the wire. Without an audience check that token
    would sign the holder in here, which turns every other Google app on the
    internet into a way into Kolabo. This is the check people leave out.
  * `iss` IS accounts.google.com, in one of its two spellings. The library
    does this one itself and raises when it does not hold.
  * `exp` HAS NOT PASSED. The library does this too, with a configurable clock
    skew we leave at zero; a Google ID token lives about an hour, which is the
    window in which a leaked one is worth anything.
  * `email_verified` IS TRUE. See below, because this one is ours and it is
    the one holding the whole design up.

THE email_verified CHECK IS WHAT STANDS BETWEEN AN ATTACKER AND AN EXISTING
ACCOUNT. The sign in endpoint links a verified Google address to whatever
Kolabo account already holds that address, deliberately, because the mailbox
IS the login identity on this platform. That decision is only safe while the
address on the token is one Google has actually confirmed. A Google Workspace
domain can be created by anyone who controls the DNS of a domain, and an
account inside it can carry any address the administrator types, including one
at a domain they do NOT control, until Google confirms it. Accepting such a
claim would mean anybody could take over a Kolabo account by asserting its
owner's address at a domain of their own. The claim is the only thing checking
that, so an unverified address is refused outright rather than downgraded to
some lesser trust.

THE ADDRESS IS NORMALISED BEFORE IT LEAVES THIS MODULE, through the same
core.emails function registration uses. Every caller does a lookup with it, and
a lookup on an un-normalised address is how one spelling of a mailbox looks
free while another is taken, which turns a clean 409 into a 500 on the insert
that finds out.

UNSET MEANS UNAVAILABLE, not broken. With no client ids configured there is no
audience to check against, so there is nothing this module could honestly
verify and the feature reports itself absent. Same rule as the YouTube key, the
Meta credentials, the Anthropic key and the FedaPay keys: a provider nobody
configured is ABSENT rather than half working.
"""
import logging
from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings
from app.core.emails import normalized_email

_log = logging.getLogger("kolabo.auth.google")


@dataclass(frozen=True)
class GoogleIdentity:
    """Who Google says this is, reduced to the two facts anything here needs.

    Frozen because it crosses a trust boundary: it is assembled once, from
    claims that have just been checked, and a caller that could edit it could
    edit the address an account is about to be created or signed in under.

    `email` is ALREADY NORMALISED. Callers look accounts up with it directly
    and must not re-derive it from anything else.

    `subject` is Google's `sub`, the stable per-account identifier. Nothing
    stores it yet, and it is carried anyway because it is the only claim that
    survives somebody changing their Google address: the day this platform
    wants to notice that two Kolabo accounts are one Google account, or to keep
    a link alive across an address change, `sub` is the column that does it.
    Reading it here costs nothing and keeps the option open.
    """

    email: str
    subject: str


def client_ids() -> set[str]:
    """The OAuth client ids a token may be addressed to.

    A COMMA SEPARATED LIST RATHER THAN ONE VALUE, because web and mobile are
    different OAuth clients with different ids, and iOS is a third. A single
    value would verify one of them and refuse the others, which would look
    exactly like a broken sign in button on whichever platform lost the toss.

    Split and cleaned the same way admins.admin_emails splits its list, so an
    operator who leaves a trailing comma or a stray space in a .env file gets
    what they meant rather than a client id with a space in it that no token
    can ever equal.

    Empty means the feature is off everywhere. See the module docstring.
    """
    return {raw.strip() for raw in settings.google_client_ids.split(",") if raw.strip()}


def verify(raw_token: str | None) -> GoogleIdentity | None:
    """Check a token completely, or answer None and say why in the log.

    ONE FAILURE VALUE FOR EVERY WAY OF FAILING, and that is the whole point.
    The caller turns None into a single refusal with a single sentence, so a
    forged, expired, wrongly addressed or unverified token are indistinguishable
    from outside. Handing back which check caught it would tell whoever is
    holding a token exactly what to fix, and no honest user is helped by the
    difference: the two things that ever help are try again and check the
    address on the Google side, and the sentence carries both.

    The reason IS recorded, at WARNING, because the person who has to diagnose
    a sign in button that refuses everybody is us, and a refusal that says
    nothing anywhere is a support ticket with no first step.
    """
    if not raw_token:
        return None

    audiences = client_ids()
    if not audiences:
        # Defensive: the endpoint refuses with auth_google_unavailable before
        # it ever gets here. Repeated because a verifier that would check a
        # signature and then skip the audience is the one mistake in this file
        # that must not be reachable by any path at all.
        _log.warning("Google sign in attempted with no GOOGLE_CLIENT_IDS configured")
        return None

    try:
        # Sorted so the list in a log line or a raised message is stable
        # between processes, which matters when two servers disagree about
        # their configuration and somebody is comparing two log lines.
        claims = id_token.verify_oauth2_token(
            raw_token,
            # Built here rather than kept at module level: it owns an HTTP
            # session, and a module level one would be created at import time
            # in every process that merely imports auth, including the test
            # suite and the sweeps container, neither of which signs anybody in.
            google_requests.Request(),
            audience=sorted(audiences),
        )
    except Exception as exc:  # noqa: BLE001
        # DELIBERATELY BROAD. The library raises ValueError for a malformed or
        # wrongly addressed token, GoogleAuthError for a bad issuer, and
        # whatever the transport raises when Google's certificate endpoint is
        # unreachable. Every one of them means the same thing to this function
        # (we cannot say who this is) and letting any of them escape would turn
        # a refused sign in into a 500.
        _log.warning("Google ID token refused: %s: %s", type(exc).__name__, exc)
        return None

    # CHECKED AGAIN, ON OUR SIDE. The library does compare `aud` against the
    # list above, so this is belt and braces rather than a gap being closed,
    # and it is here because of how quiet the failure would be if that ever
    # stopped being true: a version of google-auth that took a list and
    # silently checked only the first entry would leave the other clients
    # signing in unverified, with nothing red anywhere.
    if claims.get("aud") not in audiences:
        _log.warning("Google ID token has audience %r, which is not ours", claims.get("aud"))
        return None

    # THE CHECK THE LINKING RULE RESTS ON. See the module docstring.
    #
    # True or the string "true": the claim arrives as a JSON boolean from
    # Google today and has historically been serialised as a string by some
    # of its endpoints. Anything else at all, absent included, is unverified.
    if claims.get("email_verified") not in (True, "true"):
        _log.warning("Google ID token carries an unverified email address, refused")
        return None

    # Normalised here so no caller can forget to. See the module docstring.
    email = normalized_email(claims.get("email"))
    if email is None:
        _log.warning("Google ID token carries no usable email address")
        return None

    subject = claims.get("sub")
    if not subject:
        # Google always sends one. If it ever does not, the token is not
        # something this platform understands well enough to act on.
        _log.warning("Google ID token carries no subject claim")
        return None

    return GoogleIdentity(email=email, subject=str(subject))
