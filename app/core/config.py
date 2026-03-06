from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Competitor Radar AI"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-to-a-random-secret-key-in-production"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/competitor_radar"
    CORS_ORIGINS: List[str] = ["http://localhost:3000","http://localhost:5173","https://competitor-radar-frontend.vercel.app"]
    AI_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    JWT_SECRET: str = "change-this-jwt-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    SCRAPE_TIMEOUT: int = 30
    SCRAPE_MAX_RETRIES: int = 3
    SCRAPE_DELAY_MIN: float = 1.0
    SCRAPE_DELAY_MAX: float = 3.0
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL: str = ""
    SIMILARITY_THRESHOLD: float = 0.92
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()