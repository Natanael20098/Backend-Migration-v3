import httpx


async def send_otp(
    to_email: str,
    otp_code: str,
    api_key: str,
    domain: str,
) -> None:
    """
    Send an OTP verification email via the Mailgun API.
    Matches the behavior of the Java MailgunService.
    Raises an exception if the Mailgun API returns a non-2xx response.
    """
    url = f"https://api.mailgun.net/v3/{domain}/messages"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            auth=("api", api_key),
            data={
                "from": f"HomeLend Pro <noreply@{domain}>",
                "to": [to_email],
                "subject": "Your HomeLend Pro Verification Code",
                "text": (
                    f"Your verification code is: {otp_code}\n\n"
                    f"This code expires in 10 minutes.\n\n"
                    f"If you did not request this code, please ignore this email."
                ),
                "html": (
                    f"<p>Your verification code is: <strong>{otp_code}</strong></p>"
                    f"<p>This code expires in 10 minutes.</p>"
                    f"<p>If you did not request this code, please ignore this email.</p>"
                ),
            },
            timeout=10.0,
        )
        response.raise_for_status()
