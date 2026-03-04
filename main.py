"""
Competitor Radar AI — Production Backend
FastAPI + PostgreSQL + AI Analysis Engine
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine, Base
from app.api import competitors, scanning, changes, reports, auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()

app = FastAPI(
    title="Competitor Radar AI",
    description="AI-Powered Competitive Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend on Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Competitors"])
app.include_router(scanning.router, prefix="/api/scan", tags=["Scanning"])
app.include_router(changes.router, prefix="/api/changes", tags=["Changes"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])

@app.get("/")
async def root():
    return {
        "app": "Competitor Radar AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}
