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
    # Comma separated list of origins allowed to call the API from a browser
    # (the web app in dev and, later, the deployed web origins). Override via
    # the CORS_ORIGINS environment variable.
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://localhost:3000"
    # YouTube Data API v3 key. Public channel data needs only a key (no OAuth,
    # no app review), so setting this turns on YouTube profile auto fill.
    youtube_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
