from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.entities.base import Timestamped


class User(Timestamped):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="임시 사용자")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
