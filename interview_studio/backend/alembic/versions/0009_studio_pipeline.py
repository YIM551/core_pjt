"""Studio immutable source revisions, retrieval chunks, durable jobs."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
revision = '0009_studio_pipeline'
down_revision = '0008_studio'
branch_labels = None
depends_on = None

def timestamps():
    return [sa.Column('id',sa.Integer(),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('deleted_at',sa.DateTime(timezone=True))]

def upgrade():
    op.add_column('studio_sources',sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('studio_sources',sa.Column('parent_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_studio_sources_parent','studio_sources','studio_sources',['parent_id'],['id'])
    op.add_column('studio_sources',sa.Column('processing',sa.JSON(),nullable=False,server_default=sa.text("'{}'")))
    op.add_column('studio_sources',sa.Column('original_path',sa.Text(),nullable=True))
    op.add_column('studio_sources',sa.Column('original_filename',sa.String(255),nullable=True))
    op.create_table('studio_source_chunks',*timestamps(),sa.Column('source_id',sa.Integer(),sa.ForeignKey('studio_sources.id'),nullable=False),sa.Column('ordinal',sa.Integer(),nullable=False),sa.Column('text',sa.Text(),nullable=False),sa.Column('embedding',Vector(4096),nullable=True),sa.Column('embedding_model',sa.String(200)))
    op.create_index('ix_studio_source_chunks_source_id','studio_source_chunks',['source_id'])
    op.create_table('studio_jobs',*timestamps(),sa.Column('session_id',sa.Integer(),sa.ForeignKey('studio_sessions.id'),nullable=False),sa.Column('kind',sa.String(30),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.create_index('ix_studio_jobs_session_id','studio_jobs',['session_id'])

def downgrade():
    op.drop_table('studio_jobs')
    op.drop_table('studio_source_chunks')
    op.drop_column('studio_sources','original_filename')
    op.drop_column('studio_sources','original_path')
    op.drop_column('studio_sources','processing')
    op.drop_constraint('fk_studio_sources_parent','studio_sources',type_='foreignkey')
    op.drop_column('studio_sources','parent_id')
    op.drop_column('studio_sources','revision')
