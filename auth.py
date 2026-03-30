from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import jwt
import bcrypt
import secrets

from app.database import get_db
from app.models.models import User
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])
security = HTTPBearer(auto_error=False)


# ── Schemas ──────────────────────────────────────
class RegisterRequest(BaseModel):
    display_name: str
    email: str
    password: str
    anonymous: bool = True


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Helpers ──────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_token(user_id: str, expires_minutes: int = None) -> str:
    exp = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=exp),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = decode_token(credentials.credentials)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Routes ───────────────────────────────────────
@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check email exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        display_name=request.display_name,
        email=request.email,
        hashed_password=hash_password(request.password),
        is_anonymous=request.anonymous,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "is_anonymous": user.is_anonymous,
        }
    }


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "is_anonymous": user.is_anonymous,
        }
    }


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    # JWT is stateless — client deletes token
    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Send password reset link to email.
    Always returns 200 to avoid email enumeration — but logs if not found.
    """
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        # ✅ Return 200 anyway (security best practice — don't reveal if email exists)
        # Frontend will show "reset link sent" regardless
        return {"message": "If this email exists, a reset link has been sent"}

    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    user.reset_token = reset_token
    user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    # Send email
    try:
        from app.services.email_service import EmailService
        email_service = EmailService()
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        await email_service.send_password_reset(
            to_email=user.email,
            display_name=user.display_name,
            reset_url=reset_url
        )
    except Exception as e:
        # Email failed but token saved — log and continue
        print(f"[WARN] Password reset email failed for {user.email}: {e}")

    return {"message": "If this email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == request.token).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if user.reset_token_expiry and user.reset_token_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user.hashed_password = hash_password(request.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return {"message": "Password reset successfully"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "is_anonymous": current_user.is_anonymous,
    }
