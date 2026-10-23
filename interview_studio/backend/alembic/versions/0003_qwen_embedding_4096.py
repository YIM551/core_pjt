"""switch document chunks to Qwen 4096-dimensional embeddings

Revision ID: 0003_qwen_embedding_4096
Revises: 0002_interview_target_role
"""

from alembic import op


revision = "0003_qwen_embedding_4096"
down_revision = "0002_interview_target_role"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.execute(
        "ALTER TABLE document_chunks "
        "ALTER COLUMN embedding TYPE vector(4096) "
        "USING NULL::vector(4096)"
    )


def downgrade():
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.execute(
        "ALTER TABLE document_chunks "
        "ALTER COLUMN embedding TYPE vector(768) "
        "USING NULL::vector(768)"
    )
