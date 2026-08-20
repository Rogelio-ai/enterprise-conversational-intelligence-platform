from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
import inspect

import pymysql
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import DatabaseManager
from app.main import create_app
from app.models import ProductPrice
from app.restaurant.integrations.pos.contracts import ExternalPrice, LocationScopedPosRequestContext
from app.restaurant.integrations.pos.errors import PosMappingError
from app.restaurant.pricing.service import PriceAuthorityConflictError, resolve_external_price

PASSWORD = 'Test Password 123!'
PERMISSIONS = ('pricing.read', 'pricing.manage', 'promotion.read', 'promotion.manage')


def _execute(connection, sql, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters)
        return int(cursor.lastrowid)


def _permission(connection, role_id, code):
    _execute(connection, 'INSERT IGNORE INTO permissions (code, description) VALUES (%s, %s)', (code, code))
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM permissions WHERE code=%s', (code,)); permission_id = cursor.fetchone()['id']
    _execute(connection, 'INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s,%s)', (role_id, permission_id))


@dataclass(frozen=True)
class Scope:
    tenant_id: int
    role_id: int
    email: str
    organization_id: int
    location_id: int
    product_id: int


def _scope(connection, prefix, permissions=PERMISSIONS):
    tenant_id=_execute(connection,"INSERT INTO tenants (name,slug,status) VALUES (%s,%s,'ACTIVE')",('Pricing Tenant',prefix))
    email=f'{prefix}@example.test'; user_id=_execute(connection,"INSERT INTO users (email,password_hash,display_name,status) VALUES (%s,%s,'Pricing User','ACTIVE')",(email,hash_password(PASSWORD)))
    membership_id=_execute(connection,"INSERT INTO tenant_memberships (tenant_id,user_id,status) VALUES (%s,%s,'ACTIVE')",(tenant_id,user_id))
    role_id=_execute(connection,"INSERT INTO roles (tenant_id,name,description,status) VALUES (%s,'WS09_TEST','test','ACTIVE')",(tenant_id,))
    _execute(connection,'INSERT INTO membership_roles (tenant_id,membership_id,role_id) VALUES (%s,%s,%s)',(tenant_id,membership_id,role_id))
    for permission in permissions: _permission(connection,role_id,permission)
    organization_id=_execute(connection,"INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'ORG','Org','ACTIVE')",(tenant_id,))
    location_id=_execute(connection,"INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC','Location','UTC','ACTIVE')",(tenant_id,organization_id))
    product_id=_execute(connection,"INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Product','ACTIVE','PLATFORM')",(tenant_id,organization_id))
    return Scope(tenant_id,role_id,email,organization_id,location_id,product_id)


