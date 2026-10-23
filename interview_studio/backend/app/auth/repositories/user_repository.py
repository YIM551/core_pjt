from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.entities.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    def get_temporary(self) -> User | None:
        return self.db.scalar(select(User).where(User.email == "temporary@careerfit.local", User.deleted_at.is_(None)))

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
