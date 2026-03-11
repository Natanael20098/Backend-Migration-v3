# client-crm-service Dockerfile
#
# Build context must be ./services (not ./services/client-crm-service)
# so the shared/ module is accessible.
# In docker-compose.yml:
#   build:
#     context: ./services
#     dockerfile: client-crm-service/Dockerfile
#
# Environment variables required at runtime:
#   DATABASE_URL   — PostgreSQL connection string (asyncpg format)
#   JWT_SECRET     — HS256 signing secret (min 32 chars)
#   FRONTEND_URL   — Allowed CORS origin
#
# Exposed port: 8005

FROM python:3.11-slim

WORKDIR /app

# Create a non-root system user and group for running the service
RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 --no-create-home appuser

# Install dependencies (as root — pip installs to /usr/local, readable by all)
COPY client-crm-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module and application with correct ownership
COPY --chown=appuser:appuser shared/ ./shared/
COPY --chown=appuser:appuser client-crm-service/app/ ./app/

# Switch to non-root user before running the process
USER appuser

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
