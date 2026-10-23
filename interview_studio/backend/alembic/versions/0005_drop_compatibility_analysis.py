"""remove retired compatibility analysis storage

Revision ID: 0005_drop_compatibility_analysis
Revises: 0004_freestyle_interview
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_drop_compatibility_analysis"
down_revision = "0004_freestyle_interview"
branch_labels = None
depends_on = None


def upgrade():
    if "compatibility_analyses" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("compatibility_analyses")


def downgrade():
    # The retired data intentionally cannot be reconstructed; this is only a
    # structural rollback for development environments.
    if "compatibility_analyses" in sa.inspect(op.get_bind()).get_table_names():
        return
    from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, func
    op.create_table(
        "compatibility_analyses",
        Column("id", Integer, primary_key=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), server_default=func.now()),
        Column("deleted_at", DateTime(timezone=True)),
        Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
        Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
        Column("job_posting_id", Integer, ForeignKey("job_postings.id")),
        Column("total_score", Float, nullable=False), Column("skill_score", Float, nullable=False),
        Column("experience_score", Float, nullable=False), Column("strengths", JSON), Column("gaps", JSON),
        Column("recommended_projects", JSON), Column("recommended_keywords", JSON), Column("preparation_priorities", JSON),
    )
