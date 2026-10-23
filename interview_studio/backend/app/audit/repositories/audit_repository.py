from sqlalchemy.orm import Session

from app.core.entity_registry import AuditLog


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, log: AuditLog) -> AuditLog:
        self.db.add(log)
        return log

    def record(self, **values) -> AuditLog:
        return self.add(AuditLog(**values))
