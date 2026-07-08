from datetime import datetime, timedelta
from typing import Any
from passlib.context import CryptContext
from jose import jwt
from app.core.config import settings

# Enterprise-grade hashing algorithm (bcrypt handles salt generation internally)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the hashed database value."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generates a secure hash from plain text."""
    return pwd_context.hash(password)

def create_access_token(subject: str | Any, expires_delta: timedelta = None) -> str:
    """
    Constructs an ECDSA/RS256 JWT containing the Subject's Identity.
    'subject' usually represents the User ID (UUID string).
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        
    to_encode = {"exp": expire, "sub": str(subject)}
    
    # Sign token via high-entropy SECRET_KEY from the system memory
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt