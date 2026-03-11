# Underwriting Service Boundary Definition

## Purpose

This document defines the exact scope of the `underwriting-service` FastAPI migration, including
owned entities, preserved external endpoints, dependencies on loan/property/client data, and
coupling risks. It is the authoritative reference for the Wave 3 underwriting migration epic.

---

## 1. Owned Responsibilities

The `underwriting-service` owns all read and write operations for the following domain areas:

### 1.1 Credit Report Management

| Capability | Description |
|-----------|-------------|
| Credit report CRUD | Create, read, update, and delete credit report records (`credit_reports` table) |
| Multi-bureau support | Tracks reports from EQUIFAX, EXPERIAN, and TRANSUNION per loan |
| Report expiry tracking | Stores `expiry_date` to flag reports that require re-ordering |
| Pulled-by agent linkage | Associates report pull with the agent/officer who ordered it |

### 1.2 Underwriting Decision Management

| Capability | Description |
|-----------|-------------|
| Decision CRUD | Create, read, update, and delete underwriting decisions (`underwriting_decisions` table) |
| Decision outcomes | Records APPROVED, APPROVED_WITH_CONDITIONS, SUSPENDED, and DENIED outcomes |
| Risk metric storage | Stores DTI ratio, LTV ratio, and risk score alongside decision |
| Condition management | Manages prior-to-doc, prior-to-fund, and prior-to-close conditions (`underwriting_conditions` table) |

### 1.3 Appraisal Management

| Capability | Description |
|-----------|-------------|
| Appraisal order CRUD | Create, read, update, and delete appraisal orders (`appraisal_orders` table) |
| Appraisal report CRUD | Create, read, update appraisal reports (`appraisal_reports` table) |
| Comparable sales | Track comparable sales for appraisal reports (`comparable_sales` table) |
| Order status tracking | Manages ORDERED → SCHEDULED → IN_PROGRESS → COMPLETED / CANCELLED lifecycle |

### 1.4 Sub-Resource Reads (Cross-Domain, Read-Only)

| Resource | Source Table | Access Type |
|----------|-------------|-------------|
| Loan application summary | `loan_applications` | Read-only (owned by loan-origination-service / Java) |
| Property details for appraisal | `properties` | Read-only (owned by property-listing-service) |
| Client/borrower details | `clients` | Read-only (owned by client-crm-service / Java) |
| Agent/underwriter details | `agents` | Read-only (owned by client-crm-service / Java) |

---

## 2. Preserved Endpoints and Interactions

The following endpoints are served by the Java `UnderwritingController` and must be
reimplemented with identical external contracts. Path, method, and response shape must match
the rules in `doc/api-compatibility-rules.md`.

### 2.1 Credit Report Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/loans/{id}/credit-report` | Returns list of credit reports for loan |
| `GET` | `/api/loans/{id}/credit-report/{reportId}` | Returns single credit report |
| `POST` | `/api/loans/{id}/credit-report` | Returns 201 with created report |
| `PUT` | `/api/loans/{id}/credit-report/{reportId}` | Returns 200 with updated report |
| `DELETE` | `/api/loans/{id}/credit-report/{reportId}` | Returns 204 |

### 2.2 Underwriting Decision Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/loans/{id}/underwriting` | Returns list of decisions for loan |
| `GET` | `/api/loans/{id}/underwriting/{decisionId}` | Returns single decision with embedded conditions |
| `POST` | `/api/loans/{id}/underwriting` | Returns 201 with created decision |
| `PUT` | `/api/loans/{id}/underwriting/{decisionId}` | Returns 200 with updated decision |
| `DELETE` | `/api/loans/{id}/underwriting/{decisionId}` | Returns 204; cascades to conditions |

