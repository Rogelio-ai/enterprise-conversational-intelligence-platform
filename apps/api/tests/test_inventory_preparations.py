from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_recipe_stock_foundation import _headers, _item, _product, _scope
from test_inventory_supplier_direct_receiving import _warehouse

PERMISSIONS = (
    'inventory.manage','inventory.read','inventory.cost.read',
    'inventory.preparation.read','inventory.preparation.manage',
    'inventory.preparation.complete',
)


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value: yield value


def opening(client, headers, item_id, warehouse_id, quantity, key):
    response=client.post('/inventory/stock-movements',headers={**headers,'Idempotency-Key':key},json={'inventory_item_id':item_id,'warehouse_id':warehouse_id,'movement_type':'OPENING_BALANCE','quantity':quantity,'uom':'UNIT','reversal_of_movement_id':None,'reason':None,'reference':key})
    assert response.status_code==201,response.text


def recipe(client,headers,scope,output,components,expected_revision=0,expected='8'):
    response=client.post('/inventory/preparation-recipes',headers=headers,json={'location_id':scope.location_id,'output_inventory_item_id':output['id'],'expected_output_quantity':expected,'output_uom':'UNIT','status':'ACTIVE','expected_revision':expected_revision,'components':components})
    assert response.status_code==201,response.text
    return response.json()


def batch(client,headers,warehouse,version,quantities,output='8'):
    response=client.post('/inventory/preparation-batches',headers=headers,json={'recipe_version_id':version['id'],'warehouse_id':warehouse['id'],'reference':'B9-EVIDENCE','inputs':[{'recipe_component_id':component['id'],'source_quantity':quantity,'source_uom':'UNIT'} for component,quantity in zip(version['components'],quantities)],'output_quantity':output,'output_uom':'UNIT'})
    assert response.status_code==201,response.text
    return response.json()


def act(client,headers,value,action,key=None):
    action_headers={**headers,**({'Idempotency-Key':key} if key else {})}
    return client.post(f"/inventory/preparation-batches/{value['id']}:{action}",headers=action_headers,json={'expected_version':value['version']})


def test_immutable_recipe_multi_input_atomic_yield_cost_and_b3_b6_compatibility(client,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix,PERMISSIONS); headers=_headers(client,scope); warehouse=_warehouse(client,headers,scope.location_id)
    raw_a=_item(client,headers,scope.location_id,'PREP-A',uom='UNIT',cost='4'); raw_b=_item(client,headers,scope.location_id,'PREP-B',uom='UNIT',cost='2'); prepared=_item(client,headers,scope.location_id,'PREP-OUT',uom='UNIT',cost='1')
    opening(client,headers,raw_a['id'],warehouse['id'],'10','prep-open-a'); opening(client,headers,raw_b['id'],warehouse['id'],'2','prep-open-b')
    components=[{'inventory_item_id':raw_a['id'],'expected_quantity':'10','source_uom':'UNIT','yield_basis':True},{'inventory_item_id':raw_b['id'],'expected_quantity':'2','source_uom':'UNIT','yield_basis':False}]
    first=recipe(client,headers,scope,prepared,components)
    second=recipe(client,headers,scope,prepared,components,expected_revision=1,expected='9')
    versions=client.get('/inventory/preparation-recipes',headers=headers,params={'location_id':scope.location_id}).json()['items']
    assert [row['revision'] for row in versions]==[2,1] and next(row for row in versions if row['id']==first['id'])['expected_output_quantity']=='8.000000'
    value=batch(client,headers,warehouse,first,['10','2'])
    assert value['status']=='DRAFT' and value['movements']==[] and value['expected_yield']=='0.800000000000' and value['actual_yield']=='0.800000000000'
    assert value['material_cost']=='44.000000000000' and value['prepared_unit_material_cost']=='5.500000000000'
    started=act(client,headers,value,'start'); assert started.status_code==200,started.text; value=started.json(); assert value['movements']==[]
    completed=act(client,headers,value,'complete','complete-once'); assert completed.status_code==200,completed.text; value=completed.json()
    assert value['status']=='COMPLETED' and [row['quantity'] for row in value['movements']]==['-10.000000','-2.000000','8.000000']
    replay=act(client,headers,{'id':value['id'],'version':2},'complete','complete-once'); assert replay.status_code==200 and replay.headers['Idempotent-Replay']=='true' and len(replay.json()['movements'])==3
    with connection.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) count FROM inventory_losses WHERE tenant_id=%s',(scope.tenant_id,)); assert cursor.fetchone()['count']==0
        cursor.execute('SELECT movement_type,SUM(quantity) quantity FROM stock_movements WHERE preparation_batch_id=%s GROUP BY movement_type ORDER BY movement_type',(value['id'],)); rows=cursor.fetchall(); assert [(row['movement_type'],row['quantity']) for row in rows]==[('PREPARATION_INPUT',Decimal('-12.000000')),('PREPARATION_OUTPUT',Decimal('8.000000'))]
    product_id=_product(connection,scope,'Prepared Menu Item')
    compatible=client.put(f'/products/{product_id}/consumption-definition',headers=headers,params={'location_id':scope.location_id},json={'expected_version':0,'tracking_mode':'DERIVABLE','components':[{'inventory_item_id':prepared['id'],'quantity':'1','uom':'UNIT'}]})
    assert compatible.status_code==200,compatible.text


