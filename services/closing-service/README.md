# closing-service

FastAPI service for the HomeLend Pro **Closing/Settlement** domain.  
Wave 3 migration from the Java Spring Boot monolith.

---

## Responsibilities

- Closing detail management (scheduling, status, settlement figures)
- Closing document management (CLOSING_DISCLOSURE, DEED, NOTE, MORTGAGE, TITLE_INSURANCE)
- Title report management (PENDING → CLEAR / LIEN_FOUND / EXCEPTION)
- Escrow account management (balances, reserves, monthly payments)
- Escrow disbursement management (PROPERTY_TAX, HOMEOWNERS_INSURANCE, PMI, HOA)

See `doc/closing-service-boundary.md` for full scope definition.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/closings` | List all closings |
| `GET` | `/api/closings/{id}` | Get closing with sub-resources |
| `POST` | `/api/closings` | Create closing |
| `PUT` | `/api/closings/{id}` | Update closing |
| `DELETE` | `/api/closings/{id}` | Delete closing and sub-resources |
| `GET` | `/api/closings/{id}/documents` | List closing documents |
| `GET` | `/api/closings/{id}/documents/{docId}` | Get document |
| `POST` | `/api/closings/{id}/documents` | Add document |
| `PUT` | `/api/closings/{id}/documents/{docId}` | Update document |
| `DELETE` | `/api/closings/{id}/documents/{docId}` | Delete document |
| `GET` | `/api/closings/{id}/title-report` | List title reports |
| `GET` | `/api/closings/{id}/title-report/{reportId}` | Get title report |
| `POST` | `/api/closings/{id}/title-report` | Create title report |
| `PUT` | `/api/closings/{id}/title-report/{reportId}` | Update title report |
| `DELETE` | `/api/closings/{id}/title-report/{reportId}` | Delete title report |
| `GET` | `/api/closings/{id}/escrow` | List escrow accounts |
| `GET` | `/api/closings/{id}/escrow/{accountId}` | Get escrow account |
| `POST` | `/api/closings/{id}/escrow` | Create escrow account |
| `PUT` | `/api/closings/{id}/escrow/{accountId}` | Update escrow account |
| `DELETE` | `/api/closings/{id}/escrow/{accountId}` | Delete escrow account |
| `GET` | `/api/closings/{id}/escrow/{accountId}/disbursements` | List disbursements |
| `GET` | `/api/closings/{id}/escrow/{accountId}/disbursements/{disbId}` | Get disbursement |
| `POST` | `/api/closings/{id}/escrow/{accountId}/disbursements` | Create disbursement |
| `PUT` | `/api/closings/{id}/escrow/{accountId}/disbursements/{disbId}` | Update disbursement |
| `DELETE` | `/api/closings/{id}/escrow/{accountId}/disbursements/{disbId}` | Delete disbursement |
| `GET` | `/health` | Health check (no auth) |

All endpoints except `/health` require `Authorization: Bearer <JWT>`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL asyncpg URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | ✅ | Must match the Java monolith's JWT secret |
| `JWT_EXPIRATION_MS` | ✅ | Token TTL in ms (default: 86400000) |
| `FRONTEND_URL` | ✅ | Allowed CORS origin (e.g., `http://localhost:3000`) |

Copy `.env.example` to `.env` and fill in values before running locally.

---

## Running Locally

```bash
# From the repository root (services/ context required for shared/ module)
cd services
pip install -r closing-service/requirements.txt
DATABASE_URL=... JWT_SECRET=... JWT_EXPIRATION_MS=86400000 FRONTEND_URL=http://localhost:3000 \
  uvicorn closing-service.app.main:app --reload --port 8004
```

Or via Docker Compose:

```bash
docker compose up closing-service
```

---

## DB Tables Owned

| Table | Access |
|-------|--------|
| `closing_details` | Read + Write |
| `closing_documents` | Read + Write |
| `title_reports` | Read + Write |
| `escrow_accounts` | Read + Write |
| `escrow_disbursements` | Read + Write |
| `loan_applications` | Read-only |
| `listings` | Read-only |
| `clients` | Read-only |

Write ownership transfers from Java at Wave 3 cutover.  
See `doc/cutover-records/closing-service-cutover.md`.

---

## Cutover

See `doc/cutover-records/closing-service-cutover.md` for the full checklist.  
See `doc/cutover-playbook.md` for the playbook this record follows.
