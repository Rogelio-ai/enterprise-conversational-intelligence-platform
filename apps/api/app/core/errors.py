from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.middleware import get_correlation_id


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                'error': {
                    'code': 'http_error',
                    'message': str(exc.detail),
                },
                'correlation_id': get_correlation_id(),
            },
        )
