# Implementation Plan: Platform Baseline, Gateway, and Shared Auth Service

## Codebase Analysis

### Current Project Structure (Key Directories and Files)

```
.
├── doc/                          # Migration documentation (from previous epic)
│   ├── api-compatibility-rules.md
│   ├── cutover-playbook.md
│   ├── domain-boundary-map.md
│   └── postgresql-access-policy.md
├── frontend/                     # Next.js 14 frontend (port 3000)
│   └── src/
│       ├── app/(app)/            # Authenticated routes
│       ├── app/login/            # OTP login page
│       ├── lib/api.ts            # Axios client → http://localhost:8080
│       ├── lib/endpoints.ts      # All API endpoint definitions
│       ├── lib/types.ts          # TypeScript types (camelCase, matches Java responses)
│       └── middleware.ts         # Cookie-based auth guard (hlp_token)
├── src/main/java/com/zcloud/platform/   # Java Spring Boot monolith (port 8080)
│   ├── controller/               # AuthController, PropertyController, ListingController, etc.
│   ├── model/                    # JPA entities (flat package, all domains)
│   ├── repository/               # Spring Data repos
│   ├── security/                 # JwtAuthenticationFilter
│   ├── config/                   # SecurityConfig, CorsConfig, AppConfig, DatabaseConfig
│   ├── service/                  # MasterService (god class), LoanService, MailgunService, etc.
│   └── util/                     # JwtUtil (HMAC-SHA, subject = email), DateUtils, etc.
├── src/main/resources/
│   ├── application.properties    # Supabase DB at port 6543, jwt.secret env var, port 8080
│   ├── application-prod.properties
│   └── schema.sql                # Full monolith schema (PostgreSQL, UUIDs)
├── homelend.sh                   # Local start/stop script (mvn spring-boot:run + npm run dev)
├── Procfile                      # Heroku: java -jar target/*.jar
├── pom.xml                       # Spring Boot 3.2.5, Java 17, jjwt 0.12.6
└── CHANGELOG.md
```

### Existing Patterns and Conventions Observed

**Authentication:**
- OTP-only flow: `POST /api/auth/send-otp` → `POST /api/auth/verify-otp` → JWT token
- JWT: HMAC-SHA, `subject = email`, signed with `JWT_SECRET` env var, 86400s default expiry
- Frontend stores token in `localStorage` (key: `token`) AND cookie (`hlp_token`) for SSR middleware
- 401 response triggers `localStorage.removeItem('token')` + redirect to `/login`
- Auth endpoints (`/api/auth/**`) are public; all others require JWT Bearer token

**API contract (must be preserved):**
- Base URL: `http://localhost:8080` (NEXT_PUBLIC_API_URL env var)
- All paths start with `/api/`
- Responses use camelCase (Java Jackson default)
- Paginated responses: `{ content: [...], totalElements, totalPages, size, number }`
- Error shape: `{ "error": "..." }` on auth errors (from AuthController); `{ "message": "..." }` per api-compatibility-rules.md for domain errors
- HTTP status codes: 200/201/204/400/401/403/404 per api-compatibility-rules.md

**Database:**
- Supabase PostgreSQL, transaction pooler port 6543, `prepareThreshold=0` required
- `DATABASE_URL` env var (asyncpg format for FastAPI: `postgresql+asyncpg://...`)
- Schema: single `public` schema, UUID PKs via `gen_random_uuid()`
- `ddl-auto=none` on Java side; FastAPI must also not execute DDL on startup

**No existing Docker/containerization:**
- No Dockerfile, no docker-compose.yml anywhere in the repo
- Current local dev: `homelend.sh start` (bare-metal Maven + Node)

### Dependencies and Tech Stack in Use

