# Strangler Fig Coexistence Strategy — Route-Level Cutover Rulebook

## Purpose

This document is the route-ownership registry and coexistence rulebook for the side-by-side
operation of the Java Spring Boot monolith and the Python FastAPI microservices during the
HomeLend Pro backend migration. It complements (and does not duplicate) the following documents:

- `doc/cutover-playbook.md` — per-service cutover checklist, validation steps, and rollback procedure
- `doc/api-compatibility-rules.md` — endpoint-level compatibility rules (URLs, payloads, auth, status codes, error shapes)

> **Architecture note**: The task description references "Java EE and Spring Boot coexistence."
> The actual architecture is **Java Spring Boot monolith + Python FastAPI microservices**.
> This document reflects the actual coexistence topology.

---

## 1. Architecture Overview

The strangler fig pattern uses nginx as the routing proxy. All external traffic enters through
nginx on port 80. nginx routes each request to either the Java monolith (still handling
unmigraded domains) or the appropriate FastAPI service.

```
Frontend / External Clients
         │
         ▼
  [nginx API Gateway :80]
  (server_name: localhost, 127.0.0.1)
         │
    ┌────┴─────────────────────────────────────────────┐
    │                                                    │
[Java Monolith :8080]                   [FastAPI Services]
  /api/loans (base CRUD) — Wave 2B      auth-service:8001
  /api/admin/* — Wave 4                 property-listing-service:8002
                                        underwriting-service:8003
                                        closing-service:8004
                                        client-crm-service:8005
    │                                    │
    └─────────────────┬──────────────────┘
                      │
              [Shared PostgreSQL]
              (single schema, shared tables)
```

**Current state**: Waves 1, 2A, 3A, and 3B are migrated. The Java monolith retains
`/api/loans` (base CRUD, Wave 2B) and `/api/admin/*` (Wave 4). The Java monolith is
still running and connected to the shared PostgreSQL instance.

---

## 2. Route Ownership Registry

This is the single authoritative table of route ownership as of this epic.
It is derived directly from `gateway/nginx.conf` (which is the ground truth — if a location
block exists pointing to a FastAPI service, the route is MIGRATED).

| Path Prefix | Method Scope | Current Owner | Cutover Status | Java Retirement Status |
|-------------|-------------|---------------|----------------|----------------------|
| `/api/auth/*` | POST | FastAPI: auth-service (8001) | ✅ MIGRATED (Wave 1) | Pending JR-1 through JR-7 |
| `/api/properties/*` | GET/POST/PUT/DELETE | FastAPI: property-listing-service (8002) | ✅ MIGRATED (Wave 1) | Pending JR-1 through JR-7 |
| `/api/listings/*` | GET/POST/PUT/DELETE | FastAPI: property-listing-service (8002) | ✅ MIGRATED (Wave 1) | Pending JR-1 through JR-7 |
| `/api/loans/{id}/credit-report` | GET/POST | FastAPI: underwriting-service (8003) | ✅ MIGRATED (Wave 3A) | Pending JR-1 through JR-7 |
| `/api/loans/{id}/underwriting` | GET/POST/PUT | FastAPI: underwriting-service (8003) | ✅ MIGRATED (Wave 3A) | Pending JR-1 through JR-7 |
| `/api/loans/{id}/appraisal/*` | GET/POST | FastAPI: underwriting-service (8003) | ✅ MIGRATED (Wave 3A) | Pending JR-1 through JR-7 |
| `/api/closings/*` | GET/POST/PUT/DELETE | FastAPI: closing-service (8004) | ✅ MIGRATED (Wave 3B) | Pending JR-1 through JR-7 |
| `/api/clients/*` | GET/POST/PUT/DELETE | FastAPI: client-crm-service (8005) | ✅ MIGRATED (Wave 2A) | Pending JR-1 through JR-7 |
| `/api/agents/*` | GET/POST/PUT/DELETE | FastAPI: client-crm-service (8005) | ✅ MIGRATED (Wave 2A) | Pending JR-1 through JR-7 |
| `/api/brokerages/*` | GET/POST/PUT/DELETE | FastAPI: client-crm-service (8005) | ✅ MIGRATED (Wave 2A) | Pending JR-1 through JR-7 |
| `/api/leads/*` | GET/POST/PUT/DELETE | FastAPI: client-crm-service (8005) | ✅ MIGRATED (Wave 2A) | Pending JR-1 through JR-7 |
| `/api/showings/*` | GET/POST/PUT/DELETE | FastAPI: client-crm-service (8005) | ✅ MIGRATED (Wave 2A) | Pending JR-1 through JR-7 |
| `/api/offers/*` | GET/POST/PUT/DELETE | FastAPI: client-crm-service (8005) | ✅ MIGRATED (Wave 2A) | Pending JR-1 through JR-7 |
| `/api/loans` (base CRUD) | GET/POST/PUT/DELETE | **Java monolith** | ❌ NOT MIGRATED (Wave 2B pending) | N/A — Java still active |
| `/api/admin/*` | * | **Java monolith** | ❌ DEFERRED (Wave 4) | N/A — Java still active |

**nginx routing note**: `gateway/nginx.conf` routes all of `/api/loans/` to underwriting-service.
Requests to `/api/loans` base CRUD (non-sub-resource paths) reach underwriting-service and
return 404 because those routes are not defined in `underwriting-service/app/routers/`.
This is the expected behavior until `loan-origination-service` (Wave 2B) is deployed and the
nginx config is updated.

---

## 3. Coexistence Rules

These rules govern parallel-run behavior while any Java-owned routes remain active.

| Rule ID | Rule |
|---------|------|
| **CO-1** | Traffic routing is controlled **exclusively at the nginx gateway**. No FastAPI service proxies or forwards requests to the Java monolith. No Java code proxies to FastAPI services. |
| **CO-2** | No synchronous inter-service HTTP calls between FastAPI services are permitted. Services share the database, not HTTP endpoints. |
| **CO-3** | JWT tokens issued by the Java `AuthController` and by `auth-service` are **mutually valid** during parallel run. Both use HS256 with the shared `JWT_SECRET` environment variable. Tokens are interchangeable. |
| **CO-4** | **Write ownership follows `doc/postgresql-access-policy.md` §3**. Write ownership of a table belongs to exactly one service at a time. Split writes (Java and FastAPI simultaneously writing the same table) are forbidden. |
| **CO-5** | FastAPI services **may read any database table** regardless of current write ownership (per `postgresql-access-policy.md` Rule DB-4). Cross-domain reads are non-transactional and non-locking. |
| **CO-6** | The nginx gateway accepts requests **only for `localhost` and `127.0.0.1`** (`server_name` directive). All other `Host` header values are rejected. The client-supplied `Host` header is never forwarded to upstreams — each `location` block sets a static `Host` value (e.g., `auth-service:8001`). See `doc/gateway-host-header-audit.md` for rationale. |
| **CO-7** | New FastAPI path prefixes must not overlap with any Java-served path prefix until Java retirement for that prefix is complete (R-URL-5 from `api-compatibility-rules.md`). |
| **CO-8** | During a Wave 2B cutover, the nginx config must be updated to route `/api/loans` base CRUD paths to `loan-origination-service`. This must happen atomically with `loan-origination-service` achieving production readiness. |

---

## 4. API Compatibility Checklist Reference

All API compatibility rules are defined in `doc/api-compatibility-rules.md`. The categories are:

| Category | Rule Group | Summary |
|----------|-----------|---------|
| **URL and path** | R-URL-1 through R-URL-5 | Preserve `/api/` prefix, path segment names, path parameter names, sub-resource nesting. |
| **HTTP methods** | R-MTH-1 through R-MTH-3 | Match Java method exactly; no GET→POST changes; PUT for status updates. |
| **Request payloads** | R-REQ-1 through R-REQ-6 | camelCase field names, preserve required/optional field semantics, exact query param names, 0-based page index, Content-Type: application/json. |
| **Response payloads** | R-RES-1 through R-RES-7 | camelCase response fields, Spring Page envelope, no extra wrapper, ISO 8601 dates, UUID as string. |
| **Status codes** | R-STS-1 through R-STS-8 | 201 for creates, 200 for gets/updates, 204 for deletes, 404 for not-found, 400 for validation, 401 for auth failures, 403 for authorization failures, 422→400 remapping. |
| **Authentication** | R-AUTH-1 through R-AUTH-5 | Bearer JWT preserved, shared `JWT_SECRET`, public endpoints remain public, OTP shapes unchanged. |
| **Error responses** | R-ERR-1 through R-ERR-3 | `{"message": "..."}` for domain errors, override FastAPI `{"detail": "..."}` default. |

Implementers must consult `doc/api-compatibility-rules.md` directly for the precise requirements
before implementing any replacement endpoint.

