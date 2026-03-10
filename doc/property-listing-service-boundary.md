# Property/Listing Service Boundary Definition

## Purpose

This document defines the exact scope of the `property-listing-service` FastAPI migration, including
owned entities, preserved external endpoints, dependencies on auth and other domains, and shared-table
and ownership risks. It is the authoritative reference for the Wave 1 property/listing migration epic.

---

## 1. Owned Capabilities

The `property-listing-service` owns all read and write operations for the following domain areas:

### 1.1 Property Management

| Capability | Description |
|-----------|-------------|
| Property CRUD | Create, read, update, and delete property records (`properties` table) |
| Property search | Filter properties by city, state, type, beds, price range using parameterized queries |
| Property images | Add and retrieve images for a property (`property_images` table) |
| Property tax records | Add and retrieve tax records for a property (`property_tax_records` table) |

### 1.2 Listing Management

| Capability | Description |
|-----------|-------------|
| Listing CRUD | Create, read, update, and delete MLS listings (`listings` table) |
| Listing status management | Change listing status (ACTIVE → PENDING → SOLD/WITHDRAWN) with valid transitions |
| Listing search | Filter listings by status, agent, or price range |
| Open house management | Schedule open houses for active listings (`open_houses` table) |

### 1.3 Sub-Resource Reads (Cross-Domain, Read-Only)

| Resource | Source Table | Access Type |
|----------|-------------|-------------|
| Agent details on a listing | `agents` | Read-only (owned by client-crm-service after Wave 2) |
| Brokerage info for agent | `brokerages` | Read-only (owned by client-crm-service after Wave 2) |
| Offer count for a listing | `offers` | Read-only (owned by client-crm-service after Wave 2) |
| Showing count for a listing | `showings` | Read-only (owned by client-crm-service after Wave 2) |

---

## 2. Preserved External Endpoints

The following endpoints are served by the Java `PropertyController` and `ListingController` and must
be reimplemented with identical external contracts. Path, method, and response shape must match
the rules in `doc/api-compatibility-rules.md`.

### 2.1 Property Endpoints

| Method | Path | Java Source | Notes |
|--------|------|-------------|-------|
| `GET` | `/api/properties` | `PropertyController.listProperties` | Paginated; supports `page`, `size`, `sort` query params |
| `GET` | `/api/properties/{id}` | `PropertyController.getProperty` | Returns property with embedded images list |
| `POST` | `/api/properties` | `PropertyController.createProperty` | Returns 201 with created resource |
| `PUT` | `/api/properties/{id}` | `PropertyController.updateProperty` | Returns 200 with updated resource |
| `DELETE` | `/api/properties/{id}` | `PropertyController.deleteProperty` | Returns 204 |
| `GET` | `/api/properties/search` | `PropertyController.searchProperties` | Supports `city`, `state`, `propertyType`, `minBedrooms`, `minPrice`, `maxPrice` query params |
| `GET` | `/api/properties/{id}/images` | `PropertyImageRepository` (direct) | Returns list of property images |
| `POST` | `/api/properties/{id}/images` | `PropertyController.addImage` | Returns 201 with created image |
| `GET` | `/api/properties/{id}/tax-records` | `PropertyController.getTaxRecords` | Returns list of tax records |
| `POST` | `/api/properties/{id}/tax-records` | `PropertyController.addTaxRecord` | Returns 201 with created tax record |

### 2.2 Listing Endpoints

| Method | Path | Java Source | Notes |
|--------|------|-------------|-------|
| `GET` | `/api/listings` | `ListingController.listListings` | Paginated; supports `page`, `size` |
| `GET` | `/api/listings/{id}` | `ListingController.getListing` | Returns listing with embedded property and agent |
| `POST` | `/api/listings` | `ListingController.createListing` | Returns 201 with created resource |
| `PUT` | `/api/listings/{id}` | `ListingController.updateListing` | Returns 200 |
| `DELETE` | `/api/listings/{id}` | N/A (not in Java controller) | Returns 204 |
| `GET` | `/api/listings/status/{status}` | `ListingController.listListings?status=` | Filter listings by status |
| `GET` | `/api/listings/agent/{agentId}` | `ListingController.listListings?agentId=` | Filter listings by agent |
| `PUT` | `/api/listings/{id}/status` | `ListingController.changeListingStatus` | Status transition with validation |

---

## 3. Dependencies on Auth and Other Domains

### 3.1 Auth Dependency

| Dependency | Description | Resolution |
|-----------|-------------|------------|
| JWT validation | All property and listing endpoints require `Authorization: Bearer <token>` | Use `shared.auth.make_get_current_user(settings.JWT_SECRET)` dependency; no local auth logic |
| JWT secret | Must be identical to the Java monolith's `JWT_SECRET` | Sourced from `JWT_SECRET` env var; same value as all other services |
| Token interoperability | Tokens issued by `auth-service` or Java must both be accepted | HMAC-HS256 with shared secret; no issuer validation |

