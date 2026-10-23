from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import current_user
from app.auth.dto.models import UserResponse
from app.auth.services.service import AuthService

router = APIRouter(prefix="/auth/session", tags=["auth"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def create_session(response: Response, db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.temporary_user()
    response.set_cookie("careerfit_session", service.issue_session(user), httponly=True, samesite="lax", secure=False, max_age=86400)
    return UserResponse.model_validate(user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(response: Response):
    response.delete_cookie("careerfit_session")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=UserResponse)
def get_session(user = Depends(current_user)):
    return UserResponse.model_validate(user)
