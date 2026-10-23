"""Document domain failures independent of the HTTP transport."""


class DocumentDomainError(RuntimeError):
    """Base class for document use-case failures."""


class DocumentNotFound(DocumentDomainError):
    """The document is missing, deleted, or outside the authenticated owner scope."""


class DocumentFileUnavailable(DocumentDomainError):
    """The document metadata exists but its stored upload cannot be read safely."""


class InvalidUploadFilename(DocumentDomainError):
    """The supplied upload name cannot be normalized safely."""


class UnsupportedDocumentType(DocumentDomainError):
    """The uploaded file extension is not supported."""


class UploadTooLarge(DocumentDomainError):
    """The uploaded payload exceeds the configured size limit."""
