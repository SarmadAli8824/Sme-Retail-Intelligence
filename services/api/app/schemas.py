from datetime import date
from pydantic import BaseModel, EmailStr, Field
class RegisterIn(BaseModel): organization_name: str=Field(min_length=2,max_length=160); email: EmailStr; password: str=Field(min_length=12,max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class TokenOut(BaseModel): access_token: str; token_type: str="bearer"; role: str; organization_id: str
class UserCreate(BaseModel): email: EmailStr; password: str=Field(min_length=12); role: str="staff"
class ForecastOut(BaseModel): sku: str; horizon_days: int; model_name: str; mae: float; rmse: float; predictions: list[dict]
class ChatIn(BaseModel): question: str=Field(min_length=3,max_length=800)
class ChatOut(BaseModel): answer: str; rows: list[dict]; query_summary: str; rejected: bool=False

