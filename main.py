from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from app.core.database import engine, Base
from app.api import competitors, scanning, changes, reports, auth, demo, payments, export
from app.services.scheduler import start_scheduler, stop_scheduler
import logging

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for alter in ["ALTER TABLE reports ALTER COLUMN threat_level TYPE TEXT","ALTER TABLE reports ALTER COLUMN title TYPE TEXT","ALTER TABLE users ADD COLUMN IF NOT EXISTS slack_webhook TEXT DEFAULT ''"]:
            try:
                await conn.execute(text(alter))
            except Exception:
                pass
    start_scheduler(interval_hours=12)
    yield
    stop_scheduler()
    await engine.dispose()

app = FastAPI(title="Competitor Radar AI", version="1.0.0", lifespan=lifespan)

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = JSONResponse(content={}, status_code=200)
    else:
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse(content={"detail": "Internal server error"}, status_code=500)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(competitors.router, prefix="/api/competitors", tags=["Competitors"])
app.include_router(scanning.router, prefix="/api/scan", tags=["Scanning"])
app.include_router(changes.router, prefix="/api/changes", tags=["Changes"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(demo.router, prefix="/api/demo", tags=["Demo"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])

@app.get("/")
async def root():
    return {"app": "Competitor Radar AI", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "auto_scan": "active"}
