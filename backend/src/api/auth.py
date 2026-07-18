import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from backend.src.db.session import get_db
from backend.src.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "supersecretkey_change_in_production")
ALGORITHM = "HS256"
security = HTTPBearer()

# In-memory storage for magic link tokens: token -> email
MAGIC_TOKENS: Dict[str, str] = {}

class MagicLinkRequest(BaseModel):
    email: str

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
        
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

@router.post("/magic-link", status_code=status.HTTP_202_ACCEPTED)
def send_magic_link(request: MagicLinkRequest):
    token = str(uuid.uuid4())
    MAGIC_TOKENS[token] = request.email
    
    # Print the verification URL to the server console log
    verification_url = f"http://localhost:8000/auth/verify?token={token}"
    logging.info(f"=== MAGIC LINK GENERATED FOR {request.email} ===")
    logging.info(verification_url)
    logging.info("==============================================")
    print(f"\n=== MAGIC LINK GENERATED FOR {request.email} ===\n{verification_url}\n==============================================\n")
    
    return {"message": "Magic link sent"}

@router.get("/verify")
def verify_magic_link(token: str, db: Session = Depends(get_db)):
    if token not in MAGIC_TOKENS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link token"
        )
        
    email = MAGIC_TOKENS.pop(token)  # consume the token
    
    # Get or create user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(id=uuid.uuid4(), email=email, role="owner")
        db.add(user)
        db.commit()
        db.refresh(user)
        
    access_token = create_access_token(data={
        "sub": user.email,
        "role": user.role,
        "user_id": str(user.id)
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role
        }
    }
