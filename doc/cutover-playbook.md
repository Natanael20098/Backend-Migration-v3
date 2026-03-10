# Cutover Playbook: Service-by-Service Replacement

## Purpose

This document is the reusable cutover playbook for migrating one domain service at a time
from the Java monolith to FastAPI, while both run in parallel. Every domain migration epic
reuses this playbook without redefining it — each epic references the checklist phases and
records its domain-specific values in a filled-in **Cutover Record** (see §6).

The playbook covers four phases: Pre-Cutover, Cutover, Validation, and Rollback. It also
defines the Java retirement criteria that must be satisfied before Java code for a migrated
domain is permanently decommissioned.

---

## 1. Coexistence Architecture

During parallel run:

```
Frontend / External Clients
         │
         ▼
  [Reverse Proxy / API Gateway]
         │
    ┌────┴────────────────────────┐
    │                             │
[Java Monolith :8080]     [FastAPI Service :8XXX]
    │                             │
    └────────────┬────────────────┘
                 │
         [Shared PostgreSQL]
```

- The reverse proxy routes requests to either Java or FastAPI based on routing rules.
- During pre-cutover, all traffic goes to Java. FastAPI runs in shadow/staging mode.
- During cutover, traffic is shifted to FastAPI one path prefix at a time.
- After validation, Java routes for the migrated domain are disabled.

---

## 2. Pre-Cutover Checklist

Complete all items before shifting any production traffic to the FastAPI service.

### 2.1 Routing Readiness

- [ ] **PC-R1**: The reverse proxy (nginx / Caddy / ALB) has routing rules defined for the service's path prefix (e.g., `/api/properties/*`), pointing to the FastAPI service. Rules are in place but traffic weight = 0% to FastAPI.
- [ ] **PC-R2**: The FastAPI service is deployed and healthy in the production environment (health endpoint `/health` returns 200).
- [ ] **PC-R3**: The FastAPI service connects to the shared PostgreSQL instance and passes a read query smoke test.
- [ ] **PC-R4**: Environment variables (`DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION_MS`) are confirmed set correctly in the FastAPI service deployment.

### 2.2 Contract Checks

- [ ] **PC-C1**: Every endpoint in the service's path scope has been verified against `doc/api-compatibility-rules.md`. All applicable rules (R-URL-*, R-MTH-*, R-REQ-*, R-RES-*, R-STS-*, R-AUTH-*, R-ERR-*) are satisfied.
- [ ] **PC-C2**: A contract test suite exists for the service's endpoints and passes against the FastAPI service running in staging.
- [ ] **PC-C3**: Response payloads have been diffed against Java responses for at least 3 representative requests per endpoint. No field-name differences, no missing required fields.
- [ ] **PC-C4**: Pagination response envelope matches Spring Page format (`content`, `totalElements`, `totalPages`, `size`, `number`) for all paginated endpoints.
- [ ] **PC-C5**: JWT authentication is validated: requests with a valid Java-issued token are accepted by the FastAPI service.
- [ ] **PC-C6**: Error response shapes match (`{"message": "..."}`) for 400, 401, 403, and 404 responses.

### 2.3 Database Readiness

- [ ] **PC-D1**: The service's DB table ownership has been confirmed per `doc/postgresql-access-policy.md` §3. Write ownership transfer is scheduled for cutover, not before.
- [ ] **PC-D2**: No pending Alembic migrations exist that would modify shared tables Java is currently writing. All approved migrations have been applied.
- [ ] **PC-D3**: The FastAPI service has been confirmed to **not** execute DDL on startup in production.

### 2.4 Smoke Tests

- [ ] **PC-S1**: End-to-end smoke test suite for the service's endpoints passes against the production database (read-only queries) with the FastAPI service.
- [ ] **PC-S2**: The frontend application has been smoke-tested against the FastAPI service in a staging environment. No console errors, no broken API calls.
- [ ] **PC-S3**: Authentication flow (login → receive token → call protected endpoint) works end-to-end through the FastAPI service.

### 2.5 Rollback Readiness

- [ ] **PC-RB1**: The rollback procedure (§5) has been reviewed and understood by the on-call engineer.
- [ ] **PC-RB2**: The Java monolith is confirmed still running and passing its own smoke tests at cutover time.
- [ ] **PC-RB3**: The reverse proxy routing rules can be reverted to 100% Java in under 2 minutes.

---

## 3. Cutover Checklist

Execute in order. Do not proceed to the next step if the current step fails — execute rollback.

### 3.1 Traffic Shift

- [ ] **CO-1**: Announce cutover start to team. Record start time.
- [ ] **CO-2**: Shift 10% of traffic for the service's path prefix to FastAPI. Monitor error rate for 5 minutes.
- [ ] **CO-3**: If error rate is acceptable (< 0.1% 5xx), shift to 50% FastAPI. Monitor for 10 minutes.
- [ ] **CO-4**: If error rate is still acceptable, shift to 100% FastAPI. Monitor for 15 minutes.
- [ ] **CO-5**: Java routes for this service's path prefix are set to receive 0% traffic (kept alive for rollback; not yet disabled).

### 3.2 Write Ownership Transfer

