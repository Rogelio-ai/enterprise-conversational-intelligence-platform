import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { ManagedTable, TableGroup } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';

type Notice = { kind: 'success' | 'error'; text: string };

function tableLabel(table: ManagedTable): string {
  return `${table.is_group_representative ? '*' : ''}${table.name}`;
}

function statusLabel(value: string | null): string {
  if (!value) return 'Sin dato';
  return ({ AVAILABLE: 'Disponible', OCCUPIED: 'En servicio', ACTIVE: 'Activa', SUSPENDED: 'Suspendida', OUT_OF_SERVICE: 'Fuera de servicio', RETIRED: 'Retirada' } as Record<string, string>)[value] ?? 'Requiere atención';
}

function friendlyError(error: unknown): string {
  if (!(error instanceof ApiError)) return 'No fue posible completar la operación.';
  const text = error.message.toLowerCase();
  if (text.includes('service') || text.includes('session')) return 'No puedes modificar el grupo mientras tenga un servicio activo.';
  if (text.includes('member') || text.includes('group')) return 'Esta mesa pertenece a un grupo activo. Primero sepárala del grupo.';
  if (text.includes('available')) return 'Mesa no disponible.';
  if (text.includes('movable')) return 'La mesa o su sección no permite este movimiento.';
  if (error.status === 409) return 'El estado cambió. Actualizamos las mesas; intenta nuevamente.';
  return error.message;
}

