from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.auth.entities.models import User
from app.auth.services.service import AuthService


def current_user(careerfit_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not careerfit_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    service = AuthService(db)
    user_id = service.resolve_session(careerfit_session)
    user = service.users.get_by_id(user_id) if user_id is not None else None
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 세션입니다.")
    return user
