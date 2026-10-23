"""persist the fixed Samsung interview target role

Revision ID: 0002_interview_target_role
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_interview_target_role"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("interview_sessions")
    }
    if "target_role" in columns:
        return
    op.add_column(
        "interview_sessions",
        sa.Column(
            "target_role",
            sa.String(length=30),
            nullable=False,
            server_default="BACKEND",
        ),
    )
    op.alter_column("interview_sessions", "target_role", server_default=None)


def downgrade():
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("interview_sessions")
    }
    if "target_role" in columns:
        op.drop_column("interview_sessions", "target_role")
