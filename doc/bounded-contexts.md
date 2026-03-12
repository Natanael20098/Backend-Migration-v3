# Bounded Contexts and Dependency Rules

## Purpose

This document defines the bounded contexts for the HomeLend Pro backend using Clean Architecture
terminology. It maps each context to its current FastAPI service implementation, establishes
explicit dependency rules (allowed and forbidden), defines the shared kernel scope, and assesses
extraction readiness for future microservice decomposition.

**Inputs to this document**:
- `doc/domain-boundary-map.md` — Java class → service ownership map
- `doc/domain-persistence-analysis.md` — entity relationships and aggregate candidates
- `doc/remaining-domains-inventory.md` — wave ranking and treatment decisions
- `services/shared/` — canonical shared kernel implementation

---

## 1. Bounded Context Definitions

Each bounded context definition covers: owned responsibilities, domain layer entities,
application layer, infrastructure layer, allowed outbound reads, published events, and key constraints.

---

### 1.1 Identity & Access — `auth-service` (port 8001)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/auth/*` |
| **Migration status** | ✅ MIGRATED (Wave 1) |

**Owned responsibilities**:
- OTP lifecycle management (generation, expiry, rate limiting, single-use enforcement)
- JWT token issuance (HS256, `sub=email`, `iat`, `exp`)
- Email delivery of OTP codes via Mailgun

**Domain layer entities**:
- `OtpCode` (`otp_codes` table) — aggregate root; owns its full lifecycle

**Application layer**:
- `POST /api/auth/send-otp` — OTP generation + rate limit check + email dispatch
- `POST /api/auth/verify-otp` — OTP validation + JWT issuance

**Infrastructure layer**:
- PostgreSQL: `otp_codes` table (write owner)
- Mailgun HTTP API: OTP email delivery (`app/mailgun.py`)

**Allowed outbound reads**:
- `clients` table — read-only during parallel run (email existence verification if needed)

**Published events**: None — token returned synchronously in HTTP response.

**Key constraints**:
- `jwt.encode()` may only be called from `auth-service/app/router.py`. No other service may issue tokens.
- OTP codes are single-use (`used=true` after verification) and time-limited (`expires_at`).
- Rate limit enforced per email per hour (`OTP_RATE_LIMIT_PER_HOUR`).
- Response to `send-otp` is identical regardless of email existence (prevents user enumeration).

---

### 1.2 Content / Property Listing — `property-listing-service` (port 8002)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/properties/*`, `/api/listings/*` |
| **Migration status** | ✅ MIGRATED (Wave 1) |

**Owned responsibilities**:
- Property CRUD (address, attributes, type, location)
- Property images and tax records
- Listing lifecycle (MLS number, status machine, list price, dates)
- Open house scheduling

**Domain layer entities**:
- `Property` (aggregate root) → `PropertyImage`, `PropertyTaxRecord`
- `Listing` (aggregate root) → `OpenHouse`

**Application layer**:
- Full CRUD for properties and listings
- Property search (multi-field filter, ILIKE, up to 200 results)
- Listing status state machine (ACTIVE/PENDING/SOLD/WITHDRAWN/EXPIRED/COMING_SOON)
- Open house scheduling (ACTIVE listings only, no past dates)

**Infrastructure layer**:
- PostgreSQL: `properties`, `property_images`, `property_tax_records`, `listings`, `open_houses` (write owner for all)

**Allowed outbound reads**:
- `agents` table — read-only (agent details for listing responses; agent existence check on listing create)

**Published events**: None.

**Key constraints**:
- No JWT authentication on property/listing endpoints (see `doc/jwt-validation-policy.md` §10 and §3.5 in `doc/auth-flow-analysis.md` for the compatibility risk note).
- Listing deletion blocked if open houses exist (409).
- `tax_records`: duplicate year for same property returns 409.
- SOLD is a terminal listing status — no transitions from SOLD are allowed.

---

### 1.3 Client CRM / Agent — `client-crm-service` (port 8005)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/clients/*`, `/api/leads/*`, `/api/showings/*`, `/api/offers/*`, `/api/brokerages/*`, `/api/agents/*` |
| **Migration status** | ✅ MIGRATED (Wave 2A) |

**Owned responsibilities**:
- Client management (profile, PII handling, documents)
- Lead tracking and lifecycle
- Showing scheduling
- Offer submission and counter-offer negotiation
- Agent and brokerage management
- Commission tracking

