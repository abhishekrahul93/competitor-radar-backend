"""
Application configuration — loads from environment variables.
"""
from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Competitor Radar AI"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-to-a-random-secret-key-in-production"
    
    # Database (Railway provides DATABASE_URL automatically)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/competitor_radar"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://competitor-radar.vercel.app",  # Update with your Vercel URL
    ]
    
    # AI Provider
    AI_PROVIDER: str = "openai"  # "openai" or "anthropic"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    
    # JWT Auth
    JWT_SECRET: str = "change-this-jwt-secret-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # Scraping
    SCRAPE_TIMEOUT: int = 30
    SCRAPE_MAX_RETRIES: int = 3
    SCRAPE_DELAY_MIN: float = 1.0
    SCRAPE_DELAY_MAX: float = 3.0
    
    # Change Detection
    SIMILARITY_THRESHOLD: float = 0.92
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
