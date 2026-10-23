"""Import all SQLAlchemy mappings for Alembic and application startup."""

from app.audit.entities import AuditLog
from app.auth.entities import User
from app.company_corpus.entities import Client, Company, Department, Employee, JobPosting, QuarterlyPerformance
from app.document.entities import Document, DocumentChunk
from app.interview.entities import InterviewEvaluation, InterviewMemorySummary, InterviewMessage, InterviewSession

__all__ = [
    "AuditLog", "Client", "Company", "Department",
    "Document", "DocumentChunk", "Employee", "InterviewEvaluation", "InterviewMemorySummary", "InterviewMessage",
    "InterviewSession", "JobPosting", "QuarterlyPerformance", "User",
]

from app.studio.models import StudioWorkspace, StudioSource, StudioSession, StudioCapture, StudioChunk

from app.studio.models import StudioSourceChunk, StudioJob
