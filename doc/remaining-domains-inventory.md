# Remaining Domains: Inventory, Ranking, and Treatment Decisions

## Purpose

This document inventories all monolith domains not completed in Wave 1 (auth, property/listing)
and assigns each a treatment decision: standalone FastAPI service, grouped with another service,
or retained in the Java monolith temporarily. It ranks domains by migration priority and provides
the rationale for each decision, supporting staged monolith contraction without unnecessary
service sprawl.

**Reference documents:**
- `doc/domain-boundary-map.md` — domain identification and ownership map
- `doc/postgresql-access-policy.md` — table ownership by wave
- `doc/cutover-playbook.md` — process for executing each wave

---

## 1. Wave 1 Status (Already Completed)

| Domain | FastAPI Service | Status |
|--------|----------------|--------|
| Auth (OTP, JWT) | `auth-service` (port 8001) | ✅ Live |
| Property / Listing | `property-listing-service` (port 8002) | ✅ Live |

---

## 2. Remaining Domain Inventory

The following domains remain in the Java monolith after Wave 1:

| # | Domain | Java Controllers | Core Tables | Coupled To | Complexity |
|---|--------|-----------------|-------------|-----------|-----------|
| 1 | **Client / CRM** | `ClientController` | `clients`, `client_documents`, `leads`, `showings`, `offers`, `counter_offers` | agents, listings, loans | Medium |
| 2 | **Brokerage / Agent** | `AgentController` | `agents`, `agent_licenses`, `brokerages`, `commissions` | clients, listings | Medium |
| 3 | **Loan Origination** | `LoanController` | `loan_applications`, `borrower_employment`, `borrower_assets`, `loan_payments`, `payment_schedules` | clients, properties, closings | Medium-High |
| 4 | **Underwriting** | `UnderwritingController` | `credit_reports`, `underwriting_decisions`, `underwriting_conditions`, `appraisal_orders`, `appraisal_reports`, `comparable_sales` | loan_applications | High |
| 5 | **Closing / Settlement** | `ClosingController` | `closing_details`, `closing_documents`, `title_reports`, `escrow_accounts`, `escrow_disbursements` | loan_applications, listings, clients | High |
| 6 | **Admin / Ops** | `AdminController` | `system_settings`, `audit_logs`, `notifications` | All domains (audit writes) | Low-Medium |

> **Note**: Underwriting (domain 4) and Closing (domain 5) were migrated in Wave 3 (FastAPI services
> `underwriting-service` port 8003 and `closing-service` port 8004 are deployed and cutover-ready).
> This document focuses on the Wave 2 gap and Wave 4 Admin decision.

---

## 3. Treatment Decisions

### 3.1 Domain Ranking by Migration Priority

Domains are ranked by: (a) value delivered by migration, (b) unblocking downstream domains,
(c) coupling complexity, and (d) risk.

| Rank | Domain | Treatment | Wave | Rationale |
|------|--------|-----------|------|-----------|
| **1** | Client / CRM + Brokerage / Agent | **Grouped → `client-crm-service`** | Wave 2A | Agent and Client are tightly coupled; separating them would require heavy cross-service calls. Grouped reduces inter-service chattiness while still shrinking the monolith. Agents are referenced by nearly every domain — consolidating write ownership in one service is safer than splitting. |
| **2** | Loan Origination | **Standalone → `loan-origination-service`** | Wave 2B | Loan lifecycle is the core business domain; it deserves a dedicated service. It depends on Wave 2A's client/agent data being stable. Moderate complexity but high strategic value. |
| **3** | Underwriting | **Standalone → `underwriting-service`** | Wave 3A (deployed) | Regulatory sensitivity demands isolation. Depends on loan-origination-service being stable. |
| **4** | Closing / Settlement | **Standalone → `closing-service`** | Wave 3B (deployed) | Financial settlement logic is highest risk; migrated last among complex domains. |
| **5** | Admin / Ops | **Retain in monolith → Wave 4** | Wave 4 | Low value to extract early; `audit_logs` is written by all services. Admin is not on the critical user-facing path. Monolith retains admin until all other waves complete. |

---

### 3.2 Decision Details

#### `client-crm-service` (Wave 2A) — GROUP Client + Brokerage/Agent

**Decision**: Migrate `ClientController` + `AgentController` into a single FastAPI service.

**Rationale**:
- `agents` table is referenced by `clients`, `showings`, `offers`, `commissions`, `listings`, and
  `closings`. Splitting client and agent into separate services would require both to call each other
  for common operations (e.g., creating a showing requires both client and agent lookups). This
  creates circular service dependencies.
- `MasterService.java` mixes client and agent business logic with no clean internal boundary.
  Untangling it into two separate services during migration adds risk without proportional benefit.
- Grouping does **not** mean the domain is undifferentiated. The service is internally organized
  by sub-router (`/api/clients`, `/api/agents`, `/api/leads`, `/api/showings`, `/api/offers`,
  `/api/brokerages`). A future split is possible once the migration stabilizes.
- SSN handling in `clients` requires a security review; having it in one dedicated service
  (rather than shared across two) reduces the security audit surface.

**Tables owned (write post-cutover)**:
`clients`, `client_documents`, `leads`, `showings`, `offers`, `counter_offers`,
`agents`, `agent_licenses`, `brokerages`, `commissions`

**Path prefixes**: `/api/clients/*`, `/api/agents/*`, `/api/leads/*`, `/api/showings/*`,
`/api/offers/*`, `/api/brokerages/*`

**Port**: `8005`

---

#### `loan-origination-service` (Wave 2B) — STANDALONE

