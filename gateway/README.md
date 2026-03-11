# API Gateway (nginx)

The nginx gateway is the single ingress point for all platform traffic.
It routes requests to the appropriate FastAPI microservice based on URL path prefix,
preserving existing external API contracts.

## Current Routing Table

| Path Prefix | Upstream | Port | Status |
|-------------|----------|------|--------|
| `/api/auth/` | `auth-service` | 8001 | ✅ Migrated |
| `/api/properties/` | `property-listing-service` | 8002 | ✅ Migrated |
| `/api/listings/` | `property-listing-service` | 8002 | ✅ Migrated |
| `/api/loans/` | `underwriting-service` | 8003 | ✅ Migrated (sub-resources only — see note) |
| `/api/closings/` | `closing-service` | 8004 | ✅ Migrated |
| `/api/clients/` | `client-crm-service` | 8005 | ✅ Migrated |
| `/api/agents/` | `client-crm-service` | 8005 | ✅ Migrated |
| `/api/brokerages/` | `client-crm-service` | 8005 | ✅ Migrated |
| `/api/leads/` | `client-crm-service` | 8005 | ✅ Migrated |
| `/api/showings/` | `client-crm-service` | 8005 | ✅ Migrated |
| `/api/offers/` | `client-crm-service` | 8005 | ✅ Migrated |
| `/` | `frontend` | 3000 | Pass-through (Next.js) |

**Note on `/api/loans/`**: The underwriting-service handles loan sub-resource paths
(`/api/loans/{id}/credit-report`, `/api/loans/{id}/underwriting`, `/api/loans/{id}/appraisal`).
Base loan application CRUD is Wave 2B (`loan-origination-service`, not yet built) and returns
404 from the underwriting-service until that service is deployed.

**Note on `/api/admin/`**: The admin domain is deferred to Wave 4. These paths are not routed
and will return nginx 404 until `admin-service` is built.

## Adding a New Service (Step-by-Step)

When a new service area is migrated, follow these steps to cut over its traffic through the gateway.

### Step 1 — Update docker-compose.yml

Add the new service following the template at the bottom of `docker-compose.yml`:

```yaml
new-service:
  build:
    context: ./services
    dockerfile: new-service/Dockerfile
  ports:
    - "8006:8006"
  env_file: .env
  networks: [platform]
  restart: unless-stopped
```

Also add `new-service` to `gateway.depends_on`.

### Step 2 — Add an nginx upstream

In `gateway/nginx.conf`, add an upstream block in the `http {}` block:

```nginx
upstream new_service {
    server new-service:8006;
    keepalive 8;
}
```

### Step 3 — Add a location block

Add a `location` block in the `server {}` block:

```nginx
# Cutover status: MIGRATED
location /api/new-resource/ {
    proxy_pass http://new_service;
}
```

### Step 4 — Run smoke tests

```bash
# Rebuild and restart the gateway container
docker compose up --build gateway

# Run smoke tests (see below)
```

### Step 5 — Update the routing table above

Add the new row to the routing table in this README.

## Smoke Test Commands

Run these after any routing change before considering it production-ready.

### Full Stack Health

```bash
# Gateway itself is running
curl -I http://localhost/
# Expect: 200 or 3xx (frontend response)

# Auth service reachable through gateway
curl -X POST http://localhost/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke-test@example.com"}'
# Expect: 200 {"message":"If this email is registered, a code has been sent."}

# Auth service health (direct)
curl http://localhost:8001/health
# Expect: {"status":"ok","service":"auth-service"}

# Property listing service health (direct)
curl http://localhost:8002/health
# Expect: {"status":"ok","service":"property-listing-service"}

# Underwriting service health (direct)
curl http://localhost:8003/health
# Expect: {"status":"ok","service":"underwriting-service"}

# Closing service health (direct)
curl http://localhost:8004/health
# Expect: {"status":"ok","service":"closing-service"}

# Client CRM service health (direct)
curl http://localhost:8005/health
# Expect: {"status":"ok","service":"client-crm-service"}
```

### Testing Authenticated Routes

```bash
# First, obtain a token via the auth flow
TOKEN=$(curl -s -X POST http://localhost/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","code":"123456"}' \
  | jq -r '.token')

# Test properties (property-listing-service)
curl -I -H "Authorization: Bearer $TOKEN" http://localhost/api/properties
# Expect: 200

# Test closings (closing-service)
curl -I -H "Authorization: Bearer $TOKEN" http://localhost/api/closings
# Expect: 200

# Test clients (client-crm-service)
curl -I -H "Authorization: Bearer $TOKEN" http://localhost/api/clients
# Expect: 200

# Test underwriting sub-resources (underwriting-service)
curl -I -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/loans/00000000-0000-0000-0000-000000000001/credit-report"
# Expect: 404 (loan not found) — confirms underwriting-service is responding
```

### Checking nginx Error Logs

```bash
docker compose logs gateway
# Look for: "connect() failed", "upstream timed out", "no live upstreams"
# Any of these indicate the target service is unreachable
```

## Configuration Notes

- nginx uses **longest-prefix matching** for `location` blocks
- `proxy_http_version 1.1` + `proxy_set_header Connection ""` is required for upstream keepalive
- `proxy_connect_timeout 10s` — fail fast if a service is down
- `proxy_read_timeout 60s` — accommodate slow DB queries; tune per service as needed
- The Java monolith (`java-monolith:8080`) has been fully removed. There is no catch-all `/api/`
  fallback. Unrouted `/api/*` paths return nginx 404 by default.
