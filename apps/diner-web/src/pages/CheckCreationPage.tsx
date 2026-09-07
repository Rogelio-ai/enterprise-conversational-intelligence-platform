import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type { CheckCreateMode, CheckCreateRequest, EligibleConsumptionResponse } from '../api/contracts';
import { DinerHeader } from '../components/DinerHeader';
import { useAuth } from '../session/AuthContext';
import { formatPrice } from '../utils/formatters';

type Outcome = { kind: 'ambiguous' | 'conflict'; message: string } | null;

function eligibleMoney(value: EligibleConsumptionResponse): string {
  return value.currency ? formatPrice(value.eligible_total, value.currency) : `${value.eligible_total} · moneda no unificada`;
}

function conflictMessage(error: ApiError): string {
  if (error.code === 'DINER_HAS_ACTIVE_ORDER_DRAFT') return 'Hay un pedido en borrador. Revísalo antes de crear la cuenta.';
  if (error.code === 'NO_ELIGIBLE_CONSUMPTION') return 'El restaurante ya no reporta consumo disponible para esta selección.';
  if (error.code === 'CONSUMPTION_ALREADY_RESERVED' || error.code === 'DINER_ALREADY_ASSIGNED_TO_ACTIVE_CHECK' || error.code === 'DINER_HAS_ACTIVE_CHECK') {
    return 'Parte de este consumo ya pertenece a una cuenta activa.';
  }
  return 'La cuenta no pudo crearse porque el estado del restaurante cambió. Revisa la información actual antes de intentarlo de nuevo.';
}

