import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, dinerApi } from '../api/client';
import type {
  ConversationActionRequest,
  ConversationActionResponse,
  RestaurantIntentCode,
} from '../api/contracts';
import { DinerHeader } from '../components/DinerHeader';
import { useAuth } from '../session/AuthContext';
import { formatPrice, formatQuantity } from '../utils/formatters';

interface Submission {
  text: string;
  key: string;
  values?: Omit<ConversationActionRequest, 'modality' | 'content_text'>;
}

interface ConversationEntry {
  id: string;
  role: 'DINER' | 'DIGITAL_WAITER';
  text: string;
  response?: ConversationActionResponse;
}

interface UnknownRecord {
  [key: string]: unknown;
}

const quickStarts = [
  'Quiero ver el menú',
  'Quiero ver mi pedido',
  'Quiero ver mi cuenta',
  'Necesito ayuda',
] as const;

function record(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as UnknownRecord
    : null;
}

function positiveNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? value : null;
}

function textValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function responseContext(response: ConversationActionResponse): {
  checkId: number | null;
  checkVersion: number | null;
  paymentId: number | null;
  productId: number | null;
} {
  const data = record(response.authoritative_data);
  const product = record(data?.product);
  const items = Array.isArray(data?.items) ? data.items : [];
  const firstItem = record(items[0]);
  return {
    checkId: positiveNumber(response.pending_context.check_id)
      ?? positiveNumber(data?.check_id)
      ?? positiveNumber(data?.id),
    checkVersion: positiveNumber(response.pending_context.check_version)
      ?? positiveNumber(data?.version),
    paymentId: positiveNumber(response.pending_context.payment_id),
    productId: positiveNumber(product?.id) ?? positiveNumber(firstItem?.product_id),
  };
}

function actionTarget(action: string, response: ConversationActionResponse): string | null {
  const { checkId, paymentId, productId } = responseContext(response);
  if (action === 'SHOW_MENU' || action === 'BROWSE_MENU') return '/menu';
  if (action === 'SHOW_PRODUCT' && productId) return `/products/${productId}`;
  if (action === 'ADD_ITEM') return productId ? `/products/${productId}` : '/menu';
  if (action === 'CONFIGURE_ITEM' && ['PRODUCT_QUERY', 'PRICE_QUERY', 'PROMOTION_QUERY'].includes(response.intent_code) && productId) return `/products/${productId}`;
  if (['CONFIGURE_ITEM', 'CONFIGURE_PRODUCT', 'REVIEW_DRAFT', 'CONFIRM_ORDER', 'VIEW_ORDER'].includes(action)) return '/order';
  if (action === 'VIEW_ACCOUNT' || action === 'REQUEST_PAYMENT') return '/account';
  if (action === 'INITIATE_PAYMENT' && checkId) return `/check/${checkId}`;
  if (action === 'VIEW_CHECK' && checkId) return `/check/${checkId}`;
  if (action === 'OPEN_SECURE_PAYMENT_SOURCE' && checkId) return `/check/${checkId}`;
  if (['PAYMENT_STATUS', 'VIEW_PAYMENT_STATUS', 'WAIT_FOR_PAYMENT_RESOLUTION'].includes(action)) {
    if (checkId && paymentId) return `/check/${checkId}/payments/${paymentId}`;
    if (checkId) return `/check/${checkId}`;
  }
  return null;
}

function actionLabel(action: string): string {
  const labels: Record<string, string> = {
    SHOW_MENU: 'Ver menú',
    BROWSE_MENU: 'Explorar menú',
    ADD_ITEM: 'Elegir producto',
    SHOW_PRODUCT: 'Ver producto',
    CONFIGURE_ITEM: 'Completar configuración',
    CONFIGURE_PRODUCT: 'Completar configuración',
    REVIEW_DRAFT: 'Ver mi pedido',
    CONFIRM_ORDER: 'Revisar y confirmar',
    VIEW_ORDER: 'Ver mi pedido',
    VIEW_ACCOUNT: 'Ver mi cuenta',
    REQUEST_PAYMENT: 'Preparar cuenta',
    INITIATE_PAYMENT: 'Ir a pagar',
    VIEW_CHECK: 'Ver cuenta',
    OPEN_SECURE_PAYMENT_SOURCE: 'Completar pago seguro',
    VIEW_PAYMENT_STATUS: 'Consultar pago',
    PAYMENT_STATUS: 'Consultar pago',
    WAIT_FOR_PAYMENT_RESOLUTION: 'Consultar pago',
  };
  return labels[action] ?? action.replaceAll('_', ' ').toLocaleLowerCase('es-MX');
}

