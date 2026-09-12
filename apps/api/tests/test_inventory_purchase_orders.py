from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from test_inventory_recipe_stock_foundation import _headers,_item,_scope
from test_inventory_supplier_direct_receiving import _warehouse,_supplier,_offering

PERMISSIONS=('inventory.manage','inventory.read','inventory.supplier.manage','inventory.receipt.manage','inventory.receipt.accept','inventory.cost.read','inventory.purchase_order.read','inventory.purchase_order.manage','inventory.purchase_order.approve')

@pytest.fixture
def client(integration_settings):
  with TestClient(create_app(settings=integration_settings)) as value:
    yield value

def test_purchase_order_lifecycle_receiving_progress_and_stock_authority(integration_settings,sql_connection):
  connection,prefix=sql_connection
  with TestClient(create_app(settings=integration_settings)) as client:
    scope=_scope(connection,prefix,PERMISSIONS); headers=_headers(client,scope); warehouse=_warehouse(client,headers,scope.location_id); supplier=_supplier(client,headers,scope); a=_item(client,headers,scope.location_id,'PO-A',cost='4'); b=_item(client,headers,scope.location_id,'PO-B',cost='2'); oa=_offering(client,headers,supplier,scope,a,'G'); ob=_offering(client,headers,supplier,scope,b,'G')
    def movements():
      with connection.cursor() as c: c.execute('SELECT COUNT(*) count FROM stock_movements WHERE location_id=%s',(scope.location_id,)); return c.fetchone()['count']
    before=movements()
    response=client.post('/inventory/purchase-orders',headers=headers,json={'location_id':scope.location_id,'warehouse_id':warehouse['id'],'supplier_id':supplier['id'],'currency':'MXN','expected_delivery_at':'2026-09-20T12:00:00','lines':[{'supplier_offering_id':oa['id'],'ordered_quantity':'10','agreed_unit_price':'5'},{'supplier_offering_id':ob['id'],'ordered_quantity':'4','agreed_unit_price':'3'}]}); assert response.status_code==201,response.text; po=response.json(); assert po['status']=='DRAFT' and movements()==before
    amended=client.patch(f"/inventory/purchase-orders/{po['id']}",headers=headers,json={'expected_version':po['version'],'expected_delivery_at':'2026-09-21T12:00:00','external_reference':'PO-EVIDENCE','notes':'Auditable draft amendment','lines':[{'supplier_offering_id':oa['id'],'ordered_quantity':'10','agreed_unit_price':'5'},{'supplier_offering_id':ob['id'],'ordered_quantity':'4','agreed_unit_price':'3'}]}); assert amended.status_code==200,amended.text; po=amended.json(); assert po['version']==2 and po['external_reference']=='PO-EVIDENCE' and movements()==before
    stale=client.patch(f"/inventory/purchase-orders/{po['id']}",headers=headers,json={'expected_version':1,'lines':[{'supplier_offering_id':oa['id'],'ordered_quantity':'10','agreed_unit_price':'5'}]}); assert stale.status_code==409
    for action in ('submit','approve'):
      response=client.post(f"/inventory/purchase-orders/{po['id']}:{action}",headers={**headers,'Idempotency-Key':f'po-{action}'},json={'expected_version':po['version']}); assert response.status_code==200,response.text; po=response.json(); assert movements()==before
    submit_replay=client.post(f"/inventory/purchase-orders/{po['id']}:submit",headers={**headers,'Idempotency-Key':'po-submit'},json={'expected_version':2}); assert submit_replay.status_code==200 and submit_replay.headers['Idempotent-Replay']=='true' and movements()==before
    def receipt(lines,key):
      draft=client.post('/inventory/goods-receipts',headers=headers,json={'supplier_id':supplier['id'],'location_id':scope.location_id,'warehouse_id':warehouse['id'],'purchase_order_id':po['id'],'lines':lines}).json()
      result=client.post(f"/inventory/goods-receipts/{draft['id']}:accept",headers={**headers,'Idempotency-Key':key},json={'expected_version':draft['version']}); return result
    r=receipt([{'supplier_offering_id':oa['id'],'purchase_order_line_id':po['lines'][0]['id'],'received_quantity':'7','accepted_quantity':'6','rejected_quantity':'1','unit_cost':'6','currency':'MXN'},{'supplier_offering_id':ob['id'],'purchase_order_line_id':po['lines'][1]['id'],'received_quantity':'2','accepted_quantity':'2','rejected_quantity':'0','unit_cost':'3','currency':'MXN'}],'partial'); assert r.status_code==200,r.text
    po=client.get(f"/inventory/purchase-orders/{po['id']}",headers=headers).json(); assert po['status']=='PARTIALLY_RECEIVED'; assert po['lines'][0]['remaining_quantity']=='4.000000'; assert po['lines'][0]['rejected_quantity']=='1.000000'; assert po['lines'][0]['price_variance']=='1.000000'
    over=receipt([{'supplier_offering_id':oa['id'],'purchase_order_line_id':po['lines'][0]['id'],'received_quantity':'5','accepted_quantity':'5','rejected_quantity':'0','unit_cost':'5','currency':'MXN'}],'over'); assert over.status_code==409; assert movements()==before+2
    r=receipt([{'supplier_offering_id':oa['id'],'purchase_order_line_id':po['lines'][0]['id'],'received_quantity':'4','accepted_quantity':'4','rejected_quantity':'0','unit_cost':'5','currency':'MXN'},{'supplier_offering_id':ob['id'],'purchase_order_line_id':po['lines'][1]['id'],'received_quantity':'2','accepted_quantity':'2','rejected_quantity':'0','unit_cost':'3','currency':'MXN'}],'complete'); assert r.status_code==200,r.text
    po=client.get(f"/inventory/purchase-orders/{po['id']}",headers=headers).json(); assert po['status']=='RECEIVED' and all(v['remaining_quantity']=='0.000000' for v in po['lines'])
    assert po['lines'][0]['received_unit_price']=='5.600000' and po['lines'][0]['price_variance']=='0.600000'
    assert len(po['receipts'])==3 and len(po['lines'][0]['receipt_allocations'])==3
    closed=client.post(f"/inventory/purchase-orders/{po['id']}:close",headers={**headers,'Idempotency-Key':'close'},json={'expected_version':po['version']}); assert closed.status_code==200 and closed.json()['status']=='CLOSED'; assert movements()==before+4
    replay=client.post(f"/inventory/purchase-orders/{po['id']}:close",headers={**headers,'Idempotency-Key':'close'},json={'expected_version':po['version']}); assert replay.status_code==200 and replay.headers['Idempotent-Replay']=='true'
    hidden_headers=_headers(client,_scope(connection,prefix+'-hidden',tuple(p for p in PERMISSIONS if p!='inventory.cost.read')))
    assert client.get('/inventory/purchase-orders',headers=hidden_headers,params={'location_id':scope.location_id}).status_code==404


