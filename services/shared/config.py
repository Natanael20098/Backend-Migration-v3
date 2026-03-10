from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    JWT_SECRET: str = ""
    JWT_EXPIRATION_MS: int = 86400000
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"
