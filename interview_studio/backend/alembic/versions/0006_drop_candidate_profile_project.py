"""remove candidate profile and project storage

Revision ID: 0006_drop_candidate_profile
Revises: 0005_drop_compatibility_analysis
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_drop_candidate_profile"
down_revision = "0005_drop_compatibility_analysis"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    tables = _table_names()
    if "candidate_projects" in tables:
        op.drop_table("candidate_projects")
    if "candidate_profiles" in tables:
        op.drop_table("candidate_profiles")


def downgrade():
    # Removed rows cannot be reconstructed. Downgrade restores only the empty
    # development schema that existed before this revision.
    tables = _table_names()
    if "candidate_profiles" not in tables:
        op.create_table(
            "candidate_profiles",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("phone", sa.String(length=30), nullable=True),
            sa.Column("school", sa.String(length=200), nullable=True),
            sa.Column("major", sa.String(length=200), nullable=True),
            sa.Column("desired_position", sa.String(length=200), nullable=True),
            sa.Column("desired_industry", sa.String(length=200), nullable=True),
            sa.Column("introduction", sa.Text(), nullable=True),
            sa.Column("strengths", sa.Text(), nullable=True),
            sa.Column("weaknesses", sa.Text(), nullable=True),
            sa.Column("github_url", sa.String(length=500), nullable=True),
            sa.Column("portfolio_url", sa.String(length=500), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_candidate_profiles_user_id",
            "candidate_profiles",
            ["user_id"],
            unique=True,
        )

    if "candidate_projects" not in tables:
        op.create_table(
            "candidate_projects",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("team_size", sa.Integer(), nullable=True),
            sa.Column("role", sa.String(length=255), nullable=True),
            sa.Column("technologies", sa.Text(), nullable=True),
            sa.Column("problem", sa.Text(), nullable=True),
            sa.Column("solution", sa.Text(), nullable=True),
            sa.Column("contribution", sa.Text(), nullable=True),
            sa.Column("result", sa.Text(), nullable=True),
            sa.Column("quantitative_metric", sa.Text(), nullable=True),
            sa.Column("retrospective", sa.Text(), nullable=True),
            sa.Column("repository_url", sa.String(length=500), nullable=True),
            sa.Column("demo_url", sa.String(length=500), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_candidate_projects_user_id",
            "candidate_projects",
            ["user_id"],
            unique=False,
        )
