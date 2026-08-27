from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.customers import router as customers_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.health import router as health_router
from app.api.routes.locations import router as locations_router
from app.api.routes.menus import router as menus_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.order_drafts import router as order_drafts_router
from app.api.routes.products import router as products_router
from app.api.routes.product_compositions import router as product_compositions_router
from app.api.routes.product_aliases import router as product_aliases_router
from app.api.routes.pricing import router as pricing_router
from app.api.routes.resources import router as resources_router
from app.api.routes.tenants import router as tenants_router
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
    app.include_router(auth_router)
    app.include_router(tenants_router)
    app.include_router(organizations_router)
    app.include_router(locations_router)
    app.include_router(resources_router)
    app.include_router(customers_router)
    app.include_router(conversations_router)
    app.include_router(order_drafts_router)
    app.include_router(products_router)
    app.include_router(product_compositions_router)
    app.include_router(product_aliases_router)
    app.include_router(pricing_router)
    app.include_router(menus_router)
    return app
