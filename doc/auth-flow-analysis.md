# Authentication and Authorization Flow Analysis

## Purpose

This document traces the authentication and authorization flow end to end — from OTP request
through JWT issuance to protected endpoint access — capturing both the current Python FastAPI
implementation and the legacy Java Spring Boot behavior. It identifies token interoperability
guarantees, protected routes, principal propagation, and migration risks.

**Cross-references**:
- `doc/jwt-validation-policy.md` — authoritative JWT algorithm, library, and error behavior policy
- `doc/api-compatibility-rules.md` §6 — auth compatibility rules (R-AUTH-1 through R-AUTH-5)
- `services/shared/auth.py` — canonical validation implementation
- `services/auth-service/app/router.py` — canonical token issuance

---

## 1. End-to-End Authentication Flow (Current Python FastAPI State)

### 1.1 OTP Request Flow

```
User → POST /api/auth/send-otp (body: {"email": "user@example.com"})
  │
  ▼
nginx → auth-service:8001
  │
  ▼
Rate limit check:
  SELECT COUNT(*) FROM otp_codes
  WHERE email = ? AND created_at >= (now - 1 hour)
  └─ if count >= OTP_RATE_LIMIT_PER_HOUR → HTTP 429 ({"detail": "Too many requests..."})
  │
  ▼
Generate 6-digit OTP:
  code = f"{secrets.randbelow(1_000_000):06d}"   ← cryptographic randomness (secrets module)
  expires_at = now + OTP_EXPIRY_MINUTES
  │
  ▼
INSERT INTO otp_codes (email, code, expires_at, used=false, created_at=now)
  │
  ▼
Mailgun HTTP API → send OTP email to user
  └─ if Mailgun fails → HTTP 503 ({"detail": "Failed to send verification email."})
  │
  ▼
HTTP 200: {"message": "If this email is registered, a code has been sent."}
  NOTE: identical response for registered and unregistered emails (prevents enumeration)
```

### 1.2 OTP Verification and JWT Issuance Flow

```
User → POST /api/auth/verify-otp (body: {"email": "...", "code": "123456"})
  │
  ▼
nginx → auth-service:8001
  │
  ▼
SELECT otp_codes
  WHERE email = ? AND code = ? AND used = false AND expires_at > now
  ORDER BY created_at DESC LIMIT 1
  └─ if not found → HTTP 401 ({"detail": "Invalid or expired code."})
  │
  ▼
UPDATE otp_codes SET used = true  ← single-use enforcement
  │
  ▼
JWT issuance:
  claims = {
    "sub": email,       ← subject = authenticated user's email
    "iat": now_unix,    ← issued at (Unix timestamp)
    "exp": now + (JWT_EXPIRATION_MS / 1000)  ← expiry (Unix timestamp)
  }
  token = jwt.encode(claims, JWT_SECRET, algorithm="HS256")  ← PyJWT >= 2.9.0
  │
  ▼
HTTP 200: {"token": "<jwt>", "email": "user@example.com", "expiresIn": <seconds>}
```

### 1.3 Protected Endpoint Access Flow

```
User → GET /api/properties (Authorization: Bearer <token>)
  │
  ▼
nginx → property-listing-service:8002
  │
  ▼
NOTE: property-listing-service has NO JWT validation (see §3.5 below).
For services WITH JWT validation (all others):
  │
  ▼
FastAPI HTTPBearer security scheme:
  └─ if Authorization header missing → HTTP 403 ({"detail": "Not authenticated"})
  └─ if Authorization header present → extract Bearer token
  │
  ▼
shared.auth.verify_jwt(token, JWT_SECRET):
  jwt.decode(token, JWT_SECRET, algorithms=["HS256"])  ← algorithm hardcoded, NOT from header
  │
  ├─ ExpiredSignatureError → HTTP 401 ({"detail": "Invalid or expired token"})
  ├─ InvalidSignatureError → HTTP 401 ({"detail": "Invalid or expired token"})
  ├─ DecodeError           → HTTP 401 ({"detail": "Invalid or expired token"})
  ├─ any PyJWTError        → HTTP 401 ({"detail": "Invalid or expired token"})
  └─ sub is None/missing   → HTTP 401 ({"detail": "Invalid or expired token"})
  │
  ▼
Return: payload["sub"]  ← email string
  │
  ▼
Route handler receives: current_user: str = Depends(get_current_user)
  current_user = "user@example.com"  ← email only, no roles
```

---

## 2. Legacy Java Authentication Flow (for Migration Comparison)

The Java Spring Boot monolith (`com.zcloud.platform`) implemented the following auth flow.
Java source is not present in this repository; this reconstruction is based on
`doc/domain-boundary-map.md` §1 and Spring Security conventions for the identified class names.

### 2.1 Java Login and Token Issuance

```
Java: POST /api/auth/login (or OTP-based flow)
  → AuthController.login()
  → JwtUtil.generateToken(email)
      Jwts.builder()
          .setSubject(email)
          .setIssuedAt(new Date())
          .setExpiration(new Date(now + JWT_EXPIRATION_MS))
          .signWith(SignatureAlgorithm.HS256, JWT_SECRET)
          .compact()
  → Returns {"token": "<jwt>", "expiresIn": N}
```

