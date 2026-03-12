# Legacy Endpoint Inventory — Spring MVC / REST Controller Contract

## Purpose and Scope

This document catalogs every HTTP endpoint currently exposed by the HomeLend Pro backend.
It serves as the **migration contract baseline**: any FastAPI implementation must preserve
the contracts documented here exactly, per `doc/api-compatibility-rules.md`.

> **Terminology note**: The task description refers to "JAX-RS" resources, but the original
> backend (`com.zcloud.platform`) uses **Spring MVC `@RestController`** annotations, not
> Java EE JAX-RS. This document reflects the actual Spring MVC contract, which is now
> replicated faithfully by FastAPI services. The term "legacy contract" refers to the
> Spring MVC API contract that FastAPI must preserve.

**Authoritative sources used** (Java source not present in this repository):
1. FastAPI service routers in `services/<service>/app/routers/*.py` — treated as authoritative replicas of the Java contract.
2. `frontend/src/lib/endpoints.ts` — 692-line frontend endpoint catalog (all API paths consumed by Next.js).
3. Existing boundary docs: `doc/closing-service-boundary.md`, `doc/underwriting-service-boundary.md`, `doc/property-listing-service-boundary.md`.
4. `doc/domain-boundary-map.md` §2 — Java controller and model inventory.

---

## 1. Endpoint Catalog by Domain

### 1.1 Auth (`/api/auth/*`) — auth-service (port 8001)

All auth endpoints are **public** (no JWT required).

| Method | Path | Status Code | Auth | Request Body | Response Body | Compatibility Notes |
|--------|------|-------------|------|--------------|---------------|---------------------|
| POST | `/api/auth/send-otp` | 200 (success), 429 (rate-limited), 503 (email failure) | None | `{"email": "string"}` | `{"message": "..."}` | Response is identical regardless of email existence (anti-enumeration). Rate limit: `OTP_RATE_LIMIT_PER_HOUR` per email. |
| POST | `/api/auth/verify-otp` | 200 (success), 401 (invalid/expired code) | None | `{"email": "string", "code": "string"}` | `{"token": "string", "email": "string", "expiresIn": number}` | `token` is HS256 JWT. `expiresIn` is seconds. Frontend reads `token` directly — field name must not change (R-AUTH-3). |

**DTOs** — Pydantic schemas (`auth-service/app/schemas.py`):
- `SendOtpRequest`: `email: str` (required)
- `SendOtpResponse`: `message: str`
- `VerifyOtpRequest`: `email: str`, `code: str` (both required)
- `VerifyOtpResponse`: `token: str`, `email: str`, `expiresIn: int`

---

### 1.2 Properties (`/api/properties/*`) — property-listing-service (port 8002)

All property endpoints are **public** (no JWT required — see §3.5 for compatibility note).

| Method | Path | Status Code | Auth | Request Body | Response Body | Compatibility Notes |
|--------|------|-------------|------|--------------|---------------|---------------------|
| GET | `/api/properties` | 200 | None | — | Spring Page envelope: `{content: [...], totalElements, totalPages, size, number}` | Params: `page` (0-based), `size` (default 20, max 200), `sort` (field name). R-RES-2, R-REQ-5. |
| GET | `/api/properties/search` | 200 | None | — | `PropertyResponse[]` | Query params: `city`, `state`, `propertyType`, `minBedrooms`, `minPrice`, `maxPrice`, `query` (full-text). Returns up to 200 results (no pagination). |
| GET | `/api/properties/{id}` | 200 / 404 | None | — | `PropertyResponse` | `id` is UUID string. 404 if not found. |
| POST | `/api/properties` | 201 | None | `PropertyCreate` | `PropertyResponse` | Required fields: `addressLine1`, `city`, `state`, `zipCode`, `propertyType`. Returns 201 with created resource (R-STS-1). |
| PUT | `/api/properties/{id}` | 200 / 404 | None | `PropertyUpdate` (partial) | `PropertyResponse` | All fields optional (exclude_unset merge). R-STS-2. |
| DELETE | `/api/properties/{id}` | 204 / 404 | None | — | (empty body) | Cascades to `property_images`, `property_tax_records`. R-STS-3. |
| GET | `/api/properties/{id}/images` | 200 / 404 | None | — | `PropertyImageResponse[]` | Ordered by `displayOrder`. |
| POST | `/api/properties/{id}/images` | 201 / 404 | None | `PropertyImageCreate` | `PropertyImageResponse` | If first image or `isPrimary=true`, sets as primary (unsets previous). |
| GET | `/api/properties/{id}/tax-records` | 200 | None | — | `TaxRecordResponse[]` | Ordered by `year` descending. |
| POST | `/api/properties/{id}/tax-records` | 201 / 404 / 409 | None | `TaxRecordCreate` | `TaxRecordResponse` | 409 if a record for the same year already exists. |

