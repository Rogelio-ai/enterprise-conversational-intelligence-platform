import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, staffApi } from '../api/client';
import type { CashCount, RestaurantCheckSummary } from '../api/contracts';
import { useStaffContext } from '../context/StaffContext';
import { useAuth } from '../session/AuthContext';
import { BillingPrintPanel } from '../components/BillingPrintPanel';

type Feedback = { kind: 'success' | 'warning' | 'error'; message: string };

const money = (value: string | null | undefined, currency = 'MXN') => {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed)
    ? new Intl.NumberFormat('es-MX', { style: 'currency', currency }).format(parsed)
    : value ?? '—';
};

const errorText = (error: unknown) => {
  if (error instanceof ApiError) {
    if (error.status === 403 || error.status === 404) return 'La operación ya no está autorizada para esta ubicación.';
    if (error.kind === 'network') return 'No hubo confirmación del servidor. Actualizamos la verdad financiera antes de permitir otra acción.';
    return error.message;
  }
  return 'No fue posible completar la operación.';
};

export function CashierPage() {
  const { location } = useStaffContext();
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [registerId, setRegisterId] = useState<number | null>(null);
  const [checkId, setCheckId] = useState<number | null>(null);
  const [paymentAmount, setPaymentAmount] = useState('');
  const [tender, setTender] = useState('');
  const [movementType, setMovementType] = useState('OPENING_FLOAT');
  const [movementAmount, setMovementAmount] = useState('');
  const [movementReason, setMovementReason] = useState('');
  const [countAmount, setCountAmount] = useState('');
  const [count, setCount] = useState<CashCount | null>(null);
  const [varianceReason, setVarianceReason] = useState('');
  const [confirmClose, setConfirmClose] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [paymentReconciliationRequired, setPaymentReconciliationRequired] = useState(false);
  const paymentSubmitting = useRef(false);

  const registers = useQuery({
    queryKey: ['staff', 'cashier', 'registers', location?.id],
    queryFn: () => staffApi.cashRegisters(location!.id), enabled: Boolean(location), retry: false,
  });
  useEffect(() => {
    const values = registers.data?.items ?? [];
    if (!values.some((item) => item.id === registerId)) setRegisterId(values[0]?.id ?? null);
  }, [registerId, registers.data]);

  const session = useQuery({
    queryKey: ['staff', 'cashier', 'session', location?.id, registerId],
    queryFn: () => staffApi.activeCashSession(location!.id, registerId!),
    enabled: Boolean(location && registerId), retry: false, refetchInterval: 15_000,
  });
  const checks = useQuery({
    queryKey: ['staff', 'cashier', 'checks', location?.id],
    queryFn: () => staffApi.restaurantChecks(location!.id), enabled: Boolean(location), retry: false,
    refetchInterval: 15_000,
  });
  useEffect(() => {
    const values = checks.data?.items ?? [];
    if (!values.some((item) => item.id === checkId)) setCheckId(values[0]?.id ?? null);
  }, [checkId, checks.data]);
  const selected = checks.data?.items.find((item) => item.id === checkId) ?? null;
  useEffect(() => { if (selected) setPaymentAmount(selected.available_to_initiate); }, [selected?.id, selected?.available_to_initiate]);
  const detail = useQuery({
    queryKey: ['staff', 'cashier', 'check', location?.id, checkId],
    queryFn: () => staffApi.restaurantCheck(location!.id, checkId!), enabled: Boolean(location && checkId), retry: false,
  });
  const settlement = useQuery({
    queryKey: ['staff', 'cashier', 'settlement', location?.id, checkId],
    queryFn: () => staffApi.settlement(location!.id, checkId!), enabled: Boolean(location && checkId), retry: false,
  });
  const movements = useQuery({
    queryKey: ['staff', 'cashier', 'movements', location?.id, session.data?.id],
    queryFn: () => staffApi.cashMovements(location!.id, session.data!.id),
    enabled: Boolean(location && session.data), retry: false,
  });
  const assistance = useQuery({
    queryKey: ['staff', 'cashier', 'assistance', location?.id],
    queryFn: () => staffApi.operationalRequests(location!.id, { status: 'PENDING', requestType: 'CASH_PAYMENT_ASSISTANCE' }),
    enabled: Boolean(location && hasPermission('operational_request.read')), retry: false,
  });

  const reconcile = async () => {
    const financialQueries: Array<Promise<{ isSuccess: boolean }>> = [checks.refetch()];
    if (checkId) financialQueries.push(detail.refetch(), settlement.refetch());
    const operationalQueries: Array<Promise<{ isSuccess: boolean }>> = [session.refetch()];
    if (session.data) operationalQueries.push(movements.refetch());
    const [financialResults] = await Promise.all([
      Promise.all(financialQueries), Promise.all(operationalQueries),
    ]);
    const financialTruthConfirmed = financialResults.every((result) => result.isSuccess);
    if (financialTruthConfirmed) setPaymentReconciliationRequired(false);
    return financialTruthConfirmed;
  };
  const open = useMutation({
    mutationFn: () => staffApi.openCashSession(location!.id, registerId!, 'MXN', `cashier-open-${crypto.randomUUID()}`),
    onSuccess: async () => { setFeedback({ kind: 'success', message: 'Caja abierta y confirmada por el servidor.' }); await session.refetch(); },
    onError: async (error) => { setFeedback({ kind: 'error', message: errorText(error) }); await session.refetch(); },
  });
  const movement = useMutation({
    mutationFn: () => staffApi.createCashMovement(location!.id, session.data!.id, {
      movement_type: movementType, amount: movementAmount, currency: session.data!.currency,
      reason: movementReason || undefined, reference: 'cashier-workspace',
    }, `cashier-movement-${crypto.randomUUID()}`),
    onSuccess: async () => { setMovementAmount(''); setMovementReason(''); setFeedback({ kind: 'success', message: 'Movimiento registrado y auditado.' }); await reconcile(); },
    onError: async (error) => { setFeedback({ kind: 'error', message: errorText(error) }); await reconcile(); },
  });
  const payment = useMutation({
    mutationFn: () => staffApi.createCashPayment(location!.id, selected!.id, {
      expected_check_version: selected!.version, expected_check_fingerprint: selected!.fingerprint,
      amount: paymentAmount, currency: selected!.currency, cash_session_id: session.data!.id,
      cash_tendered_amount: tender,
    }, `cashier-payment-${crypto.randomUUID()}`),
    onSuccess: async (result) => {
      setFeedback({ kind: 'success', message: `Pago confirmado. Cambio autorizado: ${money(result.cash_change_due, result.currency)}.` });
      setTender(''); await reconcile();
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.kind === 'network') {
        setPaymentReconciliationRequired(true);
      }
      setFeedback({ kind: error instanceof ApiError && error.kind === 'network' ? 'warning' : 'error', message: errorText(error) });
      await reconcile();
    },
    onSettled: () => { paymentSubmitting.current = false; },
  });
  const captureCount = useMutation({
    mutationFn: () => staffApi.createCashCount(location!.id, session.data!.id, countAmount, session.data!.currency, `cashier-count-${crypto.randomUUID()}`),
    onSuccess: async (result) => { setCount(result); setFeedback({ kind: 'success', message: 'Conteo físico capturado. El backend validará saldo y diferencia al cerrar.' }); await session.refetch(); },
    onError: async (error) => { setFeedback({ kind: 'error', message: errorText(error) }); await session.refetch(); },
  });
  const close = useMutation({
    mutationFn: () => staffApi.closeCashSession(location!.id, session.data!.id, count!.id, varianceReason || undefined, `cashier-close-${crypto.randomUUID()}`),
    onSuccess: async (result) => {
      setFeedback({ kind: 'success', message: `Caja cerrada. Diferencia confirmada: ${money(result.frozen_variance, result.currency)}.` });
      setCount(null); setConfirmClose(false); await reconcile();
    },
    onError: async (error) => {
      setCount(null); setConfirmClose(false);
      setFeedback({ kind: 'error', message: errorText(error) }); await reconcile();
    },
  });
  const recover = useMutation({
    mutationFn: (paymentId: number) => staffApi.recoverPayment(location!.id, paymentId),
    onSuccess: async () => { setFeedback({ kind: 'success', message: 'Recuperación ejecutada; mostramos el estado confirmado.' }); await reconcile(); },
    onError: async (error) => { setFeedback({ kind: 'error', message: errorText(error) }); await reconcile(); },
  });

  const submitPayment = () => {
    if (paymentSubmitting.current) return;
    paymentSubmitting.current = true; setFeedback(null); payment.mutate();
  };
  const hasUncertainExposure = Boolean(selected && Number(selected.uncertain_exposure) !== 0);
  const canPay = Boolean(session.data && selected && Number(selected.available_to_initiate) > 0
    && !hasUncertainExposure && !paymentReconciliationRequired
    && hasPermission('restaurant_payment.manage'));

  return (
    <section className="cashier-page" aria-labelledby="cashier-heading">
      <header className="cashier-heading"><div><p className="eyebrow">Operación financiera</p><h1 id="cashier-heading">Caja</h1><p>{location?.name}. Cada cifra y estado proviene del backend.</p></div><button className="secondary-button" type="button" onClick={() => void reconcile()}>Actualizar verdad</button></header>
      {feedback ? <div className={`cashier-feedback cashier-feedback--${feedback.kind}`} role={feedback.kind === 'success' ? 'status' : 'alert'}>{feedback.message}</div> : null}

      <div className="cashier-layout">
        <aside className="cashier-rail">
          <section className="cashier-panel"><p className="eyebrow">01 · Caja física</p><h2>{session.data ? 'Caja abierta' : 'Caja cerrada'}</h2>
            <label><span>Registradora</span><select aria-label="Registradora" value={registerId ?? ''} onChange={(event) => setRegisterId(Number(event.target.value))}>{(registers.data?.items ?? []).map((item) => <option value={item.id} key={item.id}>{item.name} · {item.code}</option>)}</select></label>
            {registers.isError ? <p role="alert">{errorText(registers.error)}</p> : null}
            {!registers.isPending && registers.data?.items.length === 0 ? <p>No hay registradoras autorizadas en esta ubicación.</p> : null}
            {session.data ? <dl className="cashier-session"><div><dt>Sesión</dt><dd>#{session.data.id}</dd></div><div><dt>Efectivo esperado</dt><dd>{money(session.data.expected_cash, session.data.currency)}</dd></div><div><dt>Versión</dt><dd>{session.data.movement_version}</dd></div></dl> : registerId && hasPermission('cash_session.manage') ? <button className="primary-button" type="button" disabled={open.isPending} onClick={() => open.mutate()}>{open.isPending ? 'Abriendo…' : 'Abrir caja'}</button> : null}
          </section>
          <section className="cashier-panel"><p className="eyebrow">Contexto</p><h2>Solicitudes de efectivo</h2><strong className="cashier-big-number">{assistance.data?.items.length ?? 0}</strong><p>Son contexto operativo; no crean pagos ni liquidaciones.</p></section>
        </aside>

        <main className="cashier-main">
          <section className="cashier-panel"><div className="cashier-panel-heading"><div><p className="eyebrow">02 · Cuenta</p><h2>Cuenta a cobrar</h2></div><select aria-label="Cuenta" value={checkId ?? ''} onChange={(event) => setCheckId(Number(event.target.value))}>{(checks.data?.items ?? []).map((item) => <option value={item.id} key={item.id}>Cuenta #{item.id} · {money(item.outstanding, item.currency)}</option>)}</select></div>
            {selected ? <><div className="financial-grid"><Metric label="Responsabilidad" value={selected.liability_total} currency={selected.currency} /><Metric label="Confirmado" value={selected.confirmed_settlement} currency={selected.currency} tone="success" /><Metric label="Reservado / proceso" value={selected.reserved_financial_exposure} currency={selected.currency} /><Metric label="Incierto" value={selected.uncertain_exposure} currency={selected.currency} tone="warning" /><Metric label="Pendiente" value={selected.outstanding} currency={selected.currency} /><Metric label="Disponible para iniciar" value={selected.available_to_initiate} currency={selected.currency} /></div>
              {hasUncertainExposure ? <div className="uncertain-alert" role="alert"><strong>Exposición incierta</strong><span>No cobres de nuevo. Recupera o reconcilia el pago existente.</span></div> : null}
              {paymentReconciliationRequired ? <div className="uncertain-alert" role="alert"><strong>Confirmación pendiente</strong><span>El cobro permanece bloqueado hasta reconstruir la verdad financiera desde el servidor.</span></div> : null}
              <p className="cashier-detail-note">Detalle backend: {detail.data ? `${detail.data.resource_ids.length} recurso(s) · estado ${detail.data.status}` : 'consultando…'}</p></> : <p>No hay cuentas disponibles para esta ubicación.</p>}
          </section>

          {selected && session.data ? <section className="cashier-panel"><p className="eyebrow">03 · Cobro</p><h2>Recibir efectivo</h2><div className="cash-form"><label><span>Monto a aplicar</span><input aria-label="Monto a aplicar" inputMode="decimal" value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} /></label><label><span>Efectivo recibido</span><input aria-label="Efectivo recibido" inputMode="decimal" value={tender} onChange={(event) => setTender(event.target.value)} /></label><button className="primary-button" type="button" disabled={!canPay || !tender || payment.isPending} onClick={submitPayment}>{payment.isPending ? 'Confirmando…' : 'Confirmar pago en efectivo'}</button></div><p>El cambio se muestra únicamente después de la respuesta autoritativa.</p></section> : null}

          {settlement.data ? <section className="cashier-panel"><p className="eyebrow">04 · Pagos</p><h2>Liquidación y excepciones</h2>{settlement.data.check_status === 'SETTLED' ? <div className="settled-banner">✓ Cuenta liquidada</div> : <p>La cuenta conserva saldo o exposición pendiente según el backend.</p>}<div className="payment-list">{settlement.data.payments.map((item) => <article className={`payment-row payment-row--${item.state.toLowerCase()}`} key={item.id}><div><strong>{item.method_category} · {money(item.amount, item.currency)}</strong><span>Pago #{item.id} · {item.instrument_display ?? 'Efectivo'}</span></div><b>{item.state}</b>{item.state === 'UNCERTAIN' && hasPermission('restaurant_payment.recover') ? <button className="secondary-button" type="button" disabled={recover.isPending} onClick={() => recover.mutate(item.id)}>Recuperar estado</button> : null}</article>)}</div></section> : null}

          {session.data ? <section className="cashier-panel"><p className="eyebrow">05 · Control de efectivo</p><h2>Movimientos y cierre</h2><div className="cash-controls"><form onSubmit={(event) => { event.preventDefault(); movement.mutate(); }}><h3>Registrar movimiento</h3><label><span>Tipo</span><select value={movementType} onChange={(event) => setMovementType(event.target.value)}><option value="OPENING_FLOAT">Fondo inicial</option><option value="CASH_IN">Entrada</option><option value="CASH_OUT">Salida</option><option value="WITHDRAWAL">Retiro</option><option value="ADJUSTMENT">Ajuste</option></select></label><label><span>Monto con signo</span><input aria-label="Monto del movimiento" value={movementAmount} onChange={(event) => setMovementAmount(event.target.value)} /></label><label><span>Motivo</span><input value={movementReason} onChange={(event) => setMovementReason(event.target.value)} /></label><button className="secondary-button" disabled={!movementAmount || movement.isPending}>Registrar movimiento</button></form>
            <form onSubmit={(event) => { event.preventDefault(); captureCount.mutate(); }}><h3>Conteo y cierre</h3><dl><div><dt>Esperado por sistema</dt><dd>{money(session.data.expected_cash, session.data.currency)}</dd></div><div><dt>Conteo físico</dt><dd>{count ? money(count.counted_amount, count.currency) : 'Pendiente'}</dd></div><div><dt>Diferencia</dt><dd>{session.data.frozen_variance === null ? 'La valida el backend al cerrar' : money(session.data.frozen_variance, session.data.currency)}</dd></div></dl><label><span>Efectivo contado</span><input aria-label="Efectivo contado" value={countAmount} onChange={(event) => setCountAmount(event.target.value)} /></label><button className="secondary-button" disabled={!countAmount || captureCount.isPending}>Capturar conteo</button>{count ? <><label><span>Motivo de diferencia</span><input value={varianceReason} onChange={(event) => setVarianceReason(event.target.value)} /></label><label className="commit-check"><input type="checkbox" checked={confirmClose} onChange={(event) => setConfirmClose(event.target.checked)} /> Confirmo que revisé caja, conteo y diferencia.</label><button className="danger-button" type="button" disabled={!confirmClose || close.isPending} onClick={() => close.mutate()}>{close.isPending ? 'Cerrando…' : 'Cerrar caja'}</button></> : null}</form></div>
            <div className="movement-list"><h3>Movimientos confirmados</h3>{(movements.data ?? []).map((item) => <div key={item.id}><span>{item.movement_type}<small>{item.reason || 'Sin nota'} · #{item.id}</small></span><strong>{money(item.amount, item.currency)}</strong></div>)}</div></section> : null}
          {selected && location && hasPermission('restaurant_check.manage') ? <BillingPrintPanel locationId={location.id} check={selected} settlement={settlement.data} registerId={registerId} /> : null}
        </main>
      </div>
    </section>
  );
}

function Metric({ label, value, currency, tone }: { label: string; value: string; currency: string; tone?: string }) {
  return <div className={tone ? `financial-metric financial-metric--${tone}` : 'financial-metric'}><span>{label}</span><strong>{money(value, currency)}</strong></div>;
}
