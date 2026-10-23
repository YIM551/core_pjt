"""remove the fixed interview question count

Revision ID: 0004_freestyle_interview
Revises: 0003_qwen_embedding_4096
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_freestyle_interview"
down_revision = "0003_qwen_embedding_4096"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("interview_sessions")
    }


def upgrade():
    if "question_count" not in _columns():
        return
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.drop_column("question_count")


def downgrade():
    if "question_count" in _columns():
        return
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "question_count",
                sa.Integer(),
                nullable=False,
                server_default="5",
            )
        )
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.alter_column("question_count", server_default=None)
