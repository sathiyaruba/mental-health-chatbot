from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import UserResponse, UserUpdateRequest, SuccessResponse
from app.services.auth_service import get_current_active_user

router = APIRouter(prefix="/api/users", tags=["User Profile"])


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_active_user)):
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
def update_profile(
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.is_anonymous is not None:
        current_user.is_anonymous = body.is_anonymous

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.delete("/me", response_model=SuccessResponse)
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    current_user.is_active = False
    db.commit()
    return SuccessResponse(message="Account deactivated. We're sad to see you go. 💙")
