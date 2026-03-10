# Build context must be ./services (not ./services/auth-service)
# so that the shared/ module is accessible.
# In docker-compose.yml:
#   build:
#     context: ./services
#     dockerfile: auth-service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared module
COPY shared/ ./shared/

# Copy service application
COPY auth-service/app/ ./app/

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
