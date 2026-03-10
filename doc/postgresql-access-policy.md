# Shared PostgreSQL Access Policy for Parallel-Run Migration

## Purpose

This document defines how new FastAPI services interact with the existing PostgreSQL instance
and schema while the Java monolith and new Python services coexist during migration. It
establishes ownership rules, read/write boundaries, and schema change controls needed to
prevent data corruption, unsafe drift, and conflicting writes.

All platform engineers and domain migration teams must follow this policy. Exceptions require
a written migration decision record (MDR) in `doc/decisions/`.

---

## 1. Shared Database Context

- **Database**: PostgreSQL (hosted on Supabase, connection via transaction pooler at port 6543)
- **Schema**: Single public schema (`public`) containing all domain tables — no per-service schema isolation during migration
- **Connection string**: Sourced from `DATABASE_URL` env var (same instance used by Java monolith)
- **Java ORM**: Spring Data JPA / Hibernate with `ddl-auto=none`
- **FastAPI ORM**: SQLAlchemy (async) with Alembic for migrations; `ddl-auto` equivalent must be set to `none` / manual

---

## 2. Core Rules

### Rule DB-1: No DDL Without Approval

No FastAPI service may execute DDL statements (`CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`,
`CREATE INDEX`, `DROP COLUMN`, etc.) against the shared database without an approved MDR.

- Alembic autogenerate must **not** be run in `--autogenerate` mode against the shared schema without reviewing the generated diff first.
- All migration scripts must be reviewed by a platform engineer before execution.
- Alembic migrations that touch shared tables require sign-off from the team owning the Java monolith.

### Rule DB-2: FastAPI Services Use the Existing Schema As-Is

FastAPI services must work with the existing table and column names as defined in
`src/main/resources/schema.sql`. Column names use `snake_case` (e.g., `first_name`,
`loan_amount`) — FastAPI Pydantic models must map to these column names directly.

FastAPI services must not:
- Rename columns
- Change column types
- Add `NOT NULL` constraints to existing nullable columns
- Drop columns
- Reorder columns

### Rule DB-3: One Writer Per Table Per Transition Period

To prevent lost-update conflicts during parallel run, each database table has exactly one
authoritative writer at any given time. The Java monolith retains write ownership of all
tables until the corresponding FastAPI service completes its cutover (per `cutover-playbook.md`).

After a FastAPI service completes cutover for its domain, the Java monolith must be
reconfigured (or its routing disabled) so it no longer writes to the tables owned by that service.

### Rule DB-4: FastAPI Services May Always Read Any Table

Read-only access across domain boundaries is permitted. FastAPI services may query any table
they need to fulfill a response (e.g., `property-listing-service` reading `agents` for a listing response).

Cross-domain reads must use direct SQL queries or SQLAlchemy models; they must not trigger
writes or lazy-load relationships that cause implicit writes.

### Rule DB-5: No Application-Level Migrations in Production Without Runbook

Any Alembic migration script executed against the production database must be accompanied
by a runbook that includes:
1. The migration script content
2. Estimated execution time and locking behavior
3. A rollback script
4. Confirmation that the Java monolith is unaffected (backward compatible)

---

## 3. Table Ownership by Migration Wave

The following table defines write ownership for each database table throughout the migration.
"Java" means the Spring Boot monolith is the authoritative writer. "FastAPI: [service]" means
the named FastAPI service has taken over write ownership after cutover.

### Wave 1 Tables

| Table | Pre-cutover Owner | Post-cutover Owner | Notes |
|-------|------------------|--------------------|-------|
| `otp_codes` | Java | FastAPI: auth-service | Small table; safe to transfer early |
| `properties` | Java | FastAPI: property-listing-service | No FK dependencies from other FastAPI services until Wave 2 |
| `property_images` | Java | FastAPI: property-listing-service | Child of `properties` |
| `property_tax_records` | Java | FastAPI: property-listing-service | Child of `properties` |
| `listings` | Java | FastAPI: property-listing-service | Referenced by Wave 2 tables; transfer after Wave 2 read coordination |
| `open_houses` | Java | FastAPI: property-listing-service | Child of `listings` |

### Wave 2 Tables

| Table | Pre-cutover Owner | Post-cutover Owner | Notes |
|-------|------------------|--------------------|-------|
| `clients` | Java | FastAPI: client-crm-service | Referenced by loans, showings, offers — coordinate with Wave 3 |
| `client_documents` | Java | FastAPI: client-crm-service | Child of `clients` |
| `leads` | Java | FastAPI: client-crm-service | |
| `showings` | Java | FastAPI: client-crm-service | References `listings` (Wave 1) and `agents` |
| `offers` | Java | FastAPI: client-crm-service | References `listings` (Wave 1) |
| `counter_offers` | Java | FastAPI: client-crm-service | Child of `offers` |
| `agents` | Java | FastAPI: client-crm-service | Referenced by almost every domain — transfer last in Wave 2 |
| `agent_licenses` | Java | FastAPI: client-crm-service | Child of `agents` |
| `brokerages` | Java | FastAPI: client-crm-service | Referenced by `agents` |
| `commissions` | Java | FastAPI: client-crm-service | References `agents` and `listings` |
| `loan_applications` | Java | FastAPI: loan-origination-service | Central to Wave 3 domains |
| `borrower_employment` | Java | FastAPI: loan-origination-service | Child of `loan_applications` |
| `borrower_assets` | Java | FastAPI: loan-origination-service | Child of `loan_applications` |
| `loan_payments` | Java | FastAPI: loan-origination-service | Child of `loan_applications` |
| `payment_schedules` | Java | FastAPI: loan-origination-service | Child of `loan_applications` |

