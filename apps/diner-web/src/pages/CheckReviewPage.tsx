import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type { PaymentResponse, RestaurantCheckResponse } from '../api/contracts';
import { DinerHeader } from '../components/DinerHeader';
import { PostSettlementExperience } from '../components/PostSettlementExperience';
import { ConektaCardTokenizer, type EphemeralCustomerPaymentSource } from '../components/ConektaCardTokenizer';
import { PaymentContactForm, type PaymentCustomerIdentity } from '../components/PaymentContactForm';
import { useAuth } from '../session/AuthContext';
import { formatPrice, formatQuantity } from '../utils/formatters';

function statusCopy(status: string): { eyebrow: string; title: string; description: string } {
  if (status === 'OPEN') return { eyebrow: 'Cuenta activa', title: 'Cuenta lista para pagar', description: 'El restaurante confirmó el consumo y el saldo de esta cuenta.' };
  if (status === 'FROZEN') return { eyebrow: 'Cuenta confirmada', title: 'Cuenta confirmada', description: 'La composición de esta cuenta está confirmada por el restaurante.' };
  if (status === 'SETTLED') return { eyebrow: 'Cuenta liquidada', title: 'Saldo cubierto', description: 'El restaurante reporta esta cuenta como liquidada.' };
  if (status === 'CANCELLED') return { eyebrow: 'Cuenta cancelada', title: 'Esta cuenta fue cancelada', description: 'Consulta Mi cuenta para conocer el consumo disponible actual.' };
  return { eyebrow: 'Estado del restaurante', title: `Cuenta en estado ${status}`, description: 'Mostramos el estado recibido sin interpretarlo como pago confirmado.' };
}

function scopeCopy(check: RestaurantCheckResponse): string {
  if (check.table_scope_session_ids.length > 0) return 'Toda la mesa';
  if (check.member_ids.length > 1 || check.diner_scope_ids.length > 1) return 'Comensales seleccionados';
  return 'Consumo individual';
}

function isZeroMoney(value: string): boolean {
  return /^[-+]?0+(?:\.0+)?$/.test(value.trim());
}

