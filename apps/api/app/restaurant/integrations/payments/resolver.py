from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    LocationPaymentExecutorCapability,
    LocationPaymentExecutorConfiguration,
)
from app.restaurant.integrations.payments.registry import PaymentExecutorRegistry
from app.restaurant.payments import errors


class PaymentExecutorSelectionMode(StrEnum):
    EXPLICIT = 'EXPLICIT'
    AUTO = 'AUTO'


@dataclass(frozen=True)
class ResolvedPaymentExecutor:
    configuration: LocationPaymentExecutorConfiguration
    executor: object


class PaymentExecutorResolver:
    """Select persisted executor configuration inside a trusted restaurant scope."""

    def __init__(self, db: AsyncSession, registry: PaymentExecutorRegistry) -> None:
        self._db = db
        self._registry = registry

    async def resolve(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        method_category: str,
        currency: str,
        selection_mode: PaymentExecutorSelectionMode | str,
        executor_key: str | None = None,
    ) -> ResolvedPaymentExecutor:
        method = method_category.strip().upper()
        canonical_currency = currency.strip().upper()
        if method == 'CASH':
            raise errors.UnsupportedPaymentExecutorMethodError(
                'Cash payments use the local cash path and do not resolve an executor'
            )
        try:
            mode = PaymentExecutorSelectionMode(selection_mode)
        except (TypeError, ValueError) as exc:
            raise errors.InvalidPaymentExecutorSelectionError(
                'Payment executor selection mode must be EXPLICIT or AUTO'
            ) from exc

        if mode is PaymentExecutorSelectionMode.EXPLICIT:
            if not executor_key or not executor_key.strip():
                raise errors.InvalidPaymentExecutorSelectionError(
                    'Explicit payment executor selection requires an executor key'
                )
            configuration = await self._resolve_explicit_configuration(
                tenant_id=tenant_id,
                organization_id=organization_id,
                location_id=location_id,
                executor_key=executor_key.strip(),
                method_category=method,
                currency=canonical_currency,
            )
        else:
            if executor_key is not None:
                raise errors.InvalidPaymentExecutorSelectionError(
                    'AUTO payment executor selection does not accept an executor key'
                )
            configuration = await self._resolve_auto_configuration(
                tenant_id=tenant_id,
                organization_id=organization_id,
                location_id=location_id,
                method_category=method,
                currency=canonical_currency,
            )
        return self._resolved(configuration)

    async def resolve_historical(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        executor_configuration_id: int,
    ) -> ResolvedPaymentExecutor:
        configuration = await self._db.scalar(
            select(LocationPaymentExecutorConfiguration).where(
                LocationPaymentExecutorConfiguration.id == executor_configuration_id,
                LocationPaymentExecutorConfiguration.tenant_id == tenant_id,
                LocationPaymentExecutorConfiguration.organization_id == organization_id,
                LocationPaymentExecutorConfiguration.location_id == location_id,
            )
        )
        if configuration is None:
            raise errors.PaymentExecutorConfigurationNotFoundError(
                'Historical payment executor configuration was not found in scope'
            )
        return self._resolved(configuration)

    async def resolve_for_execution(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        executor_configuration_id: int,
        method_category: str,
        currency: str,
    ) -> ResolvedPaymentExecutor:
        """Revalidate an exact durable binding before a new external call."""
        method = method_category.strip().upper()
        canonical_currency = currency.strip().upper()
        configuration = await self._db.scalar(
            select(LocationPaymentExecutorConfiguration).where(
                LocationPaymentExecutorConfiguration.id == executor_configuration_id,
                LocationPaymentExecutorConfiguration.tenant_id == tenant_id,
                LocationPaymentExecutorConfiguration.organization_id == organization_id,
                LocationPaymentExecutorConfiguration.location_id == location_id,
            ).execution_options(populate_existing=True)
        )
        if configuration is None:
            raise errors.PaymentExecutorConfigurationNotFoundError(
                'Bound payment executor configuration was not found in scope'
            )
        if configuration.status != 'ACTIVE':
            raise errors.PaymentExecutorConfigurationInactiveError(
                'Bound payment executor configuration is inactive'
            )
        capability = await self._db.scalar(
            select(LocationPaymentExecutorCapability.id).where(
                LocationPaymentExecutorCapability.executor_configuration_id
                == configuration.id,
                LocationPaymentExecutorCapability.tenant_id == tenant_id,
                LocationPaymentExecutorCapability.organization_id == organization_id,
                LocationPaymentExecutorCapability.location_id == location_id,
                LocationPaymentExecutorCapability.method_category == method,
                LocationPaymentExecutorCapability.currency == canonical_currency,
            )
        )
        if capability is None:
            raise errors.UnsupportedPaymentExecutorCapabilityError(
                'Bound payment executor does not support the payment method and currency'
            )
        return self._resolved(configuration)

    async def list_available(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        method_category: str,
        currency: str,
    ) -> tuple[ResolvedPaymentExecutor, ...]:
        method = method_category.strip().upper()
        canonical_currency = currency.strip().upper()
        if method == 'CASH':
            return ()
        configurations = tuple((await self._db.execute(
            select(LocationPaymentExecutorConfiguration)
            .join(
                LocationPaymentExecutorCapability,
                LocationPaymentExecutorCapability.executor_configuration_id
                == LocationPaymentExecutorConfiguration.id,
            )
            .where(
                LocationPaymentExecutorConfiguration.tenant_id == tenant_id,
                LocationPaymentExecutorConfiguration.organization_id == organization_id,
                LocationPaymentExecutorConfiguration.location_id == location_id,
                LocationPaymentExecutorConfiguration.status == 'ACTIVE',
                LocationPaymentExecutorCapability.tenant_id == tenant_id,
                LocationPaymentExecutorCapability.organization_id == organization_id,
                LocationPaymentExecutorCapability.location_id == location_id,
                LocationPaymentExecutorCapability.method_category == method,
                LocationPaymentExecutorCapability.currency == canonical_currency,
            )
            .order_by(
                LocationPaymentExecutorConfiguration.selection_priority,
                LocationPaymentExecutorConfiguration.id,
            )
        )).scalars().all())
        available: list[ResolvedPaymentExecutor] = []
        for configuration in configurations:
            try:
                available.append(self._resolved(configuration))
            except errors.PaymentExecutorAdapterNotRegisteredError:
                continue
        return tuple(available)

    async def _resolve_explicit_configuration(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        executor_key: str,
        method_category: str,
        currency: str,
    ) -> LocationPaymentExecutorConfiguration:
        configuration = await self._db.scalar(
            select(LocationPaymentExecutorConfiguration).where(
                LocationPaymentExecutorConfiguration.tenant_id == tenant_id,
                LocationPaymentExecutorConfiguration.organization_id == organization_id,
                LocationPaymentExecutorConfiguration.location_id == location_id,
                LocationPaymentExecutorConfiguration.executor_key == executor_key,
            )
        )
        if configuration is None:
            raise errors.PaymentExecutorConfigurationNotFoundError(
                'Payment executor configuration was not found in scope'
            )
        if configuration.status != 'ACTIVE':
            raise errors.PaymentExecutorConfigurationInactiveError(
                'Payment executor configuration is inactive'
            )

        capabilities = tuple((await self._db.execute(
            select(
                LocationPaymentExecutorCapability.method_category,
                LocationPaymentExecutorCapability.currency,
            ).where(
                LocationPaymentExecutorCapability.executor_configuration_id == configuration.id,
                LocationPaymentExecutorCapability.tenant_id == tenant_id,
                LocationPaymentExecutorCapability.organization_id == organization_id,
                LocationPaymentExecutorCapability.location_id == location_id,
            )
        )).all())
        method_capabilities = tuple(
            capability for capability in capabilities
            if capability.method_category == method_category
        )
        if not method_capabilities:
            raise errors.UnsupportedPaymentExecutorMethodError(
                'Payment executor does not support the requested method'
            )
        if not any(capability.currency == currency for capability in method_capabilities):
            raise errors.UnsupportedPaymentExecutorCurrencyError(
                'Payment executor does not support the requested currency for this method'
            )
        return configuration

    async def _resolve_auto_configuration(
        self,
        *,
        tenant_id: int,
        organization_id: int,
        location_id: int,
        method_category: str,
        currency: str,
    ) -> LocationPaymentExecutorConfiguration:
        configuration = await self._db.scalar(
            select(LocationPaymentExecutorConfiguration)
            .join(
                LocationPaymentExecutorCapability,
                LocationPaymentExecutorCapability.executor_configuration_id
                == LocationPaymentExecutorConfiguration.id,
            )
            .where(
                LocationPaymentExecutorConfiguration.tenant_id == tenant_id,
                LocationPaymentExecutorConfiguration.organization_id == organization_id,
                LocationPaymentExecutorConfiguration.location_id == location_id,
                LocationPaymentExecutorConfiguration.status == 'ACTIVE',
                LocationPaymentExecutorCapability.tenant_id == tenant_id,
                LocationPaymentExecutorCapability.organization_id == organization_id,
                LocationPaymentExecutorCapability.location_id == location_id,
                LocationPaymentExecutorCapability.method_category == method_category,
                LocationPaymentExecutorCapability.currency == currency,
            )
            .order_by(
                LocationPaymentExecutorConfiguration.selection_priority,
                LocationPaymentExecutorConfiguration.id,
            )
            .limit(1)
        )
        if configuration is None:
            raise errors.NoEligiblePaymentExecutorError(
                'No active payment executor supports the requested method and currency'
            )
        return configuration

    def _resolved(
        self, configuration: LocationPaymentExecutorConfiguration
    ) -> ResolvedPaymentExecutor:
        return ResolvedPaymentExecutor(
            configuration=configuration,
            executor=self._registry.resolve(configuration.adapter_kind),
        )
