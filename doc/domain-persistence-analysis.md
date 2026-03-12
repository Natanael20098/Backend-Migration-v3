# Domain Persistence Analysis — Entity Map, Transaction Boundaries, and Migration Risks

## Purpose

This document supplements `doc/domain-boundary-map.md` and `doc/postgresql-access-policy.md`
with entity relationship detail, transaction scoping, aggregate candidate analysis, and
shared-table coupling risks. It is the primary input to `doc/bounded-contexts.md` and
directly supports bounded context extraction planning.

> **Note on Java source**: The original Java monolith source code is not present in this
> repository. Entity relationships and transaction behavior are reconstructed from the FastAPI
> service implementations (which are authoritative replicas of the Java contract), existing
> boundary documents, and `doc/domain-boundary-map.md` §2.

---

## 1. Entity Map by Domain

The following table documents all 28+ domain entities, their database tables, primary key types,
foreign key relationships, and current service ownership.

| Domain | Entity | Table | PK Type | Key FKs | Owning Service |
|--------|--------|-------|---------|---------|----------------|
| **Auth** | OtpCode | `otp_codes` | UUID | `email` (no FK — not a PK reference) | auth-service |
| **Property** | Property | `properties` | UUID | — | property-listing-service |
| **Property** | PropertyImage | `property_images` | UUID | `property_id → properties` | property-listing-service |
| **Property** | PropertyTaxRecord | `property_tax_records` | UUID | `property_id → properties` | property-listing-service |
| **Listing** | Listing | `listings` | UUID | `property_id → properties`, `agent_id → agents` | property-listing-service |
| **Listing** | OpenHouse | `open_houses` | UUID | `listing_id → listings`, `agent_id → agents` | property-listing-service |
| **Client/CRM** | Client | `clients` | Long | — (`ssn_encrypted` column present — security-sensitive) | client-crm-service |
| **Client/CRM** | ClientDocument | `client_documents` | Long | `client_id → clients` | client-crm-service |
| **Client/CRM** | Lead | `leads` | Long | `client_id → clients` | client-crm-service |
| **Client/CRM** | Showing | `showings` | Long | `client_id → clients`, `listing_id → listings`, `agent_id → agents` | client-crm-service |
| **Client/CRM** | Offer | `offers` | Long | `client_id → clients`, `listing_id → listings` | client-crm-service |
| **Client/CRM** | CounterOffer | `counter_offers` | Long | `offer_id → offers` | client-crm-service |
| **Agent/Brokerage** | Agent | `agents` | Long | `brokerage_id → brokerages` | client-crm-service |
| **Agent/Brokerage** | AgentLicense | `agent_licenses` | Long | `agent_id → agents` | client-crm-service |
| **Agent/Brokerage** | Brokerage | `brokerages` | Long | — | client-crm-service |
| **Agent/Brokerage** | Commission | `commissions` | Long | `agent_id → agents`, `listing_id → listings` | client-crm-service |
| **Loan Origination** | LoanApplication | `loan_applications` | Long | `borrower_id → clients`, `property_id → properties` | loan-origination-service (**Wave 2B — not yet deployed**) |
| **Loan Origination** | BorrowerEmployment | `borrower_employment` | Long | `loan_application_id → loan_applications` | loan-origination-service (Wave 2B) |
| **Loan Origination** | BorrowerAsset | `borrower_assets` | Long | `loan_application_id → loan_applications` | loan-origination-service (Wave 2B) |
| **Loan Origination** | LoanPayment | `loan_payments` | Long | `loan_application_id → loan_applications` | loan-origination-service (Wave 2B) |
| **Loan Origination** | PaymentSchedule | `payment_schedules` | Long | `loan_application_id → loan_applications` | loan-origination-service (Wave 2B) |
| **Underwriting** | CreditReport | `credit_reports` | Long | `loan_application_id → loan_applications` | underwriting-service |
| **Underwriting** | UnderwritingDecision | `underwriting_decisions` | Long | `loan_application_id → loan_applications` | underwriting-service |
| **Underwriting** | UnderwritingCondition | `underwriting_conditions` | Long | `underwriting_decision_id → underwriting_decisions` | underwriting-service |
| **Underwriting** | AppraisalOrder | `appraisal_orders` | Long | `loan_application_id → loan_applications` | underwriting-service |
| **Underwriting** | AppraisalReport | `appraisal_reports` | Long | `appraisal_order_id → appraisal_orders` | underwriting-service |
| **Underwriting** | ComparableSale | `comparable_sales` | Long | `appraisal_report_id → appraisal_reports` | underwriting-service |
| **Closing** | ClosingDetail | `closing_details` | Long | `loan_application_id → loan_applications` (nullable), `listing_id → listings` (nullable) | closing-service |
| **Closing** | ClosingDocument | `closing_documents` | Long | `closing_detail_id → closing_details` | closing-service |
| **Closing** | TitleReport | `title_reports` | Long | `closing_detail_id → closing_details` | closing-service |
| **Closing** | EscrowAccount | `escrow_accounts` | Long | `closing_detail_id → closing_details` | closing-service |
| **Closing** | EscrowDisbursement | `escrow_disbursements` | Long | `escrow_account_id → escrow_accounts` | closing-service |
| **Admin** | SystemSetting | `system_settings` | Long | — | Java monolith (Wave 4) |
| **Admin** | AuditLog | `audit_logs` | Long | — (written by all services; no FK enforcement) | Java monolith (Wave 4) |
| **Admin** | Notification | `notifications` | Long | — | Java monolith (Wave 4) |