def test_linked_receipt_concurrency_cancel_and_cost_privacy(client,sql_connection):
  connection,prefix=sql_connection
  scope=_scope(connection,prefix,PERMISSIONS); headers=_headers(client,scope); warehouse=_warehouse(client,headers,scope.location_id); supplier=_supplier(client,headers,scope); item=_item(client,headers,scope.location_id,'PO-RACE',uom='UNIT',cost='2'); offering=_offering(client,headers,supplier,scope,item,'UNIT')
  def create_po(quantity='1'):
    response=client.post('/inventory/purchase-orders',headers=headers,json={'location_id':scope.location_id,'warehouse_id':warehouse['id'],'supplier_id':supplier['id'],'currency':'MXN','lines':[{'supplier_offering_id':offering['id'],'ordered_quantity':quantity,'agreed_unit_price':'2'}]}); assert response.status_code==201,response.text; value=response.json()
    for action in ('submit','approve'):
      response=client.post(f"/inventory/purchase-orders/{value['id']}:{action}",headers={**headers,'Idempotency-Key':f"{value['id']}-{action}"},json={'expected_version':value['version']}); assert response.status_code==200,response.text; value=response.json()
    return value
  def draft(po,quantity='1'):
    response=client.post('/inventory/goods-receipts',headers=headers,json={'supplier_id':supplier['id'],'location_id':scope.location_id,'warehouse_id':warehouse['id'],'purchase_order_id':po['id'],'lines':[{'supplier_offering_id':offering['id'],'purchase_order_line_id':po['lines'][0]['id'],'received_quantity':quantity,'accepted_quantity':quantity,'rejected_quantity':'0','unit_cost':'2','currency':'MXN'}]}); assert response.status_code==201,response.text; return response.json()
  po=create_po(); first=draft(po); second=draft(po)
  def accept(value):
    return client.post(f"/inventory/goods-receipts/{value['id']}:accept",headers={**headers,'Idempotency-Key':f"accept-{value['id']}"},json={'expected_version':value['version']})
  with ThreadPoolExecutor(max_workers=2) as executor:
    results=list(executor.map(accept,(first,second)))
  assert sorted(value.status_code for value in results)==[200,409]
  projected=client.get(f"/inventory/purchase-orders/{po['id']}",headers=headers).json(); assert projected['status']=='RECEIVED' and projected['lines'][0]['accepted_quantity']=='1.000000'
  with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) count FROM stock_movements WHERE goods_receipt_id IN (%s,%s)",(first['id'],second['id'])); assert cursor.fetchone()['count']==1
    cursor.execute("SELECT permission_id FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id WHERE rp.role_id=%s AND p.code='inventory.cost.read'",(scope.role_id,)); permission_id=cursor.fetchone()['permission_id']
    cursor.execute('DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s',(scope.role_id,permission_id))
  hidden=client.get(f"/inventory/purchase-orders/{po['id']}",headers=headers); assert hidden.status_code==200,hidden.text; body=hidden.json(); assert body['cost_visible'] is False and body['currency'] is None and 'agreed_unit_price' not in body['lines'][0] and 'unit_cost' not in body['lines'][0]['receipt_allocations'][0]
  with connection.cursor() as cursor: cursor.execute('INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)',(scope.role_id,permission_id))
  cancellable=create_po('2'); partial=draft(cancellable,'1'); accepted=accept(partial); assert accepted.status_code==200,accepted.text
  pending=draft(client.get(f"/inventory/purchase-orders/{cancellable['id']}",headers=headers).json(),'1')
  current=client.get(f"/inventory/purchase-orders/{cancellable['id']}",headers=headers).json(); cancelled=client.post(f"/inventory/purchase-orders/{cancellable['id']}:cancel",headers={**headers,'Idempotency-Key':'cancel-partial'},json={'expected_version':current['version']}); assert cancelled.status_code==200,cancelled.text; snapshot=cancelled.json(); assert snapshot['status']=='CANCELLED' and snapshot['lines'][0]['remaining_quantity']=='1.000000'
  blocked=accept(pending); assert blocked.status_code==409
  after=client.get(f"/inventory/purchase-orders/{cancellable['id']}",headers=headers).json(); assert after['lines'][0]['accepted_quantity']==snapshot['lines'][0]['accepted_quantity'] and after['lines'][0]['remaining_quantity']==snapshot['lines'][0]['remaining_quantity']


