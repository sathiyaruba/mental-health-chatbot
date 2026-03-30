from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models.models import (
    User, MoodLog, ChatSession, ChatMessage,
    TrustedContact, CrisisAlert, Therapist, TherapistBooking,
    AlertStatus, MoodLevel
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# ── Simple token-based admin guard ──────────────
ADMIN_TOKEN = "solace-admin-2024"

def verify_admin(token: str = Query(..., alias="token")):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return True


# ── DASHBOARD STATS ─────────────────────────────
@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _=Depends(verify_admin)):
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    total_users      = db.query(func.count(User.id)).scalar() or 0
    new_today        = db.query(func.count(User.id)).filter(User.created_at >= today_start).scalar() or 0
    anon_users       = db.query(func.count(User.id)).filter(User.is_anonymous == True).scalar() or 0
    active_sessions  = db.query(func.count(ChatSession.id)).filter(ChatSession.created_at >= today_start).scalar() or 0
    total_messages   = db.query(func.count(ChatMessage.id)).filter(ChatMessage.created_at >= today_start).scalar() or 0
    crisis_today     = db.query(func.count(CrisisAlert.id)).filter(CrisisAlert.created_at >= today_start).scalar() or 0
    crisis_active    = db.query(func.count(CrisisAlert.id)).filter(
        CrisisAlert.status == AlertStatus.pending,
        CrisisAlert.created_at >= today_start
    ).scalar() or 0
    bookings_today   = db.query(func.count(TherapistBooking.id)).filter(TherapistBooking.created_at >= today_start).scalar() or 0
    total_mood_logs  = db.query(func.count(MoodLog.id)).scalar() or 0

    avg_mood_row = db.query(func.avg(MoodLog.score)).filter(MoodLog.created_at >= datetime.utcnow() - timedelta(days=7)).scalar()
    avg_mood = round(float(avg_mood_row), 1) if avg_mood_row else 0.0

    anon_pct = round((anon_users / total_users * 100)) if total_users else 0

    return {
        "total_users":     total_users,
        "new_today":       new_today,
        "anon_users":      anon_users,
        "anon_pct":        anon_pct,
        "active_sessions": active_sessions,
        "total_messages":  total_messages,
        "crisis_today":    crisis_today,
        "crisis_active":   crisis_active,
        "bookings_today":  bookings_today,
        "total_mood_logs": total_mood_logs,
        "avg_mood":        avg_mood,
    }


# ── CHART DATA (last 15 days) ───────────────────
@router.get("/charts")
def get_charts(db: Session = Depends(get_db), _=Depends(verify_admin)):
    days = 15
    result = {"users": [], "crisis": [], "mood": [], "labels": []}

    for i in range(days - 1, -1, -1):
        day = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(day, datetime.min.time())
        day_end   = datetime.combine(day, datetime.max.time())

        users_count = db.query(func.count(User.id)).filter(
            User.created_at <= day_end
        ).scalar() or 0

        crisis_count = db.query(func.count(CrisisAlert.id)).filter(
            CrisisAlert.created_at >= day_start,
            CrisisAlert.created_at <= day_end
        ).scalar() or 0

        mood_avg = db.query(func.avg(MoodLog.score)).filter(
            MoodLog.created_at >= day_start,
            MoodLog.created_at <= day_end
        ).scalar()
        mood_val = round(float(mood_avg), 1) if mood_avg else 0

        result["users"].append(users_count)
        result["crisis"].append(crisis_count)
        result["mood"].append(mood_val)
        result["labels"].append(day.strftime("%d %b"))

    return result


