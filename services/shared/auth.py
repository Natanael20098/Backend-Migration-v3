import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer()


def verify_jwt(token: str, secret: str) -> str:
    """
    Validate a JWT token and return the subject (email).
    Uses HMAC-HS256 — algorithm is hardcoded and never read from input.
    See doc/jwt-validation-policy.md for the full validation policy.
    Raises HTTP 401 on any validation failure.
    """
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        subject: str = payload.get("sub")
        if subject is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return subject
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def make_get_current_user(secret: str):
    """
    Factory that creates a FastAPI dependency for validating Bearer tokens.
    Each service calls this with its configured JWT_SECRET.
    Returns the email (subject) from the token.
    """
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    ) -> str:
        return verify_jwt(credentials.credentials, secret)

    return get_current_user
