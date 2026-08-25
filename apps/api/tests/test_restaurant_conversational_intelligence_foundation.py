from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect
import logging

import pymysql
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.bootstrap_admin import CORE_PERMISSIONS
from app.core.intelligence import TrustedIntelligenceContext
from app.db.session import DatabaseManager
from app.models import IntelligenceDerivation, RestaurantMessageIntent
from app.restaurant.intelligence.contracts import (
    RESTAURANT_INTENT_SCHEMA_KEY,
    RESTAURANT_INTENT_SCHEMA_VERSION,
    RestaurantIntentCandidate,
    RestaurantIntentCode,
    RestaurantMessageUnderstandingPort,
    RestaurantUnderstandingResult,
)
from app.restaurant.intelligence.errors import (
    InvalidUnderstandingResultError,
    KnowledgeNotFoundError,
    KnowledgeUnavailableError,
    UnderstandingUnavailableError,
)
from app.restaurant.intelligence.service import understand_message
from app.restaurant.intelligence.testing import DeterministicRestaurantUnderstandingFake
from app.restaurant.knowledge import service as knowledge


def _execute(connection, statement, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        return int(cursor.lastrowid)


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    organization_id: int
    location_id: int
    other_location_id: int
    resource_id: int
    conversation_id: int
    participant_id: int
    prior_message_id: int
    source_message_id: int
    product_id: int
    inactive_product_id: int
    menu_id: int


def _scope(connection, prefix: str) -> Scope:
    tenant_id = _execute(
        connection,
        "INSERT INTO tenants (name,slug,status) VALUES ('WS11 Tenant',%s,'ACTIVE')",
        (prefix,),
    )
    organization_id = _execute(
        connection,
        "INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'ORG','Org','ACTIVE')",
        (tenant_id,),
    )
    location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC-A','Location A','UTC','ACTIVE')",
        (tenant_id, organization_id),
    )
    other_location_id = _execute(
        connection,
        "INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC-B','Location B','UTC','ACTIVE')",
        (tenant_id, organization_id),
    )
    resource_id = _execute(
        connection,
        "INSERT INTO resources (tenant_id,location_id,code,name,resource_type,status) VALUES (%s,%s,'TABLE-1','Table 1','TABLE','ACTIVE')",
        (tenant_id, location_id),
    )
    conversation_id = _execute(
        connection,
        "INSERT INTO conversations (tenant_id,organization_id,location_id,resource_id,channel,status,default_language,next_message_sequence) VALUES (%s,%s,%s,%s,'IN_PERSON_DIGITAL','ACTIVE','es-MX',3)",
        (tenant_id, organization_id, location_id, resource_id),
    )
    participant_id = _execute(
        connection,
        "INSERT INTO conversation_participants (tenant_id,conversation_id,participant_type,preferred_language) VALUES (%s,%s,'CUSTOMER','es-MX')",
        (tenant_id, conversation_id),
    )
    prior_message_id = _execute(
        connection,
        "INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text,language,language_source) VALUES (%s,%s,%s,1,'TEXT',%s,'es-MX','DECLARED')",
        (tenant_id, conversation_id, participant_id, '¿Qué desayunos tienen? 🥐'),
    )
    source_message_id = _execute(
        connection,
        "INSERT INTO conversation_messages (tenant_id,conversation_id,participant_id,sequence_number,modality,content_text,language,language_source) VALUES (%s,%s,%s,2,'VOICE',%s,'en-US','DETECTED')",
        (tenant_id, conversation_id, participant_id, 'Chilaquiles, and how much are they?'),
    )
    product_id = _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,description,status,source) VALUES (%s,%s,'Chilaquiles','Canonical breakfast','ACTIVE','PLATFORM')",
        (tenant_id, organization_id),
    )
    inactive_product_id = _execute(
        connection,
        "INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Inactive Dish','INACTIVE','PLATFORM')",
        (tenant_id, organization_id),
    )
    menu_id = _execute(
        connection,
        "INSERT INTO menus (tenant_id,organization_id,name,status) VALUES (%s,%s,'Breakfast','ACTIVE')",
        (tenant_id, organization_id),
    )
    _execute(
        connection,
        "INSERT INTO menu_locations (tenant_id,organization_id,menu_id,location_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')",
        (tenant_id, organization_id, menu_id, location_id),
    )
    section_id = _execute(
        connection,
        "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,display_order,status) VALUES (%s,%s,%s,'Mains',1,'ACTIVE')",
        (tenant_id, organization_id, menu_id),
    )
    _execute(
        connection,
        "INSERT INTO menu_items (tenant_id,organization_id,menu_id,section_id,product_id,display_order,status) VALUES (%s,%s,%s,%s,%s,1,'ACTIVE')",
        (tenant_id, organization_id, menu_id, section_id, product_id),
    )
    inactive_section_id = _execute(
        connection,
        "INSERT INTO menu_sections (tenant_id,organization_id,menu_id,name,display_order,status) VALUES (%s,%s,%s,'Hidden',2,'INACTIVE')",
        (tenant_id, organization_id, menu_id),
    )
    _execute(
        connection,
        "INSERT INTO menu_items (tenant_id,organization_id,menu_id,section_id,product_id,display_order,status) VALUES (%s,%s,%s,%s,%s,2,'ACTIVE')",
        (tenant_id, organization_id, menu_id, inactive_section_id, inactive_product_id),
    )
    return Scope(
        tenant_id,
        organization_id,
        location_id,
        other_location_id,
        resource_id,
        conversation_id,
        participant_id,
        prior_message_id,
        source_message_id,
        product_id,
        inactive_product_id,
        menu_id,
    )


