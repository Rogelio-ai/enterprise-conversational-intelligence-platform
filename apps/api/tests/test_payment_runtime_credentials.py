from __future__ import annotations

import asyncio

import pytest
from pydantic import SecretStr

from app.main import create_app
from app.restaurant.integrations.payments.credentials import (
    BoundMerchantCredentialResolver,
    MerchantCredentialContext,
)
from app.restaurant.payments.errors import MerchantCredentialResolutionError


PRIVATE_KEY = 'runtime-conekta-test-private-key-never-log'
BINDING = 'pilot-location-conekta-test'


def _context(
    *, adapter_kind: str = 'CONEKTA', credential_binding: str = BINDING
) -> MerchantCredentialContext:
    return MerchantCredentialContext(
        tenant_id=1,
        organization_id=2,
        location_id=3,
        executor_configuration_id=4,
        adapter_kind=adapter_kind,
        credential_binding=credential_binding,
        operation_reference='5',
    )


def test_bound_runtime_resolver_requires_exact_adapter_and_binding() -> None:
    resolver = BoundMerchantCredentialResolver(
        adapter_kind='CONEKTA',
        credential_binding=BINDING,
        credential=SecretStr(PRIVATE_KEY),
    )

    credential = asyncio.run(resolver.resolve(context=_context()))

    assert credential.value.get_secret_value() == PRIVATE_KEY
    for context in (
        _context(adapter_kind='OTHER'),
        _context(credential_binding='foreign-location-binding'),
    ):
        with pytest.raises(MerchantCredentialResolutionError):
            asyncio.run(resolver.resolve(context=context))
    assert PRIVATE_KEY not in repr(resolver)
    assert BINDING not in repr(resolver)


def test_test_settings_wire_runtime_resolver_without_exposing_secret(
    settings, database,
) -> None:
    configured = settings.model_copy(update={
        'conekta_environment': 'test',
        'conekta_credential_binding': BINDING,
        'conekta_private_key': SecretStr(PRIVATE_KEY),
    })

    app = create_app(settings=configured, database=database)
    resolver = app.state.merchant_credential_resolver
    credential = asyncio.run(resolver.resolve(context=_context()))

    assert credential.value.get_secret_value() == PRIVATE_KEY
    assert PRIVATE_KEY not in repr(app.state.settings)
    assert PRIVATE_KEY not in repr(resolver)


def test_default_runtime_has_no_merchant_secret_resolver(settings, database) -> None:
    app = create_app(settings=settings, database=database)
    assert app.state.merchant_credential_resolver is None
