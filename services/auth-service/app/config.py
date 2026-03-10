from shared.config import Settings as BaseSettings


class Settings(BaseSettings):
    MAILGUN_API_KEY: str = ""
    MAILGUN_DOMAIN: str = "mg.tallerlabs.ai"
    OTP_EXPIRY_MINUTES: int = 10
    OTP_RATE_LIMIT_PER_HOUR: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
