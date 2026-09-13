import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { InventoryIntelligence, StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const permissions = [
  'location.read', 'inventory.read', 'inventory.cost.read', 'inventory.receipt.manage',
  'inventory.receipt.accept', 'inventory.loss.read', 'inventory.loss.manage',
  'inventory.loss.approve', 'inventory.count.read', 'inventory.count.manage',
  'inventory.count.approve', 'inventory.count.post', 'inventory.reconciliation.read',
    'inventory.reconciliation.manage',
    'inventory.purchase_order.read', 'inventory.purchase_order.manage', 'inventory.purchase_order.approve',
    'inventory.preparation.read', 'inventory.preparation.manage', 'inventory.preparation.complete',
];
const identity: StaffIdentity = { user_id: 1, email: 'inventory@example.test', display_name: 'Iris Inventario', tenant_id: 11, membership_id: 12, authorized_location_ids: [21], roles: ['INVENTORY_OPERATOR'], permissions };
const location = { id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' };
const intelligence: InventoryIntelligence = {
  location_id: 21, generated_at: '2026-09-12T12:00:00Z', cost_visible: false,
  active_warehouse_count: 1, active_inventory_item_count: 2, stock_position_count: 2,
  negative_stock_count: 0, counts_requiring_action: 0, reconciliations_requiring_action: 0,
  warehouses: [{ id: 41, code: 'MAIN', name: 'Almacén principal', negative_stock_policy: 'WARN', is_default: true }],
  stock: [
    { inventory_item_id: 51, code: 'TOM', name: 'Tomate', warehouse_id: 41, warehouse_name: 'Almacén principal', base_uom: 'KG', quantity: '8.000000', negative_stock_policy: 'WARN', attention: ['WARN_POLICY'], last_material_activity_at: '2026-09-12T11:00:00Z', standard_unit_cost: null, cost_currency: null, inventory_value_at_standard_cost: null, purchase_cost: null, stock_source: 'SUM_STOCK_MOVEMENT_QUANTITY', valuation_source: null },
    { inventory_item_id: 52, code: 'SAL', name: 'Sal', warehouse_id: 41, warehouse_name: 'Almacén principal', base_uom: 'KG', quantity: '3.000000', negative_stock_policy: 'WARN', attention: ['WARN_POLICY'], last_material_activity_at: null, standard_unit_cost: null, cost_currency: null, inventory_value_at_standard_cost: null, purchase_cost: null, stock_source: 'SUM_STOCK_MOVEMENT_QUANTITY', valuation_source: null },
  ],
  recent_receipts: [{ id: 61, warehouse_id: 41, label: 'Proveedor Norte', status: 'ACCEPTED', occurred_at: '2026-09-12T10:00:00Z', source: 'GOODS_RECEIPT_ACCEPTED' }],
  recent_losses: [], recent_counts: [],
  reconciliations: [{ id: 91, warehouse_id: 41, inventory_item_id: 51, physical_count_id: 81, status: 'CLOSED', version: 2, period_start: '2026-09-01T00:00:00Z', period_end: '2026-09-12T09:00:00Z', opening_quantity: '10', receipts: '4', theoretical_consumption: '2', registered_losses: '1', other_adjustments: '0', physical_count: '10', count_adjustment: '-1', closing_quantity: '10', unexplained_variance: '-1', variance_percentage: '-9.0909', variance_value: null, currency: null, evidence_status: 'RESOLVED', source: 'INVENTORY_RECONCILIATION' }],
  sources: { stock: 'StockMovement', receipts: 'GoodsReceipt', losses: 'InventoryLoss', counts: 'PhysicalCount', reconciliations: 'InventoryReconciliation' }, limit: 100, offset: 0,
};

function json(body: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })); }