def _result(*intents: RestaurantIntentCandidate) -> RestaurantUnderstandingResult:
    return RestaurantUnderstandingResult(
        schema_key=RESTAURANT_INTENT_SCHEMA_KEY,
        schema_version=RESTAURANT_INTENT_SCHEMA_VERSION,
        producer_key='deterministic-test-fake',
        producer_version='1',
        intents=tuple(intents),
    )


def test_contract_taxonomy_confidence_and_provider_neutrality() -> None:
    assert {item.value for item in RestaurantIntentCode} == {
        'MENU_QUERY',
        'PRODUCT_QUERY',
        'PRICE_QUERY',
        'PROMOTION_QUERY',
        'ORDER_EXPRESSION',
        'HUMAN_ASSISTANCE_REQUEST',
        'UNKNOWN',
    }
    assert isinstance(DeterministicRestaurantUnderstandingFake(), RestaurantMessageUnderstandingPort)
    assert RestaurantIntentCandidate(RestaurantIntentCode.UNKNOWN).confidence is None
    assert RestaurantIntentCandidate(RestaurantIntentCode.PRICE_QUERY, Decimal('0')).confidence == 0
    assert RestaurantIntentCandidate(RestaurantIntentCode.PRICE_QUERY, Decimal('1')).confidence == 1
    for invalid in (Decimal('-0.0001'), Decimal('1.0001'), Decimal('0.00001')):
        with pytest.raises(ValueError):
            RestaurantIntentCandidate(RestaurantIntentCode.UNKNOWN, invalid)
    with pytest.raises(ValueError):
        RestaurantIntentCandidate('GREETING')  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        RestaurantIntentCandidate(RestaurantIntentCode.UNKNOWN, 0.5)  # type: ignore[arg-type]
    source = inspect.getsource(inspect.getmodule(RestaurantMessageUnderstandingPort))
    assert all(vendor not in source.casefold() for vendor in ('openai', 'anthropic', 'google'))


def test_trusted_context_validation() -> None:
    context = TrustedIntelligenceContext(1, 2, 3, 4, 5, 6, 7, ' correlation ')
    assert context.correlation_id == 'correlation'
    with pytest.raises(ValueError):
        TrustedIntelligenceContext(1, 2, None, 4, 5, 6, 7, 'correlation')


