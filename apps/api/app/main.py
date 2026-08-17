from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RuntimeMiddleware
from app.db.session import DatabaseManager


class DatabaseLifecycle(Protocol):
    async def check_connection(self) -> None: ...

    async def dispose(self) -> None: ...


def create_app(
    settings: Settings | None = None,
    database: DatabaseLifecycle | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    runtime_database = database or DatabaseManager(runtime_settings)
    configure_logging(service=runtime_settings.app_name, level=runtime_settings.log_level)
    logger = logging.getLogger('ecip.lifecycle')

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info('API startup complete', extra={'event': 'application_started'})
        try:
            yield
        finally:
            await runtime_database.dispose()
            logger.info('API shutdown complete', extra={'event': 'application_stopped'})

    app = FastAPI(
        title=runtime_settings.app_name,
        version='0.1.0',
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.database = runtime_database
    app.add_middleware(RuntimeMiddleware)
    register_error_handlers(app)
    app.include_router(health_router)
    return app