def test_linkage_validation_and_direct_receipt_compatibility(client,sql_connection):
  connection,prefix=sql_connection
  scope=_scope(connection,prefix,PERMISSIONS); headers=_headers(client,scope); warehouse=_warehouse(client,headers,scope.location_id); supplier=_supplier(client,headers,scope); item=_item(client,headers,scope.location_id,'PO-LINK',uom='UNIT',cost='2'); offering=_offering(client,headers,supplier,scope,item,'UNIT')
  line={'supplier_offering_id':offering['id'],'received_quantity':'1','accepted_quantity':'1','rejected_quantity':'0','unit_cost':'2','currency':'MXN'}
  direct=client.post('/inventory/goods-receipts',headers=headers,json={'supplier_id':supplier['id'],'location_id':scope.location_id,'warehouse_id':warehouse['id'],'lines':[line]}); assert direct.status_code==201,direct.text; assert direct.json()['purchase_order_id'] is None
  invalid=client.post('/inventory/goods-receipts',headers=headers,json={'supplier_id':supplier['id'],'location_id':scope.location_id,'warehouse_id':warehouse['id'],'lines':[{**line,'purchase_order_line_id':999999}]}); assert invalid.status_code==422
  draft=client.post('/inventory/purchase-orders',headers=headers,json={'location_id':scope.location_id,'warehouse_id':warehouse['id'],'supplier_id':supplier['id'],'currency':'MXN','lines':[{'supplier_offering_id':offering['id'],'ordered_quantity':'1','agreed_unit_price':'2'}]}).json()
  premature=client.post('/inventory/goods-receipts',headers=headers,json={'supplier_id':supplier['id'],'location_id':scope.location_id,'warehouse_id':warehouse['id'],'purchase_order_id':draft['id'],'lines':[{**line,'purchase_order_line_id':draft['lines'][0]['id']}]}); assert premature.status_code==409
