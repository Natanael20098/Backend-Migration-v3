"""
property-listing-service — FastAPI application entry point.

Serves /api/properties/* and /api/listings/* endpoints.
All other platform routes remain with the Java monolith during Wave 1 migration.
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
from app.routers.properties import router as properties_router, _get_db as _prop_get_db
from app.routers.listings import router as listings_router, _get_db as _list_get_db


# Module-level engine and session factory — created on startup, disposed on shutdown
_engine = None
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _session_factory

    # Startup: create async engine (no DDL — schema managed by Java / external migrations)
    _engine = create_engine(settings.DATABASE_URL, service_name="property-listing-service")
    _session_factory = create_session_factory(_engine)

    # Wire the DB dependency into both routers via dependency_overrides
    async def get_db() -> AsyncSession:
        async with _session_factory() as session:
            yield session

    app.dependency_overrides[_prop_get_db] = get_db
    app.dependency_overrides[_list_get_db] = get_db

    yield

    # Shutdown: release DB connections
    if _engine is not None:
        await _engine.dispose()


app = FastAPI(
    title="Property & Listing Service",
    description=(
        "Migrated FastAPI service for property and listing management. "
        "Implements /api/properties/* and /api/listings/* with identical external "
        "contract to the Java PropertyController and ListingController."
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
app.include_router(make_health_router("property-listing-service"))

# Domain routes — JWT authentication enforced per-endpoint via shared auth dependency
app.include_router(properties_router)
app.include_router(listings_router)
