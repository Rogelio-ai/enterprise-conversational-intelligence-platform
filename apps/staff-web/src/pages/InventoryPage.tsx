import { useMemo, useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { NavLink, useParams } from 'react-router-dom';
import type { GoodsReceipt, InventoryIntelligence, InventoryLoss, PhysicalCount, PurchaseOrder } from '../api/contracts';
import { ApiError, staffApi } from '../api/client';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';
import { PurchaseOrders } from './PurchaseOrders';
import { Preparations } from './Preparations';
import { Lots, Replenishment, Valuation } from './InventoryPlanning';

const views = [
  ['overview', 'Resumen'], ['stock', 'Existencias'], ['receiving', 'Recepción'], ['purchase-orders', 'Órdenes de compra'], ['preparations', 'Preparaciones'],
  ['replenishment', 'Reabastecimiento'], ['lots', 'Lotes'], ['valuation', 'Valuación'],
  ['losses', 'Pérdidas'], ['counts', 'Conteos físicos'], ['reconciliation', 'Conciliación'],
] as const;

const quantity = (value: string | null | undefined) => value == null ? 'NO DISPONIBLE' : new Intl.NumberFormat('es-MX', { maximumFractionDigits: 6 }).format(Number(value));
const money = (value: string | null | undefined, currency: string | null | undefined) => value == null || !currency ? 'NO DERIVABLE' : new Intl.NumberFormat('es-MX', { style: 'currency', currency }).format(Number(value));
const stamp = (value: string | null | undefined) => value ? new Date(value).toLocaleString('es-MX') : 'Sin actividad material';
const attentionLabels: Record<string, string> = {
  NEGATIVE_STOCK: 'Stock negativo', WARN_POLICY: 'Política: advertir', BLOCK_POLICY: 'Política: bloquear',
  STANDARD_COST_NON_DERIVABLE: 'Sin costo estándar vigente', PURCHASE_COST_NOT_AVAILABLE: 'Sin compras aceptadas recientes',
};
const lossCategories: Record<string, string> = {
  WASTE: 'Merma operativa', SPOILAGE: 'Deterioro', BREAKAGE: 'Rotura', EXPIRY: 'Caducidad',
  PREPARATION_LOSS: 'Pérdida de preparación', OTHER: 'Otra causa',
};

interface ReceiptDraftLine {
  offeringId: number;
  inventoryItemId: number;
  purchaseUom: string;
  received: string;
  accepted: string;
  rejected: string;
  unitCost: string;
  currency: string;
  lotCode: string;
  manufactureDate: string;
  expiryDate: string;
  bestBeforeDate: string;
  purchaseOrderLineId?: number;
}

function errorMessage(error: unknown) {
  if (!(error instanceof ApiError)) return 'No pudimos completar la operación.';
  if (error.kind === 'network') return 'No hay conexión con el servicio. Conservamos tus datos capturados; intenta nuevamente.';
  if (error.status === 409) return 'El estado cambió en otra sesión. Actualiza y revisa antes de reintentar.';
  if (error.status === 403) return 'Tu identidad no tiene permiso para esta acción.';
  if (error.status === 404) return 'El recurso no existe en la ubicación autorizada.';
  if (error.code.toLowerCase().includes('uom')) return 'La conversión de unidad no es válida o no está configurada.';
  if (error.message.toLowerCase().includes('full count is incomplete')) return 'El conteo FULL está incompleto. Registra explícitamente cada artículo requerido; usa cero sólo cuando el artículo fue contado en cero.';
  if (error.message.toLowerCase().includes('occurrence time') && error.message.toLowerCase().includes('future')) return 'La fecha de ocurrencia no puede estar en el futuro. Corrígela y vuelve a intentar.';
  if (error.status === 422) return 'Revisa los datos capturados. El servidor rechazó uno o más valores.';
  return 'No pudimos completar la operación. Revisa el estado actual antes de volver a intentar.';
}

function Feedback({ error, success }: { error?: unknown; success?: string }) {
  if (error) return <p className="inventory-feedback inventory-feedback--error" role="alert">{errorMessage(error)}</p>;
  return success ? <p className="inventory-feedback inventory-feedback--success" role="status">{success}</p> : null;
}

function Metric({ label, value, attention }: { label: string; value: number; attention?: boolean }) {
  return <div className={attention ? 'inventory-metric inventory-metric--attention' : 'inventory-metric'}><span>{label}</span><strong>{value}</strong></div>;
}

function Overview({ data }: { data: InventoryIntelligence }) {
  return <div className="inventory-stack">
    <section className="inventory-metrics" aria-label="Indicadores de inventario">
      <Metric label="Almacenes activos" value={data.active_warehouse_count} />
      <Metric label="Artículos activos" value={data.active_inventory_item_count} />
      <Metric label="Posiciones" value={data.stock_position_count} />
      <Metric label="Stock negativo" value={data.negative_stock_count} attention={data.negative_stock_count > 0} />
      <Metric label="Conteos por atender" value={data.counts_requiring_action} attention={data.counts_requiring_action > 0} />
      <Metric label="Conciliaciones abiertas" value={data.reconciliations_requiring_action} attention={data.reconciliations_requiring_action > 0} />
    </section>
    <div className="inventory-two-columns">
      <section className="inventory-panel"><h2>Entradas aceptadas recientes</h2>{data.recent_receipts.length ? <ul className="inventory-activity">{data.recent_receipts.map((item) => <li key={item.id}><strong>{item.label}</strong><span>Recepción #{item.id} · ACEPTADA · {stamp(item.occurred_at)}</span></li>)}</ul> : <p className="inventory-empty">No hay recepciones aceptadas recientes.</p>}</section>
      <section className="inventory-panel"><h2>Atención operativa</h2>{data.recent_losses.filter((item) => item.status === 'PENDING_APPROVAL').map((item) => <p key={item.id} className="inventory-alert">Pérdida #{item.id}: requiere aprobación y todavía no reduce existencias.</p>)}{data.negative_stock_count === 0 && data.counts_requiring_action === 0 && data.reconciliations_requiring_action === 0 ? <p className="inventory-empty">Todo al día. No hay alertas operativas pendientes.</p> : null}<p className="inventory-source">Lectura actualizada con evidencia confirmada por el servidor.</p></section>
    </div>
  </div>;
}

function Stock({ data }: { data: InventoryIntelligence }) {
  return <section className="inventory-panel"><div className="inventory-panel-heading"><div><h2>Stock actual por almacén</h2><p>Existencias consolidadas por el servidor a partir de movimientos confirmados.</p></div></div>
    {!data.stock.length ? <p className="inventory-empty">No hay artículos activos para mostrar. Cuando se habiliten artículos, sus existencias aparecerán aquí.</p> : <div className="inventory-table-wrap" tabIndex={0} aria-label="Tabla de existencias; desplázate horizontalmente si es necesario"><table className="inventory-table"><thead><tr><th>Artículo</th><th>Almacén</th><th>Cantidad</th><th>Política / atención</th><th>Actividad</th>{data.cost_visible ? <><th>Costos de referencia</th><th>Valor a costo estándar</th></> : null}</tr></thead><tbody>{data.stock.map((row) => <tr key={`${row.warehouse_id}-${row.inventory_item_id}`}><td><strong>{row.name}</strong><small>{row.code} · {row.base_uom}</small></td><td>{row.warehouse_name}</td><td className={Number(row.quantity) < 0 ? 'inventory-negative' : ''}>{quantity(row.quantity)} {row.base_uom}</td><td><span className="inventory-badge">{attentionLabels[`${row.negative_stock_policy}_POLICY`] ?? row.negative_stock_policy}</span>{row.attention.filter((state) => state !== `${row.negative_stock_policy}_POLICY`).map((state) => <small key={state}>{attentionLabels[state] ?? 'Requiere revisión'}</small>)}</td><td>{stamp(row.last_material_activity_at)}</td>{data.cost_visible ? <><td><small><strong>Costo estándar</strong> {money(row.standard_unit_cost, row.cost_currency)}</small><small><strong>Última compra aceptada</strong> {money(row.purchase_cost?.last_purchase_cost, row.purchase_cost?.currency)}</small><small><strong>Costo ponderado de compra 30/60/90</strong> {money(row.purchase_cost?.recent_weighted_purchase_cost, row.purchase_cost?.currency)}{row.purchase_cost?.selected_window_days ? ` · ventana ${row.purchase_cost.selected_window_days} días` : ' · evidencia insuficiente'}</small></td><td>{money(row.inventory_value_at_standard_cost, row.cost_currency)}<small>Existencia × costo estándar vigente</small></td></> : null}</tr>)}</tbody></table></div>}
    {data.cost_visible ? <p className="inventory-privacy">El costo ponderado reciente resume compras aceptadas; no es valuación promedio de inventario ni FIFO.</p> : null}
    {!data.cost_visible ? <p className="inventory-privacy">Costos y valores no fueron incluidos en la respuesta del servidor.</p> : null}
  </section>;
}

function Receiving({ data, refresh }: { data: InventoryIntelligence; refresh: () => void }) {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [supplierId, setSupplierId] = useState(0);
  const [offeringId, setOfferingId] = useState(0);
  const [received, setReceived] = useState('');
  const [accepted, setAccepted] = useState('');
  const [rejected, setRejected] = useState('0');
  const [unitCost, setUnitCost] = useState('');
  const [currency, setCurrency] = useState('MXN');
  const [lotCode, setLotCode] = useState('');
  const [manufactureDate, setManufactureDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [bestBeforeDate, setBestBeforeDate] = useState('');
  const [reference, setReference] = useState('');
  const [draftLines, setDraftLines] = useState<ReceiptDraftLine[]>([]);
  const [compositionError, setCompositionError] = useState<string>();
  const [receipt, setReceipt] = useState<GoodsReceipt | null>(null);
  const [purchaseOrderId, setPurchaseOrderId] = useState(0);
  const keys = useRef(new Map<string, string>());
  const suppliers = useQuery({ queryKey: ['inventory', 'suppliers', location?.id], queryFn: () => staffApi.inventorySuppliers(location!.id), enabled: Boolean(location && hasPermission('inventory.receipt.manage')), retry: false });
  const purchaseOrders = useQuery({ queryKey: ['inventory', 'purchase-orders', location?.id], queryFn: () => staffApi.purchaseOrders(location!.id), enabled: Boolean(location && hasPermission('inventory.purchase_order.read')), retry: false });
  const offerings = useQuery({ queryKey: ['inventory', 'offerings', location?.id, supplierId], queryFn: () => staffApi.inventoryOfferings(location!.id, supplierId), enabled: Boolean(location && supplierId), retry: false });
  const selectedOffering = offerings.data?.items.find((item) => item.id === offeringId);
  const selectedPurchaseOrder = purchaseOrders.data?.items.find((item) => item.id === purchaseOrderId);
  const commandKey = (name: string) => { const found = keys.current.get(name); if (found) return found; const value = crypto.randomUUID(); keys.current.set(name, value); return value; };
  const create = useMutation({
    mutationFn: () => staffApi.createGoodsReceipt({
      supplier_id: supplierId, location_id: location!.id,
      warehouse_id: selectedPurchaseOrder?.warehouse_id ?? data.warehouses[0]?.id, external_reference: reference || null,
      purchase_order_id: purchaseOrderId || null,
      lines: draftLines.map((line) => ({
        supplier_offering_id: line.offeringId, received_quantity: line.received,
        accepted_quantity: line.accepted, rejected_quantity: line.rejected,
        unit_cost: line.unitCost, currency: line.currency,
        lot_code: line.lotCode || null, manufacture_date: line.manufactureDate || null,
        expiry_date: line.expiryDate || null, best_before_date: line.bestBeforeDate || null,
        purchase_order_line_id: line.purchaseOrderLineId ?? null,
      })),
    }),
    onSuccess: (value) => { setReceipt(value); void queryClient.invalidateQueries({ queryKey: ['inventory'] }); },
  });
  const acceptReceipt = useMutation({ mutationFn: () => staffApi.acceptGoodsReceipt(receipt!.id, receipt!.version, commandKey(`accept-${receipt!.id}`)), onSuccess: (value) => { keys.current.delete(`accept-${value.id}`); setReceipt(value); refresh(); void queryClient.invalidateQueries({ queryKey: ['inventory', 'purchase-orders'] }); } });
  const addLine = () => {
    if (!selectedOffering || !received || !accepted || !rejected || !unitCost) return;
    if (draftLines.some((line) => line.offeringId === selectedOffering.id)) {
      setCompositionError('La presentación ya está incluida; edita su línea en la revisión.');
      return;
    }
    setDraftLines((lines) => [...lines, {
      offeringId: selectedOffering.id, inventoryItemId: selectedOffering.inventory_item_id,
      purchaseUom: selectedOffering.purchase_uom, received, accepted, rejected,
      unitCost, currency, lotCode, manufactureDate, expiryDate, bestBeforeDate,
      purchaseOrderLineId: selectedPurchaseOrder?.lines.find((line) => line.supplier_offering_id === selectedOffering.id)?.id,
    }]);
    setOfferingId(0); setReceived(''); setAccepted(''); setRejected('0'); setUnitCost(''); setLotCode(''); setManufactureDate(''); setExpiryDate(''); setBestBeforeDate(''); setCompositionError(undefined);
  };
  const updateLine = (index: number, field: 'received' | 'accepted' | 'rejected' | 'unitCost' | 'currency', value: string) => {
    setDraftLines((lines) => lines.map((line, current) => current === index ? { ...line, [field]: field === 'currency' ? value.toUpperCase() : value } : line));
  };
  if (!hasPermission('inventory.receipt.manage')) return <section className="inventory-panel"><h2>Recepción</h2><p className="inventory-denied">Tu perfil no permite crear recepciones en esta ubicación.</p></section>;
  return <div className="inventory-two-columns">
    <section className="inventory-panel inventory-form"><h2>Nueva recepción directa</h2><p className="inventory-state-note">Compón una sola recepción con todas sus líneas. El DRAFT no modifica stock; solo ACEPTAR publica el conjunto atómicamente.</p>
      {suppliers.isPending ? <p role="status">Cargando proveedores autorizados…</p> : null}
      <Feedback error={suppliers.error || offerings.error} />
      {hasPermission('inventory.purchase_order.read') ? <label>Orden de compra (opcional)<select value={purchaseOrderId} onChange={(event) => { const id = Number(event.target.value); const order = purchaseOrders.data?.items.find((value) => value.id === id); setPurchaseOrderId(id); if (order) setSupplierId(order.supplier_id); setDraftLines([]); }}><option value="">Recepción directa</option>{purchaseOrders.data?.items.filter((value) => ['APPROVED','PARTIALLY_RECEIVED'].includes(value.status)).map((value) => <option value={value.id} key={value.id}>#{value.id} · {value.status}</option>)}</select></label> : null}
      <label>Proveedor<select value={supplierId} required disabled={Boolean(receipt)} onChange={(event) => { setSupplierId(Number(event.target.value)); setOfferingId(0); setDraftLines([]); }}><option value="">Seleccionar</option>{suppliers.data?.items.filter((item) => item.status === 'ACTIVE').map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <label>Artículo / presentación<select value={offeringId} required onChange={(event) => setOfferingId(Number(event.target.value))}><option value="">Seleccionar</option>{offerings.data?.items.filter((item) => item.status === 'ACTIVE' && (!selectedPurchaseOrder || selectedPurchaseOrder.lines.some((line) => line.supplier_offering_id === item.id && Number(line.remaining_quantity) > 0))).map((item) => <option value={item.id} key={item.id}>Artículo #{item.inventory_item_id} · {item.purchase_uom}</option>)}</select></label>
      <div className="inventory-form-grid"><label>Recibido<input inputMode="decimal" required value={received} onChange={(event) => { setReceived(event.target.value); if (!accepted) setAccepted(event.target.value); }} /></label><label>Aceptado<input inputMode="decimal" required value={accepted} onChange={(event) => setAccepted(event.target.value)} /></label><label>Rechazado<input inputMode="decimal" required value={rejected} onChange={(event) => setRejected(event.target.value)} /></label></div>
      <p>UOM congelada: <strong>{selectedOffering?.purchase_uom ?? 'Selecciona una presentación'}</strong></p>
      <div className="inventory-form-grid"><label>Costo unitario<input inputMode="decimal" required value={unitCost} onChange={(event) => setUnitCost(event.target.value)} /></label><label>Moneda<input maxLength={3} required value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label></div>
      <fieldset className="inventory-line-composer"><legend>Trazabilidad de lote (según política del artículo)</legend><label>Código de lote<input maxLength={100} value={lotCode} onChange={(event)=>setLotCode(event.target.value)}/></label><label>Fabricación<input type="date" value={manufactureDate} onChange={(event)=>setManufactureDate(event.target.value)}/></label><label>Caducidad<input type="date" value={expiryDate} onChange={(event)=>setExpiryDate(event.target.value)}/></label><label>Consumo preferente<input type="date" value={bestBeforeDate} onChange={(event)=>setBestBeforeDate(event.target.value)}/></label></fieldset>
      <button type="button" className="secondary-button" disabled={!selectedOffering || !received || !accepted || !rejected || !unitCost} onClick={addLine}>Agregar línea</button>
      {compositionError ? <p className="inventory-feedback inventory-feedback--error" role="alert">{compositionError}</p> : null}
      <label>Referencia externa<input value={reference} onChange={(event) => setReference(event.target.value)} /></label>
      <button type="button" className="primary-button" disabled={create.isPending || !data.warehouses.length || !draftLines.length || Boolean(receipt)} onClick={() => create.mutate()}>{create.isPending ? 'Guardando…' : 'Crear un DRAFT con todas las líneas'}</button><Feedback error={create.error} />
    </section>
    <section className="inventory-panel"><h2>Revisión y publicación</h2>
      {!receipt && draftLines.length ? <div className="inventory-table-wrap" tabIndex={0} aria-label="Revisión de líneas; desplázate horizontalmente si es necesario"><table className="inventory-table"><thead><tr><th>Artículo/UOM</th><th>Recibido</th><th>Aceptado</th><th>Rechazado</th><th>Costo</th><th>Acción</th></tr></thead><tbody>{draftLines.map((line, index) => <tr key={line.offeringId}><td>#{line.inventoryItemId}<small>{line.purchaseUom}</small></td><td><input inputMode="decimal" aria-label={`Recibido línea ${index + 1}`} value={line.received} onChange={(event) => updateLine(index, 'received', event.target.value)} /></td><td><input inputMode="decimal" aria-label={`Aceptado línea ${index + 1}`} value={line.accepted} onChange={(event) => updateLine(index, 'accepted', event.target.value)} /></td><td><input inputMode="decimal" aria-label={`Rechazado línea ${index + 1}`} value={line.rejected} onChange={(event) => updateLine(index, 'rejected', event.target.value)} /></td><td><input inputMode="decimal" aria-label={`Costo línea ${index + 1}`} value={line.unitCost} onChange={(event) => updateLine(index, 'unitCost', event.target.value)} /><input aria-label={`Moneda línea ${index + 1}`} maxLength={3} value={line.currency} onChange={(event) => updateLine(index, 'currency', event.target.value)} /></td><td><button type="button" className="secondary-button" onClick={() => setDraftLines((lines) => lines.filter((_, current) => current !== index))}>Quitar línea {index + 1}</button></td></tr>)}</tbody></table></div> : null}
      {receipt ? <><p className={`inventory-lifecycle inventory-lifecycle--${receipt.status.toLowerCase()}`}>{receipt.status === 'DRAFT' ? 'DRAFT · SIN CAMBIO DE STOCK' : receipt.status === 'ACCEPTED' ? 'ACCEPTED · STOCK PUBLICADO' : receipt.status}</p><dl className="inventory-evidence"><div><dt>Recepción</dt><dd>#{receipt.id}</dd></div><div><dt>Versión</dt><dd>{receipt.version}</dd></div><div><dt>Líneas</dt><dd>{receipt.lines.length}</dd></div><div><dt>Movimientos</dt><dd>{receipt.lines.every((line) => line.stock_movement_id) ? receipt.lines.map((line) => `#${line.stock_movement_id}`).join(', ') : 'No publicados'}</dd></div></dl><ul className="inventory-activity">{receipt.lines.map((line, index) => <li key={line.id}><strong>Línea {index + 1} · artículo #{line.inventory_item_id}</strong><span>{line.accepted_quantity} aceptado + {line.rejected_quantity} rechazado = {line.received_quantity} {line.source_uom} · {money(line.unit_cost, line.currency)}</span></li>)}</ul>{receipt.status === 'DRAFT' && hasPermission('inventory.receipt.accept') ? <button className="danger-button" disabled={acceptReceipt.isPending} onClick={() => acceptReceipt.mutate()}>{acceptReceipt.isPending ? 'Aceptando…' : 'Aceptar una vez y publicar todas las líneas'}</button> : null}<Feedback error={acceptReceipt.error} success={receipt.status === 'ACCEPTED' ? 'Recepción completa aceptada; el conjunto autoritativo de movimientos fue confirmado.' : undefined} /></> : !draftLines.length ? <p className="inventory-empty">Agrega líneas para revisar el borrador antes de crearlo.</p> : null}
    </section>
  </div>;
}

function Losses({ data, refresh }: { data: InventoryIntelligence; refresh: () => void }) {
  const { location } = useStaffContext(); const { hasPermission } = useAuth(); const queryClient = useQueryClient();
  const [itemId, setItemId] = useState(0); const [category, setCategory] = useState('WASTE'); const [amount, setAmount] = useState(''); const [uom, setUom] = useState(''); const [reason, setReason] = useState(''); const [occurredAt, setOccurredAt] = useState(''); const [current, setCurrent] = useState<InventoryLoss | null>(null); const keys = useRef(new Map<string, string>());
  const losses = useQuery({ queryKey: ['inventory', 'losses', location?.id], queryFn: () => staffApi.inventoryLosses(location!.id), enabled: Boolean(location && hasPermission('inventory.loss.read')), retry: false });
  const selected = data.stock.find((row) => row.inventory_item_id === itemId);
  const create = useMutation({ mutationFn: () => staffApi.createInventoryLoss({ warehouse_id: data.warehouses[0]?.id, inventory_item_id: itemId, category, source_quantity: amount, source_uom: uom || selected?.base_uom, reason: reason || null, occurred_at: occurredAt ? new Date(occurredAt).toISOString() : null }), onSuccess: (value) => { setCurrent(value); void queryClient.invalidateQueries({ queryKey: ['inventory', 'losses'] }); } });
  const act = useMutation({ mutationFn: (action: 'post' | 'approve') => { const name = `${action}-${current!.id}`; let key = keys.current.get(name); if (!key) { key = crypto.randomUUID(); keys.current.set(name, key); } return staffApi.actOnInventoryLoss(current!.id, action, current!.version, key); }, onSuccess: (value) => { keys.current.clear(); setCurrent(value); refresh(); void queryClient.invalidateQueries({ queryKey: ['inventory', 'losses'] }); } });
  if (!hasPermission('inventory.loss.read')) return <section className="inventory-panel"><h2>Pérdidas</h2><p className="inventory-denied">Sin permiso para consultar pérdidas.</p></section>;
  return <div className="inventory-two-columns"><form className="inventory-panel inventory-form" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><h2>Registrar pérdida dedicada</h2><p className="inventory-state-note">Una pérdida en borrador o pendiente de aprobación todavía no reduce existencias.</p><label>Artículo<select required value={itemId} onChange={(event) => { const id = Number(event.target.value); setItemId(id); setUom(data.stock.find((row) => row.inventory_item_id === id)?.base_uom ?? ''); }}><option value="">Seleccionar</option>{data.stock.filter((row, index, rows) => rows.findIndex((other) => other.inventory_item_id === row.inventory_item_id) === index).map((row) => <option value={row.inventory_item_id} key={row.inventory_item_id}>{row.name}</option>)}</select></label><label>Categoría<select value={category} onChange={(event) => setCategory(event.target.value)}>{Object.entries(lossCategories).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><div className="inventory-form-grid"><label>Cantidad<input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} /></label><label>Unidad de medida<input required value={uom} onChange={(event) => setUom(event.target.value.toUpperCase())} /></label></div><label>Fecha/hora de ocurrencia (opcional)<input type="datetime-local" value={occurredAt} onChange={(event) => setOccurredAt(event.target.value)} /></label><small>Si se omite, el servidor asigna la hora actual. El costo histórico se determina para la fecha efectiva.</small><label>Razón {category === 'OTHER' ? '(obligatoria)' : ''}<textarea required={category === 'OTHER'} value={reason} onChange={(event) => setReason(event.target.value)} /></label><button className="primary-button" disabled={create.isPending || !hasPermission('inventory.loss.manage')}>{create.isPending ? 'Guardando borrador…' : 'Crear DRAFT'}</button><Feedback error={create.error} /></form><section className="inventory-panel"><h2>Flujo de aprobación</h2><Feedback error={losses.error} />{losses.isPending ? <p role="status">Cargando pérdidas registradas…</p> : null}{current ? <><p className={`inventory-lifecycle inventory-lifecycle--${current.status.toLowerCase()}`}>{current.status}</p><p>Ocurrencia confirmada: <strong>{stamp(current.occurred_at)}</strong></p><p>{current.approval_required ? 'APROBACIÓN OBLIGATORIA antes de reducir existencias.' : 'La necesidad de aprobación se determina al enviar.'}</p>{current.status === 'DRAFT' ? <button className="danger-button" disabled={act.isPending} onClick={() => act.mutate('post')}>{act.isPending ? 'Verificando…' : 'Enviar / publicar'}</button> : null}{current.status === 'PENDING_APPROVAL' && hasPermission('inventory.loss.approve') ? <button className="danger-button" disabled={act.isPending} onClick={() => act.mutate('approve')}>{act.isPending ? 'Publicando…' : 'Aprobar y publicar'}</button> : null}<p>Movimiento de pérdida: {current.stock_movement_id ? `#${current.stock_movement_id}` : 'NO PUBLICADO'}</p>{current.reversal_stock_movement_id ? <p>Movimiento de reversión: <strong>#{current.reversal_stock_movement_id}</strong></p> : null}{current.status === 'POSTED' ? <p className="inventory-state-note">Historial publicado inmutable: la ocurrencia y su evidencia de costo ya no se editan.</p> : null}<Feedback error={act.error} success={current.status === 'POSTED' ? 'Pérdida publicada; las existencias ya reflejan el movimiento confirmado.' : undefined} /></> : <p className="inventory-empty">{losses.data?.items.length === 0 ? 'No hay pérdidas registradas. Usa el formulario para crear el primer borrador.' : 'Selecciona una pérdida para revisar su estado o registra una nueva.'}</p>}<div className="inventory-selection-list">{losses.data?.items.slice(0, 8).map((item) => <button type="button" className="inventory-selection" aria-pressed={current?.id === item.id} key={item.id} onClick={() => setCurrent(item)}>#{item.id} · {lossCategories[item.category] ?? item.category} · {item.status} · {quantity(item.source_quantity)} {item.source_uom}</button>)}</div></section></div>;
}

function Counts({ data, refresh }: { data: InventoryIntelligence; refresh: () => void }) {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState<PhysicalCount | null>(null);
  const [countScope, setCountScope] = useState<'PARTIAL' | 'FULL'>('PARTIAL');
  const [itemId, setItemId] = useState(0);
  const [amount, setAmount] = useState('');
  const [reference, setReference] = useState('');
  const keys = useRef(new Map<string, string>());
  const counts = useQuery({ queryKey: ['inventory', 'counts', location?.id], queryFn: () => staffApi.physicalCounts(location!.id), enabled: Boolean(location && hasPermission('inventory.count.read')), retry: false });
  const selected = data.stock.find((row) => row.inventory_item_id === itemId);
  const create = useMutation({ mutationFn: () => staffApi.createPhysicalCount({ warehouse_id: data.warehouses[0]?.id, count_scope: countScope, reason: 'Conteo físico operativo', reference: reference || null }), onSuccess: (value) => { setCurrent(value); void queryClient.invalidateQueries({ queryKey: ['inventory', 'counts'] }); } });
  const putLine = useMutation({ mutationFn: () => { const line = current!.lines.find((value) => value.inventory_item_id === itemId); return staffApi.putPhysicalCountLine(current!.id, itemId, { expected_count_version: current!.version, expected_line_version: line?.version ?? 0, source_quantity: amount, source_uom: selected!.base_uom }); }, onSuccess: setCurrent });
  const transition = useMutation({ mutationFn: (action: 'submit' | 'approve' | 'post') => { const name = `${action}-${current!.id}`; let key = keys.current.get(name); if (!key) { key = crypto.randomUUID(); keys.current.set(name, key); } return staffApi.transitionPhysicalCount(current!.id, action, current!.version, action === 'post' ? key : undefined); }, onSuccess: (value) => { keys.current.clear(); setCurrent(value); refresh(); void queryClient.invalidateQueries({ queryKey: ['inventory', 'counts'] }); } });
  if (!hasPermission('inventory.count.read')) return <section className="inventory-panel"><h2>Conteos físicos</h2><p className="inventory-denied">Sin permiso para consultar conteos.</p></section>;
  return <div className="inventory-two-columns">
    <section className="inventory-panel inventory-form">
      <h2>Abrir conteo</h2>
      <Feedback error={counts.error || create.error} />
      {counts.isPending ? <p role="status">Cargando conteos físicos…</p> : null}
      <label>Alcance<select value={countScope} onChange={(event) => setCountScope(event.target.value as 'PARTIAL' | 'FULL')}><option value="PARTIAL">PARTIAL · sólo observaciones explícitas</option><option value="FULL">FULL · cobertura completa</option></select></label>
      {countScope === 'FULL' ? <p className="inventory-alert">FULL exige una observación explícita para cada artículo activo del almacén. Cero debe registrarse como cero; una omisión seguirá siendo NO CONTADO y el servidor impedirá publicar.</p> : <p>PARTIAL conserva sólo las líneas capturadas; un artículo omitido no se interpreta como cero.</p>}
      <label>Referencia<input value={reference} onChange={(event) => setReference(event.target.value)} /></label>
      <button className="primary-button" disabled={create.isPending || !hasPermission('inventory.count.manage')} onClick={() => create.mutate()}>{create.isPending ? 'Abriendo conteo…' : 'Abrir conteo'}</button>
      {counts.data?.items.length === 0 ? <p className="inventory-empty">No hay conteos previos. Abre uno para comenzar.</p> : null}
      {counts.data?.items.slice(0, 5).map((value) => <button type="button" className="inventory-selection" aria-pressed={current?.id === value.id} key={value.id} onClick={() => setCurrent(value)}>#{value.id} · {value.count_scope} · {value.status} · {value.lines.length} contados</button>)}
    </section>
    <section className="inventory-panel">
      <h2>Captura y ciclo</h2>
      {current ? <>
        <p className="inventory-lifecycle">#{current.id} · {current.count_scope} · {current.status}</p>
        {current.count_scope === 'FULL' ? <p className="inventory-alert">Cobertura FULL: captura todos los artículos mostrados. Esta guía no sustituye la validación del servidor.</p> : null}
        <p className="inventory-state-note">Sin congelamiento: cursor {stamp(current.cursor_at)} / movimiento #{current.cursor_movement_id}. Las operaciones posteriores se preservan.</p>
        {['DRAFT','COUNTING'].includes(current.status) ? <form className="inventory-form" onSubmit={(event) => { event.preventDefault(); putLine.mutate(); }}>
          <label>Artículo<select required value={itemId} onChange={(event) => setItemId(Number(event.target.value))}><option value="">Seleccionar</option>{data.stock.filter((row) => row.warehouse_id === current.warehouse_id).map((row) => <option value={row.inventory_item_id} key={row.inventory_item_id}>{row.name} · {row.quantity} {row.base_uom}</option>)}</select></label>
          <label>Cantidad contada<input required inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
          <div className="inventory-actions"><button className="secondary-button" type="button" onClick={() => setAmount('0')}>Marcar CONTADO CERO</button><button className="primary-button" disabled={putLine.isPending}>{putLine.isPending ? 'Guardando…' : 'Guardar observación'}</button></div>
        </form> : null}
        <div className="inventory-count-grid">{data.stock.filter((row) => row.warehouse_id === current.warehouse_id).map((row) => { const line = current.lines.find((value) => value.inventory_item_id === row.inventory_item_id); return <div key={row.inventory_item_id} className={line ? 'inventory-counted' : 'inventory-not-counted'}><strong>{row.name}</strong><span>{line ? `CONTADO ${quantity(line.normalized_counted_quantity)} · esperado al cursor ${quantity(line.expected_quantity_at_cursor)} · varianza ${quantity(line.variance_quantity)}` : 'NO CONTADO'}</span></div>; })}</div>
        <div className="inventory-actions">
          {['DRAFT','COUNTING'].includes(current.status) && hasPermission('inventory.count.manage') ? <button className="danger-button" disabled={!current.lines.length || transition.isPending} onClick={() => transition.mutate('submit')}>{transition.isPending ? 'Enviando…' : 'Enviar'}</button> : null}
          {current.status === 'SUBMITTED' && hasPermission('inventory.count.approve') ? <button className="danger-button" disabled={transition.isPending} onClick={() => transition.mutate('approve')}>{transition.isPending ? 'Aprobando…' : 'Aprobar'}</button> : null}
          {current.status === 'APPROVED' && hasPermission('inventory.count.post') ? <button className="danger-button" disabled={transition.isPending} onClick={() => transition.mutate('post')}>{transition.isPending ? 'Publicando…' : 'Publicar ajustes'}</button> : null}
        </div>
        <Feedback error={putLine.error || transition.error} success={current.status === 'POSTED' ? 'Conteo publicado; ajustes confirmados y movimientos posteriores preservados.' : undefined} />
      </> : <p className="inventory-empty">Abre o selecciona un conteo. Los artículos ausentes permanecen NO CONTADOS.</p>}
    </section>
  </div>;
}

function Reconciliation({ data, refresh }: { data: InventoryIntelligence; refresh: () => void }) {
  const { location } = useStaffContext(); const { hasPermission } = useAuth(); const [periodStart, setPeriodStart] = useState(''); const [lineId, setLineId] = useState(0);
  const counts = useQuery({ queryKey: ['inventory', 'counts', location?.id], queryFn: () => staffApi.physicalCounts(location!.id), enabled: Boolean(location && hasPermission('inventory.reconciliation.manage')), retry: false });
  const create = useMutation({ mutationFn: () => staffApi.createInventoryReconciliation(lineId, new Date(periodStart).toISOString()), onSuccess: refresh });
  const close = useMutation({ mutationFn: ({ id, version }: { id: number; version: number }) => staffApi.closeInventoryReconciliation(id, version), onSuccess: refresh });
  return <div className="inventory-stack">{hasPermission('inventory.reconciliation.manage') ? <form className="inventory-panel inventory-form" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}><h2>Abrir conciliación</h2><Feedback error={counts.error || create.error} />{counts.isPending ? <p role="status">Cargando conteos publicados…</p> : null}<label>Línea de conteo publicado<select required value={lineId} onChange={(event) => setLineId(Number(event.target.value))}><option value="">Seleccionar</option>{counts.data?.items.filter((count) => count.status === 'POSTED').flatMap((count) => count.lines.map((line) => <option value={line.id} key={line.id}>Conteo #{count.id} · artículo #{line.inventory_item_id}</option>))}</select></label>{counts.data && !counts.data.items.some((count) => count.status === 'POSTED' && count.lines.length) ? <p className="inventory-empty">Aún no hay líneas de conteo publicadas. Publica un conteo para poder conciliar.</p> : null}<label>Inicio del periodo<input type="datetime-local" required value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} /></label><button className="primary-button" disabled={create.isPending}>{create.isPending ? 'Abriendo conciliación…' : 'Crear conciliación OPEN'}</button></form> : null}<section className="inventory-panel"><h2>Clasificación de variación</h2><p className="inventory-state-note">Cada concepto se presenta por separado. Una variación sin explicar no atribuye una causa sin evidencia.</p>{data.reconciliations.length ? <div className="inventory-reconciliations">{data.reconciliations.map((value) => <article key={value.id}><header><strong>Conciliación #{value.id} · {value.status}</strong>{value.status === 'OPEN' && hasPermission('inventory.reconciliation.manage') ? <button className="danger-button" disabled={close.isPending} onClick={() => close.mutate({ id: value.id, version: value.version })}>{close.isPending ? 'Cerrando…' : 'Cerrar y calcular'}</button> : null}</header><dl className="inventory-evidence">{[['Existencia inicial',value.opening_quantity],['Entradas recibidas',value.receipts],['Consumo teórico',value.theoretical_consumption],['Pérdidas registradas',value.registered_losses],['Otros ajustes',value.other_adjustments],['Observación física',value.physical_count],['Ajuste del conteo',value.count_adjustment],['Existencia final',value.closing_quantity],['Varianza sin explicar',value.unexplained_variance]].map(([label, amount]) => <div key={label}><dt>{label}</dt><dd>{quantity(amount)}</dd></div>)}</dl>{data.cost_visible ? <p>Valor de la varianza a costo estándar: <strong>{money(value.variance_value, value.currency)}</strong></p> : null}<p>Evidencia: {value.evidence_status ?? 'PENDIENTE'}. La varianza no se etiqueta como merma, robo o consumo sin evidencia.</p></article>)}</div> : <p className="inventory-empty">No hay conciliaciones para esta ubicación. Selecciona una línea de conteo publicada para crear la primera.</p>}<Feedback error={close.error} /></section></div>;
}

export function InventoryPage() {
  const { view = 'overview' } = useParams(); const activeView = views.some(([key]) => key === view) ? view : 'overview';
  const { location } = useStaffContext(); const [warehouseId, setWarehouseId] = useState<number | undefined>();
  const intelligence = useQuery({ queryKey: ['inventory', 'intelligence', location?.id, warehouseId], queryFn: () => staffApi.inventoryIntelligence(location!.id, warehouseId), enabled: Boolean(location), retry: false, refetchInterval: 30_000 });
  const data = intelligence.data; const refresh = () => { void intelligence.refetch(); };
  const hasWarehouses = Boolean(data?.warehouses.length);
  const title = useMemo(() => views.find(([key]) => key === activeView)?.[1] ?? 'Resumen', [activeView]);
  if (data && hasWarehouses && ['replenishment', 'lots', 'valuation'].includes(activeView)) {
    return <section className="inventory-page" aria-labelledby="inventory-heading"><header className="inventory-heading"><div><p className="eyebrow">Control de inventario · {location?.name}</p><h1 id="inventory-heading">Inventario</h1><p>{title}. Estado operativo confirmado por el servidor.</p></div></header><nav className="inventory-nav" aria-label="Secciones de inventario">{views.map(([key, label]) => <NavLink key={key} end={key === 'overview'} to={key === 'overview' ? '/inventory' : `/inventory/${key}`}>{label}</NavLink>)}</nav>{activeView === 'replenishment' ? <Replenishment data={data} /> : activeView === 'lots' ? <Lots data={data} /> : <Valuation data={data} />}</section>;
  }
  return <section className="inventory-page" aria-labelledby="inventory-heading"><header className="inventory-heading"><div><p className="eyebrow">Control de inventario · {location?.name}</p><h1 id="inventory-heading">Inventario</h1><p>{title}. Estado operativo confirmado por el servidor.</p></div><div><label>Almacén<select value={warehouseId ?? ''} onChange={(event) => setWarehouseId(event.target.value ? Number(event.target.value) : undefined)}><option value="">Todos</option>{data?.warehouses.map((value) => <option value={value.id} key={value.id}>{value.name}</option>)}</select></label><button className="secondary-button" disabled={intelligence.isFetching} onClick={refresh}>{intelligence.isFetching ? 'Actualizando…' : 'Actualizar'}</button></div></header><nav className="inventory-nav" aria-label="Secciones de inventario">{views.map(([key, label]) => <NavLink key={key} end={key === 'overview'} to={key === 'overview' ? '/inventory' : `/inventory/${key}`}>{label}</NavLink>)}</nav>{intelligence.isPending ? <div className="inventory-panel inventory-loading" role="status"><span className="state-spinner" aria-hidden="true">◌</span><span>Cargando inventario confirmado…</span></div> : null}{intelligence.isError ? <div className="inventory-panel inventory-feedback--error" role="alert"><strong>No fue posible cargar inventario.</strong><p>{errorMessage(intelligence.error)}</p><button className="secondary-button" onClick={refresh}>Reintentar</button></div> : null}{data && !hasWarehouses ? <div className="inventory-panel inventory-empty" role="status"><strong>No hay almacenes activos.</strong> Habilita un almacén para consultar o registrar operación de inventario.</div> : null}{data && hasWarehouses && activeView === 'overview' ? <Overview data={data} /> : null}{data && hasWarehouses && activeView === 'stock' ? <Stock data={data} /> : null}{data && hasWarehouses && activeView === 'receiving' ? <Receiving data={data} refresh={refresh} /> : null}{data && hasWarehouses && activeView === 'purchase-orders' ? <PurchaseOrders data={data} /> : null}{data && hasWarehouses && activeView === 'preparations' ? <Preparations data={data} /> : null}{data && hasWarehouses && activeView === 'losses' ? <Losses data={data} refresh={refresh} /> : null}{data && hasWarehouses && activeView === 'counts' ? <Counts data={data} refresh={refresh} /> : null}{data && hasWarehouses && activeView === 'reconciliation' ? <Reconciliation data={data} refresh={refresh} /> : null}</section>;
}