- [ ] **CO-6**: Confirm that all in-flight Java write requests for the domain have completed (drain period: wait for Java request queue to empty, typically 30 seconds after traffic = 0%).
- [ ] **CO-7**: Update the DB ownership record in `doc/postgresql-access-policy.md` §3 to reflect FastAPI as the new writer.
- [ ] **CO-8**: Verify the FastAPI service is successfully writing to its owned tables (check at least one create/update operation end-to-end).

---

## 4. Validation Checklist

Run immediately after cutover and again after 24 hours in production.

### 4.1 Immediate Post-Cutover Validation (T+0 to T+1 hour)

- [ ] **V-1**: Error rate for the service's path prefix is below pre-cutover Java baseline.
- [ ] **V-2**: Response latency p95 is within acceptable range (≤ 2× Java baseline, or defined SLA).
- [ ] **V-3**: All paginated endpoints return correct `totalElements` and `content` arrays verified against direct DB count queries.
- [ ] **V-4**: JWT-protected endpoints reject invalid tokens with 401.
- [ ] **V-5**: At least one create, read, update, and delete operation per core resource has been exercised and verified via the production API.
- [ ] **V-6**: Frontend application is functioning normally (no user-facing errors, confirmed by frontend team or synthetic monitoring).
- [ ] **V-7**: Audit log records are being created by the FastAPI service for write operations.

### 4.2 Stability Validation (T+24 hours)

- [ ] **V-8**: No elevated error rates in the preceding 24 hours.
- [ ] **V-9**: No data consistency issues reported (spot-check DB records written by FastAPI vs expected).
- [ ] **V-10**: Java monolith logs show no write attempts to the transferred tables (confirm write ownership is fully transferred).
- [ ] **V-11**: Rollback decision deadline has passed. Record that the cutover is confirmed stable.

---

## 5. Rollback Checklist

Execute if any cutover or validation step fails and cannot be resolved within the rollback window (default: 30 minutes from first failure signal).

- [ ] **RB-1**: Announce rollback to team. Record start time and failure reason.
- [ ] **RB-2**: Shift 100% of traffic back to Java monolith for the affected path prefix via the reverse proxy. Time target: < 2 minutes.
- [ ] **RB-3**: Verify Java is receiving traffic and returning correct responses.
- [ ] **RB-4**: If write ownership had been transferred (CO-7 completed), identify any records written by FastAPI since CO-6. Assess for data consistency issues.
  - If FastAPI writes are a superset of Java data (new records only): no action needed; Java will read them correctly.
  - If FastAPI writes modified existing records: run the domain-specific reconciliation script (must be prepared as part of pre-cutover).
- [ ] **RB-5**: Stop the FastAPI service (or isolate from DB writes) to prevent further divergence.
- [ ] **RB-6**: Revert the DB ownership record in `doc/postgresql-access-policy.md` §3 to Java.
- [ ] **RB-7**: File a post-mortem issue documenting the failure cause, timeline, and resolution steps before the next cutover attempt.

---

## 6. Java Retirement Criteria

Java code for a migrated domain may only be permanently removed when **all** of the following
criteria are satisfied:

| Criterion | Description |
|-----------|-------------|
| **JR-1: Stability window** | The FastAPI service has run in production with 100% traffic for at least **14 consecutive days** without a rollback. |
| **JR-2: Coverage confirmation** | Every endpoint in the domain's path scope returns correct responses as confirmed by the contract test suite. |
| **JR-3: DB write confirmation** | No Java code writes to the domain's owned tables (verified via DB audit logs or query tracing for the stability window). |
| **JR-4: Cross-domain dependencies resolved** | No other active Java domain code calls the domain's service beans or repositories. Verify via static analysis or integration tests. |
| **JR-5: Routing cleanup** | The reverse proxy no longer has routing rules for the Java monolith's path prefix for this domain. Java routes have been removed from the proxy config. |
| **JR-6: Documentation updated** | `doc/domain-boundary-map.md` has been updated to reflect the completed migration. `doc/postgresql-access-policy.md` ownership table has been updated. |
| **JR-7: Team sign-off** | Platform engineer and domain engineer sign off on the retirement in the domain's MDR. |

After all criteria are met:
1. Delete the Java controller, service, repository, and model classes for the domain.
2. Remove the domain's JPA entity registrations.
3. Run remaining Java tests to confirm no compile or test failures.
4. Deploy the reduced Java monolith.

---

## 7. How Domain Teams Use This Playbook

Each domain migration epic must:

1. **Reference this playbook** in the epic description (do not copy the checklist; link to this file).
2. **Create a Cutover Record** — a filled-in checklist instance stored at `doc/cutover-records/<service-name>-cutover.md` — containing:
   - Service name and path prefix
   - Target cutover date
   - On-call engineer names
   - Checkbox status for each item (completed/N/A with date and initials)
   - Rollback window start/end times (if rollback was executed)
   - Java retirement sign-off date
3. **Adapt where necessary**: If a specific checklist item is not applicable to the domain (e.g., the domain has no paginated endpoints), mark it `N/A` with a brief justification. Do not delete items from the master playbook.

This process ensures every cutover is traceable, comparable across domains, and produces a
clear audit trail for compliance purposes — without adding unnecessary release process overhead.
