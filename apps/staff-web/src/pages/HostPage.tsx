import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type {
  CurrentServiceSession,
  EligibleWaiter,
  OpenServiceSessionResponse,
  Resource,
  ServiceResponsibility,
  TableWaiterAssignment,
  TableWaiterAssignmentSet,
} from '../api/contracts';
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
  assignment,
  assignmentChecking,
  assignmentFailed,
  responsibility,
  responsibilityChecking,
  responsibilityFailed,
  canManageAssignments,
  onManageAssignments,
  onManageResponsibility,
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
  assignment: TableWaiterAssignmentSet | undefined;
  assignmentChecking: boolean;
  assignmentFailed: boolean;
  responsibility: ServiceResponsibility | undefined;
  responsibilityChecking: boolean;
  responsibilityFailed: boolean;
  canManageAssignments: boolean;
  onManageAssignments: () => void;
  onManageResponsibility: () => void;
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
          <section className="service-responsibility" aria-label={`Responsables del servicio de ${table.name}`}>
            <strong>Responsables del servicio</strong>
            {responsibilityChecking ? <p>Consultando responsabilidad del servicio…</p> : null}
            {responsibilityFailed ? <p role="alert">No fue posible consultar la responsabilidad del servicio.</p> : null}
            {responsibility && !responsibility.initialized ? <p className="service-responsibility__legacy">Responsabilidad del servicio no inicializada</p> : null}
            {responsibility?.initialized ? <ul>{responsibility.responsible_waiters.map((waiter) => <li key={waiter.membership_id}>{waiter.display_name}</li>)}</ul> : null}
            {responsibility?.initialized && responsibility.status === 'OPEN' && canManage ? <button className="link-button" type="button" onClick={onManageResponsibility} disabled={busy}>Cambiar responsables del servicio</button> : null}
          </section>
        </div>
      ) : null}
      {known && !session ? <p className="table-card__copy">Sin sesión de servicio activa.</p> : null}
      <section className="waiter-summary" aria-label={`Meseros asignados a ${table.name}`}>
        <div className="waiter-summary__heading"><strong>Meseros asignados</strong>{assignment ? <span>v{assignment.version}</span> : null}</div>
        {assignmentChecking ? <p>Consultando responsables…</p> : null}
        {assignmentFailed ? <p role="alert">No fue posible consultar la asignación.</p> : null}
        {assignment && assignment.assignments.length === 0 ? <p>Sin configuración operativa.</p> : null}
        {assignment && assignment.assignments.length > 0 ? <ul>{assignment.assignments.map((waiter) => <li key={waiter.membership_id}><span>{waiter.display_name}</span>{waiter.is_responsible ? <strong>Responsable</strong> : null}</li>)}</ul> : null}
        {assignment && canManageAssignments ? <button className="link-button" type="button" onClick={onManageAssignments} disabled={busy}>Gestionar meseros</button> : null}
      </section>
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
  const canManageAssignments = hasPermission('resource.manage');
  const [opening, setOpening] = useState<Resource | null>(null);
  const [closing, setClosing] = useState<{ table: Resource; session: CurrentServiceSession } | null>(null);
  const [partySize, setPartySize] = useState('2');
  const [validation, setValidation] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [staffingTable, setStaffingTable] = useState<Resource | null>(null);
  const [selectedWaiterId, setSelectedWaiterId] = useState('');
  const [responsibleIds, setResponsibleIds] = useState<number[]>([]);
  const [removingWaiter, setRemovingWaiter] = useState<TableWaiterAssignment | null>(null);
  const [replacementIds, setReplacementIds] = useState<number[]>([]);
  const [responsibilityTable, setResponsibilityTable] = useState<Resource | null>(null);
  const [responsibilitySession, setResponsibilitySession] = useState<CurrentServiceSession | null>(null);
  const [serviceResponsibleIds, setServiceResponsibleIds] = useState<number[]>([]);

  useEffect(() => {
    setOpening(null);
    setClosing(null);
    setFeedback(null);
    setHandoff(null);
    setStaffingTable(null);
    setRemovingWaiter(null);
    setResponsibilityTable(null);
    setResponsibilitySession(null);
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
  const assignmentQueries = useQueries({
    queries: tables.map((table) => ({
      queryKey: ['staff', 'host', 'waiter-assignments', location!.id, table.id],
      queryFn: () => staffApi.tableWaiterAssignments(location!.id, table.id),
      retry: false,
      refetchInterval: 12_000,
      refetchIntervalInBackground: false,
    })),
  });
  const responsibilityQueries = useQueries({
    queries: tables.map((table, index) => {
      const session = sessionQueries[index]?.data;
      return {
        queryKey: ['staff', 'host', 'service-responsibility', location!.id, session?.id ?? 'none'],
        queryFn: () => staffApi.serviceResponsibility(location!.id, session!.id),
        enabled: Boolean(session),
        retry: false,
        refetchInterval: session ? 12_000 : false,
        refetchIntervalInBackground: false,
      };
    }),
  });
  const eligibleWaitersQuery = useQuery({
    queryKey: ['staff', 'host', 'eligible-waiters', location!.id],
    queryFn: () => staffApi.eligibleTableWaiters(location!.id),
    retry: false,
  });

  const refresh = async () => {
    setFeedback(null);
    await Promise.all([tablesQuery.refetch(), eligibleWaitersQuery.refetch(), ...sessionQueries.map((query) => query.refetch()), ...assignmentQueries.map((query) => query.refetch()), ...responsibilityQueries.filter((_, index) => Boolean(sessionQueries[index]?.data)).map((query) => query.refetch())]);
  };
  const revalidateAssignments = async (resourceId: number) => {
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'waiter-assignments', location!.id, resourceId] });
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'eligible-waiters', location!.id] });
  };
  const revalidateTable = async (resourceId: number) => {
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'current-session', location!.id, resourceId] });
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'tables', location!.id] });
  };
  const revalidateResponsibility = async (sessionId: number) => {
    await queryClient.invalidateQueries({ queryKey: ['staff', 'host', 'service-responsibility', location!.id, sessionId] });
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

  type StaffingAction =
    | { kind: 'assign'; tableId: number; membershipId: number; version: number }
    | { kind: 'responsible'; tableId: number; membershipIds: number[]; version: number }
    | { kind: 'unassign'; tableId: number; membershipId: number; replacementIds: number[]; version: number };
  const staffingMutation = useMutation({
    mutationFn: (action: StaffingAction) => {
      if (action.kind === 'assign') return staffApi.assignTableWaiter(location!.id, action.tableId, action.membershipId, action.version);
      if (action.kind === 'responsible') return staffApi.updateResponsibleWaiters(location!.id, action.tableId, action.membershipIds, action.version);
      return staffApi.unassignTableWaiter(location!.id, action.tableId, action.membershipId, action.replacementIds, action.version);
    },
    onSuccess: async (result, action) => {
      setResponsibleIds(result.assignments.filter((value) => value.is_responsible).map((value) => value.membership_id));
      setSelectedWaiterId('');
      setRemovingWaiter(null);
      setReplacementIds([]);
      setFeedback({ kind: 'success', message: 'La asignación de la mesa quedó actualizada.' });
      await revalidateAssignments(action.tableId);
    },
    onError: async (error, action) => {
      setFeedback({ kind: error instanceof ApiError && error.status === 409 ? 'conflict' : 'error', message: readableError(error, 'No fue posible actualizar los meseros.') });
      await revalidateAssignments(action.tableId);
    },
  });

  const responsibilityMutation = useMutation({
    mutationFn: ({ sessionId, membershipIds, version, key }: {
      tableId: number; sessionId: number; membershipIds: number[]; version: number; key: string;
    }) => staffApi.replaceServiceResponsibility(
      location!.id, sessionId, membershipIds, version, key,
    ),
    onSuccess: async (_, variables) => {
      setFeedback({ kind: 'success', message: 'La responsabilidad del servicio quedó actualizada.' });
      await revalidateResponsibility(variables.sessionId);
      setResponsibilityTable(null);
      setResponsibilitySession(null);
    },
    onError: async (error, variables) => {
      setFeedback({
        kind: error instanceof ApiError && error.status === 409 ? 'conflict' : 'error',
        message: readableError(error, 'No fue posible actualizar la responsabilidad del servicio.'),
      });
      await revalidateResponsibility(variables.sessionId);
    },
  });

  const busy = openMutation.isPending || regenerateMutation.isPending || closeMutation.isPending || staffingMutation.isPending || responsibilityMutation.isPending;
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
  const staffingIndex = staffingTable ? tables.findIndex((value) => value.id === staffingTable.id) : -1;
  const staffing = staffingIndex >= 0 ? assignmentQueries[staffingIndex]?.data : undefined;
  const eligibleWaiters = eligibleWaitersQuery.data?.items ?? [];
  const assignableWaiters = eligibleWaiters.filter((waiter) => !staffing?.assignments.some((value) => value.membership_id === waiter.membership_id));
  const remainingAfterRemoval = staffing && removingWaiter ? staffing.assignments.filter((value) => value.membership_id !== removingWaiter.membership_id) : [];
  const removalNeedsReplacement = Boolean(removingWaiter?.is_responsible && staffing?.assignments.filter((value) => value.is_responsible).length === 1 && remainingAfterRemoval.length > 1);
  const responsibilityIndex = responsibilityTable ? tables.findIndex((value) => value.id === responsibilityTable.id) : -1;
  const serviceResponsibility = responsibilityIndex >= 0 ? responsibilityQueries[responsibilityIndex]?.data : undefined;
  const responsibilityCandidates = responsibilityIndex >= 0 ? assignmentQueries[responsibilityIndex]?.data?.assignments ?? [] : [];

  useEffect(() => {
    if (responsibilitySession && serviceResponsibility?.initialized) {
      setServiceResponsibleIds(serviceResponsibility.responsible_membership_ids);
    }
  }, [responsibilitySession, serviceResponsibility]);

  function showStaffing(table: Resource, value: TableWaiterAssignmentSet) {
    setStaffingTable(table);
    setSelectedWaiterId('');
    setResponsibleIds(value.assignments.filter((waiter) => waiter.is_responsible).map((waiter) => waiter.membership_id));
    setRemovingWaiter(null);
    setReplacementIds([]);
  }

  function showResponsibility(
    table: Resource, session: CurrentServiceSession, value: ServiceResponsibility,
  ) {
    setResponsibilityTable(table);
    setResponsibilitySession(session);
    setServiceResponsibleIds(value.responsible_membership_ids);
  }

  function toggleId(values: number[], id: number): number[] {
    return values.includes(id) ? values.filter((value) => value !== id) : [...values, id];
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
        const assignment = assignmentQueries[index];
        const responsibility = responsibilityQueries[index];
        return <TableCard key={table.id} table={table} session={session} checking={!current || current.isPending} failed={Boolean(current?.isError)} canManage={canManage} busy={busy} assignment={assignment?.data} assignmentChecking={!assignment || assignment.isPending} assignmentFailed={Boolean(assignment?.isError)} responsibility={responsibility?.data} responsibilityChecking={Boolean(session && (!responsibility || responsibility.isPending))} responsibilityFailed={Boolean(responsibility?.isError)} canManageAssignments={canManageAssignments} onManageAssignments={() => assignment?.data && showStaffing(table, assignment.data)} onManageResponsibility={() => session && responsibility?.data && showResponsibility(table, session, responsibility.data)} onOpen={() => showOpen(table)} onRegenerate={() => session && regenerateMutation.mutate({ table, session })} onClose={() => session && setClosing({ table, session })} />;
      })}</div> : null}

      {responsibilityTable && responsibilitySession && serviceResponsibility?.initialized ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog service-responsibility-dialog" role="dialog" aria-modal="true" aria-labelledby="service-responsibility-heading">
        <p className="eyebrow">Responsabilidad del servicio</p><h2 id="service-responsibility-heading">{responsibilityTable.name} · Servicio #{responsibilitySession.id}</h2><p>Esta selección pertenece al servicio abierto. No modifica la asignación ni los responsables de la mesa.</p>
        <fieldset className="service-responsibility-options"><legend>Responsables del servicio</legend>{responsibilityCandidates.map((waiter) => <label key={waiter.membership_id}><input type="checkbox" checked={serviceResponsibleIds.includes(waiter.membership_id)} onChange={() => setServiceResponsibleIds((values) => toggleId(values, waiter.membership_id))} disabled={responsibilityMutation.isPending} /><span><strong>{waiter.display_name}</strong><small>{waiter.email}</small></span></label>)}</fieldset>
        {serviceResponsibleIds.length === 0 ? <p className="field-error" role="alert">Selecciona al menos un responsable del servicio.</p> : null}
        <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => { setResponsibilityTable(null); setResponsibilitySession(null); }} disabled={responsibilityMutation.isPending}>Cancelar</button><button className="primary-button" type="button" disabled={serviceResponsibleIds.length === 0 || responsibilityMutation.isPending || serviceResponsibility.version === null} onClick={() => responsibilityMutation.mutate({ tableId: responsibilityTable.id, sessionId: responsibilitySession.id, membershipIds: serviceResponsibleIds, version: serviceResponsibility.version!, key: `service-responsibility-${responsibilitySession.id}-${crypto.randomUUID()}` })}>{responsibilityMutation.isPending ? 'Guardando…' : 'Guardar responsables del servicio'}</button></div>
      </section></div> : null}

      {staffingTable && staffing ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog staffing-dialog" role="dialog" aria-modal="true" aria-labelledby="staffing-heading">
        <p className="eyebrow">Asignación de mesa</p><h2 id="staffing-heading">{staffingTable.name}</h2><p>La responsabilidad pertenece a la asignación de esta mesa, no a una sesión de servicio.</p>
        <div className="staffing-list">
          {staffing.assignments.length === 0 ? <p>Asigna el primer mesero; quedará responsable automáticamente.</p> : staffing.assignments.map((waiter) => <div key={waiter.membership_id}>
            <label><input type="checkbox" checked={responsibleIds.includes(waiter.membership_id)} onChange={() => setResponsibleIds((values) => toggleId(values, waiter.membership_id))} disabled={staffingMutation.isPending} /><span><strong>{waiter.display_name}</strong><small>{waiter.email}</small></span></label>
            <button className="danger-button" type="button" onClick={() => { setRemovingWaiter(waiter); setReplacementIds([]); }} disabled={staffingMutation.isPending}>Desasignar</button>
          </div>)}
        </div>
        {staffing.assignments.length > 0 ? <button className="secondary-button" type="button" disabled={responsibleIds.length === 0 || staffingMutation.isPending} onClick={() => staffingMutation.mutate({ kind: 'responsible', tableId: staffingTable.id, membershipIds: responsibleIds, version: staffing.version })}>Guardar responsables</button> : null}
        <div className="staffing-add"><label className="field"><span>Mesero elegible</span><select value={selectedWaiterId} onChange={(event) => setSelectedWaiterId(event.target.value)}><option value="">Selecciona un mesero</option>{assignableWaiters.map((waiter: EligibleWaiter) => <option key={waiter.membership_id} value={waiter.membership_id}>{waiter.display_name}</option>)}</select></label><button className="primary-button" type="button" disabled={!selectedWaiterId || staffingMutation.isPending} onClick={() => staffingMutation.mutate({ kind: 'assign', tableId: staffingTable.id, membershipId: Number(selectedWaiterId), version: staffing.version })}>Asignar mesero</button></div>
        <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setStaffingTable(null)} disabled={staffingMutation.isPending}>Cerrar</button></div>
      </section></div> : null}

      {staffingTable && staffing && removingWaiter ? <div className="modal-backdrop modal-backdrop--nested" role="presentation"><section className="operation-dialog" role="alertdialog" aria-modal="true" aria-labelledby="unassign-heading">
        <p className="eyebrow">Confirmar desasignación</p><h2 id="unassign-heading">Desasignar a {removingWaiter.display_name}</h2>
        {remainingAfterRemoval.length === 0 ? <p role="alert">El último mesero asignado no puede retirarse.</p> : null}
        {removingWaiter.is_responsible && remainingAfterRemoval.length === 1 ? <p>{remainingAfterRemoval[0].display_name} quedará responsable automáticamente.</p> : null}
        {removalNeedsReplacement ? <fieldset className="replacement-list"><legend>Selecciona al menos un responsable sustituto</legend>{remainingAfterRemoval.map((waiter) => <label key={waiter.membership_id}><input type="checkbox" checked={replacementIds.includes(waiter.membership_id)} onChange={() => setReplacementIds((values) => toggleId(values, waiter.membership_id))} />{waiter.display_name}</label>)}</fieldset> : null}
        <div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setRemovingWaiter(null)} disabled={staffingMutation.isPending}>Cancelar</button><button className="danger-button" type="button" disabled={remainingAfterRemoval.length === 0 || (removalNeedsReplacement && replacementIds.length === 0) || staffingMutation.isPending} onClick={() => staffingMutation.mutate({ kind: 'unassign', tableId: staffingTable.id, membershipId: removingWaiter.membership_id, replacementIds, version: staffing.version })}>Confirmar desasignación</button></div>
      </section></div> : null}

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
