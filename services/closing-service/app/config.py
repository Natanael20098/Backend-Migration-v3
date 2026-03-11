from shared.config import Settings as BaseSettings


class Settings(BaseSettings):
    """
    Configuration for the closing-service.
    Inherits DATABASE_URL, JWT_SECRET, JWT_EXPIRATION_MS, FRONTEND_URL from shared.config.
    No additional service-specific settings required.
    """
    pass


settings = Settings()
