# property-listing-service Dockerfile
#
# Build context must be ./services (not ./services/property-listing-service)
# so the shared/ module is accessible.
#
# In docker-compose.yml:
#   build:
#     context: ./services
#     dockerfile: property-listing-service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY property-listing-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared module (required by app/config.py, app/main.py, etc.)
COPY shared/ ./shared/

# Copy the service application
COPY property-listing-service/app/ ./app/

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
