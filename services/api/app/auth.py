from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User
password_hash = PasswordHash.recommended()
bearer = HTTPBearer()
def hash_password(value: str): return password_hash.hash(value)
def verify_password(value: str, hashed: str): return password_hash.verify(value, hashed)
def token_for(user: User):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub":user.id,"org":user.organization_id,"role":user.role,"exp":exp}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
def current_user(credentials: HTTPAuthorizationCredentials=Depends(bearer), db: Session=Depends(get_db)) -> User:
    try: claims=jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user=db.get(User, claims.get("sub"))
    if not user or not user.is_active or user.organization_id != claims.get("org"): raise HTTPException(401,"Inactive or invalid account")
    return user
def require_owner(user: User=Depends(current_user)):
    if user.role != "owner": raise HTTPException(403,"Owner role required")
    return user