**Domain layer entities**:
- `Client` (aggregate root) → `ClientDocument`, `Lead`
- `Agent` (aggregate root) → `AgentLicense`, `Commission`
- `Brokerage`
- `Showing`
- `Offer` (aggregate root) → `CounterOffer`

**Application layer**:
- Full CRUD for clients, leads, showings, offers, counter-offers, agents, agent licenses, brokerages, commissions
- Offer status machine (PENDING → ACCEPTED/REJECTED/COUNTERED/WITHDRAWN)
- Showing status management

**Infrastructure layer**:
- PostgreSQL: `clients`, `client_documents`, `leads`, `showings`, `offers`, `counter_offers`, `agents`, `agent_licenses`, `brokerages`, `commissions` (write owner for all)

**Allowed outbound reads**:
- `listings` table — read-only (for showing/offer context — listing details, status checks)
- `properties` table — read-only (property details in client/lead context)

**Published events**: None.

**Key constraints**:
- `ssn_encrypted` in `clients` table must **never** appear in any API response or log output.
- Denormalized columns (`agent_name`, `client_name`, etc.) in `commissions` and other tables must not be written by FastAPI — they are Java legacy read-only artifacts.
- Before deleting an agent, verify no active listings/showings/commissions reference them (application-layer guard — no DB-level cascade).

---

### 1.4 Loan Origination — `loan-origination-service` (Wave 2B — **not yet deployed**)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/loans/*` (base CRUD, excluding sub-resources) |
| **Migration status** | ❌ NOT MIGRATED — planned port 8006 |

**Owned responsibilities**:
- Loan application lifecycle (STARTED → SUBMITTED → IN_REVIEW → APPROVED/DENIED → FUNDED)
- Borrower employment and asset collection
- Loan payment recording
- Payment schedule generation

**Domain layer entities**:
- `LoanApplication` (aggregate root) → `BorrowerEmployment`, `BorrowerAsset`, `LoanPayment`, `PaymentSchedule`

**Application layer**:
- Full CRUD for loan applications and sub-resources
- Status machine for loan lifecycle (state transitions trigger downstream underwriting/closing workflows)

**Infrastructure layer**:
- PostgreSQL: `loan_applications`, `borrower_employment`, `borrower_assets`, `loan_payments`, `payment_schedules` (write owner — currently Java)

**Allowed outbound reads**:
- `clients` table — borrower profile
- `properties` table — collateral property details

**Published events**: Loan status transitions must eventually trigger underwriting and closing workflow initiation. Currently Java handles this via `MasterService`; FastAPI implementation requires explicit event or API coordination design (out of scope for this epic).

**Key constraints**:
- `MasterService` decomposition required before implementation.
- Wave 2B is gated on `client-crm-service` (Wave 2A) stability.
- Must not write to `underwriting_*` or `closing_*` tables.

---

### 1.5 Underwriting — `underwriting-service` (port 8003)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/loans/{id}/credit-report`, `/api/loans/{id}/underwriting`, `/api/loans/{id}/appraisal/*` |
| **Migration status** | ✅ MIGRATED (Wave 3A) |

**Owned responsibilities**:
- Credit report ordering and storage
- Underwriting decision recording and condition management
- Appraisal ordering, report submission, comparable sales analysis

**Domain layer entities**:
- `UnderwritingDecision` (aggregate root) → `UnderwritingCondition`
- `AppraisalOrder` (aggregate root) → `AppraisalReport` → `ComparableSale`
- `CreditReport`

**Application layer**:
- GET/POST for credit reports
- GET/POST/PUT for underwriting decisions
- GET/POST for appraisal orders, reports, and comparables

**Infrastructure layer**:
- PostgreSQL: `credit_reports`, `underwriting_decisions`, `underwriting_conditions`, `appraisal_orders`, `appraisal_reports`, `comparable_sales` (write owner for all)

**Allowed outbound reads**:
- `loan_applications` table — loan context (borrower, property, status); currently Java-written (Wave 2B gap)
- `clients` table — borrower details
- `properties` table — collateral property details

**Published events**: None.

**Key constraints**:
- Must not modify `loan_applications.status` or any field on `loan_applications`.
- Must not write to `closing_*` tables.
- Underwriting decisions are regulatory-sensitive — decision logic must be preserved exactly.

---

### 1.6 Closing / Settlement — `closing-service` (port 8004)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/closings/*` |
| **Migration status** | ✅ MIGRATED (Wave 3B) |

