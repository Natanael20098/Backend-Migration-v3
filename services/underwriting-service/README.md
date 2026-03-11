# underwriting-service

FastAPI service for the underwriting domain. Implements credit report management,
underwriting decisions/conditions, and appraisal order/report tracking.

Migrated from the Java `UnderwritingController` and `UnderwritingService` as part of the
HomeLend Pro backend migration (Wave 3).

---

## Endpoints

### Credit Reports

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/loans/{loanId}/credit-report` | List all credit reports for a loan |
| `GET` | `/api/loans/{loanId}/credit-report/{reportId}` | Get a single credit report |
| `POST` | `/api/loans/{loanId}/credit-report` | Create a credit report (returns 201) |
| `PUT` | `/api/loans/{loanId}/credit-report/{reportId}` | Update a credit report |
| `DELETE` | `/api/loans/{loanId}/credit-report/{reportId}` | Delete a credit report (returns 204) |

### Underwriting Decisions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/loans/{loanId}/underwriting` | List all underwriting decisions for a loan |
| `GET` | `/api/loans/{loanId}/underwriting/{decisionId}` | Get a single underwriting decision |
| `POST` | `/api/loans/{loanId}/underwriting` | Record an underwriting decision (returns 201) |
| `PUT` | `/api/loans/{loanId}/underwriting/{decisionId}` | Update an underwriting decision |
| `DELETE` | `/api/loans/{loanId}/underwriting/{decisionId}` | Delete a decision and its conditions (returns 204) |

### Underwriting Conditions

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/loans/{loanId}/underwriting/{decisionId}/conditions` | List conditions for a decision |
| `POST` | `/api/loans/{loanId}/underwriting/{decisionId}/conditions` | Add a condition (returns 201) |
| `PUT` | `/api/loans/{loanId}/underwriting/{decisionId}/conditions/{conditionId}` | Update a condition |
| `DELETE` | `/api/loans/{loanId}/underwriting/{decisionId}/conditions/{conditionId}` | Delete a condition (returns 204) |

### Appraisal Orders

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/loans/{loanId}/appraisal` | List all appraisal orders for a loan |
| `GET` | `/api/loans/{loanId}/appraisal/{orderId}` | Get a single appraisal order |
| `POST` | `/api/loans/{loanId}/appraisal` | Create an appraisal order (returns 201) |
| `PUT` | `/api/loans/{loanId}/appraisal/{orderId}` | Update an appraisal order |
| `DELETE` | `/api/loans/{loanId}/appraisal/{orderId}` | Delete order and reports (returns 204) |

### Appraisal Reports

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/loans/{loanId}/appraisal/{orderId}/report` | List all reports for an order |
| `GET` | `/api/loans/{loanId}/appraisal/{orderId}/report/{reportId}` | Get a single report |
| `POST` | `/api/loans/{loanId}/appraisal/{orderId}/report` | Submit an appraisal report (returns 201) |
| `PUT` | `/api/loans/{loanId}/appraisal/{orderId}/report/{reportId}` | Update a report |

### Comparable Sales

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/loans/{loanId}/appraisal/{orderId}/report/{reportId}/comparables` | List comparable sales |
| `POST` | `/api/loans/{loanId}/appraisal/{orderId}/report/{reportId}/comparables` | Add a comparable sale (returns 201) |

---

## Authentication

All endpoints require `Authorization: Bearer <token>` with a valid JWT signed with `JWT_SECRET`.
Tokens are HMAC-HS256 and are interoperable between this service and the Java monolith.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://` URL for the shared Supabase PostgreSQL instance |
| `JWT_SECRET` | Yes | Shared HMAC-HS256 signing secret (must match all other services) |
| `JWT_EXPIRATION_MS` | No | Token expiry in milliseconds (default: 86400000) |
| `FRONTEND_URL` | No | Allowed CORS origin (default: `http://localhost:3000`) |

---

## DB Table Ownership

| Table | Access Type | Notes |
|-------|-------------|-------|
| `credit_reports` | **Write** (after cutover) | Owned post-Wave 3 cutover |
| `underwriting_decisions` | **Write** (after cutover) | Owned post-Wave 3 cutover |
| `underwriting_conditions` | **Write** (after cutover) | Child of underwriting_decisions |
| `appraisal_orders` | **Write** (after cutover) | Owned post-Wave 3 cutover |
| `appraisal_reports` | **Write** (after cutover) | Child of appraisal_orders |
| `comparable_sales` | **Write** (after cutover) | Child of appraisal_reports |
| `loan_applications` | **Read-only** | Owned by loan-origination-service / Java |
| `properties` | **Read-only** | Owned by property-listing-service |
| `clients` | **Read-only** | Owned by client-crm-service / Java |
| `agents` | **Read-only** | Owned by client-crm-service / Java |

---

## Running Locally

```bash
# From the repo root
cd services/underwriting-service
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://... JWT_SECRET=... uvicorn app.main:app --port 8003 --reload
```

---

## Running with Docker

```bash
# From the repo root (build context must be ./services)
docker build -f services/underwriting-service/Dockerfile -t underwriting-service ./services
docker run -p 8003:8003 --env-file .env underwriting-service
```

Or use Docker Compose:

```bash
docker compose up underwriting-service
```

---

## Smoke Tests

```bash
# Health check (no auth required)
curl http://localhost:8003/health

# List credit reports for a loan (requires JWT)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/loans/<loan-id>/credit-report

# List underwriting decisions
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/loans/<loan-id>/underwriting

# List appraisal orders
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost/api/loans/<loan-id>/appraisal
```

---

## Cutover Record

See `doc/cutover-records/underwriting-service-cutover.md` for the full cutover checklist and results.
