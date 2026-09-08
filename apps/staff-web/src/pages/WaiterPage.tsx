import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type {
  OperationalRequestStatus,
  OperationalRequestType,
  StaffOperationalRequest,
} from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';

const statusOptions: Array<{ value: OperationalRequestStatus | ''; label: string }> = [
  { value: 'PENDING', label: 'Pendientes' },
  { value: 'ACKNOWLEDGED', label: 'En atención' },
  { value: 'COMPLETED', label: 'Completadas' },
  { value: '', label: 'Todas' },
];

const typeOptions: Array<{ value: OperationalRequestType | ''; label: string }> = [
  { value: '', label: 'Todos los tipos' },
  { value: 'HUMAN_ASSISTANCE', label: 'Ayuda' },
  { value: 'CASH_PAYMENT_ASSISTANCE', label: 'Efectivo' },
  { value: 'INVOICE_ASSISTANCE', label: 'Factura' },
  { value: 'PAID_CHECK_PRINT', label: 'Impresión' },
];

const requestLabels: Record<OperationalRequestType, string> = {
  HUMAN_ASSISTANCE: 'Ayuda al comensal',
  CASH_PAYMENT_ASSISTANCE: 'Pago en efectivo',
  INVOICE_ASSISTANCE: 'Solicitud de factura',
  PAID_CHECK_PRINT: 'Cuenta impresa',
};

const requestHints: Record<OperationalRequestType, string> = {
  HUMAN_ASSISTANCE: 'Acércate a la mesa y atiende personalmente la solicitud.',
  CASH_PAYMENT_ASSISTANCE: 'Solicitud de manejo de efectivo. Escala al flujo de caja correspondiente.',
  INVOICE_ASSISTANCE: 'Acompaña la solicitud; la emisión fiscal ocurre en el flujo de facturación.',
  PAID_CHECK_PRINT: 'Coordina la impresión autorizada. Este inbox no envía trabajos a impresoras.',
};

const statusLabels: Record<OperationalRequestStatus, string> = {
  PENDING: 'Pendiente',
  ACKNOWLEDGED: 'En atención',
  COMPLETED: 'Completada',
  CANCELLED: 'Cancelada',
};

type Feedback = { kind: 'success' | 'error' | 'conflict'; message: string };
type Transition = { request: StaffOperationalRequest; action: 'acknowledge' | 'complete' };

function requestAge(value: string): string {
  const minutes = Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 60_000));
  if (!Number.isFinite(minutes) || minutes < 1) return 'Hace menos de un minuto';
  if (minutes === 1) return 'Hace 1 minuto';
  if (minutes < 60) return `Hace ${minutes} minutos`;
  const hours = Math.floor(minutes / 60);
  return hours === 1 ? 'Hace 1 hora' : `Hace ${hours} horas`;
}

function readableError(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : 'No fue posible actualizar la solicitud. Intenta nuevamente.';
}

function RequestCard({
  request,
  canManage,
  busy,
  onTransition,
}: {
  request: StaffOperationalRequest;
  canManage: boolean;
  busy: boolean;
  onTransition: (action: Transition['action']) => void;
}) {
  const terminal = request.status === 'COMPLETED' || request.status === 'CANCELLED';
  return (
    <article className={`request-card request-card--${request.status.toLowerCase()}`} role="listitem">
      <header className="request-card__header">
        <div>
          <p className="request-kind">{requestLabels[request.request_type]}</p>
          <h2>{request.resource_name}</h2>
          <span className="request-code">{request.resource_code}</span>
        </div>
        <span className={`request-status request-status--${request.status.toLowerCase()}`}>
          {statusLabels[request.status]}
        </span>
      </header>
      <div className="request-context">
        <div><span>Comensal</span><strong>{request.diner_display_name}</strong></div>
        <div><span>Recibida</span><strong>{requestAge(request.created_at)}</strong></div>
        <div><span>Sesión</span><strong>#{request.service_session_id}</strong></div>
      </div>
      <p className="request-hint">{requestHints[request.request_type]}</p>
      <footer className="request-card__actions">
        {request.status === 'PENDING' && canManage ? (
          <button className="primary-button" type="button" disabled={busy} onClick={() => onTransition('acknowledge')}>
            {busy ? 'Actualizando…' : 'Atender'}
          </button>
        ) : null}
        {request.status === 'ACKNOWLEDGED' && canManage ? (
          <button className="primary-button" type="button" disabled={busy} onClick={() => onTransition('complete')}>
            {busy ? 'Actualizando…' : 'Completar'}
          </button>
        ) : null}
        {!terminal && !canManage ? <span className="read-only-label">Consulta solamente</span> : null}
        {terminal ? <span className="terminal-label">Sin acciones pendientes</span> : null}
      </footer>
    </article>
  );
}

