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

    class Config:
        env_file = ".env"


settings = Settings()
