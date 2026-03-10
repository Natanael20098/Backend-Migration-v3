# Auth Service

FastAPI implementation of the HomeLend Pro authentication service.
Replaces the `AuthController` in the Java monolith with identical external API contracts.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/send-otp` | None | Send 6-digit OTP to the given email |
| `POST` | `/api/auth/verify-otp` | None | Verify OTP and receive a JWT token |
| `GET`  | `/health` | None | Service health check |

### POST /api/auth/send-otp

**Request:**
```json
{ "email": "user@example.com" }
```

**Response 200:**
```json
{ "message": "If this email is registered, a code has been sent." }
```

**Response 429** (rate limit exceeded):
```json
{ "error": "Too many requests. Please wait before requesting another code." }
```

**Response 503** (Mailgun failure):
```json
{ "error": "Failed to send verification email. Please try again later." }
```

### POST /api/auth/verify-otp

**Request:**
```json
{ "email": "user@example.com", "code": "123456" }
```

**Response 200:**
```json
{ "token": "<JWT>", "email": "user@example.com", "expiresIn": 86400 }
```

**Response 401** (invalid/expired code):
```json
{ "error": "Invalid or expired code." }
```

### GET /health

```json
{ "status": "ok", "service": "auth-service" }
```

## JWT Compatibility

Tokens are signed with **HMAC-HS256** using the same `JWT_SECRET` shared with the Java monolith.
Claims: `sub` (email), `iat`, `exp`. No additional claims are included.

The Java `JwtAuthenticationFilter` will accept tokens issued by this service, and vice versa.

## Environment Variables

See `.env.example` for the full list with descriptions.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | Supabase asyncpg connection string |
| `JWT_SECRET` | Yes | — | HMAC secret (must match Java monolith) |
| `JWT_EXPIRATION_MS` | No | `86400000` | Token lifetime in ms |
| `MAILGUN_API_KEY` | Yes | — | Mailgun API key |
| `MAILGUN_DOMAIN` | No | `mg.tallerlabs.ai` | Mailgun sending domain |
| `FRONTEND_URL` | No | `http://localhost:3000` | Allowed CORS origin |
| `OTP_EXPIRY_MINUTES` | No | `10` | OTP validity window |
| `OTP_RATE_LIMIT_PER_HOUR` | No | `5` | Max OTPs per email per hour |

## Database

The service uses the `otp_codes` table. This table is **not created automatically** —
it must be created via the schema migration below before the service is started.

```sql
CREATE TABLE IF NOT EXISTS otp_codes (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    code        VARCHAR(6) NOT NULL,
    expires_at  TIMESTAMP NOT NULL,
    used        BOOLEAN DEFAULT FALSE NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_otp_codes_email ON otp_codes(email);
CREATE INDEX IF NOT EXISTS idx_otp_codes_email_created ON otp_codes(email, created_at);
```

## Running Locally (bare-metal)

```bash
cd services/auth-service

# Create and activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies (shared module must be on PYTHONPATH)
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with real values

# Run (from services/ directory so shared/ is importable)
cd ..
PYTHONPATH=. uvicorn auth-service.app.main:app --reload --port 8001
```

## Running with Docker

```bash
# From repo root
docker compose up auth-service

# Or build the image manually:
docker build -f services/auth-service/Dockerfile -t auth-service:local ./services
docker run --env-file .env -p 8001:8001 auth-service:local
```

## Running the Full Stack

```bash
# From repo root — starts gateway, Java monolith, auth-service, and frontend
docker compose up

# Or use the helper script:
./homelend.sh docker
```

## Smoke Tests

```bash
# Health check
curl http://localhost:8001/health

# Via gateway (when running full stack)
curl http://localhost/health  # Note: health is per-service, not proxied by default

# Send OTP (use a real email for actual delivery, or test with a known address)
curl -X POST http://localhost/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'

# Verify OTP
curl -X POST http://localhost/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","code":"123456"}'
```
