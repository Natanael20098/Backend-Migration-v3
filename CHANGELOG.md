# Changelog

## [Unreleased] – 2025-01-30 12:00

### Added
- `doc/api-compatibility-rules.md` — Explicit API compatibility rules for frontend-preserving migration covering URLs, HTTP methods, request/response payloads, status codes, authentication, error shapes, known exceptions, non-goals, and the approval process for frontend-impacting changes. Reusable by all migration epics.
- `doc/domain-boundary-map.md` — Legacy backend domain and service boundary map. Maps Java monolith packages (`com.zcloud.platform`) to proposed FastAPI service ownership across auth, property/listing, client/CRM, loan origination, underwriting, closing, and admin domains. Identifies first-wave vs later-wave migration candidates, shared concerns, and cross-domain touchpoints.
- `doc/postgresql-access-policy.md` — Shared PostgreSQL access policy for parallel-run migration. Defines DB usage rules, per-table write ownership by migration wave, denormalized column handling, schema change process (MDR-gated), and FastAPI connection configuration requirements.
- `doc/cutover-playbook.md` — Reusable service-by-service cutover playbook. Covers pre-cutover readiness (routing, contracts, DB, smoke tests, rollback prep), traffic shift procedure, post-cutover validation (immediate and 24-hour), rollback steps, and Java retirement criteria. Domain teams create a Cutover Record per service without redefining the master checklist.
