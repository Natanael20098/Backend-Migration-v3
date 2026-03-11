# Implementation Plan: Harden Container Runtime and Dockerfiles

## Codebase Analysis

### Current Project Structure (Key Directories and Files)
```
services/
  auth-service/Dockerfile          — port 8001, runs as root
  client-crm-service/Dockerfile    — port 8005, runs as root
  closing-service/Dockerfile       — port 8004, runs as root
  property-listing-service/Dockerfile — port 8002, runs as root
  underwriting-service/Dockerfile  — port 8003, runs as root
  shared/health.py                 — exposes GET /health returning {"status":"ok","service":"<name>"}
frontend/Dockerfile                — ALREADY has non-root user (nextjs:nodejs, uid 1001)
docker-compose.yml                 — build context is ./services for all FastAPI services
```

### Existing Patterns and Conventions Observed

**All 5 FastAPI Dockerfiles share an identical pattern:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY <service>/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared/ ./shared/
COPY <service>/app/ ./app/
EXPOSE <port>
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "<port>"]
```
- Build context: `./services` (required so `shared/` is accessible)
- None of them define a non-root user — all currently run as root
- None of them have a HEALTHCHECK directive

**Frontend Dockerfile (already hardened) uses:**
```dockerfile
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
COPY --chown=nextjs:nodejs ...
USER nextjs
```
This is the established project pattern for non-root users.

**Health endpoint:** Every FastAPI service mounts `GET /health` via `shared/health.py`'s `make_health_router()`. Returns `{"status": "ok", "service": "<name>"}`. This is the canonical low-cost health target.

**docker-compose.yml:** All services use `restart: unless-stopped`, no healthcheck entries currently defined at compose level. Health checks belong in the Dockerfiles per the task requirement.

### Dependencies and Tech Stack
- **FastAPI services:** `python:3.11-slim` base image, uvicorn server
- **Frontend:** `node:20-alpine`, Next.js 14, multi-stage build
- **Gateway:** `nginx:1.25-alpine` (not a custom Dockerfile — not in scope)

---

## Implementation Strategy

### Overall Approach

**Task 2 defines the secure baseline pattern** — it must be understood first because Tasks 1 and 4 are applications of that same pattern. There is no separate "baseline file" to create (the task says "a reusable Dockerfile pattern", not a shared base image or template file). The pattern is simply the hardened Dockerfile structure that will be replicated across all services.

**The secure FastAPI Dockerfile pattern:**
1. `FROM python:3.11-slim`
2. `WORKDIR /app`
3. Create non-root system user and group (`appuser`, gid/uid 1001) in a single `RUN` layer
4. Install dependencies as root (before switching user — pip install to system, no chown issues)
5. Copy files with `--chown=appuser:appuser`
6. `USER appuser`
7. `EXPOSE <port>`
8. Document env vars and port in Dockerfile comments
9. `HEALTHCHECK` directive targeting `GET /health`
10. `CMD ["uvicorn", ...]`

**Non-root user implementation:** Use `addgroup` + `adduser` (available in slim images):
```dockerfile
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser
```

**HEALTHCHECK parameters:** Use curl (available in python:3.11-slim via apt) or use Python's built-in `urllib` to avoid installing extra packages. Best approach: install `curl` during the build in a single RUN layer with pip, OR use Python directly:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:<port>/health')" || exit 1
```
This avoids adding `curl` as a dependency and keeps the image minimal. `python:3.11-slim` includes Python, so this works without any extra installs.

**File ownership:** Since `WORKDIR /app` is created before user exists, chown must happen at COPY time: `COPY --chown=appuser:appuser`.

**Task 3 (HEALTHCHECK):** The frontend already has a non-root user. Its health check should target the Next.js server. The Next.js app listens on port 3000. There is no explicit `/health` endpoint in the frontend code; however, the root path `/` or the Next.js built-in status would work. Use `http://localhost:3000/` or use Node's built-in. Given the project convention (all FastAPI services have `/health`), use `wget` which is available in `node:20-alpine`, or `node` itself:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null || exit 1
```
`wget` is available in `node:20-alpine` by default.

**Task dependency order:**
1. Understand the baseline pattern (Task 2 — defines the pattern applied everywhere)
2. Apply to auth-service (Task 1 — single service, critical)
3. Apply HEALTHCHECK to frontend (Task 3 — frontend already has non-root, just adds HEALTHCHECK)
4. Apply baseline + HEALTHCHECK to remaining 4 services (Task 4 + Task 3 combined)
5. Update CHANGELOG.md

### Shared Foundations
- Non-root user: `appuser` (gid/uid 1001) — consistent across all FastAPI services
- Health check command: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:<port>/health')"` with `|| exit 1`
- HEALTHCHECK timing: `--interval=30s --timeout=5s --start-period=10s --retries=3`

