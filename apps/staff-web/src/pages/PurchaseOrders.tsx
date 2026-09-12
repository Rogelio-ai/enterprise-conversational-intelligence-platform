import { useRef, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { NavLink } from 'react-router-dom';

import { ApiError, staffApi } from '../api/client';
import type { InventoryIntelligence, PurchaseOrder } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';

interface DraftLine {
  supplier_offering_id: number;
  ordered_quantity: string;
  agreed_unit_price: string;
  inventory_item_id: number;
  uom: string;
}

function money(value?: string | null, currency?: string | null) {
  if (value == null || !currency) return 'NO DISPONIBLE';
  return new Intl.NumberFormat('es-MX', {
    style: 'currency', currency, maximumFractionDigits: 6,
  }).format(Number(value));
}

function timestamp(value?: string | null) {
  return value ? new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value)) : 'Pendiente';
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : 'No fue posible completar la operación.';
}

export function PurchaseOrders({ data }: { data: InventoryIntelligence }) {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const commandKeys = useRef(new Map<string, string>());
  const [supplierId, setSupplierId] = useState(0);
  const [warehouseId, setWarehouseId] = useState(0);
  const [currency, setCurrency] = useState('MXN');
  const [delivery, setDelivery] = useState('');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [offeringId, setOfferingId] = useState(0);
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [editingLine, setEditingLine] = useState<number>();
  const [editingOrderId, setEditingOrderId] = useState<number>();
  const [current, setCurrent] = useState<PurchaseOrder | null>(null);
  const [compositionError, setCompositionError] = useState<string>();

  const orders = useQuery({
    queryKey: ['inventory', 'purchase-orders', location?.id],
    queryFn: () => staffApi.purchaseOrders(location!.id),
    enabled: Boolean(location && hasPermission('inventory.purchase_order.read')),
    retry: false,
  });
  const suppliers = useQuery({
    queryKey: ['inventory', 'suppliers', location?.id],
    queryFn: () => staffApi.inventorySuppliers(location!.id),
    enabled: Boolean(location && hasPermission('inventory.purchase_order.manage')),
    retry: false,
  });
  const offerings = useQuery({
    queryKey: ['inventory', 'offerings', location?.id, supplierId],
    queryFn: () => staffApi.inventoryOfferings(location!.id, supplierId),
    enabled: Boolean(location && supplierId), retry: false,
  });
  const selectedOffering = offerings.data?.items.find((value) => value.id === offeringId);

  const resetComposition = () => {
    setEditingOrderId(undefined); setSupplierId(0); setWarehouseId(0);
    setCurrency('MXN'); setDelivery(''); setReference(''); setNotes('');
    setOfferingId(0); setQuantity(''); setPrice(''); setLines([]);
    setEditingLine(undefined); setCompositionError(undefined);
  };
  const payload = () => ({
    location_id: location!.id,
    warehouse_id: warehouseId || data.warehouses[0].id,
    supplier_id: supplierId,
    currency,
    expected_delivery_at: delivery ? new Date(delivery).toISOString() : null,
    external_reference: reference || null,
    notes: notes || null,
    lines: lines.map(({ inventory_item_id: _item, uom: _uom, ...line }) => line),
  });
  const create = useMutation({
    mutationFn: () => staffApi.createPurchaseOrder(payload()),
    onSuccess: (value) => {
      setCurrent(value); resetComposition();
      void queryClient.invalidateQueries({ queryKey: ['inventory', 'purchase-orders'] });
    },
  });
  const amend = useMutation({
    mutationFn: () => staffApi.amendPurchaseOrder(editingOrderId!, {
      expected_version: current!.version,
      expected_delivery_at: delivery ? new Date(delivery).toISOString() : null,
      external_reference: reference || null, notes: notes || null,
      lines: lines.map(({ inventory_item_id: _item, uom: _uom, ...line }) => line),
    }),
    onSuccess: (value) => {
      setCurrent(value); resetComposition();
      void queryClient.invalidateQueries({ queryKey: ['inventory', 'purchase-orders'] });
    },
  });
  const action = useMutation({
    mutationFn: (name: 'submit' | 'approve' | 'cancel' | 'close') => {
      let key = commandKeys.current.get(name);
      if (!key) { key = crypto.randomUUID(); commandKeys.current.set(name, key); }
      return staffApi.actOnPurchaseOrder(current!.id, name, current!.version, key);
    },
    onSuccess: (value) => {
      setCurrent(value); commandKeys.current.clear();
      void queryClient.invalidateQueries({ queryKey: ['inventory', 'purchase-orders'] });
    },
  });

  const editDraft = () => {
    if (!current || current.status !== 'DRAFT') return;
    setEditingOrderId(current.id); setSupplierId(current.supplier_id);
    setWarehouseId(current.warehouse_id); setCurrency(current.currency ?? 'MXN');
    setDelivery(current.expected_delivery_at?.slice(0, 16) ?? '');
    setReference(current.external_reference ?? ''); setNotes(current.notes ?? '');
    setLines(current.lines.map((line) => ({
      supplier_offering_id: line.supplier_offering_id,
      ordered_quantity: line.ordered_quantity,
      agreed_unit_price: line.agreed_unit_price ?? '0',
      inventory_item_id: line.inventory_item_id, uom: line.source_uom,
    })));
    setCompositionError(undefined);
  };
  const addOrUpdateLine = () => {
    if (!selectedOffering || !quantity || price === '') return;
    const duplicate = lines.findIndex((line) => line.supplier_offering_id === offeringId);
    if (duplicate >= 0 && duplicate !== editingLine) {
      setCompositionError('La presentación ya forma parte de esta orden. Edítala en su línea actual.');
      return;
    }
    const next = {
      supplier_offering_id: selectedOffering.id,
      inventory_item_id: selectedOffering.inventory_item_id,
      ordered_quantity: quantity, agreed_unit_price: price,
      uom: selectedOffering.purchase_uom,
    };
    setLines((values) => editingLine == null
      ? [...values, next]
      : values.map((value, index) => index === editingLine ? next : value));
    setOfferingId(0); setQuantity(''); setPrice('');
    setEditingLine(undefined); setCompositionError(undefined);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!lines.length) { setCompositionError('Agrega al menos una línea.'); return; }
    if (editingOrderId) amend.mutate(); else create.mutate();
  };
  const formError = create.error || amend.error || suppliers.error || offerings.error;

  if (!hasPermission('inventory.purchase_order.read')) return (
    <section className="inventory-panel"><h2>Órdenes de compra</h2>
      <p className="inventory-denied">Sin permiso para consultar órdenes de compra.</p>
    </section>
  );

  return <div className="inventory-two-columns">
    {hasPermission('inventory.purchase_order.manage') ? <form className="inventory-panel inventory-form" onSubmit={submit}>
      <div className="inventory-panel-heading"><div>
        <h2>{editingOrderId ? `Editar orden #${editingOrderId}` : 'Nueva orden de compra'}</h2>
        <p className="inventory-state-note">Autoriza intención comercial. No modifica existencias; sólo una recepción ACEPTADA crea movimientos.</p>
      </div>{editingOrderId ? <button type="button" className="secondary-button" onClick={resetComposition}>Salir de edición</button> : null}</div>
      <div className="inventory-form-grid">
        <label>Proveedor<select required disabled={Boolean(editingOrderId)} value={supplierId} onChange={(event) => { setSupplierId(Number(event.target.value)); setOfferingId(0); setLines([]); }}><option value="">Seleccionar</option>{suppliers.data?.items.filter((value) => value.status === 'ACTIVE').map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
        <label>Almacén<select required disabled={Boolean(editingOrderId)} value={warehouseId || data.warehouses[0]?.id || ''} onChange={(event) => setWarehouseId(Number(event.target.value))}>{data.warehouses.map((value) => <option key={value.id} value={value.id}>{value.name}</option>)}</select></label>
        <label>Moneda<input required maxLength={3} disabled={Boolean(editingOrderId)} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} /></label>
      </div>
      <div className="inventory-form-grid">
        <label>Entrega esperada<input type="datetime-local" value={delivery} onChange={(event) => setDelivery(event.target.value)} /></label>
        <label>Referencia externa<input maxLength={200} value={reference} onChange={(event) => setReference(event.target.value)} /></label>
      </div>
      <label>Notas<textarea maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <fieldset className="inventory-line-composer"><legend>{editingLine == null ? 'Agregar línea' : `Editar línea ${editingLine + 1}`}</legend>
        <label>Presentación<select value={offeringId} onChange={(event) => setOfferingId(Number(event.target.value))}><option value="">Seleccionar</option>{offerings.data?.items.filter((value) => value.status === 'ACTIVE').map((value) => <option key={value.id} value={value.id}>Artículo #{value.inventory_item_id} · {value.purchase_uom}</option>)}</select></label>
        <div className="inventory-form-grid"><label>Cantidad ordenada<input inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} /></label><label>Precio acordado<input inputMode="decimal" value={price} onChange={(event) => setPrice(event.target.value)} /></label></div>
        <button type="button" className="secondary-button" disabled={!selectedOffering || !quantity || price === ''} onClick={addOrUpdateLine}>{editingLine == null ? 'Agregar línea' : 'Guardar línea'}</button>
      </fieldset>
      {lines.length ? <ol className="inventory-draft-lines">{lines.map((line, index) => <li key={line.supplier_offering_id}><span><strong>Artículo #{line.inventory_item_id}</strong><small>{line.ordered_quantity} {line.uom} · {money(line.agreed_unit_price, currency)}</small></span><span className="inventory-actions"><button type="button" className="secondary-button" onClick={() => { setEditingLine(index); setOfferingId(line.supplier_offering_id); setQuantity(line.ordered_quantity); setPrice(line.agreed_unit_price); }}>Editar línea {index + 1}</button><button type="button" className="secondary-button" onClick={() => setLines((values) => values.filter((_, lineIndex) => lineIndex !== index))}>Quitar línea {index + 1}</button></span></li>)}</ol> : <p className="inventory-empty">Agrega varias presentaciones para crear una sola orden comercial.</p>}
      {compositionError ? <p className="inventory-feedback inventory-feedback--error" role="alert">{compositionError}</p> : null}
      {formError ? <p className="inventory-feedback inventory-feedback--error" role="alert">{errorMessage(formError)}</p> : null}
      <button className="primary-button" disabled={!lines.length || create.isPending || amend.isPending}>{create.isPending || amend.isPending ? 'Guardando…' : editingOrderId ? 'Guardar cambios del DRAFT' : 'Crear DRAFT'}</button>
    </form> : null}

    <section className="inventory-panel" aria-labelledby="purchase-order-detail-heading">
      <div className="inventory-panel-heading"><div><h2 id="purchase-order-detail-heading">Seguimiento y autorización</h2><p>Progreso derivado de recepciones aceptadas; los rechazos permanecen como evidencia.</p></div></div>
      {orders.isPending ? <p role="status">Cargando órdenes…</p> : null}
      {orders.error ? <p className="inventory-feedback inventory-feedback--error" role="alert">{errorMessage(orders.error)}</p> : null}
      {current ? <div className="inventory-stack">
        <p className={`inventory-lifecycle inventory-lifecycle--${current.status.toLowerCase()}`}>#{current.id} · {current.status}</p>
        <dl className="inventory-evidence"><div><dt>Proveedor</dt><dd>#{current.supplier_id}</dd></div><div><dt>Almacén</dt><dd>#{current.warehouse_id}</dd></div><div><dt>Versión</dt><dd>{current.version}</dd></div><div><dt>Entrega</dt><dd>{timestamp(current.expected_delivery_at)}</dd></div><div><dt>Recepciones vinculadas</dt><dd>{current.receipts?.length ?? 0}</dd></div><div><dt>Efecto de la OC</dt><dd>CERO movimientos</dd></div></dl>
        {current.lines.map((line) => <article className="inventory-state-note" key={line.id}><strong>Línea {line.line_number} · artículo #{line.inventory_item_id}</strong><p>Ordenado {line.ordered_quantity} · Aceptado {line.accepted_quantity} · Rechazado {line.rejected_quantity} · Pendiente {line.remaining_quantity} {line.source_uom}</p><small>{current.cost_visible ? <>Acordado {money(line.agreed_unit_price, line.currency)} · recibido {money(line.received_unit_price, line.currency)} · variación {money(line.price_variance, line.currency)}{line.price_variance_percentage != null ? ` (${line.price_variance_percentage}%)` : ''}</> : 'Información monetaria protegida por permisos.'}</small>{line.receipt_allocations?.length ? <small>Recepciones: {line.receipt_allocations.map((value) => `#${value.goods_receipt_id} ${value.status}`).join(' · ')}</small> : null}</article>)}
        <div className="inventory-actions">
          {current.status === 'DRAFT' && hasPermission('inventory.purchase_order.manage') ? <><button className="secondary-button" disabled={action.isPending} onClick={editDraft}>Editar DRAFT</button><button className="primary-button" disabled={action.isPending} onClick={() => action.mutate('submit')}>Enviar a aprobación</button></> : null}
          {current.status === 'SUBMITTED' && hasPermission('inventory.purchase_order.approve') ? <button className="primary-button" disabled={action.isPending} onClick={() => action.mutate('approve')}>Aprobar</button> : null}
          {['APPROVED', 'PARTIALLY_RECEIVED'].includes(current.status) ? <NavLink className="primary-button" to="/inventory/receiving">Recibir contra esta orden</NavLink> : null}
          {['DRAFT', 'SUBMITTED', 'APPROVED', 'PARTIALLY_RECEIVED'].includes(current.status) && hasPermission('inventory.purchase_order.manage') ? <button className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('cancel')}>Cancelar orden</button> : null}
          {['RECEIVED', 'PARTIALLY_RECEIVED'].includes(current.status) && hasPermission('inventory.purchase_order.manage') ? <button className="secondary-button" disabled={action.isPending} onClick={() => action.mutate('close')}>Cerrar orden</button> : null}
        </div>
        {action.error ? <p className="inventory-feedback inventory-feedback--error" role="alert">{errorMessage(action.error)}</p> : null}
      </div> : <p className="inventory-empty">Selecciona una orden para revisar su detalle, o crea un DRAFT con varias líneas.</p>}
      <div className="inventory-selection-list">{orders.data?.items.map((value) => <button type="button" className="inventory-selection" aria-pressed={current?.id === value.id} key={value.id} onClick={() => { setCurrent(value); commandKeys.current.clear(); }}>#{value.id} · {value.status} · {value.lines.length} líneas</button>)}</div>
    </section>
  </div>;
}
