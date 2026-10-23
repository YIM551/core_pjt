from __future__ import annotations


class InterviewDomainError(Exception):
    status: int = 500
    code: str = "INTERVIEW_ERROR"
    detail: str = "Interview operation failed."


class CompanyEvidenceUnavailable(InterviewDomainError):
    status = 503
    code = "COMPANY_EVIDENCE_UNAVAILABLE"
    detail = "Samsung interview evidence is unavailable. Reindex the corpus and try again."


class InterviewNotFound(InterviewDomainError):
    status = 404
    code = "INTERVIEW_NOT_FOUND"
    detail = "interview session not found"


class InterviewNotCompleted(InterviewDomainError):
    status = 409
    code = "INTERVIEW_NOT_COMPLETED"
    detail = "interview must be completed before its report is available"
