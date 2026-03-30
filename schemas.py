from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.models import MoodLevel, AlertStatus, MessageRole


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────
class RegisterRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    anonymous: bool = True

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


# ─────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────
class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_anonymous: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    is_anonymous: Optional[bool] = None


# ─────────────────────────────────────────────
# MOOD
# ─────────────────────────────────────────────
class MoodLogCreate(BaseModel):
    mood: MoodLevel
    score: int = Field(..., ge=1, le=10)
    note: Optional[str] = None
    tags: Optional[List[str]] = []


class MoodLogResponse(BaseModel):
    id: UUID
    mood: MoodLevel
    score: int
    note: Optional[str]
    tags: Optional[str]
    ai_insight: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MoodAnalyticsResponse(BaseModel):
    average_score: float
    streak_days: int
    total_entries: int
    best_day: Optional[str]
    worst_day: Optional[str]
    weekly_data: List[dict]
    ai_insight: str


# ─────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────
class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[UUID] = None


class ChatMessageResponse(BaseModel):
    id: UUID
    role: MessageRole
    content: str
    detected_mood: Optional[str]
    crisis_flag: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    session_id: UUID
    reply: str
    detected_mood: Optional[str]
    crisis_detected: bool
    message_id: UUID


class ChatSessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# TRUSTED CONTACTS
# ─────────────────────────────────────────────
class TrustedContactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    relationship: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class TrustedContactResponse(BaseModel):
    id: UUID
    name: str
    relation_type: Optional[str] = None   # DB field name
    relationship: Optional[str] = None    # ✅ Frontend expects this
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def sync_relationship(self):
        # ✅ relation_type → relationship auto sync
        if self.relationship is None and self.relation_type is not None:
            self.relationship = self.relation_type
        elif self.relation_type is None and self.relationship is not None:
            self.relation_type = self.relationship
        return self


# ─────────────────────────────────────────────
# CRISIS ALERTS
# ─────────────────────────────────────────────
class CrisisAlertCreate(BaseModel):
    contact_id: UUID
    trigger_text: Optional[str] = None


class CrisisAlertResponse(BaseModel):
    id: UUID
    status: AlertStatus
    sent_at: Optional[datetime]
    created_at: datetime
    contact_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# THERAPISTS
# ─────────────────────────────────────────────
class TherapistResponse(BaseModel):
    id: UUID
    name: str
    specialization: str
    languages: Optional[str]
    approaches: Optional[str]
    rating: float
    review_count: int
    availability: str
    avatar_emoji: str
    bio: Optional[str]

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    therapist_id: UUID
    scheduled_at: datetime
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    id: UUID
    therapist_id: UUID
    scheduled_at: datetime
    status: str
    notes: Optional[str]
    created_at: datetime
    therapist_name: Optional[str] = None

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────
# GENERIC
# ─────────────────────────────────────────────
class SuccessResponse(BaseModel):
    message: str
    success: bool = True


# Fix forward reference
TokenResponse.model_rebuild()