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
    auto_release_days: int = 7
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
