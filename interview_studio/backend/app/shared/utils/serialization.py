"""Transport-independent entity serialization for audit snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


PRIVATE_COLUMNS = {
    "file_path",
    "extracted_text",
    "embedding",
    "metadata_json",
    "deleted_at",
}


def dump(instance: Any) -> dict[str, Any]:
    """Serialize mapped entities while excluding private storage and RAG fields."""
    result: dict[str, Any] = {}
    for column in instance.__table__.columns:
        if column.name in PRIVATE_COLUMNS:
            continue
        value = getattr(instance, column.name)
        result[column.name] = (
            value.isoformat() if isinstance(value, (date, datetime)) else value
        )
    return result
