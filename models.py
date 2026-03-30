import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Float,
    DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, relationship
from app.database import Base
import enum


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────
class MoodLevel(str, enum.Enum):
    great    = "great"
    good     = "good"
    okay     = "okay"
    low      = "low"
    awful    = "awful"

class AlertStatus(str, enum.Enum):
    pending  = "pending"
    sent     = "sent"
    failed   = "failed"

class MessageRole(str, enum.Enum):
    user      = "user"
    assistant = "assistant"
    system    = "system"


# ─────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email           = Column(String, unique=True, index=True, nullable=False)
    display_name    = Column(String(100), nullable=False)
    hashed_password = Column(String, nullable=True)        # null for social logins
    is_anonymous    = Column(Boolean, default=True)
    is_active       = Column(Boolean, default=True)
    is_verified     = Column(Boolean, default=False)
    oauth_provider  = Column(String(20), nullable=True)    # "google" | "apple" | None
    oauth_id        = Column(String, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    last_login      = Column(DateTime, nullable=True)

    # Relationships
    mood_logs        = relationship("MoodLog",       back_populates="user", cascade="all, delete-orphan")
    chat_sessions    = relationship("ChatSession",   back_populates="user", cascade="all, delete-orphan")
    trusted_contacts = relationship("TrustedContact",back_populates="user", cascade="all, delete-orphan")
    crisis_alerts    = relationship("CrisisAlert",   back_populates="user", cascade="all, delete-orphan")
    therapist_bookings = relationship("TherapistBooking", back_populates="user", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# MOOD LOG
# ─────────────────────────────────────────────
class MoodLog(Base):
    __tablename__ = "mood_logs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    mood       = Column(SAEnum(MoodLevel), nullable=False)
    score      = Column(Integer, nullable=False)           # 1–10
    note       = Column(Text, nullable=True)
    tags       = Column(String, nullable=True)             # comma-separated
    ai_insight = Column(Text, nullable=True)               # AI-generated insight
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="mood_logs")


# ─────────────────────────────────────────────
# CHAT SESSION & MESSAGES
# ─────────────────────────────────────────────
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title      = Column(String(200), default="Support Session")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user     = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id   = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role         = Column(SAEnum(MessageRole), nullable=False)
    content      = Column(Text, nullable=False)
    detected_mood= Column(String(50), nullable=True)
    crisis_flag  = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# ─────────────────────────────────────────────
# TRUSTED CONTACTS
# ─────────────────────────────────────────────
class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name         = Column(String(100), nullable=False)
    relation_type = Column(String(50), nullable=True)      # "Family" | "Friend" | "Therapist"
    email        = Column(String, nullable=True)
    phone        = Column(String(20), nullable=True)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    user   = relationship("User", back_populates="trusted_contacts")
    alerts = relationship("CrisisAlert", back_populates="contact", cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# CRISIS ALERTS
# ─────────────────────────────────────────────
class CrisisAlert(Base):
    __tablename__ = "crisis_alerts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    contact_id   = Column(UUID(as_uuid=True), ForeignKey("trusted_contacts.id"), nullable=True)
    trigger_text = Column(Text, nullable=True)             # message that triggered crisis
    status       = Column(SAEnum(AlertStatus), default=AlertStatus.pending)
    sent_at      = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    user    = relationship("User", back_populates="crisis_alerts")
    contact = relationship("TrustedContact", back_populates="alerts")


# ─────────────────────────────────────────────
# THERAPISTS
# ─────────────────────────────────────────────
class Therapist(Base):
    __tablename__ = "therapists"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name         = Column(String(100), nullable=False)
    specialization = Column(String(200), nullable=False)
    languages    = Column(String, nullable=True)           # comma-separated
    approaches   = Column(String, nullable=True)           # "CBT,DBT,EMDR"
    rating       = Column(Float, default=4.5)
    review_count = Column(Integer, default=0)
    availability = Column(String(20), default="online")    # online | busy | offline
    avatar_emoji = Column(String(10), default="🩺")
    bio          = Column(Text, nullable=True)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)

    bookings = relationship("TherapistBooking", back_populates="therapist")


class TherapistBooking(Base):
    __tablename__ = "therapist_bookings"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    therapist_id  = Column(UUID(as_uuid=True), ForeignKey("therapists.id"), nullable=False)
    scheduled_at  = Column(DateTime, nullable=False)
    status        = Column(String(20), default="pending")  # pending | confirmed | cancelled
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    user      = relationship("User", back_populates="therapist_bookings")
    therapist = relationship("Therapist", back_populates="bookings")
