import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { InternalMessageDetail } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

function historyLabel(eventType: string): string {
  return ({
    MESSAGE_CREATED: 'Solicitado',
    ENTERADO: 'Enterado',
    RESPONSE_ADDED: 'Respuesta',
    READY: 'Listo',
  } as Record<string, string>)[eventType] ?? 'Actualización';
}

export function WaiterInternalInbox() {
  const { location, hasPermission } = useStaffContext();
  const queryClient = useQueryClient();
  const canRead = hasPermission('internal_message.read');
  const canRespond = hasPermission('internal_message.respond');
  const canReadTables = hasPermission('resource.read');
  const [responseFor, setResponseFor] = useState<number | null>(null);
  const [responseText, setResponseText] = useState('');
  const [prepared, setPrepared] = useState<Record<number, string>>({});
  const [feedback, setFeedback] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const responseIntents = useRef(new Map<number, { content: string; key: string }>());
  useEffect(() => {
    setResponseFor(null); setResponseText(''); setPrepared({}); setFeedback(null); responseIntents.current.clear();
  }, [location?.id]);
  const inbox = useQuery({
    queryKey: ['internal-messages', location?.id, 'inbox'],
    queryFn: () => staffApi.internalMessageInbox(location!.id),
    enabled: Boolean(location && canRead),
    retry: false,
    refetchInterval: 10_000,
  });
  const details = useQueries({
    queries: (inbox.data?.items ?? []).map((message) => ({
      queryKey: ['internal-messages', location?.id, 'detail', message.id],
      queryFn: () => staffApi.internalMessage(location!.id, message.id),
      enabled: canRead,
      retry: false,
      refetchInterval: 10_000,
    })),
  });
  const tables = useQuery({
    queryKey: ['table-management', location?.id, 'tables'],
    queryFn: () => staffApi.managedTables(location!.id),
    enabled: Boolean(location && canReadTables),
    retry: false,
    refetchInterval: 12_000,
  });
  const representativeTables = tables.data?.items.filter((table) => table.is_group_representative && table.active_group_id) ?? [];
  const tableGroups = useQueries({
    queries: representativeTables.map((table) => ({
      queryKey: ['table-management', location?.id, 'group', table.active_group_id],
      queryFn: () => staffApi.activeTableGroup(location!.id, table.resource_id),
      enabled: Boolean(location && canReadTables),
      retry: false,
      refetchInterval: 12_000,
    })),
  });
  const refresh = async (messageId: number) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['internal-messages', location?.id, 'inbox'] }),
      queryClient.invalidateQueries({ queryKey: ['internal-messages', location?.id, 'detail', messageId] }),
    ]);
  };
  const mutation = useMutation({
    mutationFn: async (action: { kind: 'enterado'; messageId: number } | { kind: 'respond'; messageId: number; content: string; key: string } | { kind: 'ready'; messageId: number; tableId: number }) => {
      if (action.kind === 'enterado') return staffApi.enterInternalMessage(location!.id, action.messageId);
      if (action.kind === 'respond') return staffApi.respondInternalMessage(location!.id, action.messageId, action.content, action.key);
      return staffApi.readyInternalMessage(location!.id, action.messageId, action.tableId);
    },
    onSuccess: async (detail, action) => {
      queryClient.setQueryData(['internal-messages', location?.id, 'detail', detail.id], detail);
      if (action.kind === 'respond') { responseIntents.current.delete(action.messageId); setResponseFor(null); setResponseText(''); }
      setFeedback({ kind: 'success', text: action.kind === 'ready' ? 'La mesa está lista; Recepción ya puede verla.' : action.kind === 'enterado' ? 'Enterado registrado.' : 'Respuesta enviada.' });
      await refresh(action.messageId);
    },
    onError: async (error, action) => {
      setFeedback({ kind: 'error', text: error instanceof ApiError && error.status === 409 ? 'El estado cambió. Mostramos la versión canónica más reciente.' : error instanceof ApiError ? error.message : 'No fue posible completar la acción.' });
      if (error instanceof ApiError && (error.status === 409 || error.status === 404)) await refresh(action.messageId);
    },
  });
  const submitResponse = (event: FormEvent, messageId: number) => {
    event.preventDefault();
    const content = responseText.trim();
    if (!content) return;
    const old = responseIntents.current.get(messageId);
    const intent = old?.content === content ? old : { content, key: crypto.randomUUID() };
    responseIntents.current.set(messageId, intent);
    mutation.mutate({ kind: 'respond', messageId, ...intent });
  };
  if (!canRead) return null;
  const candidates = tables.data?.items.filter((table) => table.operational_status === 'AVAILABLE' && (!table.active_group_id || table.is_group_representative)) ?? [];
  return (
    <section className="waiter-internal-inbox" aria-labelledby="internal-inbox-heading">
      <div className="operational-section-heading"><div><p className="eyebrow">Recepción · IMP-B</p><h2 id="internal-inbox-heading">Preparación de mesas</h2><p>Solicitudes internas separadas de la atención a comensales.</p></div><button type="button" className="secondary-button" onClick={() => void inbox.refetch()} disabled={inbox.isFetching}>Actualizar</button></div>
      {feedback ? <p className={`operational-notice operational-notice--${feedback.kind}`} role={feedback.kind === 'error' ? 'alert' : 'status'}>{feedback.text}</p> : null}
      {inbox.isPending ? <p>Cargando solicitudes internas…</p> : null}
      {inbox.isError ? <p role="alert">No fue posible consultar las solicitudes de Recepción.</p> : null}
      {inbox.data?.items.length === 0 ? <p>No hay mesas pendientes de preparación.</p> : null}
      <div className="internal-message-list" role="list" aria-label="Solicitudes internas">
        {inbox.data?.items.map((summary, index) => {
          const detail = details[index]?.data;
          if (!detail) return <article className="internal-message-card" role="listitem" key={summary.id}><p>Cargando mesa para {summary.party_size} personas…</p></article>;
          const enterAllowed = canRespond && detail.allowed_actions.includes('ENTERADO');
          const respondAllowed = canRespond && detail.allowed_actions.includes('RESPOND');
          const readyAllowed = canRespond && detail.allowed_actions.includes('READY');
          const selectedTable = prepared[detail.id] ?? '';
          const selectedCandidate = candidates.find((table) => String(table.resource_id) === selectedTable);
          const selectedGroup = selectedCandidate?.active_group_id
            ? tableGroups.find((query) => query.data?.id === selectedCandidate.active_group_id)?.data
            : undefined;
          return <article className="internal-message-card" role="listitem" key={detail.id}>
            <header><div><p className="request-kind">Mesa para {detail.party_size} personas</p><h3>{detail.creator.display_name}</h3></div><span className={`message-progress message-progress--${detail.ready_at ? 'listo' : detail.entered_at ? 'enterado' : 'solicitado'}`}>{detail.ready_at ? 'Listo' : detail.entered_at ? 'Enterado' : 'Solicitado'}</span></header>
            <p>{detail.text}</p><small>Recibida {formatTime(detail.created_at)}</small>
            {detail.responses.length ? <ol className="message-responses">{detail.responses.map((response) => <li key={response.id}><strong>{response.author.display_name}:</strong> {response.content}<small>{formatTime(response.created_at)}</small></li>)}</ol> : null}
            {detail.history.length ? <details><summary>Historial</summary><ol className="message-responses">{detail.history.map((event) => <li key={event.sequence}><strong>{historyLabel(event.event_type)}</strong> · {event.actor.display_name}<small>{formatTime(event.occurred_at)}</small></li>)}</ol></details> : null}
            {detail.prepared_table ? <div className="prepared-table-result"><strong>{detail.prepared_table.is_group_representative ? '*' : ''}{detail.prepared_table.name}</strong>{detail.prepared_table.is_group_representative ? <ul className="prepared-table-members">{detail.prepared_table.members.map((member, index) => <li key={member.resource_id}>{index === 0 ? `*${member.name}` : member.name}</li>)}</ul> : null}<span>Capacidad: {detail.prepared_table.derived_group_capacity ?? detail.prepared_table.physical_capacity}</span></div> : null}
            {responseFor === detail.id && respondAllowed ? <form className="response-composer" onSubmit={(event) => submitResponse(event, detail.id)}><label htmlFor={`internal-response-${detail.id}`}>Respuesta a Recepción</label><textarea id={`internal-response-${detail.id}`} rows={3} maxLength={4000} value={responseText} onChange={(event) => setResponseText(event.target.value)} autoFocus /><div className="response-composer__actions"><button type="button" className="secondary-button" onClick={() => { setResponseFor(null); setResponseText(''); }}>Cancelar</button><button type="submit" className="primary-button" disabled={!responseText.trim() || mutation.isPending}>Enviar</button></div></form> : null}
              {readyAllowed ? <label className="field"><span>Mesa preparada</span><select aria-label={`Mesa preparada para ${detail.party_size} personas`} value={selectedTable} onChange={(event) => setPrepared((current) => ({ ...current, [detail.id]: event.target.value }))}><option value="">Selecciona la mesa preparada</option>{candidates.map((table) => { const group = tableGroups.find((query) => query.data?.id === table.active_group_id)?.data; return <option key={table.resource_id} value={table.resource_id}>{table.is_group_representative ? '*' : ''}{table.name} · capacidad {group?.derived_capacity ?? table.physical_capacity ?? 'sin definir'}</option>; })}</select></label> : null}
              {readyAllowed && selectedCandidate?.is_group_representative && selectedGroup ? <div className="prepared-table-result" aria-label="Grupo de mesas seleccionado"><strong>*{selectedCandidate.name}</strong><ul className="prepared-table-members">{selectedGroup.member_resource_ids.map((resourceId, index) => { const member = tables.data?.items.find((table) => table.resource_id === resourceId); return <li key={resourceId}>{index === 0 ? '*' : '├── '}{member?.name ?? selectedGroup.member_codes[index]}</li>; })}</ul><span>Capacidad: {selectedGroup.derived_capacity}</span></div> : null}
            <footer className="request-card__actions">
              {enterAllowed ? <button type="button" className="primary-button" disabled={mutation.isPending} onClick={() => mutation.mutate({ kind: 'enterado', messageId: detail.id })}>Enterado</button> : null}
              {respondAllowed && responseFor !== detail.id ? <button type="button" className="secondary-button" disabled={mutation.isPending} onClick={() => { setResponseFor(detail.id); setResponseText(''); }}>Responder</button> : null}
              {readyAllowed ? <button type="button" className="primary-button" disabled={!selectedTable || mutation.isPending} onClick={() => mutation.mutate({ kind: 'ready', messageId: detail.id, tableId: Number(selectedTable) })}>Listo</button> : null}
            </footer>
          </article>;
        })}
      </div>
    </section>
  );
}
