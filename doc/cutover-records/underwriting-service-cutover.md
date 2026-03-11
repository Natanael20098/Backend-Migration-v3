# Cutover Record: underwriting-service

**Playbook reference**: `doc/cutover-playbook.md`
**Service**: `underwriting-service`
**Path prefixes**: `/api/loans/{id}/credit-report`, `/api/loans/{id}/underwriting`, `/api/loans/{id}/appraisal`
**Migration wave**: Wave 3
**Port**: `8003`

---

## Checklist Status

> **Legend**: ✅ Complete | 🔲 Pending | N/A Not applicable
>
> Fill in the date and initials next to each item as it is completed.

---

## Pre-Cutover Checklist

### Routing Readiness

| Item | Status | Date | Notes |
|------|--------|------|-------|
| **PC-R1** — Nginx upstream `underwriting_service` and location blocks defined for `/api/loans/` prefix pointing to underwriting-service | 🔲 | | Nginx config updated; traffic weight = 0% (commented out) until pre-cutover items complete |
| **PC-R2** — `GET /health` returns 200 from underwriting-service in production | 🔲 | | Smoke test: `curl http://underwriting-service:8003/health` |
| **PC-R3** — Service connects to shared PostgreSQL and passes a read query | 🔲 | | Test: `GET /api/loans/<known-id>/credit-report` returns 200 or 404 (not 500) |
| **PC-R4** — `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRATION_MS` confirmed set correctly in production deployment | 🔲 | | |

### Contract Checks

| Item | Status | Date | Notes |
|------|--------|------|-------|
| **PC-C1** — All endpoints verified against `doc/api-compatibility-rules.md` (R-URL-*, R-MTH-*, R-REQ-*, R-RES-*, R-STS-*, R-AUTH-*, R-ERR-*) | 🔲 | | |
| **PC-C2** — Contract test suite exists for underwriting endpoints and passes against FastAPI in staging | 🔲 | | |
| **PC-C3** — Response payloads diffed against Java responses for ≥3 representative requests per endpoint | 🔲 | | Focus on: `GET /underwriting`, `POST /underwriting`, `GET /credit-report` |
| **PC-C4** — N/A: No paginated endpoints in underwriting service | N/A | | All list endpoints return flat arrays |
| **PC-C5** — JWT from Java monolith accepted by underwriting-service | 🔲 | | Test with token issued by Java `AuthController` |
| **PC-C6** — Error shapes match: `{"message": "..."}` for 400/404, 401 for invalid JWT | 🔲 | | |

### Database Readiness

| Item | Status | Date | Notes |
|------|--------|------|-------|
| **PC-D1** — DB table ownership confirmed per `doc/postgresql-access-policy.md` §3 (Wave 3 tables) | 🔲 | | Java retains write ownership until CO-7 completes |
| **PC-D2** — No pending Alembic migrations that modify Wave 3 or shared tables | 🔲 | | No schema changes required for underwriting-service implementation |
| **PC-D3** — Service confirmed to NOT execute DDL on startup | ✅ | | No `Base.metadata.create_all()` call; lifespan only creates engine |

### Smoke Tests

| Item | Status | Date | Notes |
|------|--------|------|-------|
| **PC-S1** — End-to-end smoke tests pass against production DB (read-only) | 🔲 | | See smoke test commands below |
| **PC-S2** — Frontend smoke-tested against underwriting-service in staging | 🔲 | | Loan detail page loads; underwriting section visible |
| **PC-S3** — Auth flow end-to-end: login → token → call `/api/loans/{id}/underwriting` → 200 | 🔲 | | |

### Rollback Readiness

| Item | Status | Date | Notes |
|------|--------|------|-------|
| **PC-RB1** — Rollback procedure reviewed by on-call engineer | 🔲 | | See §Rollback below |
| **PC-RB2** — Java monolith running and passing its own smoke tests at cutover time | 🔲 | | |
| **PC-RB3** — Proxy routing can be reverted to 100% Java in < 2 minutes | 🔲 | | Revert nginx location blocks; no deploy required |

---

## Cutover Checklist

### Traffic Shift

| Item | Status | Date/Time | Notes |
|------|--------|-----------|-------|
| **CO-1** — Cutover announced; start time recorded | 🔲 | | |
| **CO-2** — 10% traffic shifted to underwriting-service; monitored 5 min; error rate < 0.1% 5xx | 🔲 | | |
| **CO-3** — 50% traffic shifted; monitored 10 min; error rate acceptable | 🔲 | | |
| **CO-4** — 100% traffic shifted to underwriting-service; monitored 15 min | 🔲 | | |
| **CO-5** — Java routes for underwriting paths set to 0% (kept alive for rollback) | 🔲 | | |

### Write Ownership Transfer

| Item | Status | Date/Time | Notes |
|------|--------|-----------|-------|
| **CO-6** — In-flight Java write requests for underwriting domain drained (30s after traffic = 0%) | 🔲 | | |
| **CO-7** — `doc/postgresql-access-policy.md` §3 updated: Wave 3 underwriting tables → FastAPI: underwriting-service | 🔲 | | Tables: credit_reports, underwriting_decisions, underwriting_conditions, appraisal_orders, appraisal_reports, comparable_sales |
| **CO-8** — FastAPI successfully writing: create and read one record per core resource type | 🔲 | | Test create + retrieve for each of: credit_report, underwriting_decision, underwriting_condition, appraisal_order, appraisal_report |

---

## Validation Checklist

