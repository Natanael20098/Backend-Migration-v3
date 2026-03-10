# Legacy Backend Domain and Service Boundary Map

## Purpose

This document maps the Java Spring Boot monolith (`com.zcloud.platform`) to proposed FastAPI
service ownership boundaries. It identifies first-wave migration candidates, defines initial
responsibility scopes, and flags shared concerns that must be handled carefully during parallel
coexistence.

Use this document as the authoritative reference when deciding which FastAPI service owns a
given Java controller, model, repository, or service class.

---

## 1. Monolith Structure Summary

The Java monolith is organized as a single Spring Boot application with the following package structure:

```
com.zcloud.platform/
├── config/          # Cross-cutting: security, CORS, DB, constants
├── controller/      # HTTP layer — one controller per domain area
├── model/           # JPA entities — all domains in one flat package
├── repository/      # Spring Data JPA repos — all domains in one flat package
├── security/        # JWT filter
├── service/         # Business logic — mixed: MasterService, LoanService, UnderwritingService, ClosingService, etc.
└── util/            # DateUtils, JsonHelper, JwtUtil, SecurityUtils, SqlBuilder
```

**Anti-patterns identified:**
- All JPA entities live in one flat `model/` package with no domain separation.
- `MasterService.java` is a god service handling multiple domain operations.
- All repositories share a single flat `repository/` package.
- Denormalized data is duplicated across multiple tables (e.g., `agent_name` in `commissions`, `listings`, `showings`).
- SSN stored in the main `clients` table.
- No existing seam boundaries — all domain logic is reachable from any service bean.

---

## 2. Domain Identification

The monolith covers the following domains, identified from controllers, models, and schema:

| Domain | Java Controllers | Core Java Models | Core Repositories |
|--------|-----------------|-----------------|-------------------|
| **Auth** | `AuthController` | `OtpCode` | `OtpCodeRepository` |
| **Brokerage/Agent** | `AgentController` | `Agent`, `AgentLicense`, `Brokerage`, `Commission` | `AgentRepository`, `AgentLicenseRepository`, `BrokerageRepository`, `CommissionRepository` |
| **Property/Listing** | `PropertyController`, `ListingController` | `Property`, `PropertyImage`, `PropertyTaxRecord`, `Listing`, `OpenHouse` | `PropertyRepository`, `PropertyImageRepository`, `PropertyTaxRecordRepository`, `ListingRepository`, `OpenHouseRepository` |
| **Client/CRM** | `ClientController` | `Client`, `ClientDocument`, `Lead`, `Showing`, `Offer`, `CounterOffer` | `ClientRepository`, `ClientDocumentRepository`, `LeadRepository`, `ShowingRepository`, `OfferRepository`, `CounterOfferRepository` |
| **Loan Origination** | `LoanController` | `LoanApplication`, `BorrowerEmployment`, `BorrowerAsset`, `LoanPayment`, `PaymentSchedule` | `LoanApplicationRepository`, `BorrowerEmploymentRepository`, `BorrowerAssetRepository`, `LoanPaymentRepository`, `PaymentScheduleRepository` |
| **Underwriting** | `UnderwritingController` | `CreditReport`, `UnderwritingDecision`, `UnderwritingCondition`, `AppraisalOrder`, `AppraisalReport`, `ComparableSale` | `CreditReportRepository`, `UnderwritingDecisionRepository`, `UnderwritingConditionRepository`, `AppraisalOrderRepository`, `AppraisalReportRepository`, `ComparableSaleRepository` |
| **Closing/Settlement** | `ClosingController` | `ClosingDetail`, `ClosingDocument`, `TitleReport`, `EscrowAccount`, `EscrowDisbursement` | `ClosingDetailRepository`, `ClosingDocumentRepository`, `TitleReportRepository`, `EscrowAccountRepository`, `EscrowDisbursementRepository` |
| **Admin/Ops** | `AdminController` | `SystemSetting`, `AuditLog`, `Notification` | `SystemSettingRepository`, `AuditLogRepository`, `NotificationRepository` |

---

## 3. Proposed FastAPI Service Ownership Map

### 3.1 First-Wave Services (Priority migration candidates)

These services have the clearest seam boundaries, the highest development velocity impact,
and the most stable external contracts.

---

