import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mailgun import send_otp
from app.models import OtpCode
from app.schemas import SendOtpRequest, SendOtpResponse, VerifyOtpRequest, VerifyOtpResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_db():
    """Placeholder — overridden in main.py via app.dependency_overrides."""
    raise NotImplementedError


async def _send_otp_handler(
    request: SendOtpRequest,
    db: AsyncSession = Depends(_get_db),
) -> SendOtpResponse:
    # Rate limit: count OTPs created for this email in the last hour
    one_hour_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    result = await db.execute(
        select(func.count()).where(
            OtpCode.email == request.email,
            OtpCode.created_at >= one_hour_ago,
        )
    )
    count = result.scalar_one()
    if count >= settings.OTP_RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait before requesting another code.",
        )

    # Generate 6-digit OTP with cryptographic randomness
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=settings.OTP_EXPIRY_MINUTES
    )

    otp = OtpCode(email=request.email, code=code, expires_at=expires_at)
    db.add(otp)
    await db.commit()

    # Send email — if this fails, return 503 to match Java behavior
    try:
        await send_otp(
            to_email=request.email,
            otp_code=code,
            api_key=settings.MAILGUN_API_KEY,
            domain=settings.MAILGUN_DOMAIN,
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Failed to send verification email. Please try again later.",
        )

    return SendOtpResponse(
        message="If this email is registered, a code has been sent."
    )


async def _verify_otp_handler(
    request: VerifyOtpRequest,
    db: AsyncSession = Depends(_get_db),
) -> VerifyOtpResponse:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Look up the most recent valid, unused, non-expired OTP for this email
    result = await db.execute(
        select(OtpCode)
        .where(
            OtpCode.email == request.email,
            OtpCode.code == request.code,
            OtpCode.used == False,  # noqa: E712
            OtpCode.expires_at > now,
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()

    if otp is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")

    # Mark OTP as used
    otp.used = True
    await db.commit()

    # Generate JWT — HMAC-HS256, sub=email, to match Java jjwt output
    expiry_seconds = settings.JWT_EXPIRATION_MS // 1000
    now_utc = datetime.now(timezone.utc)
    claims = {
        "sub": request.email,
        "iat": int(now_utc.timestamp()),
        "exp": int((now_utc + timedelta(seconds=expiry_seconds)).timestamp()),
    }
    token = jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")

    return VerifyOtpResponse(
        token=token,
        email=request.email,
        expiresIn=expiry_seconds,
    )


# Register route handlers — dependency injection wired in main.py
router.add_api_route(
    "/send-otp",
    _send_otp_handler,
    methods=["POST"],
    response_model=SendOtpResponse,
    summary="Send OTP to email address",
)
router.add_api_route(
    "/verify-otp",
    _verify_otp_handler,
    methods=["POST"],
    response_model=VerifyOtpResponse,
    summary="Verify OTP and receive JWT token",
)
