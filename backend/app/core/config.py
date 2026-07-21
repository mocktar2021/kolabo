from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "development"
    database_url: str = "postgresql://kolabo:kolabo@localhost:5432/kolabo"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    class Config:
        env_file = ".env"


settings = Settings()