- **Java monolith**: Spring Boot 3.2.5, Java 17, jjwt 0.12.6, PostgreSQL driver, HikariCP
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Axios
- **New FastAPI services**: Python 3.11+, FastAPI, SQLAlchemy async (asyncpg), Pydantic v2, python-jose/PyJWT
- **Gateway**: Nginx (lightweight, matches cutover-playbook.md architecture diagram)
- **Container runtime**: Docker + Docker Compose (local dev)
- **Database**: Supabase PostgreSQL (external; not containerized)

---

## Task Deduplication

The 12 tasks collapse to 4 unique tasks (each repeated 2-3 times):

| Unique Task | Occurrences |
|-------------|-------------|
| **A** – Docker + local deployment baseline | Tasks 1, 7, 9 |
| **B** – API gateway / reverse proxy | Tasks 2, 6, 11 |
| **C** – Shared auth service (FastAPI) | Tasks 3, 8, 12 |
| **D** – Reusable FastAPI service baseline | Tasks 4, 5, 10 |

Each unique task is implemented once.

---

## Implementation Strategy

### Overall Architecture

```
┌─────────────────────────────────────────────────┐
│               docker-compose.yml                 │
│                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐ │
│  │ frontend │   │  nginx   │   │  auth-service │ │
│  │  :3000   │──▶│  :80     │──▶│  :8001        │ │
│  └──────────┘   │(gateway) │   └──────────────┘ │
│                 │          │                     │
│                 │          │──▶ [Java :8080]     │
│                 └──────────┘   (host network or  │
│                                 separate container│
│                                 in compose)       │
└─────────────────────────────────────────────────┘
         │ (all services)
         ▼
   [Supabase PostgreSQL – external]
```

**Key decisions:**
1. **Nginx** as gateway (minimal, well-understood, matches cutover-playbook.md diagrams, no new infrastructure concepts)
2. **FastAPI service baseline** created as `services/shared/` — a template/skeleton that `auth-service` uses directly; it is NOT an installable package, just a reference structure plus a `shared/` module copied-in
3. **Auth service** lives at `services/auth-service/` — a full FastAPI service implementing `POST /api/auth/send-otp` and `POST /api/auth/verify-otp` with identical external contract to Java
4. **Docker Compose** at repo root provides the full local stack; Java monolith is also containerized so everything runs with `docker compose up`
5. The `homelend.sh` script is updated to add a `docker` subcommand as an alternative; bare-metal mode is preserved
6. **Shared Python module**: `services/shared/` contains Pydantic base config (camelCase aliases, error handlers, health endpoint) — copied/reused by each FastAPI service (no pip package overhead)

### Dependency Order

```
Task D (FastAPI baseline) → Task C (auth-service uses baseline)
Task A (Docker/compose)   → Task B (nginx gateway config lives in compose)
Task B depends on knowing service ports → defined in Task D/C
```

Correct build order: **D → C → A → B** (baseline → auth service → containers → gateway config)

---

## Execution Plan

### BUILD Phase

#### Step 1 — FastAPI Service Baseline (Task D)

- [ ] File: `services/shared/__init__.py` — CREATE — empty, marks package
- [ ] File: `services/shared/config.py` — CREATE — `Settings` class using `pydantic-settings`; fields: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION_MS` (default 86400000), `FRONTEND_URL` (default `http://localhost:3000`); loaded from env vars
- [ ] File: `services/shared/database.py` — CREATE — SQLAlchemy async engine factory; `create_async_engine` with `asyncpg`, `pool_size=3`, `connect_args={"server_settings": {"application_name": "service"}}` and `prepared_statement_cache_size=0` (Supabase transaction pooler requirement = prepareThreshold=0 equivalent for asyncpg); `AsyncSession` factory; `get_db` dependency
- [ ] File: `services/shared/models.py` — CREATE — `PageResponse` Pydantic generic model with fields `content`, `totalElements`, `totalPages`, `size`, `number`; uses `model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)` for camelCase output; `ErrorResponse` model with `message: str`
- [ ] File: `services/shared/auth.py` — CREATE — `verify_jwt(token: str, secret: str) -> str` (returns email/subject); uses `python-jose` or `PyJWT`; raises `HTTPException(401)` on invalid token; `get_current_user` FastAPI dependency that reads `Authorization: Bearer` header and calls `verify_jwt`
- [ ] File: `services/shared/exceptions.py` — CREATE — `http_exception_handler` and `validation_exception_handler` functions; maps FastAPI 422 → 400, wraps all client errors as `{"message": "..."}` not `{"detail": "..."}` (per R-ERR-2); returns `{"error": "..."}` shape for auth errors to match Java AuthController exactly
- [ ] File: `services/shared/health.py` — CREATE — `router = APIRouter()`; `GET /health` returns `{"status": "ok", "service": service_name}`; no auth required
- [ ] File: `services/README.md` — CREATE — Documents the shared module, how to use it in a new service, the baseline conventions (camelCase, error shape, health endpoint, DB connection), and port allocation table

