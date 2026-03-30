from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, MoodLog
from app.schemas.schemas import MoodLogCreate, MoodLogResponse, MoodAnalyticsResponse
from app.services.auth_service import get_current_active_user
from app.services.ai_service import generate_mood_insight

router = APIRouter(prefix="/api/mood", tags=["Mood Tracker"])


# ─── Log Mood ───────────────────────────────
@router.post("/log", response_model=MoodLogResponse, status_code=201)
async def log_mood(
    body: MoodLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    log = MoodLog(
        user_id = current_user.id,
        mood    = body.mood,
        score   = body.score,
        note    = body.note,
        tags    = ",".join(body.tags) if body.tags else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return MoodLogResponse.model_validate(log)


# ─── Get Recent Logs ────────────────────────
@router.get("/logs", response_model=list[MoodLogResponse])
def get_logs(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(MoodLog)
        .filter(MoodLog.user_id == current_user.id, MoodLog.created_at >= since)
        .order_by(MoodLog.created_at.desc())
        .all()
    )
    return [MoodLogResponse.model_validate(l) for l in logs]


# ─── Analytics ──────────────────────────────
@router.get("/analytics", response_model=MoodAnalyticsResponse)
async def get_analytics(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(MoodLog)
        .filter(MoodLog.user_id == current_user.id, MoodLog.created_at >= since)
        .order_by(MoodLog.created_at.asc())
        .all()
    )

    if not logs:
        return MoodAnalyticsResponse(
            average_score = 0,
            streak_days   = 0,
            total_entries = 0,
            best_day      = None,
            worst_day     = None,
            weekly_data   = [],
            ai_insight    = "Start logging your mood daily to see insights here! 💙",
        )

    scores   = [l.score for l in logs]
    avg      = round(sum(scores) / len(scores), 1)
    best_log = max(logs, key=lambda l: l.score)
    worst_log= min(logs, key=lambda l: l.score)

    # Streak calculation
    streak = _calculate_streak(current_user.id, db)

    # Build weekly bar data
    weekly_data = _build_weekly_data(logs)

    # AI insight from last 14 days
    history_for_ai = [
        {
            "date":  l.created_at.strftime("%a %b %d"),
            "mood":  l.mood.value,
            "score": l.score,
            "note":  l.note or "",
        }
        for l in logs[-14:]
    ]
    ai_insight = await generate_mood_insight(history_for_ai)

    return MoodAnalyticsResponse(
        average_score = avg,
        streak_days   = streak,
        total_entries = len(logs),
        best_day      = best_log.created_at.strftime("%A"),
        worst_day     = worst_log.created_at.strftime("%A"),
        weekly_data   = weekly_data,
        ai_insight    = ai_insight,
    )


def _calculate_streak(user_id, db: Session) -> int:
    """Count consecutive days with at least one mood log."""
    today = datetime.utcnow().date()
    streak = 0
    check_date = today

    while True:
        start = datetime.combine(check_date, datetime.min.time())
        end   = datetime.combine(check_date, datetime.max.time())
        count = db.query(MoodLog).filter(
            MoodLog.user_id  == user_id,
            MoodLog.created_at >= start,
            MoodLog.created_at <= end,
        ).count()
        if count == 0:
            break
        streak    += 1
        check_date = check_date - timedelta(days=1)

    return streak


def _build_weekly_data(logs: list) -> list[dict]:
    """Group logs by day-of-week, average scores."""
    from collections import defaultdict
    day_scores = defaultdict(list)
    for l in logs:
        day = l.created_at.strftime("%a")
        day_scores[day].append(l.score)

    days_order = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    return [
        {
            "day":   d,
            "score": round(sum(day_scores[d]) / len(day_scores[d]), 1) if day_scores[d] else 0,
            "count": len(day_scores[d]),
        }
        for d in days_order
    ]


# ─── Delete a log entry ─────────────────────
@router.delete("/log/{log_id}")
def delete_log(
    log_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    log = db.query(MoodLog).filter(
        MoodLog.id      == log_id,
        MoodLog.user_id == current_user.id
    ).first()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    db.delete(log)
    db.commit()
    return {"message": "Deleted"}
