"""Private interview studio storage.
Revision ID: 0008_studio
Revises: 0007_interview_memory_summaries
"""
from alembic import op
import sqlalchemy as sa
revision = '0008_studio'
down_revision = '0007_interview_memory_summaries'
branch_labels = None
depends_on = None

def timestamps():
    return [sa.Column('id',sa.Integer(),primary_key=True),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True)]

def upgrade():
    op.create_table('studio_workspaces',*timestamps(),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('name',sa.String(200),nullable=False),sa.Column('company_name',sa.String(200),nullable=False),sa.Column('target_role',sa.String(100),nullable=False))
    op.create_index('ix_studio_workspaces_user_id','studio_workspaces',['user_id'])
    op.create_table('studio_sources',*timestamps(),sa.Column('workspace_id',sa.Integer(),sa.ForeignKey('studio_workspaces.id'),nullable=False),sa.Column('category',sa.String(40),nullable=False),sa.Column('title',sa.String(200),nullable=False),sa.Column('text',sa.Text(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False))
    op.create_index('ix_studio_sources_workspace_id','studio_sources',['workspace_id'])
    op.create_table('studio_sessions',*timestamps(),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('workspace_id',sa.Integer(),sa.ForeignKey('studio_workspaces.id'),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.create_index('ix_studio_sessions_user_id','studio_sessions',['user_id'])
    op.create_table('studio_captures',*timestamps(),sa.Column('session_id',sa.Integer(),sa.ForeignKey('studio_sessions.id'),nullable=False),sa.Column('sealed',sa.Boolean(),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.create_index('ix_studio_captures_session_id','studio_captures',['session_id'])
    op.create_table('studio_chunks',*timestamps(),sa.Column('capture_id',sa.Integer(),sa.ForeignKey('studio_captures.id'),nullable=False),sa.Column('track',sa.String(10),nullable=False),sa.Column('seq',sa.Integer(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('content',sa.LargeBinary(),nullable=False),sa.UniqueConstraint('capture_id','track','seq'))
    op.create_index('ix_studio_chunks_capture_id','studio_chunks',['capture_id'])

def downgrade():
    for table in ('studio_chunks','studio_captures','studio_sessions','studio_sources','studio_workspaces'):
        op.drop_table(table)