# ── USERS ───────────────────────────────────────
@router.get("/users")
def get_users(
    search: str = "",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(verify_admin)
):
    q = db.query(User)
    if search:
        q = q.filter(
            User.display_name.ilike(f"%{search}%") |
            User.email.ilike(f"%{search}%")
        )
    users = q.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
    total = q.count()

    result = []
    for u in users:
        mood_avg = db.query(func.avg(MoodLog.score)).filter(MoodLog.user_id == u.id).scalar()
        session_count = db.query(func.count(ChatSession.id)).filter(ChatSession.user_id == u.id).scalar() or 0
        has_crisis = db.query(func.count(CrisisAlert.id)).filter(CrisisAlert.user_id == u.id).scalar() or 0

        result.append({
            "id":           str(u.id),
            "display_name": u.display_name,
            "email":        u.email,
            "is_anonymous": u.is_anonymous,
            "is_active":    u.is_active,
            "is_verified":  u.is_verified,
            "oauth_provider": u.oauth_provider,
            "created_at":   u.created_at.isoformat() if u.created_at else None,
            "last_login":   u.last_login.isoformat() if u.last_login else None,
            "mood_avg":     round(float(mood_avg), 1) if mood_avg else None,
            "session_count": session_count,
            "has_crisis":   has_crisis > 0,
        })

    return {"users": result, "total": total}