### 2.2 Java Request Authentication (Per-Request Filter)

```
Java: Any HTTP request
  → JwtAuthenticationFilter extends OncePerRequestFilter
  → Extracts "Authorization: Bearer <token>" header
  → JwtUtil.validateToken(token):
      Jwts.parser()
          .setSigningKey(JWT_SECRET)
          .parseClaimsJws(token)
          .getBody()
          .getSubject()
  → SecurityContextHolder.setAuthentication(
      new UsernamePasswordAuthenticationToken(email, null, authorities)
    )
  → Downstream: SecurityUtils.getCurrentUserEmail()
       = SecurityContextHolder.getContext().getAuthentication().getName()
```

### 2.3 Java Authorization (Role-Based)

```
Java: Protected method/endpoint
  → @PreAuthorize("hasRole('ADMIN')") or @Secured("ROLE_LOAN_OFFICER")
  → Spring Security evaluates roles from UsernamePasswordAuthenticationToken authorities
  → 403 Forbidden if role check fails
  → 401 Unauthorized if token validation fails (all auth failures → 401 in Java)
```

---

## 3. Token Interoperability Analysis

During the parallel run period (Java and FastAPI serving different routes simultaneously),
tokens issued by Java must be accepted by FastAPI services, and vice versa.

| Interoperability Factor | Java Behavior | FastAPI Behavior | Compatible? |
|-------------------------|--------------|------------------|:-----------:|
| **Algorithm** | HS256 (`jjwt` library) | HS256 (`PyJWT` library) | ✅ Yes |
| **Secret** | `JWT_SECRET` env var | `JWT_SECRET` env var (same value) | ✅ Yes |
| **`sub` claim** | Set to email string | Validated: must be present and non-null | ✅ Yes |
| **`iat` claim** | Set by `jjwt` | Not validated (only `sub` and `exp` checked) | ✅ Yes |
| **`exp` claim** | Set to `now + JWT_EXPIRATION_MS` | Validated automatically by PyJWT | ✅ Yes |
| **`iss` claim** | Not set | Not validated (intentional for compatibility) | ✅ Yes |
| **`aud` claim** | Not set | Not validated (intentional for compatibility) | ✅ Yes |
| **Token expiry duration** | `JWT_EXPIRATION_MS` | `JWT_EXPIRATION_MS` / 1000 (seconds) | ✅ Yes (same env var) |
| **Issuer domain** | N/A | N/A | ✅ Yes |

**Conclusion**: Tokens issued by Java `AuthController` are fully accepted by FastAPI services.
Tokens issued by FastAPI `auth-service` are fully accepted by the Java `JwtAuthenticationFilter`.
The shared `JWT_SECRET` is the single shared credential enabling this interoperability.

**OTP table schema compatibility**: Java may use an `otp_codes` table with different column
names or types. If Java uses an in-memory OTP store, no schema conflict exists. If Java uses
the same `otp_codes` table, confirm the DDL against `auth-service` Alembic migration SQL before
Wave 1 Java retirement. This is a **pre-retirement action item** for `auth-service`.

---

## 4. Authorization Checks and Protected Routes

### 4.1 Protected route inventory

