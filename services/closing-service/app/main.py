"""
closing-service — FastAPI application entry point.

Serves closing domain endpoints:
  /api/closings/*                                  — Closing detail management
  /api/closings/{id}/documents/*                   — Closing document management
  /api/closings/{id}/title-report/*                — Title report management
  /api/closings/{id}/escrow/*                      — Escrow account management
  /api/closings/{id}/escrow/{accountId}/disbursements/*  — Escrow disbursement management

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
from app.routers.closings import router as closings_router, _get_db as _cl_get_db
from app.routers.documents import router as documents_router, _get_db as _doc_get_db
from app.routers.title_reports import router as title_reports_router, _get_db as _tr_get_db
from app.routers.escrow import router as escrow_router, _get_db as _esc_get_db


# Module-level engine and session factory — created on startup, disposed on shutdown
_engine = None
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _session_factory

    # Startup: create async engine (no DDL — schema managed by Java / external migrations)
    _engine = create_engine(settings.DATABASE_URL, service_name="closing-service")
    _session_factory = create_session_factory(_engine)

    # Wire the DB dependency into all routers via dependency_overrides
    async def get_db() -> AsyncSession:
        async with _session_factory() as session:
            yield session

    app.dependency_overrides[_cl_get_db] = get_db
    app.dependency_overrides[_doc_get_db] = get_db
    app.dependency_overrides[_tr_get_db] = get_db
    app.dependency_overrides[_esc_get_db] = get_db

    yield

    # Shutdown: release DB connections
    if _engine is not None:
        await _engine.dispose()


app = FastAPI(
    title="Closing Service",
    description=(
        "Migrated FastAPI service for closing/settlement domain management. "
        "Implements closing details, documents, title reports, escrow accounts, and "
        "disbursements under /api/closings/* with identical external contract to the "
        "Java ClosingController."
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
app.include_router(make_health_router("closing-service"))

# Domain routes — JWT authentication enforced per-endpoint via shared auth dependency
app.include_router(closings_router)
app.include_router(documents_router)
app.include_router(title_reports_router)
app.include_router(escrow_router)