### 2.3 Underwriting Condition Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/loans/{id}/underwriting/{decisionId}/conditions` | Returns list of conditions |
| `POST` | `/api/loans/{id}/underwriting/{decisionId}/conditions` | Returns 201 with created condition |
| `PUT` | `/api/loans/{id}/underwriting/{decisionId}/conditions/{conditionId}` | Returns 200 |
| `DELETE` | `/api/loans/{id}/underwriting/{decisionId}/conditions/{conditionId}` | Returns 204 |

### 2.4 Appraisal Endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/loans/{id}/appraisal` | Returns list of appraisal orders for loan |
| `GET` | `/api/loans/{id}/appraisal/{orderId}` | Returns order with embedded reports |
| `POST` | `/api/loans/{id}/appraisal` | Returns 201 with created order |
| `PUT` | `/api/loans/{id}/appraisal/{orderId}` | Returns 200 with updated order |
| `DELETE` | `/api/loans/{id}/appraisal/{orderId}` | Returns 204; cascades to reports and comps |
| `GET` | `/api/loans/{id}/appraisal/{orderId}/report` | Returns list of appraisal reports |
| `GET` | `/api/loans/{id}/appraisal/{orderId}/report/{reportId}` | Returns single report with comparable sales |
| `POST` | `/api/loans/{id}/appraisal/{orderId}/report` | Returns 201 with created report |
| `PUT` | `/api/loans/{id}/appraisal/{orderId}/report/{reportId}` | Returns 200 with updated report |
| `GET` | `/api/loans/{id}/appraisal/{orderId}/report/{reportId}/comparables` | Returns list of comparable sales |
| `POST` | `/api/loans/{id}/appraisal/{orderId}/report/{reportId}/comparables` | Returns 201 with created comparable |

---

## 3. Dependencies on Loan, Property, and Client Data

### 3.1 Loan Application Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Loan existence validation | All underwriting resources are scoped under `/api/loans/{id}/`; loan must exist | Read-only SELECT on `loan_applications` before creating any underwriting resource |
| Loan data in responses | Credit reports and decisions embed loan summary (type, amount, status) | Join via `loan_application_id` FK using SQLAlchemy `selectin` loading |
| Loan write ownership | `loan_applications` is owned by loan-origination-service / Java during Wave 3 | No writes to `loan_applications` from this service |

### 3.2 Property Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Property in appraisal orders | Appraisal orders reference `property_id` for the property being appraised | Read-only SELECT on `properties` when embedding property summary |
| Property write ownership | `properties` is owned by property-listing-service | No writes to `properties` from this service |

### 3.3 Client/Borrower Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Borrower in loan summary | Loan application summary embeds borrower (client) details | Read-only SELECT on `clients` via loan_application.borrower_id |
| Client write ownership | `clients` is owned by client-crm-service / Java | No writes to `clients` from this service |

### 3.4 Agent/Underwriter Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| Underwriter on decision | `underwriting_decisions.underwriter_id` references an agent | Read-only SELECT on `agents` when embedding underwriter summary |
| Credit report pulled_by | `credit_reports.pulled_by` references the agent who pulled the report | Read-only SELECT on `agents` |
| Condition assigned_to | `underwriting_conditions.assigned_to` references an agent | Read-only SELECT on `agents` |
| Agent write ownership | `agents` is owned by client-crm-service / Java | No writes to `agents` from this service |

### 3.5 Auth Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| JWT validation | All underwriting endpoints require `Authorization: Bearer <token>` | Use `shared.auth.make_get_current_user(settings.JWT_SECRET)` dependency |
| JWT secret | Must be identical to the Java monolith's `JWT_SECRET` | Sourced from `JWT_SECRET` env var |

---

## 4. Risks from Coupling

### 4.1 loan_applications Write Ownership Dependency

The underwriting-service depends on `loan_applications` existing before underwriting resources can
be created. During Wave 3 parallel run, Java (or the future loan-origination-service) is the writer.

**Risk**: If a loan application is deleted by Java while underwriting resources exist for it, FK
violations will prevent deletion unless cascades are defined.

**Mitigation**: The underwriting-service must validate loan existence before any write. During
parallel run, loan deletion should be coordinated between teams. This service does not need to
implement cascade logic on loan deletions — that is the loan-origination-service's responsibility.

