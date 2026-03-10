# Changelog

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
