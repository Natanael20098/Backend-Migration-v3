# Closing Service Boundary Definition

## Purpose

This document defines the exact scope of the `closing-service` FastAPI migration, including
owned entities, preserved external endpoints, dependencies on loan/listing/client/agent data,
and coupling risks. It is the authoritative reference for the Wave 3 closing migration epic.

---

## 1. Owned Responsibilities

The `closing-service` owns all read and write operations for the following domain areas:

### 1.1 Closing Detail Management

| Capability | Description |
|-----------|-------------|
| Closing CRUD | Create, read, update, and delete closing records (`closing_details` table) |
| Status lifecycle | Manages SCHEDULED → IN_PROGRESS → COMPLETED / CANCELLED / DELAYED lifecycle |
| Settlement figures | Stores total closing costs, seller credits, buyer credits, proration date |
| Closing coordination | Records closing date, time, location, and agent details for scheduling |

### 1.2 Closing Document Management

| Capability | Description |
|-----------|-------------|
| Document CRUD | Create, read, update, and delete closing documents (`closing_documents` table) |
| Document type support | Tracks CLOSING_DISCLOSURE, DEED, NOTE, MORTGAGE, TITLE_INSURANCE |
| Signing workflow | Records signed status, signed date, signed_by, and notarization details |

### 1.3 Title Report Management

| Capability | Description |
|-----------|-------------|
| Title report CRUD | Create, read, update, and delete title reports (`title_reports` table) |
| Status tracking | Manages PENDING, CLEAR, LIEN_FOUND, EXCEPTION outcomes |
| Issue recording | Stores title issues (JSON as TEXT per legacy schema), lien amounts |
| Date tracking | Stores report date and effective date |

### 1.4 Escrow Account Management

| Capability | Description |
|-----------|-------------|
| Escrow account CRUD | Create, read, update, and delete escrow accounts (`escrow_accounts` table) |
| Reserve tracking | Manages property tax reserve, insurance reserve, PMI reserve, cushion months |
| Balance management | Tracks current balance and monthly payment |
| Status management | Manages ACTIVE / CLOSED escrow account status |

### 1.5 Escrow Disbursement Management

| Capability | Description |
|-----------|-------------|
| Disbursement CRUD | Create, read, update, and delete disbursements (`escrow_disbursements` table) |
| Disbursement types | Supports PROPERTY_TAX, HOMEOWNERS_INSURANCE, PMI, HOA |
| Payment tracking | Records payee, payee account, paid date, check number, confirmation |

### 1.6 Sub-Resource Reads (Cross-Domain, Read-Only)

| Resource | Source Table | Access Type |
|----------|-------------|-------------|
| Loan application summary | `loan_applications` | Read-only (owned by loan-origination-service / Java) |
| Listing details | `listings` | Read-only (owned by property-listing-service) |
| Client/buyer/seller details | `clients` | Read-only (owned by client-crm-service / Java) |
| Agent details | `agents` | Read-only (owned by client-crm-service / Java) |

---

## 2. Preserved Endpoints and Interactions

The following endpoints are served by the Java `ClosingController` and must be reimplemented
with identical external contracts. Path, method, and response shape must match the rules in
`doc/api-compatibility-rules.md`.

### 2.1 Closing Detail Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/closings` | Returns list of all closing details |
| `GET` | `/api/closings/{id}` | Returns single closing with embedded sub-resources |
| `POST` | `/api/closings` | Returns 201 with created closing |
| `PUT` | `/api/closings/{id}` | Returns 200 with updated closing |
| `DELETE` | `/api/closings/{id}` | Returns 204; cascades to documents, title reports, escrow accounts |

### 2.2 Closing Document Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/closings/{id}/documents` | Returns list of documents for closing |
| `GET` | `/api/closings/{id}/documents/{docId}` | Returns single document |
| `POST` | `/api/closings/{id}/documents` | Returns 201 with created document |
| `PUT` | `/api/closings/{id}/documents/{docId}` | Returns 200 with updated document |
| `DELETE` | `/api/closings/{id}/documents/{docId}` | Returns 204 |

### 2.3 Title Report Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/closings/{id}/title-report` | Returns list of title reports for closing |
| `GET` | `/api/closings/{id}/title-report/{reportId}` | Returns single title report |
| `POST` | `/api/closings/{id}/title-report` | Returns 201 with created title report |
| `PUT` | `/api/closings/{id}/title-report/{reportId}` | Returns 200 with updated title report |
| `DELETE` | `/api/closings/{id}/title-report/{reportId}` | Returns 204 |

### 2.4 Escrow Account Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/closings/{id}/escrow` | Returns list of escrow accounts for closing |
| `GET` | `/api/closings/{id}/escrow/{accountId}` | Returns escrow account with embedded disbursements |
| `POST` | `/api/closings/{id}/escrow` | Returns 201 with created escrow account |
| `PUT` | `/api/closings/{id}/escrow/{accountId}` | Returns 200 with updated escrow account |
| `DELETE` | `/api/closings/{id}/escrow/{accountId}` | Returns 204; cascades to disbursements |

### 2.5 Escrow Disbursement Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/closings/{id}/escrow/{accountId}/disbursements` | Returns list of disbursements |
| `GET` | `/api/closings/{id}/escrow/{accountId}/disbursements/{disbId}` | Returns single disbursement |
| `POST` | `/api/closings/{id}/escrow/{accountId}/disbursements` | Returns 201 with created disbursement |
| `PUT` | `/api/closings/{id}/escrow/{accountId}/disbursements/{disbId}` | Returns 200 with updated disbursement |
| `DELETE` | `/api/closings/{id}/escrow/{accountId}/disbursements/{disbId}` | Returns 204 |

