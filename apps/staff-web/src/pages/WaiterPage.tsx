import { FormEvent, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { StaffOperationalRequest, StaffOperationalRequestListResponse, WaiterOperationalRequestView } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';

const requestLabels = {
  HUMAN_ASSISTANCE: 'Ayuda al comensal',
  CASH_PAYMENT_ASSISTANCE: 'Pago en efectivo',
  INVOICE_ASSISTANCE: 'Solicitud de factura',
  PAID_CHECK_PRINT: 'Cuenta impresa',
  PREPARATION_READY: 'Preparación lista',
} as const;
const statusLabels = { PENDING: 'Pendiente', ACKNOWLEDGED: 'En atención', COMPLETED: 'Completada', CANCELLED: 'Cancelada' } as const;
type Action = 'entered' | 'hide' | 'show' | 'acknowledge' | 'complete' | 'pick-up' | 'deliver' | 'respond';
type Feedback = { kind: 'success' | 'error' | 'conflict'; title: string; message: string };
type ResponseIntent = { content: string; key: string };

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function actionLabel(action: Action): string {
  return ({ entered: 'Enterado', hide: 'Ocultar', show: 'Mostrar', acknowledge: 'Atendido', complete: 'Completar', 'pick-up': 'Recogido', deliver: 'Entregado', respond: 'Enviar' })[action];
}

function errorFeedback(error: unknown): Feedback {
  if (error instanceof ApiError && error.status === 403) return { kind: 'error', title: 'Acceso actualizado', message: 'Ya no tienes permiso para realizar esta acción.' };
  if (error instanceof ApiError && error.status === 409) return { kind: 'conflict', title: 'Estado actualizado', message: 'La solicitud cambió. Mostramos el estado canónico más reciente.' };
  if (error instanceof ApiError && error.status === 404) return { kind: 'conflict', title: 'Solicitud no disponible', message: 'La solicitud ya no está en tu ruta. Actualizamos el centro de mensajes.' };
  return { kind: 'error', title: 'No se pudo actualizar', message: error instanceof ApiError ? error.message : 'No fue posible conectar con el servicio. Intenta nuevamente.' };
}

function Evidence({ request }: { request: StaffOperationalRequest }) {
  return (
    <dl className="request-evidence">
      {request.current_waiter_entered_at ? <div><dt>Enterado</dt><dd>{formatTime(request.current_waiter_entered_at)}</dd></div> : null}
      {request.acknowledged_at ? <div><dt>Atendido</dt><dd>{request.acknowledged_by_display_name || (request.acknowledged_by_membership_id ? `Miembro #${request.acknowledged_by_membership_id}` : 'Actor registrado')} · {formatTime(request.acknowledged_at)}</dd></div> : null}
      {request.picked_up_at ? <div><dt>Recogido</dt><dd>Miembro #{request.picked_up_by_membership_id} · {formatTime(request.picked_up_at)}</dd></div> : null}
      {request.delivered_at ? <div><dt>Entregado</dt><dd>Miembro #{request.delivered_by_membership_id} · {formatTime(request.delivered_at)}</dd></div> : null}
      {request.resolved_at ? <div><dt>Completado</dt><dd>Miembro #{request.resolved_by_membership_id} · {formatTime(request.resolved_at)}</dd></div> : null}
    </dl>
  );
}

interface RequestCardProps {
  request: StaffOperationalRequest;
  view: WaiterOperationalRequestView;
  canManage: boolean;
  pending: Set<string>;
  composerOpen: boolean;
  responseText: string;
  responseError: string | null;
  onAction: (request: StaffOperationalRequest, action: Action, content?: string) => void;
  onOpenComposer: (id: number) => void;
  onCloseComposer: () => void;
  onResponseText: (value: string) => void;
}

function RequestCard(props: RequestCardProps) {
  const { request, view, canManage, pending, composerOpen, responseText, responseError } = props;
  const preparation = request.request_type === 'PREPARATION_READY';
  const terminal = request.status === 'COMPLETED' || request.status === 'CANCELLED';
  const respondEligible = !preparation && request.diner_session_id !== null && request.status !== 'CANCELLED';
  const cardBusy = [...pending].some((key) => key.startsWith(`${request.id}:`));
  const pendingAction = [...pending].find((key) => key.startsWith(`${request.id}:`))?.split(':')[1] as Action | undefined;
  const submitResponse = (event: FormEvent) => { event.preventDefault(); props.onAction(request, 'respond', responseText); };

  return (
    <article className={`request-card request-card--${request.status.toLowerCase()} ${preparation ? 'request-card--preparation' : ''}`} role="listitem">
      <header className="request-card__header">
        <div><p className="request-kind">{requestLabels[request.request_type]}</p><h2>{request.resource_name}</h2><span className="request-code">{request.resource_code}</span></div>
        <span className={`request-status request-status--${request.status.toLowerCase()}`}>{statusLabels[request.status]}</span>
      </header>
      <div className="request-context">
        <div><span>Recibida</span><strong>{formatTime(request.created_at)}</strong></div>
        <div><span>Sesión de servicio</span><strong>#{request.service_session_id}</strong></div>
        {request.diner_session_id !== null ? <div><span>Comensal</span><strong>{request.diner_display_name || `Sesión #${request.diner_session_id}`}</strong></div> : null}
        {preparation && request.restaurant_order_id ? <div><span>Orden</span><strong>#{request.restaurant_order_id}</strong></div> : null}
        {preparation && request.preparation_work_id ? <div><span>Preparación</span><strong>#{request.preparation_work_id}</strong></div> : null}
        {preparation && request.preparation_area_name ? <div><span>Área</span><strong>{request.preparation_area_name}{request.preparation_area_code ? ` · ${request.preparation_area_code}` : ''}</strong></div> : null}
      </div>
      <Evidence request={request} />
      {composerOpen ? (
        <form className="response-composer" onSubmit={submitResponse}>
          <label htmlFor={`response-${request.id}`}>Respuesta al comensal</label>
          <textarea id={`response-${request.id}`} value={responseText} onChange={(event) => props.onResponseText(event.target.value)} disabled={cardBusy} rows={3} maxLength={10_000} autoFocus />
          {responseError ? <p className="field-error" role="alert">{responseError}</p> : null}
          <div className="response-composer__actions">
            <button className="secondary-button" type="button" onClick={props.onCloseComposer} disabled={cardBusy}>Cancelar</button>
            <button className="primary-button" type="submit" disabled={cardBusy || !responseText.trim()}>{pendingAction === 'respond' ? 'Enviando…' : 'Enviar'}</button>
          </div>
        </form>
      ) : null}
      <footer className="request-card__actions" aria-label={`Acciones para ${request.resource_name}`}>
        {canManage && request.current_waiter_entered_at == null ? <button type="button" className="secondary-button" disabled={cardBusy} onClick={() => props.onAction(request, 'entered')}>{pendingAction === 'entered' ? 'Guardando…' : 'Enterado'}</button> : null}
        {canManage && request.status === 'PENDING' ? <button type="button" className="secondary-button" disabled={cardBusy} onClick={() => props.onAction(request, 'acknowledge')}>{pendingAction === 'acknowledge' ? 'Guardando…' : 'Atendido'}</button> : null}
        {canManage && preparation && !request.picked_up_at && !terminal ? <button type="button" className="primary-button" disabled={cardBusy} onClick={() => props.onAction(request, 'pick-up')}>{pendingAction === 'pick-up' ? 'Guardando…' : 'Recogido'}</button> : null}
        {canManage && preparation && request.picked_up_at && !request.delivered_at && !terminal ? <button type="button" className="primary-button" disabled={cardBusy} onClick={() => props.onAction(request, 'deliver')}>{pendingAction === 'deliver' ? 'Guardando…' : 'Entregado'}</button> : null}
        {canManage && !preparation && request.status === 'ACKNOWLEDGED' ? <button type="button" className="primary-button" disabled={cardBusy} onClick={() => props.onAction(request, 'complete')}>{pendingAction === 'complete' ? 'Guardando…' : 'Completar'}</button> : null}
        {canManage && respondEligible && !composerOpen ? <button type="button" className="secondary-button" disabled={cardBusy} onClick={() => props.onOpenComposer(request.id)}>Responder</button> : null}
        {canManage && !terminal && view === 'active' ? <button type="button" className="quiet-button" disabled={cardBusy} onClick={() => props.onAction(request, 'hide')}>{pendingAction === 'hide' ? 'Guardando…' : 'Ocultar'}</button> : null}
        {canManage && !terminal && view === 'hidden' ? <button type="button" className="quiet-button" disabled={cardBusy} onClick={() => props.onAction(request, 'show')}>{pendingAction === 'show' ? 'Guardando…' : 'Mostrar'}</button> : null}
        {!canManage ? <span className="read-only-label">Consulta solamente</span> : null}
      </footer>
    </article>
  );
}

export function WaiterPage() {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [view, setView] = useState<WaiterOperationalRequestView>('active');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [pending, setPending] = useState<Set<string>>(new Set());
  const pendingRef = useRef(new Set<string>());
  const responseIntents = useRef(new Map<number, ResponseIntent>());
  const [composerRequestId, setComposerRequestId] = useState<number | null>(null);
  const [responseText, setResponseText] = useState('');
  const [responseError, setResponseError] = useState<string | null>(null);
  const queryKey = ['waiter', 'operational-requests', location?.id, view];
  const requests = useQuery({ queryKey, queryFn: () => staffApi.waiterOperationalRequests(location!.id, { view }), enabled: Boolean(location), refetchInterval: 15_000, retry: false });
  const markPending = (key: string, value: boolean) => { if (value) pendingRef.current.add(key); else pendingRef.current.delete(key); setPending(new Set(pendingRef.current)); };
  const updateCanonicalRequest = (canonical: StaffOperationalRequest) => queryClient.setQueryData<StaffOperationalRequestListResponse>(queryKey, (current) => current ? ({ ...current, items: current.items.map((item) => item.id === canonical.id ? canonical : item) }) : current);

  const performAction = async (request: StaffOperationalRequest, action: Action, rawContent?: string) => {
    const pendingKey = `${request.id}:${action}`;
    if (pendingRef.current.has(pendingKey) || !location) return;
    let content = '';
    let intent: ResponseIntent | undefined;
    if (action === 'respond') {
      content = rawContent?.trim() ?? '';
      if (!content) { setResponseError('Escribe una respuesta antes de enviar.'); return; }
      const previous = responseIntents.current.get(request.id);
      intent = previous?.content === content ? previous : { content, key: crypto.randomUUID() };
      responseIntents.current.set(request.id, intent);
    }
    markPending(pendingKey, true);
    setFeedback(null);
    setResponseError(null);
    try {
      let canonical: StaffOperationalRequest | null = null;
      if (action === 'entered') canonical = await staffApi.enterWaiterOperationalRequest(request.id, location.id);
      if (action === 'hide') canonical = await staffApi.hideWaiterOperationalRequest(request.id, location.id);
      if (action === 'show') canonical = await staffApi.showWaiterOperationalRequest(request.id, location.id);
      if (action === 'acknowledge') canonical = await staffApi.acknowledgeWaiterOperationalRequest(request.id, location.id);
      if (action === 'complete') canonical = await staffApi.completeWaiterOperationalRequest(request.id, location.id);
      if (action === 'pick-up') canonical = await staffApi.pickUpWaiterOperationalRequest(request.id, location.id);
      if (action === 'deliver') canonical = await staffApi.deliverWaiterOperationalRequest(request.id, location.id);
      if (action === 'respond' && intent) await staffApi.respondToWaiterOperationalRequest(request.id, location.id, content, intent.key);
      if (canonical) updateCanonicalRequest(canonical);
      if (action === 'respond') { responseIntents.current.delete(request.id); setComposerRequestId(null); setResponseText(''); }
      setFeedback({ kind: 'success', title: 'Cambio confirmado', message: action === 'respond' ? 'Respuesta disponible para el comensal.' : `${actionLabel(action)} registrado con evidencia canónica.` });
      await requests.refetch();
    } catch (error) {
      setFeedback(errorFeedback(error));
      if (error instanceof ApiError && (error.status === 409 || error.status === 404)) await requests.refetch();
    } finally { markPending(pendingKey, false); }
  };

  const openComposer = (requestId: number) => { if (composerRequestId !== requestId) setResponseText(''); setComposerRequestId(requestId); setResponseError(null); };
  const closeComposer = () => { if (composerRequestId !== null) responseIntents.current.delete(composerRequestId); setComposerRequestId(null); setResponseText(''); setResponseError(null); };
  const values = requests.data?.items ?? [];
  const canManage = hasPermission('operational_request.manage');
  return (
    <section className="waiter-page" aria-labelledby="waiter-heading">
      <header className="waiter-heading">
        <div><p className="eyebrow">Centro de mensajes</p><h1 id="waiter-heading">Solicitudes</h1><p>Atención compartida de {location?.name}. Cada acción se confirma con el estado canónico.</p></div>
        <button className="secondary-button" type="button" onClick={() => void requests.refetch()} disabled={requests.isFetching}>{requests.isFetching && !requests.isPending ? 'Actualizando…' : 'Actualizar'}</button>
      </header>
      <div className="message-view-tabs" role="tablist" aria-label="Vista del centro de mensajes">
        {(['active', 'hidden'] as const).map((value) => <button key={value} type="button" role="tab" aria-selected={view === value} className={view === value ? 'active' : ''} onClick={() => { setView(value); setFeedback(null); }}>{value === 'active' ? 'ACTIVOS' : 'OCULTOS'}</button>)}
      </div>
      {feedback ? <div className={`inbox-feedback inbox-feedback--${feedback.kind}`} role={feedback.kind === 'success' ? 'status' : 'alert'}><strong>{feedback.title}</strong><span>{feedback.message}</span></div> : null}
      {requests.isPending ? <div className="inbox-state" role="status"><span className="state-spinner" aria-hidden="true">◌</span><h2>Cargando {view === 'active' ? 'activos' : 'ocultos'}</h2><p>Consultamos tu vista autorizada para esta ubicación.</p></div>
        : requests.isError ? <div className="inbox-state" role="alert"><span aria-hidden="true">!</span><h2>No pudimos cargar {view === 'active' ? 'los activos' : 'los ocultos'}</h2><p>{errorFeedback(requests.error).message}</p><button className="primary-button" type="button" onClick={() => void requests.refetch()}>Reintentar</button></div>
          : values.length === 0 ? <div className="inbox-state inbox-state--empty"><span aria-hidden="true">✓</span><h2>{view === 'active' ? 'No hay solicitudes activas.' : 'No hay solicitudes ocultas.'}</h2><p>{view === 'active' ? 'Tu centro de mensajes está al día.' : 'No has ocultado solicitudes no terminales.'}</p></div>
            : <div className="request-list" role="list" aria-label={`Solicitudes ${view === 'active' ? 'activas' : 'ocultas'}`}>{values.map((request) => <RequestCard key={request.id} request={request} view={view} canManage={canManage} pending={pending} composerOpen={composerRequestId === request.id} responseText={responseText} responseError={composerRequestId === request.id ? responseError : null} onAction={(item, action, content) => void performAction(item, action, content)} onOpenComposer={openComposer} onCloseComposer={closeComposer} onResponseText={(value) => { setResponseText(value); setResponseError(null); }} />)}</div>}
    </section>
  );
}
