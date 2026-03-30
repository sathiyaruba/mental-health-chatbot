from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, Therapist, TherapistBooking
from app.schemas.schemas import TherapistResponse, BookingCreate, BookingResponse, SuccessResponse
from app.services.auth_service import get_current_active_user

router = APIRouter(prefix="/api/therapists", tags=["Therapists"])


# ─── List Therapists ────────────────────────
@router.get("/", response_model=list[TherapistResponse])
def list_therapists(
    language: str | None   = Query(None, description="Filter by language, e.g. Tamil"),
    approach: str | None   = Query(None, description="Filter by approach, e.g. CBT"),
    availability: str | None = Query(None, description="online | busy | offline"),
    db: Session = Depends(get_db),
):
    query = db.query(Therapist).filter(Therapist.is_active == True)

    if language:
        query = query.filter(Therapist.languages.ilike(f"%{language}%"))
    if approach:
        query = query.filter(Therapist.approaches.ilike(f"%{approach}%"))
    if availability:
        query = query.filter(Therapist.availability == availability)

    therapists = query.order_by(Therapist.rating.desc()).all()
    return [TherapistResponse.model_validate(t) for t in therapists]


# ─── Get Single Therapist ───────────────────
@router.get("/{therapist_id}", response_model=TherapistResponse)
def get_therapist(therapist_id: UUID, db: Session = Depends(get_db)):
    t = db.query(Therapist).filter(Therapist.id == therapist_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Therapist not found")
    return TherapistResponse.model_validate(t)


# ─── Book Session ───────────────────────────
@router.post("/book", response_model=BookingResponse, status_code=201)
def book_session(
    body: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    therapist = db.query(Therapist).filter(Therapist.id == body.therapist_id).first()
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")
    if therapist.availability == "offline":
        raise HTTPException(status_code=400, detail="Therapist is currently offline")

    booking = TherapistBooking(
        user_id      = current_user.id,
        therapist_id = body.therapist_id,
        scheduled_at = body.scheduled_at,
        notes        = body.notes,
        status       = "pending",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return BookingResponse(
        id             = booking.id,
        therapist_id   = booking.therapist_id,
        scheduled_at   = booking.scheduled_at,
        status         = booking.status,
        notes          = booking.notes,
        created_at     = booking.created_at,
        therapist_name = therapist.name,
    )


# ─── My Bookings ────────────────────────────
@router.get("/bookings/me", response_model=list[BookingResponse])
def my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    bookings = (
        db.query(TherapistBooking)
        .filter(TherapistBooking.user_id == current_user.id)
        .order_by(TherapistBooking.scheduled_at.desc())
        .all()
    )
    result = []
    for b in bookings:
        result.append(BookingResponse(
            id             = b.id,
            therapist_id   = b.therapist_id,
            scheduled_at   = b.scheduled_at,
            status         = b.status,
            notes          = b.notes,
            created_at     = b.created_at,
            therapist_name = b.therapist.name if b.therapist else None,
        ))
    return result


# ─── Cancel Booking ─────────────────────────
@router.patch("/bookings/{booking_id}/cancel", response_model=SuccessResponse)
def cancel_booking(
    booking_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    booking = db.query(TherapistBooking).filter(
        TherapistBooking.id      == booking_id,
        TherapistBooking.user_id == current_user.id,
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Already cancelled")

    booking.status = "cancelled"
    db.commit()
    return SuccessResponse(message="Booking cancelled.")
