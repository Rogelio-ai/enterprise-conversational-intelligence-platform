from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.restaurant.integrations.payments.registry import PaymentExecutorRegistry
from app.restaurant.integrations.payments.resolver import (
    PaymentExecutorResolver,
    PaymentExecutorSelectionMode,
)
from app.restaurant.payments import errors


@dataclass(frozen=True)
class PaymentExecutorClientConfiguration:
    provider: str
    tokenization_mode: str
    public_key: str
    locale: str


class PaymentExecutorClientConfigurationResolver:
    """Resolve an allow-listed browser configuration inside a trusted scope."""

    def __init__(self, db: AsyncSession, registry: PaymentExecutorRegistry) -> None:
        self._db = db
        self._registry = registry

    async def resolve_conekta_card(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        executor_key: str,
        currency: str,
    ) -> PaymentExecutorClientConfiguration:
        resolved = await PaymentExecutorResolver(self._db, self._registry).resolve(
            tenant_id=tenant_id,
            organization_id=organization_id,
            location_id=location_id,
            method_category='CARD',
            currency=currency,
            selection_mode=PaymentExecutorSelectionMode.EXPLICIT,
            executor_key=executor_key,
        )
        configuration = resolved.configuration
        if configuration.adapter_kind.strip().upper() != 'CONEKTA':
            raise errors.PaymentClientConfigurationUnavailableError(
                'Client configuration is unavailable for this payment executor'
            )
        public_key = configuration.client_public_key
        if public_key is None or not public_key.strip():
            raise errors.PaymentClientConfigurationUnavailableError(
                'Client configuration is unavailable for this payment executor'
            )
        return PaymentExecutorClientConfiguration(
            provider='CONEKTA',
            tokenization_mode='WEB_TOKENIZER',
            public_key=public_key.strip(),
            locale='es',
        )