---

## Execution Plan (by phase)

### BUILD Phase

All changes are Dockerfile modifications only. No Python source files, no docker-compose.yml changes, no new files beyond CHANGELOG.md.

**Step 1 — Apply secure baseline to `auth-service` (Task 1 + Task 2 + Task 3)**
- [ ] File: `services/auth-service/Dockerfile` — **MODIFY** — Add non-root user (`appuser`, uid/gid 1001), use `--chown=appuser:appuser` on COPY instructions, add `USER appuser`, add `HEALTHCHECK` targeting `http://localhost:8001/health`, document env vars (DATABASE_URL, JWT_SECRET, JWT_EXPIRATION_MS, MAILGUN_API_KEY, MAILGUN_DOMAIN, FRONTEND_URL) and port 8001 in comments.

**Step 2 — Apply secure baseline to `property-listing-service` (Task 4 + Task 3)**
- [ ] File: `services/property-listing-service/Dockerfile` — **MODIFY** — Same hardening pattern: non-root user, `--chown`, `USER appuser`, `HEALTHCHECK` targeting `http://localhost:8002/health`, document env vars (DATABASE_URL, JWT_SECRET, FRONTEND_URL) and port 8002.

**Step 3 — Apply secure baseline to `underwriting-service` (Task 4 + Task 3)**
- [ ] File: `services/underwriting-service/Dockerfile` — **MODIFY** — Same hardening pattern: non-root user, `--chown`, `USER appuser`, `HEALTHCHECK` targeting `http://localhost:8003/health`, document env vars and port 8003.

**Step 4 — Apply secure baseline to `closing-service` (Task 4 + Task 3)**
- [ ] File: `services/closing-service/Dockerfile` — **MODIFY** — Same hardening pattern: non-root user, `--chown`, `USER appuser`, `HEALTHCHECK` targeting `http://localhost:8004/health`, document env vars and port 8004.

**Step 5 — Apply secure baseline to `client-crm-service` (Task 4 + Task 3)**
- [ ] File: `services/client-crm-service/Dockerfile` — **MODIFY** — Same hardening pattern: non-root user, `--chown`, `USER appuser`, `HEALTHCHECK` targeting `http://localhost:8005/health`, document env vars and port 8005.

**Step 6 — Add HEALTHCHECK to frontend (Task 3)**
- [ ] File: `frontend/Dockerfile` — **MODIFY** — Add `HEALTHCHECK` directive to the runner stage, targeting `http://localhost:3000/`. Use `wget -qO- http://localhost:3000/ > /dev/null` (wget is available in `node:20-alpine`). Timing: `--interval=30s --timeout=5s --start-period=15s --retries=3`. The non-root user is already present — no other changes needed.

**Step 7 — Update CHANGELOG.md**
- [ ] File: `CHANGELOG.md` — **MODIFY** — Append new `[Unreleased]` entry documenting all Dockerfile hardening changes: non-root user added to 5 FastAPI services, HEALTHCHECK added to all 6 images (5 FastAPI + 1 frontend).

---

### Exact Dockerfile Structure for Each FastAPI Service

The final structure for each FastAPI service Dockerfile (illustrating `auth-service` at port 8001):

