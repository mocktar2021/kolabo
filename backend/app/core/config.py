from pydantic import model_validator
from pydantic_settings import BaseSettings

# THE COMMITTED DEFAULTS, NAMED, so that production can refuse them by value.
#
# A laptop must run with no setup, which is what these defaults are for. A
# production deployment must never run WITH them: a JWT secret that is in a
# public git history lets anyone mint a token for any account, including an
# admin's, and the admin surface includes POST /payments/escrow/{id}/resolve,
# which splits any escrow to any amounts that balance. The gap between those
# two sentences is one forgotten environment variable, and until the
# validator below existed nothing noticed. Kept as module constants rather
# than inlined twice so the check and the default cannot drift apart.
DEFAULT_JWT_SECRET = "change-me"
DEFAULT_DOCUMENT_ENCRYPTION_KEY = "t8eo8FXK3XnpNtKXhH39F9ZPzwrcn3fpIaiBQaFBgnk="


class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "postgresql://kolabo:kolabo@localhost:5432/kolabo"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    # Fernet key used to encrypt verification documents at rest. Override in
    # production via the DOCUMENT_ENCRYPTION_KEY environment variable.
    document_encryption_key: str = DEFAULT_DOCUMENT_ENCRYPTION_KEY
    # Platform commission in basis points (1500 = 15 percent). Launch value,
    # to be confirmed via Business Model Validation and set per country later.
    commission_bps: int = 1500
    # Days a held escrow waits before it auto releases if the business does
    # not confirm delivery.
    #
    # STILL THE FUNDING-TIME DEFAULT, and no longer the number that decides an
    # auto release on its own. due_release_at is stamped with it when the
    # escrow is funded, and then RE-STAMPED from review_window_days the moment
    # the creator submits work. It survives as the value a funded-but-never-
    # delivered escrow carries — a deadline the sweep will not act on, because
    # nothing has been submitted against it.
    auto_release_days: int = 7
    # Days the business has to review submitted work before the escrow releases
    # itself.
    #
    # Shorter than auto_release_days on purpose. The old seven days had to
    # cover the whole job — agree, shoot, post, review — because the clock
    # started at funding. This one starts when the work is actually in front of
    # the brand, so it only has to cover LOOKING at it, and a creator who
    # delivered should not wait a week on a brand that never clicks. Short
    # enough to keep payouts moving, long enough that a weekend does not run
    # it out. Reset on every resubmission, so revised work earns a fresh look.
    review_window_days: int = 4
    # Days between "your delivery date has passed" and the escrow being
    # refunded to the brand, when the creator has submitted NOTHING at all.
    #
    # The pause exists because a refund ends the job. A creator who is three
    # days late and about to post is not the same person as one who has
    # vanished, and the platform cannot tell them apart — so it says so out
    # loud and gives the late one a window to act in. Five days is long enough
    # to cover a bad week and short enough that a brand's money is not stuck
    # for a month. See payments.service.run_non_delivery_refunds.
    non_delivery_grace_days: int = 5
    # Hours the other party has to answer a dispute before it reaches the
    # admin queue. Long enough that somebody in another timezone with a day
    # job can actually reply; short enough that a real refusal is not a month
    # of frozen money. A setting rather than a constant because the right
    # number is a thing the pilot will tell us, not a thing we know.
    dispute_response_hours: int = 72

    # ---------------------------------------------------------------- payments
    # FedaPay is the contracted gateway for the UEMOA launch markets: Benin,
    # Togo and Cote d'Ivoire. The decision and the numbers behind it are in
    # docs/PAYMENTS_FEDAPAY.md; the short version is that a marketplace has to
    # be able to pay third parties from code, and of the two candidates only
    # FedaPay has an API that does it.
    #
    # UNSET MEANS PAYMENTS ARE OFF, not that they run against some default.
    # With no secret key the gateway registry is empty, escrow funding falls
    # back to the in-process mock provider, and every real money endpoint
    # refuses with a sentence that says so. Same rule the YouTube and Anthropic
    # integrations follow below: a feature with no key reports itself
    # unavailable rather than half working.
    fedapay_secret_key: str = ""
    # The publishable key. The backend never calls FedaPay with it — it is
    # served to the clients through GET /payments/config so that rotating a key
    # is a backend deploy rather than two app store releases.
    fedapay_public_key: str = ""
    # The endpoint secret from the FedaPay dashboard's webhook tab, prefixed
    # wh_. NOT the same value as fedapay_secret_key, and mixing them up rejects
    # every webhook in a way that reads like a network fault rather than a
    # configuration one. Empty makes verification REFUSE rather than skip —
    # see gateways/signature.py for why that is the only safe direction.
    fedapay_webhook_secret: str = ""
    # Sandbox by default, so a deployment handed live keys without being told
    # to use them stays in the test environment instead of moving real money.
    # Going live is an explicit FEDAPAY_SANDBOX=false.
    fedapay_sandbox: bool = True
    # Where the gateway sends the payer when checkout finishes; the payment
    # intent id is appended as a query parameter. The domain must be
    # whitelisted in the FedaPay dashboard or payers land on a signup page
    # instead of a payment form. Mobile passes its own kolabo:// deep link per
    # request rather than using this.
    payment_return_url: str = "http://localhost:5173/checkout/return"
    # How many times a failed payout is retried before the sweep leaves it
    # alone and it becomes a support queue item. A payout that has failed five
    # times will not succeed on the sixth for the same reason it failed on the
    # first, and retrying forever bills us per attempt.
    payout_max_attempts: int = 5

    # How long a password reset code stays usable.
    #
    # Short on purpose, and shorter than the registration OTP's ten minutes is
    # not the point — what this window really bounds is how long a borrowed or
    # briefly unattended handset is an account takeover. The code arrives by
    # SMS on the phone that IS the login identity, so the SMS itself is the
    # credential, and a credential sitting readable on a lock screen should
    # stop working quickly. A setting rather than a constant because support
    # will tell us whether fifteen minutes is enough for a real person on a
    # slow network.
    password_reset_ttl_minutes: int = 15
    # How many live (unconsumed, unexpired) reset codes one phone may hold
    # within an hour. Every request sends an SMS and every SMS costs money, so
    # an uncapped endpoint is a bill that anyone on the internet can run up on
    # us by looping over a phone number. It also caps how many valid codes are
    # in flight for one account at once.
    password_reset_max_per_hour: int = 3
    # How many live (unconsumed, unexpired) verification codes one phone may
    # hold within an hour.
    #
    # THE REGISTRATION OTP HAD NO CEILING AT ALL, which is the gap this closes.
    # POST /auth/register re-sends the code when the number already has an
    # unverified row, so it is the resend endpoint as well as the signup one,
    # and a loop over a single phone number was an unbounded SMS bill anybody
    # on the internet could run up on us. SMS is the most expensive thing this
    # product does per request in the launch markets.
    #
    # Same number and same shape as password_reset_max_per_hour above,
    # deliberately: there is ONE rule about how many codes may be in flight to
    # one handset, and a second mechanism with its own arithmetic would be a
    # second thing to reason about the day either number changes.
    otp_max_per_hour: int = 3
    # How many live verification codes the WHOLE PLATFORM may hold at once.
    #
    # THE CAP ABOVE IS NOT A BILL CAP, and that is the hole this closes. It
    # counts codes per phone, so cycling fresh numbers costs one SMS each and
    # the total stays unbounded: three per number times as many numbers as an
    # attacker cares to type. Nothing anywhere counted the total.
    #
    # A BACKSTOP, NOT A QUEUE. A global ceiling is itself a denial of service —
    # whoever reaches it locks out every legitimate signup until the codes
    # expire — so it is set two orders of magnitude above any plausible
    # legitimate ten minutes rather than anywhere near real traffic. Five
    # hundred unconsumed codes alive at once is a launch-day crowd several
    # times over in five pilot countries; reaching it means something is wrong,
    # not that the product is popular. What it buys is a bounded worst case:
    # with a ten-minute OTP lifetime, at most ~3,000 messages an hour instead
    # of however many an attacker feels like paying us to send. That is a bill
    # somebody notices and survives.
    #
    # A setting rather than a constant precisely because of the DoS side of the
    # trade: if this ever bites a real burst it has to be raisable with an
    # environment variable and a restart, not a code change and a new image.
    #
    # SAME COUNTING as otp_max_per_hour — live (unconsumed, unexpired, issued
    # within the hour) rows, not sends per hour — so the two numbers mean the
    # same kind of thing. With a ten-minute TTL that makes both of them really
    # "codes in flight", which is the quantity that maps to money spent.
    #
    # NOT applied to password reset. That endpoint only ever sends to a number
    # that already has an account, so its bill is bounded by the user table
    # rather than by the attacker's imagination — and a global cap there would
    # let one attacker lock every real user out of recovering their account,
    # which is a worse outcome than the one it would prevent.
    otp_global_max_per_hour: int = 500
    # Comma separated phone numbers of the people who may use the admin
    # surface. THIS IS THE ADMIN LIST, and the database is made to agree with
    # it on every boot — listed numbers are granted, unlisted holders are
    # revoked. See app.modules.auth.admins for why deployment config rather
    # than a flag somebody sets through the UI.
    #
    # Empty by default, and empty means NOBODY. A deployment that forgot to
    # configure this locks the admin surface instead of opening it.
    admin_phones: str = ""
    # Comma separated list of origins allowed to call the API from a browser
    # (the web app in dev and, later, the deployed web origins). Override via
    # the CORS_ORIGINS environment variable.
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://localhost:3000"
    # Where this API is reachable from the public internet, with no trailing
    # slash. Used to build the OAuth redirect_uri
    # (<base>/profiles/oauth/<platform>/callback) that a social platform sends
    # a creator's browser back to.
    #
    # A SETTING RATHER THAN SOMETHING DERIVED FROM THE REQUEST, and the reason
    # is that OAuth compares this string BYTE FOR BYTE. It has to match what is
    # registered in the platform's developer console, and it has to be the same
    # value at the authorization step and again at the token exchange — the
    # providers reject a mismatch outright. Building it from the incoming Host
    # header would make a creator's ability to connect their account depend on
    # which proxy header survived the last infrastructure change, and the
    # failure ("redirect_uri_mismatch") names none of that.
    #
    # Not a credential. It IS in .env.example, and the note beside it there
    # says why: this default is the local dev API, so a deployed server that
    # never sets it sends every creator to a callback on localhost:8000 and
    # Meta refuses the handshake before the consent screen is even drawn. That
    # is a one-line misconfiguration whose error message names nothing, which
    # is exactly the kind that belongs in the example file.
    api_public_base_url: str = "http://localhost:8000"
    # YouTube Data API v3 key. Public channel data needs only a key (no OAuth,
    # no app review), so setting this turns on YouTube profile auto fill.
    youtube_api_key: str = ""
    # Meta Graph API credentials for Instagram and Facebook profile auto fill.
    # Both platforms are read through the same Graph host (graph.facebook.com),
    # so they share one long-lived access token and one pinned API version.
    #
    # meta_graph_token: a long-lived token that can read the fields below. For a
    #   Facebook Page that is a Page or app token with pages_read_engagement;
    #   for Instagram Business Discovery it must be tied to the Business account
    #   in instagram_business_account_id, with instagram_basic and
    #   pages_show_list. One token carrying all of those drives both features.
    # instagram_business_account_id: the Instagram Business/Creator account the
    #   app queries THROUGH. Business Discovery returns another creator's public
    #   stats by handle, but only when the caller is itself a Business account,
    #   so this id is required — unset leaves Instagram auto fill off even when
    #   the token is present, while Facebook still works on the token alone.
    # meta_graph_version: the pinned Graph API version, overridable as Meta ages
    #   versions out from under a fixed string.
    #
    #   THIS DEFAULT HAS AN EXPIRY DATE, which is the point of the note. Meta
    #   keeps each Graph API version for AT LEAST TWO YEARS from release and
    #   then stops answering it, so a version pinned here is correct when it is
    #   written and silently wrong later: calls to a retired version fail, and
    #   the enrichers turn that into a logged warning and a None, which reads
    #   like a bad token rather than a stale string. This sat on v19.0
    #   (released 23 January 2024) until three months past its 21 May 2026
    #   expiry, and nothing said so because no deployment had a token set.
    #
    #   v26.0 was released 29 July 2026. Its two removals — root GET /?ids=
    #   batch lookups and legacy ETag handling — are not used by either
    #   enricher, which fetch one node at a time with a fields parameter. Put
    #   the release date beside the next value too, so the next person can tell
    #   at a glance how much runway is left.
    #
    #   IT NOW PINS THE OAUTH PROVIDER TOO, which raises the cost of letting it
    #   go stale. A retired version does not merely stop enriching profiles: it
    #   stops the consent dialog and the token exchange, so nobody can connect
    #   an account at all.
    meta_graph_token: str = ""
    instagram_business_account_id: str = ""
    meta_graph_version: str = "v26.0"
    # The Meta APP's own credentials, for the OAuth handshake in
    # profiles/oauth.py that connects a creator's Facebook Page.
    #
    # A DIFFERENT THING FROM meta_graph_token ABOVE, and the distinction is
    # what earns them separate settings rather than a reused one.
    # meta_graph_token is a token belonging to KOLABO, used to read public data
    # about a handle the creator typed — nobody authorised anything. These two
    # are the app's identity in a handshake where the CREATOR authorises US,
    # and what comes back is a token belonging to them, over their own Page.
    # One is a key we hold; the other is how we ask permission.
    #
    # UNSET MEANS THE PROVIDER IS NOT REGISTERED, the same rule as
    # youtube_api_key and fedapay_secret_key. With neither set,
    # oauth.build_default_providers() returns the empty registry it always
    # returned and POST /profiles/oauth/facebook/start answers
    # `oauth_platform_unsupported`, exactly as it did before the provider
    # existed. BOTH are required: an app id with no secret cannot complete a
    # token exchange, so half-configured is treated as unconfigured rather than
    # as a consent screen that ends in a 502.
    #
    # THE SECRET IS A SECRET, and it is not the kind that only embarrasses us.
    # Anyone holding it can mint tokens as the Kolabo app. It belongs in
    # deploy/.env on the server and never in this repository, an image, or a
    # screenshot.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    # Anthropic API key for AI drafted profile bios. Unset means the feature is
    # reported as unavailable rather than half working.
    anthropic_api_key: str = ""
    bio_model: str = "claude-sonnet-5"
    # How many times one creator may regenerate a bio. A retry button with no
    # cap is an open tab on the inference bill.
    bio_generation_limit: int = 10

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _refuse_committed_secrets_in_production(self):
        """Refuse to exist with ENV=production and a secret still at its default.

        AT CONSTRUCTION, WHICH IS IMPORT, WHICH IS STARTUP. Settings() runs at
        the bottom of this module, so the API, the sweeps container and any
        script that imports app.core.config all refuse in the same way and
        none of them gets as far as opening a database with a forged-token
        risk hanging over it. The traceback names the variables, because the
        person reading it is mid-deploy and needs the fix, not a riddle.

        The codebase already accepts this pattern for a smaller risk:
        gateway_router computes mock_payments as (not live) and env !=
        "production", and gateway_schemas calls the environment half of that
        condition load-bearing. Same reasoning, higher stakes.

        Development is untouched. A laptop still runs with no setup, which is
        the reason the defaults exist at all.
        """
        if self.env != "production":
            return self
        problems: list[str] = []
        if self.jwt_secret == DEFAULT_JWT_SECRET:
            problems.append("JWT_SECRET is the committed default; anyone can mint a token")
        if self.document_encryption_key == DEFAULT_DOCUMENT_ENCRYPTION_KEY:
            problems.append(
                "DOCUMENT_ENCRYPTION_KEY is the committed default; verification documents are readable"
            )
        # Only when payments are live. With no secret key the registry is
        # empty and no webhook will ever arrive, so an empty webhook secret
        # is not a fault. With one, every webhook FedaPay sends would be
        # rejected, and /payments/config would report healthy right up until
        # the first escrow failed to fund.
        if self.fedapay_secret_key and not self.fedapay_webhook_secret:
            problems.append(
                "FEDAPAY_WEBHOOK_SECRET is empty while FEDAPAY_SECRET_KEY is set; every webhook would be rejected"
            )
        if problems:
            raise RuntimeError(
                "Refusing to start with ENV=production. Set these in deploy/.env and restart:\n  "
                + "\n  ".join(problems)
            )
        return self


settings = Settings()
