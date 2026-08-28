from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./retail.db"
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    resend_api_key: str | None = None
    resend_from: str = "onboarding@resend.dev"
    frontend_origin: str = "http://localhost:3000"

settings = Settings()

