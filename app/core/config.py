from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, EmailStr, validator
from typing import Optional

class Settings(BaseSettings):
    # App config
    PROJECT_NAME: str = "Gym Management ERP"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # JWT Security - Validates secrets securely
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours typical for accountant shifts
    
    # Database Settings
    DATABASE_URL: str

    # Allow mapping variables directly from .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @property
    def async_database_url(self) -> str:
        """
        Dynamically ensures our Postgres URL utilizes the asyncpg driver
        vital for high-concurrent QR scan websockets.
        """
        if self.DATABASE_URL.startswith("sqlite"):
            return self.DATABASE_URL
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Instantiate settings to be imported cleanly across the app
settings = Settings()