import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { CurrentServiceSession, OpenServiceSessionResponse, Resource } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';

type Feedback = { kind: 'success' | 'error' | 'conflict'; message: string };
type Handoff = { table: Resource; sessionId: number; accessCode: string; joinContextKey: string; version: number };

function readableError(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function elapsedLabel(openedAt: string): string {
  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - Date.parse(openedAt)) / 60_000));
  if (!Number.isFinite(elapsedMinutes) || elapsedMinutes < 1) return 'Abierta hace menos de un minuto';
  if (elapsedMinutes === 1) return 'Abierta hace 1 minuto';
  return `Abierta hace ${elapsedMinutes} minutos`;
}

function TableCard({
  table,
  session,
  checking,
  failed,
  canManage,
  busy,
  onOpen,
  onRegenerate,
  onClose,
}: {
  table: Resource;
  session: CurrentServiceSession | null | undefined;
  checking: boolean;
  failed: boolean;
  canManage: boolean;
  busy: boolean;
  onOpen: () => void;
  onRegenerate: () => void;
  onClose: () => void;
}) {
  const known = !checking && !failed;
  const occupied = known && session !== null;
  return (
    <article role="listitem" className={`table-card${occupied ? ' table-card--occupied' : ''}${failed ? ' table-card--attention' : ''}`}>
      <header className="table-card__header">
        <div><span className="table-code">{table.code}</span><h2>{table.name}</h2></div>
        <span className={`table-state table-state--${checking ? 'checking' : failed ? 'attention' : occupied ? 'occupied' : 'available'}`}>
          {checking ? 'Comprobando' : failed ? 'Requiere atención' : occupied ? 'En servicio' : 'Disponible'}
        </span>
      </header>
      {checking ? <p className="table-card__copy">Consultando la sesión actual…</p> : null}
      {failed ? <p className="table-card__copy">No fue posible verificar el estado. Actualiza antes de operar esta mesa.</p> : null}
      {occupied && session ? (
        <div className="session-summary">
          <dl>
            <div><dt>Comensales activos</dt><dd>{session.active_diner_count}</dd></div>
            <div><dt>Tamaño de grupo</dt><dd>{session.party_size}</dd></div>
            <div><dt>Sesión</dt><dd>#{session.id}</dd></div>
          </dl>
          <p>{elapsedLabel(session.opened_at)}</p>
        </div>
      ) : null}
      {known && !session ? <p className="table-card__copy">Sin sesión de servicio activa.</p> : null}
      <footer className="table-card__actions">
        {known && !session && canManage ? <button className="primary-button" type="button" onClick={onOpen} disabled={busy}>Abrir mesa</button> : null}
        {occupied && canManage ? <>
          <button className="secondary-button" type="button" onClick={onRegenerate} disabled={busy}>Nuevo código</button>
          <button className="danger-button" type="button" onClick={onClose} disabled={busy}>Cerrar mesa</button>
        </> : null}
        {known && !canManage ? <span className="read-only-label">Consulta solamente</span> : null}
      </footer>
    </article>
  );
}