**Key DTOs** (`property-listing-service/app/schemas.py`, camelCase aliases via `CamelModel`):
- `PropertyResponse`: `id` (UUID), `addressLine1`, `addressLine2`, `city`, `state`, `zipCode`, `county`, `latitude`, `longitude`, `beds`, `baths`, `sqft`, `lotSize`, `yearBuilt`, `propertyType`, `description`, `parkingSpaces`, `garageType`, `hoaFee`, `zoning`, `parcelNumber`, `createdAt`, `updatedAt`
- `PropertyImageResponse`: `id`, `propertyId`, `url`, `caption`, `isPrimary`, `displayOrder`, `uploadedAt`
- `TaxRecordResponse`: `id`, `propertyId`, `year`, `assessedValue`, `taxAmount`, `taxRate`, `exemptions`, `paid`, `paidDate`, `createdAt`

---

### 1.3 Listings (`/api/listings/*`) — property-listing-service (port 8002)

All listing endpoints are **public** (no JWT required — see §3.5).

| Method | Path | Status Code | Auth | Request Body | Response Body | Compatibility Notes |
|--------|------|-------------|------|--------------|---------------|---------------------|
| GET | `/api/listings` | 200 | None | — | Spring Page envelope | Params: `page` (0-based), `size` (default 20, max 200). |
| GET | `/api/listings/status/{status}` | 200 | None | — | `ListingResponse[]` | Returns all listings with the given status string. |
| GET | `/api/listings/agent/{agentId}` | 200 | None | — | `ListingResponse[]` | Returns all listings for a given agent UUID. |
| GET | `/api/listings/{id}` | 200 / 404 | None | — | `ListingResponse` | Includes computed `daysOnMarket` field. |
| POST | `/api/listings` | 201 / 404 | None | `ListingCreate` | `ListingResponse` | Verifies agent exists (cross-domain read). Required: `propertyId`, `agentId`, `listPrice`. |
| PUT | `/api/listings/{id}` | 200 / 404 | None | `ListingUpdate` (partial) | `ListingResponse` | |
| DELETE | `/api/listings/{id}` | 204 / 404 / 409 | None | — | (empty body) | 409 if open houses exist (must remove first). |
| PUT | `/api/listings/{id}/status` | 200 / 400 / 404 | None | `{"status": "ACTIVE\|PENDING\|SOLD\|WITHDRAWN\|EXPIRED\|COMING_SOON"}` | `ListingResponse` | State machine validated. SOLD is terminal — no further transitions. Sets `soldDate` when transitioning to SOLD. |
| POST | `/api/listings/{id}/open-houses` | 201 / 400 / 404 | None | `OpenHouseCreate` | `OpenHouseResponse` | Only ACTIVE listings accepted. Past dates rejected (400). |

**Key DTOs** (`property-listing-service/app/schemas.py`):
- `ListingResponse`: `id`, `propertyId`, `agentId`, `listPrice`, `originalPrice`, `status`, `mlsNumber`, `listedDate`, `expiryDate`, `soldDate`, `daysOnMarket`, `description`, `virtualTourUrl`, `createdAt`, `updatedAt`
- `OpenHouseResponse`: `id`, `listingId`, `date`, `startTime`, `endTime`, `agentId`, `notes`, `createdAt`

---

### 1.4 Clients / CRM (`/api/clients/*`, `/api/leads/*`, `/api/showings/*`, `/api/offers/*`) — client-crm-service (port 8005)

All CRM endpoints require **JWT authentication**.

