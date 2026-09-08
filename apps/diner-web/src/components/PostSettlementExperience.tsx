import { useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type {
  OperationalRequestResponse,
  OperationalRequestType,
  RestaurantCheckResponse,
} from '../api/contracts';
import { useAuth } from '../session/AuthContext';

const requestOptions: Array<{
  type: Exclude<OperationalRequestType, 'CASH_PAYMENT_ASSISTANCE'>;
  label: string;
  description: string;
}> = [
  {
    type: 'INVOICE_ASSISTANCE',
    label: 'Solicitar factura',
    description: 'El equipo del restaurante te ayudará con tus datos fiscales y la emisión.',
  },
  {
    type: 'PAID_CHECK_PRINT',
    label: 'Solicitar cuenta impresa',
    description: 'El equipo recibirá tu solicitud y gestionará la impresión autorizada.',
  },
  {
    type: 'HUMAN_ASSISTANCE',
    label: 'Necesito ayuda',
    description: 'Envía una solicitud general de asistencia al equipo del restaurante.',
  },
];

interface Props {
  check: RestaurantCheckResponse;
  paymentId?: number;
}

export function PostSettlementExperience({ check, paymentId }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { markSessionClosed, session } = useAuth();
  const intentPrefix = `diner-c5:${session?.dinerSessionId ?? 'unknown'}:${check.id}`;
  const requestKeys = useRef(new Map<OperationalRequestType, string>());
  const requestInFlight = useRef(false);
  const continuationIntent = useRef<{ decision: 'YES' | 'NO'; key: string } | null>((() => {
    const stored = sessionStorage.getItem(`${intentPrefix}:continuation`);
    if (!stored) return null;
    try {
      const parsed = JSON.parse(stored) as { decision?: string; key?: string };
      if ((parsed.decision === 'YES' || parsed.decision === 'NO') && parsed.key) {
        return { decision: parsed.decision, key: parsed.key };
      }
    } catch {
      sessionStorage.removeItem(`${intentPrefix}:continuation`);
    }
    return null;
  })());
  const finishInFlight = useRef(false);
  const [requests, setRequests] = useState<Partial<Record<OperationalRequestType, OperationalRequestResponse>>>({});
  const [requestError, setRequestError] = useState<OperationalRequestType | null>(null);
  const [continuationNotice, setContinuationNotice] = useState<string | null>(null);
  const [finishPending, setFinishPending] = useState(check.continuation_decision === 'NO');
  const [finishing, setFinishing] = useState(false);
  const [closureRequiresStaff, setClosureRequiresStaff] = useState(false);

  const operationalRequest = useMutation({
    mutationFn: ({ type, key }: { type: OperationalRequestType; key: string }) => dinerApi.createOperationalRequest(
      type,
      type === 'HUMAN_ASSISTANCE' ? null : check.id,
      key,
    ),
    retry: false,
  });

  async function reconcileFinancialState(): Promise<RestaurantCheckResponse | undefined> {
    try {
      const latest = await dinerApi.getCheck(check.id);
      queryClient.setQueryData(['diner', 'restaurant-check', check.id], latest);
      const refetches = [
        queryClient.refetchQueries({ queryKey: ['diner', 'restaurant-check-settlement', check.id], exact: true }),
      ];
      if (paymentId !== undefined) {
        refetches.push(queryClient.refetchQueries({ queryKey: ['diner', 'payment', check.id, paymentId], exact: true }));
      }
      await Promise.all(refetches);
      return latest;
    } catch {
      return undefined;
    }
  }

  async function submitOperationalRequest(type: OperationalRequestType) {
    if (requestInFlight.current || requests[type]) return;
    requestInFlight.current = true;
    setRequestError(null);
    let key = requestKeys.current.get(type);
    if (!key) {
      const storageKey = `${intentPrefix}:request:${type}`;
      key = sessionStorage.getItem(storageKey)
        ?? `diner-post-settlement-${type.toLowerCase()}-${crypto.randomUUID()}`;
      sessionStorage.setItem(storageKey, key);
      requestKeys.current.set(type, key);
    }
    try {
      const result = await operationalRequest.mutateAsync({ type, key });
      setRequests((current) => ({ ...current, [type]: result }));
    } catch (error) {
      if (!(error instanceof ApiError && error.state === 'SESSION_CLOSED')) setRequestError(type);
    } finally {
      requestInFlight.current = false;
    }
  }

  async function finishSession() {
    if (finishInFlight.current) return;
    finishInFlight.current = true;
    setFinishing(true);
    setContinuationNotice(null);
    try {
      await dinerApi.endCurrentSession();
      markSessionClosed();
    } catch (error) {
      if (error instanceof ApiError && error.state === 'SESSION_CLOSED') return;
      if (error instanceof ApiError && error.status === 409) {
        await reconcileFinancialState();
        setFinishPending(false);
        setClosureRequiresStaff(true);
        setContinuationNotice('La decisión quedó registrada. El equipo del restaurante completará el cierre correspondiente.');
        return;
      }
      if (error instanceof ApiError && error.status === 0) {
        try {
          await dinerApi.getCurrentSession();
        } catch (readError) {
          if (readError instanceof ApiError && readError.state === 'SESSION_CLOSED') return;
        }
      }
      await reconcileFinancialState();
      setFinishPending(true);
      setContinuationNotice('La decisión quedó registrada, pero aún no pudimos confirmar el cierre. Puedes volver a intentarlo de forma segura.');
    } finally {
      finishInFlight.current = false;
      setFinishing(false);
    }
  }

  const continuation = useMutation({
    mutationFn: ({ decision, key }: { decision: 'YES' | 'NO'; key: string }) => dinerApi.decideContinuation(
      check.id,
      check.version,
      decision,
      key,
    ),
    retry: false,
  });

  async function decide(decision: 'YES' | 'NO') {
    const existing = continuationIntent.current;
    if (existing && existing.decision !== decision) {
      setContinuationNotice('Primero debemos confirmar la decisión anterior antes de enviar una distinta.');
      await reconcileFinancialState();
      return;
    }
    const intent = existing ?? {
      decision,
      key: `diner-continuation-${crypto.randomUUID()}`,
    };
    continuationIntent.current = intent;
    sessionStorage.setItem(`${intentPrefix}:continuation`, JSON.stringify(intent));
    setContinuationNotice(null);
    try {
      const result = await continuation.mutateAsync(intent);
      queryClient.setQueryData(['diner', 'restaurant-check', check.id], result);
      if (result.continuation_decision === 'YES') {
        navigate('/menu', { replace: true });
      } else if (result.continuation_decision === 'NO') {
        setFinishPending(true);
        await finishSession();
      }
    } catch (error) {
      if (error instanceof ApiError && error.state === 'SESSION_CLOSED') return;
      const latest = await reconcileFinancialState();
      if (latest?.continuation_decision === 'YES') {
        navigate('/menu', { replace: true });
        return;
      }
      if (latest?.continuation_decision === 'NO') {
        setFinishPending(true);
        await finishSession();
        return;
      }
      setContinuationNotice(
        error instanceof ApiError && error.status === 0
          ? 'No pudimos confirmar la decisión. Conservamos la misma solicitud para que puedas reintentarla sin enviar una decisión distinta.'
          : 'El estado cambió antes de registrar la decisión. Actualizamos la cuenta; revisa su estado antes de continuar.',
      );
    }
  }

  const lockedDecision = continuationIntent.current?.decision;
  const continuationPending = continuation.isPending || finishing;

  return (
    <section className="post-settlement" aria-labelledby="post-settlement-title">
      <div className="post-settlement-heading">
        <span className="post-settlement-mark" aria-hidden="true">✓</span>
        <div>
          <p className="eyebrow">Cuenta liquidada</p>
          <h2 id="post-settlement-title">Gracias. ¿Necesitas algo más?</h2>
          <p>Tu pago está confirmado. Estas solicitudes se enviarán al equipo del restaurante.</p>
        </div>
      </div>

      <div className="post-settlement-section" aria-labelledby="account-help-title">
        <p className="panel-kicker">Necesidades posteriores</p>
        <h3 id="account-help-title">Relacionado con tu cuenta</h3>
        <div className="post-settlement-requests">
          {requestOptions.map((option) => {
            const result = requests[option.type];
            const isCurrent = operationalRequest.isPending && operationalRequest.variables?.type === option.type;
            return (
              <article key={option.type}>
                <div><h4>{option.label}</h4><p>{option.description}</p></div>
                {result ? (
                  <p className="request-acknowledgement" role="status">
                    <strong>Solicitud enviada</strong>
                    <span>Estado del restaurante: {result.status === 'PENDING' ? 'Pendiente' : result.status}</span>
                  </p>
                ) : (
                  <button className="secondary-button" type="button" disabled={operationalRequest.isPending} onClick={() => submitOperationalRequest(option.type)}>
                    {isCurrent ? 'Enviando solicitud…' : option.label}
                  </button>
                )}
                {requestError === option.type && <p className="request-error" role="alert">No pudimos confirmar la solicitud. Reintenta para usar la misma identidad segura.</p>}
              </article>
            );
          })}
        </div>
      </div>

      <div className="post-settlement-section continuation-panel" aria-labelledby="continuation-title">
        <p className="panel-kicker">Continuación del servicio</p>
        <h3 id="continuation-title">¿Desean algo más?</h3>
        {closureRequiresStaff ? (
          <div className="continuation-result" role="status"><strong>Decisión registrada.</strong><span>El equipo completará el cierre correspondiente.</span></div>
        ) : check.continuation_decision === 'PENDING' && !finishPending ? (
          <>
            <p>Elige explícitamente si desean seguir ordenando o terminar esta visita.</p>
            <div className="continuation-actions">
              <button className="primary-button" type="button" disabled={continuationPending || lockedDecision === 'NO'} onClick={() => decide('YES')}>
                {continuation.isPending && lockedDecision === 'YES' ? 'Confirmando…' : 'Sí, queremos continuar'}
              </button>
              <button className="secondary-button" type="button" disabled={continuationPending || lockedDecision === 'YES'} onClick={() => decide('NO')}>
                {continuation.isPending && lockedDecision === 'NO' ? 'Confirmando…' : 'No, hemos terminado'}
              </button>
            </div>
          </>
        ) : check.continuation_decision === 'YES' ? (
          <div className="continuation-result" role="status"><strong>Pueden seguir ordenando.</strong><Link to="/menu">Volver al menú</Link></div>
        ) : (
          <div className="continuation-result"><p>La decisión de terminar ya fue registrada.</p><button className="primary-button" type="button" disabled={continuationPending} onClick={finishSession}>{continuationPending ? 'Finalizando…' : 'Finalizar mi sesión'}</button></div>
        )}
        {continuationNotice && <p className="continuation-notice" role="alert">{continuationNotice}</p>}
      </div>
    </section>
  );
}