function mockApi(currentIdentity = identity, acceptConflict = false, inventoryData = intelligence) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let receiptLines: Array<Record<string, unknown>> = [];
  const preparationRecipe = { id: 201, location_id: 21, output_inventory_item_id: 53, revision: 1, status: 'ACTIVE', publication_status: 'PUBLISHED', expected_output_quantity: '8.000000', output_source_uom: 'KG', normalized_expected_output_quantity: '8.000000', output_base_uom_evidence: 'KG', expected_yield: '0.800000000000', effective_from: '2026-09-12T12:00:00Z', effective_to: null, published_at: '2026-09-12T12:00:00Z', components: [{ id: 202, inventory_item_id: 51, line_number: 1, expected_quantity: '10.000000', source_uom: 'KG', normalized_expected_quantity: '10.000000', base_uom_evidence: 'KG', yield_basis: true }, { id: 203, inventory_item_id: 52, line_number: 2, expected_quantity: '2.000000', source_uom: 'KG', normalized_expected_quantity: '2.000000', base_uom_evidence: 'KG', yield_basis: false }] };
  let preparationBatch: any = null;
  let count: Record<string, any> = { id: 81, warehouse_id: 41, count_scope: 'PARTIAL', status: 'DRAFT', opened_at: '2026-09-12T12:00:00Z', cursor_at: '2026-09-12T12:00:00Z', cursor_movement_id: 70, reason: 'Conteo', reference: null, version: 1, lines: [] };
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input); calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(currentIdentity);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/inventory/intelligence?')) return json(inventoryData);
    if (url.includes('/inventory-items?')) return json({ items: [{ id: 51, code: 'TOM', name: 'Tomate', base_uom: 'KG', status: 'ACTIVE' }, { id: 52, code: 'SAL', name: 'Sal', base_uom: 'KG', status: 'ACTIVE' }, { id: 53, code: 'SALSA', name: 'Salsa preparada', base_uom: 'KG', status: 'ACTIVE' }] });
    if (url.includes('/inventory/preparation-recipes?')) return json({ items: [preparationRecipe] });
    if (url.includes('/inventory/preparation-batches?')) return json({ items: preparationBatch ? [preparationBatch] : [] });
    if (url.endsWith('/inventory/preparation-batches') && init?.method === 'POST') { const payload=JSON.parse(String(init.body)); preparationBatch={ id:204,location_id:21,warehouse_id:41,recipe_version_id:201,status:'DRAFT',version:1,reference:payload.reference,expected_yield:'0.800000000000',actual_yield:'0.800000000000',yield_variance:'0.000000000000',cost_evidence_status:'RESOLVED',material_cost:'44.000000000000',prepared_unit_material_cost:'5.500000000000',cost_currency_evidence:'MXN',cost_visible:true,inputs:preparationRecipe.components.map((row:any,index:number)=>({id:205+index,recipe_component_id:row.id,inventory_item_id:row.inventory_item_id,source_quantity:payload.inputs[index].source_quantity,source_uom:'KG',normalized_quantity:payload.inputs[index].source_quantity,base_uom_evidence:'KG',evidence_status:'RESOLVED'})),output:{id:207,inventory_item_id:53,source_quantity:payload.output_quantity,source_uom:'KG',normalized_quantity:payload.output_quantity,base_uom_evidence:'KG',evidence_status:'RESOLVED'},movements:[],created_at:'2026-09-12T12:00:00Z',started_at:null,completed_at:null,cancelled_at:null};return json(preparationBatch,201); }
    if (/\/inventory\/preparation-batches\/204:(start|complete|cancel)$/.test(url)) { const action=url.split(':').at(-1); preparationBatch={...preparationBatch,status:action==='start'?'IN_PROGRESS':action==='complete'?'COMPLETED':'CANCELLED',version:preparationBatch.version+1,movements:action==='complete'?[{id:210,movement_type:'PREPARATION_INPUT',quantity:'-10.000000'},{id:211,movement_type:'PREPARATION_INPUT',quantity:'-2.000000'},{id:212,movement_type:'PREPARATION_OUTPUT',quantity:'8.000000'}]:[]};return json(preparationBatch); }
    if (url.includes('/inventory/purchase-orders?')) return json({ items: [] });
    if (url.endsWith('/inventory/purchase-orders') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      return json({ id: 101, location_id: 21, warehouse_id: 41, supplier_id: 71, status: 'DRAFT', currency: 'MXN', cost_visible: true, expected_delivery_at: payload.expected_delivery_at, external_reference: null, notes: null, version: 1, lines: payload.lines.map((line: any, index: number) => ({ id: 102 + index, ...line, inventory_item_id: index ? 52 : 51, line_number: index + 1, source_uom: 'KG', normalized_ordered_quantity: line.ordered_quantity, base_uom_evidence: 'KG', accepted_quantity: '0.000000', rejected_quantity: '0.000000', remaining_quantity: line.ordered_quantity, currency: 'MXN', received_unit_price: null, price_variance: null })) }, 201);
    }
    if (url.endsWith('/inventory/purchase-orders/101') && init?.method === 'PATCH') {
      const payload = JSON.parse(String(init.body));
      return json({ id: 101, location_id: 21, warehouse_id: 41, supplier_id: 71, status: 'DRAFT', currency: 'MXN', cost_visible: true, expected_delivery_at: payload.expected_delivery_at, external_reference: payload.external_reference, notes: payload.notes, version: 2, receipts: [], submitted_at: null, approved_at: null, terminated_at: null, lines: payload.lines.map((line: any, index: number) => ({ id: 102 + index, ...line, inventory_item_id: index ? 52 : 51, line_number: index + 1, source_uom: 'KG', conversion_factor: '1.000000', normalized_ordered_quantity: line.ordered_quantity, base_uom_evidence: 'KG', accepted_quantity: '0.000000', rejected_quantity: '0.000000', remaining_quantity: line.ordered_quantity, currency: 'MXN', received_unit_price: null, price_variance: null, receipt_allocations: [] })) });
    }
    if (/\/inventory\/purchase-orders\/101:(submit|approve|cancel|close)$/.test(url)) {
      const action = url.split(':').at(-1); const status = action === 'submit' ? 'SUBMITTED' : action === 'approve' ? 'APPROVED' : action === 'cancel' ? 'CANCELLED' : 'CLOSED';
      return json({ id: 101, location_id: 21, warehouse_id: 41, supplier_id: 71, status, currency: 'MXN', cost_visible: true, expected_delivery_at: null, external_reference: null, notes: null, version: action === 'submit' ? 2 : 3, lines: [] });
    }
    if (url.includes('/inventory/suppliers?')) return json({ items: [{ id: 71, code: 'NORTE', name: 'Proveedor Norte', status: 'ACTIVE', location_ids: [21] }] });
    if (url.includes('/inventory/suppliers/71/offerings?')) return json({ items: [
      { id: 72, supplier_id: 71, location_id: 21, inventory_item_id: 51, purchase_uom: 'KG', status: 'ACTIVE' },
      { id: 73, supplier_id: 71, location_id: 21, inventory_item_id: 52, purchase_uom: 'KG', status: 'ACTIVE' },
    ] });
    if (url.endsWith('/inventory/goods-receipts') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      receiptLines = payload.lines.map((line: Record<string, unknown>, index: number) => ({ id: 74 + index, inventory_item_id: line.supplier_offering_id === 72 ? 51 : 52, accepted_quantity: line.accepted_quantity, rejected_quantity: line.rejected_quantity, received_quantity: line.received_quantity, source_uom: 'KG', unit_cost: line.unit_cost, currency: line.currency, evidence_status: 'PENDING', stock_movement_id: null }));
      return json({ id: 73, location_id: 21, warehouse_id: 41, supplier_id: 71, external_reference: payload.external_reference, status: 'DRAFT', version: 1, accepted_at: null, lines: receiptLines }, 201);
    }
    if (url.includes('/inventory/goods-receipts/73:accept')) return acceptConflict ? json({ detail: { code: 'goods_receipt_conflict', message: 'Receipt changed' } }, 409) : json({ id: 73, location_id: 21, warehouse_id: 41, supplier_id: 71, external_reference: null, status: 'ACCEPTED', version: 2, accepted_at: '2026-09-12T12:01:00Z', lines: receiptLines.map((line, index) => ({ ...line, evidence_status: 'RESOLVED', stock_movement_id: 80 + index })) });
    if (url.includes('/inventory/losses?')) return json({ items: [] });
    if (url.endsWith('/inventory/losses') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      if (payload.occurred_at?.startsWith('2035')) return json({ detail: { code: 'invalid_inventory_loss', message: 'Occurrence time cannot be in the future' } }, 422);
      return json({ id: 76, warehouse_id: 41, inventory_item_id: 51, category: 'WASTE', source_quantity: '1', source_uom: 'KG', normalized_quantity: null, evidence_status: 'PENDING', cost_visible: false, extended_loss_cost: null, cost_currency_evidence: null, reason: 'Daño', occurred_at: payload.occurred_at ?? '2026-09-12T12:00:00Z', status: 'DRAFT', version: 1, approval_required: false, approval_reason: null, stock_movement_id: null, reversal_stock_movement_id: null }, 201);
    }
    if (url.includes('/inventory/losses/76:post')) return json({ id: 76, warehouse_id: 41, inventory_item_id: 51, category: 'WASTE', source_quantity: '1', source_uom: 'KG', normalized_quantity: '1', evidence_status: 'RESOLVED', cost_visible: false, extended_loss_cost: null, cost_currency_evidence: null, reason: 'Daño', occurred_at: '2026-09-12T12:00:00Z', status: 'PENDING_APPROVAL', version: 2, approval_required: true, approval_reason: 'VALUE_THRESHOLD', stock_movement_id: null, reversal_stock_movement_id: null });
    if (url.includes('/inventory/losses/76:approve')) return json({ id: 76, warehouse_id: 41, inventory_item_id: 51, category: 'WASTE', source_quantity: '1', source_uom: 'KG', normalized_quantity: '1', evidence_status: 'RESOLVED', cost_visible: false, extended_loss_cost: null, cost_currency_evidence: null, reason: 'Daño', occurred_at: '2026-09-12T12:00:00Z', status: 'POSTED', version: 3, approval_required: true, approval_reason: 'VALUE_THRESHOLD', stock_movement_id: 77, reversal_stock_movement_id: null });
    if (url.includes('/inventory/physical-counts?')) return json({ items: [count] });
    if (url.endsWith('/inventory/physical-counts') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      count = { ...count, id: Number(count.id) + 1, count_scope: payload.count_scope, status: 'DRAFT', version: 1, lines: [] };
      return json(count, 201);
    }
    if (/\/inventory\/physical-counts\/\d+\/lines\/\d+$/.test(url)) {
      const payload = JSON.parse(String(init?.body));
      const itemId = Number(url.split('/').at(-1));
      const expected = itemId === 51 ? '8' : '3';
      const existing = count.lines.find((line: Record<string, any>) => line.inventory_item_id === itemId);
      const line = { id: existing?.id ?? 82 + count.lines.length, physical_count_id: count.id, inventory_item_id: itemId, expected_quantity_at_cursor: expected, source_quantity: payload.source_quantity, source_uom: 'KG', normalized_counted_quantity: payload.source_quantity, variance_quantity: String(Number(payload.source_quantity) - Number(expected)), variance_value: null, evidence_status: 'RESOLVED', version: (existing?.version ?? 0) + 1, adjustment_stock_movement_id: null };
      count = { ...count, status: 'COUNTING', version: Number(count.version) + 1, lines: [...count.lines.filter((value: Record<string, any>) => value.inventory_item_id !== itemId), line] };
      return json(count);
    }
    if (/\/inventory\/physical-counts\/\d+:(submit|approve|post)$/.test(url)) {
      const action = url.split(':').at(-1);
      if (action === 'post' && count.count_scope === 'FULL' && count.lines.length < 2) return json({ error: { code: 'INVALID_PHYSICAL_COUNT', message: 'FULL count is incomplete: 1 active item(s) are not counted' } }, 422);
      count = { ...count, status: action === 'submit' ? 'SUBMITTED' : action === 'approve' ? 'APPROVED' : 'POSTED', version: Number(count.version) + 1, lines: action === 'post' ? count.lines.map((line: Record<string, unknown>, index: number) => ({ ...line, adjustment_stock_movement_id: 90 + index })) : count.lines };
      return json(count);
    }
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock); return { calls };
}