def test_block_atomicity_concurrent_completion_isolation_and_cost_privacy(integration_settings,sql_connection):
    connection,prefix=sql_connection
    with TestClient(create_app(settings=integration_settings)) as client:
        scope=_scope(connection,prefix,PERMISSIONS); headers=_headers(client,scope); warehouse=_warehouse(client,headers,scope.location_id)
        with connection.cursor() as cursor: cursor.execute("UPDATE warehouses SET negative_stock_policy='BLOCK' WHERE id=%s",(warehouse['id'],))
        raw=_item(client,headers,scope.location_id,'PREP-BLOCK',uom='UNIT',cost='3'); prepared=_item(client,headers,scope.location_id,'PREP-BLOCK-OUT',uom='UNIT',cost='1')
        version=recipe(client,headers,scope,prepared,[{'inventory_item_id':raw['id'],'expected_quantity':'2','source_uom':'UNIT','yield_basis':True}],expected='1')
        blocked=batch(client,headers,warehouse,version,['2'],output='1'); blocked=act(client,headers,blocked,'start').json(); response=act(client,headers,blocked,'complete','blocked'); assert response.status_code==409
        with connection.cursor() as cursor: cursor.execute('SELECT COUNT(*) count FROM stock_movements WHERE preparation_batch_id=%s',(blocked['id'],)); assert cursor.fetchone()['count']==0
        opening(client,headers,raw['id'],warehouse['id'],'2','prep-block-stock')
        ready=batch(client,headers,warehouse,version,['2'],output='1'); ready=act(client,headers,ready,'start').json()
        def complete(_): return act(client,headers,ready,'complete','race-key')
        with ThreadPoolExecutor(max_workers=2) as executor: results=list(executor.map(complete,(1,2)))
        assert [row.status_code for row in results]==[200,200] and sorted(row.headers.get('Idempotent-Replay')=='true' for row in results)==[False,True]
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) count FROM stock_movements WHERE preparation_batch_id=%s',(ready['id'],)); assert cursor.fetchone()['count']==2
            cursor.execute("SELECT p.id permission_id FROM permissions p JOIN role_permissions rp ON rp.permission_id=p.id WHERE rp.role_id=%s AND p.code='inventory.cost.read'",(scope.role_id,)); permission=cursor.fetchone()['permission_id']; cursor.execute('DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s',(scope.role_id,permission))
        hidden=client.get('/inventory/preparation-batches',headers=headers,params={'location_id':scope.location_id}); assert hidden.status_code==200; projected=next(row for row in hidden.json()['items'] if row['id']==ready['id']); assert projected['cost_visible'] is False and projected['material_cost'] is None and 'standard_unit_cost_evidence' not in projected['inputs'][0]
        foreign=_scope(connection,prefix+'-foreign',PERMISSIONS); foreign_headers=_headers(client,foreign)
        assert client.get('/inventory/preparation-batches',headers=foreign_headers,params={'location_id':scope.location_id}).status_code==404


def test_currency_mismatch_is_cost_non_derivable(client,sql_connection):
    connection,prefix=sql_connection; scope=_scope(connection,prefix,PERMISSIONS); headers=_headers(client,scope); warehouse=_warehouse(client,headers,scope.location_id)
    mxn=_item(client,headers,scope.location_id,'PREP-MXN',uom='UNIT',cost='2',currency='MXN'); usd=_item(client,headers,scope.location_id,'PREP-USD',uom='UNIT',cost='3',currency='USD'); output=_item(client,headers,scope.location_id,'PREP-MIXED',uom='UNIT',cost='1',currency='MXN')
    version=recipe(client,headers,scope,output,[{'inventory_item_id':mxn['id'],'expected_quantity':'1','source_uom':'UNIT','yield_basis':True},{'inventory_item_id':usd['id'],'expected_quantity':'1','source_uom':'UNIT','yield_basis':False}],expected='1')
    value=batch(client,headers,warehouse,version,['1','1'],output='1')
    assert value['cost_evidence_status']=='COST_NON_DERIVABLE' and value['material_cost'] is None and value['prepared_unit_material_cost'] is None
