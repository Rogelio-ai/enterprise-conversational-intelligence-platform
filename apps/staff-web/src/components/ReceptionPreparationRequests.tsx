import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { InternalMessageDetail } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';

function formatTime(value: string): string {
  return new Intl.DateTimeFormat('es-MX', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

function progress(detail: InternalMessageDetail): string {
  if (detail.ready_at) return 'Listo';
  if (detail.entered_at) return 'Enterado';
  return 'Solicitado';
}

function historyLabel(eventType: string): string {
  return ({
    MESSAGE_CREATED: 'Solicitado',
    ENTERADO: 'Enterado',
    RESPONSE_ADDED: 'Respuesta',
    READY: 'Listo',
  } as Record<string, string>)[eventType] ?? 'Actualización';
}

export function ReceptionPreparationRequests() {
  const { location, hasPermission } = useStaffContext();
  const queryClient = useQueryClient();
  const canRead = hasPermission('internal_message.read');
  const canSend = hasPermission('internal_message.send');
  const [partySize, setPartySize] = useState('');
  const [waiterId, setWaiterId] = useState('');
  const [validation, setValidation] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const intent = useRef<{ signature: string; key: string } | null>(null);
  useEffect(() => {
    setPartySize(''); setWaiterId(''); setValidation(null); setNotice(null); intent.current = null;
  }, [location?.id]);
  const sent = useQuery({
    queryKey: ['internal-messages', location?.id, 'sent'],
    queryFn: () => staffApi.sentInternalMessages(location!.id),
    enabled: Boolean(location && canRead),
    retry: false,
    refetchInterval: 10_000,
  });
  const waiters = useQuery({
    queryKey: ['staff', 'host', 'eligible-waiters', location?.id],
    queryFn: () => staffApi.eligibleTableWaiters(location!.id),
    enabled: Boolean(location && canSend),
    retry: false,
  });
  const details = useQueries({
    queries: (sent.data?.items ?? []).map((message) => ({
      queryKey: ['internal-messages', location?.id, 'detail', message.id],
      queryFn: () => staffApi.internalMessage(location!.id, message.id),
      enabled: canRead,
      retry: false,
      refetchInterval: 10_000,
    })),
  });
  const send = useMutation({
    mutationFn: ({ recipient, size, key }: { recipient: number; size: number; key: string }) => staffApi.createTablePreparationRequest(location!.id, recipient, size, key),
    onSuccess: async () => {
      intent.current = null;
      setPartySize(''); setWaiterId(''); setValidation(null); setNotice('Solicitud enviada al mesero.');
      await queryClient.invalidateQueries({ queryKey: ['internal-messages', location?.id, 'sent'] });
    },
    onError: async (error) => {
      setValidation(error instanceof ApiError && error.status === 409 ? 'La solicitud cambió. Actualizamos la información.' : error instanceof ApiError ? error.message : 'No fue posible enviar la solicitud.');
      if (error instanceof ApiError && error.status === 409) await sent.refetch();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const size = Number(partySize);
    if (!Number.isInteger(size) || size <= 0 || size > 999) { setValidation('Indica cuántas personas son (entre 1 y 999).'); return; }
    if (!waiterId) { setValidation('Selecciona al mesero que preparará la mesa.'); return; }
    const signature = `${waiterId}:${size}`;
    if (intent.current?.signature !== signature) intent.current = { signature, key: crypto.randomUUID() };
    send.mutate({ recipient: Number(waiterId), size, key: intent.current.key });
  };
  if (!canRead && !canSend) return null;
  return (
    <section className="preparation-requests" aria-labelledby="arrival-heading">
      <div className="operational-section-heading"><div><p className="eyebrow">Llegada de comensales</p><h2 id="arrival-heading">Solicitar preparación de mesa</h2><p>La solicitud ocurre antes de abrir una sesión de servicio.</p></div></div>
      {canSend ? <form className="arrival-form" onSubmit={submit}>
        <label className="field"><span>¿Cuántas personas son?</span><input type="number" min="1" max="999" value={partySize} onChange={(event) => { setPartySize(event.target.value); setValidation(null); }} required /></label>
        <label className="field"><span>Mesero</span><select value={waiterId} onChange={(event) => { setWaiterId(event.target.value); setValidation(null); }} required><option value="">Selecciona un mesero</option>{waiters.data?.items.map((waiter) => <option key={waiter.membership_id} value={waiter.membership_id}>{waiter.display_name}</option>)}</select></label>
        <button className="primary-button" type="submit" disabled={send.isPending}>{send.isPending ? 'Enviando…' : 'Solicitar mesa'}</button>
      </form> : null}
      {validation ? <p className="field-error" role="alert">{validation}</p> : null}
      {notice ? <p className="operational-notice operational-notice--success" role="status">{notice}</p> : null}
      {canRead ? <div className="internal-message-list" role="list" aria-label="Solicitudes de preparación enviadas">
        {sent.isPending ? <p>Cargando solicitudes…</p> : null}
        {sent.isError ? <p role="alert">No fue posible consultar las solicitudes enviadas.</p> : null}
        {sent.data?.items.length === 0 ? <p>No hay solicitudes de preparación.</p> : null}
        {sent.data?.items.map((summary, index) => {
          const detail = details[index]?.data;
          const value = detail ?? summary;
          return <article className="internal-message-card" role="listitem" key={summary.id}>
            <header><div><p className="request-kind">Mesa para {value.party_size} personas</p><h3>{value.recipient.display_name}</h3></div><span className={`message-progress message-progress--${progress(detail ?? ({ ...summary, responses: [], history: [], prepared_table: null, allowed_actions: [], enterado: null, ready: null } as InternalMessageDetail)).toLowerCase()}`}>{progress(detail ?? ({ ...summary, responses: [], history: [], prepared_table: null, allowed_actions: [], enterado: null, ready: null } as InternalMessageDetail))}</span></header>
            <p>{value.text}</p><small>Solicitado {formatTime(value.created_at)}</small>
            {value.entered_at ? <p><strong>Enterado:</strong> {formatTime(value.entered_at)}</p> : null}
            {detail?.responses.length ? <ol className="message-responses">{detail.responses.map((response) => <li key={response.id}><strong>{response.author.display_name}:</strong> {response.content}</li>)}</ol> : null}
            {detail?.history.length ? <details><summary>Historial</summary><ol className="message-responses">{detail.history.map((event) => <li key={event.sequence}><strong>{historyLabel(event.event_type)}</strong> · {event.actor.display_name}<small>{formatTime(event.occurred_at)}</small></li>)}</ol></details> : null}
            {detail?.ready_at && detail.prepared_table ? <div className="prepared-table-result"><strong>La mesa está lista: {detail.prepared_table.is_group_representative ? '*' : ''}{detail.prepared_table.name}</strong>{detail.prepared_table.is_group_representative ? <ul className="prepared-table-members">{detail.prepared_table.members.map((member, index) => <li key={member.resource_id}>{index === 0 ? `*${member.name}` : member.name}</li>)}</ul> : null}<span>Capacidad: {detail.prepared_table.derived_group_capacity ?? detail.prepared_table.physical_capacity}</span><small>Listo {formatTime(detail.ready_at)}</small></div> : null}
          </article>;
        })}
      </div> : null}
    </section>
  );
}
