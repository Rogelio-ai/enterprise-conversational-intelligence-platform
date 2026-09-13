from decimal import Decimal
from fastapi.testclient import TestClient
import pytest
from app.main import create_app
from test_inventory_recipe_stock_foundation import _headers,_item,_scope
from test_inventory_supplier_direct_receiving import _offering,_receipt,_supplier,_warehouse

PERMISSIONS=('inventory.manage','inventory.read','inventory.cost.read','inventory.supplier.manage','inventory.receipt.manage','inventory.receipt.accept','inventory.lot.read','inventory.valuation.read','inventory.valuation.create','inventory.fifo.read','inventory.transfer.read','inventory.transfer.manage')
@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:yield value
def accept(client,headers,receipt,key):
    response=client.post(f"/inventory/goods-receipts/{receipt['id']}:accept",headers={**headers,'Idempotency-Key':key},json={'expected_version':receipt['version']})
    assert response.status_code==200,response.text
def test_fifo_multi_layer_partial_atomic_transfer_and_snapshot(client,sql_connection):
    connection,prefix=sql_connection;scope=_scope(connection,prefix,PERMISSIONS);headers=_headers(client,scope)
    source=_warehouse(client,headers,scope.location_id)
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO warehouses (tenant_id,organization_id,location_id,code,name,status,default_slot,negative_stock_policy,version) VALUES (%s,%s,%s,'DEST','Destination','ACTIVE',NULL,'BLOCK',1)",(scope.tenant_id,scope.organization_id,scope.location_id));destination_id=cursor.lastrowid
    item=_item(client,headers,scope.location_id,'B11-FIFO',uom='UNIT',cost='50');supplier=_supplier(client,headers,scope);offering=_offering(client,headers,supplier,scope,item,'UNIT')
    for n,cost in enumerate(('80','90'),1):
        receipt=_receipt(client,headers,supplier,scope,source,[{'supplier_offering_id':offering['id'],'received_quantity':'10','accepted_quantity':'10','rejected_quantity':'0','unit_cost':cost,'currency':'MXN'}]);accept(client,headers,receipt,f'b11-receipt-{n}')
    layers=client.get('/inventory/fifo-layers',headers=headers,params={'location_id':scope.location_id}).json()['items'];assert [x['unit_cost'] for x in layers]==['80.000000000000','90.000000000000']
    created=client.post('/inventory/transfers',headers=headers,json={'source_warehouse_id':source['id'],'destination_warehouse_id':destination_id,'reference':'B11 exact transfer','lines':[{'inventory_item_id':item['id'],'quantity':'15'}]})
    assert created.status_code==201,created.text;transfer=created.json()
    for action in ('submit','ship'):
        response=client.post(f"/inventory/transfers/{transfer['id']}:{action}",headers={**headers,'Idempotency-Key':f'b11-{action}'},json={'expected_version':transfer['version'],'receipts':None});assert response.status_code==200,response.text;transfer=response.json()
    line=transfer['lines'][0];assert [(a['quantity'],a['unit_cost']) for a in line['source_allocations']]==[('10.000000','80.000000000000'),('5.000000','90.000000000000')]
    for n,quantity in enumerate(('6','9'),1):
        response=client.post(f"/inventory/transfers/{transfer['id']}:receive",headers={**headers,'Idempotency-Key':f'b11-receive-{n}'},json={'expected_version':transfer['version'],'receipts':[{'line_id':line['id'],'quantity':quantity}]});assert response.status_code==200,response.text;transfer=response.json();line=transfer['lines'][0]
    assert transfer['status']=='RECEIVED' and line['remaining_in_transit']=='0.000000'
    assert sum(Decimal(r['extended_cost']) for r in line['receipts'])==Decimal('1250.000000000000')
    with connection.cursor() as cursor:
        cursor.execute("SELECT warehouse_id,SUM(quantity) quantity FROM stock_movements WHERE tenant_id=%s AND inventory_item_id=%s GROUP BY warehouse_id ORDER BY warehouse_id",(scope.tenant_id,item['id']));balances={r['warehouse_id']:r['quantity'] for r in cursor.fetchall()};assert balances[source['id']]==Decimal('5.000000') and balances[destination_id]==Decimal('15.000000')
    with connection.cursor() as cursor:cursor.execute('SELECT CURRENT_TIMESTAMP now');as_of=cursor.fetchone()['now'].isoformat()
    snapshot=client.post('/inventory/valuation-snapshots',headers={**headers,'Idempotency-Key':'b11-fifo-snapshot'},json={'warehouse_id':destination_id,'as_of':as_of,'currency':'MXN','valuation_method':'FIFO'})
    assert snapshot.status_code==201,snapshot.text;value=snapshot.json();assert value['valuation_method']=='FIFO' and value['derivable_total_value']=='1250.000000000000' and value['non_derivable_line_count']==0
