# Changelog

## [Unreleased] – 2025-01-31 18:00

### Security
- **Host header injection remediated in nginx gateway**: `proxy_set_header Host $host` (attacker-controlled) removed from `gateway/nginx.conf`. Every `proxy_pass` location now sets an explicit, static `Host` header (`<container-name>:<port>`). The `server_name` directive is tightened from a catch-all `_` to an explicit list (`localhost 127.0.0.1`); requests with any other `Host` are rejected by nginx before reaching any upstream service.

### Added
- `doc/gateway-host-header-audit.md` — Full audit of the flagged `$host` usage: lists every affected directive and location, enumerates attack classes enabled by blind Host trust (injection, cache poisoning, SSRF, virtual-host confusion), and documents the explicit-host-per-location replacement strategy with a verification checklist.
- `gateway/tests/test_host_header.sh` — Executable behavioral test script covering: valid Host values (`localhost`, `127.0.0.1`) are routed correctly to all five services and the frontend; injected Host values (`attacker.com`, `evil.example.com`, unexpected port) are rejected and do not return HTTP 200; empty Host header does not cause a 5xx error; upstream auth health endpoint responds with valid JSON regardless of inbound Host header.

### Changed
- `gateway/nginx.conf` — Removed server-level `proxy_set_header Host $host`. Added per-location `proxy_set_header Host <upstream-name>:<port>` for all twelve location blocks. Tightened `server_name` from `_` to `localhost 127.0.0.1`. Added security note comment at the top of the file referencing the audit document.

## [Unreleased] – 2025-01-31 16:00

### Security
- **Non-root container runtime**: All five FastAPI microservice containers now run as a non-root system user (`appuser`, uid/gid 1001). Previously all containers ran as root. The user is created in a single `RUN` layer using `addgroup`/`adduser` system flags. Application files are copied with `--chown=appuser:appuser`; Python dependencies are installed as root to `/usr/local` (world-readable) before the user switch, requiring no PATH changes.

### Added
- `HEALTHCHECK` directives added to all six service images:
  - `services/auth-service/Dockerfile` — `GET http://localhost:8001/health` via `python -c "import urllib.request; ..."` (no extra packages needed)
  - `services/property-listing-service/Dockerfile` — `GET http://localhost:8002/health`
  - `services/underwriting-service/Dockerfile` — `GET http://localhost:8003/health`
  - `services/closing-service/Dockerfile` — `GET http://localhost:8004/health`
  - `services/client-crm-service/Dockerfile` — `GET http://localhost:8005/health`
  - `frontend/Dockerfile` — `GET http://localhost:3000/` via `wget` (available in `node:20-alpine`); `start-period` is 15s (vs 10s for FastAPI) to allow Next.js bundle initialisation
- All FastAPI Dockerfiles now document required runtime environment variables and exposed port in header comments.

### Changed
- `services/auth-service/Dockerfile` — Added `appuser` system user, `--chown=appuser:appuser` on COPY instructions, `USER appuser`, `HEALTHCHECK`, and runtime env var documentation.
- `services/property-listing-service/Dockerfile` — Same hardening applied.
- `services/underwriting-service/Dockerfile` — Same hardening applied.
- `services/closing-service/Dockerfile` — Same hardening applied.
- `services/client-crm-service/Dockerfile` — Same hardening applied.
- `frontend/Dockerfile` — Added `HEALTHCHECK` directive (non-root user `nextjs:nodejs` was already present).

## [Unreleased] – 2025-01-31 14:00

### Security
- **CVE-2022-29217 remediated**: Replaced `python-jose[cryptography]==3.3.0` with `PyJWT==2.9.0` in all services that required a JWT library. `python-jose` is no longer present in any service's `requirements.txt`. PyJWT is actively maintained and does not require the `[cryptography]` extra for HS256.

### Changed
- `services/shared/auth.py` — Migrated from `from jose import JWTError, jwt` to `import jwt`; exception handler updated from `except JWTError:` to `except jwt.PyJWTError:`. Call signatures (`jwt.decode` / `jwt.encode`) are identical in PyJWT 2.x — no behavior change.
- `services/auth-service/app/router.py` — Migrated from `from jose import jwt` to `import jwt`. Token issuance logic unchanged.
- `services/auth-service/requirements.txt` — Replaced `python-jose[cryptography]==3.3.0` with `PyJWT==2.9.0`; added `pytest==8.2.0` for running unit tests.
- `services/client-crm-service/requirements.txt` — Replaced `python-jose[cryptography]==3.3.0` with `PyJWT==2.9.0`.
- `services/closing-service/requirements.txt` — Replaced `python-jose[cryptography]==3.3.0` with `PyJWT==2.9.0`.
- `services/underwriting-service/requirements.txt` — Replaced `python-jose[cryptography]==3.3.0` with `PyJWT==2.9.0`.
- `services/property-listing-service/requirements.txt` — Removed `python-jose[cryptography]==3.3.0` with **no replacement**. This service has no JWT operations and no import of `shared.auth`; the dependency was an unused copy-paste artifact.