#### Step 2 — Auth Service (Task C)

- [ ] File: `services/auth-service/requirements.txt` — CREATE — pins: `fastapi==0.111.0`, `uvicorn[standard]==0.29.0`, `sqlalchemy[asyncio]==2.0.30`, `asyncpg==0.29.0`, `python-jose[cryptography]==3.3.0`, `pydantic-settings==2.2.1`, `httpx==0.27.0` (for Mailgun HTTP calls)
- [ ] File: `services/auth-service/app/__init__.py` — CREATE — empty
- [ ] File: `services/auth-service/app/config.py` — CREATE — imports `Settings` from `shared.config`; adds auth-specific: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN` (default `mg.tallerlabs.ai`); `OTP_EXPIRY_MINUTES=10`, `OTP_RATE_LIMIT_PER_HOUR=5`
- [ ] File: `services/auth-service/app/models.py` — CREATE — SQLAlchemy ORM model `OtpCode` mapping to `otp_codes` table (columns: `id UUID PK`, `email VARCHAR`, `code VARCHAR(6)`, `expires_at TIMESTAMP`, `used BOOLEAN DEFAULT FALSE`, `created_at TIMESTAMP`); uses `MappedColumn` / `mapped_column` (SQLAlchemy 2.0 style)
- [ ] File: `services/auth-service/app/schemas.py` — CREATE — Pydantic schemas: `SendOtpRequest(email: EmailStr)`, `SendOtpResponse(message: str)`, `VerifyOtpRequest(email: EmailStr, code: str)`, `VerifyOtpResponse(token: str, email: str, expiresIn: int)`. All response models use `model_config = ConfigDict(populate_by_name=True)`. Note: `VerifyOtpResponse` uses `expiresIn` (camelCase) to match Java response field exactly.
- [ ] File: `services/auth-service/app/mailgun.py` — CREATE — `send_otp(to_email: str, otp_code: str, api_key: str, domain: str)` async function using `httpx.AsyncClient`; posts to `https://api.mailgun.net/v3/{domain}/messages` with Basic auth; matches Java MailgunService behavior (same email template subject/body structure)
- [ ] File: `services/auth-service/app/router.py` — CREATE — `router = APIRouter(prefix="/api/auth", tags=["auth"])`; implements:
  - `POST /api/auth/send-otp`: validates email, checks rate limit (count OTPs in last hour), generates 6-digit code with `secrets.randbelow(1_000_000)`, saves to `otp_codes`, calls mailgun; returns `{"message": "If this email is registered, a code has been sent."}` or 429/503 errors matching Java shapes
  - `POST /api/auth/verify-otp`: looks up valid unexpired unused OTP, marks used, generates JWT using `JWT_SECRET` + `python-jose`; returns `{"token": ..., "email": ..., "expiresIn": 86400}`. JWT claims: `sub = email`, `iat`, `exp` — HMAC-HS256 to match Java jjwt output
