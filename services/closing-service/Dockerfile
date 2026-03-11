# closing-service Dockerfile
#
# Build context must be ./services (not ./services/closing-service)
# so the shared/ module is accessible.
#
# In docker-compose.yml:
#   build:
#     context: ./services
#     dockerfile: closing-service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY closing-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared module (required by app/config.py, app/main.py, etc.)
COPY shared/ ./shared/

# Copy the service application
COPY closing-service/app/ ./app/

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
