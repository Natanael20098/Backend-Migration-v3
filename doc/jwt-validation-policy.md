# JWT Validation Policy

**Scope:** All Python FastAPI services in the HomeLend Pro platform.  
**Effective as of:** CVE-2022-29217 remediation (python-jose → PyJWT migration).

---

## 1. Purpose

This document defines the authoritative JWT validation policy for the HomeLend Pro Python backend. All services must follow this policy. Deviations require an architecture review.

---

## 2. Library

| Requirement | Value |
|---|---|
| **Required library** | `PyJWT >= 2.9.0` |
| **Replaced library** | `python-jose 3.3.0` (CVE-2022-29217 — algorithm confusion) |
| **Why PyJWT** | Actively maintained, widely adopted, compatible API, no extra `[cryptography]` dependency required for HS256 |

`python-jose` must not be added to any service's `requirements.txt`.

---

## 3. Algorithm

- **Allowed algorithm:** HMAC-SHA256 (`HS256`) only.
- **Algorithm is never read from the token header or from request input.** The decoder is always called with `algorithms=["HS256"]` hardcoded in source.
- No asymmetric algorithms (RS256, ES256, etc.) are used or accepted.
- No "none" algorithm is accepted.

This directly mitigates CVE-2022-29217 (algorithm confusion) and any related header-injection attacks.

---

## 4. Token Structure

Tokens are issued by `auth-service` and consumed by all other services. The canonical token payload is:

| Claim | Type | Description |
|---|---|---|
| `sub` | string | Subject — the authenticated user's email address |
| `iat` | integer (Unix timestamp) | Issued-at time |
| `exp` | integer (Unix timestamp) | Expiration time |

- `sub` must be present and non-null. A token with a missing or null `sub` is rejected.
- `iss` (issuer) and `aud` (audience) are not currently used and not validated. This is intentional for compatibility with the legacy Java `jjwt`-issued tokens during the migration window.

---

## 5. Validation Rules

Every token passed in a `Bearer` `Authorization` header must satisfy all of the following:

1. **Signature is valid** — verified using the shared `JWT_SECRET` env var and `HS256`.
2. **Not expired** — `exp` is after the current UTC time. PyJWT validates this automatically on `jwt.decode()`.
3. **`sub` is present and non-null** — checked explicitly after decoding.

No other claim validation is performed currently.

---

## 6. Where Validation Occurs

**All JWT validation is performed exclusively in `services/shared/auth.py::verify_jwt`.**

- No service may implement its own JWT decode/verify logic.
- No service may call `jwt.decode()` directly (except `shared/auth.py`).
- Services obtain the current user by importing and using `make_get_current_user` from `shared.auth`:

```python
from shared.auth import make_get_current_user

get_current_user = make_get_current_user(settings.JWT_SECRET)

@router.get("/resource")
async def get_resource(current_user: str = Depends(get_current_user)):
    ...
```

---

## 7. Token Issuance

**Only `auth-service` issues tokens.** No other service may call `jwt.encode()`.

Token issuance occurs in `services/auth-service/app/router.py` at the `/api/auth/verify-otp` endpoint, after OTP validation succeeds.

The signing call is:
```python
import jwt
token = jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")
```

The `algorithm` parameter is always `"HS256"` — it is never accepted from external input.

---

## 8. Secret Management

- The shared secret is `JWT_SECRET` (environment variable, present in `.env.example`).
- The same `JWT_SECRET` value must be set identically across all services.
- Minimum recommended length: 32 random characters.
- The secret must never be logged, returned in API responses, or committed to source control.

---

## 9. Error Handling

Any JWT validation failure raises **HTTP 401** with a standardized error body:

```json
{"detail": "Invalid or expired token"}
```

This covers all failure modes:
- Expired token (`jwt.ExpiredSignatureError`)
- Invalid signature (`jwt.InvalidSignatureError`)
- Malformed token (`jwt.DecodeError`)
- Wrong algorithm
- Missing or null `sub` claim
- Any other `jwt.PyJWTError` subclass

The error message is intentionally generic to avoid leaking which specific check failed.

---

## 10. Per-Service Strategy (Inventory)

| Service | Imports JWT directly | JWT Operations | Strategy |
|---|---|---|---|
| `auth-service` | YES — `router.py` imports `jwt` | Issues tokens (`jwt.encode`) at `/verify-otp` | **Upgrade**: replaced `python-jose` with `PyJWT==2.9.0` |
| `shared/auth.py` | YES — imports `jwt` | Validates tokens (`jwt.decode`) | **Upgrade**: replaced `python-jose` with `PyJWT==2.9.0` |
| `client-crm-service` | NO — imports `shared.auth` only | Validates via shared | **Replace in requirements.txt**: `python-jose` → `PyJWT` (needed to run `shared.auth`) |
| `closing-service` | NO — imports `shared.auth` only | Validates via shared | **Replace in requirements.txt**: `python-jose` → `PyJWT` (needed to run `shared.auth`) |
| `underwriting-service` | NO — imports `shared.auth` only | Validates via shared | **Replace in requirements.txt**: `python-jose` → `PyJWT` (needed to run `shared.auth`) |
| `property-listing-service` | NO — does NOT import `shared.auth` | No JWT operations | **Remove entirely**: `python-jose` removed, `PyJWT` not added — no JWT dependency needed |

### Finding: `property-listing-service`

This service has no routes that require authentication. Neither its routers nor its main module import anything from `shared.auth`. The presence of `python-jose[cryptography]==3.3.0` in its `requirements.txt` was a copy-paste artifact from the service template. It has been removed with no replacement.

### Finding: Validation is already centralized

All non-auth services delegate validation to `shared.auth.make_get_current_user`. None of them call `jose`/`jwt` directly. This means the migration to PyJWT required changes in only two source files: `shared/auth.py` and `auth-service/app/router.py`.

---

## 11. Invalid and Expired Token Behavior

| Scenario | HTTP Status | Response Body |
|---|---|---|
| Valid token | 200 (or applicable success code) | Normal response |
| Expired token | 401 | `{"detail": "Invalid or expired token"}` |
| Invalid signature | 401 | `{"detail": "Invalid or expired token"}` |
| Malformed/unparseable token | 401 | `{"detail": "Invalid or expired token"}` |
| Missing `Authorization` header | 403 | `{"detail": "Not authenticated"}` (FastAPI HTTPBearer default) |
| Missing `sub` claim | 401 | `{"detail": "Invalid or expired token"}` |

This behavior is standardized across all services through the shared `verify_jwt` function. Individual services do not handle these cases differently.

---

## 12. References

- [PyJWT Documentation](https://pyjwt.readthedocs.io/)
- [CVE-2022-29217](https://nvd.nist.gov/vuln/detail/CVE-2022-29217) — python-jose algorithm confusion
- `services/shared/auth.py` — canonical validation implementation
- `services/auth-service/app/router.py` — canonical token issuance
- `services/auth-service/tests/test_jwt.py` — JWT unit tests
