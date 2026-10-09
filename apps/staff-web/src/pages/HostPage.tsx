import { useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { CurrentServiceSession, Resource, TableWaiterAssignmentSet } from '../api/contracts';
import { ReceptionPreparationRequests } from '../components/ReceptionPreparationRequests';
import { TableManagementPanel } from '../components/TableManagementPanel';
import { useStaffContext } from '../context/StaffContext';

function readableError(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function elapsedLabel(openedAt: string): string {
  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - Date.parse(openedAt)) / 60_000));
  if (!Number.isFinite(elapsedMinutes) || elapsedMinutes < 1) return 'Abierta hace menos de un minuto';
  if (elapsedMinutes === 1) return 'Abierta hace 1 minuto';
  return `Abierta hace ${elapsedMinutes} minutos`;
}

function ReceptionTableCard({ table, session, checking, failed, assignment }: {
  table: Resource;
  session: CurrentServiceSession | null | undefined;
  checking: boolean;
  failed: boolean;
  assignment: TableWaiterAssignmentSet | undefined;
}) {
  const occupied = !checking && !failed && session !== null;
  return <article role="listitem" className={`table-card${occupied ? ' table-card--occupied' : ''}${failed ? ' table-card--attention' : ''}`}>
    <header className="table-card__header">
      <div><span className="table-code">{table.code}</span><h2>{table.name}</h2></div>
      <span className={`table-state table-state--${checking ? 'checking' : failed ? 'attention' : occupied ? 'occupied' : 'available'}`}>
        {checking ? 'Comprobando' : failed ? 'Requiere atención' : occupied ? 'En servicio' : 'Disponible'}
      </span>
    </header>
    {checking ? <p className="table-card__copy">Consultando el estado de la mesa…</p> : null}
    {failed ? <p className="table-card__copy">No fue posible verificar el estado. Actualiza antes de orientar a los comensales.</p> : null}
    {occupied && session ? <div className="session-summary"><dl><div><dt>Comensales activos</dt><dd>{session.active_diner_count}</dd></div><div><dt>Personas esperadas</dt><dd>{session.party_size}</dd></div></dl><p>{elapsedLabel(session.opened_at)}</p></div> : null}
    {!checking && !failed && !session ? <p className="table-card__copy">Sin servicio activo.</p> : null}
    <section className="waiter-summary" aria-label={`Meseros asignados a ${table.name}`}>
      <strong>Meseros asignados</strong>
      {assignment?.assignments.length ? <ul>{assignment.assignments.map((waiter) => <li key={waiter.membership_id}><span>{waiter.display_name}</span>{waiter.is_responsible ? <strong>Responsable</strong> : null}</li>)}</ul> : <p>Sin asignación visible.</p>}
    </section>
    <footer className="table-card__actions"><span className="read-only-label">Consulta solamente</span></footer>
  </article>;
}

export function HostPage() {
  const { location } = useStaffContext();
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
  const counts = useMemo(() => sessionQueries.reduce((value, query) => {
    if (query.isSuccess) query.data ? value.occupied++ : value.available++;
    else value.pending++;
    return value;
  }, { available: 0, occupied: 0, pending: 0 }), [sessionQueries]);
  const refresh = async () => {
    await Promise.all([tablesQuery.refetch(), ...sessionQueries.map((query) => query.refetch()), ...assignmentQueries.map((query) => query.refetch())]);
  };

  return <section className="host-page" aria-labelledby="host-heading">
    <header className="host-heading">
      <div><p className="eyebrow">Recepción · {location?.name}</p><h1 id="host-heading">Llegada de comensales</h1><p>Solicita la preparación y consulta qué mesa o grupo está listo.</p></div>
      <button className="secondary-button" type="button" onClick={() => void refresh()} disabled={tablesQuery.isFetching}>Actualizar</button>
    </header>
    <ReceptionPreparationRequests />
    <TableManagementPanel title="Mesas y grupos preparados" readOnly />
    <div className="host-metrics" aria-label="Resumen de mesas"><div><strong>{counts.available}</strong><span>Disponibles</span></div><div><strong>{counts.occupied}</strong><span>En servicio</span></div><div><strong>{counts.pending}</strong><span>Por verificar</span></div></div>
    {tablesQuery.isPending ? <div className="host-state" role="status"><span className="state-spinner" aria-hidden="true">◌</span><strong>Cargando mesas</strong><p>Aún no determinamos disponibilidad.</p></div> : null}
    {tablesQuery.isError ? <div className="host-state" role="alert"><strong>No pudimos cargar las mesas</strong><p>{readableError(tablesQuery.error, 'Revisa la conexión e inténtalo de nuevo.')}</p><button className="primary-button" type="button" onClick={() => void tablesQuery.refetch()}>Reintentar</button></div> : null}
    {tablesQuery.isSuccess && tables.length === 0 ? <div className="host-state"><strong>No hay mesas activas configuradas</strong><p>La sucursal no devolvió mesas activas.</p></div> : null}
    {tables.length ? <div className="table-grid" role="list" aria-label="Mesas de la sucursal">{tables.map((table, index) => <ReceptionTableCard key={table.id} table={table} session={sessionQueries[index]?.data} checking={!sessionQueries[index] || sessionQueries[index].isPending} failed={Boolean(sessionQueries[index]?.isError)} assignment={assignmentQueries[index]?.data} />)}</div> : null}
  </section>;
}
