"""
underwriting-service — FastAPI application entry point.

Serves underwriting domain endpoints:
  /api/loans/{id}/credit-report       — Credit report management
  /api/loans/{id}/underwriting        — Underwriting decisions and conditions
  /api/loans/{id}/appraisal           — Appraisal orders and reports

All other platform routes remain with the Java monolith during Wave 3 migration.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from shared.database import create_engine, create_session_factory
from shared.exceptions import http_exception_handler, validation_exception_handler
from shared.health import make_health_router

from app.config import settings
from app.routers.credit_reports import router as credit_reports_router, _get_db as _cr_get_db
from app.routers.underwriting import router as underwriting_router, _get_db as _uw_get_db
from app.routers.appraisals import router as appraisals_router, _get_db as _ap_get_db


# Module-level engine and session factory — created on startup, disposed on shutdown
_engine = None
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _session_factory

    # Startup: create async engine (no DDL — schema managed by Java / external migrations)
    _engine = create_engine(settings.DATABASE_URL, service_name="underwriting-service")
    _session_factory = create_session_factory(_engine)

    # Wire the DB dependency into all routers via dependency_overrides
    async def get_db() -> AsyncSession:
        async with _session_factory() as session:
            yield session

    app.dependency_overrides[_cr_get_db] = get_db
    app.dependency_overrides[_uw_get_db] = get_db
    app.dependency_overrides[_ap_get_db] = get_db

    yield

    # Shutdown: release DB connections
    if _engine is not None:
        await _engine.dispose()


app = FastAPI(
    title="Underwriting Service",
    description=(
        "Migrated FastAPI service for underwriting domain management. "
        "Implements credit reports, underwriting decisions/conditions, and appraisal "
        "orders/reports under /api/loans/{id}/* with identical external contract to the "
        "Java UnderwritingController."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the configured frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers — registered before routes
# Maps 422 → 400 and {"detail": ...} → {"message": ...} per api-compatibility-rules.md R-STS-8, R-ERR-2
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Health endpoint — no auth required (required by cutover-playbook.md PC-R2)
app.include_router(make_health_router("underwriting-service"))

# Domain routes — JWT authentication enforced per-endpoint via shared auth dependency
app.include_router(credit_reports_router)
app.include_router(underwriting_router)
app.include_router(appraisals_router)