def test_understanding_persists_ordered_provenance_reprocesses_and_logs_safely(
    integration_settings, sql_connection, caplog
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    result = _result(
        RestaurantIntentCandidate(RestaurantIntentCode.PRODUCT_QUERY, Decimal('0.8000')),
        RestaurantIntentCandidate(RestaurantIntentCode.PRICE_QUERY),
    )
    fake = DeterministicRestaurantUnderstandingFake(result=result)

    async def scenario():
        manager = DatabaseManager(integration_settings)
        try:
            values = []
            for _ in range(2):
                async with manager.session_factory() as db:
                    values.append(
                        await understand_message(
                            db,
                            fake,
                            tenant_id=scope.tenant_id,
                            conversation_id=scope.conversation_id,
                            source_message_id=scope.source_message_id,
                            correlation_id='ws11-correlation',
                            history_limit=10,
                        )
                    )
            async with manager.session_factory() as db:
                derivations = await db.scalar(
                    select(func.count(IntelligenceDerivation.id)).where(
                        IntelligenceDerivation.tenant_id == scope.tenant_id
                    )
                )
                intents = await db.scalar(
                    select(func.count(RestaurantMessageIntent.id)).where(
                        RestaurantMessageIntent.tenant_id == scope.tenant_id
                    )
                )
            return values, derivations, intents
        finally:
            await manager.dispose()

    with caplog.at_level(logging.INFO):
        values, derivation_count, intent_count = asyncio.run(scenario())
    assert values[0].derivation_id != values[1].derivation_id
    assert derivation_count == 2 and intent_count == 4
    assert [item.ordinal for item in values[0].intents] == [1, 2]
    assert [item.intent_code for item in values[0].intents] == ['PRODUCT_QUERY', 'PRICE_QUERY']
    assert values[0].schema_version == '1' and values[0].correlation_id == 'ws11-correlation'
    assert len(fake.requests) == 2
    request = fake.requests[0]
    assert request.context.organization_id == scope.organization_id
    assert request.context.location_id == scope.location_id
    assert request.context.resource_id == scope.resource_id
    assert request.context.participant_id == scope.participant_id
    assert [item.message_id for item in request.history] == [scope.prior_message_id]
    assert request.history[0].content_text == '¿Qué desayunos tienen? 🥐'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT content_text FROM conversation_messages WHERE id=%s',
            (scope.source_message_id,),
        )
        assert cursor.fetchone()['content_text'] == 'Chilaquiles, and how much are they?'
    assert 'Chilaquiles, and how much are they?' not in caplog.text
    assert '¿Qué desayunos tienen?' not in caplog.text


def test_unknown_and_stable_understanding_failures(integration_settings, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)

    async def execute(fake):
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await understand_message(
                    db,
                    fake,
                    tenant_id=scope.tenant_id,
                    conversation_id=scope.conversation_id,
                    source_message_id=scope.source_message_id,
                    correlation_id='failure-correlation',
                )
        finally:
            await manager.dispose()

    unknown = asyncio.run(
        execute(
            DeterministicRestaurantUnderstandingFake(
                result=_result(RestaurantIntentCandidate(RestaurantIntentCode.UNKNOWN))
            )
        )
    )
    assert unknown.intents[0].confidence is None
    with pytest.raises(UnderstandingUnavailableError):
        asyncio.run(
            execute(
                DeterministicRestaurantUnderstandingFake(
                    failure=UnderstandingUnavailableError('timeout')
                )
            )
        )
    with pytest.raises(InvalidUnderstandingResultError):
        asyncio.run(
            execute(
                DeterministicRestaurantUnderstandingFake(
                    result=RestaurantUnderstandingResult(
                        schema_key='wrong.schema',
                        schema_version='1',
                        producer_key='fake',
                        producer_version='1',
                        intents=(RestaurantIntentCandidate(RestaurantIntentCode.UNKNOWN),),
                    )
                )
            )
        )

    class InvalidFake:
        async def understand(self, request):
            return object()

    with pytest.raises(InvalidUnderstandingResultError):
        asyncio.run(execute(InvalidFake()))


def test_knowledge_database_failures_map_to_stable_error() -> None:
    class BrokenDatabase:
        async def scalar(self, statement):
            raise SQLAlchemyError('database unavailable')

    with pytest.raises(KnowledgeUnavailableError):
        asyncio.run(
            knowledge.get_product(
                BrokenDatabase(),  # type: ignore[arg-type]
                tenant_id=1,
                organization_id=1,
                product_id=1,
            )
        )


def test_no_public_intelligence_api_or_rbac_permission(settings, database) -> None:
    from app.main import create_app

    paths = create_app(settings=settings, database=database).openapi()['paths']
    assert all('intelligence' not in path and 'analyze' not in path for path in paths)
    assert all(not code.startswith(('intelligence.', 'ai.', 'provider.')) for code in CORE_PERMISSIONS)


