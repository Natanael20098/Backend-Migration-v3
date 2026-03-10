# Platform Services

This directory contains all FastAPI microservices extracted from the Java monolith
during the backend migration, plus the shared module they all depend on.

## Directory Structure

```
services/
├── shared/              # Shared Python module (copied into each service's Docker image)
│   ├── __init__.py
│   ├── config.py        # Settings base class (pydantic-settings)
│   ├── database.py      # SQLAlchemy async engine + session factory
│   ├── models.py        # PageResponse, ErrorResponse, CamelModel base
│   ├── auth.py          # JWT verification + FastAPI dependency
│   ├── exceptions.py    # Unified HTTP + validation exception handlers
│   └── health.py        # GET /health router factory
├── auth-service/        # OTP authentication service (port 8001)
└── README.md            # This file
```

## Port Allocation

| Service        | Port | Status     | Notes                              |
|----------------|------|------------|------------------------------------|
| Java monolith  | 8080 | Active     | Spring Boot legacy                 |
| auth-service   | 8001 | Active     | OTP + JWT, migrated from Java      |
| *(next service)*| 8002 | Planned    | Add here when creating new service |
| nginx gateway  | 80   | Active     | Ingress, routes to above services  |
| frontend       | 3000 | Active     | Next.js                            |

## The Shared Module

The `shared/` package provides the common baseline for all FastAPI services:

- **`config.py`** — `Settings` base class via `pydantic-settings`. Extend it in each
  service to add service-specific env vars.
- **`database.py`** — Async SQLAlchemy engine factory pre-configured for Supabase
  transaction pooler (`prepared_statement_cache_size=0`).
- **`models.py`** — `CamelModel` (camelCase output), `PageResponse[T]` (matches
  Spring Data Page shape), `ErrorResponse`, `AuthErrorResponse`.
- **`auth.py`** — `verify_jwt(token, secret) -> email` and `make_get_current_user(secret)`
  FastAPI dependency factory. Uses HMAC-HS256 matching the Java jjwt config.
- **`exceptions.py`** — Exception handlers that map 422→400 and produce the correct
  error shape (`{"error":"..."}` for auth paths, `{"message":"..."}` for others).
- **`health.py`** — `make_health_router(service_name)` returns a router with
  `GET /health` → `{"status":"ok","service":"<name>"}`.

### Why Copied, Not Installed

The shared module is copied into each service's Docker image at build time
(see each service's `Dockerfile`). This avoids creating a private PyPI package
for a small number of files, keeps the dependency graph flat, and makes
each service image self-contained. When `shared/` changes, rebuild affected
service images.

## Creating a New Service

Follow these steps when extracting a new domain from the Java monolith:

### 1. Create the service directory

```
services/
└── my-service/
    ├── app/
    │   ├── __init__.py
    │   ├── config.py     # Extend shared.config.Settings
    │   ├── models.py     # SQLAlchemy ORM models (no DDL on startup)
    │   ├── schemas.py    # Pydantic request/response schemas
    │   ├── router.py     # APIRouter with your endpoints
    │   └── main.py       # FastAPI app + wiring
    ├── Dockerfile
    ├── requirements.txt
    └── .env.example
```

### 2. Service config (`app/config.py`)

```python
from shared.config import Settings as BaseSettings

class Settings(BaseSettings):
    MY_EXTRA_VAR: str = ""

settings = Settings()
```

### 3. Service main (`app/main.py`)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from shared.health import make_health_router
from shared.exceptions import http_exception_handler, validation_exception_handler
from app.config import settings
from app.router import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: initialize DB engine, etc.
    yield
    # shutdown: dispose engine, etc.

app = FastAPI(title="My Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.FRONTEND_URL], ...)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(make_health_router("my-service"))
app.include_router(router)
```

### 4. Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY my-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY my-service/app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

Build context in `docker-compose.yml` must be `./services` (not `./services/my-service`).

### 5. Register in docker-compose.yml

```yaml
my-service:
  build:
    context: ./services
    dockerfile: my-service/Dockerfile
  ports:
    - "8002:8002"
  env_file: .env
  networks: [platform]
```

### 6. Add nginx route in `gateway/nginx.conf`

```nginx
upstream my_service { server my-service:8002; }

# In server block — add BEFORE the generic /api/ location:
location /api/my-domain/ {
    proxy_pass http://my_service;
    include /etc/nginx/proxy_params.conf;
}
```

See `gateway/README.md` for full instructions and smoke test commands.

## Conventions

| Convention | Value |
|------------|-------|
| Response JSON casing | camelCase (use `CamelModel` base) |
| Pagination shape | `{content, totalElements, totalPages, size, number}` |
| Domain error body | `{"message": "..."}` |
| Auth error body | `{"error": "..."}` (auth paths only) |
| JWT algorithm | HMAC-HS256 (`sub = email`) |
| DB DDL on startup | **Never** — schema managed by Java side |
| Health endpoint | `GET /health` — no auth required |
| Port range | 8001+ for FastAPI services |
