"""
client-crm-service — FastAPI application entry point.

Serves client/CRM and brokerage/agent domain endpoints:
  /api/clients/*      — Client management and documents
  /api/agents/*       — Agent management, licenses, commissions
  /api/brokerages/*   — Brokerage management
  /api/leads/*        — Lead tracking
  /api/showings/*     — Showing scheduling
  /api/offers/*       — Offer submission and counter-offers

Migration wave: Wave 2A
Port: 8005

All other platform routes remain with the Java monolith or other migrated services.
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
from app.routers.agents import router as agents_router, _get_db as _ag_get_db
from app.routers.brokerages import router as brokerages_router, _get_db as _br_get_db
from app.routers.clients import router as clients_router, _get_db as _cl_get_db
from app.routers.leads import router as leads_router, _get_db as _le_get_db
from app.routers.offers import router as offers_router, _get_db as _of_get_db
from app.routers.showings import router as showings_router, _get_db as _sh_get_db

# Module-level engine and session factory — created on startup, disposed on shutdown
_engine = None
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _session_factory

    # Startup: create async engine (no DDL — schema managed by Java / external migrations)
    _engine = create_engine(settings.DATABASE_URL, service_name="client-crm-service")
    _session_factory = create_session_factory(_engine)

    # Wire the DB dependency into all routers via dependency_overrides
    async def get_db() -> AsyncSession:
        async with _session_factory() as session:
            yield session

    app.dependency_overrides[_cl_get_db] = get_db
    app.dependency_overrides[_ag_get_db] = get_db
    app.dependency_overrides[_br_get_db] = get_db
    app.dependency_overrides[_le_get_db] = get_db
    app.dependency_overrides[_sh_get_db] = get_db
    app.dependency_overrides[_of_get_db] = get_db

    yield

    # Shutdown: release DB connections
    if _engine is not None:
        await _engine.dispose()


app = FastAPI(
    title="Client CRM Service",
    description=(
        "Migrated FastAPI service for client/CRM and brokerage/agent domain management. "
        "Implements clients, agents, brokerages, leads, showings, and offers "
        "under their respective /api/* prefixes with identical external contract to the "
        "Java ClientController and AgentController."
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
app.include_router(make_health_router("client-crm-service"))

# Domain routes — JWT authentication enforced per-endpoint via shared auth dependency
app.include_router(clients_router)
app.include_router(agents_router)
app.include_router(brokerages_router)
app.include_router(leads_router)
app.include_router(showings_router)
app.include_router(offers_router)
