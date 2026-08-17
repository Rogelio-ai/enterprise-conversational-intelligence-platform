from __future__ import annotations

import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


router = APIRouter(tags=['runtime'])
logger = logging.getLogger('ecip.health')


@router.get('/health')
async def health(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        'status': 'ok',
        'service': settings.app_name,
        'environment': settings.app_env,
    }


@router.get('/ready')
async def ready(request: Request):
    try:
        await request.app.state.database.check_connection()
    except Exception:
        logger.warning('Database readiness check failed', extra={'event': 'readiness_failed'})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                'status': 'not_ready',
                'service': request.app.state.settings.app_name,
            },
        )
    return {
        'status': 'ready',
        'service': request.app.state.settings.app_name,
    }


@router.get('/metrics', include_in_schema=False)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
