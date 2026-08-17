from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware


CORRELATION_HEADER = 'X-Correlation-ID'
MAX_CORRELATION_ID_LENGTH = 128
_CORRELATION_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$')
_correlation_id_context: ContextVar[str | None] = ContextVar('correlation_id', default=None)

HTTP_REQUESTS_TOTAL = Counter(
    'ecip_http_requests_total',
    'Total HTTP requests processed.',
    ('method', 'route', 'status_code'),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    'ecip_http_request_duration_seconds',
    'HTTP request duration in seconds.',
    ('method', 'route'),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

logger = logging.getLogger('ecip.request')


def get_correlation_id() -> str | None:
    return _correlation_id_context.get()


def resolve_correlation_id(value: str | None) -> str:
    candidate = value.strip() if value else ''
    if (
        candidate
        and len(candidate) <= MAX_CORRELATION_ID_LENGTH
        and _CORRELATION_PATTERN.fullmatch(candidate)
    ):
        return candidate
    return str(uuid4())


def _route_label(request: Request) -> str:
    route = request.scope.get('route')
    path = getattr(route, 'path', None)
    return str(path) if path else 'unmatched'


class RuntimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = resolve_correlation_id(request.headers.get(CORRELATION_HEADER))
        context_token = _correlation_id_context.set(correlation_id)
        request.state.correlation_id = correlation_id
        started_at = perf_counter()
        status_code = 500

        try:
            try:
                response = await call_next(request)
                status_code = response.status_code
            except Exception:
                logger.exception(
                    'Unhandled request exception',
                    extra={
                        'event': 'request_unhandled_exception',
                        'method': request.method,
                        'path': request.url.path,
                    },
                )
                response = JSONResponse(
                    status_code=500,
                    content={
                        'error': {
                            'code': 'internal_error',
                            'message': 'Internal server error',
                        },
                        'correlation_id': correlation_id,
                    },
                )
            response.headers[CORRELATION_HEADER] = correlation_id
            return response
        finally:
            duration_seconds = perf_counter() - started_at
            route = _route_label(request)
            HTTP_REQUESTS_TOTAL.labels(request.method, route, str(status_code)).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(request.method, route).observe(duration_seconds)
            logger.info(
                'Request completed',
                extra={
                    'event': 'request_completed',
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': status_code,
                    'duration_ms': round(duration_seconds * 1000, 3),
                    'correlation_id': correlation_id,
                },
            )
            _correlation_id_context.reset(context_token)
