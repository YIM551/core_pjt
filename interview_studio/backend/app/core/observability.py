"""Safe, structured observability for AI request processing."""

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonAuditFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        request_id = _request_id.get()
        if request_id:
            payload["request_id"] = request_id
        payload.update(getattr(record, "audit", {}))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_audit_logging() -> None:
    logger = logging.getLogger("careerfit.audit")
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonAuditFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def set_request_id(value: str) -> Token:
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def audit_event(event: str, **fields: object) -> None:
    """Log approved metadata only; never pass prompt, content, or credentials."""
    logging.getLogger("careerfit.audit").info(event, extra={"audit": fields})
