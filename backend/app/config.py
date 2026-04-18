"""Application configuration."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "Skyeye"
    APP_ENV: str = os.getenv("APP_ENV", "dev")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # AWS
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_PROFILE: str = os.getenv("AWS_PROFILE", "default")
    DYNAMODB_TABLE_PREFIX: str = os.getenv("DYNAMODB_TABLE_PREFIX", "skyeye")

    # S3 for attachments
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "skyeye-attachments")

    # Auth
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "skyeye-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @property
    def table_name(self) -> str:
        return f"{self.DYNAMODB_TABLE_PREFIX}-{self.APP_ENV}"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
