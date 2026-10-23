"""initial careerfit schema

Revision ID: 0001_initial
Revises:

This revision intentionally owns a frozen copy of the original schema.  It
must not import the application's live SQLAlchemy registry: doing so makes a
fresh database depend on entities added by later migrations.
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


HISTORICAL_METADATA = sa.MetaData()


def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


sa.Table(
    "users", HISTORICAL_METADATA,
    *_timestamp_columns(),
    sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
    sa.Column("name", sa.String(100), nullable=False, server_default="temporary user"),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
)
sa.Table(
    "companies", HISTORICAL_METADATA,
    *_timestamp_columns(),
    sa.Column("name", sa.String(255), nullable=False, unique=True, index=True),
    sa.Column("slogan", sa.String(255)), sa.Column("description", sa.Text()),
    sa.Column("founded_date", sa.Date()), sa.Column("founder", sa.String(100)),
    sa.Column("ceo", sa.String(100)), sa.Column("headquarters", sa.String(255)),
    sa.Column("industry", sa.String(255)), sa.Column("employee_count", sa.Integer()),
    sa.Column("vision", sa.Text()), sa.Column("core_values", sa.Text()),
    sa.Column("talent_profile", sa.Text()), sa.Column("culture", sa.Text()),
    sa.Column("website_url", sa.String(500)),
)
sa.Table(
    "departments", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("name", sa.String(255), nullable=False), sa.Column("description", sa.Text()),
    sa.Column("main_tasks", sa.Text()), sa.Column("goals", sa.Text()), sa.Column("required_competencies", sa.Text()),
)
sa.Table(
    "employees", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id"), nullable=False, index=True),
    sa.Column("name", sa.String(100), nullable=False), sa.Column("hire_date", sa.Date()),
    sa.Column("position", sa.String(100)), sa.Column("title", sa.String(100)),
    sa.Column("school", sa.String(200)), sa.Column("major", sa.String(200)),
    sa.Column("salary", sa.Float()), sa.Column("employment_status", sa.String(50), nullable=False, server_default="ACTIVE"),
    sa.Column("main_responsibilities", sa.Text()),
)
sa.Table(
    "job_postings", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id")),
    sa.Column("title", sa.String(255), nullable=False), sa.Column("position_name", sa.String(255)),
    sa.Column("responsibilities", sa.Text()), sa.Column("qualifications", sa.Text()),
    sa.Column("preferred_qualifications", sa.Text()), sa.Column("required_skills", sa.Text()),
    sa.Column("preferred_skills", sa.Text()), sa.Column("status", sa.String(50), nullable=False, server_default="OPEN"),
)
sa.Table(
    "quarterly_performance", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("year", sa.Integer(), nullable=False), sa.Column("quarter", sa.Integer(), nullable=False),
    sa.Column("revenue", sa.Float(), nullable=False), sa.Column("operating_profit", sa.Float()),
    sa.Column("net_profit", sa.Float()), sa.Column("highlights", sa.Text()), sa.Column("risks", sa.Text()),
    sa.UniqueConstraint("company_id", "year", "quarter", name="uq_company_performance_period"),
)
sa.Table(
    "clients", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id")),
    sa.Column("name", sa.String(255), nullable=False), sa.Column("industry", sa.String(255)),
    sa.Column("country", sa.String(100)), sa.Column("contract_amount", sa.Float()),
    sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"), sa.Column("risk_level", sa.String(50)),
)
sa.Table(
    "candidate_profiles", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True, index=True),
    sa.Column("phone", sa.String(30)), sa.Column("school", sa.String(200)), sa.Column("major", sa.String(200)),
    sa.Column("desired_position", sa.String(200)), sa.Column("desired_industry", sa.String(200)),
    sa.Column("introduction", sa.Text()), sa.Column("strengths", sa.Text()), sa.Column("weaknesses", sa.Text()),
    sa.Column("github_url", sa.String(500)), sa.Column("portfolio_url", sa.String(500)),
)
sa.Table(
    "candidate_projects", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("title", sa.String(255), nullable=False), sa.Column("summary", sa.Text(), nullable=False),
    sa.Column("start_date", sa.Date()), sa.Column("end_date", sa.Date()), sa.Column("team_size", sa.Integer()),
    sa.Column("role", sa.String(255)), sa.Column("technologies", sa.Text()), sa.Column("problem", sa.Text()),
    sa.Column("solution", sa.Text()), sa.Column("contribution", sa.Text()), sa.Column("result", sa.Text()),
    sa.Column("quantitative_metric", sa.Text()), sa.Column("retrospective", sa.Text()),
    sa.Column("repository_url", sa.String(500)), sa.Column("demo_url", sa.String(500)),
)
sa.Table(
    "documents", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("scope", sa.String(20), nullable=False, index=True),
    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
    sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), index=True),
    sa.Column("document_type", sa.String(50), nullable=False, server_default="OTHER"),
    sa.Column("title", sa.String(255), nullable=False), sa.Column("original_filename", sa.String(255), nullable=False),
    sa.Column("file_path", sa.String(500), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False),
    sa.Column("extracted_text", sa.Text()), sa.Column("processing_status", sa.String(30), nullable=False, server_default="UPLOADED"),
)
sa.Table(
    "document_chunks", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False, index=True),
    sa.Column("scope", sa.String(20), nullable=False, index=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
    sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), index=True), sa.Column("chunk_index", sa.Integer(), nullable=False),
    sa.Column("content", sa.Text(), nullable=False), sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("embedding", Vector(768)),
)
sa.Table(
    "interview_sessions", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id")),
    sa.Column("interview_type", sa.String(50), nullable=False, server_default="COMPREHENSIVE"),
    sa.Column("difficulty", sa.String(50), nullable=False, server_default="INTERMEDIATE"),
    sa.Column("question_count", sa.Integer(), nullable=False, server_default="5"),
    sa.Column("status", sa.String(30), nullable=False, server_default="IN_PROGRESS"),
    sa.Column("overall_score", sa.Float()), sa.Column("summary", sa.Text()),
)
sa.Table(
    "interview_messages", HISTORICAL_METADATA,
    sa.Column("id", sa.Integer(), primary_key=True), sa.Column("interview_session_id", sa.Integer(), sa.ForeignKey("interview_sessions.id"), nullable=False, index=True),
    sa.Column("sequence_number", sa.Integer(), nullable=False), sa.Column("speaker", sa.String(20), nullable=False),
    sa.Column("question_type", sa.String(50)), sa.Column("content", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
sa.Table(
    "interview_evaluations", HISTORICAL_METADATA,
    sa.Column("id", sa.Integer(), primary_key=True), sa.Column("interview_message_id", sa.Integer(), sa.ForeignKey("interview_messages.id"), nullable=False, unique=True),
    sa.Column("scores", sa.JSON(), nullable=False, server_default="{}"), sa.Column("total_score", sa.Float(), nullable=False),
    sa.Column("strengths", sa.JSON(), nullable=False, server_default="[]"), sa.Column("weaknesses", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("missing_points", sa.JSON(), nullable=False, server_default="[]"), sa.Column("improvement_advice", sa.Text(), nullable=False),
    sa.Column("improved_answer", sa.Text(), nullable=False), sa.Column("follow_up_question", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
sa.Table(
    "compatibility_analyses", HISTORICAL_METADATA,
    *_timestamp_columns(), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
    sa.Column("job_posting_id", sa.Integer(), sa.ForeignKey("job_postings.id")), sa.Column("total_score", sa.Float(), nullable=False),
    sa.Column("skill_score", sa.Float(), nullable=False), sa.Column("experience_score", sa.Float(), nullable=False),
    sa.Column("strengths", sa.JSON(), nullable=False, server_default="[]"), sa.Column("gaps", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("recommended_projects", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("recommended_keywords", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("preparation_priorities", sa.JSON(), nullable=False, server_default="[]"),
)
sa.Table(
    "audit_logs", HISTORICAL_METADATA,
    sa.Column("id", sa.Integer(), primary_key=True), sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("action", sa.String(30), nullable=False), sa.Column("resource_type", sa.String(100), nullable=False),
    sa.Column("resource_id", sa.Integer(), nullable=False), sa.Column("data_scope", sa.String(20), nullable=False),
    sa.Column("before_data", sa.JSON()), sa.Column("after_data", sa.JSON()),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    HISTORICAL_METADATA.create_all(bind=bind)


def downgrade():
    HISTORICAL_METADATA.drop_all(bind=op.get_bind())
