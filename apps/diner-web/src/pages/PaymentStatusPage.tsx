import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type { DinerPaymentResponse } from '../api/contracts';
import { DinerHeader } from '../components/DinerHeader';
import { formatPrice } from '../utils/formatters';

function isZeroMoney(value: string): boolean {
  return /^[-+]?0+(?:\.0+)?$/.test(value.trim());
}

function paymentCopy(payment: DinerPaymentResponse) {
  if (payment.state === 'RESERVED') return {
    eyebrow: 'Pago registrado', title: 'Pago reservado',
    description: 'El restaurante registró el intento, pero todavía no confirma su ejecución.',
    tone: 'pending',
  };
  if (payment.state === 'IN_PROGRESS') return {
    eyebrow: 'Pago en proceso', title: 'Estamos procesando tu pago',
    description: 'No realices otro pago mientras el restaurante termina este intento.',
    tone: 'pending',
  };
  if (payment.state === 'SUCCEEDED') return {
    eyebrow: 'Pago confirmado', title: 'Pago registrado',
    description: 'El restaurante confirmó este pago. Abajo puedes consultar el estado de la cuenta.',
    tone: 'success',
  };
  if (payment.state === 'REJECTED') return {
    eyebrow: 'Pago no aprobado', title: 'El pago no fue aprobado',
    description: 'Este intento no fue registrado como pago confirmado.',
    tone: 'failure',
  };
  if (payment.state === 'FAILED') return {
    eyebrow: 'Pago no completado', title: 'No se pudo completar el pago',
    description: 'El intento terminó sin confirmación de pago.',
    tone: 'failure',
  };
  if (payment.state === 'UNCERTAIN') return {
    eyebrow: 'Resultado pendiente', title: 'Estamos confirmando el resultado de tu pago',
    description: 'No intentes realizar otro pago mientras verificamos el resultado.',
    tone: 'uncertain',
  };
  if (payment.state === 'CANCELLED') return {
    eyebrow: 'Pago cancelado', title: 'Este intento ya no está activo',
    description: 'El restaurante informa que este intento de pago fue cancelado.',
    tone: 'failure',
  };
  return {
    eyebrow: 'Estado del pago', title: 'Consultando el resultado',
    description: 'Mostramos únicamente el estado confirmado por el restaurante.',
    tone: 'pending',
  };
}

