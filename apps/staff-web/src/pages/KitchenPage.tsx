import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type {
  PreparationDispatch,
  PreparationState,
  PreparationWork,
  PreparationWorkItem,
} from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';

const stateLabels: Record<PreparationState, string> = {
  NEW: 'Pendiente',
  IN_PROGRESS: 'En preparación',
  COMPLETED: 'Listo',
};

const stateOptions: Array<{ value: PreparationState | ''; label: string }> = [
  { value: '', label: 'Activos' },
  { value: 'NEW', label: 'Pendientes' },
  { value: 'IN_PROGRESS', label: 'En preparación' },
  { value: 'COMPLETED', label: 'Listos' },
];

const dispatchLabels: Record<string, string> = {
  PENDING: 'Pendiente de impresión',
  IN_PROGRESS: 'Enviando',
  DESTINATION_SUBMISSION_ACCEPTED: 'Enviado',
  RETRYABLE_FAILURE: 'Reintento pendiente',
  UNCERTAIN: 'Resultado incierto',
  ACTION_REQUIRED: 'Requiere atención',
};

type Feedback = { kind: 'success' | 'conflict' | 'error'; message: string };
type ItemTransition = { item: PreparationWorkItem; toState: PreparationState };

function readableError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403 || error.status === 404) {
      return 'Esta ubicación ya no está autorizada para tu cuenta. Cambia de ubicación o solicita acceso.';
    }
    if (error.kind === 'network') return 'Sin conexión con Preparación. Conservamos la vista sin inventar cambios.';
    return error.message;
  }
  return 'La operación no pudo completarse.';
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('es-MX', {
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value));
}

function formatQuantity(value: string): string {
  const quantity = Number(value);
  return Number.isFinite(quantity)
    ? new Intl.NumberFormat('es-MX', { maximumFractionDigits: 3 }).format(quantity)
    : value;
}

function nextState(state: PreparationState): PreparationState | null {
  if (state === 'NEW') return 'IN_PROGRESS';
  if (state === 'IN_PROGRESS') return 'COMPLETED';
  return null;
}

function latestDispatches(dispatches: PreparationDispatch[]): PreparationDispatch[] {
  const latest = new Map<number, PreparationDispatch>();
  dispatches.forEach((dispatch) => {
    const current = latest.get(dispatch.destination_id);
    if (!current || dispatch.generation > current.generation) latest.set(dispatch.destination_id, dispatch);
  });
  return [...latest.values()].sort((left, right) => left.destination_name.localeCompare(right.destination_name));
}

