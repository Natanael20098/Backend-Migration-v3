# API Compatibility Rules for Frontend-Preserving Migration

## Purpose

This document defines the explicit compatibility rules that govern how the backend migration
from Java (Spring Boot) to Python (FastAPI) must preserve the existing external API contracts.
These rules apply to **all migration epics** and must be consulted before any FastAPI service
exposes a route that replaces a Java-served endpoint.

The frontend (Next.js, `frontend/src/lib/api.ts`) calls `http://localhost:8080` and expects
the contract described here to remain stable. Any deviation that affects the frontend requires
explicit approval per the process defined in [§6 Approval Process](#6-approval-process).

---

## 1. URL and Path Rules

| Rule | Requirement |
|------|-------------|
| **R-URL-1** | All paths must preserve the `/api/` prefix exactly as defined in `frontend/src/lib/endpoints.ts`. |
| **R-URL-2** | Path segment names must not change (e.g., `/api/loans/{id}/credit-report` stays; renaming to `/api/loans/{id}/credit_report` is forbidden). |
| **R-URL-3** | Path parameter names visible in the URL pattern must stay the same (`{id}`, `{status}`, `{agentId}`, `{clientType}`). |
| **R-URL-4** | Sub-resource paths must stay nested under their parent (e.g., `/api/loans/{id}/employment` must not become `/api/employment?loanId={id}`). |
| **R-URL-5** | New internal-only routes added by FastAPI services may use any path, but must not collide with existing Java-served paths until Java is retired for that route. |

---

## 2. HTTP Method Rules

| Rule | Requirement |
|------|-------------|
| **R-MTH-1** | The HTTP method for each endpoint must match the Java implementation exactly (GET, POST, PUT, DELETE, PATCH). |
| **R-MTH-2** | A GET endpoint must not be changed to POST or any other method without frontend approval. |
| **R-MTH-3** | Status update sub-resources currently served via `PUT /api/{resource}/{id}/status` must remain PUT; they must not become PATCH without approval. |

---

## 3. Request Payload Rules

| Rule | Requirement |
|------|-------------|
| **R-REQ-1** | All JSON request body field names must use **camelCase** to match the existing frontend TypeScript types in `frontend/src/lib/types.ts`. |
| **R-REQ-2** | Required fields that are currently accepted by Java endpoints must remain accepted. New FastAPI implementations must not add required fields not present in the original contract. |
| **R-REQ-3** | Optional fields in existing request bodies must remain optional. |
| **R-REQ-4** | Query parameter names must be preserved exactly (`page`, `size`, `sort`, `status`, `clientType`, etc.). |
| **R-REQ-5** | Pagination parameters must use 0-based `page` index and a `size` parameter (Spring Data style), not 1-based offset/limit unless a translation layer is applied transparently. |
| **R-REQ-6** | The `Content-Type: application/json` request header assumption must be preserved; multipart or form-encoded bodies must not be required where JSON was previously used. |

---

## 4. Response Payload Rules

| Rule | Requirement |
|------|-------------|
| **R-RES-1** | All JSON response field names must use **camelCase** matching the TypeScript types in `frontend/src/lib/types.ts`. FastAPI's default `snake_case` serialization must be overridden via response model aliasing or a custom serializer. |
| **R-RES-2** | Paginated list responses must preserve the Spring Page envelope: `{ content: [...], totalElements, totalPages, size, number }`. |
| **R-RES-3** | Single-resource responses must return the resource object directly (no additional wrapper unless Java already wrapped it). |
| **R-RES-4** | Nested objects (e.g., `property`, `agent`, `borrower` inside a listing or loan response) must be embedded with the same depth as the Java response to avoid frontend `undefined` access errors. |
| **R-RES-5** | Null fields must be serialized as `null` in JSON, not omitted, unless the original Java implementation omitted them. |
| **R-RES-6** | Date/time fields must use ISO 8601 string format (`YYYY-MM-DDTHH:mm:ss.sssZ`) matching Spring's default Jackson serialization. |
| **R-RES-7** | UUID-typed IDs must remain serialized as strings (not integers) in all responses. |

---

## 5. HTTP Status Code Rules

| Rule | Requirement |
|------|-------------|
| **R-STS-1** | Successful resource creation must return **201 Created** with the created resource body. |
| **R-STS-2** | Successful retrieval and update must return **200 OK**. |
| **R-STS-3** | Successful deletion must return **200 OK** or **204 No Content** matching the Java behavior per endpoint (check Java controller before implementing). |
| **R-STS-4** | Resource-not-found responses must return **404 Not Found**, not 400 or 500. |
| **R-STS-5** | Validation errors on request bodies must return **400 Bad Request**. |
| **R-STS-6** | Authentication failures (missing or invalid JWT) must return **401 Unauthorized**. The frontend `api.ts` interceptor redirects to `/login` on 401; this must continue to trigger correctly. |
| **R-STS-7** | Authorization failures (authenticated but lacking permission) must return **403 Forbidden**. |
| **R-STS-8** | FastAPI's **422 Unprocessable Entity** (Pydantic validation default) must be remapped to **400 Bad Request** for any endpoint that was previously returning 400 from Java, so the frontend error handling is not broken. |

---

## 6. Authentication Rules

| Rule | Requirement |
|------|-------------|
| **R-AUTH-1** | JWT Bearer token authentication must be preserved. The `Authorization: Bearer <token>` header sent by the frontend (`api.ts` line 10–14) must be accepted without change. |
| **R-AUTH-2** | The JWT signing secret and expiration semantics must produce tokens that are interoperable between Java and FastAPI during parallel-run. Coordinate via the shared secret (`JWT_SECRET` env var). |
| **R-AUTH-3** | The `/api/auth/login` and `/api/auth/register` endpoints must preserve their exact request/response shapes. The `token` field in the login response is read directly by the frontend. |
| **R-AUTH-4** | Public endpoints (those not requiring authentication in Java) must remain public in FastAPI replacements. |
| **R-AUTH-5** | OTP and email-based auth flows exposed through `/api/auth/*` must not change their external shapes during migration. |

---

## 7. Error Response Shape Rules

| Rule | Requirement |
|------|-------------|
| **R-ERR-1** | Error responses must include at least a `message` field (string) at the top level of the JSON body, matching Spring's default error format. |
| **R-ERR-2** | FastAPI's default error body (`{"detail": "..."}`) must be overridden to use `{"message": "..."}` for all client-facing errors on migrated endpoints. |
| **R-ERR-3** | Field-level validation error responses may include additional structured detail, but must still include the top-level `message` field. |

---

## 8. Known Exceptions and Non-Goals

The following are **known acceptable deviations** that do not require additional approval:

| Exception | Justification |
|-----------|--------------|
| **EX-1**: Internal server error response body changes | `500` error bodies are not consumed by the frontend in a structured way; wording may differ. |
| **EX-2**: Response header additions | Adding `X-Request-Id` or other diagnostic headers does not affect frontend behavior. |
| **EX-3**: Improved validation detail on 400 responses | Adding more detail fields alongside `message` is non-breaking. |
| **EX-4**: Performance characteristics | Response time and throughput are not part of the compatibility contract (though SLAs apply separately). |
| **EX-5**: Server-side logging and audit fields | Internal log format changes are invisible to the frontend. |
| **EX-6**: Java anti-pattern denormalized fields | Denormalized/duplicate fields in the DB (e.g., `agent_name` stored in `commissions`) do not need to appear in API responses if the normalized form is equivalent. |

The following are **explicit non-goals** of these compatibility rules:

- This document does not define internal service-to-service API contracts (those are defined per-service).
- This document does not govern the database schema evolution policy (see `postgresql-access-policy.md`).
- This document does not define performance SLAs.
- This document does not apply to admin-only internal tooling APIs with no frontend consumer.

---

## 6. Approval Process for Frontend-Impacting Changes

Any proposed change that would break one or more of the rules above is a **frontend-impacting change** and requires the following:

1. **Document the deviation**: Open a migration decision record (MDR) in `doc/decisions/` describing the old contract, the proposed new contract, and the migration rationale.
2. **Frontend team sign-off**: A frontend engineer must explicitly acknowledge the change and commit any required frontend updates in the same PR or a coordinated PR.
3. **Versioning strategy**: If a clean break is unavoidable, a `/v2/` path prefix or feature-flag-based rollout must be agreed upon before the MDR is approved.
4. **Revert plan**: The MDR must include a rollback step (reverting to Java routing) if the frontend change cannot be deployed simultaneously.

No migration epic may merge a FastAPI service that violates these rules without a merged, approved MDR.

---

## How to Use This Document

- **Migration epic authors**: Reference this document in each epic's acceptance criteria. Link to the specific rules that apply.
- **FastAPI service implementers**: Before implementing a route, look up the original Java controller, confirm the method/path/payload against this document, and implement accordingly.
- **Reviewers**: Use the rule IDs (e.g., `R-RES-1`, `R-STS-8`) as review checklist items for PRs introducing new FastAPI endpoints.
- **QA/integration testers**: Map each rule to a contract test assertion in the integration test suite.
