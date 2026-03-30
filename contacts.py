from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, TrustedContact, CrisisAlert, AlertStatus
from app.schemas.schemas import (
    TrustedContactCreate, TrustedContactResponse,
    CrisisAlertCreate, CrisisAlertResponse, SuccessResponse
)
from app.services.auth_service import get_current_active_user
from app.services.email_service import send_crisis_alert

router = APIRouter(prefix="/api/contacts", tags=["Trusted Contacts & Crisis Alerts"])


# ─── Add Trusted Contact ────────────────────
@router.post("/", response_model=TrustedContactResponse, status_code=201)
def add_contact(
    body: TrustedContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not body.email and not body.phone:
        raise HTTPException(status_code=400, detail="Provide at least an email or phone number")

    contact = TrustedContact(
        user_id=current_user.id,
        name=body.name,
        phone=body.phone,
        email=body.email,
        relation_type=body.relationship,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return TrustedContactResponse.model_validate(contact)


# ─── List Contacts ──────────────────────────
@router.get("/", response_model=list[TrustedContactResponse])
def list_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    contacts = db.query(TrustedContact).filter(
        TrustedContact.user_id   == current_user.id,
        TrustedContact.is_active == True
    ).all()
    return [TrustedContactResponse.model_validate(c) for c in contacts]


# ─── Delete Contact ─────────────────────────
@router.delete("/{contact_id}", response_model=SuccessResponse)
def delete_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    contact = db.query(TrustedContact).filter(
        TrustedContact.id      == contact_id,
        TrustedContact.user_id == current_user.id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.is_active = False
    db.commit()
    return SuccessResponse(message="Contact removed.")


# ─── Send Manual Crisis Alert ───────────────
@router.post("/alert", response_model=CrisisAlertResponse)
def send_manual_alert(
    body: CrisisAlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    contact = db.query(TrustedContact).filter(
        TrustedContact.id        == body.contact_id,
        TrustedContact.user_id   == current_user.id,
        TrustedContact.is_active == True,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Trusted contact not found")

    alert = CrisisAlert(
        user_id      = current_user.id,
        contact_id   = contact.id,
        trigger_text = body.trigger_text,
        status       = AlertStatus.pending,
    )
    db.add(alert)
    db.flush()

    if contact.email:
        sent = send_crisis_alert(contact.name, contact.email, current_user.display_name)
        alert.status  = AlertStatus.sent if sent else AlertStatus.failed
        alert.sent_at = datetime.utcnow() if sent else None
    else:
        alert.status = AlertStatus.failed

    db.commit()
    db.refresh(alert)

    return CrisisAlertResponse(
        id           = alert.id,
        status       = alert.status,
        sent_at      = alert.sent_at,
        created_at   = alert.created_at,
        contact_name = contact.name,
    )


# ─── Alert History ──────────────────────────
@router.get("/alerts", response_model=list[CrisisAlertResponse])
def get_alert_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    alerts = (
        db.query(CrisisAlert)
        .filter(CrisisAlert.user_id == current_user.id)
        .order_by(CrisisAlert.created_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for a in alerts:
        contact_name = a.contact.name if a.contact else None
        result.append(CrisisAlertResponse(
            id           = a.id,
            status       = a.status,
            sent_at      = a.sent_at,
            created_at   = a.created_at,
            contact_name = contact_name,
        ))
    return result