### 4.2 agents Table Dependency on Multiple FKs

Three columns in underwriting tables reference `agents.id`:
- `underwriting_decisions.underwriter_id`
- `credit_reports.pulled_by`
- `underwriting_conditions.assigned_to`

**Risk**: If an agent record is deleted by Java/client-crm-service while referenced by underwriting
data, FK violations occur.

**Mitigation**: These FK columns are nullable; the service accepts null values and treats agent
references as advisory. Responses degrade gracefully if the referenced agent no longer exists.

### 4.3 client_documents FK in underwriting_conditions

`underwriting_conditions.document_id` references `client_documents.id`, which is owned by
client-crm-service / Java.

**Risk**: Documents uploaded through the Java client document management may be referenced by
conditions, creating a cross-service FK dependency.

**Mitigation**: The `document_id` field is nullable and is treated as an advisory reference. The
underwriting-service does not validate document existence before setting `document_id`. This is
an acceptable compromise during Wave 3 given client documents are Java-owned.

### 4.4 Regulatory Sensitivity

Underwriting decisions have regulatory significance (ECOA, FCRA compliance). The decision logic
from the Java `UnderwritingService` must be preserved exactly.

**Mitigation**: This service does not implement automated decision logic — it stores decisions made
by human underwriters. All decision values are provided by callers. The service enforces valid
decision outcome values (`APPROVED`, `APPROVED_WITH_CONDITIONS`, `SUSPENDED`, `DENIED`) via
Pydantic `Literal` validation.

### 4.5 Denormalized Column Policy

Per `postgresql-access-policy.md` §4, the following denormalized columns exist in owned tables
but must **not** be written by this service:

| Column | Table | Policy |
|--------|-------|--------|
| `loan_amount` | `underwriting_decisions` | Do not write; legacy Java artifact |
| `loan_type` | `underwriting_decisions` | Do not write; legacy Java artifact |
| `borrower_name` | `underwriting_decisions` | Do not write; legacy Java artifact |
| `property_address` | `underwriting_decisions` | Do not write; legacy Java artifact |
| `borrower_name` | `credit_reports` | Do not write; legacy Java artifact |
| `borrower_ssn_last4` | `credit_reports` | Do not write; legacy Java artifact |
| `property_address` | `appraisal_orders` | Do not write; legacy Java artifact |
| `property_type` | `appraisal_orders` | Do not write; legacy Java artifact |
| `property_address` | `appraisal_reports` | Do not write; legacy Java artifact |
| `property_sqft` | `appraisal_reports` | Do not write; legacy Java artifact |
| `property_beds` | `appraisal_reports` | Do not write; legacy Java artifact |
| `property_baths` | `appraisal_reports` | Do not write; legacy Java artifact |

---

## 5. Summary

| Attribute | Value |
|-----------|-------|
| **Service name** | `underwriting-service` |
| **Path prefixes owned** | `/api/loans/{id}/credit-report`, `/api/loans/{id}/underwriting`, `/api/loans/{id}/appraisal` |
| **Port** | `8003` |
| **DB tables owned (write)** | `credit_reports`, `underwriting_decisions`, `underwriting_conditions`, `appraisal_orders`, `appraisal_reports`, `comparable_sales` |
| **DB tables read (cross-domain)** | `loan_applications`, `properties`, `clients`, `agents`, `client_documents` (reference only) |
| **Migration wave** | Wave 3 |
| **Auth dependency** | Shared `JWT_SECRET`; validates tokens from `auth-service` or Java |
| **External service dependencies** | None (no email/notification; reads loan/property/client data directly from shared DB) |
| **Cutover record** | `doc/cutover-records/underwriting-service-cutover.md` |
| **Prerequisite services** | Wave 1 (`property-listing-service`), Wave 2 (`loan-origination-service`, `client-crm-service`) should be stable before Wave 3 cutover |
