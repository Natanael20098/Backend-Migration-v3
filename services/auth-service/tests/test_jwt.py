"""
JWT unit tests for auth-service.

Covers:
  - Encode/decode round trip
  - Expired token → HTTP 401
  - Invalid signature → HTTP 401
  - Wrong algorithm → HTTP 401
  - Missing sub claim → HTTP 401
  - Algorithm is not input-driven (policy enforcement)

Run: cd services/auth-service && pytest
PYTHONPATH is set to `services/` via pytest.ini so `shared.auth` is importable.
"""
import inspect
import time

import jwt
import pytest
from fastapi import HTTPException

from shared.auth import verify_jwt

SECRET = "test-secret-at-least-32-chars-long-xx"
EMAIL = "user@example.com"


def _make_token(payload: dict, secret: str = SECRET, algorithm: str = "HS256") -> str:
    return jwt.encode(payload, secret, algorithm=algorithm)


def _valid_claims(offset_seconds: int = 3600) -> dict:
    now = int(time.time())
    return {
        "sub": EMAIL,
        "iat": now,
        "exp": now + offset_seconds,
    }


# ---------------------------------------------------------------------------
# 1. Encode / decode round trip
# ---------------------------------------------------------------------------

def test_encode_decode_round_trip():
    token = _make_token(_valid_claims())
    subject = verify_jwt(token, SECRET)
    assert subject == EMAIL


# ---------------------------------------------------------------------------
# 2. Expired token → HTTP 401
# ---------------------------------------------------------------------------

def test_expired_token_raises_401():
    claims = _valid_claims(offset_seconds=-1)  # exp already in the past
    token = _make_token(claims)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(token, SECRET)
    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 3. Invalid signature → HTTP 401
# ---------------------------------------------------------------------------

def test_invalid_signature_raises_401():
    token = _make_token(_valid_claims())
    # Tamper with the signature portion of the token
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + ".invalidsignatureXXX"
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(tampered, SECRET)
    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 4. Wrong algorithm → HTTP 401
# ---------------------------------------------------------------------------

def test_wrong_algorithm_rejected():
    # Encode with HS384 — verify_jwt only accepts HS256
    token = _make_token(_valid_claims(), algorithm="HS384")
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(token, SECRET)
    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 5. Missing sub claim → HTTP 401
# ---------------------------------------------------------------------------

def test_missing_sub_raises_401():
    now = int(time.time())
    claims = {"iat": now, "exp": now + 3600}  # no "sub"
    token = _make_token(claims)
    with pytest.raises(HTTPException) as exc_info:
        verify_jwt(token, SECRET)
    assert exc_info.value.status_code == 401
    assert "Invalid or expired token" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 6. Algorithm is not input-driven (policy enforcement)
# ---------------------------------------------------------------------------

def test_algorithm_is_not_input_driven():
    """
    verify_jwt must not accept an `algorithm` parameter.
    The algorithm (HS256) is hardcoded inside the function — it is never
    read from the token header, request input, or caller arguments.
    """
    sig = inspect.signature(verify_jwt)
    assert "algorithm" not in sig.parameters, (
        "verify_jwt must not expose an `algorithm` parameter — "
        "the algorithm must be hardcoded per the JWT validation policy."
    )
