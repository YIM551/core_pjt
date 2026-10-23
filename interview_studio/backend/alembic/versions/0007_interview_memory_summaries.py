"""add interview three-tier memory summaries

Revision ID: 0007_interview_memory_summaries
Revises: 0006_drop_candidate_profile
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0007_interview_memory_summaries"
down_revision = "0006_drop_candidate_profile"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    if "interview_memory_summaries" in _table_names():
        return
    op.create_table(
        "interview_memory_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("interview_session_id", sa.Integer(), nullable=False),
        sa.Column("start_sequence_number", sa.Integer(), nullable=False),
        sa.Column("end_sequence_number", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "interview_session_id",
            "end_sequence_number",
            name="uq_interview_memory_summaries_session_end_sequence",
        ),
    )
    op.create_index(
        "ix_interview_memory_summaries_interview_session_id",
        "interview_memory_summaries",
        ["interview_session_id"],
        unique=False,
    )


def downgrade():
    if "interview_memory_summaries" in _table_names():
        op.drop_table("interview_memory_summaries")
