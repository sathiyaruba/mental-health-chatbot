from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import json
import re

from app.database import get_db
from app.models.models import User, ChatSession, ChatMessage
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    content: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    detected_mood: Optional[str] = None
    crisis_detected: bool = False


def _parse_ai_result(raw) -> dict:
    """
    Robustly extract reply/mood/crisis from AI response.
    Handles ALL these cases:
      - Plain text string
      - Pure JSON string  {"reply": "...", "mood": "...", "crisis": true}
      - Text WITH JSON appended  "Some text { \"reply\": ... }"
      - Dict object directly
    """
    # Already a dict
    if isinstance(raw, dict):
        return {
            "reply": str(raw.get("reply") or raw.get("message") or "I'm here with you."),
            "mood": raw.get("mood") or raw.get("detected_mood") or "unknown",
            "crisis": bool(raw.get("crisis") or raw.get("crisis_detected") or False),
        }

    if not isinstance(raw, str):
        raw = str(raw)

    # Strip markdown fences
    cleaned = re.sub(r'^```json\s*', '', raw.strip())
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()

    # Case 1: Pure JSON object
    if cleaned.startswith('{'):
        try:
            data = json.loads(cleaned)
            return {
                "reply": str(data.get("reply") or data.get("message") or cleaned),
                "mood": data.get("mood") or data.get("detected_mood") or "unknown",
                "crisis": bool(data.get("crisis") or data.get("crisis_detected") or False),
            }
        except json.JSONDecodeError:
            pass

    # Case 2: Text with JSON block appended at end
    # Pattern: "Some reply text {"reply": ...}"
    json_pattern = re.search(r'\s*(\{[\s\S]*"reply"[\s\S]*\})\s*$', cleaned)
    if json_pattern:
        text_before = cleaned[:json_pattern.start()].strip()
        try:
            json_part = json.loads(json_pattern.group(1))
            # Use text_before as reply if it exists, else use json reply field
            final_reply = text_before if text_before else str(json_part.get("reply", ""))
            return {
                "reply": final_reply,
                "mood": json_part.get("mood") or json_part.get("detected_mood") or "unknown",
                "crisis": bool(json_part.get("crisis") or json_part.get("crisis_detected") or False),
            }
        except json.JSONDecodeError:
            # JSON parse failed — just strip the JSON-looking part
            if text_before:
                return {"reply": text_before, "mood": "unknown", "crisis": False}

    # Case 3: Plain text — return as-is
    return {
        "reply": cleaned,
        "mood": "unknown",
        "crisis": False,
    }


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get or create session
    session = None
    if request.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == request.session_id,
            ChatSession.user_id == current_user.id
        ).first()

    if not session:
        session = ChatSession(user_id=current_user.id)
        db.add(session)
        db.commit()
        db.refresh(session)

    # Load conversation history (last 20 messages)
    history = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at.asc()).all()

    # Build history BEFORE saving current message (avoid duplicate to Groq)
    messages = [{"role": msg.role, "content": msg.content} for msg in history[-20:]]

    # Save user message AFTER building history
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.content
    )
    db.add(user_msg)
    db.commit()

    # Get AI response
    try:
        result = await get_ai_reply(
            user_message=request.content,
            conversation_history=messages
        )
        # get_ai_reply already returns clean {reply, mood, crisis} dict
        reply_text      = result.get("reply", "I'm here with you. 💙")
        detected_mood   = result.get("mood", "unknown")
        crisis_detected = bool(result.get("crisis", False))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    # Save assistant message (clean text only)
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=reply_text
    )
    db.add(assistant_msg)
    db.commit()

    # Auto crisis alert
    if crisis_detected:
        try:
            from app.services.alert_service import AlertService
            alert_service = AlertService(db)
            await alert_service.send_crisis_alert(
                user_id=current_user.id,
                trigger_text=request.content
            )
        except Exception:
            pass

    return ChatResponse(
        reply=reply_text,
        session_id=str(session.id),
        detected_mood=detected_mood,
        crisis_detected=crisis_detected
    )


@router.get("/sessions")
async def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.created_at.desc()).limit(20).all()
    return sessions


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at.asc()).all()
    return messages