#### Clients

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/clients` | 200 | ✅ Required | Paginated. Params: `page`, `size`, `clientType` filter. |
| GET | `/api/clients/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/clients` | 201 | ✅ Required | |
| PUT | `/api/clients/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/clients/{id}` | 204 / 404 | ✅ Required | |
| GET | `/api/clients/{id}/documents` | 200 | ✅ Required | |
| POST | `/api/clients/{id}/documents` | 201 | ✅ Required | |
| DELETE | `/api/clients/{id}/documents/{docId}` | 204 | ✅ Required | |

#### Leads

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/leads` | 200 | ✅ Required | Paginated. |
| GET | `/api/leads/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/leads` | 201 | ✅ Required | |
| PUT | `/api/leads/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/leads/{id}` | 204 / 404 | ✅ Required | |

#### Showings

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/showings` | 200 | ✅ Required | Paginated. |
| GET | `/api/showings/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/showings` | 201 | ✅ Required | |
| PUT | `/api/showings/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/showings/{id}` | 204 / 404 | ✅ Required | |
| PUT | `/api/showings/{id}/status` | 200 / 400 / 404 | ✅ Required | Status transition validated. |

#### Offers

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/offers` | 200 | ✅ Required | Paginated. |
| GET | `/api/offers/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/offers` | 201 | ✅ Required | |
| PUT | `/api/offers/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/offers/{id}` | 204 / 404 | ✅ Required | |
| PUT | `/api/offers/{id}/status` | 200 / 400 / 404 | ✅ Required | Status transition (PENDING → ACCEPTED/REJECTED/COUNTERED/WITHDRAWN). |
| GET | `/api/offers/{id}/counter-offers` | 200 | ✅ Required | |
| POST | `/api/offers/{id}/counter-offers` | 201 | ✅ Required | |

---

### 1.5 Agents / Brokerages (`/api/agents/*`, `/api/brokerages/*`) — client-crm-service (port 8005)

