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
    max_upload_bytes: int = 5_000_000
    query_timeout_ms: int = 2_000
    seed_demo_data: bool = False
    demo_owner_email: str = "owner@demo.example"
    demo_owner_password: str = "RetailDemo123!"

settings = Settings()