**PK type note**: Properties, PropertyImages, and auth entities use UUID PKs (introduced in the Python
migration). Legacy Java-origin entities (`clients`, `agents`, `loan_applications`, etc.) use Long
(auto-increment integer) PKs. This heterogeneity must be accounted for during cross-domain reads
and any schema normalization effort.

---

## 2. Aggregate Candidates

Aggregates are clusters of entities that must be modified together within a single transaction
to maintain consistency. The following aggregate roots are identified based on write ownership
and child entity cardinality.

| Aggregate Root | Child Entities | Owning Service | Consistency Requirement |
|----------------|----------------|----------------|-------------------------|
| `Property` | `PropertyImage`, `PropertyTaxRecord` | property-listing-service | Deleting Property cascades to images and tax records (application-layer cascade). Same service, clean boundary. |
| `Listing` | `OpenHouse` | property-listing-service | Listing deletion blocked if open houses exist (409). OpenHouse FK → Listing. |
| `LoanApplication` | `BorrowerEmployment`, `BorrowerAsset`, `LoanPayment`, `PaymentSchedule` | loan-origination-service (Wave 2B) | All child entities require a valid loan application to exist. Status transitions on LoanApplication trigger downstream workflows. |
| `ClosingDetail` | `ClosingDocument`, `TitleReport`, `EscrowAccount`, `EscrowDisbursement` | closing-service | Deleting ClosingDetail requires application-layer cascade deletion of all children. EscrowAccount → EscrowDisbursement is a nested aggregate. |
| `EscrowAccount` | `EscrowDisbursement` | closing-service | Disbursements belong to exactly one EscrowAccount. |
| `UnderwritingDecision` | `UnderwritingCondition` | underwriting-service | Conditions are sub-items of a decision. Decision transitions (APPROVED/DENIED) are regulatory-sensitive. |
| `AppraisalOrder` | `AppraisalReport` → `ComparableSale` | underwriting-service | Report belongs to Order; ComparableSale belongs to Report. Two-level nesting. |
| `Agent` | `AgentLicense`, `Commission` | client-crm-service | Licenses and commissions belong to the agent's lifecycle. |
| `Client` | `ClientDocument`, `Lead` | client-crm-service | Documents are directly owned by Client. Leads reference a Client. |
| `Offer` | `CounterOffer` | client-crm-service | Counter-offers are sub-items of an offer. Offer status (ACCEPTED/REJECTED/COUNTERED) governs valid counter-offer creation. |

---

## 3. Transaction Boundaries

### 3.1 Current FastAPI transaction scope

All migrated FastAPI services use the following transaction pattern:

- **Session lifecycle**: `AsyncSession` obtained via `Depends(get_db)` from `services/shared/database.py`.
- **Transaction scope**: One transaction per HTTP request. The session context manager (`async with db.begin()`) wraps the request handler.
- **Commit strategy**: Explicit `await db.commit()` at end of successful write operations. No auto-commit.
- **Rollback strategy**: Unhandled exceptions cause the session to roll back automatically (SQLAlchemy context manager behavior).