export function PaymentStatusPage() {
  const { checkId, paymentId } = useParams();
  const parsedCheckId = Number(checkId);
  const parsedPaymentId = Number(paymentId);
  const validIds = Number.isSafeInteger(parsedCheckId) && parsedCheckId > 0
    && Number.isSafeInteger(parsedPaymentId) && parsedPaymentId > 0;
  const heading = useRef<HTMLHeadingElement>(null);
  const queryClient = useQueryClient();
  const paymentKey = ['diner', 'payment', parsedCheckId, parsedPaymentId] as const;
  const settlementKey = ['diner', 'restaurant-check-settlement', parsedCheckId] as const;
  const checkKey = ['diner', 'restaurant-check', parsedCheckId] as const;
  const payment = useQuery({
    queryKey: paymentKey,
    queryFn: () => dinerApi.getPayment(parsedCheckId, parsedPaymentId),
    enabled: validIds,
    retry: false,
  });
  const settlement = useQuery({
    queryKey: settlementKey,
    queryFn: () => dinerApi.getCheckSettlement(parsedCheckId),
    enabled: validIds,
    retry: false,
  });
  const check = useQuery({
    queryKey: checkKey,
    queryFn: () => dinerApi.getCheck(parsedCheckId),
    enabled: validIds,
    retry: false,
  });
  const recovery = useMutation({
    mutationFn: () => dinerApi.recoverPayment(parsedCheckId, parsedPaymentId),
    retry: false,
    onSuccess: (result) => {
      queryClient.setQueryData(paymentKey, result);
    },
    onSettled: async (_data, error) => {
      if (error instanceof ApiError && error.state === 'SESSION_CLOSED') return;
      await Promise.all([
        queryClient.refetchQueries({ queryKey: paymentKey, exact: true }),
        queryClient.refetchQueries({ queryKey: settlementKey, exact: true }),
        queryClient.refetchQueries({ queryKey: checkKey, exact: true }),
      ]);
    },
  });

  useEffect(() => {
    document.title = 'Estado del pago · Mesa';
    if (!validIds || payment.data || payment.error) heading.current?.focus();
  }, [validIds, payment.data, payment.error]);

  async function refreshStatus() {
    await Promise.all([payment.refetch(), settlement.refetch(), check.refetch()]);
  }

  if (!validIds) return <div className="diner-page"><DinerHeader /><main className="product-state"><p className="eyebrow">Pago no válido</p><h1 ref={heading} tabIndex={-1}>No pudimos identificar este pago</h1><Link className="primary-button button-link" to="/account">Volver a mi cuenta</Link></main></div>;
  if (payment.isPending || settlement.isPending || check.isPending) return <div className="diner-page"><DinerHeader /><main className="product-state" aria-busy="true"><p>Consultando el estado financiero…</p></main></div>;
  if (payment.isError || settlement.isError || check.isError) {
    const errors = [payment.error, settlement.error, check.error];
    const missing = errors.some((error) => error instanceof ApiError && error.status === 404);
    return <div className="diner-page"><DinerHeader /><main className="product-state" role="alert"><p className="eyebrow">{missing ? 'Pago no encontrado' : 'Consulta interrumpida'}</p><h1 ref={heading} tabIndex={-1}>No pudimos mostrar el estado del pago</h1><p>{missing ? 'No tienes acceso a este pago o ya no está disponible.' : 'Ningún dato financiero fue modificado.'}</p>{!missing && <button className="primary-button" type="button" onClick={refreshStatus}>Reintentar consulta</button>}</main></div>;
  }

  const currentPayment = payment.data;
  const currentSettlement = settlement.data;
  const currentCheck = check.data;
  const copy = paymentCopy(currentPayment);
  const unresolved = !isZeroMoney(currentSettlement.reserved_financial_exposure)
    || !isZeroMoney(currentSettlement.uncertain_exposure);
  const financiallyComplete = currentSettlement.check_status === 'SETTLED'
    && isZeroMoney(currentCheck.outstanding)
    && !unresolved;
  const mayStartAnotherPayment = ['SUCCEEDED', 'REJECTED', 'FAILED', 'CANCELLED'].includes(currentPayment.state)
    && ['OPEN', 'FROZEN'].includes(currentSettlement.check_status)
    && !unresolved
    && !isZeroMoney(currentSettlement.available_to_initiate);
  const busy = payment.isFetching || settlement.isFetching || check.isFetching || recovery.isPending;

  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="payment-status-main">
        <section className={`payment-status-card payment-status-card--${copy.tone}`} aria-labelledby="payment-status-title" role={currentPayment.state === 'UNCERTAIN' || copy.tone === 'failure' ? 'alert' : 'status'}>
          <p className="eyebrow">{copy.eyebrow}</p>
          <h1 id="payment-status-title" ref={heading} tabIndex={-1}>{copy.title}</h1>
          <p>{copy.description}</p>
          <dl className="payment-status-summary">
            <div><dt>Importe de este pago</dt><dd>{formatPrice(currentPayment.amount, currentPayment.currency)}</dd></div>
            <div><dt>Método</dt><dd>{currentPayment.method_category === 'CARD' ? 'Tarjeta' : currentPayment.method_category}</dd></div>
            {currentPayment.instrument_display && <div><dt>Instrumento</dt><dd>{currentPayment.instrument_display}</dd></div>}
          </dl>
          <div className="payment-status-actions">
            {currentPayment.state === 'UNCERTAIN' && <button className="primary-button" type="button" disabled={busy} onClick={() => recovery.mutate()}>{recovery.isPending ? 'Consultando estado…' : 'Consultar estado'}</button>}
            <button className="secondary-button" type="button" disabled={busy} onClick={refreshStatus}>{busy && !recovery.isPending ? 'Actualizando…' : 'Actualizar'}</button>
          </div>
          {recovery.isError && <p className="payment-status-feedback" role="alert">Aún no podemos confirmar el resultado. No realices otro pago por ahora.</p>}
        </section>

        <section className="payment-status-card" aria-labelledby="account-status-title">
          <p className="panel-kicker">Estado de la cuenta</p>
          <h2 id="account-status-title">{financiallyComplete ? 'Tu cuenta quedó liquidada' : 'Resumen financiero'}</h2>
          {currentPayment.state === 'SUCCEEDED' && !financiallyComplete && <p>Este pago fue registrado, pero la cuenta aún conserva saldo pendiente.</p>}
          {unresolved && <p className="payment-status-warning" role="alert">Existe un pago pendiente de confirmación. No realices otro pago por ahora.</p>}
          <dl className="payment-status-summary">
            <div><dt>Pago confirmado en la cuenta</dt><dd>{formatPrice(currentSettlement.confirmed_settlement, currentSettlement.currency)}</dd></div>
            {!isZeroMoney(currentSettlement.reserved_financial_exposure) && <div><dt>Importe reservado o en proceso</dt><dd>{formatPrice(currentSettlement.reserved_financial_exposure, currentSettlement.currency)}</dd></div>}
            {!isZeroMoney(currentSettlement.uncertain_exposure) && <div><dt>Importe pendiente de confirmación</dt><dd>{formatPrice(currentSettlement.uncertain_exposure, currentSettlement.currency)}</dd></div>}
            <div><dt>Saldo pendiente</dt><dd>{formatPrice(currentCheck.outstanding, currentCheck.currency)}</dd></div>
            <div><dt>Disponible para un pago intencional</dt><dd>{formatPrice(currentSettlement.available_to_initiate, currentSettlement.currency)}</dd></div>
          </dl>
          {financiallyComplete && <p role="status">El restaurante confirmó que no queda saldo pendiente ni exposición financiera sin resolver.</p>}
          {mayStartAnotherPayment && <Link className="primary-button button-link" to={`/check/${parsedCheckId}`}>Volver a opciones de pago</Link>}
        </section>
      </main>
    </div>
  );
}