**Owned responsibilities**:
- Closing scheduling and detail tracking
- Closing document management
- Title report tracking
- Escrow account management and disbursements

**Domain layer entities**:
- `ClosingDetail` (aggregate root) → `ClosingDocument`, `TitleReport`, `EscrowAccount` → `EscrowDisbursement`

**Application layer**:
- Full CRUD for closings, documents, title reports, escrow accounts, disbursements
- Application-layer cascade: deleting ClosingDetail removes all children in dependency order

**Infrastructure layer**:
- PostgreSQL: `closing_details`, `closing_documents`, `title_reports`, `escrow_accounts`, `escrow_disbursements` (write owner for all)

**Allowed outbound reads**:
- `loan_applications` table — loan context (currently Java-written, Wave 2B gap)
- `listings` table — property/listing context
- `clients` table — buyer/seller details
- `agents` table — agent involved in closing

**Published events**: None.

**Key constraints**:
- Escrow financial totals must not be calculated by this service alone — coordination with underwriting is required for production accuracy.
- Must not write to `loan_applications`, `underwriting_*`, or any table outside its 5 owned tables.

---

### 1.7 Shared Kernel — `services/shared/`

The shared kernel is the only module that all services depend on. It contains **only**
infrastructure cross-cutting concerns, never domain logic.

| Attribute | Value |
|-----------|-------|
| **Location** | `services/shared/` |
| **Depends on** | Nothing else in this repository |

**Contents (what IS in shared kernel)**:

| Module | Contents |
|--------|----------|
| `shared/models.py` | `CamelModel` (alias_generator=to_camel, populate_by_name=True), `PageResponse[T]`, `ErrorResponse` |
| `shared/auth.py` | `verify_jwt(token, secret)`, `make_get_current_user(secret)` — JWT validation factory using PyJWT HS256 |
| `shared/database.py` | `create_engine_from_settings()` — async SQLAlchemy engine factory (asyncpg, prepare_threshold=0) |
| `shared/config.py` | `BaseSettings` base class for service configuration |
| `shared/exceptions.py` | 422→400 remapping exception handler; `{"message": "..."}` error response producer |
| `shared/health.py` | Health endpoint factory returning `{"status": "ok"}` at `/health` |

