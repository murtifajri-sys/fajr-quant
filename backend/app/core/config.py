"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    APP_NAME: str = "Fajr Quant"
    ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "mysql+pymysql://fajr:fajr@db:3306/fajr_quant?charset=utf8mb4"

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Token encryption key (Fernet). Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = "CHANGE_ME_FERNET_KEY"

    # Stockbit
    STOCKBIT_BASE_URL: str = "https://exodus.stockbit.com"
    STOCKBIT_REQUEST_TIMEOUT: int = 30
    STOCKBIT_MAX_RETRIES: int = 3

    # yfinance
    YFINANCE_PROXY: Optional[str] = None

    # AI provider: deepseek | openai | claude | gemini
    AI_PROVIDER: str = "deepseek"
    AI_API_KEY: str = "sk-b545bbace5de4b279e4ea30cf75f7f63"
    AI_BASE_URL: str = "https://api.deepseek.com"
    AI_MODEL: str = "deepseek-v4-pro"

    # Free fallback model (OpenAI-compatible). Used automatically when the primary
    # AI runs out of tokens / quota. By default it mirrors the primary endpoint but
    # uses AI_FALLBACK_MODEL (deepseek-v4-flash) which is free. Override the three
    # AI_FALLBACK_* vars to point at any other free OpenAI-compatible endpoint
    # (e.g. local Ollama, Groq, OpenRouter).
    AI_FALLBACK_API_KEY: str = "sk-b545bbace5de4b279e4ea30cf75f7f63"
    AI_FALLBACK_BASE_URL: str = "https://api.deepseek.com"
    AI_FALLBACK_MODEL: str = "deepseek-v4-flash"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""

    # Data windows
    TECHNICAL_LOOKBACK_DAYS: int = 1000
    BANDARMOLOGY_LOOKBACK_DAYS: int = 90
    DAILY_INCREMENTAL_OVERLAP_DAYS: int = 5  # overlap when fetching missing data
    DAILY_INCREMENTAL_MAX_DAYS: int = 30  # max lookback for incremental daily fetch

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Universe
    SCREENER_UNIVERSE: str = "idx"  # idx | watchlist
    DAILY_PIPELINE_MAX_TICKERS: int = 50

    # Pipeline
    PIPELINE_MAX_WORKERS: int = 4
    STOCKBIT_RATE_LIMIT_DELAY: float = 0.5
    RECOMMENDATION_MAX_TICKERS: int = 10  # AI recommendations per day (top scores)
    RECOMMENDATION_LOOKBACK_DAYS: int = 20
    RECOMMENDATION_MIN_AVG_DAILY_VALUE: float = 500_000_000  # IDR; minimum average daily transaction value
    RECOMMENDATION_MAX_AVG_WICK_PCT: float = 0.05  # maximum average total wick % of close


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