def _headers(client, scope):
    response=client.post('/auth/login',json={'email':scope.email,'password':PASSWORD}); assert response.status_code==200
    return {'Authorization':f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value: yield value


def test_price_permissions_exact_money_crud_lookup_and_boundaries(client, sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix,permissions=()); headers=_headers(client,scope)
    assert client.get(f'/prices?organization_id={scope.organization_id}').status_code==401
    assert client.get(f'/prices?organization_id={scope.organization_id}',headers=headers).status_code==403
    _permission(connection,scope.role_id,'pricing.read')
    assert client.get(f'/prices?organization_id={scope.organization_id}',headers=headers).status_code==200
    assert client.post('/prices',headers=headers,json={}).status_code==403
    _permission(connection,scope.role_id,'pricing.manage')
    payload={'organization_id':scope.organization_id,'product_id':scope.product_id,'location_id':scope.location_id,'amount':'12.3400','currency':' mxn '}
    response=client.post('/prices',headers=headers,json=payload); assert response.status_code==201,response.text
    price=response.json(); assert price['amount']=='12.3400' and price['currency']=='MXN' and price['source']=='PLATFORM' and price['status']=='ACTIVE'
    assert client.post('/prices',headers=headers,json=payload).status_code==409
    assert client.post('/prices',headers=headers,json={**payload,'amount':1.2}).status_code==422
    assert client.post('/prices',headers=headers,json={**payload,'amount':'1.00001'}).status_code==422
    assert client.post('/prices',headers=headers,json={**payload,'currency':'MÉX'}).status_code==422
    current=client.get(f'/products/{scope.product_id}/price?location_id={scope.location_id}',headers=headers); assert current.status_code==200 and current.json()['price_id']==price['id']
    updated=client.patch(f"/prices/{price['id']}",headers=headers,json={'amount':'0.0000','status':'INACTIVE'}); assert updated.status_code==200
    assert client.get(f'/products/{scope.product_id}/price?location_id={scope.location_id}',headers=headers).status_code==404
    assert client.patch(f"/prices/{price['id']}",headers=headers,json={'source':'POS'}).status_code==422
    assert client.patch(f"/prices/{price['id']}",headers=headers,json={'amount':None}).status_code==422
    assert client.patch(f"/prices/{price['id']}",headers=headers,json={}).status_code==422
    assert client.delete(f"/prices/{price['id']}",headers=headers).status_code==405


def test_current_price_does_not_fallback_to_another_location(client, sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix); headers=_headers(client,scope)
    other_location=_execute(connection,"INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'LOC-B','Location B','UTC','ACTIVE')",(scope.tenant_id,scope.organization_id))
    payload={'organization_id':scope.organization_id,'product_id':scope.product_id,'location_id':scope.location_id,'amount':'12.3400','currency':'MXN'}
    assert client.post('/prices',headers=headers,json=payload).status_code==201
    response=client.get(f'/products/{scope.product_id}/price?location_id={other_location}',headers=headers)
    assert response.status_code==404


def test_price_cross_organization_and_raw_database_integrity(client, sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix); headers=_headers(client,scope)
    other_tenant=_scope(connection,f'{prefix}-other')
    other_org=_execute(connection,"INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'OTHER','Other','ACTIVE')",(scope.tenant_id,))
    other_location=_execute(connection,"INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'OTHER','Other','UTC','ACTIVE')",(scope.tenant_id,other_org))
    payload={'organization_id':scope.organization_id,'product_id':scope.product_id,'location_id':other_location,'amount':'1.0000','currency':'USD'}
    assert client.post('/prices',headers=headers,json=payload).status_code==404
    statements=[
        ("INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,-1,'USD','ACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,scope.product_id,scope.location_id)),
        ("INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,1,'usd','ACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,scope.product_id,scope.location_id)),
        ("INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,1,'USD','BROKEN','PLATFORM')",(scope.tenant_id,scope.organization_id,scope.product_id,scope.location_id)),
        ("INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,1,'USD','ACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,scope.product_id,other_location)),
        ("INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,1,'USD','ACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,other_tenant.product_id,scope.location_id)),
        ("INSERT INTO product_prices (tenant_id,organization_id,product_id,location_id,amount,currency,status,source) VALUES (%s,%s,%s,%s,1,'USD','ACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,scope.product_id,other_tenant.location_id)),
    ]
    for statement,parameters in statements:
        with pytest.raises((pymysql.err.IntegrityError,pymysql.err.OperationalError)): _execute(connection,statement,parameters)


def _promotion_payload(scope, **updates):
    now=datetime.now(UTC); value={'organization_id':scope.organization_id,'name':'Lunch','promotion_type':'PERCENTAGE_DISCOUNT','benefit_value':'10.0000','currency':None,'starts_at':(now-timedelta(hours=1)).isoformat(),'ends_at':(now+timedelta(hours=1)).isoformat(),'applies_to_all_locations':True}; value.update(updates); return value


def test_promotion_validation_activation_associations_and_candidates(client,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix); headers=_headers(client,scope)
    response=client.post('/promotions',headers=headers,json=_promotion_payload(scope)); assert response.status_code==201,response.text
    promotion=response.json(); assert promotion['status']=='INACTIVE' and promotion['source']=='PLATFORM'
    invalid=[
        _promotion_payload(scope,promotion_type='BOGO'),
        _promotion_payload(scope,benefit_value='100.0001'),
        _promotion_payload(scope,currency='USD'),
        _promotion_payload(scope,promotion_type='FIXED_AMOUNT_DISCOUNT',currency=None),
        _promotion_payload(scope,starts_at='2026-01-01T00:00:00'),
    ]
    for payload in invalid: assert client.post('/promotions',headers=headers,json=payload).status_code==422
    for field in ('benefit_value','starts_at','ends_at'):
        assert client.patch(f"/promotions/{promotion['id']}",headers=headers,json={field:None}).status_code==422
    assert client.patch(f"/promotions/{promotion['id']}",headers=headers,json={'status':'ACTIVE'}).status_code==409
    association=client.post(f"/promotions/{promotion['id']}/products",headers=headers,json={'product_id':scope.product_id}); assert association.status_code==201
    assert client.patch(f"/promotions/{promotion['id']}",headers=headers,json={'status':'ACTIVE'}).status_code==200
    now=datetime.now(UTC).isoformat(); candidates=client.get('/promotions/applicable',headers=headers,params={'product_id':scope.product_id,'location_id':scope.location_id,'effective_at':now})
    assert candidates.status_code==200,candidates.text; assert [item['promotion_id'] for item in candidates.json()]==[promotion['id']]
    assert {'effective_price','final_price','discount_amount','applied_promotion','best_promotion','stacking','priority'}.isdisjoint(candidates.json()[0])
    assert client.patch(f"/promotions/{promotion['id']}/products/{scope.product_id}",headers=headers,json={'status':'INACTIVE'}).status_code==409
    assert client.delete(f"/promotions/{promotion['id']}",headers=headers).status_code==405


def test_fixed_amount_promotion_exact_money_currency_and_utc(client, sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix); headers=_headers(client,scope)
    starts_at=datetime(2030,1,1,12,0,tzinfo=timezone(timedelta(hours=5,minutes=30)))
    ends_at=starts_at+timedelta(hours=2)
    payload=_promotion_payload(
        scope,
        name='Fixed Lunch',
        promotion_type='FIXED_AMOUNT_DISCOUNT',
        benefit_value='25.5000',
        currency=' mxn ',
        starts_at=starts_at.isoformat(),
        ends_at=ends_at.isoformat(),
    )
    response=client.post('/promotions',headers=headers,json=payload)
    assert response.status_code==201,response.text
    promotion=response.json()
    assert promotion['promotion_type']=='FIXED_AMOUNT_DISCOUNT'
    assert promotion['benefit_value']=='25.5000' and promotion['currency']=='MXN'
    assert promotion['status']=='INACTIVE' and promotion['source']=='PLATFORM'
    assert datetime.fromisoformat(promotion['starts_at'].replace('Z','+00:00'))==starts_at.astimezone(UTC)
    assert datetime.fromisoformat(promotion['ends_at'].replace('Z','+00:00'))==ends_at.astimezone(UTC)
    invalid_values=(
        _promotion_payload(scope,benefit_value=1.5),
        _promotion_payload(scope,benefit_value='1.00001'),
        _promotion_payload(scope,promotion_type='FIXED_AMOUNT_DISCOUNT',currency='US'),
        _promotion_payload(scope,currency='USD'),
    )
    for invalid in invalid_values:
        assert client.post('/promotions',headers=headers,json=invalid).status_code==422
    assert client.post('/promotions',headers=headers,json=_promotion_payload(scope,name='Valid Percentage')).status_code==201


def test_promotion_permission_separation_and_multiple_candidate_order(client,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix,permissions=()); headers=_headers(client,scope)
    assert client.get(f'/promotions?organization_id={scope.organization_id}').status_code==401
    assert client.get(f'/promotions?organization_id={scope.organization_id}',headers=headers).status_code==403
    _permission(connection,scope.role_id,'promotion.read')
    assert client.get(f'/promotions?organization_id={scope.organization_id}',headers=headers).status_code==200
    assert client.post('/promotions',headers=headers,json=_promotion_payload(scope)).status_code==403
    _permission(connection,scope.role_id,'promotion.manage')
    ids=[]
    for name in ('First','Second'):
        promotion=client.post('/promotions',headers=headers,json=_promotion_payload(scope,name=name)).json(); ids.append(promotion['id'])
        client.post(f"/promotions/{promotion['id']}/products",headers=headers,json={'product_id':scope.product_id})
        assert client.patch(f"/promotions/{promotion['id']}",headers=headers,json={'status':'ACTIVE'}).status_code==200
    candidates=client.get('/promotions/applicable',headers=headers,params={'product_id':scope.product_id,'location_id':scope.location_id,'effective_at':datetime.now(UTC).isoformat()})
    assert [item['promotion_id'] for item in candidates.json()]==ids


def test_raw_promotion_constraints_and_relationship_integrity(sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix)
    other_tenant=_scope(connection,f'{prefix}-other')
    now=datetime.now(UTC).replace(tzinfo=None); later=now+timedelta(hours=1)
    promotion_id=_execute(connection,"INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,status,source) VALUES (%s,%s,'Promo','PERCENTAGE_DISCOUNT',10,NULL,%s,%s,1,'INACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,now,later))
    other_org=_execute(connection,"INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'OTHER-P','Other','ACTIVE')",(scope.tenant_id,))
    other_product=_execute(connection,"INSERT INTO products (tenant_id,organization_id,name,status,source) VALUES (%s,%s,'Other','ACTIVE','PLATFORM')",(scope.tenant_id,other_org))
    invalid_promotions=[
        ("INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,status,source) VALUES (%s,%s,'Bad','BOGO',10,NULL,%s,%s,1,'INACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,now,later)),
        ("INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,status,source) VALUES (%s,%s,'Bad','PERCENTAGE_DISCOUNT',101,NULL,%s,%s,1,'INACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,now,later)),
        ("INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,status,source) VALUES (%s,%s,'Bad','FIXED_AMOUNT_DISCOUNT',1,NULL,%s,%s,1,'INACTIVE','PLATFORM')",(scope.tenant_id,scope.organization_id,now,later)),
        ("INSERT INTO promotions (tenant_id,organization_id,name,promotion_type,benefit_value,currency,starts_at,ends_at,applies_to_all_locations,status,source) VALUES (%s,%s,'Bad','PERCENTAGE_DISCOUNT',10,NULL,%s,%s,1,'BROKEN','PLATFORM')",(scope.tenant_id,scope.organization_id,later,now)),
    ]
    for statement,params in invalid_promotions:
        with pytest.raises((pymysql.err.IntegrityError,pymysql.err.OperationalError)): _execute(connection,statement,params)
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(connection,"INSERT INTO promotion_products (tenant_id,organization_id,promotion_id,product_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')",(scope.tenant_id,scope.organization_id,promotion_id,other_product))
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(connection,"INSERT INTO promotion_products (tenant_id,organization_id,promotion_id,product_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')",(scope.tenant_id,scope.organization_id,promotion_id,other_tenant.product_id))
    with pytest.raises(pymysql.err.IntegrityError):
        _execute(connection,"INSERT INTO promotion_locations (tenant_id,organization_id,promotion_id,location_id,status) VALUES (%s,%s,%s,%s,'ACTIVE')",(scope.tenant_id,scope.organization_id,promotion_id,other_tenant.location_id))


def test_selected_location_scope_and_half_open_interval(client,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix); headers=_headers(client,scope)
    start=datetime(2030,1,1,tzinfo=UTC); end=start+timedelta(hours=1)
    promotion=client.post('/promotions',headers=headers,json=_promotion_payload(scope,starts_at=start.isoformat(),ends_at=end.isoformat(),applies_to_all_locations=False)).json()
    client.post(f"/promotions/{promotion['id']}/products",headers=headers,json={'product_id':scope.product_id})
    assert client.patch(f"/promotions/{promotion['id']}",headers=headers,json={'status':'ACTIVE'}).status_code==409
    client.post(f"/promotions/{promotion['id']}/locations",headers=headers,json={'location_id':scope.location_id})
    assert client.patch(f"/promotions/{promotion['id']}",headers=headers,json={'status':'ACTIVE'}).status_code==200
    def query(moment): return client.get('/promotions/applicable',headers=headers,params={'product_id':scope.product_id,'location_id':scope.location_id,'effective_at':moment.isoformat()}).json()
    assert len(query(start))==1 and query(end)==[]


class PricePort:
    def __init__(self, external_id='external-product', amount='7.2500'): self.external_id=external_id; self.amount=amount; self.calls=0
    async def get_price(self, context, *, product_external_id):
        self.calls+=1; return ExternalPrice(product_external_id=self.external_id,amount=self.amount,currency='mxn')


def test_explicit_pricing_port_projection_and_authority(integration_settings,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix)
    _execute(connection,'INSERT INTO product_external_mappings (tenant_id,product_id,connector_key,external_product_id) VALUES (%s,%s,%s,%s)',(scope.tenant_id,scope.product_id,'mock','external-product'))
    context=LocationScopedPosRequestContext(tenant_id=scope.tenant_id,location_id=scope.location_id,connector_key='mock',correlation_id='test-correlation')
    async def scenario():
        manager=DatabaseManager(integration_settings); port=PricePort()
        try:
            async def resolve():
                async with manager.session_factory() as session:
                    return await resolve_external_price(session,port,context,product_id=scope.product_id,external_product_id='external-product')
            first, second = await asyncio.gather(resolve(), resolve())
            assert first.id == second.id
            price = first
            assert price.source=='POS' and price.amount==Decimal('7.2500')
            port.amount='8.5000'
            async with manager.session_factory() as session:
                price=await resolve_external_price(session,port,context,product_id=scope.product_id,external_product_id='external-product'); assert price.amount==Decimal('8.5000')
            with pytest.raises(PosMappingError):
                async with manager.session_factory() as session: await resolve_external_price(session,PricePort('wrong'),context,product_id=scope.product_id,external_product_id='external-product')
            async with manager.session_factory() as session:
                price=await session.scalar(select(ProductPrice).where(ProductPrice.id==price.id)); price.source='PLATFORM'; await session.commit()
            with pytest.raises(PriceAuthorityConflictError):
                async with manager.session_factory() as session: await resolve_external_price(session,port,context,product_id=scope.product_id,external_product_id='external-product')
        finally: await manager.dispose()
    asyncio.run(scenario())


def test_pricing_port_rejects_invalid_scope_and_missing_mapping(integration_settings,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix)
    other_org=_execute(connection,"INSERT INTO organizations (tenant_id,code,name,status) VALUES (%s,'POS-OTHER','POS Other','ACTIVE')",(scope.tenant_id,))
    other_location=_execute(connection,"INSERT INTO locations (tenant_id,organization_id,code,name,timezone,status) VALUES (%s,%s,'POS-OTHER','POS Other','UTC','ACTIVE')",(scope.tenant_id,other_org))
    valid_context=LocationScopedPosRequestContext(tenant_id=scope.tenant_id,location_id=scope.location_id,connector_key='mock',correlation_id='negative-path')
    missing_location_context=valid_context.model_copy(update={'location_id':999999999})
    mismatched_context=valid_context.model_copy(update={'location_id':other_location})
    async def scenario():
        manager=DatabaseManager(integration_settings); port=PricePort()
        try:
            for context,product_id in (
                (missing_location_context,scope.product_id),
                (valid_context,999999999),
                (mismatched_context,scope.product_id),
            ):
                with pytest.raises(ValueError):
                    async with manager.session_factory() as session:
                        await resolve_external_price(session,port,context,product_id=product_id,external_product_id='external-product')
            with pytest.raises(PosMappingError):
                async with manager.session_factory() as session:
                    await resolve_external_price(session,port,valid_context,product_id=scope.product_id,external_product_id='external-product')
            assert port.calls==0
        finally: await manager.dispose()
    asyncio.run(scenario())


def test_production_pricing_boundary_has_no_promotion_port_or_mock_import():
    import app.restaurant.pricing.service as service
    source=inspect.getsource(service)
    assert 'PromotionPort' not in source and 'MockPosAdapter' not in source and 'PriceExternalMapping' not in source