- [ ] File: `services/auth-service/app/main.py` — CREATE — FastAPI app creation; mounts `shared.health.router` (unprotected); mounts `router` from `app.router`; registers exception handlers from `shared.exceptions`; CORS middleware with `FRONTEND_URL`; `lifespan` context manager for DB engine startup (no DDL)
- [ ] File: `services/auth-service/Dockerfile` — CREATE — `FROM python:3.11-slim`; `WORKDIR /app`; copies `requirements.txt` + installs; copies `app/` and `../shared/` (as `shared/`); `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]`
- [ ] File: `services/auth-service/.env.example` — CREATE — documents required env vars: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION_MS`, `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `FRONTEND_URL`
- [ ] File: `services/auth-service/README.md` — CREATE — Service description, endpoints, env vars, how to run locally and with Docker

#### Step 3 — Docker and Local Deployment Baseline (Task A)

- [ ] File: `Dockerfile.java` — CREATE — Multi-stage: stage 1 `FROM maven:3.9-eclipse-temurin-17 AS build`, `mvn package -DskipTests`; stage 2 `FROM eclipse-temurin:17-jre-alpine`, copies JAR, `EXPOSE 8080`, `ENTRYPOINT ["java", "-Dspring.profiles.active=prod", "-jar", "/app/app.jar"]`
- [ ] File: `frontend/Dockerfile` — CREATE — Multi-stage: stage 1 `FROM node:20-alpine AS deps`, `npm ci`; stage 2 `FROM node:20-alpine AS builder`, `npm run build`; stage 3 `FROM node:20-alpine AS runner`, production Next.js server, `EXPOSE 3000`
- [ ] File: `docker-compose.yml` — CREATE — defines services:
  - `java-monolith`: builds `Dockerfile.java`; port `8080:8080`; env_file `.env`; networks `[platform]`
  - `auth-service`: builds `services/auth-service/Dockerfile`; build context includes `services/`; port `8001:8001`; env_file `services/auth-service/.env.example` → override with `.env`; networks `[platform]`; depends_on `[]` (DB is external)
  - `gateway`: `image: nginx:1.25-alpine`; volumes `./gateway/nginx.conf:/etc/nginx/nginx.conf:ro`; port `80:80`; depends_on `[java-monolith, auth-service]`; networks `[platform]`
  - `frontend`: builds `frontend/Dockerfile`; port `3000:3000`; env: `NEXT_PUBLIC_API_URL=http://localhost:80`; depends_on `[gateway]`; networks `[platform]`
  - networks: `platform: driver: bridge`
  - Comment block explaining how to add new services: add new service block + nginx upstream + location block
