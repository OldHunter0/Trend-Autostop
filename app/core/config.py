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
    
    # Server
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # Exchange
    DEFAULT_EXCHANGE: str = "binance"
    
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

