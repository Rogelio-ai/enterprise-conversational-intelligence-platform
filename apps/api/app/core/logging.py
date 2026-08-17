from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.middleware import get_correlation_id


_STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'service': self.service,
            'event': getattr(record, 'event', record.getMessage()),
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None) or get_correlation_id() or None,
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and key not in payload and key != 'event':
                payload[key] = value
        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(',', ':'))


def configure_logging(*, service: str, level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    handler = next(
        (candidate for candidate in root.handlers if getattr(candidate, '_ecip_json_handler', False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        handler._ecip_json_handler = True  # type: ignore[attr-defined]
        root.handlers.clear()
        root.addHandler(handler)
    handler.setFormatter(JsonFormatter(service))

    for logger_name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        runtime_logger = logging.getLogger(logger_name)
        runtime_logger.handlers.clear()
        runtime_logger.addHandler(handler)
        runtime_logger.setLevel(level)
        runtime_logger.propagate = False
