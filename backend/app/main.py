from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.database import check_database_connection, AsyncSessionLocal
from app.services.baseline_service import baseline_cache, start_baseline_refresh_task
from app.services.diagnostics import start_discovery_worker, start_diagnostic_cleanup_task
from app.schemas import APIResponse
from app.routers import auth, endpoints, reports, topology, users
from app.routers.reports import telemetry_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_database_connection()
    # Initialize baseline cache and start background tasks
    async with AsyncSessionLocal() as db:
        await baseline_cache.refresh_from_db(db)
    refresh_task = await start_baseline_refresh_task(AsyncSessionLocal, interval_seconds=3600)
    discovery_task = await start_discovery_worker(AsyncSessionLocal)
    cleanup_task = await start_diagnostic_cleanup_task(AsyncSessionLocal, interval_seconds=86400)
    logger.info("lnmp monitoring platform started with Hybrid Adaptive Baseline & Diagnostics.")
    yield
    refresh_task.cancel()
    discovery_task.cancel()
    cleanup_task.cancel()
    logger.info("lnmp monitoring platform shutting down.")

app = FastAPI(
    title="lnmp - Network Monitoring Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Requested-With"],
)

class HSTSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if settings.security.hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

app.add_middleware(HSTSMiddleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(endpoints.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(topology.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(telemetry_router)

@app.get("/api/v1/version", tags=["system"])
async def get_version():
    return APIResponse.success(data={"version": "1.0.0"})

@app.get("/api/v1/health", tags=["system"])
async def health_check():
    return APIResponse.success(data={"status": "ok"})
