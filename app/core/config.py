"""Application configuration settings."""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/trend_autostop"
    
    # Security
    SECRET_KEY: str = "change_this_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Master key for envelope encryption (API keys)
    MASTER_KEY: str = "change_this_master_key_in_production_32chars"
    
    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    BASE_URL: str = "http://localhost:8000"
    
    # Exchange
    DEFAULT_EXCHANGE: str = "binance"
    
    # Email Configuration
    SMTP_HOST: str = "smtp.resend.com"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Trend-Autostop"
    SMTP_USE_TLS: bool = True  # True for SSL (port 465), False for STARTTLS (port 587)
    
    # Email verification token expiry (hours)
    EMAIL_VERIFY_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1
    
    # Timeframe options (in minutes)
    TIMEFRAME_OPTIONS: dict = {
        "10min": 10,
        "15min": 15,
        "30min": 30,
        "1h": 60,
        "4h": 240
    }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