function WorkCard({
  work,
  dispatches,
  canExecute,
  canReprint,
  busyItemId,
  busyDispatchId,
  onTransition,
  onReprint,
}: {
  work: PreparationWork;
  dispatches: PreparationDispatch[];
  canExecute: boolean;
  canReprint: boolean;
  busyItemId?: number;
  busyDispatchId?: number;
  onTransition: (item: PreparationWorkItem, toState: PreparationState) => void;
  onReprint: (dispatch: PreparationDispatch) => void;
}) {
  const table = work.order.current_resource_name || work.order.current_resource_code;
  return (
    <article className={`kitchen-card kitchen-card--${work.execution_state.toLowerCase()}`}>
      <header className="kitchen-card__header">
        <div>
          <p className="kitchen-area">{work.area_name} <span>{work.area_code}</span></p>
          <h2>{table || `Orden #${work.order.restaurant_order_id}`}</h2>
          <p>Orden #{work.order.restaurant_order_id} · entrada {formatTime(work.routed_at)}</p>
        </div>
        <span className={`kitchen-status kitchen-status--${work.execution_state.toLowerCase()}`}>
          {stateLabels[work.execution_state]}
        </span>
      </header>

      <ul className="kitchen-items" aria-label={`Productos de la orden ${work.order.restaurant_order_id}`}>
        {work.items.map((item) => {
          const target = nextState(item.execution_state);
          const busy = busyItemId === item.id;
          return (
            <li key={item.id}>
              <div className="kitchen-item__quantity" aria-label={`Cantidad ${formatQuantity(item.required_quantity)}`}>
                {formatQuantity(item.required_quantity)}×
              </div>
              <div className="kitchen-item__copy">
                <strong>{item.product_name}</strong>
                {item.parent_product_name ? (
                  <span>Configuración de {item.parent_product_name}</span>
                ) : (
                  <span>Producto directo · sin configuración adicional expuesta</span>
                )}
                <small>{stateLabels[item.execution_state]}</small>
              </div>
              <div className="kitchen-item__action">
                {target && canExecute ? (
                  <button
                    className="primary-button"
                    type="button"
                    disabled={busy}
                    onClick={() => onTransition(item, target)}
                  >
                    {busy ? 'Confirmando…' : target === 'IN_PROGRESS' ? 'Iniciar' : 'Marcar listo'}
                  </button>
                ) : target ? (
                  <span className="read-only-label">Solo consulta</span>
                ) : (
                  <span className="terminal-label">Terminado</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {dispatches.length > 0 ? (
        <footer className="kitchen-dispatches">
          <h3>Impresión y despacho</h3>
          {latestDispatches(dispatches).map((dispatch) => (
            <div key={dispatch.id}>
              <span>
                <strong>{dispatch.destination_name}</strong>
                <small>{dispatchLabels[dispatch.state] ?? dispatch.state} · generación {dispatch.generation}</small>
                {dispatch.last_error_message || dispatch.last_error_kind ? (
                  <em>{dispatch.last_error_message || dispatch.last_error_kind}</em>
                ) : null}
              </span>
              {canReprint ? (
                <button
                  className="secondary-button"
                  type="button"
                  disabled={busyDispatchId === dispatch.id}
                  onClick={() => onReprint(dispatch)}
                >{busyDispatchId === dispatch.id ? 'Solicitando…' : 'Reimprimir'}</button>
              ) : null}
            </div>
          ))}
          <p>La impresora se opera mediante el conector local; el estado de Preparación no se revierte por una falla de impresión.</p>
        </footer>
      ) : null}
    </article>
  );
}

export function KitchenPage() {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [stateFilter, setStateFilter] = useState<PreparationState | ''>('');
  const [areaFilter, setAreaFilter] = useState<number | ''>('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const transitioning = useRef(false);
  const reprinting = useRef(false);

  const worksKey = ['staff', 'kitchen', 'works', location?.id, stateFilter, areaFilter];
  const areas = useQuery({
    queryKey: ['staff', 'kitchen', 'areas', location?.id],
    queryFn: () => staffApi.preparationAreas(location!.id),
    enabled: Boolean(location),
    staleTime: 60_000,
    retry: false,
  });
  const works = useQuery({
    queryKey: worksKey,
    queryFn: () => staffApi.preparationWorks(location!.id, {
      state: stateFilter || undefined,
      areaId: areaFilter || undefined,
    }),
    enabled: Boolean(location),
    refetchInterval: 10_000,
    retry: false,
  });
  const dispatches = useQuery({
    queryKey: ['staff', 'kitchen', 'dispatches', location?.id],
    queryFn: () => staffApi.preparationDispatches(location!.id),
    enabled: Boolean(location),
    refetchInterval: 10_000,
    retry: false,
  });

  const transition = useMutation({
    mutationFn: ({ item, toState }: ItemTransition) => staffApi.transitionPreparationItem(
      item.id,
      item.execution_state,
      item.execution_version,
      toState,
      `kitchen-${item.id}-${item.execution_version}-${crypto.randomUUID()}`,
    ),
    onSuccess: async (_, variables) => {
      setFeedback({
        kind: 'success',
        message: variables.toState === 'IN_PROGRESS'
          ? `${variables.item.product_name} quedó en preparación.`
          : `${variables.item.product_name} quedó listo.`,
      });
      await queryClient.invalidateQueries({ queryKey: ['staff', 'kitchen', 'works', location?.id] });
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setFeedback({ kind: 'conflict', message: 'El trabajo cambió en otra estación. Ya consultamos el estado más reciente.' });
        await works.refetch();
      } else {
        setFeedback({ kind: 'error', message: readableError(error) });
      }
    },
    onSettled: () => { transitioning.current = false; },
  });

  const reprint = useMutation({
    mutationFn: (dispatch: PreparationDispatch) => staffApi.reprintPreparationDispatch(dispatch.id),
    onSuccess: async () => {
      setFeedback({ kind: 'success', message: 'Reimpresión solicitada al backend. La Preparación conserva su estado.' });
      await queryClient.invalidateQueries({ queryKey: ['staff', 'kitchen', 'dispatches', location?.id] });
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setFeedback({ kind: 'conflict', message: 'El despacho cambió. Actualizamos su estado antes de continuar.' });
        await dispatches.refetch();
      } else {
        setFeedback({ kind: 'error', message: readableError(error) });
      }
    },
    onSettled: () => { reprinting.current = false; },
  });

  const submitTransition = (item: PreparationWorkItem, toState: PreparationState) => {
    if (transitioning.current) return;
    transitioning.current = true;
    setFeedback(null);
    transition.mutate({ item, toState });
  };
  const submitReprint = (dispatch: PreparationDispatch) => {
    if (reprinting.current) return;
    reprinting.current = true;
    setFeedback(null);
    reprint.mutate(dispatch);
  };
  const refresh = async () => {
    await Promise.all([areas.refetch(), works.refetch(), dispatches.refetch()]);
  };

  const values = works.data ?? [];
  const loading = works.isPending || areas.isPending;
  const loadError = works.error || areas.error;
  const dispatchesByWork = new Map<number, PreparationDispatch[]>();
  (dispatches.data ?? []).forEach((dispatch) => {
    const current = dispatchesByWork.get(dispatch.preparation_work_id) ?? [];
    current.push(dispatch);
    dispatchesByWork.set(dispatch.preparation_work_id, current);
  });

  return (
    <section className="kitchen-page" aria-labelledby="kitchen-heading">
      <header className="kitchen-heading">
        <div>
          <p className="eyebrow">Operación de cocina</p>
          <h1 id="kitchen-heading">Preparación</h1>
          <p>Cola autorizada de {location?.name}. Actualización automática cada 10 segundos.</p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void refresh()} disabled={works.isFetching}>
          {works.isFetching && !works.isPending ? 'Actualizando…' : 'Actualizar'}
        </button>
      </header>

      <div className="kitchen-toolbar" aria-label="Filtros de preparación">
        <div className="status-tabs" role="group" aria-label="Filtrar por estado">
          {stateOptions.map((option) => (
            <button
              type="button"
              className={stateFilter === option.value ? 'active' : ''}
              aria-pressed={stateFilter === option.value}
              onClick={() => setStateFilter(option.value)}
              key={option.label}
            >{option.label}</button>
          ))}
        </div>
        <label className="type-filter">
          <span>Área / estación</span>
          <select value={areaFilter} onChange={(event) => setAreaFilter(event.target.value ? Number(event.target.value) : '')}>
            <option value="">Todas las áreas</option>
            {(areas.data?.items ?? []).filter((area) => area.status === 'ACTIVE').map((area) => (
              <option value={area.id} key={area.id}>{area.name} · {area.code}</option>
            ))}
          </select>
        </label>
      </div>

      {feedback ? (
        <div className={`kitchen-feedback kitchen-feedback--${feedback.kind}`} role={feedback.kind === 'success' ? 'status' : 'alert'}>
          <strong>{feedback.kind === 'success' ? 'Estado confirmado' : feedback.kind === 'conflict' ? 'Cola reconciliada' : 'No se pudo completar'}</strong>
          <span>{feedback.message}</span>
        </div>
      ) : null}

      {dispatches.isError && !loading && !loadError ? (
        <div className="kitchen-feedback kitchen-feedback--error" role="alert">
          <strong>Impresión no disponible</strong>
          <span>{readableError(dispatches.error)} La cola de Preparación permanece visible y sin cambios.</span>
        </div>
      ) : null}

      {loading ? (
        <div className="kitchen-state" role="status"><span className="state-spinner" aria-hidden="true">◌</span><h2>Cargando Preparación</h2><p>Consultamos la cola y las estaciones autorizadas para esta ubicación.</p></div>
      ) : loadError ? (
        <div className="kitchen-state" role="alert"><span aria-hidden="true">!</span><h2>No pudimos cargar Preparación</h2><p>{readableError(loadError)}</p><button className="primary-button" type="button" onClick={() => void refresh()}>Reintentar</button></div>
      ) : values.length === 0 ? (
        <div className="kitchen-state kitchen-state--empty"><span aria-hidden="true">✓</span><h2>No hay trabajo para estos filtros.</h2><p>La cola está al día; solo aparecerá trabajo de Preparación ya creado por el backend.</p></div>
      ) : (
        <div className="kitchen-board" role="list" aria-label="Cola de preparación">
          {values.map((work) => (
            <div role="listitem" key={work.id}>
              <WorkCard
                work={work}
                dispatches={dispatchesByWork.get(work.id) ?? []}
                canExecute={hasPermission('preparation.execute')}
                canReprint={hasPermission('preparation.dispatch')}
                busyItemId={transition.isPending ? transition.variables?.item.id : undefined}
                busyDispatchId={reprint.isPending ? reprint.variables?.id : undefined}
                onTransition={submitTransition}
                onReprint={submitReprint}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