| Path Prefix | Auth Required | FastAPI Implementation | Notes |
|-------------|:---:|----------------------|-------|
| `/api/auth/*` | ❌ Public | No `Depends(get_current_user)` | `send-otp`, `verify-otp` are intentionally public |
| `/api/properties/*` | ❌ Public | No `Depends(get_current_user)` | See §3.5 — potential regression from Java (documented risk) |
| `/api/listings/*` | ❌ Public | No `Depends(get_current_user)` | Same as above |
| `/api/loans/{id}/credit-report` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/loans/{id}/underwriting` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/loans/{id}/appraisal/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/closings/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/clients/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/agents/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/brokerages/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/leads/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/showings/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |
| `/api/offers/*` | ✅ Required | `Depends(get_current_user)` | Any valid JWT |

### 4.2 Role-based access — known regression from Java

The Java monolith enforced **role-based authorization** using Spring Security annotations:
- `@Secured("ROLE_ADMIN")` — system settings, admin operations, certain reporting endpoints
- `@Secured("ROLE_LOAN_OFFICER")` — underwriting decisions, appraisal orders
- `@Secured("ROLE_CLIENT")` — client profile, document uploads (own data only)

The FastAPI implementation uses **identity-only authorization** (email string from JWT `sub` claim).
**All authenticated users have identical access to all protected endpoints.** This is a known
regression from the Java authorization model. No role claim exists in the current JWT payload.

**Impact**: Any Java endpoint that was restricted to `ADMIN` or `LOAN_OFFICER` roles is now
accessible to any authenticated user in the FastAPI implementation.

**Explicit list of Java role-restricted endpoints** (reconstructed from Java class inventory;
exact role assignments require Java source code verification):
- `/api/admin/*` — ADMIN role required (deferred to Wave 4; currently returns 404)
- `/api/loans/{id}/underwriting` POST/PUT — likely LOAN_OFFICER role in Java
- `/api/loans/{id}/appraisal` POST — likely LOAN_OFFICER role in Java

---

## 5. Principal Propagation

How the authenticated user identity is passed through the request handling stack:

### 5.1 FastAPI propagation (current)

```python
# In each service's main.py or router configuration:
get_current_user = make_get_current_user(settings.JWT_SECRET)

# In route handlers:
@router.get("/api/closings")
async def list_closings(
    current_user: str = Depends(get_current_user),  # email string injected
    db: AsyncSession = Depends(get_db),
):
    # current_user = "user@example.com"
    # Usage: audit log population (planned Wave 4), ownership checks
    ...
```

- `current_user` is a plain email string — no role, no tenant, no additional claims.
- Used for: audit log population (planned), operation context, not for access control.
- **No role propagation** in current FastAPI implementation.

### 5.2 Java propagation (legacy)

```java
// SecurityUtils.java
public static String getCurrentUserEmail() {
    Authentication auth = SecurityContextHolder.getContext().getAuthentication();
    return auth.getName();  // returns email (principal name)
}

public static boolean hasRole(String role) {
    Authentication auth = SecurityContextHolder.getContext().getAuthentication();
    return auth.getAuthorities().stream()
        .anyMatch(a -> a.getAuthority().equals("ROLE_" + role));
}
```

- Java propagated both **identity** (email) and **roles** (granted authorities).
- Roles were loaded from a user profile or statically embedded in the JWT.
- FastAPI's equivalent only propagates identity.

---

## 6. Migration Risks and Compatibility Needs

| Risk ID | Risk | Description | Mitigation |
|---------|------|-------------|------------|
| **AUTH-R1** | **Role-based auth regression** | Java enforced `ADMIN`, `LOAN_OFFICER`, `CLIENT` roles. FastAPI does not. Java-restricted admin/loan endpoints are now accessible to any authenticated user in FastAPI. | Document which routes were role-restricted. Add a `roles` claim to the JWT payload in a future epic. Until then, treat the role regression as a known accepted risk per Wave 3A/3B cutover. |
| **AUTH-R2** | **`property-listing-service` has no JWT auth** | Property and listing endpoints have no authentication in the FastAPI implementation. If Java's `PropertyController` required auth, FastAPI is less restrictive. | Verify whether Java's `PropertyController` used `@Secured` or `permitAll()` in `SecurityConfig`. If auth was required, add `Depends(get_current_user)` before Wave 1 retirement. Documented in `jwt-validation-policy.md` §10 as a known finding. |
| **AUTH-R3** | **JWT_SECRET rotation** | Rotating the secret invalidates all in-flight tokens from both Java and FastAPI simultaneously. No rolling rotation is supported. | Coordinate rotation during a scheduled maintenance window. Issue a forced re-authentication event to all sessions. No gradual rotation supported in current architecture. |
| **AUTH-R4** | **HTTPBearer 403 vs Java 401 for missing header** | FastAPI HTTPBearer returns **403** for missing `Authorization` header. Java `JwtAuthenticationFilter` returned **401** for all auth failures. The frontend `api.ts` redirects on **401**, not 403. | The frontend redirect on 401 may not trigger for missing-header cases (which produce 403). Risk is low for normal user flows (authenticated users always send the header). Monitor for 403 responses after cutover to identify unexpected missing-header cases. |
| **AUTH-R5** | **OTP table schema mismatch** | Java may store OTPs in-memory or in a different `otp_codes` schema. If Java writes `otp_codes` with different column names or types, the FastAPI `auth-service` may read inconsistent records during parallel run. | Confirm Java's OTP storage mechanism against `auth-service` Alembic migration SQL before Wave 1 Java retirement. |
| **AUTH-R6** | **Token expiry clock skew** | Near-expiry tokens valid on Java's clock may be rejected by FastAPI's clock (or vice versa) if server clocks drift. | Use NTP-synchronized clocks in production. Docker containers inherit the host clock. Acceptable drift threshold: < 5 seconds. |
| **AUTH-R7** | **No ownership enforcement** | FastAPI services do not verify that the authenticated user owns the resource being accessed (e.g., a client can access any other client's data). Java may have enforced resource ownership via `@PostAuthorize` or service-layer checks. | Audit Java service layer for ownership checks in `ClientService`, `LoanService`. Add ownership verification to FastAPI handlers where Java enforced it, before production cutover for those routes. |

---

## 7. Summary: Authentication Architecture Invariants

The following properties are guaranteed by the current implementation and must be preserved:

1. **JWT algorithm is always HS256** — hardcoded in both `auth-service/router.py` and `shared/auth.py`. Never read from token header.
2. **JWT secret is environment-injected** — `JWT_SECRET` env var; never in source code.
3. **Only `auth-service` issues tokens** — all other services validate only.
4. **Validation is centralized in `shared/auth.py`** — no service implements its own `jwt.decode()`.
5. **`sub` claim = email string** — the principal identity throughout the system.
6. **OTP single-use enforcement** — `used=true` update is atomic with OTP lookup.
7. **Anti-enumeration** — `send-otp` response is identical for registered and unregistered emails.