**Decision**: Migrate `LoanController` + `LoanService` into a dedicated FastAPI service.

**Rationale**:
- Loan applications are the central business entity that both underwriting and closing depend on.
  A dedicated service makes dependency direction explicit: underwriting-service and closing-service
  read loan data; they do not own it.
- `LoanService.java` contains a complex loan lifecycle state machine (STARTED → FUNDED). This
  logic is substantial enough to warrant isolation in its own service boundary.
- The loan domain has no circular dependency with client-crm-service (loans read clients;
  clients do not read loans in the critical path).
- Wave 2B must be sequenced after Wave 2A (client-crm-service cutover) so that `clients`
  write ownership is confirmed before loan-origination-service takes `loan_applications` write
  ownership (loans reference clients).

**Tables owned (write post-cutover)**:
`loan_applications`, `borrower_employment`, `borrower_assets`, `loan_payments`, `payment_schedules`

**Path prefixes**: `/api/loans/*`

**Port**: `8006`

---

#### `admin-service` (Wave 4) — RETAIN IN MONOLITH TEMPORARILY

**Decision**: `AdminController` and its supporting services (`ReportingService`, `CacheManager`,
`NotificationHelper`) remain in the Java monolith until all other waves complete.

**Rationale**:
- `audit_logs` is written by **all** FastAPI services during parallel run. The table has no single
  authoritative writer until Wave 4. Extracting admin now would not actually shrink the monolith's
  write scope for this table.
- The admin controller exposes a significant security anti-pattern (exposing JWT secrets in the
  `/api/admin/settings` response). Migration should include a security redesign of that endpoint,
  not a direct port. That redesign work is out of scope for the current migration wave.
- Reporting (`ReportingService`) and the in-memory `CacheManager` are entirely internal to Java;
  they have no external API dependencies from other FastAPI services.
- The hidden `/api/admin/cache/clear` backdoor endpoint should be removed, not migrated. That
  cleanup is appropriate during Wave 4 when the admin domain is fully redesigned.
- Admin is the lowest user-facing priority. Retaining it in the monolith does not block any
  Wave 2 or Wave 3 migration.

**Action for Wave 4**: Design a secure `admin-service` from scratch rather than porting the
existing anti-pattern-laden controller. This is noted in `doc/domain-boundary-map.md` §3.3.

---

## 4. Monolith Surface Area Reduction Plan

The following table tracks monolith contraction across waves:

| Wave | Services Extracted | Java Controllers Retired | Tables Transferred | Monolith Shrinks? |
|------|-------------------|------------------------|-------------------|-------------------|
| Wave 1 (done) | `auth-service`, `property-listing-service` | `AuthController`, `PropertyController`, `ListingController` | 6 tables | ✅ Yes |
| Wave 2A | `client-crm-service` | `ClientController`, `AgentController` | 10 tables | ✅ Yes |
| Wave 2B | `loan-origination-service` | `LoanController` | 5 tables | ✅ Yes |
| Wave 3A (deployed) | `underwriting-service` | `UnderwritingController` | 6 tables | ✅ Yes |
| Wave 3B (deployed) | `closing-service` | `ClosingController` | 5 tables | ✅ Yes |
| Wave 4 (deferred) | `admin-service` | `AdminController` | 3 tables | ✅ Yes |

After Wave 3B, the only remaining Java controller is `AdminController`. The monolith becomes
a thin admin shell. After Wave 4, the Java monolith can be decommissioned.

---

## 5. Decision Rationale: Avoiding Service Sprawl

The following grouping decisions were made to prevent unnecessary fragmentation:

| Option Considered | Rejected Because |
|------------------|-----------------|
| Separate `agent-service` + `client-service` | Circular dependency between agent and client data; `agents` referenced by clients, showings, offers. Would require synchronous inter-service calls on nearly every write path. |
| Separate `lead-service` + `showing-service` | Both are sub-resources of clients and agents. Extracting them as standalone services creates micro-services for domain objects that have no independent lifecycle. |
| Separate `commission-service` | Commissions are purely derived from agent+listing data. No independent lifecycle. Belongs in `client-crm-service` with agents. |
| `admin-service` now | Admin controller has serious security anti-patterns requiring redesign, not porting. Premature extraction would carry the anti-patterns into the new service. |
| `loan-service` + `payment-service` | Loan payments are a sub-resource of loan applications. No independent lifecycle justifying a separate deployment. |

**Rule applied**: A domain warrants its own service only if it has an independent lifecycle,
a sufficiently isolated table ownership set, and a meaningful path prefix separation. Sub-resources
of a domain belong in the same service.

---

## 6. Staged Contraction Gates

Each wave has a contraction gate — a condition that must be met before the monolith is considered
contracted at that level:

| Gate | Condition | Reference |
|------|-----------|-----------|
| **G1** | Wave 1 Java controllers retired (14-day stability, JR-1 through JR-7) | `cutover-playbook.md` §6 |
| **G2** | Wave 2A + 2B Java controllers retired after client-crm and loan-origination cutovers | `doc/cutover-records/client-crm-service-cutover.md` |
| **G3** | Wave 3A + 3B Java controllers retired after underwriting and closing cutovers | `doc/cutover-records/underwriting-service-cutover.md`, `closing-service-cutover.md` |
| **G4** | Wave 4 admin-service deployed and AdminController retired | TBD — admin-service epic |
| **G5** | Java monolith decommissioned; `Dockerfile.java` and `pom.xml` removed from repository | Final epic |

Gates must be satisfied in order. No gate may be skipped.
