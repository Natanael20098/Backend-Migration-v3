# Gateway Host Header Audit

**Date:** 2025-01-31  
**File audited:** `gateway/nginx.conf`  
**Status:** Remediated — see Section 4

---

## 1. Directives Using Request Host Values

### Finding: `proxy_set_header Host $host` (server-level, line 68)

```nginx
server {
    listen 80;
    server_name _;

    # ← FLAGGED
    proxy_set_header Host $host;
    ...
}
```

The directive `proxy_set_header Host $host` was set at the `server {}` block level, making it the
default for **every** `proxy_pass` location in the file unless overridden in the location block.

**What `$host` resolves to in nginx:**

| Request condition | `$host` value |
|---|---|
| `Host` header present and non-empty | Value of the `Host` header (attacker-controlled) |
| `Host` header absent | Value from the `server_name` directive |

Because `server_name _` was a catch-all wildcard, in practice `$host` was always set from the
inbound `Host` header — a value fully controlled by the HTTP client.

### No other attacker-controlled variables used

A full grep of the file confirmed no other client-controlled variables (`$http_host`,
`$http_x_forwarded_host`, `$http_*`) were used in proxy headers or `proxy_pass` directives.

---

## 2. Routes Depending on the Current Behavior

All eleven upstream location blocks inherited the server-level `proxy_set_header Host $host`:

| Location | Upstream service | Port |
|---|---|---|
| `/api/auth/` | `auth-service` | 8001 |
| `/api/properties/` | `property-listing-service` | 8002 |
| `/api/listings/` | `property-listing-service` | 8002 |
| `/api/loans/` | `underwriting-service` | 8003 |
| `/api/closings/` | `closing-service` | 8004 |
| `/api/clients/` | `client-crm-service` | 8005 |
| `/api/agents/` | `client-crm-service` | 8005 |
| `/api/brokerages/` | `client-crm-service` | 8005 |
| `/api/leads/` | `client-crm-service` | 8005 |
| `/api/showings/` | `client-crm-service` | 8005 |
| `/api/offers/` | `client-crm-service` | 8005 |
| `/` (frontend) | `frontend` (Next.js) | 3000 |

**Do any upstream services use the Host header?**

All upstreams are FastAPI services and the Next.js frontend running inside the Docker `platform`
network. Checked each service's application code:

- FastAPI services: do **not** use the `Host` header for routing, URL construction, or any
  business logic. FastAPI processes path and query parameters from the URL, not from Host.
- Next.js frontend: does **not** use the proxied `Host` header for internal routing; it renders
  pages based on URL path. Next.js hot-reload WebSocket connection uses the `Upgrade` header, not
  `Host`.

**Conclusion:** No upstream service functionally depends on receiving the client-supplied `Host`
value. The behavior can be changed without breaking any route.

---

## 3. Attack Surface of Blind `$host` Trust

Forwarding the client-supplied `Host` header to upstreams enables several attack classes:

### 3a. Host Header Injection / Password Reset Poisoning
If any service generates absolute URLs using the Host header (e.g., for password-reset emails,
OAuth redirects, or PDF export links), an attacker sends:
```
Host: attacker.com
```
The service builds `https://attacker.com/api/auth/reset?token=XXX` and emails it to the victim.

### 3b. Web Cache Poisoning
If a CDN or reverse proxy caches responses keyed partly on `Host`, an attacker can poison the
cache for legitimate users by sending a crafted `Host` value that resolves to the same backend
page.

### 3c. Server-Side Request Forgery (SSRF) via Host Routing
In some nginx configurations, `proxy_pass` targets are constructed from the Host header. While
this configuration used static `proxy_pass` targets, the forwarded header could still be used by
misconfigured upstream middleware that re-routes internally.

### 3d. Virtual-Host Confusion
If the upstream application uses `Host` to select a tenant or configuration (multi-tenant
patterns), an attacker could access resources belonging to another tenant.

---

## 4. Safe Replacement Strategy (Implemented)

### Decision: Explicit static Host per location block

Each location block now sets its own `proxy_set_header Host` with a hard-coded value
(container name + port) that matches the upstream:

```nginx
location /api/auth/ {
    proxy_set_header Host auth-service:8001;   # ← static, not attacker-controlled
    proxy_pass http://auth_service;
}
```

The server-level `proxy_set_header Host $host` directive has been **removed entirely**.

### Why not `$server_name` or a map?

- `$server_name` would be `localhost` (from `server_name localhost 127.0.0.1`), which is valid
  but misleading — upstreams receive `localhost` rather than their own container identity.
- A `map` allowlist (e.g., only forward Host if it matches `localhost`) would still forward
  attacker-controlled data on a match — the allowlisted value would be fine, but the complexity
  adds no benefit over just using a literal string.
- An explicit literal per location is the simplest, most auditable, and most forward-safe option.

### Tightened `server_name`

The catch-all `server_name _` has been replaced with an explicit allowlist:

```nginx
server_name localhost 127.0.0.1;
```

Requests arriving with a `Host` header that does not match `localhost` or `127.0.0.1` will not
match this server block. For production, the real public hostname(s) should be added here.

### Routes that continue to work

All eleven API routes and the frontend passthrough continue to function identically:
- URL-based routing (`proxy_pass` targets) is unchanged.
- Upstream services receive a meaningful `Host` header identifying the upstream container.
- `X-Forwarded-For`, `X-Real-IP`, and `X-Forwarded-Proto` are still forwarded from the real
  client request, so upstream services can log the original requester.
- WebSocket upgrade headers (`Upgrade`, `Connection`) are still set in the `/` location.

---

## 5. Verification Checklist

| Check | Status |
|---|---|
| `$host` or `$http_host` no longer used in any `proxy_set_header` | ✅ |
| Every `proxy_pass` location has an explicit `proxy_set_header Host` | ✅ |
| `server_name` is an explicit allowlist, not `_` wildcard | ✅ |
| All 12 routes (11 API + frontend) confirmed working | ✅ (see `gateway/tests/test_host_header.sh`) |
| No attacker-controlled variable used anywhere in nginx.conf | ✅ |

---

## 6. References

- [OWASP: Host Header Injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/17-Testing_for_Host_Header_Injection)
- [PortSwigger: Web Cache Poisoning](https://portswigger.net/web-security/web-cache-poisoning)
- [nginx docs: `proxy_set_header`](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)
- [nginx docs: `$host` variable](https://nginx.org/en/docs/http/ngx_http_core_module.html#var_host)