def test_service_rejects_cross_tenant_and_cross_conversation(
    integration_settings, sql_connection
) -> None:
    connection, prefix = sql_connection
    first = _scope(connection, prefix)
    second = _scope(connection, f'{prefix}-other')
    fake = DeterministicRestaurantUnderstandingFake(
        result=_result(RestaurantIntentCandidate(RestaurantIntentCode.UNKNOWN))
    )

    async def execute(tenant_id, conversation_id, message_id):
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await understand_message(
                    db,
                    fake,
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    source_message_id=message_id,
                    correlation_id='scope-correlation',
                )
        finally:
            await manager.dispose()

    with pytest.raises(InvalidUnderstandingResultError):
        asyncio.run(execute(first.tenant_id, first.conversation_id, second.source_message_id))
    with pytest.raises(InvalidUnderstandingResultError):
        asyncio.run(execute(first.tenant_id, second.conversation_id, first.source_message_id))


def test_database_rejects_cross_scope_duplicate_ordinal_and_invalid_confidence(
    sql_connection,
) -> None:
    connection, prefix = sql_connection
    first = _scope(connection, prefix)
    second = _scope(connection, f'{prefix}-other')
    values = (
        first.tenant_id,
        first.conversation_id,
        first.source_message_id,
        'restaurant.message_intents',
        '1',
        'raw-test',
        '1',
        'raw-correlation',
    )
    connection.begin()
    try:
        derivation_id = _execute(
            connection,
            'INSERT INTO intelligence_derivations (tenant_id,conversation_id,source_message_id,schema_key,schema_version,producer_key,producer_version,correlation_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
            values,
        )
        _execute(
            connection,
            "INSERT INTO restaurant_message_intents (tenant_id,derivation_id,ordinal,intent_code,confidence) VALUES (%s,%s,1,'UNKNOWN',NULL)",
            (first.tenant_id, derivation_id),
        )
        invalid = (
            (
                'INSERT INTO intelligence_derivations (tenant_id,conversation_id,source_message_id,schema_key,schema_version,producer_key,producer_version,correlation_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                (first.tenant_id, first.conversation_id, second.source_message_id, *values[3:]),
            ),
            (
                'INSERT INTO intelligence_derivations (tenant_id,conversation_id,source_message_id,schema_key,schema_version,producer_key,producer_version,correlation_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                (first.tenant_id, second.conversation_id, first.source_message_id, *values[3:]),
            ),
            (
                "INSERT INTO restaurant_message_intents (tenant_id,derivation_id,ordinal,intent_code) VALUES (%s,%s,2,'UNKNOWN')",
                (second.tenant_id, derivation_id),
            ),
            (
                "INSERT INTO restaurant_message_intents (tenant_id,derivation_id,ordinal,intent_code,confidence) VALUES (%s,%s,2,'UNKNOWN',1.0001)",
                (first.tenant_id, derivation_id),
            ),
            (
                "INSERT INTO restaurant_message_intents (tenant_id,derivation_id,ordinal,intent_code) VALUES (%s,%s,1,'PRICE_QUERY')",
                (first.tenant_id, derivation_id),
            ),
        )
        for statement, parameters in invalid:
            with pytest.raises((pymysql.err.IntegrityError, pymysql.err.OperationalError)):
                _execute(connection, statement, parameters)
    finally:
        connection.rollback()