```dockerfile
# Build context must be ./services (not ./services/auth-service)
# so that the shared/ module is accessible.
# In docker-compose.yml:
#   build:
#     context: ./services
#     dockerfile: auth-service/Dockerfile
#
# Environment variables required at runtime:
#   DATABASE_URL       — PostgreSQL connection string (asyncpg format)
#   JWT_SECRET         — HS256 signing secret (min 32 chars)
#   JWT_EXPIRATION_MS  — Token lifetime in milliseconds (default: 86400000)
#   MAILGUN_API_KEY    — Mailgun API key for OTP email delivery
#   MAILGUN_DOMAIN     — Mailgun sending domain
#   FRONTEND_URL       — Allowed CORS origin
#
# Exposed port: 8001

FROM python:3.11-slim

WORKDIR /app

# Create a non-root system user and group for running the service
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser

# Install dependencies (as root — pip installs to /usr/local, readable by all)
COPY auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module and application with correct ownership
COPY --chown=appuser:appuser shared/ ./shared/
COPY --chown=appuser:appuser auth-service/app/ ./app/

# Switch to non-root user before running the process
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

The `requirements.txt` file is copied before the chown'd files — it is a temporary build artifact (overwritten by each service's own copy) and is only needed during `pip install`. It does not need to be owned by `appuser`.

Repeat with appropriate service name, env vars, and port for each of the 5 FastAPI services.

---

### Frontend HEALTHCHECK Addition

Only the runner stage needs modification. Add between `USER nextjs` and `EXPOSE 3000`:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/ > /dev/null || exit 1
```

The `start-period` is slightly longer (15s vs 10s) for Next.js since the Node.js server takes a moment to initialize the compiled bundle.

---

### TEST Phase

No automated test files are required by any acceptance criterion. Manual/CI validation criteria per task:

- **Task 1:** `docker build -f services/auth-service/Dockerfile --build-context services ./services && docker run --rm <image> id` should show uid=1001(appuser) not root.
- **Tasks 1, 4:** Each service's `GET /health` endpoint should return 200 after startup.
- **Task 3:** `docker inspect <image> | grep -A5 Healthcheck` should show a non-null healthcheck on all 6 images.

No new test files need to be created — the acceptance criteria are satisfied by the Dockerfile changes themselves and can be validated during `docker build` + `docker run` in CI.

---

### DOCS Phase

- [ ] File: `CHANGELOG.md` — **MODIFY** — Append entry documenting:
  - Security: All FastAPI service containers now run as non-root user `appuser` (uid/gid 1001)
  - Added: HEALTHCHECK directives to all 5 FastAPI Dockerfiles (targeting `GET /health`) and the frontend Dockerfile (targeting `GET /`)
  - Changed: List each Dockerfile modified with before/after summary

---

## Risks and Considerations

### File Ownership and WORKDIR
`WORKDIR /app` creates the directory as root (before `USER appuser`). The `--chown=appuser:appuser` flag on each `COPY` instruction ensures the application files are owned by `appuser`. Since uvicorn only reads files (no write to `/app` at runtime), this is sufficient. If any service writes temp files to `/app`, a `RUN chown appuser:appuser /app` after WORKDIR would be needed — inspection of the service code shows no runtime writes to the working directory, so this is not needed.

### pip install as root
`pip install` runs as root, installing to `/usr/local/lib/python3.11/site-packages/`. This is readable by all users including `appuser`. This is correct and intentional — switching to non-root before pip install would require `--user` installs with PATH changes, which is unnecessary complexity.

### requirements.txt COPY ownership
The `COPY auth-service/requirements.txt .` line copies to `/app/requirements.txt`. This file is only needed during the build step (`RUN pip install`). It does not need `--chown` since it's not accessed at runtime. Keeping it without chown is correct.

### Health check for frontend
The frontend has no dedicated `/health` route. Using `GET /` is valid — it's the cheapest available endpoint. The acceptance criterion says "valid, low-cost endpoints," and the root path of Next.js returns 200 for a running server. `wget` is confirmed available in `node:20-alpine`.

### No changes to docker-compose.yml
The task asks for HEALTHCHECK in Dockerfiles, not in docker-compose.yml. Docker Compose can override healthchecks, but since none are defined in docker-compose.yml, the Dockerfile directives will be active. No changes to docker-compose.yml are needed.

### No base image creation
Task 2 says "a single reusable secure Dockerfile pattern" — this means a documented pattern (documented in this plan and visible in each Dockerfile's structure), not a shared base image. Creating a shared base image would require a registry, additional build steps, and is not implied by the task. Each Dockerfile is self-contained.

### Consistency of `appuser` across services
Using the same username (`appuser`) and uid/gid (1001) across all FastAPI services ensures image structure is consistent (Task 4 acceptance criterion: "image structure remains consistent across services"). The frontend uses `nextjs:nodejs` (uid 1001) — this is a different username but same uid. There is no conflict since they run in separate containers.
