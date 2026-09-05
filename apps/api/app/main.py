from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from collections.abc import Mapping
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router
from app.api.routes.cash_sessions import router as cash_sessions_router
from app.api.routes.connector_admin import router as connector_admin_router
from app.api.routes.connector_api import router as connector_api_router
from app.api.routes.connector_auth import router as connector_auth_router
from app.api.routes.customers import router as customers_router
from app.api.routes.diner_sessions import router as diner_sessions_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.health import router as health_router
from app.api.routes.fiscal_issuance import router as fiscal_issuance_router
from app.api.routes.locations import router as locations_router
from app.api.routes.menus import router as menus_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.order_drafts import router as order_drafts_router
from app.api.routes.products import router as products_router
from app.api.routes.product_compositions import router as product_compositions_router
from app.api.routes.product_aliases import router as product_aliases_router
from app.api.routes.pricing import router as pricing_router
from app.api.routes.pos_submissions import router as pos_submissions_router
from app.api.routes.preparation import router as preparation_router
from app.api.routes.preparation_delivery import router as preparation_delivery_router
from app.api.routes.resources import router as resources_router
from app.api.routes.restaurant_service_sessions import router as restaurant_service_sessions_router
from app.api.routes.restaurant_orders import router as restaurant_orders_router
from app.api.routes.restaurant_checks import router as restaurant_checks_router
from app.api.routes.restaurant_payments import router as restaurant_payments_router
from app.api.routes.tenants import router as tenants_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RuntimeMiddleware
from app.db.session import DatabaseManager
from app.restaurant.integrations.payments.credentials import MerchantCredentialResolver
from app.restaurant.integrations.payments.registry import PaymentExecutorRegistry
from app.restaurant.integrations.fiscal.credentials import (
    FiscalProviderCredentialResolver,
)
from app.restaurant.integrations.fiscal.artifact_storage import FiscalArtifactStoragePort
from app.restaurant.integrations.fiscal.registry import FiscalProviderRegistry
from app.restaurant.integrations.fiscal.finkok import (
    FinkokFiscalIssuanceAdapter,
    HttpxFinkokSoapTransport,
)


class DatabaseLifecycle(Protocol):
    async def check_connection(self) -> None: ...

    async def dispose(self) -> None: ...


def create_app(
    settings: Settings | None = None,
    database: DatabaseLifecycle | None = None,
    pos_adapters: Mapping[str, object] | None = None,
    payment_executors: Mapping[str, object] | None = None,
    payment_executor_registry: PaymentExecutorRegistry | None = None,
    merchant_credential_resolver: MerchantCredentialResolver | None = None,
    fiscal_providers: Mapping[str, object] | None = None,
    fiscal_provider_registry: FiscalProviderRegistry | None = None,
    fiscal_credential_resolver: FiscalProviderCredentialResolver | None = None,
    fiscal_artifact_storage: FiscalArtifactStoragePort | None = None,
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
    app.state.pos_adapters = dict(pos_adapters or {})
    app.state.payment_executor_registry = (
        payment_executor_registry or PaymentExecutorRegistry(payment_executors)
    )
    app.state.merchant_credential_resolver = merchant_credential_resolver
    if fiscal_provider_registry is not None:
        app.state.fiscal_provider_registry = fiscal_provider_registry
    else:
        configured_fiscal_providers = dict(fiscal_providers or {})
        configured_fiscal_providers.setdefault(
            'FINKOK',
            FinkokFiscalIssuanceAdapter(
                transport=HttpxFinkokSoapTransport(
                    endpoint=runtime_settings.finkok_service_endpoint,
                    connect_timeout_seconds=(
                        runtime_settings.finkok_connect_timeout_seconds
                    ),
                    read_timeout_seconds=(
                        runtime_settings.finkok_read_timeout_seconds
                    ),
                )
            ),
        )
        app.state.fiscal_provider_registry = FiscalProviderRegistry(
            configured_fiscal_providers
        )
    app.state.fiscal_credential_resolver = fiscal_credential_resolver
    app.state.fiscal_artifact_storage = fiscal_artifact_storage
    app.add_middleware(RuntimeMiddleware)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(connector_auth_router)
    app.include_router(connector_api_router)
    app.include_router(connector_admin_router)
    app.include_router(tenants_router)
    app.include_router(organizations_router)
    app.include_router(locations_router)
    app.include_router(resources_router)
    app.include_router(cash_sessions_router)
    app.include_router(restaurant_service_sessions_router)
    app.include_router(diner_sessions_router)
    app.include_router(restaurant_orders_router)
    app.include_router(restaurant_checks_router)
    app.include_router(restaurant_payments_router)
    app.include_router(billing_router)
    app.include_router(fiscal_issuance_router)
    app.include_router(pos_submissions_router)
    app.include_router(preparation_router)
    app.include_router(preparation_delivery_router)
    app.include_router(customers_router)
    app.include_router(conversations_router)
    app.include_router(order_drafts_router)
    app.include_router(products_router)
    app.include_router(product_compositions_router)
    app.include_router(product_aliases_router)
    app.include_router(pricing_router)
    app.include_router(menus_router)
    return app
