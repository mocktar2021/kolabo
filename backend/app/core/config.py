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

    class Config:
        env_file = ".env"


settings = Settings()