**What is NOT in shared kernel**:
- Domain entities or business rules
- Service-specific configuration values (JWT_SECRET, DATABASE_URL, etc. belong in each service's `config.py`)
- Email sending logic (belongs in auth-service)
- Any `models.py` SQLAlchemy table mappings (belong in each service's `app/models.py`)
- Any router logic

**Shared kernel rule**: If a new module is a candidate for `services/shared/`, verify:
1. It is used by 3+ services, AND
2. It contains no domain logic, AND
3. It is purely infrastructure or serialization concern.

---

### 1.8 Admin / Ops — Java monolith (Wave 4 — deferred)

| Attribute | Value |
|-----------|-------|
| **Path prefix** | `/api/admin/*` |
| **Migration status** | ❌ DEFERRED (Wave 4) — Java monolith retains this domain |

**Owned responsibilities**: System settings, audit logging, notification management, reporting.

**Domain layer entities**: `SystemSetting`, `AuditLog`, `Notification`.

**Deferred per**: `doc/remaining-domains-inventory.md` §3.2.

**Current state**: Each FastAPI service writes audit records directly to `audit_logs` using its own DB session until Wave 4 transfers write ownership to `admin-service`.

---

## 2. Dependency Rules (Allowed and Forbidden)

### 2.1 Allowed dependencies

```
ALLOWED dependency directions:

auth-service              → services/shared/
property-listing-service  → services/shared/
client-crm-service        → services/shared/
loan-origination-service  → services/shared/
underwriting-service      → services/shared/
closing-service           → services/shared/

All services → PostgreSQL (shared schema)
  Read access: any table (CO-5 from strangler-coexistence-strategy.md)
  Write access: owned tables only (per postgresql-access-policy.md §3)
```

### 2.2 Forbidden dependencies

```
FORBIDDEN dependency directions:

Any service          →→ Another service's HTTP API
                        (no synchronous inter-service HTTP calls — ever)

services/shared/     →→ Any service-specific code
                        (shared kernel must remain a leaf — no circular deps)

auth-service         →→ Write to any non-auth table
                        (may read clients table for email lookup only)

property-listing-service →→ Write to clients, agents, loan_applications, or any
                            table not in the Wave 1 ownership list

client-crm-service   →→ Write to listings, properties, loan_applications,
                         closing_details, or any table outside its 10 owned tables

underwriting-service →→ Write to loan_applications or closing_* tables
                        →→ Modify loan status in any form

closing-service      →→ Write to loan_applications, underwriting_* tables,
                         or calculate financial totals independently
                        →→ Write to any table outside its 5 owned tables

loan-origination-service →→ Write to underwriting_* or closing_* tables
                            (Wave 2B: define boundaries before implementation)

Any FastAPI service   →→ Call jwt.encode() — only auth-service may issue tokens
Any FastAPI service   →→ Call jwt.decode() directly — use shared/auth.py only
```

---

## 3. Shared Kernel Scope — Explicit Boundary

| IS in shared kernel | IS NOT in shared kernel |
|---------------------|------------------------|
| `CamelModel` — camelCase alias base class | Domain entities (SQLAlchemy models) |
| `PageResponse[T]` — Spring Page envelope | Business rules or domain logic |
| `ErrorResponse` — standardized error shape | Email sending logic |
| `verify_jwt` / `make_get_current_user` — JWT validation factory | Service-specific config (JWT_SECRET, DATABASE_URL) |
| `create_engine_from_settings` — DB engine factory | Router handlers |
| 422→400 exception handler | Pydantic schemas for domain DTOs |
| Health endpoint factory | Any import of service-specific `app/` modules |

---

## 4. Modular Monolith Extraction Readiness

Assessment per service:

| Service | Extraction Readiness | Blocking Dependencies | Notes |
|---------|---------------------|----------------------|-------|
| auth-service | ✅ Ready | None | Independent HTTP API, owns `otp_codes` only, no synchronous inter-service calls |
| property-listing-service | ✅ Ready | Cross-domain read of `agents` table | If fully independent, needs an Agent read API or agents table replicated |
| client-crm-service | ✅ Ready | Cross-domain reads of `listings`, `properties` | FK dependencies on listings/properties require read API or data denormalization |
| underwriting-service | ⚠️ Partially ready | Reads `loan_applications` (Java-written until Wave 2B) | Blocked until loan-origination-service owns `loan_applications` |
| closing-service | ⚠️ Partially ready | Reads `loan_applications`, `listings`, `clients`, `agents` | 4 cross-domain reads; full extraction requires per-service APIs or DB partitioning |
| loan-origination-service | ❌ Not yet built | `MasterService` decomposition | Cannot assess until Wave 2B is implemented |

**Current deployment topology**: Each service already operates as a separate deployment unit
(Docker container, independent port, independent Python process). The strangler proxy (nginx)
enforces service boundaries at the HTTP level.

**`services/shared/` extraction path**: Currently imported at build time as a local Python
package. If microservice decomposition to separate repositories is needed:
- Promote `services/shared/` to a PyPI package (`homelend-shared`) or git submodule.
- Update each service's `requirements.txt` to reference the versioned package.
- No source code changes required in the services themselves.

**Database decomposition**: The only remaining coupling point between all services is the
shared PostgreSQL instance and schema. DB decomposition (separate schemas or instances per
service) requires:
1. All cross-domain reads replaced with service API calls.
2. Shared tables migrated to the owning service's schema.
3. Denormalized columns removed (consolidated to normalized form in owning service).

---

## 5. Clean Architecture Layer Mapping

The following maps Clean Architecture layers to actual file locations per service:

| Layer | Role | Location |
|-------|------|----------|
| **Domain layer** | Entities, aggregate roots, business invariants | `services/<service>/app/models.py` (SQLAlchemy ORM) — conceptual aggregates per §2 of `domain-persistence-analysis.md` |
| **Application layer** | Use case handlers, orchestration | `services/<service>/app/routers/*.py` — each route function is a use case |
| **Interface layer** | HTTP request/response schema, serialization | `services/<service>/app/schemas.py` (Pydantic v2 models) + FastAPI router decorators |
| **Infrastructure layer** | DB engine, auth, cross-cutting | `services/shared/database.py`, `services/shared/auth.py`, `services/shared/exceptions.py` |

**Current architectural note**: The application layer (use cases) and interface layer (HTTP
serialization) are merged in the router files. This is pragmatic for the current service size
and consistent across all services. If a service grows to require explicit separation (e.g.,
testable use cases independent of HTTP), thin service objects can be extracted from router
files without changing the external API contract.