---

## 3. Dependencies on Loan, Listing, Client, and Agent Data

### 3.1 Loan Application Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Loan existence validation | `closing_details.loan_application_id` references a loan; loan must exist for embedded summaries | Read-only SELECT on `loan_applications` when embedding loan summary |
| Loan data in responses | Closing detail responses embed loan summary (type, amount, status) | Join via `loan_application_id` FK using SQLAlchemy `selectin` loading |
| Loan write ownership | `loan_applications` is owned by loan-origination-service / Java during Wave 3 | No writes to `loan_applications` from this service |

### 3.2 Listing Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Listing in closing | `closing_details.listing_id` references the listing being closed | Read-only SELECT on `listings` when embedding listing summary |
| Listing write ownership | `listings` is owned by property-listing-service | No writes to `listings` from this service |

### 3.3 Client Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Borrower in loan summary | Loan application summary embeds borrower (client) details | Read-only SELECT on `clients` via loan_application.borrower_id |
| Client write ownership | `clients` is owned by client-crm-service / Java | No writes to `clients` from this service |

### 3.4 Agent Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Closing coordination agent | `closing_details.closing_agent_name` and `closing_agent_email` are denormalized strings (no FK to agents) | No agent FK join required; denormalized fields are read as-is |
| Agent write ownership | `agents` is owned by client-crm-service / Java | No writes to `agents` from this service |

### 3.5 Auth Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| JWT validation | All closing endpoints require `Authorization: Bearer <token>` | Use `shared.auth.make_get_current_user(settings.JWT_SECRET)` dependency |
| JWT secret | Must be identical to the Java monolith's `JWT_SECRET` | Sourced from `JWT_SECRET` env var |

---

## 4. Risks from Coupling

### 4.1 loan_applications Write Ownership Dependency

The closing-service depends on `loan_applications` existing for embedding loan summaries in
closing detail responses.

**Risk**: If a loan application is deleted by Java while closing records exist for it, the FK
in `closing_details.loan_application_id` will either prevent deletion (FK violation) or leave
an orphaned closing record.

**Mitigation**: The closing-service does not validate loan existence before creating a closing
(the Java ClosingController did not enforce this either — the FK is nullable). Responses
degrade gracefully if no loan is associated.

### 4.2 listings FK Dependency

`closing_details.listing_id` references `listings.id`. The `property-listing-service` owns
`listings` writes.

**Risk**: If a listing is deleted while a closing record references it, FK violation occurs
unless ON DELETE SET NULL or ON DELETE CASCADE is defined (the schema uses no explicit cascade).

**Mitigation**: Both FK columns (`loan_application_id`, `listing_id`) are nullable. The
closing-service does not validate their existence before writing. During parallel run, listing
and loan deletions are coordinated by the respective service teams.

### 4.3 Escrow Disbursements FK Dependency on escrow_accounts

`escrow_disbursements.escrow_account_id` references `escrow_accounts.id`. The closing-service
owns both tables, so this dependency is internal.

**Mitigation**: On DELETE of an escrow account, the closing-service explicitly deletes all
child disbursements first (cascades are not defined at the DB schema level).

### 4.4 Financial Settlement Sensitivity

Closing costs, escrow balances, and disbursement records have financial and legal significance.

**Mitigation**: This service stores settlement figures provided by callers — it does not
calculate closing costs or automatically trigger disbursements. All financial values are
provided explicitly via API request bodies. Validation via Pydantic enforces required field
presence on create operations.

### 4.5 Denormalized Column Policy

Per `postgresql-access-policy.md` §4, the following denormalized columns exist in owned tables
but must **not** be written by this service:

| Column | Table | Policy |
|--------|-------|--------|
| `property_address` | `closing_details` | Do not write; legacy Java artifact |
| `buyer_name` | `closing_details` | Do not write; legacy Java artifact |
| `seller_name` | `closing_details` | Do not write; legacy Java artifact |
| `loan_amount` | `closing_details` | Do not write; legacy Java artifact |
| `sale_price` | `closing_details` | Do not write; legacy Java artifact |
| `borrower_name` | `escrow_accounts` | Do not write; legacy Java artifact |
| `property_address` | `escrow_accounts` | Do not write; legacy Java artifact |
| `property_address` | `escrow_disbursements` | Do not write; legacy Java artifact |
| `borrower_name` | `escrow_disbursements` | Do not write; legacy Java artifact |
| `property_address` | `title_reports` | Do not write; legacy Java artifact |
| `owner_name` | `title_reports` | Do not write; legacy Java artifact |

---

## 5. Summary

| Attribute | Value |
|-----------|-------|
| **Service name** | `closing-service` |
| **Path prefixes owned** | `/api/closings/*` |
| **Port** | `8004` |
| **DB tables owned (write)** | `closing_details`, `closing_documents`, `title_reports`, `escrow_accounts`, `escrow_disbursements` |
| **DB tables read (cross-domain)** | `loan_applications`, `listings`, `clients`, `agents` |
| **Migration wave** | Wave 3 |
| **Auth dependency** | Shared `JWT_SECRET`; validates tokens from `auth-service` or Java |
| **External service dependencies** | None (reads loan/listing/client data directly from shared DB) |
| **Cutover record** | `doc/cutover-records/closing-service-cutover.md` |
| **Prerequisite services** | Wave 1 (`property-listing-service`), Wave 2 (`loan-origination-service`, `client-crm-service`) should be stable before Wave 3 cutover |