# ── USER DETAIL ─────────────────────────────────
@router.get("/users/{user_id}")
def get_user_detail(user_id: str, db: Session = Depends(get_db), _=Depends(verify_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "User not found")

    mood_logs = db.query(MoodLog).filter(MoodLog.user_id == u.id).order_by(desc(MoodLog.created_at)).limit(10).all()
    sessions  = db.query(ChatSession).filter(ChatSession.user_id == u.id).order_by(desc(ChatSession.created_at)).limit(5).all()
    alerts    = db.query(CrisisAlert).filter(CrisisAlert.user_id == u.id).order_by(desc(CrisisAlert.created_at)).limit(5).all()

    return {
        "id":           str(u.id),
        "display_name": u.display_name,
        "email":        u.email,
        "is_anonymous": u.is_anonymous,
        "is_active":    u.is_active,
        "is_verified":  u.is_verified,
        "oauth_provider": u.oauth_provider,
        "created_at":   u.created_at.isoformat() if u.created_at else None,
        "last_login":   u.last_login.isoformat() if u.last_login else None,
        "mood_logs": [{
            "mood": m.mood.value, "score": m.score,
            "note": m.note, "created_at": m.created_at.isoformat()
        } for m in mood_logs],
        "sessions": [{
            "id": str(s.id), "title": s.title,
            "created_at": s.created_at.isoformat()
        } for s in sessions],
        "crisis_alerts": [{
            "status": a.status.value, "trigger_text": a.trigger_text,
            "created_at": a.created_at.isoformat()
        } for a in alerts],
    }


# ── DEACTIVATE USER ─────────────────────────────
@router.patch("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, db: Session = Depends(get_db), _=Depends(verify_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(404, "User not found")
    u.is_active = False
    db.commit()
    return {"message": f"User {u.display_name} deactivated"}


# ── CRISIS ALERTS ───────────────────────────────
@router.get("/crisis")
def get_crisis(db: Session = Depends(get_db), _=Depends(verify_admin)):
    # Active (pending) crisis alerts
    active = db.query(CrisisAlert).filter(
        CrisisAlert.status == AlertStatus.pending
    ).order_by(desc(CrisisAlert.created_at)).all()

    # History (last 30)
    history = db.query(CrisisAlert).order_by(desc(CrisisAlert.created_at)).limit(30).all()

    def fmt(a):
        u = db.query(User).filter(User.id == a.user_id).first()
        c = db.query(TrustedContact).filter(TrustedContact.id == a.contact_id).first() if a.contact_id else None
        return {
            "id":           str(a.id),
            "user_id":      str(a.user_id),
            "user_name":    u.display_name if u else "Unknown",
            "user_email":   u.email if u else "",
            "trigger_text": a.trigger_text,
            "status":       a.status.value,
            "contact_name": c.name if c else None,
            "sent_at":      a.sent_at.isoformat() if a.sent_at else None,
            "created_at":   a.created_at.isoformat(),
        }

    return {
        "active":  [fmt(a) for a in active],
        "history": [fmt(a) for a in history],
    }


# ── RESOLVE CRISIS ──────────────────────────────
@router.patch("/crisis/{alert_id}/resolve")
def resolve_crisis(alert_id: str, db: Session = Depends(get_db), _=Depends(verify_admin)):
    alert = db.query(CrisisAlert).filter(CrisisAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status = AlertStatus.sent
    db.commit()
    return {"message": "Crisis marked as resolved"}


# ── CHAT SESSIONS ───────────────────────────────
@router.get("/chats")
def get_chats(
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(verify_admin)
):
    sessions = db.query(ChatSession).order_by(desc(ChatSession.updated_at)).limit(limit).all()
    result = []
    for s in sessions:
        u = db.query(User).filter(User.id == s.user_id).first()
        msg_count = db.query(func.count(ChatMessage.id)).filter(ChatMessage.session_id == s.id).scalar() or 0
        crisis_count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.session_id == s.id,
            ChatMessage.crisis_flag == True
        ).scalar() or 0
        result.append({
            "id":           str(s.id),
            "user_name":    u.display_name if u else "Unknown",
            "user_id":      str(s.user_id),
            "title":        s.title,
            "msg_count":    msg_count,
            "crisis_flag":  crisis_count > 0,
            "created_at":   s.created_at.isoformat(),
            "updated_at":   s.updated_at.isoformat() if s.updated_at else s.created_at.isoformat(),
        })
    return {"sessions": result}


# ── MOOD ANALYTICS ──────────────────────────────
@router.get("/mood")
def get_mood_analytics(
    days: int = 30,
    db: Session = Depends(get_db),
    _=Depends(verify_admin)
):
    since = datetime.utcnow() - timedelta(days=days)
    logs = db.query(MoodLog).filter(MoodLog.created_at >= since).order_by(desc(MoodLog.created_at)).all()

    total = len(logs)
    avg   = round(sum(l.score for l in logs) / total, 1) if total else 0
    crisis_logs = [l for l in logs if l.score <= 2]

    # Mood distribution
    from collections import Counter
    mood_dist = Counter(l.mood.value for l in logs)

    # Tag frequency
    all_tags = []
    for l in logs:
        if l.tags:
            all_tags.extend([t.strip() for t in l.tags.split(",") if t.strip()])
    tag_freq = Counter(all_tags).most_common(10)

    # Recent logs with user info
    recent = []
    for l in logs[:50]:
        u = db.query(User).filter(User.id == l.user_id).first()
        recent.append({
            "id":         str(l.id),
            "user_name":  u.display_name if u else "Unknown",
            "user_id":    str(l.user_id),
            "mood":       l.mood.value,
            "score":      l.score,
            "note":       l.note,
            "tags":       l.tags,
            "created_at": l.created_at.isoformat(),
        })

    return {
        "total":       total,
        "avg_score":   avg,
        "crisis_count": len(crisis_logs),
        "mood_dist":   dict(mood_dist),
        "top_tags":    [{"tag": t, "count": c} for t, c in tag_freq],
        "recent_logs": recent,
    }


# ── THERAPISTS ──────────────────────────────────
@router.get("/therapists")
def get_therapists(db: Session = Depends(get_db), _=Depends(verify_admin)):
    therapists = db.query(Therapist).filter(Therapist.is_active == True).order_by(desc(Therapist.rating)).all()
    result = []
    for t in therapists:
        booking_count = db.query(func.count(TherapistBooking.id)).filter(TherapistBooking.therapist_id == t.id).scalar() or 0
        result.append({
            "id":             str(t.id),
            "name":           t.name,
            "specialization": t.specialization,
            "languages":      t.languages,
            "approaches":     t.approaches,
            "rating":         t.rating,
            "review_count":   t.review_count,
            "availability":   t.availability,
            "avatar_emoji":   t.avatar_emoji,
            "bio":            t.bio,
            "booking_count":  booking_count,
        })
    return {"therapists": result}


# ── ADD THERAPIST ───────────────────────────────
@router.post("/therapists")
def add_therapist(
    name: str, specialization: str,
    languages: str = "", approaches: str = "",
    bio: str = "", availability: str = "online",
    db: Session = Depends(get_db), _=Depends(verify_admin)
):
    t = Therapist(
        name=name, specialization=specialization,
        languages=languages, approaches=approaches,
        bio=bio, availability=availability,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"message": "Therapist added", "id": str(t.id)}


# ── BOOKINGS ────────────────────────────────────
@router.get("/bookings")
def get_bookings(db: Session = Depends(get_db), _=Depends(verify_admin)):
    bookings = db.query(TherapistBooking).order_by(desc(TherapistBooking.created_at)).all()
    result = []
    for b in bookings:
        u = db.query(User).filter(User.id == b.user_id).first()
        t = db.query(Therapist).filter(Therapist.id == b.therapist_id).first()
        result.append({
            "id":            str(b.id),
            "user_name":     u.display_name if u else "Unknown",
            "user_id":       str(b.user_id),
            "therapist_name": t.name if t else "Unknown",
            "scheduled_at":  b.scheduled_at.isoformat(),
            "status":        b.status,
            "notes":         b.notes,
            "created_at":    b.created_at.isoformat(),
        })

    confirmed = sum(1 for b in result if b["status"] == "confirmed")
    pending   = sum(1 for b in result if b["status"] == "pending")
    cancelled = sum(1 for b in result if b["status"] == "cancelled")

    return {
        "bookings": result,
        "stats": {"confirmed": confirmed, "pending": pending, "cancelled": cancelled, "total": len(result)}
    }


# ── UPDATE BOOKING STATUS ───────────────────────
@router.patch("/bookings/{booking_id}")
def update_booking(
    booking_id: str, status: str,
    db: Session = Depends(get_db), _=Depends(verify_admin)
):
    b = db.query(TherapistBooking).filter(TherapistBooking.id == booking_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    b.status = status
    db.commit()
    return {"message": f"Booking status updated to {status}"}


# ── ACTIVITY FEED ───────────────────────────────
@router.get("/activity")
def get_activity(db: Session = Depends(get_db), _=Depends(verify_admin)):
    events = []

    # Recent crisis alerts
    alerts = db.query(CrisisAlert).order_by(desc(CrisisAlert.created_at)).limit(5).all()
    for a in alerts:
        u = db.query(User).filter(User.id == a.user_id).first()
        events.append({
            "type": "crisis", "color": "red",
            "text": f"🚨 Crisis detected — {u.display_name if u else 'Unknown'}",
            "time": a.created_at.isoformat()
        })

    # Recent signups
    users = db.query(User).order_by(desc(User.created_at)).limit(5).all()
    for u in users:
        events.append({
            "type": "signup", "color": "blue",
            "text": f"👤 New signup — {u.display_name} ({'Anonymous' if u.is_anonymous else 'Named'})",
            "time": u.created_at.isoformat()
        })

    # Recent bookings
    bookings = db.query(TherapistBooking).order_by(desc(TherapistBooking.created_at)).limit(5).all()
    for b in bookings:
        u = db.query(User).filter(User.id == b.user_id).first()
        t = db.query(Therapist).filter(Therapist.id == b.therapist_id).first()
        events.append({
            "type": "booking", "color": "green",
            "text": f"📅 Booking — {u.display_name if u else '?'} with {t.name if t else '?'} ({b.status})",
            "time": b.created_at.isoformat()
        })

    # Sort by time descending
    events.sort(key=lambda x: x["time"], reverse=True)
    return {"events": events[:20]}