### 3.2 Cross-Domain Data Dependencies (Read-Only During Wave 1)

| Table | Owning Service (Wave 1) | Access by property-listing-service | Notes |
|-------|------------------------|-------------------------------------|-------|
| `agents` | Java (until Wave 2) | Read-only JOIN for listing.agent | SELECT only; no writes |
| `brokerages` | Java (until Wave 2) | Read-only JOIN for agent.brokerage | SELECT only; no writes |
| `offers` | Java (until Wave 2) | Read-only COUNT for listing detail | SELECT COUNT only; no writes |
| `showings` | Java (until Wave 2) | Read-only COUNT for listing detail | SELECT COUNT only; no writes |

### 3.3 Email / Notification Dependency

The Java `ListingController` sends inline notifications via `NotificationHelper` on status changes
and open house creation. The `property-listing-service` does **not** reimplement this in Wave 1 —
no email/notification calls are made. This is an acceptable deviation per the migration plan; the
Java monolith retains notification responsibility until `admin-service` is migrated.

---

## 4. Shared-Table and Ownership Risks

### 4.1 Write Ownership Conflict Risk

| Table | Risk | Mitigation |
|-------|------|-----------|
| `listings` | Both Java and FastAPI writing simultaneously would cause lost-update conflicts | Enforce one-writer-per-table rule per `postgresql-access-policy.md` §3. Java traffic for `/api/listings/*` is cut over via nginx before FastAPI takes write ownership. |
| `properties` | Same risk as listings | Same mitigation — routing cutover precedes write ownership transfer. |
| `open_houses` | Child of `listings`; same cutover timing applies | Included in property-listing-service cutover scope. |
| `property_images` | Child of `properties` | Included in property-listing-service cutover scope. |
| `property_tax_records` | Child of `properties` | Included in property-listing-service cutover scope. |

### 4.2 FK Reference Risks (Tables Owned by Other Services)

| FK From | FK To | Risk |
|---------|-------|------|
| `listings.agent_id` | `agents.id` | Java writes `agents`; FastAPI creates listings referencing existing agent UUIDs. Agent must exist before listing creation. If agent is deleted while Java owns it, FK will fail. Low risk in practice. |
| `commissions.listing_id` | `listings.id` | `commissions` is owned by Java/Wave 2 service. If listing is deleted via FastAPI, commissions table will have orphaned FK references unless cascade delete is handled. **Risk: FastAPI delete must check for or cascade commissions.** |
| `showings.listing_id` | `listings.id` | Same risk as commissions. |
| `offers.listing_id` | `listings.id` | Same risk as commissions. |

**Recommendation**: During Wave 1, the `property-listing-service` should reject DELETE of a listing
that has associated offers, showings, or commissions with a 409 Conflict response.

### 4.3 Denormalized Column Policy

Per `postgresql-access-policy.md` §4, the following denormalized columns exist in the owned tables
but must **not** be written by the FastAPI service:

| Column | Table | Policy |
|--------|-------|--------|
| `property_address` | `listings` | Do not write; left nullable |
| `property_city` | `listings` | Do not write; left nullable |
| `property_state` | `listings` | Do not write; left nullable |
| `property_zip` | `listings` | Do not write; left nullable |
| `property_beds` | `listings` | Do not write; left nullable |
| `property_baths` | `listings` | Do not write; left nullable |
| `property_sqft` | `listings` | Do not write; left nullable |
| `property_address` | `property_tax_records` | Do not write; left nullable |
| `property_address` | `open_houses` | Do not write; left nullable |

### 4.4 Schema Anti-Patterns Inherited

The following Java-era anti-patterns are present in the schema and are inherited by the FastAPI
service. They must not be perpetuated, but cannot be removed without an MDR per `postgresql-access-policy.md`.

| Anti-Pattern | Tables Affected | FastAPI Handling |
|-------------|----------------|-----------------|
| No CHECK constraints on enum-like columns (`property_type`, `status`) | `properties`, `listings` | Pydantic `Literal` validation at application layer |
| UUID PKs (no integer sequences) | All | Use Python `uuid` library; no auto-increment |
| Mixed `TIMESTAMP` and `TIMESTAMP WITH TIME ZONE` column types | `properties.updated_at`, `agents.updated_at` | Map to `datetime` in Python; accept both timezone-aware and naive |

---

## 5. Summary

| Attribute | Value |
|-----------|-------|
| **Service name** | `property-listing-service` |
| **Path prefixes owned** | `/api/properties/*`, `/api/listings/*` |
| **Port** | `8002` |
| **DB tables owned (write)** | `properties`, `property_images`, `property_tax_records`, `listings`, `open_houses` |
| **DB tables read (cross-domain)** | `agents`, `brokerages` |
| **Migration wave** | Wave 1 |
| **Auth dependency** | Shared `JWT_SECRET`; validates tokens from `auth-service` or Java |
| **External service dependencies** | None (no email/notification in Wave 1) |
| **Cutover record** | `doc/cutover-records/property-listing-service-cutover.md` |