All agent/brokerage endpoints require **JWT authentication**.

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/agents` | 200 | ✅ Required | Paginated. |
| GET | `/api/agents/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/agents` | 201 | ✅ Required | |
| PUT | `/api/agents/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/agents/{id}` | 204 / 404 | ✅ Required | |
| GET | `/api/agents/{id}/licenses` | 200 | ✅ Required | |
| POST | `/api/agents/{id}/licenses` | 201 | ✅ Required | |
| PUT | `/api/agents/{id}/licenses/{licId}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/agents/{id}/licenses/{licId}` | 204 / 404 | ✅ Required | |
| GET | `/api/agents/{agentId}/commissions` | 200 | ✅ Required | |
| POST | `/api/agents/{agentId}/commissions` | 201 | ✅ Required | |
| GET | `/api/brokerages` | 200 | ✅ Required | Paginated. |
| GET | `/api/brokerages/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/brokerages` | 201 | ✅ Required | |
| PUT | `/api/brokerages/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/brokerages/{id}` | 204 / 404 | ✅ Required | |

---

### 1.6 Underwriting Sub-Resources (`/api/loans/{id}/*`) — underwriting-service (port 8003)

All underwriting endpoints require **JWT authentication**.
Note: Only sub-resources are served here. Base loan CRUD (`GET/POST/PUT/DELETE /api/loans`) is **not migrated** (see §4).

#### Credit Reports

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/loans/{loanId}/credit-report` | 200 / 404 | ✅ Required | Returns latest or specific credit report. |
| POST | `/api/loans/{loanId}/credit-report` | 201 | ✅ Required | Orders/records a credit report for the loan. |

#### Underwriting

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/loans/{loanId}/underwriting` | 200 / 404 | ✅ Required | Returns underwriting decision with conditions. |
| POST | `/api/loans/{loanId}/underwriting` | 201 | ✅ Required | Creates underwriting decision. |
| PUT | `/api/loans/{loanId}/underwriting/{decisionId}` | 200 / 404 | ✅ Required | Updates underwriting decision (e.g., APPROVED/DENIED). |

#### Appraisals

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/loans/{loanId}/appraisal` | 200 / 404 | ✅ Required | Lists appraisal orders. |
| POST | `/api/loans/{loanId}/appraisal` | 201 | ✅ Required | Creates appraisal order. |
| GET | `/api/loans/{loanId}/appraisal/{orderId}/report` | 200 / 404 | ✅ Required | Gets appraisal report. |
| POST | `/api/loans/{loanId}/appraisal/{orderId}/report` | 201 | ✅ Required | Submits appraisal report. |
| GET | `/api/loans/{loanId}/appraisal/{orderId}/report/comparables` | 200 | ✅ Required | Lists comparable sales. |
| POST | `/api/loans/{loanId}/appraisal/{orderId}/report/comparables` | 201 | ✅ Required | Adds a comparable sale. |

---

### 1.7 Closing / Settlement (`/api/closings/*`) — closing-service (port 8004)

All closing endpoints require **JWT authentication**.

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/closings` | 200 | ✅ Required | Paginated. |
| GET | `/api/closings/{id}` | 200 / 404 | ✅ Required | |
| POST | `/api/closings` | 201 | ✅ Required | |
| PUT | `/api/closings/{id}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/closings/{id}` | 204 / 404 | ✅ Required | Cascades to documents, title reports, escrow accounts, escrow disbursements. |
| GET | `/api/closings/{id}/documents` | 200 | ✅ Required | |
| POST | `/api/closings/{id}/documents` | 201 | ✅ Required | |
| GET | `/api/closings/{id}/documents/{docId}` | 200 / 404 | ✅ Required | |
| PUT | `/api/closings/{id}/documents/{docId}` | 200 / 404 | ✅ Required | |
| DELETE | `/api/closings/{id}/documents/{docId}` | 204 / 404 | ✅ Required | |
| GET | `/api/closings/{id}/title-report` | 200 / 404 | ✅ Required | |
| POST | `/api/closings/{id}/title-report` | 201 / 409 | ✅ Required | 409 if title report already exists. |
| PUT | `/api/closings/{id}/title-report` | 200 / 404 | ✅ Required | |
| GET | `/api/closings/{id}/escrow` | 200 / 404 | ✅ Required | |
| POST | `/api/closings/{id}/escrow` | 201 / 409 | ✅ Required | 409 if escrow account already exists. |
| PUT | `/api/closings/{id}/escrow` | 200 / 404 | ✅ Required | |
| GET | `/api/closings/{id}/escrow/disbursements` | 200 | ✅ Required | |
| POST | `/api/closings/{id}/escrow/disbursements` | 201 | ✅ Required | |
| PUT | `/api/closings/{id}/escrow/disbursements/{disbId}` | 200 / 404 | ✅ Required | |

---

### 1.8 Loan Origination (`/api/loans/*` base CRUD) — **NOT MIGRATED** (Wave 2B)

These endpoints are defined in the frontend (`frontend/src/lib/endpoints.ts`) and were served
by `LoanController` in the Java monolith. The `loan-origination-service` has not yet been
implemented. All of the following return **404** currently.

| Method | Path | Status Code | Auth | Notes |
|--------|------|-------------|------|-------|
| GET | `/api/loans` | **404** (unmigrated) | ✅ Required | Paginated loan applications. |
| GET | `/api/loans/{id}` | **404** (unmigrated) | ✅ Required | Single loan application. |
| POST | `/api/loans` | **404** (unmigrated) | ✅ Required | Create loan application. |
| PUT | `/api/loans/{id}` | **404** (unmigrated) | ✅ Required | Update loan application. |
| GET | `/api/loans/{id}/employment` | **404** (unmigrated) | ✅ Required | Borrower employment. |
| POST | `/api/loans/{id}/employment` | **404** (unmigrated) | ✅ Required | |
| PUT | `/api/loans/{id}/employment/{empId}` | **404** (unmigrated) | ✅ Required | |
| GET | `/api/loans/{id}/assets` | **404** (unmigrated) | ✅ Required | Borrower assets. |
| POST | `/api/loans/{id}/assets` | **404** (unmigrated) | ✅ Required | |
| PUT | `/api/loans/{id}/assets/{assetId}` | **404** (unmigrated) | ✅ Required | |
| GET | `/api/loans/{id}/payments` | **404** (unmigrated) | ✅ Required | Loan payments. |
| POST | `/api/loans/{id}/payments` | **404** (unmigrated) | ✅ Required | |
| GET | `/api/loans/{id}/payment-schedule` | **404** (unmigrated) | ✅ Required | Payment schedule. |

---

### 1.9 Admin (`/api/admin/*`) — **DEFERRED** (Wave 4)

Admin endpoints are not currently routed in `gateway/nginx.conf`. All return **404**.
Served by `AdminController` in the Java monolith (Wave 4 deferred per `remaining-domains-inventory.md` §3.2).

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/admin/settings` | System settings |
| PUT | `/api/admin/settings/{key}` | Update setting |
| GET | `/api/admin/audit-logs` | Paginated audit log |
| GET | `/api/admin/notifications` | Paginated notifications |
| PUT | `/api/admin/notifications/{id}/read` | Mark notification read |

---

## 2. Compatibility-Sensitive Behaviors

The following behaviors are cross-cutting and must be preserved across all migrated endpoints.
Rule IDs reference `doc/api-compatibility-rules.md`.

| Behavior | Rule ID | Detail |
|----------|---------|--------|
| **camelCase response fields** | R-RES-1 | All FastAPI services use `CamelModel` with `alias_generator = to_camel`. Fields like `created_at` serialize as `createdAt` in responses. |
| **Spring Page envelope** | R-RES-2 | All paginated responses return `{content: [...], totalElements, totalPages, size, number}` with 0-based `number` (page index). |
| **422 → 400 remapping** | R-STS-8 | FastAPI's default 422 Unprocessable Entity is remapped to 400 Bad Request via shared exception handler in `services/shared/exceptions.py`. |
| **Error body shape** | R-ERR-1, R-ERR-2 | Domain errors return `{"message": "..."}`. Auth failures return `{"detail": "..."}` (FastAPI HTTPBearer default — intentional exception). |
| **JWT 401 vs 403** | `jwt-validation-policy.md` §11 | Invalid/expired token → 401. Missing `Authorization` header → 403 (FastAPI HTTPBearer). Frontend redirects on 401, not 403. |
| **OTP rate-limit 429** | (FastAPI-specific) | `POST /api/auth/send-otp` returns 429 when `OTP_RATE_LIMIT_PER_HOUR` exceeded. No Java equivalent (Java likely returned different behavior). |
| **Listing status state machine** | (business rule) | SOLD is terminal. Invalid transitions return 400. |
| **Tax record duplicate year** | (business rule) | Duplicate year in `POST /api/properties/{id}/tax-records` returns 409. |
| **Listing with open houses** | (business rule) | `DELETE /api/listings/{id}` returns 409 if open houses exist. |
| **Property type default** | (implicit) | Defaults to `SINGLE_FAMILY` if `propertyType` omitted on create. |

---

## 3. Unmigrated Paths (Currently Return 404)

| Path Group | Reason | Wave Target |
|------------|--------|-------------|
| `/api/loans` base CRUD | `loan-origination-service` not built | Wave 2B |
| `/api/loans/{id}/employment` | Same | Wave 2B |
| `/api/loans/{id}/assets` | Same | Wave 2B |
| `/api/loans/{id}/payments` | Same | Wave 2B |
| `/api/loans/{id}/payment-schedule` | Same | Wave 2B |
| `/api/admin/*` | Admin domain deferred | Wave 4 |

---

## 4. DTOs by Domain

DTOs are defined as Pydantic v2 models in `services/<service>/app/schemas.py` per service.
All response models extend `CamelModel` from `services/shared/models.py`, which applies:
- `alias_generator = to_camel` — snake_case Python fields serialize as camelCase in JSON
- `populate_by_name = True` — allows both snake_case and camelCase on input

**DTO naming convention**: `{Entity}Create` (POST body), `{Entity}Update` (PUT body, all fields optional), `{Entity}Response` (serialized output). Sub-resource DTOs follow the same pattern.

**Field name examples** (Python → JSON alias in responses):
- `address_line1` → `addressLine1`
- `created_at` → `createdAt`
- `property_type` → `propertyType`
- `total_elements` → `totalElements`
- `is_primary` → `isPrimary`

Full Pydantic schema definitions are the canonical DTO reference. Consult individual service
`schemas.py` files for complete field lists and validation constraints.

---

## 5. How to Use This Document

- **Migration implementers**: For each new FastAPI endpoint, verify the path, method, status codes, and DTO field names against this catalog before merging.
- **Contract test authors**: Use the endpoint tables in §§1.1–1.9 as the test matrix. Each row is a test case.
- **Frontend team**: This catalog reflects the complete set of paths the frontend (`frontend/src/lib/endpoints.ts`) calls. Paths in §§1.8–1.9 currently return 404 — plan frontend error handling accordingly.
- **QA/integration testers**: Map `doc/api-compatibility-rules.md` rule IDs from §2 to contract test assertions.