### 3.2 Write paths by service

| Service | Write Tables | Trigger |
|---------|-------------|---------|
| auth-service | `otp_codes` | POST `/api/auth/send-otp` (INSERT), POST `/api/auth/verify-otp` (UPDATE `used=true`) |
| property-listing-service | `properties`, `property_images`, `property_tax_records`, `listings`, `open_houses` | CRUD operations on property/listing endpoints |
| client-crm-service | `clients`, `client_documents`, `leads`, `showings`, `offers`, `counter_offers`, `agents`, `agent_licenses`, `brokerages`, `commissions` | CRUD operations on CRM endpoints |
| underwriting-service | `credit_reports`, `underwriting_decisions`, `underwriting_conditions`, `appraisal_orders`, `appraisal_reports`, `comparable_sales` | CRUD on underwriting sub-resource endpoints |
| closing-service | `closing_details`, `closing_documents`, `title_reports`, `escrow_accounts`, `escrow_disbursements` | CRUD on closing endpoints |
| loan-origination-service | `loan_applications`, `borrower_employment`, `borrower_assets`, `loan_payments`, `payment_schedules` | **Wave 2B — not yet implemented** |

### 3.3 Cross-service transaction rules

- **No distributed transactions**: There are no cross-service (two-phase commit) transactions. Each service writes only to its owned tables.
- **Cross-domain reads are non-transactional**: When a service reads from a table owned by another service (e.g., underwriting-service reads `loan_applications`), this is a plain SELECT within its own session — no locking, no write coordination.
- **Cascade deletes**: Implemented at the application layer within a single service transaction. The database schema does NOT rely on `ON DELETE CASCADE` DDL rules. Application-layer cascades are the sole mechanism.
  - Example (closing-service): Deleting a `ClosingDetail` explicitly deletes `EscrowDisbursement` → `EscrowAccount` → `TitleReport` → `ClosingDocument` → `ClosingDetail` within a single session.

### 3.4 Legacy Java transaction scope (for migration reference)

- Java monolith used Spring's `@Transactional` annotation at the service layer.
- `MasterService` handled multiple domain operations within a single transaction, creating implicit cross-domain transactional coupling that does not have an equivalent in the FastAPI architecture.
- For Wave 2B migration, `LoanService` state machine transitions (loan status changes that trigger underwriting) must be decomposed into event-driven patterns or explicit API calls between services.

---

## 4. Shared-Table and Tight-Coupling Risks

Cross-reference: `doc/postgresql-access-policy.md` §4 (denormalized columns) for the full
denormalized column inventory.

| Table | Risk Description | Services Affected | Mitigation |
|-------|-----------------|-------------------|------------|
| `agents` | Referenced as FK by `listings`, `open_houses`, `showings`, `commissions` across 4+ services. `client-crm-service` holds write ownership, but all other services depend on agent records being consistent. | property-listing-service, client-crm-service, closing-service | Never delete an agent with active listings, showings, or commissions. Application-layer guard required before delete. |
| `clients` | `ssn_encrypted` column stores sensitive PII. Used as FK by `loan_applications`, `showings`, `offers`, `closing_details`. | client-crm-service, underwriting-service, closing-service, loan-origination-service | SSN field must never appear in any API response (confirmed in existing schemas). Security review required before Wave 2B. |
| `listings` | Central FK target for `showings`, `offers`, `commissions`, `closing_details` across 3+ services. Write ownership held by property-listing-service. | property-listing-service, client-crm-service, closing-service | Listing deletion blocked by open house check (409). No application-layer guard exists for offers/showings/commissions — FK constraint at DB level is the only protection. |
| `loan_applications` | Central FK target for underwriting-service and closing-service. Wave 2B gap: Java still writes this table; FastAPI underwriting-service and closing-service read it cross-domain. | underwriting-service, closing-service, loan-origination-service | Until Wave 2B is deployed, `loan_applications` write ownership stays in Java. FastAPI services must not attempt writes to this table. |
| `audit_logs` | Written by all services during their respective waves. No single Python service owns this table until Wave 4. Each FastAPI service inserts rows directly using its own DB session. | All services | Audit log schema must not change until `admin-service` (Wave 4) takes ownership. Schema pinned per `postgresql-access-policy.md`. |
| `commissions` | Contains denormalized `agent_name` and `listing_address` columns (Java legacy). FastAPI `client-crm-service` must not write to these denormalized columns. | client-crm-service | Per `postgresql-access-policy.md` §4: denormalized columns are read-only from FastAPI perspective. |
| `showings` | Cross-domain FK references to `clients`, `listings`, and `agents`. Three separate service boundaries intersect here. | client-crm-service | All FK targets must exist before a showing can be created. Application-layer existence checks required. |