### Immediate Post-Cutover (T+0 to T+1 hour)

| Item | Status | Date/Time | Notes |
|------|--------|-----------|-------|
| **V-1** — Error rate for underwriting path prefix below pre-cutover Java baseline | 🔲 | | |
| **V-2** — Response latency p95 ≤ 2× Java baseline | 🔲 | | |
| **V-3** — N/A: No paginated endpoints | N/A | | |
| **V-4** — JWT-protected endpoints reject invalid tokens with 401 | 🔲 | | |
| **V-5** — At least one create, read, update, delete per core resource verified via production API | 🔲 | | |
| **V-6** — Frontend Loan Detail page functions normally; underwriting section loads | 🔲 | | |
| **V-7** — N/A: Audit log writes not implemented in Wave 3 (planned for admin-service wave) | N/A | | |

### Stability (T+24 hours)

| Item | Status | Date/Time | Notes |
|------|--------|-----------|-------|
| **V-8** — No elevated error rates in preceding 24 hours | 🔲 | | |
| **V-9** — No data consistency issues; spot-check DB records written by FastAPI | 🔲 | | |
| **V-10** — Java logs show no writes to Wave 3 underwriting tables | 🔲 | | Verify via DB audit log or query tracing |
| **V-11** — Rollback deadline passed; cutover confirmed stable | 🔲 | | |

---

## Java Retirement Status

Retirement is blocked until **all** of the following are satisfied (per `doc/cutover-playbook.md` §6):

| Criterion | Status | Date | Notes |
|-----------|--------|------|-------|
| **JR-1** — 14-day stability window complete | 🔲 | | Start date: ___ |
| **JR-2** — All underwriting endpoints verified by contract test suite | 🔲 | | |
| **JR-3** — No Java writes to underwriting tables confirmed | 🔲 | | |
| **JR-4** — No other Java domain code calls `UnderwritingService` or `UnderwritingController` beans | 🔲 | | Requires static analysis or integration tests |
| **JR-5** — Nginx routes for Java underwriting paths removed from proxy config | 🔲 | | |
| **JR-6** — `doc/domain-boundary-map.md` and `doc/postgresql-access-policy.md` updated | 🔲 | | |
| **JR-7** — Platform engineer and domain engineer sign off | 🔲 | | Platform eng: ___ Domain eng: ___ |

**Java classes to remove after retirement:**
- `com.zcloud.platform.controller.UnderwritingController`
- `com.zcloud.platform.service.UnderwritingService`
- `com.zcloud.platform.model.CreditReport`
- `com.zcloud.platform.model.UnderwritingDecision`
- `com.zcloud.platform.model.UnderwritingCondition`
- `com.zcloud.platform.model.AppraisalOrder`
- `com.zcloud.platform.model.AppraisalReport`
- `com.zcloud.platform.model.ComparableSale`
- `com.zcloud.platform.repository.CreditReportRepository`
- `com.zcloud.platform.repository.UnderwritingDecisionRepository`
- `com.zcloud.platform.repository.UnderwritingConditionRepository`
- `com.zcloud.platform.repository.AppraisalOrderRepository`
- `com.zcloud.platform.repository.AppraisalReportRepository`
- `com.zcloud.platform.repository.ComparableSaleRepository`

---

## Rollback Procedure

If any cutover or validation step fails:

1. **RB-1** — Announce rollback; record start time and failure reason.
2. **RB-2** — In nginx.conf, revert underwriting location blocks to `proxy_pass http://java_monolith`. Reload nginx (`docker compose exec gateway nginx -s reload`). Time target: < 2 minutes.
3. **RB-3** — Verify Java is receiving traffic: `curl -H "Authorization: Bearer $TOKEN" http://localhost/api/loans/<id>/underwriting` returns expected response.
4. **RB-4** — If CO-7 completed, assess FastAPI writes since CO-6. Underwriting-service only creates new records (no in-place modification of loan_applications); new records are safe for Java to read.
5. **RB-5** — Stop underwriting-service: `docker compose stop underwriting-service`.
6. **RB-6** — Revert `doc/postgresql-access-policy.md` §3 to Java as writer for Wave 3 tables.
7. **RB-7** — File post-mortem issue before next cutover attempt.

---

## Smoke Test Commands

```bash
# Health check (no auth)
curl -I http://localhost:8003/health

# Via gateway (requires valid JWT)
export TOKEN="<jwt-from-login>"

# List credit reports for a loan
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/loans/<loan-id>/credit-report

# Create a credit report
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bureau":"EQUIFAX","score":720,"reportDate":"2025-01-31"}' \
  http://localhost/api/loans/<loan-id>/credit-report

# List underwriting decisions
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/loans/<loan-id>/underwriting

# Create an underwriting decision
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"decision":"APPROVED","dtiRatio":35.5,"ltvRatio":80.0}' \
  http://localhost/api/loans/<loan-id>/underwriting

# List appraisal orders
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/loans/<loan-id>/appraisal

# Invalid token — should return 401
curl -H "Authorization: Bearer invalid-token" \
  http://localhost/api/loans/<loan-id>/underwriting
```

---

## Cutover Results

> Fill in after cutover is complete.

| Field | Value |
|-------|-------|
| **Cutover start time** | |
| **100% traffic cutover time** | |
| **Write ownership transfer time** | |
| **Rollback executed?** | No |
| **Issues encountered** | None |
| **Stability window start** | |
| **Java retirement date** | |
| **Platform engineer sign-off** | |
| **Domain engineer sign-off** | |