function renderInventory(path: string) {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Tenant' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={[path]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter></ThemeProvider></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Inventory Staff Web', () => {
  it('shows scoped ledger stock, navigation, attention, and server-side cost masking', async () => {
    const api = mockApi({ ...identity, permissions: permissions.filter((value) => value !== 'inventory.cost.read') }); renderInventory('/inventory/stock');
    expect(await screen.findByRole('heading', { name: 'Stock actual por almacén' }, { timeout: 10_000 })).toBeVisible();
    expect(screen.getByText('Tomate')).toBeVisible(); expect(screen.getByText('8 KG')).toBeVisible();
    expect(screen.getByText(/Costos y valores no fueron incluidos/)).toBeVisible();
    expect(screen.queryByRole('columnheader', { name: 'Costos' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Recepción' })).toHaveAttribute('href', '/inventory/receiving');
    expect(api.calls.some(({ url }) => url.includes('location_id=21'))).toBe(true);
  }, 15_000);

  it('shows a deliberate no-warehouse state without exposing unusable workflows', async () => {
    mockApi(identity, false, { ...intelligence, active_warehouse_count: 0, stock_position_count: 0, warehouses: [], stock: [] });
    const { container } = renderInventory('/inventory/receiving');
    expect(await screen.findByText('No hay almacenes activos.')).toBeVisible();
    expect(screen.getByText(/Habilita un almacén/)).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Nueva recepción directa' })).not.toBeInTheDocument();
    expect(container.querySelector('.inventory-page')).not.toHaveTextContent('000000');
  });

  it('creates a multi-line purchase-order draft and submits it without claiming stock impact', async () => {
    mockApi(); const user = userEvent.setup(); renderInventory('/inventory/purchase-orders');
    expect(await screen.findByRole('heading', { name: 'Nueva orden de compra' })).toBeVisible();
    expect(screen.getByText(/No modifica existencias/)).toBeVisible();
    await screen.findByRole('option', { name: 'Proveedor Norte' });
    await user.selectOptions(screen.getByLabelText('Proveedor'), '71');
    await screen.findByRole('option', { name: 'Artículo #51 · KG' });
    await user.selectOptions(screen.getByLabelText('Presentación'), '72');
    await user.type(screen.getByLabelText('Cantidad ordenada'), '10'); await user.type(screen.getByLabelText('Precio acordado'), '5'); await user.click(screen.getByRole('button', { name: 'Agregar línea' }));
    await user.selectOptions(screen.getByLabelText('Presentación'), '73'); await user.type(screen.getByLabelText('Cantidad ordenada'), '4'); await user.type(screen.getByLabelText('Precio acordado'), '3'); await user.click(screen.getByRole('button', { name: 'Agregar línea' }));
    await user.click(screen.getByRole('button', { name: 'Crear DRAFT' }));
    expect(await screen.findByText('#101 · DRAFT')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Editar DRAFT' }));
    await user.click(screen.getByRole('button', { name: 'Editar línea 1' }));
    await user.clear(screen.getByLabelText('Cantidad ordenada')); await user.type(screen.getByLabelText('Cantidad ordenada'), '11');
    await user.click(screen.getByRole('button', { name: 'Guardar línea' }));
    await user.click(screen.getByRole('button', { name: 'Quitar línea 2' }));
    await user.selectOptions(screen.getByLabelText('Presentación'), '73'); await user.type(screen.getByLabelText('Cantidad ordenada'), '4'); await user.type(screen.getByLabelText('Precio acordado'), '3'); await user.click(screen.getByRole('button', { name: 'Agregar línea' }));
    await user.click(screen.getByRole('button', { name: 'Guardar cambios del DRAFT' }));
    expect(await screen.findByText(/Ordenado 11/)).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Enviar a aprobación' }));
    expect(await screen.findByText('#101 · SUBMITTED')).toBeVisible();
  }, 15_000);

  it('runs a multi-input preparation batch and presents server-derived yield and cost', async () => {
    mockApi(); const user=userEvent.setup(); renderInventory('/inventory/preparations');
    expect(await screen.findByRole('heading',{name:'Nueva versión de preparación'})).toBeVisible();
    await screen.findByRole('option',{name:'Salsa preparada · revisión 1'}); await user.selectOptions(screen.getByLabelText('Receta publicada'),'201');
    expect(screen.getByLabelText('Entrada real Tomate')).toHaveValue('10.000000'); expect(screen.getByLabelText('Entrada real Sal')).toHaveValue('2.000000');
    await user.click(screen.getByRole('button',{name:'Crear lote DRAFT'})); expect(await screen.findByText('Lote #204 · DRAFT',{selector:'p'})).toBeVisible(); expect(screen.getByText(/Movimientos/).parentElement).toHaveTextContent('0');
    await user.click(screen.getByRole('button',{name:'Iniciar lote'})); expect(await screen.findByText('Lote #204 · IN_PROGRESS',{selector:'p'})).toBeVisible();
    await user.click(screen.getByRole('button',{name:'Completar lote'})); expect(await screen.findByText('Lote #204 · COMPLETED',{selector:'p'})).toBeVisible(); expect(screen.getByText(/Costo material 44/)).toBeVisible(); expect(screen.getByText(/Rendimiento real/).parentElement).toHaveTextContent('0.800000000000');
  },15_000);

  it('composes, edits, removes, and accepts one authoritative multi-line receipt', async () => {
    const api = mockApi(); const user = userEvent.setup(); renderInventory('/inventory/receiving');
    await screen.findByRole('heading', { name: 'Nueva recepción directa' });
    await screen.findByRole('option', { name: 'Proveedor Norte' });
    await user.selectOptions(screen.getByLabelText('Proveedor'), '71');
    await screen.findByRole('option', { name: 'Artículo #51 · KG' });
    await user.selectOptions(screen.getByLabelText('Artículo / presentación'), '72');
    await user.type(screen.getByLabelText('Recibido'), '2'); await user.clear(screen.getByLabelText('Aceptado')); await user.type(screen.getByLabelText('Aceptado'), '2');
    await user.type(screen.getByLabelText('Costo unitario'), '20'); await user.click(screen.getByRole('button', { name: 'Agregar línea' }));
    await user.selectOptions(screen.getByLabelText('Artículo / presentación'), '73');
    await user.type(screen.getByLabelText('Recibido'), '3'); await user.clear(screen.getByLabelText('Aceptado')); await user.type(screen.getByLabelText('Aceptado'), '3');
    await user.type(screen.getByLabelText('Costo unitario'), '5'); await user.click(screen.getByRole('button', { name: 'Agregar línea' }));
    await user.clear(screen.getByLabelText('Costo línea 2')); await user.type(screen.getByLabelText('Costo línea 2'), '6');
    await user.click(screen.getByRole('button', { name: 'Quitar línea 2' }));
    await user.selectOptions(screen.getByLabelText('Artículo / presentación'), '73');
    await user.type(screen.getByLabelText('Recibido'), '4'); await user.clear(screen.getByLabelText('Aceptado')); await user.type(screen.getByLabelText('Aceptado'), '4');
    await user.type(screen.getByLabelText('Costo unitario'), '6'); await user.click(screen.getByRole('button', { name: 'Agregar línea' }));
    await user.click(screen.getByRole('button', { name: 'Crear un DRAFT con todas las líneas' }));
    expect(await screen.findByText('DRAFT · SIN CAMBIO DE STOCK')).toBeVisible();
    expect(screen.getByText('2', { selector: 'dd' })).toBeVisible();
    const creation = api.calls.find(({ url, init }) => url.endsWith('/inventory/goods-receipts') && init?.method === 'POST')!;
    const payload = JSON.parse(String(creation.init?.body));
    expect(payload.lines).toHaveLength(2);
    expect(payload.lines.map((line: Record<string, unknown>) => line.supplier_offering_id)).toEqual([72, 73]);
    expect(payload.lines[1]).toMatchObject({ received_quantity: '4', accepted_quantity: '4', unit_cost: '6' });
    expect(api.calls.filter(({ url }) => url.endsWith('/inventory/goods-receipts'))).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Aceptar una vez y publicar todas las líneas' }));
    expect(await screen.findByText('ACCEPTED · STOCK PUBLICADO')).toBeVisible();
    expect(screen.getByText('Recepción completa aceptada; el conjunto autoritativo de movimientos fue confirmado.')).toBeVisible();
    expect(screen.getByText('#80, #81')).toBeVisible();
    const acceptance = api.calls.find(({ url }) => url.includes(':accept'))!;
    expect(new Headers(acceptance.init?.headers).get('Idempotency-Key')).toBeTruthy();
    expect(api.calls.filter(({ url }) => url.includes(':accept'))).toHaveLength(1);
  });

  it('keeps not-counted distinct from counted zero at the frozen cursor', async () => {
    mockApi(); const user = userEvent.setup(); renderInventory('/inventory/counts');
    await screen.findByRole('heading', { name: 'Abrir conteo' }); await user.click(screen.getByRole('button', { name: 'Abrir conteo' }));
    await user.selectOptions(screen.getByLabelText('Artículo'), '51'); await user.click(screen.getByRole('button', { name: 'Marcar CONTADO CERO' }));
    await user.click(screen.getByRole('button', { name: 'Guardar observación' }));
    expect(await screen.findByText(/CONTADO 0 · esperado al cursor 8 · varianza -8/)).toBeVisible();
    expect(screen.getByText('NO CONTADO')).toBeVisible(); expect(screen.getByText(/Sin congelamiento: cursor/)).toBeVisible();
  });

  it('persists FULL scope, surfaces incomplete coverage, and posts only explicit complete coverage', async () => {
    const api = mockApi(); const user = userEvent.setup(); renderInventory('/inventory/counts');
    await screen.findByRole('heading', { name: 'Abrir conteo' });
    await user.selectOptions(screen.getByLabelText('Alcance'), 'FULL');
    expect(screen.getByText(/FULL exige una observación explícita/)).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Abrir conteo' }));
    const firstCreation = api.calls.find(({ url, init }) => url.endsWith('/inventory/physical-counts') && init?.method === 'POST')!;
    expect(JSON.parse(String(firstCreation.init?.body)).count_scope).toBe('FULL');
    expect((await screen.findAllByText(/#82 · FULL · DRAFT/))[0]).toBeVisible();
    await user.selectOptions(screen.getByLabelText('Artículo'), '51');
    await user.click(screen.getByRole('button', { name: 'Marcar CONTADO CERO' }));
    await user.click(screen.getByRole('button', { name: 'Guardar observación' }));
    expect(await screen.findByText(/CONTADO 0 · esperado al cursor 8/)).toBeVisible();
    expect(screen.getByText('NO CONTADO')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    await user.click(await screen.findByRole('button', { name: 'Aprobar' }));
    await user.click(await screen.findByRole('button', { name: 'Publicar ajustes' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El conteo FULL está incompleto');
    await user.click(screen.getByRole('button', { name: 'Publicar ajustes' }));
    await waitFor(() => expect(api.calls.filter(({ url }) => url.endsWith(':post'))).toHaveLength(2));
    const failedPosts = api.calls.filter(({ url }) => url.endsWith(':post'));
    expect(new Headers(failedPosts[0].init?.headers).get('Idempotency-Key')).toBe(new Headers(failedPosts[1].init?.headers).get('Idempotency-Key'));

    await user.click(screen.getByRole('button', { name: 'Abrir conteo' }));
    await waitFor(() => expect(screen.getAllByText(/#83 · FULL · DRAFT/)[0]).toBeVisible());
    await user.selectOptions(screen.getByLabelText('Artículo'), '51');
    await user.click(screen.getByRole('button', { name: 'Marcar CONTADO CERO' }));
    await user.click(screen.getByRole('button', { name: 'Guardar observación' }));
    await user.selectOptions(screen.getByLabelText('Artículo'), '52');
    await user.clear(screen.getByLabelText('Cantidad contada')); await user.type(screen.getByLabelText('Cantidad contada'), '3');
    await user.click(screen.getByRole('button', { name: 'Guardar observación' }));
    await user.click(await screen.findByRole('button', { name: 'Enviar' }));
    await user.click(await screen.findByRole('button', { name: 'Aprobar' }));
    await user.click(await screen.findByRole('button', { name: 'Publicar ajustes' }));
    expect(await screen.findByText('Conteo publicado; ajustes confirmados y movimientos posteriores preservados.')).toBeVisible();
    expect(screen.getAllByText(/#83 · FULL · POSTED/)[0]).toBeVisible();
  });

  it('sends default and custom loss occurrence times, shows validation, and locks posted history', async () => {
    const api = mockApi(); const user = userEvent.setup(); renderInventory('/inventory/losses');
    await screen.findByRole('heading', { name: 'Registrar pérdida dedicada' });
    await user.selectOptions(screen.getByLabelText('Artículo'), '51');
    await user.type(screen.getByLabelText('Cantidad'), '1'); await user.type(screen.getByLabelText(/Razón/), 'Daño');
    await user.click(screen.getByRole('button', { name: 'Crear DRAFT' }));
    let creations = api.calls.filter(({ url, init }) => url.endsWith('/inventory/losses') && init?.method === 'POST');
    expect(JSON.parse(String(creations[0].init?.body)).occurred_at).toBeNull();
    await user.type(screen.getByLabelText('Fecha/hora de ocurrencia (opcional)'), '2026-09-10T08:30');
    await user.click(screen.getByRole('button', { name: 'Crear DRAFT' }));
    creations = api.calls.filter(({ url, init }) => url.endsWith('/inventory/losses') && init?.method === 'POST');
    expect(JSON.parse(String(creations[1].init?.body)).occurred_at).toBe(new Date('2026-09-10T08:30').toISOString());
    expect(await screen.findByText(/Ocurrencia confirmada/)).toBeVisible();
    await user.clear(screen.getByLabelText('Fecha/hora de ocurrencia (opcional)'));
    await user.type(screen.getByLabelText('Fecha/hora de ocurrencia (opcional)'), '2035-01-01T08:30');
    await user.click(screen.getByRole('button', { name: 'Crear DRAFT' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La fecha de ocurrencia no puede estar en el futuro');
    await user.click(screen.getByRole('button', { name: 'Enviar / publicar' }));
    await user.click(await screen.findByRole('button', { name: 'Aprobar y publicar' }));
    expect(await screen.findByText(/Historial publicado inmutable/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Enviar / publicar' })).not.toBeInTheDocument();
  });

  it('surfaces a controlled conflict and reuses the idempotency key on safe retry', async () => {
    const api = mockApi(identity, true); const user = userEvent.setup(); renderInventory('/inventory/receiving');
    await screen.findByRole('option', { name: 'Proveedor Norte' }); await user.selectOptions(screen.getByLabelText('Proveedor'), '71');
    await screen.findByRole('option', { name: 'Artículo #51 · KG' }); await user.selectOptions(screen.getByLabelText('Artículo / presentación'), '72');
    await user.type(screen.getByLabelText('Recibido'), '2'); await user.type(screen.getByLabelText('Aceptado'), '2'); await user.type(screen.getByLabelText('Costo unitario'), '20');
    await user.click(screen.getByRole('button', { name: 'Agregar línea' })); await user.click(screen.getByRole('button', { name: 'Crear un DRAFT con todas las líneas' })); await user.click(await screen.findByRole('button', { name: 'Aceptar una vez y publicar todas las líneas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El estado cambió en otra sesión');
    await user.click(screen.getByRole('button', { name: 'Aceptar una vez y publicar todas las líneas' }));
    await waitFor(() => expect(api.calls.filter(({ url }) => url.includes(':accept'))).toHaveLength(2));
    const acceptanceCalls = api.calls.filter(({ url }) => url.includes(':accept'));
    expect(new Headers(acceptanceCalls[0].init?.headers).get('Idempotency-Key')).toBe(new Headers(acceptanceCalls[1].init?.headers).get('Idempotency-Key'));
  });

  it('makes approval explicit and renders evidence-classified unexplained variance', async () => {
    mockApi(); const user = userEvent.setup(); renderInventory('/inventory/losses');
    await screen.findByRole('heading', { name: 'Registrar pérdida dedicada' }); await user.selectOptions(screen.getByLabelText('Artículo'), '51');
    await user.type(screen.getByLabelText('Cantidad'), '1'); await user.type(screen.getByLabelText(/Razón/), 'Daño'); await user.click(screen.getByRole('button', { name: 'Crear DRAFT' }));
    await user.click(await screen.findByRole('button', { name: 'Enviar / publicar' }));
    expect(await screen.findByText(/APROBACIÓN OBLIGATORIA/)).toBeVisible(); expect(screen.getByText(/Movimiento de pérdida: NO PUBLICADO/)).toBeVisible();
    cleanup(); mockApi(); renderInventory('/inventory/reconciliation');
    expect(await screen.findByText('Varianza sin explicar')).toBeVisible();
    expect(screen.getByText(/no se etiqueta como merma, robo o consumo sin evidencia/)).toBeVisible();
  });

  it('denies inventory routing and navigation without inventory.read', async () => {
    mockApi({ ...identity, permissions: ['location.read'] }); renderInventory('/inventory');
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Inventario' })).not.toBeInTheDocument());
  });
});