### Wave 3 Tables

| Table | Pre-cutover Owner | Post-cutover Owner | Notes |
|-------|------------------|--------------------|-------|
| `credit_reports` | Java | FastAPI: underwriting-service | References `loan_applications` (Wave 2) |
| `underwriting_decisions` | Java | FastAPI: underwriting-service | |
| `underwriting_conditions` | Java | FastAPI: underwriting-service | |
| `appraisal_orders` | Java | FastAPI: underwriting-service | |
| `appraisal_reports` | Java | FastAPI: underwriting-service | |
| `comparable_sales` | Java | FastAPI: underwriting-service | |
| `closing_details` | Java | FastAPI: closing-service | References `loan_applications` (Wave 2) |
| `closing_documents` | Java | FastAPI: closing-service | |
| `title_reports` | Java | FastAPI: closing-service | |
| `escrow_accounts` | Java | FastAPI: closing-service | |
| `escrow_disbursements` | Java | FastAPI: closing-service | |

### Wave 4 Tables

| Table | Pre-cutover Owner | Post-cutover Owner | Notes |
|-------|------------------|--------------------|-------|
| `system_settings` | Java | FastAPI: admin-service | Low priority |
| `audit_logs` | Java (and all FastAPI services write) | FastAPI: admin-service | All services write during parallel run; admin-service takes ownership last |
| `notifications` | Java | FastAPI: admin-service | |

---

## 4. Denormalized Column Policy

The existing schema contains numerous denormalized columns (e.g., `agent_name` in `commissions`,
`property_address` in `showings`, `client_name` in `leads`). These are Java-era anti-patterns.

**Policy for FastAPI services:**

- FastAPI services **must not write** to denormalized columns in tables they do not own.
- FastAPI services **must not write** denormalized columns in tables they do own (do not perpetuate the anti-pattern).
- FastAPI services **may read** denormalized columns for performance if needed, but must treat normalized FK relationships as the source of truth.
- When a FastAPI service takes write ownership of a table, denormalized columns should be left nullable and gradually phased out — not dropped — until a confirmed no-dependency state is reached.

---

## 5. Schema Change Process

When a FastAPI service requires a schema change (new column, new index, new table), the
following process applies:

```
1. Author opens an MDR in doc/decisions/ describing:
   - The required change
   - Why it cannot be avoided
   - Impact on Java monolith (will Java break if this runs? will it ignore the column?)
   - Rollback SQL

2. Platform engineer reviews the MDR for:
   - Backward compatibility with Java (new columns must be nullable or have defaults)
   - Lock duration (prefer non-blocking index creation: CREATE INDEX CONCURRENTLY)
   - Alembic script correctness

3. MDR is approved by platform engineer + one domain engineer.

4. Migration is tested against a staging database clone.

5. Migration is applied to production during a low-traffic window with monitoring.

6. Java monolith is confirmed unaffected post-migration.
```

**Key constraint**: Any new column added while Java is still writing to that table must be either:
- `NULL`able with no default (Java will not set it; FastAPI will), OR
- Given a `DEFAULT` value that is safe for Java to ignore.

Never add a `NOT NULL` constraint without a `DEFAULT` to a table that Java is still writing.

---

## 6. Connection Configuration for FastAPI Services

Each FastAPI service must use the following connection approach:

- **Async driver**: `asyncpg` (via SQLAlchemy async engine)
- **Connection pool**: Each service maintains its own pool; pool sizes must be configured to respect the Supabase transaction pooler limit (total connections across all services ≤ configured maximum)
- **Supabase transaction pooler requirement**: `prepare_threshold=0` (equivalent to Spring's `prepareThreshold=0` HikariCP setting) must be set on the asyncpg connection
- **Environment variable**: `DATABASE_URL` must be provided as a `postgresql+asyncpg://` URL
- **No DDL on startup**: FastAPI services must not use `Base.metadata.create_all()` in production

Recommended pool sizing during parallel run:
- Java monolith: max 6 connections (reduced from default 10)
- Each Wave 1 FastAPI service: max 3 connections each
- Adjust as waves complete and Java pool is further reduced

---

## 7. Usability Notes for Platform and Domain Tasks

- **Platform tasks**: Use this document to configure the shared database access layer and set
  connection pool limits before any FastAPI service is deployed.
- **Domain migration tasks**: Reference the ownership table in §3 to determine whether your
  service is permitted to write to a given table at migration time. If Java still owns the table,
  implement read-only access in FastAPI and document it in the service's README.
- **All services**: The `audit_logs` table is a shared write target. All FastAPI services must
  write audit records using their own DB connection; do not call Java APIs to create audit logs.
