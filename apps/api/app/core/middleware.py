from __future__ import annotations

import logging
import re
from collections import deque
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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'same-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cache-Control', 'no-store')
        return response


class EntryPointRateLimitMiddleware(BaseHTTPMiddleware):
    """Bounded, per-process protection for public credential entry points."""

    def __init__(self, app, *, staff_limit: int, diner_limit: int) -> None:
        super().__init__(app)
        self.limits = {'/auth/login': staff_limit, '/diner-sessions/join': diner_limit}
        self.requests: dict[tuple[str, str], deque[float]] = {}

    async def dispatch(self, request: Request, call_next):
        limit = self.limits.get(request.url.path) if request.method == 'POST' else None
        if limit is None:
            return await call_next(request)
        now = perf_counter()
        client = request.client.host if request.client else 'unknown'
        key = (request.url.path, client)
        bucket = self.requests.get(key)
        if bucket is None:
            if len(self.requests) >= 10_000:
                self.requests.pop(next(iter(self.requests)))
            bucket = self.requests[key] = deque()
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= limit:
            logger.warning(
                'Credential entry point rate limited',
                extra={'event': 'credential_entry_rate_limited', 'path': request.url.path},
            )
            return JSONResponse(
                status_code=429,
                content={'error': {'code': 'rate_limited', 'message': 'Too many requests'}},
                headers={'Retry-After': '60'},
            )
        bucket.append(now)
        return await call_next(request)


class PilotCapabilityBoundaryMiddleware(BaseHTTPMiddleware):
    """Fail closed for externally acting capabilities excluded from the initial pilot."""

    def __init__(self, app, *, connector_enabled: bool, external_pos_enabled: bool) -> None:
        super().__init__(app)
        self.connector_enabled = connector_enabled
        self.external_pos_enabled = external_pos_enabled

    async def dispatch(self, request: Request, call_next):
        capability = None
        if request.url.path.startswith('/connector/v1/') and not self.connector_enabled:
            capability = 'physical_printing'
        elif '/pos-submission' in request.url.path and not self.external_pos_enabled:
            capability = 'external_pos'
        if capability is not None:
            return JSONResponse(
                status_code=503,
                content={
                    'error': {
                        'code': 'capability_disabled',
                        'message': f'{capability} is disabled by deployment policy',
                    }
                },
            )
        return await call_next(request)


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
                    'user_id': getattr(request.state, 'user_id', None),
                    'tenant_id': getattr(request.state, 'tenant_id', None),
                },
            )
            _correlation_id_context.reset(context_token)
