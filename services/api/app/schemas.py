from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    organization_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    organization_id: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: str = "staff"


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class SettingsIn(BaseModel):
    low_stock_threshold: float = Field(ge=0, le=100000)
    overstock_days: int = Field(ge=7, le=365)
    digest_enabled: bool


class ForecastOut(BaseModel):
    sku: str
    horizon_days: int
    model_name: str
    mae: float
    rmse: float
    confidence: str
    status: str
    predictions: list[dict]


class ChatIn(BaseModel):
    question: str = Field(min_length=3, max_length=800)


class ChatOut(BaseModel):
    answer: str
    rows: list[dict]
    query_summary: str
    source_context: list[str] = Field(default_factory=list)
    rejected: bool = False