export function CheckCreationPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<CheckCreateMode | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>(session ? [session.dinerSessionId] : []);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const intentRef = useRef<{ signature: string; key: string } | null>(null);
  const inFlight = useRef(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const eligibility = useQuery({
    queryKey: ['diner', 'eligible-consumption'],
    queryFn: dinerApi.getEligibleConsumption,
    retry: false,
  });

  useEffect(() => {
    document.title = 'Preparar cuenta · Mesa';
  }, []);

  useEffect(() => {
    if (eligibility.data || eligibility.error) heading.current?.focus();
  }, [eligibility.data, eligibility.error]);

  const diners = eligibility.data ?? [];
  const own = diners.find((value) => value.diner_session_id === session?.dinerSessionId);
  const activeCheckId = own?.active_check_id ?? null;
  const anyEligible = diners.some((value) => value.eligible_order_ids.length > 0);
  const selectedEligible = diners.some((value) => selectedIds.includes(value.diner_session_id) && value.eligible_order_ids.length > 0);
  const canCreate = mode === 'INDIVIDUAL'
    ? Boolean(own?.eligible_order_ids.length)
    : mode === 'GLOBAL_TABLE' ? anyEligible : mode === 'SELECTED' && selectedIds.length > 0 && selectedEligible;

  const payload = useMemo<CheckCreateRequest | null>(() => (
    mode === null ? null : mode === 'SELECTED' ? { mode, diner_session_ids: [...selectedIds].sort((a, b) => a - b) } : { mode }
  ), [mode, selectedIds]);

  async function recoverAuthoritativeState(error: ApiError): Promise<boolean> {
    let latest: EligibleConsumptionResponse[];
    try {
      latest = await dinerApi.getEligibleConsumption();
      queryClient.setQueryData(['diner', 'eligible-consumption'], latest);
    } catch {
      setOutcome({
        kind: 'ambiguous',
        message: 'No pudimos confirmar si el restaurante creó la cuenta. No repetiremos la solicitud automáticamente.',
      });
      return false;
    }
    const latestOwn = latest.find((value) => value.diner_session_id === session?.dinerSessionId);
    if (latestOwn?.active_check_id) {
      try {
        const check = await dinerApi.getCheck(latestOwn.active_check_id);
        queryClient.setQueryData(['diner', 'restaurant-check', check.id], check);
        navigate(`/check/${check.id}`, { replace: true });
        return true;
      } catch {
        setOutcome({ kind: 'ambiguous', message: 'El restaurante reporta una cuenta activa, pero no pudimos recuperarla. No repetiremos la creación automáticamente.' });
        return false;
      }
    }
    setOutcome(error.status === 0
      ? { kind: 'ambiguous', message: 'La respuesta se perdió y el restaurante aún no reporta una cuenta activa. Puedes verificar otra vez o repetir tu misma solicitud de forma segura.' }
      : { kind: 'conflict', message: conflictMessage(error) });
    if (error.status === 409) intentRef.current = null;
    return false;
  }

  async function submit() {
    if (!canCreate || !payload || inFlight.current) return;
    const signature = JSON.stringify(payload);
    if (!intentRef.current || intentRef.current.signature !== signature) {
      intentRef.current = { signature, key: `diner-check-${crypto.randomUUID()}` };
    }
    inFlight.current = true;
    setBusy(true);
    setOutcome(null);
    try {
      const check = await dinerApi.createCheck(payload, intentRef.current.key);
      navigate(`/check/${check.id}`, { replace: true });
    } catch (unknownError) {
      const error = unknownError instanceof ApiError
        ? unknownError
        : new ApiError(0, 'network_error', undefined, undefined);
      if (error.status === 0 || error.status === 409) {
        await recoverAuthoritativeState(error);
      } else {
        setOutcome({ kind: 'conflict', message: 'El restaurante no pudo crear la cuenta. Revisa los datos e intenta nuevamente.' });
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  function chooseMode(next: CheckCreateMode) {
    setMode(next);
    setOutcome(null);
    intentRef.current = null;
  }

  function toggleDiner(dinerId: number) {
    if (dinerId === session?.dinerSessionId) return;
    setSelectedIds((current) => current.includes(dinerId) ? current.filter((id) => id !== dinerId) : [...current, dinerId]);
    setOutcome(null);
    intentRef.current = null;
  }

  if (eligibility.isPending) return <div className="diner-page"><DinerHeader /><main className="product-state" aria-busy="true"><p>Cargando consumo elegible…</p></main></div>;
  if (activeCheckId) return <Navigate to={`/check/${activeCheckId}`} replace />;
  if (eligibility.isError) {
    return <div className="diner-page"><DinerHeader /><main className="product-state" role="alert"><p className="eyebrow">Consulta no disponible</p><h1 ref={heading} tabIndex={-1}>No pudimos preparar tu cuenta</h1><p>Ninguna cuenta fue creada. Vuelve a consultar el estado del restaurante.</p><div className="product-state-actions"><button className="primary-button button-link" type="button" onClick={() => eligibility.refetch()}>Reintentar</button><Link className="secondary-button button-link" to="/account">Volver a mi cuenta</Link></div></main></div>;
  }
  if (!own || !anyEligible) {
    return <div className="diner-page"><DinerHeader /><main className="product-state"><p className="eyebrow">Sin consumo elegible</p><h1 ref={heading} tabIndex={-1}>No hay una cuenta por crear</h1><p>El restaurante no reporta consumo disponible en este momento.</p><Link className="primary-button button-link" to="/account">Volver a mi cuenta</Link></main></div>;
  }

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="check-main">
        <header className="account-hero">
          <p className="eyebrow">Acción explícita</p>
          <h1 ref={heading} tabIndex={-1}>Preparar cuenta</h1>
          <p>Elige qué consumo incluir. La cuenta sólo se creará cuando confirmes al final.</p>
        </header>
        <div className="check-create-layout">
          <section className="check-scope-card" aria-labelledby="check-scope-title">
            <h2 id="check-scope-title">¿Qué consumo quieres incluir?</h2>
            <label><input type="radio" name="scope" checked={mode === 'INDIVIDUAL'} disabled={busy} onChange={() => chooseMode('INDIVIDUAL')} /><span><strong>Sólo mi consumo</strong><small>{eligibleMoney(own)}</small></span></label>
            <label><input type="radio" name="scope" checked={mode === 'GLOBAL_TABLE'} disabled={busy} onChange={() => chooseMode('GLOBAL_TABLE')} /><span><strong>Toda la mesa</strong><small>El restaurante incluirá el consumo elegible de la mesa.</small></span></label>
            <label><input type="radio" name="scope" checked={mode === 'SELECTED'} disabled={busy} onChange={() => chooseMode('SELECTED')} /><span><strong>Elegir comensales</strong><small>Selecciona a las personas que compartirán esta cuenta.</small></span></label>
            {mode === 'SELECTED' && <fieldset className="check-diners"><legend>Comensales</legend>{diners.map((diner) => {
              const note = diner.active_check_id !== null ? 'El restaurante reporta una cuenta activa'
                : diner.has_active_nonempty_draft ? 'El restaurante reporta un pedido en borrador'
                  : diner.eligible_order_ids.length === 0 ? 'Sin consumo elegible reportado' : eligibleMoney(diner);
              return <label key={diner.diner_session_id}><input type="checkbox" checked={selectedIds.includes(diner.diner_session_id)} disabled={busy || diner.diner_session_id === session?.dinerSessionId} onChange={() => toggleDiner(diner.diner_session_id)} /><span><strong>{diner.display_name}{diner.diner_session_id === session?.dinerSessionId ? ' (tú)' : ''}</strong><small>{note}</small></span></label>;
            })}</fieldset>}
          </section>
          <aside className="check-action-card">
            <p className="panel-kicker">Confirmación</p>
            <h2>Crear una cuenta</h2>
            <p>El total definitivo y la inclusión del consumo los determinará el restaurante.</p>
            {outcome && <div className={`check-outcome check-outcome--${outcome.kind}`} role="alert"><strong>{outcome.kind === 'ambiguous' ? 'Resultado sin confirmar' : 'La cuenta cambió'}</strong><p>{outcome.message}</p>{outcome.kind === 'ambiguous' && <button className="secondary-button" type="button" onClick={() => eligibility.refetch()}>Verificar otra vez</button>}{outcome.kind === 'conflict' && own.has_active_nonempty_draft && <Link to="/order">Revisar pedido</Link>}</div>}
            <button className="primary-button" type="button" disabled={!canCreate || busy} onClick={submit}>{busy ? 'Consultando al restaurante…' : 'Crear cuenta para pagar'}</button>
            {busy ? <span className="check-cancel-link">Espera la respuesta del restaurante</span> : <Link className="check-cancel-link" to="/account">Cancelar y volver</Link>}
          </aside>
        </div>
      </main>
    </div>
  );
}