### 4.1 Tight-coupling risk: `MasterService` god class

The Java `MasterService` combines client and agent operations in a single service class with
no domain separation. Before `client-crm-service` processes Wave 2B loan-related logic, the
`MasterService` must be analyzed to identify which logic belongs to `loan-origination-service`
vs. `client-crm-service`. Failure to decompose this correctly risks duplicating or dropping
business rules.

### 4.2 PK type mismatch risk

Auth-service and property-listing-service use **UUID** PKs (introduced in the Python migration).
All legacy Java entities use **Long** (auto-increment integer) PKs. This mismatch becomes
critical when:
- Cross-domain FK references use different PK types (e.g., `Listing.agent_id` is UUID but `Agent.id` is Long — verify alignment before Wave 2B).
- Data migration scripts must handle type coercion.

---

## 5. Migration Risks Relevant to Spring Data JPA Adoption

These risks apply if any remaining Java service areas adopt Spring Data JPA or if the Java
entities are being analyzed for migration preparation.

| Risk | Description | Recommended Action |
|------|-------------|-------------------|
| **`MasterService` god class** | Mixed client/agent/loan business logic must be decomposed. Attempting to migrate individual Java controllers while `MasterService` is intact will result in broken references. | Decompose `MasterService` before Wave 2B. Map each method to its owning bounded context. |
| **No ON DELETE CASCADE in schema** | Application-layer cascades (explicit child deletes before parent delete) are fragile. If DDL rules ever diverge from application logic, orphaned records will accumulate. | Add `ON DELETE CASCADE` constraints to child tables in a coordinated DDL migration. Requires `postgresql-access-policy.md` change process. |
| **Denormalized columns** | 11+ columns across tables (`agent_name`, `client_name`, etc.) are denormalized Java artifacts. FastAPI services do not write these. If new Java features write them, FastAPI reads may become inconsistent. | Freeze denormalized columns as read-only legacy. Do not add new denormalized columns. Plan removal as part of admin-service (Wave 4) schema cleanup. |
| **Long vs UUID PK heterogeneity** | Long PKs in Java-origin entities; UUID PKs in Python-origin entities. Cross-service reads that join on FK values must handle the type difference. | Normalize PK types during Wave 2B or Wave 4 schema cleanup. Coordinate with `postgresql-access-policy.md` DDL change process. |
| **`loan_applications` write gap** | Until `loan-origination-service` (Wave 2B) is deployed, Java retains write ownership of `loan_applications`. Underwriting and closing services depend on Java-written records. | Maintain Java write ownership per `postgresql-access-policy.md` §3 until Wave 2B cutover completes. |
| **No explicit seam boundaries in Java model/ package** | All JPA entities are in a single flat `model/` package. Spring Data JPA's `@Repository` beans are also flat. There is no package-level enforcement of bounded context separation. | Use the entity-to-service mapping in §1 above as the authoritative seam definition. Enforce via module structure in Wave 2B implementation. |

---

## 6. How This Document Supports Bounded Context Definition

The entity map in §1 and aggregate analysis in §2 directly feed `doc/bounded-contexts.md`:

- Each aggregate root defines the **domain layer** of a bounded context.
- The owning service column maps to the **infrastructure layer** (database write ownership).
- Shared-table risks in §4 identify the **anti-corruption layer** needs between contexts.
- Transaction boundaries in §3 constrain which operations can be composed without distributed coordination.

See `doc/bounded-contexts.md` for the full Clean Architecture layer mapping per service.
