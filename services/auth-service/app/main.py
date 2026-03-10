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
from app.router import router, _get_db


# Module-level engine and session factory — initialized on startup
_engine = None
_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine, _session_factory

    # Startup: create DB engine (no DDL — schema is managed by the Java side)
    _engine = create_engine(settings.DATABASE_URL, service_name="auth-service")
    _session_factory = create_session_factory(_engine)

    # Override the placeholder DB dependency in the router
    async def get_db() -> AsyncSession:
        async with _session_factory() as session:
            yield session

    app.dependency_overrides[_get_db] = get_db

    yield

    # Shutdown: dispose engine
    if _engine is not None:
        await _engine.dispose()


app = FastAPI(
    title="Auth Service",
    description="OTP-based authentication service. Implements /api/auth/send-otp and /api/auth/verify-otp with identical contract to the Java monolith AuthController.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers — must be registered before routes
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Health endpoint — no auth required
app.include_router(make_health_router("auth-service"))

# Auth routes
app.include_router(router)