- [ ] File: `.env.example` — CREATE — All env vars for the full stack: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION_MS`, `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `FRONTEND_URL`, `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, `SPRING_DATASOURCE_PASSWORD`

#### Step 4 — API Gateway Configuration (Task B)

- [ ] File: `gateway/nginx.conf` — CREATE — nginx configuration with:
  - `upstream java_monolith { server java-monolith:8080; }`
  - `upstream auth_service { server auth-service:8001; }`
  - `server { listen 80; }` block with location routing:
    - `location /api/auth/ { proxy_pass http://auth_service; }` — routes auth to FastAPI auth-service
    - `location /api/ { proxy_pass http://java_monolith; }` — all other /api/ routes go to Java
    - `location / { proxy_pass http://frontend:3000; }` — frontend passthrough
  - Proxy headers: `proxy_set_header Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`, `Connection ""`
  - `proxy_http_version 1.1` (required for keepalive)
  - `proxy_read_timeout 60s`, `proxy_connect_timeout 10s`
  - Comment blocks explaining how to cut over additional service areas (add upstream + change location block)
  - Comment: "Smoke validation: after adding a location block, test with curl -I http://localhost/api/{new-path} and verify 200/expected status before deploying to production"
- [ ] File: `gateway/README.md` — CREATE — Documents: routing table (current location→upstream mappings), how to add a new service (step-by-step: add upstream, add location, test), smoke test commands, rollback procedure (revert location block to `java_monolith`), incremental cutover process

#### Step 5 — Update Wiring and Supporting Files

- [ ] File: `homelend.sh` — MODIFY — Add `docker` and `docker-stop` subcommands that run `docker compose up -d` / `docker compose down`; keep existing `start`/`stop`/`status` for bare-metal; update help text
- [ ] File: `.gitignore` — MODIFY — Add Python-specific entries: `**/__pycache__/`, `**/*.pyc`, `**/*.pyo`, `services/**/.venv/`, `services/**/.env`, `.env`, `**/.pytest_cache/`
- [ ] File: `CHANGELOG.md` — MODIFY — Append entry for this epic's additions

---

### TEST Phase

There are no explicit test tasks in this epic. However, the acceptance criteria for Task B ("Basic smoke validation is defined for route changes") requires that smoke test commands be documented in `gateway/README.md`. The plan covers this in the gateway README rather than creating test files.

If tests are added in a future epic, the baseline structure supports:
- `services/auth-service/tests/test_router.py` — FastAPI `TestClient` tests for send-otp and verify-otp
- Contract smoke tests via `curl` commands documented in `gateway/README.md`

---

### DOCS Phase

Documentation is embedded in the BUILD phase above, but summarized here:

- [ ] `services/README.md` — Shared module docs + port allocation + new service creation guide
- [ ] `services/auth-service/README.md` — Auth service: endpoints, env vars, local run, Docker run
- [ ] `services/auth-service/.env.example` — Env var reference for auth service
- [ ] `.env.example` — Env var reference for full stack
- [ ] `gateway/README.md` — Routing table, add-service guide, smoke test commands, rollback steps
- [ ] `CHANGELOG.md` — Updated with this epic's additions

---

## File-by-File Execution Order (Dependency-First)

```
Phase 1 – Shared baseline (no dependencies):
  1.  services/shared/__init__.py
  2.  services/shared/config.py
  3.  services/shared/database.py
  4.  services/shared/models.py
  5.  services/shared/auth.py
  6.  services/shared/exceptions.py
  7.  services/shared/health.py
  8.  services/README.md

Phase 2 – Auth service (depends on shared/):
  9.  services/auth-service/requirements.txt
  10. services/auth-service/app/__init__.py
  11. services/auth-service/app/config.py
  12. services/auth-service/app/models.py
  13. services/auth-service/app/schemas.py
  14. services/auth-service/app/mailgun.py
  15. services/auth-service/app/router.py
  16. services/auth-service/app/main.py
  17. services/auth-service/Dockerfile
  18. services/auth-service/.env.example
  19. services/auth-service/README.md

Phase 3 – Container baseline (depends on knowing all services):
  20. Dockerfile.java
  21. frontend/Dockerfile
  22. .env.example
  23. docker-compose.yml

Phase 4 – Gateway (depends on docker-compose service names):
  24. gateway/nginx.conf
  25. gateway/README.md

Phase 5 – Wiring updates:
  26. homelend.sh  (MODIFY)
  27. .gitignore   (MODIFY)
  28. CHANGELOG.md (MODIFY)
```

---

## Risks and Considerations

### 1. JWT Token Interoperability (Critical)
The Java monolith uses `io.jsonwebtoken` (jjwt 0.12.6) with HMAC-SHA256 and `subject = email`. The FastAPI auth-service must produce tokens with identical claims structure (`sub`, `iat`, `exp`) and the same signing algorithm so that:
- Tokens issued by FastAPI auth-service are accepted by the Java monolith's `JwtAuthenticationFilter`
- Tokens issued by Java (if any fallback occurs) are validated by the FastAPI auth-service's `get_current_user` dependency

**Implementation note:** Use `python-jose` with `algorithm="HS256"`, `sub=email`. Do NOT add extra claims. The `JWT_SECRET` must be identical between services.

### 2. OTP Error Response Shape Mismatch
The Java `AuthController` returns `{"error": "..."}` for auth errors (not `{"message": "..."}` as defined in api-compatibility-rules.md). The frontend login page reads `response.data.error`. The FastAPI auth-service must match the Java shape exactly for the login flow to work:
- `send-otp` 429: `{"error": "Too many requests..."}`
- `send-otp` 503: `{"error": "Failed to send verification email..."}`
- `verify-otp` 401: `{"error": "Invalid or expired code."}`
- `verify-otp` 200: `{"token": ..., "email": ..., "expiresIn": 86400}`

This is a deliberate exception to R-ERR-2 for `/api/auth/*` endpoints only.

### 3. Nginx Routing Auth vs. All /api/ Paths
The `location /api/auth/` block must be declared **before** `location /api/` in nginx.conf for correct prefix matching. Nginx uses longest-prefix matching so `location /api/auth/` will correctly take priority over `location /api/` even if declared after — but explicit ordering is cleaner and avoids confusion.

### 4. Supabase Transaction Pooler (asyncpg)
The `prepareThreshold=0` HikariCP setting on the Java side corresponds to `prepared_statement_cache_size=0` in asyncpg. This must be passed via `connect_args` in `create_async_engine`. The `DATABASE_URL` for FastAPI must be `postgresql+asyncpg://user:pass@host:6543/postgres`.

### 5. Docker Build Context for auth-service
The auth-service `Dockerfile` needs access to both `services/auth-service/` and `services/shared/`. The `docker-compose.yml` build context must be set to `./services` (not `./services/auth-service`) so the shared module is accessible during the Docker build. The Dockerfile then does `COPY shared/ ./shared/` and `COPY auth-service/app/ ./app/`.

### 6. Java Monolith Container (Dockerfile.java)
The Java monolith build requires Maven, which requires internet access (Maven Central) during `docker build`. For CI/production use, a `.m2` cache mount should be used. For local dev, the image can be pre-built and the compose file can reference it. The plan uses a standard multi-stage build; teams with slow internet can substitute `build: .` with `image: zcloud/java-monolith:latest` after a one-time build.

### 7. Frontend NEXT_PUBLIC_API_URL
In the Docker Compose setup, the frontend calls the gateway at `http://localhost:80` (exposed on host). The `NEXT_PUBLIC_API_URL` must be set to `http://localhost` (port 80 is default). In the bare-metal setup (`homelend.sh start`), it remains `http://localhost:8080` pointing directly to Java. The `next.config.mjs` may need no change since NEXT_PUBLIC_ vars are baked at build time — the compose frontend service must have this env var set at build time, not just runtime. The compose file uses `build.args` for this.

### 8. Task 4/5/10 are Identical (FastAPI Baseline)
Tasks 4, 5, and 10 are word-for-word identical. They are implemented once as `services/shared/`. The acceptance criteria "suitable for auth and domain services" is satisfied because the auth-service directly uses this shared module, demonstrating fitness for purpose.

### 9. No External Database Container
Supabase PostgreSQL is an external managed service. The docker-compose.yml intentionally does NOT include a local PostgreSQL container. All services connect to the external Supabase instance via `DATABASE_URL`. This is consistent with the existing project setup (the Java monolith already uses Supabase in development). A comment in docker-compose.yml explains this choice.

### 10. Incremental Service Addition
The docker-compose.yml includes a commented-out template block showing how to add a new service:
```yaml
# new-service:
#   build:
#     context: ./services
#     dockerfile: new-service/Dockerfile
#   ports:
#     - "8002:8002"
#   env_file: .env
#   networks: [platform]
```
And a corresponding nginx upstream + location block template in `gateway/README.md`.