function MenuResult({ value }: { value: unknown }) {
  if (!Array.isArray(value)) return null;
  const products = value.flatMap((menu) => {
    const menuRecord = record(menu);
    if (!Array.isArray(menuRecord?.sections)) return [];
    return menuRecord.sections.flatMap((section) => {
      const sectionRecord = record(section);
      return Array.isArray(sectionRecord?.products) ? sectionRecord.products : [];
    });
  }).map(record).filter((product): product is UnknownRecord => product !== null);
  if (products.length === 0) return null;
  return (
    <div className="waiter-product-grid" aria-label="Productos encontrados">
      {products.slice(0, 6).map((product) => {
        const id = positiveNumber(product.id);
        const name = textValue(product.name);
        const price = record(product.price);
        if (!id || !name) return null;
        return (
          <article key={id} className="waiter-product-card">
            <div><strong>{name}</strong>{textValue(product.description) && <p>{String(product.description)}</p>}</div>
            <div>
              {textValue(price?.amount) && textValue(price?.currency) && (
                <span>{formatPrice(String(price?.amount), String(price?.currency))}</span>
              )}
              <Link to={`/products/${id}`} aria-label={`Ver ${name}`}>Ver <span aria-hidden="true">→</span></Link>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function CompactDomainResult({ response }: { response: ConversationActionResponse }) {
  const data = record(response.authoritative_data);
  if (!data) return <MenuResult value={response.authoritative_data} />;
  const requestType = textValue(data.request_type);
  if (requestType) {
    return (
      <div className="waiter-domain-summary" role="status">
        <strong>Solicitud registrada</strong>
        <span>Estado: {textValue(data.status) ?? 'recibida por el restaurante'}</span>
      </div>
    );
  }
  const items = Array.isArray(data.items) ? data.items.map(record).filter(Boolean) as UnknownRecord[] : [];
  if (items.length > 0 && items.some((item) => textValue(item.product_name))) {
    return (
      <div className="waiter-domain-summary">
        <strong>{response.intent_code === 'ORDER_CONFIRMATION' ? 'Pedido aceptado' : 'Resumen del pedido'}</strong>
        <ul>{items.slice(0, 5).map((item, index) => <li key={positiveNumber(item.item_id) ?? index}><span>{textValue(item.product_name)}</span><span>{textValue(item.quantity) ? `× ${formatQuantity(String(item.quantity))}` : ''}</span></li>)}</ul>
      </div>
    );
  }
  const total = textValue(data.eligible_total) ?? textValue(data.liability_total) ?? textValue(data.payable_total);
  const currency = textValue(data.currency);
  if (total && currency) {
    return (
      <div className="waiter-domain-summary waiter-domain-summary--money">
        <span>Total informado por el restaurante</span>
        <strong>{formatPrice(total, currency)}</strong>
      </div>
    );
  }
  const state = textValue(data.state) ?? textValue(data.check_status) ?? textValue(data.status);
  if (state) return <div className="waiter-domain-summary"><strong>Estado del restaurante</strong><span>{state}</span></div>;
  return null;
}

function CandidateChoices({
  response,
  disabled,
  onChoose,
}: {
  response: ConversationActionResponse;
  disabled: boolean;
  onChoose: (name: string, intent: RestaurantIntentCode, productId: number) => void;
}) {
  const data = record(response.authoritative_data);
  if (!Array.isArray(data?.candidates)) return null;
  const candidates = data.candidates.map(record).filter((candidate): candidate is UnknownRecord => candidate !== null);
  return (
    <div className="waiter-choice-list" aria-label="Opciones disponibles">
      {candidates.map((candidate) => {
        const productId = positiveNumber(candidate.product_id);
        const name = textValue(candidate.display_name);
        if (!productId || !name) return null;
        return <button key={productId} type="button" disabled={disabled} onClick={() => onChoose(name, response.intent_code, productId)}>{name}</button>;
      })}
    </div>
  );
}

function ResponseActions({
  response,
  disabled,
  onFollowUp,
}: {
  response: ConversationActionResponse;
  disabled: boolean;
  onFollowUp: (text: string, values?: Submission['values']) => void;
}) {
  const { checkId, checkVersion } = responseContext(response);
  if (response.experience.state === 'CONTINUATION_REQUIRED') {
    return (
      <div className="waiter-decision" aria-label="Decisión de continuación">
        <button className="primary-button" type="button" disabled={disabled || !checkId || !checkVersion} onClick={() => onFollowUp('Sí, queremos algo más', { intent_code: 'SERVICE_CONTINUATION', check_id: checkId!, continuation_decision: 'YES', expected_check_version: checkVersion! })}>Sí, continuar</button>
        <button className="secondary-button" type="button" disabled={disabled || !checkId || !checkVersion} onClick={() => onFollowUp('No, ya terminamos', { intent_code: 'SERVICE_CONTINUATION', check_id: checkId!, continuation_decision: 'NO', expected_check_version: checkVersion! })}>No, hemos terminado</button>
      </div>
    );
  }
  if (response.experience.code === 'PAYMENT_SCOPE_REQUIRED') {
    return (
      <div className="waiter-choice-list" aria-label="Alcance de la cuenta">
        <button type="button" disabled={disabled} onClick={() => onFollowUp('Mi consumo', { intent_code: 'PAYMENT_REQUEST', check_scope: 'INDIVIDUAL' })}>Mi consumo</button>
        <button type="button" disabled={disabled} onClick={() => onFollowUp('Toda la mesa', { intent_code: 'PAYMENT_REQUEST', check_scope: 'GLOBAL_TABLE' })}>Toda la mesa</button>
      </div>
    );
  }
  if (response.experience.code === 'PAYMENT_METHOD_REQUIRED' && checkId) {
    return (
      <div className="waiter-choice-list" aria-label="Método de pago">
        <button type="button" disabled={disabled} onClick={() => onFollowUp('Tarjeta', { intent_code: 'PAYMENT_REQUEST', check_id: checkId, payment_method: 'CARD' })}>Tarjeta</button>
        <button type="button" disabled={disabled} onClick={() => onFollowUp('Efectivo', { intent_code: 'PAYMENT_REQUEST', check_id: checkId, payment_method: 'CASH' })}>Efectivo</button>
      </div>
    );
  }
  const actions = [response.ui_action, ...response.experience.allowed_actions]
    .filter((action): action is string => Boolean(action))
    .filter((action, index, values) => values.indexOf(action) === index)
    .map((action) => ({ action, target: actionTarget(action, response) }))
    .filter((value): value is { action: string; target: string } => value.target !== null)
    .filter((value, index, values) => values.findIndex((candidate) => candidate.target === value.target) === index)
    .slice(0, 3);
  if (actions.length === 0) return null;
  return <div className="waiter-response-actions">{actions.map(({ action, target }) => <Link key={action} to={target}>{actionLabel(action)}</Link>)}</div>;
}

export function DigitalWaiterPage() {
  const { markSessionClosed } = useAuth();
  const [input, setInput] = useState('');
  const [entries, setEntries] = useState<ConversationEntry[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<Submission | null>(null);
  const inFlight = useRef(false);
  const endMarker = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    document.title = 'Mesero digital · Mesa';
  }, []);

  useEffect(() => {
    endMarker.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  }, [entries, submitting]);

  const terminal = entries.some((entry) => entry.response?.experience.state === 'SESSION_CLOSED');

  async function execute(submission: Submission, appendDiner = true) {
    if (inFlight.current || terminal) return;
    inFlight.current = true;
    setSubmitting(true);
    setFailure(null);
    if (appendDiner) {
      setEntries((current) => [...current, { id: `diner-${submission.key}`, role: 'DINER', text: submission.text }]);
    }
    try {
      const response = await dinerApi.sendConversationAction({
        modality: 'TEXT',
        content_text: submission.text,
        ...submission.values,
      }, submission.key);
      setEntries((current) => [...current, {
        id: `waiter-${response.response_message.id}`,
        role: 'DIGITAL_WAITER',
        text: response.message,
        response,
      }]);
      if (response.experience.state === 'SESSION_CLOSED') markSessionClosed();
    } catch (error) {
      if (!(error instanceof ApiError && error.state === 'SESSION_CLOSED')) setFailure(submission);
    } finally {
      inFlight.current = false;
      setSubmitting(false);
      composer.current?.focus();
    }
  }

  function send(text: string, values?: Submission['values']) {
    const normalized = text.trim();
    if (!normalized || inFlight.current || terminal) return;
    setInput('');
    void execute({ text: normalized, values, key: `diner-conversation-${crypto.randomUUID()}` });
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    send(input);
  }

  return (
    <div className="diner-page waiter-page">
      <DinerHeader />
      <main className="waiter-main">
        <header className="waiter-hero">
          <div className="waiter-symbol" aria-hidden="true"><span>✦</span></div>
          <div><p className="eyebrow">Asistente de tu mesa</p><h1>Mesero digital</h1><p>Pide, consulta o solicita apoyo con palabras sencillas. El restaurante siempre confirma la información.</p></div>
        </header>

        <section className="waiter-conversation" aria-label="Conversación con el Mesero digital" aria-live="polite">
          {entries.length === 0 && (
            <div className="waiter-welcome">
              <p>Hola. Puedo ayudarte con el menú, tu pedido, tu cuenta o solicitar apoyo.</p>
              <div className="waiter-quick-starts" aria-label="Sugerencias para comenzar">
                {quickStarts.map((text) => <button key={text} type="button" disabled={submitting} onClick={() => send(text)}>{text}</button>)}
              </div>
            </div>
          )}
          {entries.map((entry) => (
            <article key={entry.id} className={`waiter-entry waiter-entry--${entry.role.toLowerCase()}`}>
              <p className="waiter-speaker">{entry.role === 'DINER' ? 'Tú' : 'Mesero digital'}</p>
              <div className={`waiter-bubble${entry.response ? ` waiter-bubble--${entry.response.experience.state.toLowerCase()}` : ''}`} role={entry.response && ['PAYMENT_UNCERTAIN', 'ACTION_BLOCKED'].includes(entry.response.experience.state) ? 'alert' : undefined}>
                <p>{entry.text}</p>
                {entry.response && <CompactDomainResult response={entry.response} />}
                {entry.response && (
                  <CandidateChoices
                    response={entry.response}
                    disabled={submitting}
                    onChoose={(name, intent, productId) => send(name, { intent_code: intent, product_id: productId })}
                  />
                )}
                {entry.response && <ResponseActions response={entry.response} disabled={submitting} onFollowUp={send} />}
              </div>
            </article>
          ))}
          {submitting && <div className="waiter-thinking" role="status"><span className="spinner" aria-hidden="true" />El mesero digital está revisando…</div>}
          {failure && (
            <div className="waiter-error" role="alert">
              <div><strong>No pudimos confirmar la respuesta</strong><p>Conservamos la misma solicitud para reintentarla de forma segura.</p></div>
              <button type="button" disabled={submitting} onClick={() => void execute(failure, false)}>Reintentar</button>
            </div>
          )}
          <div ref={endMarker} />
        </section>

        <form className="waiter-composer" onSubmit={submit}>
          <label htmlFor="waiter-message">Escribe lo que necesitas</label>
          <div>
            <textarea
              ref={composer}
              id="waiter-message"
              rows={2}
              value={input}
              disabled={submitting || terminal}
              placeholder={terminal ? 'Esta sesión ha terminado' : 'Por ejemplo: Quiero ver mi cuenta'}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  send(input);
                }
              }}
            />
            <button className="primary-button" type="submit" disabled={submitting || terminal || !input.trim()}>{submitting ? 'Enviando…' : 'Enviar'}</button>
          </div>
          <p>Los pagos con tarjeta siempre se completan en el formulario seguro, nunca en esta conversación.</p>
        </form>
      </main>
    </div>
  );
}