export function TableManagementPanel({ title = 'Organización de mesas', readOnly = false }: { title?: string; readOnly?: boolean }) {
  const { location, hasPermission } = useStaffContext();
  const locationId = location?.id;
  const queryClient = useQueryClient();
  const canRead = hasPermission('resource.read') && Boolean(locationId);
  const canManage = !readOnly && hasPermission('table_management.manage');
  const [notice, setNotice] = useState<Notice | null>(null);
  const [joining, setJoining] = useState<number | null>(null);
  const [joinedIds, setJoinedIds] = useState<number[]>([]);
  const [responsibleIds, setResponsibleIds] = useState<number[]>([]);
  const [adding, setAdding] = useState<TableGroup | null>(null);
  const [addTableId, setAddTableId] = useState('');
  const [moving, setMoving] = useState<ManagedTable | null>(null);
  const [sectionId, setSectionId] = useState('');
  useEffect(() => {
    setNotice(null); setJoining(null); setJoinedIds([]); setResponsibleIds([]);
    setAdding(null); setAddTableId(''); setMoving(null); setSectionId('');
  }, [locationId]);

  const tablesQuery = useQuery({
    queryKey: ['table-management', locationId, 'tables'],
    queryFn: () => staffApi.managedTables(locationId!),
    enabled: canRead,
    retry: false,
    refetchInterval: 12_000,
  });
  const sectionsQuery = useQuery({
    queryKey: ['table-management', locationId, 'sections'],
    queryFn: () => staffApi.diningSections(locationId!),
    enabled: canRead,
    retry: false,
  });
  const tables = tablesQuery.data?.items ?? [];
  const representatives = tables.filter((table) => table.is_group_representative && table.active_group_id);
  const groupQueries = useQueries({
    queries: representatives.map((table) => ({
      queryKey: ['table-management', locationId, 'group', table.active_group_id],
      queryFn: () => staffApi.activeTableGroup(locationId!, table.resource_id),
      enabled: canRead,
      retry: false,
      refetchInterval: 12_000,
    })),
  });
  const groups = groupQueries.map((query) => query.data).filter((group): group is TableGroup => Boolean(group));
  const assignments = useQueries({
    queries: tables.map((table) => ({
      queryKey: ['table-management', locationId, 'waiter-assignments', table.resource_id],
      queryFn: () => staffApi.tableWaiterAssignments(locationId!, table.resource_id),
      enabled: canRead,
      retry: false,
    })),
  });
  const tableById = useMemo(() => new Map(tables.map((table) => [table.resource_id, table])), [tables]);
  const waiterById = useMemo(() => {
    const result = new Map<number, string>();
    assignments.forEach((query) => query.data?.assignments.forEach((waiter) => result.set(waiter.membership_id, waiter.display_name)));
    return result;
  }, [assignments]);
  const selectedIds = joining ? [joining, ...joinedIds] : [];
  const selectedAssignments = selectedIds.map((id) => assignments[tables.findIndex((table) => table.resource_id === id)]);
  const selectedAssignmentsReady = selectedIds.length > 1 && selectedAssignments.every((query) => query?.isSuccess);
  const available = tables.filter((table) => table.operational_status === 'AVAILABLE' && !table.active_group_id && table.effective_movable);
  const preview = useQuery({
    queryKey: ['table-management', locationId, 'group-preview', joining, ...joinedIds.slice().sort((a, b) => a - b)],
    queryFn: () => staffApi.previewTableGroup(locationId!, joining!, joinedIds),
    enabled: Boolean(canManage && joining && joinedIds.length),
    retry: false,
  });
  const selectedWaiterIds = preview.data?.assigned_membership_ids ?? [];
  const responsibilityResolved = selectedAssignmentsReady
    && selectedWaiterIds.length > 0
    && selectedWaiterIds.every((membershipId) => waiterById.has(membershipId));
  const automaticResponsibleIds = preview.data?.automatic_responsible_membership_ids ?? [];
  const responsibilitySelectionRequired = preview.data?.responsibility_selection_required ?? false;

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['table-management', locationId] });
  };
  const mutation = useMutation({
    mutationFn: async (action:
      | { kind: 'join'; representative: number; members: number[]; responsible: number[] }
      | { kind: 'add'; group: TableGroup; table: number }
      | { kind: 'remove'; group: TableGroup; table: number }
      | { kind: 'dissolve'; group: TableGroup }
      | { kind: 'move'; table: ManagedTable; section: number }) => {
      if (action.kind === 'join') return staffApi.createTableGroup(locationId!, action.representative, action.members, action.responsible);
      if (action.kind === 'add') return staffApi.addTableToGroup(locationId!, action.group.id, action.table, action.group.version);
      if (action.kind === 'remove') return staffApi.removeTableFromGroup(locationId!, action.group.id, action.table, action.group.version);
      if (action.kind === 'dissolve') return staffApi.dissolveTableGroup(locationId!, action.group.id, action.group.version);
      return staffApi.moveManagedTable(locationId!, action.table.resource_id, action.section, action.table.metadata_version ?? 1);
    },
    onSuccess: async (result, action) => {
      setNotice({
        kind: 'success',
        text: action.kind === 'join'
          ? `Grupo confirmado con capacidad ${'derived_capacity' in result ? result.derived_capacity : 'calculada'}.`
          : 'La organización de mesas quedó actualizada.',
      });
      setJoining(null); setJoinedIds([]); setResponsibleIds([]); setAdding(null); setAddTableId(''); setMoving(null); setSectionId('');
      await refresh();
    },
    onError: async (error) => { setNotice({ kind: 'error', text: friendlyError(error) }); await refresh(); },
  });

  if (!canRead) return null;
  return (
    <section className="table-management-panel" aria-labelledby="table-management-heading">
      <div className="operational-section-heading"><div><p className="eyebrow">Organización confirmada</p><h2 id="table-management-heading">{title}</h2></div></div>
      {notice ? <p className={`operational-notice operational-notice--${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>{notice.text}</p> : null}
      {tablesQuery.isPending ? <p>Cargando organización de mesas…</p> : null}
      {tablesQuery.isError ? <p>No fue posible consultar la organización de mesas.</p> : null}
      <div className="managed-table-grid" role="list" aria-label="Organización de mesas">
        {tables.map((table) => {
          const group = groups.find((value) => value.id === table.active_group_id);
          const members = group?.member_resource_ids.map((id) => tableById.get(id)).filter((value): value is ManagedTable => Boolean(value)) ?? [];
          return <article className="managed-table" role="listitem" key={table.resource_id}>
            <header><h3>{tableLabel(table)}</h3><span>{statusLabel(table.operational_status)}</span></header>
            <dl><div><dt>Sección</dt><dd>{table.dining_section_name ?? 'Sin sección'}</dd></div><div><dt>Capacidad física</dt><dd>{table.physical_capacity ?? 'No definida'}</dd></div><div><dt>Estado administrativo</dt><dd>{statusLabel(table.administrative_status)}</dd></div></dl>
            {group ? <div className="table-group-summary"><strong>Capacidad del grupo: {group.derived_capacity}</strong><ul>{members.map((member) => <li key={member.resource_id}>{member.resource_id === group.representative_resource_id ? `*${member.name}` : member.name}</li>)}</ul></div> : null}
            {canManage ? <div className="managed-table__actions">
              {!table.active_group_id && table.operational_status === 'AVAILABLE' ? <button type="button" className="secondary-button" onClick={() => { setJoining(table.resource_id); setJoinedIds([]); setResponsibleIds([]); }}>Unir mesas</button> : null}
              {group && table.is_group_representative ? <><button type="button" className="secondary-button" onClick={() => setAdding(group)}>Agregar mesa</button><button type="button" className="danger-button" onClick={() => mutation.mutate({ kind: 'dissolve', group })}>Disolver grupo</button></> : null}
              {group && !table.is_group_representative ? <button type="button" className="secondary-button" onClick={() => mutation.mutate({ kind: 'remove', group, table: table.resource_id })}>Retirar mesa</button> : null}
              <button type="button" className="quiet-button" disabled={!table.effective_movable || Boolean(table.active_group_id && !table.is_group_representative)} title={table.active_group_id && !table.is_group_representative ? 'Primero separa la mesa del grupo.' : undefined} onClick={() => { setMoving(table); setSectionId(''); }}>Mover mesa</button>
            </div> : null}
          </article>;
        })}
      </div>

      {joining ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog" role="dialog" aria-modal="true" aria-labelledby="join-heading">
        <p className="eyebrow">Unir mesas</p><h2 id="join-heading">*{tableById.get(joining)?.name}</h2>
        <fieldset><legend>Mesas disponibles</legend>{available.filter((table) => table.resource_id !== joining).map((table) => <label key={table.resource_id}><input type="checkbox" checked={joinedIds.includes(table.resource_id)} onChange={() => { setJoinedIds((current) => current.includes(table.resource_id) ? current.filter((id) => id !== table.resource_id) : [...current, table.resource_id]); setResponsibleIds([]); }} />{table.name} · capacidad {table.physical_capacity ?? 'sin definir'}</label>)}</fieldset>
        <div className="group-preview"><strong>Grupo: *{tableById.get(joining)?.name}</strong><span>Mesas: {selectedIds.map((id) => tableById.get(id)?.name).join(' + ')}</span>{preview.isPending && joinedIds.length ? <span>Calculando capacidad…</span> : null}{preview.isError ? <span role="alert">{friendlyError(preview.error)}</span> : null}{preview.data ? <span>Capacidad: {preview.data.derived_capacity}</span> : null}</div>
        {joinedIds.length && (!preview.isSuccess || !responsibilityResolved) ? <p>Consultando responsabilidad de meseros…</p> : null}
        {responsibilityResolved && automaticResponsibleIds.length === 1 ? <p>Responsable automático: {waiterById.get(automaticResponsibleIds[0])}</p> : null}
        {responsibilityResolved && responsibilitySelectionRequired ? <fieldset><legend>Selecciona responsable(s) del grupo</legend>{selectedWaiterIds.map((id) => <label key={id}><input type="checkbox" checked={responsibleIds.includes(id)} onChange={() => setResponsibleIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])} />{waiterById.get(id)}</label>)}</fieldset> : null}
        <div className="dialog-actions"><button type="button" className="secondary-button" onClick={() => setJoining(null)}>Cancelar</button><button type="button" className="primary-button" disabled={!joinedIds.length || !preview.isSuccess || !responsibilityResolved || (responsibilitySelectionRequired && !responsibleIds.length) || mutation.isPending} onClick={() => mutation.mutate({ kind: 'join', representative: joining, members: joinedIds, responsible: responsibilitySelectionRequired ? responsibleIds : automaticResponsibleIds })}>Confirmar unión</button></div>
      </section></div> : null}

      {adding ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog" role="dialog" aria-modal="true" aria-labelledby="add-table-heading"><h2 id="add-table-heading">Agregar mesa a {tableById.get(adding.representative_resource_id)?.name}</h2><label className="field"><span>Mesa disponible</span><select value={addTableId} onChange={(event) => setAddTableId(event.target.value)}><option value="">Selecciona una mesa</option>{available.map((table) => <option key={table.resource_id} value={table.resource_id}>{table.name}</option>)}</select></label><div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setAdding(null)}>Cancelar</button><button className="primary-button" type="button" disabled={!addTableId || mutation.isPending} onClick={() => mutation.mutate({ kind: 'add', group: adding, table: Number(addTableId) })}>Agregar</button></div></section></div> : null}
      {moving ? <div className="modal-backdrop" role="presentation"><section className="operation-dialog" role="dialog" aria-modal="true" aria-labelledby="move-table-heading"><h2 id="move-table-heading">Mover {moving.name}</h2>{!moving.effective_movable ? <p role="alert">La mesa o su sección no permite movimientos.</p> : null}<label className="field"><span>Sección de destino</span><select value={sectionId} onChange={(event) => setSectionId(event.target.value)}><option value="">Selecciona una sección</option>{sectionsQuery.data?.items.filter((section) => section.status === 'ACTIVE' && section.id !== moving.dining_section_id).map((section) => <option key={section.id} value={section.id}>{section.name}</option>)}</select></label><div className="dialog-actions"><button className="secondary-button" type="button" onClick={() => setMoving(null)}>Cancelar</button><button className="primary-button" type="button" disabled={!sectionId || !moving.effective_movable || mutation.isPending} onClick={() => mutation.mutate({ kind: 'move', table: moving, section: Number(sectionId) })}>Confirmar movimiento</button></div></section></div> : null}
    </section>
  );
}
