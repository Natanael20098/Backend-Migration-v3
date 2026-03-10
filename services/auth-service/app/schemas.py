from pydantic import BaseModel, ConfigDict, EmailStr


class SendOtpRequest(BaseModel):
    email: EmailStr


class SendOtpResponse(BaseModel):
    message: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyOtpResponse(BaseModel):
    """
    camelCase field names match the Java AuthController response exactly.
    The frontend reads token, email, and expiresIn from this response.
    """
    model_config = ConfigDict(populate_by_name=True)

    token: str
    email: str
    expiresIn: int
