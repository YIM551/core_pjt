"""Filesystem adapter for uploaded document content."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4


class UnsafeUploadName(ValueError):
    """The client filename cannot be represented safely."""


class UnsafeStoredUploadPath(ValueError):
    """A persisted upload path escapes the configured upload root."""


@dataclass(frozen=True)
class StoredUpload:
    path: str
    original_filename: str
    suffix: str


def describe_upload(filename: str) -> tuple[str, str]:
    normalized = str(filename or "upload").replace("\\", "/")
    original_filename = PurePosixPath(normalized).name
    if not original_filename or original_filename in {".", ".."}:
        raise UnsafeUploadName()
    return original_filename, Path(original_filename).suffix.lower()


def write_upload(root: Path, filename: str, content: bytes) -> StoredUpload:
    original_filename, suffix = describe_upload(filename)
    resolved_root = root.resolve()
    resolved_root.mkdir(parents=True, exist_ok=True)
    path = (resolved_root / f"{uuid4().hex}{suffix}").resolve()
    if path.parent != resolved_root:
        raise UnsafeUploadName()
    path.write_bytes(content)
    return StoredUpload(
        path=str(path),
        original_filename=original_filename,
        suffix=suffix,
    )


def resolve_upload_path(root: Path, stored_path: str | Path) -> Path:
    """Resolve current and legacy Docker upload paths inside ``root`` only."""
    resolved_root = root.resolve()
    normalized = str(stored_path).replace("\\", "/")
    persisted = PurePosixPath(normalized)

    if persisted.is_absolute() or Path(normalized).is_absolute():
        candidate = Path(normalized).resolve()
        try:
            candidate.relative_to(resolved_root)
            return candidate
        except ValueError:
            legacy_root = PurePosixPath("/app/uploads")
            try:
                relative = persisted.relative_to(legacy_root)
            except ValueError as exc:
                raise UnsafeStoredUploadPath() from exc
            candidate = (resolved_root / Path(*relative.parts)).resolve()
    else:
        candidate = (resolved_root / Path(*persisted.parts)).resolve()

    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise UnsafeStoredUploadPath() from exc
    return candidate


def read_bytes(root: Path, stored_path: str | Path) -> bytes:
    return resolve_upload_path(root, stored_path).read_bytes()


def safe_delete(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)
