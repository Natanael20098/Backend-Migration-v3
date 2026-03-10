# API Gateway (nginx)

The nginx gateway is the single ingress point for all platform traffic.
It routes requests to the Java monolith or to migrated FastAPI services
based on URL path prefix, preserving existing external API contracts.

## Current Routing Table

| Path Prefix | Upstream | Status | Notes |
|-------------|----------|--------|-------|
| `/api/auth/` | `auth-service:8001` | Migrated | FastAPI OTP auth service |
| `/api/` | `java-monolith:8080` | Legacy | Spring Boot catch-all |
| `/` | `frontend:3000` | Pass-through | Next.js |

Nginx uses longest-prefix matching: more specific paths (e.g., `/api/auth/`)
take priority over shorter ones (e.g., `/api/`) regardless of declaration order,
but specific blocks are declared first for clarity.

## Adding a New Service (Step-by-Step)

When a new service area is migrated from Java to FastAPI, follow these steps
to cut over its traffic through the gateway.

### Step 1 — Update docker-compose.yml

Add the new service following the template at the bottom of `docker-compose.yml`:

```yaml
properties-service:
  build:
    context: ./services
    dockerfile: properties-service/Dockerfile
  ports:
    - "8002:8002"
  env_file: .env
  networks: [platform]
  restart: unless-stopped
```

### Step 2 — Add an nginx upstream

In `gateway/nginx.conf`, add an upstream block in the `http {}` block:

```nginx
upstream properties_service {
    server properties-service:8002;
    keepalive 8;
}
```

### Step 3 — Add a location block

Add a `location` block **before** the generic `location /api/` block:

```nginx
# Cutover status: MIGRATED — properties domain now served by FastAPI
# Rollback: change proxy_pass to http://java_monolith
location /api/properties/ {
    proxy_pass http://properties_service;
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

### Step 6 — Validate for 24 hours

Monitor logs and error rates before retiring the Java code path:
```bash
docker compose logs -f gateway
docker compose logs -f properties-service
```

## Smoke Test Commands

Run these after any routing change before considering it production-ready.

### Full Stack Health

```bash
# Gateway itself is running
curl -I http://localhost/
# Expect: 200 or 3xx (frontend response)

# Java monolith reachable through gateway
curl -I http://localhost/api/agents
# Expect: 200 or 401 (requires auth — 401 means the monolith is up and responding)

# Auth service reachable through gateway
curl -X POST http://localhost/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke-test@example.com"}'
# Expect: 200 {"message":"If this email is registered, a code has been sent."}

# Auth service health (direct — not proxied through gateway by default)
curl http://localhost:8001/health
# Expect: {"status":"ok","service":"auth-service"}
```

### After Adding a New Route

```bash
# Replace /api/<new-path> with the actual path of the new service
curl -I http://localhost/api/<new-path>
# Expect: 200 or 401 (not 502 Bad Gateway or 404 from nginx)

# Verify Java monolith still responds for un-migrated paths
curl -I http://localhost/api/loans
# Expect: 200 or 401 (not 502)

# Auth flow still works
curl -X POST http://localhost/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke-test@example.com"}'
# Expect: 200
```

### Checking nginx Error Logs

```bash
docker compose logs gateway
# Look for: "connect() failed", "upstream timed out", "no live upstreams"
# Any of these indicate the target service is unreachable
```

## Rollback Procedure

If a newly migrated route causes errors, roll back by reverting the location block
to point at `java_monolith`:

1. In `gateway/nginx.conf`, change:
   ```nginx
   location /api/properties/ {
       proxy_pass http://properties_service;
   }
   ```
   to:
   ```nginx
   location /api/properties/ {
       proxy_pass http://java_monolith;
   }
   ```

2. Reload the nginx container:
   ```bash
   docker compose up --build gateway
   # Or, if nginx is running, reload config without restart:
   docker compose exec gateway nginx -s reload
   ```

3. Verify traffic is flowing again:
   ```bash
   curl -I http://localhost/api/properties/
   ```

4. Investigate the new service before attempting cutover again.

## Incremental Cutover Process

The gateway enables gradual, path-by-path migration from Java to FastAPI:

1. **Identify** the domain boundary to migrate (see `doc/domain-boundary-map.md`)
2. **Build and test** the new FastAPI service in isolation
3. **Add gateway route** following the steps above
4. **Run smoke tests** — all paths must respond correctly
5. **Monitor 24 hours** — check error rates and response times
6. **Retire Java code** only after 24-hour validation passes (see `doc/cutover-playbook.md`)

Current migration state is tracked in the routing table at the top of this README.
Update the table after each cutover.

## Configuration Notes

- nginx uses **longest-prefix matching** for `location` blocks — no `~` regex needed for path prefixes
- `proxy_http_version 1.1` + `proxy_set_header Connection ""` is required for upstream keepalive
- `proxy_connect_timeout 10s` — fail fast if a service is down; upstream error is clearer than a hanging connection
- `proxy_read_timeout 60s` — accommodate slow DB queries during migration; tune per service as needed
