from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "postgresql://kolabo:kolabo@localhost:5432/kolabo"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    # Fernet key used to encrypt verification documents at rest. Override in
    # production via the DOCUMENT_ENCRYPTION_KEY environment variable.
    document_encryption_key: str = "t8eo8FXK3XnpNtKXhH39F9ZPzwrcn3fpIaiBQaFBgnk="
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
    # YouTube Data API v3 key. Public channel data needs only a key (no OAuth,
    # no app review), so setting this turns on YouTube profile auto fill.
    youtube_api_key: str = ""
    # Anthropic API key for AI drafted profile bios. Unset means the feature is
    # reported as unavailable rather than half working.
    anthropic_api_key: str = ""
    bio_model: str = "claude-sonnet-5"
    # How many times one creator may regenerate a bio. A retry button with no
    # cap is an open tab on the inference bill.
    bio_generation_limit: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