#### Service: `auth-service`

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/auth/*` |
| **Java source** | `AuthController`, `JwtAuthenticationFilter`, `JwtUtil`, `SecurityUtils`, `SecurityConfig`, `OtpCodeRepository`, `OtpCode` |
| **Responsibilities** | Login, registration, JWT issuance and validation, OTP generation/verification, email-based auth flows |
| **DB tables owned (write)** | `otp_codes` |
| **DB tables read** | `clients` (read-only during parallel run, until client-service owns writes) |
| **External dependencies** | `MailgunService` (email OTP delivery) — must be re-implemented or proxied |
| **Shared concerns** | JWT secret must be shared with all other services during parallel run (see `postgresql-access-policy.md`) |
| **Migration complexity** | **Low** — stateless JWT logic, small model surface, no complex business rules |

---

#### Service: `property-listing-service`

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/properties/*`, `/api/listings/*` |
| **Java source** | `PropertyController`, `ListingController`, `Property`, `PropertyImage`, `PropertyTaxRecord`, `Listing`, `OpenHouse` and their repositories |
| **Responsibilities** | Property CRUD, property search, property images, tax records, listing CRUD, listing status management, open houses |
| **DB tables owned (write)** | `properties`, `property_images`, `property_tax_records`, `listings`, `open_houses` |
| **DB tables read** | `agents` (for listing.agent), `brokerages` |
| **External dependencies** | None beyond DB |
| **Shared concerns** | `listings` is referenced by `commissions`, `showings`, `offers`, `closings` — write ownership of `listings` must be coordinated during parallel run |
| **Migration complexity** | **Low-Medium** — large surface area but straightforward CRUD; pagination and search require care (see `api-compatibility-rules.md` R-REQ-5) |

---

### 3.2 Second-Wave Services

These services depend on first-wave data or have more complex business logic requiring
first-wave services to be stable before migration begins.

---

#### Service: `client-crm-service`

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/clients/*`, `/api/leads/*`, `/api/showings/*`, `/api/offers/*`, `/api/brokerages/*` |
| **Java source** | `ClientController`, `AgentController`, `Client`, `ClientDocument`, `Lead`, `Showing`, `Offer`, `CounterOffer`, `Agent`, `AgentLicense`, `Brokerage`, `Commission` and their repositories |
| **Responsibilities** | Client management, lead tracking, showing scheduling, offer submission and status, agent and brokerage management, commission tracking |
| **DB tables owned (write)** | `clients`, `client_documents`, `leads`, `showings`, `offers`, `counter_offers`, `agents`, `agent_licenses`, `brokerages`, `commissions` |
| **DB tables read** | `listings`, `properties` |
| **Shared concerns** | `agents` is referenced by nearly every other domain — write access must be carefully coordinated; SSN handling in `clients` requires security review |
| **Migration complexity** | **Medium** — broad domain surface; `MasterService` likely contains mixed client/agent logic that must be untangled |

---

#### Service: `loan-origination-service`

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/loans/*` (excluding underwriting sub-routes) |
| **Java source** | `LoanController`, `LoanService`, `LoanApplication`, `BorrowerEmployment`, `BorrowerAsset`, `LoanPayment`, `PaymentSchedule` and their repositories |
| **Responsibilities** | Loan application lifecycle (STARTED → FUNDED), employment and asset collection, payment recording, payment scheduling |
| **DB tables owned (write)** | `loan_applications`, `borrower_employment`, `borrower_assets`, `loan_payments`, `payment_schedules` |
| **DB tables read** | `clients`, `properties`, `closings` |
| **Shared concerns** | Loan status transitions trigger downstream underwriting and closing workflows — event/message coordination needed |
| **Migration complexity** | **Medium-High** — state machine logic in `LoanService`; cross-domain reads during loan creation |

---

### 3.3 Later-Wave Domains

These domains have the highest business-rule complexity or the most cross-domain coupling.
They should not be migrated until first- and second-wave services are stable in production.

---

#### Service: `underwriting-service`

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/loans/{id}/credit-report`, `/api/loans/{id}/underwriting`, `/api/loans/{id}/appraisal` |
| **Java source** | `UnderwritingController`, `UnderwritingService`, `CreditReport`, `UnderwritingDecision`, `UnderwritingCondition`, `AppraisalOrder`, `AppraisalReport`, `ComparableSale` and their repositories |
| **Responsibilities** | Credit report ordering/storage, underwriting decision recording, condition management, appraisal ordering, comparable sales analysis |
| **DB tables owned (write)** | `credit_reports`, `underwriting_decisions`, `underwriting_conditions`, `appraisal_orders`, `appraisal_reports`, `comparable_sales` |
| **DB tables read** | `loan_applications`, `properties`, `clients` |
| **Migration complexity** | **High** — regulatory-sensitive domain; decision logic must be preserved exactly |

---

#### Service: `closing-service`

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/closings/*` |
| **Java source** | `ClosingController`, `ClosingService`, `ClosingDetail`, `ClosingDocument`, `TitleReport`, `EscrowAccount`, `EscrowDisbursement` and their repositories |
| **Responsibilities** | Closing scheduling, document management, title report tracking, escrow account management, disbursements |
| **DB tables owned (write)** | `closing_details`, `closing_documents`, `title_reports`, `escrow_accounts`, `escrow_disbursements` |
| **DB tables read** | `loan_applications`, `listings`, `clients`, `agents` |
| **Migration complexity** | **High** — financial settlement logic; must coordinate with loan origination service on closing status |

---

#### Service: `admin-service` (or merged into platform layer)

| Attribute | Value |
|-----------|-------|
| **Proposed path prefix** | `/api/admin/*` (internal) |
| **Java source** | `AdminController`, `ReportingService`, `SystemSetting`, `AuditLog`, `Notification` and their repositories |
| **Responsibilities** | System settings, audit logging, notification management, reporting |
| **Migration complexity** | **Low-Medium** — but low priority; Java monolith can retain this for longer |

---

## 4. Shared Concerns and Cross-Domain Touchpoints

The following concerns span multiple domain boundaries and must be addressed at the platform
level before domain-specific migration proceeds:

| Concern | Description | Resolution Approach |
|---------|-------------|---------------------|
| **JWT validation** | Every service must validate JWT tokens | Shared JWT secret via environment; each FastAPI service validates independently using `python-jose` or `PyJWT` |
| **`agents` table** | Referenced by listings, clients, showings, offers, commissions, closings | During parallel run: Java retains write access; FastAPI services read only. `client-crm-service` takes write ownership in second wave. |
| **`clients` table** | Referenced by loans, showings, offers, closings | During parallel run: Java retains write access; FastAPI services read only until `client-crm-service` migrates. |
| **`listings` table** | Referenced by showings, offers, commissions, closings | During parallel run: Java retains write access; FastAPI services read only until `property-listing-service` takes ownership. |
| **Pagination envelope** | Spring Page format must be preserved | Each FastAPI service implements a shared `PageResponse` Pydantic model (see `api-compatibility-rules.md` R-RES-2) |
| **camelCase serialization** | FastAPI defaults to snake_case | Each FastAPI service configures `alias_generator = to_camel` on all response models |
| **Error response shape** | `{"message": "..."}` expected by frontend | Each FastAPI service installs a shared exception handler producing this shape |
| **`MasterService` god class** | Contains mixed-domain logic | Must be decomposed during migration; logic assigned to the owning service before that service goes live |
| **Denormalized DB columns** | `agent_name`, `client_name`, etc. duplicated across tables | FastAPI services do NOT write to denormalized columns (they are Java legacy artifacts); reads may use them for performance but must not rely on them as source of truth |
| **SSN in `clients` table** | `ssn_encrypted` stored in main table | Requires a dedicated security design review before `client-crm-service` migration; not a blocker for first-wave services |

---

## 5. Migration Wave Summary

| Wave | Services | Status |
|------|----------|--------|
| **Wave 1** | `auth-service`, `property-listing-service` | First to migrate; lowest coupling, highest value |
| **Wave 2** | `client-crm-service`, `loan-origination-service` | After Wave 1 is stable in production |
| **Wave 3** | `underwriting-service`, `closing-service` | After Wave 2; highest complexity and regulatory sensitivity |
| **Wave 4** | `admin-service` | Last; Java monolith retains admin functionality until all other waves complete |

---

## 6. Areas That Must Remain Shared During Transition

The following capabilities must remain in the Java monolith (or be implemented as a shared
platform library/sidecar) until all waves are complete:

1. **JWT issuance** — Until `auth-service` is live and validated, the Java monolith issues tokens. After `auth-service` cutover, Java must validate (not issue) tokens using the same secret.
2. **Email notifications (`MailgunService`)** — Shared infrastructure; FastAPI services call a notification microservice or the Java monolith's internal notification endpoint until `admin-service` is migrated.
3. **Audit logging** — The `AuditLog` table is written by all domains. Each FastAPI service must write audit records; the schema is shared. Ownership moves to `admin-service` in Wave 4.
4. **Database schema** — The single PostgreSQL schema is shared throughout migration. No DDL changes are permitted without the process defined in `postgresql-access-policy.md`.