export function WaiterPage() {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<OperationalRequestStatus | ''>('PENDING');
  const [typeFilter, setTypeFilter] = useState<OperationalRequestType | ''>('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const submitting = useRef(false);
  const queryKey = ['staff', 'operational-requests', location?.id, statusFilter, typeFilter];
  const requests = useQuery({
    queryKey,
    queryFn: () => staffApi.operationalRequests(location!.id, {
      status: statusFilter || undefined,
      requestType: typeFilter || undefined,
    }),
    enabled: Boolean(location),
    refetchInterval: 15_000,
    retry: false,
  });
  const transition = useMutation({
    mutationFn: ({ request, action }: Transition) => action === 'acknowledge'
      ? staffApi.acknowledgeOperationalRequest(request.id, location!.id)
      : staffApi.completeOperationalRequest(request.id, location!.id),
    onSuccess: async (_, variables) => {
      setFeedback({
        kind: 'success',
        message: variables.action === 'acknowledge'
          ? 'Solicitud marcada en atención.'
          : 'Atención operativa completada.',
      });
      await queryClient.invalidateQueries({ queryKey: ['staff', 'operational-requests'] });
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setFeedback({
          kind: 'conflict',
          message: 'La solicitud cambió mientras la atendías. Mostramos el estado más reciente.',
        });
        await requests.refetch();
      } else {
        setFeedback({ kind: 'error', message: readableError(error) });
      }
    },
    onSettled: () => { submitting.current = false; },
  });

  const submit = (request: StaffOperationalRequest, action: Transition['action']) => {
    if (submitting.current) return;
    submitting.current = true;
    setFeedback(null);
    transition.mutate({ request, action });
  };

  const values = requests.data?.items ?? [];
  const canManage = hasPermission('operational_request.manage');
  return (
    <section className="waiter-page" aria-labelledby="waiter-heading">
      <header className="waiter-heading">
        <div>
          <p className="eyebrow">Atención en sala</p>
          <h1 id="waiter-heading">Solicitudes</h1>
          <p>Trabajo compartido de {location?.name}. El estado siempre se confirma con el backend.</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void requests.refetch()} disabled={requests.isFetching}>
          {requests.isFetching && !requests.isPending ? 'Actualizando…' : 'Actualizar'}
        </button>
      </header>

      <div className="inbox-toolbar" aria-label="Filtros de solicitudes">
        <div className="status-tabs" role="group" aria-label="Filtrar por estado">
          {statusOptions.map((option) => (
            <button
              type="button"
              className={statusFilter === option.value ? 'active' : ''}
              aria-pressed={statusFilter === option.value}
              onClick={() => setStatusFilter(option.value)}
              key={option.label}
            >{option.label}</button>
          ))}
        </div>
        <label className="type-filter">
          <span>Tipo de solicitud</span>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as OperationalRequestType | '')}>
            {typeOptions.map((option) => <option value={option.value} key={option.label}>{option.label}</option>)}
          </select>
        </label>
      </div>

      {feedback ? (
        <div className={`inbox-feedback inbox-feedback--${feedback.kind}`} role={feedback.kind === 'success' ? 'status' : 'alert'}>
          <strong>{feedback.kind === 'success' ? 'Estado confirmado' : feedback.kind === 'conflict' ? 'Estado actualizado' : 'No se pudo actualizar'}</strong>
          <span>{feedback.message}</span>
        </div>
      ) : null}

      {requests.isPending ? (
        <div className="inbox-state" role="status"><span className="state-spinner" aria-hidden="true">◌</span><h2>Cargando solicitudes</h2><p>Consultamos el trabajo autorizado para esta ubicación.</p></div>
      ) : requests.isError ? (
        <div className="inbox-state" role="alert"><span aria-hidden="true">!</span><h2>No pudimos cargar el inbox</h2><p>{readableError(requests.error)}</p><button className="primary-button" type="button" onClick={() => void requests.refetch()}>Reintentar</button></div>
      ) : values.length === 0 ? (
        <div className="inbox-state inbox-state--empty"><span aria-hidden="true">✓</span><h2>No hay solicitudes pendientes.</h2><p>El inbox está al día para los filtros seleccionados.</p></div>
      ) : (
        <div className="request-list" role="list" aria-label="Solicitudes operativas">
          {values.map((request) => (
            <RequestCard
              request={request}
              canManage={canManage}
              busy={transition.isPending && transition.variables?.request.id === request.id}
              onTransition={(action) => submit(request, action)}
              key={request.id}
            />
          ))}
        </div>
      )}
    </section>
  );
}