---

## 5. Rollback Trigger Conditions

Base rollback procedure is defined in `doc/cutover-playbook.md` §5. The following extends
that procedure with service-specific trigger conditions and timing rules.

### 5.1 Rollback triggers

A rollback must be initiated immediately upon observing any of the following:

| Trigger | Condition | Threshold |
|---------|-----------|-----------|
| **Error rate spike** | 5xx response rate for the migrated path prefix exceeds pre-cutover Java baseline | > 0.1% over 5-minute window |
| **Data consistency failure** | Records written by FastAPI produce unexpected results on subsequent reads | Any confirmed instance |
| **JWT compatibility break** | Java-issued tokens rejected by FastAPI service (401 on valid tokens) | Any confirmed instance |
| **Performance regression** | p95 response time > 2× Java baseline for migrated paths | Sustained > 15 minutes |
| **Frontend breakage** | User-facing errors reported or synthetic monitor failures for migrated paths | Any confirmed instance |
| **Health check failure** | FastAPI service `/health` endpoint returns non-200 | Any instance during cutover window |

### 5.2 Rollback window and process

- **Rollback window**: 30 minutes from first failure signal. If the root cause cannot be resolved within 30 minutes, initiate rollback immediately (per `cutover-playbook.md` RB-1).
- **Rollback execution time target**: nginx reload to restore 100% Java traffic in **< 2 minutes**.
- **Rollback confirmation**: After nginx reload, verify Java is receiving traffic and returning correct responses (cutover-playbook.md RB-3).

### 5.3 Post-rollback rules

- **No automatic retry**: After a rollback, do not attempt the cutover again without completing a post-mortem.
- **Post-mortem requirement**: File a post-mortem issue documenting failure cause, timeline, and resolution steps before scheduling the next cutover attempt (per `cutover-playbook.md` RB-7).
- **Write ownership revert**: If write ownership had been transferred before the rollback (CO-7 in the cutover checklist), revert `doc/postgresql-access-policy.md` §3 to Java and assess data written by FastAPI for consistency (per `cutover-playbook.md` RB-4 through RB-6).

---

## 6. Java Retirement Gates — Current Status

Full retirement criteria are defined in `doc/cutover-playbook.md` §6 (JR-1 through JR-7).
The following table shows the current gate status for each migrated service:

| Criterion | Description | auth-service | property-listing-service | client-crm-service | underwriting-service | closing-service |
|-----------|-------------|:---:|:---:|:---:|:---:|:---:|
| **JR-1**: Stability window | 14 consecutive days in production, no rollback | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| **JR-2**: Coverage confirmation | Contract test suite passes for all endpoints | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| **JR-3**: DB write confirmation | No Java code writes to owned tables | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| **JR-4**: Cross-domain deps resolved | No other Java code calls this domain's beans | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| **JR-5**: Routing cleanup | Java routing removed from nginx | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| **JR-6**: Documentation updated | `domain-boundary-map.md` and `postgresql-access-policy.md` updated | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| **JR-7**: Team sign-off | Platform + domain engineer sign-off in MDR | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending | ⏳ Pending |

**Next retirement milestone**: Wave 1 services (`auth-service`, `property-listing-service`)
are the earliest candidates for Java code retirement. JR-1 (14-day stability window) is
the gating criterion — confirm the stability window start date from the Wave 1 cutover records.

**Per-service cutover records** (active tracking instances):
- `doc/cutover-records/closing-service-cutover.md`
- `doc/cutover-records/underwriting-service-cutover.md`

Additional cutover records must be created for auth-service, property-listing-service, and
client-crm-service following the template in `doc/cutover-playbook.md` §7.

---

## 7. Wave Progression — Remaining Steps

| Wave | Work Item | Dependency |
|------|-----------|-----------|
| Wave 2B | Build `loan-origination-service` (port 8006) | Requires `MasterService` decomposition; `loan_applications` table must have write ownership transferred from Java |
| Wave 2B | Update `gateway/nginx.conf` to route `/api/loans` base CRUD to `loan-origination-service` | After loan-origination-service passes pre-cutover checklist |
| Wave 2B | Update `docker-compose.yml` to add `loan-origination-service` | Part of Wave 2B service build |
| Wave 4 | Build `admin-service` | After all other waves are stable; `audit_logs` write ownership transfer required |
| All waves | Complete JR-1 through JR-7 for each migrated service | Triggered by 14-day stability window per service |