def test_physical_intelligence_schema_is_portable_and_append_oriented(sql_connection) -> None:
    connection, _ = sql_connection
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT TABLE_NAME, ENGINE, TABLE_COLLATION
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA=DATABASE()
              AND TABLE_NAME IN ('intelligence_derivations','restaurant_message_intents')
            ORDER BY TABLE_NAME
            '''
        )
        tables = cursor.fetchall()
        assert [(row['TABLE_NAME'], row['ENGINE'], row['TABLE_COLLATION']) for row in tables] == [
            ('intelligence_derivations', 'InnoDB', 'utf8mb4_unicode_ci'),
            ('restaurant_message_intents', 'InnoDB', 'utf8mb4_unicode_ci'),
        ]
        cursor.execute(
            '''
            SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=DATABASE()
              AND TABLE_NAME IN ('intelligence_derivations','restaurant_message_intents')
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            '''
        )
        columns = {
            (row['TABLE_NAME'], row['COLUMN_NAME']): (row['COLUMN_TYPE'], row['IS_NULLABLE'])
            for row in cursor.fetchall()
        }
    # MariaDB 10.6 reports the legacy integer display width while MySQL 8.4
    # omits it; both describe the same BIGINT storage contract.
    assert columns[('intelligence_derivations', 'id')][0] in {'bigint', 'bigint(20)'}
    assert columns[('intelligence_derivations', 'created_at')][0] == 'datetime'
    assert columns[('restaurant_message_intents', 'confidence')] == ('decimal(5,4)', 'YES')
    assert ('intelligence_derivations', 'updated_at') not in columns
    assert ('restaurant_message_intents', 'updated_at') not in columns
    assert all('json' not in column_type for column_type, _ in columns.values())


def test_read_only_knowledge_filters_catalog_and_reuses_price_promotion_rules(
    integration_settings, sql_connection
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _execute(
        connection,
        "INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,130.0000,'MXN','ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, scope.product_id, scope.location_id),
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    promotion_id = _execute(
        connection,
        "INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,status,source) VALUES (%s,%s,'Breakfast Promo','PERCENTAGE_DISCOUNT',10,NULL,%s,%s,1,'ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, now - timedelta(hours=1), now + timedelta(hours=1)),
    )
    _execute(
        connection,
        "INSERT INTO promotion_products (tenant_id,organization_id,promotion_id,product_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')",
        (scope.tenant_id, scope.organization_id, promotion_id, scope.product_id),
    )

    async def scenario():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                menus = await knowledge.get_location_menu(
                    db,
                    tenant_id=scope.tenant_id,
                    organization_id=scope.organization_id,
                    location_id=scope.location_id,
                )
                products = await knowledge.find_products(
                    db,
                    tenant_id=scope.tenant_id,
                    organization_id=scope.organization_id,
                )
                product = await knowledge.get_product(
                    db,
                    tenant_id=scope.tenant_id,
                    organization_id=scope.organization_id,
                    product_id=scope.product_id,
                )
                price = await knowledge.get_current_price(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=scope.product_id,
                    location_id=scope.location_id,
                )
                promotions = await knowledge.find_applicable_promotions(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=scope.product_id,
                    location_id=scope.location_id,
                    effective_at=datetime.now(UTC),
                )
                return menus, products, product, price, promotions
        finally:
            await manager.dispose()

    before = {}
    with connection.cursor() as cursor:
        for table in ('products', 'menus', 'product_prices', 'promotions', 'conversations'):
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (scope.tenant_id,))
            before[table] = cursor.fetchone()['count']
    menus, products, product, price, promotions = asyncio.run(scenario())
    assert [item.id for item in products] == [scope.product_id]
    assert product.id == scope.product_id and not hasattr(product, 'available')
    assert len(menus) == 1 and [section.name for section in menus[0].sections] == ['Mains']
    assert [item.product.id for item in menus[0].sections[0].items] == [scope.product_id]
    assert price.amount == Decimal('130.0000') and price.location_id == scope.location_id
    assert len(promotions) == 1 and promotions[0].promotion_id == promotion_id
    assert not hasattr(promotions[0], 'effective_price')
    with connection.cursor() as cursor:
        for table, count in before.items():
            cursor.execute(f'SELECT COUNT(*) AS count FROM {table} WHERE tenant_id=%s', (scope.tenant_id,))
            assert cursor.fetchone()['count'] == count


def test_current_price_never_falls_back_to_another_location(
    integration_settings, sql_connection
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix)
    _execute(
        connection,
        "INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,130.0000,'MXN','ACTIVE','PLATFORM')",
        (scope.tenant_id, scope.organization_id, scope.product_id, scope.location_id),
    )

    async def scenario():
        manager = DatabaseManager(integration_settings)
        try:
            async with manager.session_factory() as db:
                return await knowledge.get_current_price(
                    db,
                    tenant_id=scope.tenant_id,
                    product_id=scope.product_id,
                    location_id=scope.other_location_id,
                )
        finally:
            await manager.dispose()

    with pytest.raises(KnowledgeNotFoundError, match='Current Price not found'):
        asyncio.run(scenario())