export function CheckReviewPage() {
  const { checkId } = useParams();
  const parsedId = Number(checkId);
  const navigate = useNavigate();
  const validId = Number.isSafeInteger(parsedId) && parsedId > 0;
  const heading = useRef<HTMLHeadingElement>(null);
  const { session, knownEmail } = useAuth();
  const [paymentSource, setPaymentSource] = useState<EphemeralCustomerPaymentSource | null>(null);
  const [paymentCustomerIdentity, setPaymentCustomerIdentity] = useState<PaymentCustomerIdentity | null>(null);
  const [paymentResult, setPaymentResult] = useState<Pick<PaymentResponse, 'state' | 'amount' | 'currency'> | null>(null);
  const [submittingPayment, setSubmittingPayment] = useState(false);
  const [tokenizerGeneration, setTokenizerGeneration] = useState(0);
  const paymentInFlight = useRef(false);
  const paymentIntentKey = useRef<string | null>(null);
  const checkQuery = useQuery({
    queryKey: ['diner', 'restaurant-check', parsedId],
    queryFn: () => dinerApi.getCheck(parsedId),
    enabled: validId,
    retry: false,
    staleTime: 5_000,
  });
  const checkCurrency = checkQuery.data?.currency ?? '';
  const settlement = useQuery({
    queryKey: ['diner', 'restaurant-check-settlement', parsedId],
    queryFn: () => dinerApi.getCheckSettlement(parsedId),
    enabled: validId && checkQuery.isSuccess,
    retry: false,
  });
  const settlementCanInitiate = ['OPEN', 'FROZEN'].includes(settlement.data?.check_status ?? '')
    && isZeroMoney(settlement.data?.reserved_financial_exposure ?? '')
    && isZeroMoney(settlement.data?.uncertain_exposure ?? '')
    && !isZeroMoney(settlement.data?.available_to_initiate ?? '0');
  const executors = useQuery({
    queryKey: ['diner', 'card-payment-executors', settlement.data?.currency ?? checkCurrency],
    queryFn: () => dinerApi.getCardPaymentExecutors(settlement.data?.currency ?? checkCurrency),
    enabled: settlementCanInitiate,
    retry: false,
  });

  async function submitPayment(executorKey: string) {
    const authoritative = settlement.data;
    if (!authoritative || !session || !paymentCustomerIdentity || !paymentSource || paymentInFlight.current) return;
    paymentInFlight.current = true;
    setSubmittingPayment(true);
    if (!paymentIntentKey.current) paymentIntentKey.current = `diner-payment-${crypto.randomUUID()}`;
    const source = paymentSource.source;
    setPaymentSource(null);
    setTokenizerGeneration((current) => current + 1);
    try {
      const result = await dinerApi.initiateCardPayment(authoritative.check_id, {
        expected_check_version: authoritative.check_version,
        expected_check_fingerprint: authoritative.check_fingerprint,
        amount: authoritative.available_to_initiate,
        currency: authoritative.currency,
        method_category: 'CARD',
        payer_type: 'DINER',
        payer_diner_session_id: session.dinerSessionId,
        selection_mode: 'EXPLICIT',
        executor_key: executorKey,
        customer_payment_source: source,
        payment_customer_identity: paymentCustomerIdentity,
      }, paymentIntentKey.current);
      navigate(`/check/${authoritative.check_id}/payments/${result.id}`);
    } catch (unknownError) {
      if (unknownError instanceof ApiError && unknownError.status === 0) {
        const [latestSettlement] = await Promise.all([
          settlement.refetch(),
          checkQuery.refetch(),
        ]);
        const unresolvedPayments = latestSettlement.data?.payments.filter((payment) => (
          ['RESERVED', 'IN_PROGRESS', 'UNCERTAIN'].includes(payment.state)
        )) ?? [];
        const unresolvedPayment = unresolvedPayments[unresolvedPayments.length - 1];
        if (unresolvedPayment) {
          navigate(`/check/${authoritative.check_id}/payments/${unresolvedPayment.id}`);
          return;
        }
        setPaymentResult({
          state: 'UNCERTAIN',
          amount: authoritative.available_to_initiate,
          currency: authoritative.currency,
        });
      } else if (!(unknownError instanceof ApiError && unknownError.state === 'SESSION_CLOSED')) {
        setPaymentResult({
          state: 'FAILED',
          amount: authoritative.available_to_initiate,
          currency: authoritative.currency,
        });
      }
    } finally {
      paymentInFlight.current = false;
      setSubmittingPayment(false);
    }
  }

  function prepareFreshCard() {
    paymentIntentKey.current = null;
    setPaymentResult(null);
    setPaymentSource(null);
    setTokenizerGeneration((current) => current + 1);
  }

  useEffect(() => {
    document.title = 'Revisar cuenta · Mesa';
    if (checkQuery.data || checkQuery.error || !validId) heading.current?.focus();
  }, [checkQuery.data, checkQuery.error, validId]);

  if (!validId) return <div className="diner-page"><DinerHeader /><main className="product-state"><p className="eyebrow">Cuenta no válida</p><h1 ref={heading} tabIndex={-1}>No pudimos identificar esa cuenta</h1><Link className="primary-button button-link" to="/account">Volver a mi cuenta</Link></main></div>;
  if (checkQuery.isPending) return <div className="diner-page"><DinerHeader /><main className="product-state" aria-busy="true"><p>Cargando cuenta del restaurante…</p></main></div>;
  if (checkQuery.isError) {
    const missing = checkQuery.error instanceof ApiError && checkQuery.error.status === 404;
    return <div className="diner-page"><DinerHeader /><main className="product-state" role="alert"><p className="eyebrow">{missing ? 'Cuenta no encontrada' : 'Consulta no disponible'}</p><h1 ref={heading} tabIndex={-1}>No pudimos mostrar esta cuenta</h1><p>{missing ? 'No tienes acceso a esta cuenta o ya no está disponible.' : 'Ningún dato fue modificado. Puedes volver a consultar.'}</p><div className="product-state-actions">{!missing && <button className="primary-button button-link" type="button" onClick={() => checkQuery.refetch()}>Reintentar</button>}<Link className="secondary-button button-link" to="/account">Volver a mi cuenta</Link></div></main></div>;
  }

  const check = checkQuery.data;
  const hasUncertainPayment = !isZeroMoney(check.uncertain_exposure);
  const unresolvedPayments = settlement.data?.payments.filter((payment) => (
    ['RESERVED', 'IN_PROGRESS', 'UNCERTAIN'].includes(payment.state)
  )) ?? [];
  const unresolvedPayment = unresolvedPayments[unresolvedPayments.length - 1];
  const showPaymentSection = ['OPEN', 'FROZEN'].includes(check.status)
    && (!isZeroMoney(check.outstanding) || hasUncertainPayment || unresolvedPayment !== undefined);
  const financiallyComplete = settlement.data?.check_status === 'SETTLED'
    && check.status === 'SETTLED'
    && isZeroMoney(check.outstanding)
    && isZeroMoney(settlement.data.reserved_financial_exposure)
    && isZeroMoney(settlement.data.uncertain_exposure);
  const status = hasUncertainPayment
    ? { eyebrow: 'Cuenta activa · Pago sin confirmar', title: 'Pago pendiente de confirmación', description: 'El restaurante aún verifica una operación. No vuelvas a pagar por el momento.' }
    : statusCopy(check.status);
  return (
    <div className="diner-page">
      <DinerHeader />
      <main className="check-main">
        <header className="check-review-hero">
          <div><p className="eyebrow">{status.eyebrow}</p><h1 ref={heading} tabIndex={-1}>{status.title}</h1><p>{status.description}</p></div>
          <button className="secondary-button" type="button" disabled={checkQuery.isFetching} onClick={() => checkQuery.refetch()}>{checkQuery.isFetching ? 'Actualizando…' : 'Actualizar'}</button>
        </header>
        <p className="check-scope-summary"><strong>Estado:</strong> {statusCopy(check.status).eyebrow} · <strong>Alcance:</strong> {scopeCopy(check)}</p>
        <div className="check-review-layout">
          <section className="check-details" aria-labelledby="check-details-title">
            <h2 id="check-details-title">Consumo incluido</h2>
            {check.details?.length ? check.details.map((resource) => resource.diners.map((diner) => (
              <article key={`${resource.service_session_id}-${diner.diner_session_id}`}>
                <h3>{diner.display_name}</h3>
                {diner.orders.map((order) => <div className="check-order" key={order.order_id}><ul>{order.items.map((item) => <li key={item.item_id}><span>{formatQuantity(item.quantity)} × {item.product_name}</span><strong>{formatPrice(item.commercial_amount, check.currency)}</strong></li>)}</ul><p><span>Consumo aceptado del pedido</span><strong>{formatPrice(order.accepted_payable_amount, check.currency)}</strong></p></div>)}
              </article>
            ))) : <p>El restaurante no proporcionó el desglose en esta consulta.</p>}
          </section>
          <aside className="check-financial" aria-labelledby="check-financial-title">
            <p className="panel-kicker">Resumen autoritativo</p>
            <h2 id="check-financial-title">Saldo de la cuenta</h2>
            <dl>
              <div><dt>Consumo</dt><dd>{formatPrice(check.consumption_total, check.currency)}</dd></div>
              <div><dt>Propina</dt><dd>{formatPrice(check.gratuity_total, check.currency)}</dd></div>
              <div><dt>Responsabilidad total</dt><dd>{formatPrice(check.liability_total, check.currency)}</dd></div>
              <div><dt>Pago confirmado</dt><dd>{formatPrice(check.confirmed_settlement, check.currency)}</dd></div>
              {hasUncertainPayment && <div className="check-uncertain"><dt>Pago pendiente de confirmación</dt><dd>{formatPrice(check.uncertain_exposure, check.currency)}</dd></div>}
              <div className="check-outstanding"><dt>Saldo pendiente</dt><dd>{formatPrice(check.outstanding, check.currency)}</dd></div>
            </dl>
            {hasUncertainPayment && <p className="check-financial-note">Este importe no se presenta como pagado hasta que el restaurante lo confirme.</p>}
            {check.status === 'OPEN' && !hasUncertainPayment && <p className="check-financial-note">La opción de pago se habilitará en un siguiente paso.</p>}
            {check.signal === 'SERVICE_CONTINUATION_DECISION_REQUIRED' && <p className="check-financial-note">El restaurante indica que después deberá decidirse si el servicio continúa.</p>}
          </aside>
        </div>
        {showPaymentSection && (
          <div className="check-payment-section">
            {settlement.isPending ? (
              <section className="conekta-tokenizer" aria-busy="true"><h2>Consultando pagos</h2><p role="status">Verificando el estado financiero del restaurante…</p></section>
            ) : settlement.isError ? (
              <section className="conekta-tokenizer" role="alert"><h2>Estado de pago no disponible</h2><p>No fue posible confirmar el estado financiero. No inicies otro pago.</p><button className="secondary-button" type="button" onClick={() => settlement.refetch()}>Reintentar</button></section>
            ) : unresolvedPayment ? (
              <section className="payment-result payment-result--uncertain" role="alert"><h2>Hay un pago pendiente de confirmación</h2><p>No inicies otro pago. Consulta el intento existente para conocer su estado autoritativo.</p><Link className="primary-button button-link" to={`/check/${check.id}/payments/${unresolvedPayment.id}`}>Consultar pago</Link></section>
            ) : paymentResult ? (
              <section className={`payment-result payment-result--${paymentResult.state.toLowerCase()}`} role="status" aria-live="polite">
                {paymentResult.state === 'SUCCEEDED' ? <><h2>Pago registrado correctamente</h2><p>El restaurante confirmó el registro inicial de este pago.</p></>
                  : paymentResult.state === 'REJECTED' ? <><h2>Pago no aprobado</h2><p>La tarjeta no fue aprobada. No se registró como pago confirmado.</p><button className="secondary-button" type="button" onClick={prepareFreshCard}>Intentar con otra tarjeta</button></>
                    : paymentResult.state === 'FAILED' ? <><h2>No se pudo procesar el pago</h2><p>El intento terminó sin aprobación. Puedes preparar una tarjeta nueva.</p><button className="secondary-button" type="button" onClick={prepareFreshCard}>Intentar con otra tarjeta</button></>
                      : paymentResult.state === 'UNCERTAIN' ? <><h2>Estamos confirmando el resultado de tu pago</h2><p>No intentes realizar otro pago por ahora.</p></>
                        : <><h2>Pago en proceso</h2><p>El restaurante todavía procesa este pago. No inicies otro intento.</p></>}
              </section>
            ) : submittingPayment ? (
              <section className="payment-result" role="status" aria-busy="true"><h2>Procesando pago</h2><p>Espera la respuesta autoritativa del restaurante. No inicies otro intento.</p></section>
            ) : !settlementCanInitiate ? (
              <section className="payment-result payment-result--uncertain" role="status"><h2>Pago no disponible</h2><p>El estado financiero actual no permite iniciar otro pago.</p></section>
            ) : executors.isPending ? (
              <section className="conekta-tokenizer" aria-busy="true"><h2>Pago seguro con tarjeta</h2><p role="status">Consultando opciones de tarjeta…</p></section>
            ) : executors.isError || !executors.data[0] ? (
              <section className="conekta-tokenizer" role="alert"><h2>Pago con tarjeta no disponible</h2><p>No fue posible cargar el pago con tarjeta. Ningún pago fue realizado.</p><button className="secondary-button" type="button" onClick={() => executors.refetch()}>Reintentar</button></section>
            ) : (
              <>
                <PaymentContactForm
                  initialName={session?.displayName ?? ''}
                  initialEmail={knownEmail ?? ''}
                  onReady={setPaymentCustomerIdentity}
                  onEdit={() => { setPaymentCustomerIdentity(null); setPaymentSource(null); paymentIntentKey.current = null; }}
                />
                {paymentCustomerIdentity && (
                  <ConektaCardTokenizer
                    key={tokenizerGeneration}
                    executorKey={executors.data[0].executor_key}
                    currency={settlement.data.currency}
                    onSourceReady={(source) => { paymentIntentKey.current = null; setPaymentSource(source); }}
                  />
                )}
                {paymentCustomerIdentity && paymentSource && (
                  <section className="payment-confirmation" aria-labelledby="payment-confirmation-title">
                    <p className="panel-kicker">Confirmación de pago</p>
                    <h2 id="payment-confirmation-title">Información de tarjeta preparada</h2>
                    <p>Se solicitará al restaurante cobrar {formatPrice(settlement.data.available_to_initiate, settlement.data.currency)}.</p>
                    <button className="primary-button" type="button" disabled={submittingPayment} onClick={() => submitPayment(executors.data[0].executor_key)}>
                      {submittingPayment ? 'Procesando pago…' : 'Pagar ahora'}
                    </button>
                  </section>
                )}
              </>
            )}
          </div>
        )}
        {financiallyComplete && <PostSettlementExperience check={check} />}
      </main>
    </div>
  );
}
