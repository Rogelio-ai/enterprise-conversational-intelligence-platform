import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ApiError, staffApi } from '../api/client';
import type { ManagerOperationalOverview } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';

const money = (value: string, currency: string) => new Intl.NumberFormat('es-MX', {
  style: 'currency', currency,
}).format(Number(value));

const count = (values: Record<string, number>, state: string) => values[state] ?? 0;

const errorText = (error: unknown) => {
  if (error instanceof ApiError && (error.status === 403 || error.status === 404)) {
    return 'La vista ya no está autorizada para esta ubicación.';
  }
  return 'No pudimos reconstruir el estado operativo. Conservamos la última verdad confirmada, si existe.';
};

function Metric({ label, value, tone = 'normal' }: { label: string; value: number; tone?: 'normal' | 'attention' | 'critical' }) {
  return <div className={`manager-metric manager-metric--${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

function Counts({ values, labels }: { values: Record<string, number>; labels: Record<string, string> }) {
  return <dl className="manager-counts">{Object.entries(labels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{count(values, key)}</dd></div>)}</dl>;
}

function Empty({ children }: { children: string }) {
  return <p className="manager-empty">✓ {children}</p>;
}

function Overview({ value }: { value: ManagerOperationalOverview }) {
  return <>
    <section className="manager-status" aria-labelledby="manager-status-heading">
      <div><p className="eyebrow">Estado de ubicación</p><h2 id="manager-status-heading">Panorama inmediato</h2><p>Reconstruido por el backend a las {new Date(value.generated_at).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}.</p></div>
      <div className="manager-status-grid"><Metric label="Pagos inciertos" value={value.uncertain_payments.length} tone={value.uncertain_payments.length ? 'critical' : 'normal'} /><Metric label="Solicitudes pendientes" value={count(value.request_counts_by_status, 'PENDING')} tone={count(value.request_counts_by_status, 'PENDING') ? 'attention' : 'normal'} /><Metric label="Sesiones activas" value={value.active_service_session_count} /></div>
    </section>

    {value.uncertain_payments.length ? <section className="manager-critical" role="alert" aria-labelledby="uncertain-heading"><div><p className="eyebrow">Excepción financiera</p><h2 id="uncertain-heading">PAGO INCIERTO</h2><p>NO COBRAR DE NUEVO HASTA RECONCILIAR EN CAJA.</p></div><Link className="danger-button button-link" to="/cashier">Abrir Caja</Link>{value.uncertain_payments.map((item) => <p key={item.id}>Pago #{item.id} · Check #{item.check_id} · {money(item.amount, item.currency)} · {item.method_category}</p>)}</section> : null}

    <div className="manager-overview-grid">
      <section className="manager-card" aria-labelledby="service-summary"><header><div><p className="eyebrow">Servicio</p><h2 id="service-summary">Mesas y sesiones</h2></div><Link to="/host">Ver Host</Link></header><div className="manager-card-metrics"><Metric label="Mesas disponibles" value={value.available_table_count} /><Metric label="Sesiones activas" value={value.active_service_session_count} /><Metric label="Comensales activos" value={value.active_diner_count} /></div>{value.service_sessions.length ? <ul className="manager-list">{value.service_sessions.map((item) => <li key={item.id}><strong>{item.resource_name} · {item.resource_code}</strong><span>{item.active_diner_count}/{item.party_size} comensales · sesión #{item.id}</span></li>)}</ul> : <Empty>No hay sesiones de servicio activas.</Empty>}</section>

      <section className="manager-card" aria-labelledby="requests-summary"><header><div><p className="eyebrow">Atención</p><h2 id="requests-summary">Solicitudes operativas</h2></div><Link to="/waiter">Ver solicitudes</Link></header><Counts values={value.request_counts_by_status} labels={{ PENDING: 'Pendientes', ACKNOWLEDGED: 'En atención', COMPLETED: 'Completadas', CANCELLED: 'Canceladas' }} /><Counts values={value.request_counts_by_type} labels={{ HUMAN_ASSISTANCE: 'Asistencia', CASH_PAYMENT_ASSISTANCE: 'Pago en efectivo', INVOICE_ASSISTANCE: 'Factura', PAID_CHECK_PRINT: 'Cuenta impresa' }} />{count(value.request_counts_by_status, 'PENDING') === 0 && count(value.request_counts_by_status, 'ACKNOWLEDGED') === 0 ? <Empty>No hay solicitudes accionables.</Empty> : null}</section>

      <section className="manager-card" aria-labelledby="kitchen-summary"><header><div><p className="eyebrow">Producción</p><h2 id="kitchen-summary">Cocina y despachos</h2></div><Link to="/kitchen">Ver Cocina</Link></header><Counts values={value.preparation_item_counts} labels={{ NEW: 'Por iniciar', IN_PROGRESS: 'En preparación', COMPLETED: 'Completado' }} />{value.preparation_dispatch_exceptions.length ? <ul className="manager-list manager-list--exception">{value.preparation_dispatch_exceptions.map((item) => <li key={item.id}><strong>{item.state}</strong><span>Despacho #{item.id} · trabajo #{item.reference_id} · {item.destination_name}</span></li>)}</ul> : <Empty>No hay excepciones de despacho.</Empty>}</section>

      <section className="manager-card" aria-labelledby="financial-summary"><header><div><p className="eyebrow">Finanzas operativas</p><h2 id="financial-summary">Checks y Caja</h2></div><Link to="/cashier">Ver Caja</Link></header><div className="manager-card-metrics"><Metric label="Saldo pendiente" value={value.checks_with_outstanding_count} tone={value.checks_with_outstanding_count ? 'attention' : 'normal'} /><Metric label="Pagos inciertos" value={value.uncertain_payments.length} tone={value.uncertain_payments.length ? 'critical' : 'normal'} /><Metric label="Cajas abiertas" value={count(value.cash_session_counts, 'OPEN')} /></div>{value.check_exceptions.length ? <ul className="manager-list">{value.check_exceptions.map((item) => <li key={item.id}><strong>Check #{item.id} · {item.status}</strong><span>Pendiente {money(item.outstanding, item.currency)} · reservado {money(item.reserved_exposure, item.currency)} · incierto {money(item.uncertain_exposure, item.currency)}</span></li>)}</ul> : <Empty>No hay Checks con exposición financiera.</Empty>}{value.cash_session_exceptions.filter((item) => item.status === 'CLOSED').map((item) => <p className="manager-inline-exception" key={item.id}>Caja #{item.id}: diferencia confirmada {money(item.frozen_variance ?? '0', item.currency)}</p>)}</section>

      <section className="manager-card" aria-labelledby="billing-summary"><header><div><p className="eyebrow">Facturación</p><h2 id="billing-summary">CFDI</h2></div><Link to="/cashier">Abrir facturación</Link></header><Counts values={value.fiscal_issuance_counts} labels={{ PENDING: 'Pendientes', IN_PROGRESS: 'En proceso', FAILED: 'Fallidas', REJECTED: 'Rechazadas', UNCERTAIN: 'Inciertas', SUCCEEDED: 'Emitidas' }} />{value.fiscal_exceptions.length ? <ul className="manager-list manager-list--exception">{value.fiscal_exceptions.map((item) => <li key={item.id}><strong>{item.state}</strong><span>Emisión #{item.id} · documento #{item.billing_document_id} · {item.provider_key}</span></li>)}</ul> : <Empty>No hay emisiones fiscales pendientes o fallidas.</Empty>}</section>

      <section className="manager-card" aria-labelledby="print-summary"><header><div><p className="eyebrow">Entrega local</p><h2 id="print-summary">Cuenta pagada</h2></div><Link to="/cashier">Abrir impresión</Link></header><Counts values={value.paid_print_counts} labels={{ PENDING: 'Pendientes', IN_PROGRESS: 'En proceso', RETRYABLE_FAILURE: 'Fallo reintentable', UNCERTAIN: 'Inciertas', ACTION_REQUIRED: 'Requieren atención', DESTINATION_SUBMISSION_ACCEPTED: 'Entrega aceptada' }} />{value.paid_print_exceptions.length ? <ul className="manager-list manager-list--exception">{value.paid_print_exceptions.map((item) => <li key={item.id}><strong>{item.state}</strong><span>Despacho #{item.id} · Check #{item.reference_id} · {item.destination_name}</span></li>)}</ul> : <Empty>No hay impresiones pendientes o con excepción.</Empty>}</section>
    </div>
  </>;
}

export function ManagerPage() {
  const { location } = useStaffContext();
  const overview = useQuery({
    queryKey: ['staff', 'manager', 'overview', location?.id],
    queryFn: () => staffApi.managerOperationalOverview(location!.id),
    enabled: Boolean(location), retry: false, refetchInterval: 15_000,
  });

  return <section className="manager-page" aria-labelledby="manager-heading">
    <header className="manager-heading"><div><p className="eyebrow">Control operativo</p><h1 id="manager-heading">Gerencia</h1><p>{location?.name}. Excepciones primero; las acciones permanecen en su espacio operativo.</p></div><button className="secondary-button" type="button" disabled={overview.isFetching} onClick={() => overview.refetch()}>{overview.isFetching ? 'Actualizando…' : 'Actualizar panorama'}</button></header>
    {overview.isPending ? <div className="manager-loading" role="status">Reconstruyendo estado desde el backend…</div> : null}
    {overview.isError ? <div className="manager-failure" role="alert"><strong>No hay una lectura autoritativa actual.</strong><span>{errorText(overview.error)}</span><button className="secondary-button" type="button" onClick={() => overview.refetch()}>Reintentar</button></div> : null}
    {overview.data ? <Overview value={overview.data} /> : null}
  </section>;
}
