from sqlalchemy import JSON, ForeignKey, String, Text, LargeBinary, UniqueConstraint
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
from app.auth.entities.base import Timestamped

class StudioWorkspace(Timestamped):
    __tablename__ = 'studio_workspaces'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200))
    target_role: Mapped[str] = mapped_column(String(100))

class StudioSource(Timestamped):
    __tablename__ = 'studio_sources'
    workspace_id: Mapped[int] = mapped_column(ForeignKey('studio_workspaces.id'), index=True)
    category: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(default=1)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('studio_sources.id'))
    processing: Mapped[dict] = mapped_column(JSON, default=dict)
    original_path: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(255))

class StudioSession(Timestamped):
    __tablename__ = 'studio_sessions'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey('studio_workspaces.id'))
    status: Mapped[str] = mapped_column(String(30), default='READY')
    data: Mapped[dict] = mapped_column(JSON, default=dict)

class StudioCapture(Timestamped):
    __tablename__ = 'studio_captures'
    session_id: Mapped[int] = mapped_column(ForeignKey('studio_sessions.id'), index=True)
    sealed: Mapped[bool] = mapped_column(default=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

class StudioChunk(Timestamped):
    __tablename__ = 'studio_chunks'
    __table_args__ = (UniqueConstraint('capture_id', 'track', 'seq'),)
    capture_id: Mapped[int] = mapped_column(ForeignKey('studio_captures.id'), index=True)
    track: Mapped[str] = mapped_column(String(10))
    seq: Mapped[int]
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)

class StudioSourceChunk(Timestamped):
    __tablename__ = 'studio_source_chunks'
    source_id: Mapped[int] = mapped_column(ForeignKey('studio_sources.id'), index=True)
    ordinal: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(Vector(4096), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200))

class StudioJob(Timestamped):
    __tablename__ = 'studio_jobs'
    session_id: Mapped[int] = mapped_column(ForeignKey('studio_sessions.id'), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default='PENDING')
    data: Mapped[dict] = mapped_column(JSON, default=dict)