export function HostPage() {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const canManage = hasPermission('restaurant_service.manage');
  const [opening, setOpening] = useState<Resource | null>(null);
  const [closing, setClosing] = useState<{ table: Resource; session: CurrentServiceSession } | null>(null);
  const [partySize, setPartySize] = useState('2');
  const [validation, setValidation] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [handoff, setHandoff] = useState<Handoff | null>(null);

  useEffect(() => {
    setOpening(null);
    setClosing(null);
    setFeedback(null);
    setHandoff(null);
  }, [location!.id]);

  const tablesQuery = useQuery({
    queryKey: ['staff', 'host', 'tables', location!.id],
    queryFn: () => staffApi.tables(location!.id),
    retry: false,
    refetchInterval: 12_000,
    refetchIntervalInBackground: false,
  });
  const tables = tablesQuery.data?.items ?? [];
  const sessionQueries = useQueries({
    queries: tables.map((table) => ({
      queryKey: ['staff', 'host', 'current-session', location!.id, table.id],
      queryFn: () => staffApi.currentServiceSession(table.id),
      retry: false,
      refetchInterval: 12_000,
      refetchIntervalInBackground: false,
    })),
  });

  const refresh = async () => {
    setFeedback(null);
    await Promise.all([tablesQuery.refetch(), ...sessionQueries.map((query) => query.refetch())]);
  };
  const revalidateTable = async (resourceId: number) => {
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'current-session', location!.id, resourceId] });
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'tables', location!.id] });
  };
  const handleMutationError = async (error: unknown, resourceId: number, fallback: string) => {
    const conflict = error instanceof ApiError && error.status === 409;
    setFeedback({ kind: conflict ? 'conflict' : 'error', message: readableError(error, fallback) });
    await revalidateTable(resourceId);
  };

  const openMutation = useMutation({
    mutationFn: ({ table, size }: { table: Resource; size: number }) => staffApi.openServiceSession(table.id, size),
    onSuccess: async (result: OpenServiceSessionResponse, variables) => {
      setOpening(null);
      setHandoff({ table: variables.table, sessionId: result.id, accessCode: result.access_code, joinContextKey: result.join_context_key, version: result.access_code_version });
      setFeedback({ kind: 'success', message: `${variables.table.name} quedó en servicio.` });
      await revalidateTable(variables.table.id);
    },
    onError: (error, variables) => {
      setOpening(null);
      return handleMutationError(error, variables.table.id, 'No fue posible abrir la mesa.');
    },
  });
  const regenerateMutation = useMutation({
    mutationFn: ({ table, session }: { table: Resource; session: CurrentServiceSession }) => staffApi.regenerateAccessCode(session.id),
    onSuccess: async (result, variables) => {
      setHandoff({ table: variables.table, sessionId: variables.session.id, accessCode: result.access_code, joinContextKey: variables.session.join_context_key, version: result.access_code_version });
      setFeedback({ kind: 'success', message: 'El backend emitió un nuevo código de acceso.' });
      await revalidateTable(variables.table.id);
    },
    onError: (error, variables) => handleMutationError(error, variables.table.id, 'No fue posible regenerar el código.'),
  });
  const closeMutation = useMutation({
    mutationFn: ({ session }: { table: Resource; session: CurrentServiceSession }) => staffApi.closeServiceSession(session.id),
    onSuccess: async (_, variables) => {
      setClosing(null);
      setHandoff(null);
      setFeedback({ kind: 'success', message: `${variables.table.name} fue cerrada y liberada por el backend.` });
      await revalidateTable(variables.table.id);
    },
    onError: async (error, variables) => {
      setClosing(null);
      await handleMutationError(error, variables.table.id, 'La mesa no puede cerrarse en este momento.');
    },
  });

  const busy = openMutation.isPending || regenerateMutation.isPending || closeMutation.isPending;
  const counts = useMemo(() => sessionQueries.reduce((value, query) => {
    if (query.isSuccess) query.data ? value.occupied++ : value.available++;
    else value.pending++;
    return value;
  }, { available: 0, occupied: 0, pending: 0 }), [sessionQueries]);

  function showOpen(table: Resource) {
    setPartySize('2');
    setValidation(null);
    setFeedback(null);
    setOpening(table);
  }
  function submitOpen(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!opening || openMutation.isPending) return;
    const size = Number(partySize);
    if (!Number.isInteger(size) || size < 1 || size > 999) {
      setValidation('Ingresa un tamaño de grupo entre 1 y 999.');
      return;
    }
    setValidation(null);
    openMutation.mutate({ table: opening, size });
  }

  return (
    <section className="host-page" aria-labelledby="host-heading">
      <header className="host-heading">
        <div><p className="eyebrow">Recepción · {location?.name}</p><h1 id="host-heading">Mesas en servicio</h1><p>Disponibilidad derivada de la sesión actual registrada por el backend.</p></div>
        <button className="secondary-button" type="button" onClick={() => void refresh()} disabled={tablesQuery.isFetching || busy}>↻ Actualizar</button>
      </header>

      {feedback ? <div className={`host-feedback host-feedback--${feedback.kind}`} role={feedback.kind === 'success' ? 'status' : 'alert'}><strong>{feedback.kind === 'conflict' ? 'El estado cambió' : feedback.kind === 'success' ? 'Operación confirmada' : 'No se completó la operación'}</strong><span>{feedback.message}</span>{feedback.kind === 'conflict' ? <small>La vista se revalidó con el estado más reciente.</small> : null}</div> : null}

      <div className="host-metrics" aria-label="Resumen de mesas">
        <div><strong>{counts.available}</strong><span>Disponibles</span></div>
        <div><strong>{counts.occupied}</strong><span>En servicio</span></div>
        <div><strong>{counts.pending}</strong><span>Por verificar</span></div>
      </div>

      {tablesQuery.isPending ? <div className="host-state" role="status"><span className="state-spinner" aria-hidden="true">◌</span><strong>Cargando mesas</strong><p>Aún no determinamos disponibilidad.</p></div> : null}
      {tablesQuery.isError ? <div className="host-state" role="alert"><strong>No pudimos cargar las mesas</strong><p>{readableError(tablesQuery.error, 'Revisa la conexión e inténtalo de nuevo.')}</p><button className="primary-button" type="button" onClick={() => void tablesQuery.refetch()}>Reintentar</button></div> : null}
      {tablesQuery.isSuccess && tables.length === 0 ? <div className="host-state"><strong>No hay mesas activas configuradas</strong><p>La ubicación no devolvió recursos TABLE con estado ACTIVE.</p></div> : null}
      {tables.length > 0 ? <div className="table-grid" role="list" aria-label="Mesas de la ubicación">{tables.map((table, index) => {
        const current = sessionQueries[index];
        const session = current?.data;
        return <TableCard key={table.id} table={table} session={session} checking={!current || current.isPending} failed={Boolean(current?.isError)} canManage={canManage} busy={busy} onOpen={() => showOpen(table)} onRegenerate={() => session && regenerateMutation.mutate({ table, session })} onClose={() => session && setClosing({ table, session })} />;
      })}</div> : null}

      {opening ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog" role="dialog" aria-modal="true" aria-labelledby="open-table-heading">
        <p className="eyebrow">Abrir mesa</p><h2 id="open-table-heading">{opening.name}</h2><p>La mesa seguirá disponible hasta que el backend confirme la sesión.</p>
        <form onSubmit={submitOpen}>
          <label className="field"><span>Tamaño del grupo</span><input name="partySize" type="number" inputMode="numeric" min="1" max="999" step="1" value={partySize} onChange={(event) => setPartySize(event.target.value)} autoFocus required /></label>
          {validation ? <p className="field-error" role="alert">{validation}</p> : null}
          <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setOpening(null)} disabled={openMutation.isPending}>Cancelar</button><button className="primary-button" type="submit" disabled={openMutation.isPending}>{openMutation.isPending ? 'Abriendo…' : 'Confirmar apertura'}</button></div>
        </form>
      </section></div> : null}

      {closing ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog" role="alertdialog" aria-modal="true" aria-labelledby="close-table-heading">
        <p className="eyebrow">Confirmar cierre</p><h2 id="close-table-heading">Cerrar {closing.table.name}</h2><p>El backend verificará saldos, continuidad y demás condiciones. Si procede, las sesiones activas de comensales terminarán y la mesa quedará liberada.</p>
        <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setClosing(null)} disabled={closeMutation.isPending}>Conservar abierta</button><button className="danger-button" type="button" onClick={() => closeMutation.mutate(closing)} disabled={closeMutation.isPending}>{closeMutation.isPending ? 'Verificando…' : 'Cerrar y liberar'}</button></div>
      </section></div> : null}

      {handoff ? <div className="modal-backdrop modal-backdrop--handoff" role="presentation"><section className="access-handoff" role="dialog" aria-modal="true" aria-labelledby="access-heading">
        <p className="eyebrow">Mesa lista</p><h2 id="access-heading">{handoff.table.name}</h2><p>Comparte este código con los comensales. Es el valor emitido por el backend.</p>
        <div className="access-code"><span>Código de acceso</span><strong>{handoff.accessCode}</strong></div>
        <dl><div><dt>Sesión</dt><dd>#{handoff.sessionId}</dd></div><div><dt>Versión</dt><dd>{handoff.version}</dd></div><div><dt>Contexto de ingreso</dt><dd>{handoff.joinContextKey}</dd></div></dl>
        <button className="primary-button" type="button" onClick={() => setHandoff(null)}>Handoff completado</button>
      </section></div> : null}
    </section>
  );
}
