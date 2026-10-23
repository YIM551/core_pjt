import re

_INTERNAL = re.compile(r"(?:https?://\S+|\bdoc_[A-Za-z0-9_-]+\b|[A-Za-z]:[\\/]\S*|\[[^\]]+\]\([^)]*\))", re.IGNORECASE)


def remove_internal_metadata(value: str) -> str:
    return " ".join(_INTERNAL.sub("", value).split())
