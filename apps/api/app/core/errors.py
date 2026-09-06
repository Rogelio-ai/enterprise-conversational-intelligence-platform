from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.middleware import get_correlation_id


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        safe_errors = [
            {
                'type': error['type'],
                'loc': error['loc'],
                'msg': error['msg'],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                'error': {
                    'code': 'validation_error',
                    'message': 'Request validation failed',
                    'details': safe_errors,
                },
                'correlation_id': get_correlation_id(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            error = {
                'code': str(detail.get('code', 'http_error')),
                'message': str(detail.get('message', detail)),
            }
            for key in ('state', 'required_input', 'allowed_actions', 'next_action'):
                if key in detail:
                    error[key] = detail[key]
        else:
            error = {'code': 'http_error', 'message': str(detail)}
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                'error': error,
                'correlation_id': get_correlation_id(),
            },
        )
