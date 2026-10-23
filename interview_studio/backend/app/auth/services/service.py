from itsdangerous import BadSignature
from sqlalchemy.orm import Session

from app.auth.entities.models import User
from app.auth.repositories.user_repository import UserRepository
from app.shared.utils.security import session_serializer


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def temporary_user(self) -> User:
        user = self.users.get_temporary()
        if user is None:
            user = self.users.add(User(email="temporary@careerfit.local", name="임시 사용자"))
            try:
                self.db.commit()
                self.db.refresh(user)
            except Exception:
                self.db.rollback()
                raise
        return user

    def issue_session(self, user: User) -> str:
        return session_serializer().dumps({"user_id": user.id})

    def resolve_session(self, token: str | None) -> int | None:
        if not token:
            return None
        try:
            return int(session_serializer().loads(token)["user_id"])
        except (BadSignature, KeyError, TypeError, ValueError):
            return None