### Added
- `doc/jwt-validation-policy.md` — Platform-wide JWT validation policy. Documents the allowed algorithm (HS256 only, never input-driven), required library (PyJWT ≥ 2.9.0), validated claims (`sub`, `exp`), where validation must occur (`shared/auth.py::verify_jwt` exclusively), token issuance ownership (`auth-service` only), error behavior (HTTP 401 for all failure modes), secret management requirements, and the per-service dependency inventory and strategy.
- `services/auth-service/tests/test_jwt.py` — 6 JWT unit tests: encode/decode round trip, expired token (401), invalid signature (401), wrong algorithm (401), missing `sub` claim (401), algorithm-not-input-driven policy enforcement.
- `services/auth-service/tests/__init__.py` — Package marker for test discovery.
- `services/auth-service/pytest.ini` — pytest configuration: `testpaths = tests`, `pythonpath = ..` (makes `services/shared` importable during test runs).

## [Unreleased] – 2025-01-31 10:00

### Added
- `services/shared/` — Reusable FastAPI service baseline module (`config.py`, `database.py`, `models.py`, `auth.py`, `exceptions.py`, `health.py`). Provides camelCase response models, async SQLAlchemy engine factory (Supabase-compatible), JWT verification (HMAC-HS256 matching Java jjwt), unified exception handlers (422→400, `{"error"}` for auth paths, `{"message"}` for others), and health endpoint factory.
- `services/auth-service/` — FastAPI OTP authentication service (port 8001). Implements `POST /api/auth/send-otp` and `POST /api/auth/verify-otp` with identical external contract to the Java `AuthController`. Issues JWT tokens compatible with the Java `JwtAuthenticationFilter`. Includes rate limiting, OTP expiry, and Mailgun email delivery.
- `services/README.md` — Documents the shared module, port allocation table, and step-by-step guide for creating new FastAPI services.
- `services/auth-service/README.md` — Auth service endpoint reference, env vars, local and Docker run instructions, otp_codes migration SQL, smoke tests.
- `services/auth-service/.env.example` — Environment variable reference for the auth service.
- `gateway/nginx.conf` — nginx API gateway configuration. Routes `/api/auth/` to the FastAPI auth service, all other `/api/` traffic to the Java monolith, and `/` to the Next.js frontend. Supports incremental cutover by adding upstream + location blocks.
- `gateway/README.md` — Routing table, step-by-step instructions for adding new services, smoke test commands, rollback procedure, incremental cutover process.
- `Dockerfile.java` — Multi-stage Docker build for the Java Spring Boot monolith (Maven build + JRE runtime).
- `frontend/Dockerfile` — Multi-stage Docker build for the Next.js frontend (deps, build, runner stages; bakes `NEXT_PUBLIC_API_URL` at build time).
- `docker-compose.yml` — Local development stack: java-monolith, auth-service, gateway (nginx), frontend. External Supabase database is not containerized. Includes a commented template for adding new services.
- `.env.example` — Full-stack environment variable reference covering database, JWT, Mailgun, CORS, and frontend URL.
- `homelend.sh` — Added `docker` and `docker-stop` subcommands (`docker compose up -d` / `docker compose down`) alongside existing bare-metal `start`/`stop`/`restart`/`status` commands.
- `.gitignore` — Added Python-specific entries: `__pycache__/`, `*.pyc`, `*.pyo`, `.venv/`, `.env`, `.pytest_cache/`.

## [Unreleased] – 2025-01-30 12:00

### Added
- `doc/api-compatibility-rules.md` — Explicit API compatibility rules for frontend-preserving migration covering URLs, HTTP methods, request/response payloads, status codes, authentication, error shapes, known exceptions, non-goals, and the approval process for frontend-impacting changes. Reusable by all migration epics.
- `doc/domain-boundary-map.md` — Legacy backend domain and service boundary map. Maps Java monolith packages (`com.zcloud.platform`) to proposed FastAPI service ownership across auth, property/listing, client/CRM, loan origination, underwriting, closing, and admin domains. Identifies first-wave vs later-wave migration candidates, shared concerns, and cross-domain touchpoints.
- `doc/postgresql-access-policy.md` — Shared PostgreSQL access policy for parallel-run migration. Defines DB usage rules, per-table write ownership by migration wave, denormalized column handling, schema change process (MDR-gated), and FastAPI connection configuration requirements.
- `doc/cutover-playbook.md` — Reusable service-by-service cutover playbook. Covers pre-cutover readiness (routing, contracts, DB, smoke tests, rollback prep), traffic shift procedure, post-cutover validation (immediate and 24-hour), rollback steps, and Java retirement criteria. Domain teams create a Cutover Record per service without redefining the master checklist.
