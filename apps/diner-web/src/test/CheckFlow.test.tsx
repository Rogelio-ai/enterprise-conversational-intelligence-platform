import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { CONEKTA_SCRIPT_URL, type ConektaCardParameters } from '../payments/conekta';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

const session = {
  id: 11, service_session_id: 22, resource_id: 44, conversation_id: 33,
  display_name: 'Ana', customer_id: null, status: 'ACTIVE',
  joined_at: '2026-09-06T20:00:00Z', ended_at: null,
};

function eligible(overrides: Record<string, unknown> = {}) {
  return {
    diner_session_id: 11, service_session_id: 22, resource_id: 44, display_name: 'Ana',
    eligible_order_ids: [901], eligible_total: '190.0000', currency: 'MXN',
    active_check_id: null, has_active_nonempty_draft: false, ...overrides,
  };
}

function check(overrides: Record<string, unknown> = {}) {
  return {
    id: 77, tenant_id: 1, organization_id: 2, location_id: 3, status: 'OPEN', version: 1,
    fingerprint: 'fingerprint', currency: 'MXN', controller_diner_session_id: 11,
    member_ids: [11], diner_scope_ids: [11], table_scope_session_ids: [],
    consumption_total: '190.0000', gratuity_total: '0.0000', liability_total: '190.0000',
    confirmed_settlement: '40.0000', outstanding: '150.0000', uncertain_exposure: '0.0000',
    frozen_at: null, settled_at: null, continuation_decision: 'UNDECIDED', cancelled_at: null,
    signal: null,
    details: [{
      resource_id: 44, service_session_id: 22, diners: [{
        diner_session_id: 11, display_name: 'Ana', orders: [{
          order_id: 901, diner_session_id: 11, service_session_id: 22, resource_id: 44,
          accepted_at: '2026-09-06T20:15:00Z', accepted_payable_amount: '190.0000',
          accepted_commercial_fingerprint: 'commercial',
          items: [{ item_id: 902, product_id: 101, product_name: 'Tacos de pescado', quantity: '2.0000', commercial_amount: '190.0000' }],
        }],
      }],
    }],
    ...overrides,
  };
}

function settlement(overrides: Record<string, unknown> = {}) {
  return {
    check_id: 77, check_status: 'OPEN', check_version: 1,
    check_fingerprint: 'fingerprint', liability_total: '190.0000',
    currency: 'MXN', confirmed_settlement: '40.0000',
    reserved_financial_exposure: '0.0000', uncertain_exposure: '0.0000',
    available_to_initiate: '150.0000', payments: [], ...overrides,
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11, serviceSessionId: 22, conversationId: 33, displayName: 'Ana',
    customerId: null, accessToken: 'check-token', expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function renderPath(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={[path]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter></ThemeProvider></QueryClientProvider>);
}

function mockFetch(
  handler: (url: string, init?: RequestInit) => Promise<Response>,
  currentSession: typeof session & { email?: string | null } = session,
  currentSettlement: Record<string, unknown> = settlement(),
) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
    if (url.endsWith('/diner/restaurant-checks/77/settlement')) {
      return Promise.resolve(json(currentSettlement));
    }
    return handler(url, init);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); seedSession(); });
afterEach(() => {
  cleanup();
  delete window.ConektaCheckoutComponents;
  document.querySelectorAll(`script[src="${CONEKTA_SCRIPT_URL}"]`).forEach((script) => script.remove());
  vi.unstubAllGlobals();
});

describe('check creation and review', () => {
  it('reconstructs the post-settlement experience on Check Review for non-card completion paths', async () => {
    const settledCheck = check({
      status: 'SETTLED', confirmed_settlement: '190.0000', outstanding: '0.0000',
      continuation_decision: 'PENDING', settled_at: '2026-09-07T20:00:00Z',
      signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED',
    });
    const fetchMock = mockFetch((url) => {
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(settledCheck));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }, session, settlement({
      check_status: 'SETTLED', confirmed_settlement: '190.0000',
      available_to_initiate: '0.0000',
    }));
    renderPath('/check/77');

    expect(await screen.findByRole('heading', { name: 'Gracias. ¿Necesitas algo más?' }, { timeout: 5_000 })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Solicitar factura' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'No, hemos terminado' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('does not create on entry and sends the exact individual command only after confirmation', async () => {
    let releasePost: ((value: Response) => void) | undefined;
    const pendingPost = new Promise<Response>((resolve) => { releasePost = resolve; });
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/diner/eligible-consumption')) return Promise.resolve(json([eligible()]));
      if (url.endsWith('/diner/restaurant-checks') && init?.method === 'POST') return pendingPost;
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');

    expect(await screen.findByRole('heading', { name: 'Preparar cuenta' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
    expect(screen.getByRole('button', { name: 'Crear cuenta para pagar' })).toBeDisabled();
    await userEvent.click(screen.getByRole('radio', { name: /Sólo mi consumo/ }));
    const create = screen.getByRole('button', { name: 'Crear cuenta para pagar' });
    fireEvent.click(create);
    fireEvent.click(create);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(post?.[0]).toBe('/api/diner/restaurant-checks');
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ mode: 'INDIVIDUAL' });
    const headers = new Headers(post?.[1]?.headers);
    expect(headers.get('Authorization')).toBe('Bearer check-token');
    expect(headers.get('Idempotency-Key')).toMatch(/^diner-check-/);

    releasePost?.(json(check({ details: null }), 201));
    expect(await screen.findByRole('heading', { name: 'Cuenta lista para pagar' })).toBeInTheDocument();
  });

  it('creates the selected scope with the current diner and selected companions', async () => {
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/diner/eligible-consumption')) return Promise.resolve(json([
        eligible(), eligible({ diner_session_id: 12, display_name: 'Luis', eligible_order_ids: [903], eligible_total: '80.0000' }),
      ]));
      if (url.endsWith('/diner/restaurant-checks') && init?.method === 'POST') return Promise.resolve(json(check({ member_ids: [11, 12], diner_scope_ids: [11, 12] }), 201));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check({ member_ids: [11, 12], diner_scope_ids: [11, 12] })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    await userEvent.click(await screen.findByRole('radio', { name: /Elegir comensales/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /Luis/ }));
    expect(screen.getByRole('checkbox', { name: /Ana \(tú\)/ })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta para pagar' }));
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({ mode: 'SELECTED', diner_session_ids: [11, 12] });
    });
  });

  it('recovers an active check after an ambiguous create without retrying the POST', async () => {
    let eligibilityReads = 0;
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/diner/eligible-consumption')) {
        eligibilityReads += 1;
        return Promise.resolve(json([eligible(eligibilityReads > 1 ? { active_check_id: 77, eligible_order_ids: [], eligible_total: '0.0000' } : {})]));
      }
      if (url.endsWith('/diner/restaurant-checks') && init?.method === 'POST') return Promise.reject(new TypeError('connection lost'));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    await userEvent.click(await screen.findByRole('radio', { name: /Sólo mi consumo/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta para pagar' }));

    expect(await screen.findByRole('heading', { name: 'Cuenta lista para pagar' })).toBeInTheDocument();
    expect(eligibilityReads).toBe(2);
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });

  it('keeps an ambiguous request safe and reuses its idempotency key on an intentional retry', async () => {
    const keys: string[] = [];
    let posts = 0;
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/diner/eligible-consumption')) return Promise.resolve(json([eligible()]));
      if (url.endsWith('/diner/restaurant-checks') && init?.method === 'POST') {
        posts += 1;
        keys.push(new Headers(init.headers).get('Idempotency-Key') ?? '');
        return posts === 1 ? Promise.reject(new TypeError('connection lost')) : Promise.resolve(json(check(), 200));
      }
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    await userEvent.click(await screen.findByRole('radio', { name: /Sólo mi consumo/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta para pagar' }));
    expect(await screen.findByText('Resultado sin confirmar')).toBeInTheDocument();
    expect(posts).toBe(1);
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta para pagar' }));
    expect(await screen.findByRole('heading', { name: 'Cuenta lista para pagar' })).toBeInTheDocument();
    expect(keys[0]).toBe(keys[1]);
  });

  it('re-reads a conflict and routes a newly reported draft to order review', async () => {
    let eligibilityReads = 0;
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/diner/eligible-consumption')) {
        eligibilityReads += 1;
        return Promise.resolve(json([eligible(eligibilityReads > 1 ? { has_active_nonempty_draft: true } : {})]));
      }
      if (url.endsWith('/diner/restaurant-checks') && init?.method === 'POST') return Promise.resolve(json({ error: { code: 'DINER_HAS_ACTIVE_ORDER_DRAFT', message: 'Draft' } }, 409));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    await userEvent.click(await screen.findByRole('radio', { name: /Sólo mi consumo/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Crear cuenta para pagar' }));
    expect(await screen.findByText('Hay un pedido en borrador. Revísalo antes de crear la cuenta.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Revisar pedido' })).toHaveAttribute('href', '/order');
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });

  it('resolves direct /check access with reads only and never creates implicitly', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) return Promise.resolve(json({ active_check_id: null }));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check');
    expect(await screen.findByRole('heading', { name: 'No hay una cuenta por revisar' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('loads an existing active check instead of creating a duplicate', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/eligible-consumption')) return Promise.resolve(json([eligible({ active_check_id: 77 })]));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    expect(await screen.findByRole('heading', { name: 'Cuenta lista para pagar' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('handles no eligible consumption without creating a zero check', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/eligible-consumption')) return Promise.resolve(json([eligible({ eligible_order_ids: [], eligible_total: '0.0000' })]));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    expect(await screen.findByRole('heading', { name: 'No hay una cuenta por crear' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('preserves terminal session closure while loading check eligibility', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/eligible-consumption')) return Promise.resolve(json({ error: { code: 'session_closed', state: 'SESSION_CLOSED', message: 'Session closed' } }, 409));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/new');
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull());
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
  });

  it('shows only backend financial fields and treats uncertain exposure as unconfirmed', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check({ uncertain_exposure: '30.0000' })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }, session, settlement({
      uncertain_exposure: '30.0000', available_to_initiate: '120.0000',
      payments: [{ id: 501, state: 'UNCERTAIN' }],
    }));
    renderPath('/check/77');
    expect(await screen.findByText('2 × Tacos de pescado')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pago pendiente de confirmación' })).toBeInTheDocument();
    expect(screen.getByText('El restaurante aún verifica una operación. No vuelvas a pagar por el momento.')).toBeInTheDocument();
    expect(screen.getByText('Alcance:').parentElement).toHaveTextContent('Consumo individual');
    expect(screen.getByText('Pago confirmado')).toBeInTheDocument();
    expect(screen.getByText('$40.00')).toBeInTheDocument();
    expect(screen.getAllByText('Pago pendiente de confirmación')).toHaveLength(2);
    expect(screen.getByText('$30.00')).toBeInTheDocument();
    expect(screen.getByText('Saldo pendiente')).toBeInTheDocument();
    expect(screen.getByText('$150.00')).toBeInTheDocument();
    expect(screen.getByText('Este importe no se presenta como pagado hasta que el restaurante lo confirme.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /pagar|método/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/diner/restaurant-checks/77?view=detailed'))).toHaveLength(2));
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/diner/restaurant-checks/77/settlement'))).toBe(true);
    expect(fetchMock.mock.calls.some(([input]) => /payment-executors|conekta/i.test(String(input)))).toBe(false);
    expect(screen.getByRole('link', { name: 'Consultar pago' })).toHaveAttribute('href', '/check/77/payments/501');
  });

  it('uses the authoritative CARD executor key to request client configuration', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      if (url.endsWith('/diner/payment-executors?method_category=CARD&currency=MXN')) {
        return Promise.resolve(json([{
          executor_key: 'location-priority-card', display_name: 'Tarjeta',
          topology: 'LOCATION', method_category: 'CARD', currency: 'MXN',
        }]));
      }
      if (url.endsWith('/diner/payment-executors/location-priority-card/client-configuration?currency=MXN')) {
        return Promise.resolve(json({
          provider: 'UNSUPPORTED', tokenization_mode: 'UNSUPPORTED',
          public_key: 'key_test_public', locale: 'es',
        }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/77');

    expect(await screen.findByRole('heading', { name: 'Cuenta lista para pagar' })).toBeInTheDocument();
    await userEvent.type(await screen.findByRole('textbox', { name: 'Correo electrónico' }), 'ana@example.com');
    await userEvent.type(screen.getByRole('textbox', { name: 'Teléfono' }), '+525500000001');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar al formulario de tarjeta' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible preparar la tarjeta');
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith(
      '/diner/payment-executors/location-priority-card/client-configuration?currency=MXN',
    ))).toBe(true);
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).includes('/payments') && init?.method === 'POST')).toBe(false);
  });

  it('preserves terminal session closure during card client configuration', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      if (url.endsWith('/diner/payment-executors?method_category=CARD&currency=MXN')) {
        return Promise.resolve(json([{
          executor_key: 'location-priority-card', display_name: 'Tarjeta',
          topology: 'LOCATION', method_category: 'CARD', currency: 'MXN',
        }]));
      }
      if (url.endsWith('/diner/payment-executors/location-priority-card/client-configuration?currency=MXN')) {
        return Promise.resolve(json({
          error: { code: 'session_closed', state: 'SESSION_CLOSED', message: 'Session closed' },
        }, 409));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/77');

    await userEvent.type(await screen.findByRole('textbox', { name: 'Correo electrónico' }), 'ana@example.com');
    await userEvent.type(screen.getByRole('textbox', { name: 'Teléfono' }), '+525500000001');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar al formulario de tarjeta' }));
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull());
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).includes('/payments') && init?.method === 'POST')).toBe(false);
  });

  it('keeps payment contact route-local and gates card preparation on valid contact data', async () => {
    const originalSessionStorage = sessionStorage.getItem('diner-auth-session-v1');
    const fetchMock = mockFetch((url) => {
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      if (url.endsWith('/diner/payment-executors?method_category=CARD&currency=MXN')) {
        return Promise.resolve(json([{
          executor_key: 'card', display_name: 'Tarjeta', topology: 'LOCATION',
          method_category: 'CARD', currency: 'MXN',
        }]));
      }
      if (url.endsWith('/diner/payment-executors/card/client-configuration?currency=MXN')) {
        return Promise.resolve(json({ provider: 'UNSUPPORTED', tokenization_mode: 'UNSUPPORTED', public_key: 'public', locale: 'es' }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }, { ...session, email: 'ana.known@example.com' });
    renderPath('/check/77');

    const name = await screen.findByRole('textbox', { name: 'Nombre' });
    const email = screen.getByRole('textbox', { name: 'Correo electrónico' });
    const phone = screen.getByRole('textbox', { name: 'Teléfono' });
    expect(name).toHaveValue('Ana');
    expect(email).toHaveValue('ana.known@example.com');

    await userEvent.clear(email);
    await userEvent.type(email, 'correo-invalido');
    await userEvent.type(phone, '5512345678');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar al formulario de tarjeta' }));
    expect(screen.getByText('Ingresa un correo electrónico válido.')).toBeInTheDocument();
    expect(screen.getByText(/Ingresa el teléfono con código de país/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/client-configuration'))).toBe(false);

    await userEvent.clear(email);
    await userEvent.type(email, 'corrected@example.com');
    await userEvent.clear(phone);
    await userEvent.type(phone, '+52 55 1234 5678');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar al formulario de tarjeta' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible preparar la tarjeta');
    expect(sessionStorage.getItem('diner-auth-session-v1')).toBe(originalSessionStorage);
    expect(JSON.stringify({ ...localStorage })).not.toContain('corrected@example.com');
    expect(JSON.stringify({ ...localStorage })).not.toContain('+52 55 1234 5678');
    expect(sessionStorage.getItem('diner-auth-session-v1')).not.toContain('corrected@example.com');
    expect(sessionStorage.getItem('diner-auth-session-v1')).not.toContain('+52 55 1234 5678');
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).includes('/payments') && init?.method === 'POST')).toBe(false);
    expect(screen.queryByLabelText(/número de tarjeta|cvv|cvc|fecha de vencimiento/i)).not.toBeInTheDocument();
  });

  it('hands the opaque token to one explicit payment initiation and renders its authoritative result', async () => {
    let cardParameters: ConektaCardParameters | undefined;
    let releasePayment: ((value: Response) => void) | undefined;
    const pendingPayment = new Promise<Response>((resolve) => { releasePayment = resolve; });
    const fetchMock = mockFetch((url, init) => {
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check()));
      if (url.endsWith('/diner/payment-executors?method_category=CARD&currency=MXN')) {
        return Promise.resolve(json([{
          executor_key: 'conekta-card', display_name: 'Tarjeta', topology: 'LOCATION',
          method_category: 'CARD', currency: 'MXN',
        }]));
      }
      if (url.endsWith('/diner/payment-executors/conekta-card/client-configuration?currency=MXN')) {
        return Promise.resolve(json({
          provider: 'CONEKTA', tokenization_mode: 'WEB_TOKENIZER',
          public_key: 'key_test_public', locale: 'es',
        }));
      }
      if (url.endsWith('/diner/restaurant-checks/77/payments') && init?.method === 'POST') {
        return pendingPayment;
      }
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) {
        return Promise.resolve(json({
          id: 501, check_id: 77, amount: '150.0000', currency: 'MXN',
          method_category: 'CARD', state: 'SUCCEEDED',
          instrument_display: 'VISA •••• 4242', terminal_at: '2026-09-07T20:00:00Z',
        }));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPath('/check/77');

    await userEvent.type(await screen.findByRole('textbox', { name: 'Correo electrónico' }), 'ana@example.com');
    await userEvent.type(screen.getByRole('textbox', { name: 'Teléfono' }), '+525500000001');
    await userEvent.click(screen.getByRole('button', { name: 'Continuar al formulario de tarjeta' }));
    await waitFor(() => expect(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`)).not.toBeNull());
    window.ConektaCheckoutComponents = {
      Card: (parameters) => { cardParameters = parameters; },
    };
    fireEvent.load(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`) as HTMLScriptElement);
    await waitFor(() => expect(cardParameters).toBeDefined());
    const providerSubmit = vi.fn();
    cardParameters?.callbacks.onUpdateSubmitTrigger(providerSubmit);
    await userEvent.click(await screen.findByRole('button', { name: 'Continuar con tarjeta' }));
    expect(providerSubmit).toHaveBeenCalledOnce();
    cardParameters?.callbacks.onCreateTokenSucceeded({ id: 'tok_payment_once' });

    const pay = await screen.findByRole('button', { name: 'Pagar ahora' });
    expect(fetchMock.mock.calls.some(([input, request]) => String(input).endsWith('/payments') && request?.method === 'POST')).toBe(false);
    fireEvent.click(pay);
    fireEvent.click(pay);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([input, request]) => (
      String(input).endsWith('/payments') && request?.method === 'POST'
    ))).toHaveLength(1));
    const paymentCall = fetchMock.mock.calls.find(([input, request]) => (
      String(input).endsWith('/payments') && request?.method === 'POST'
    ));
    expect(new Headers(paymentCall?.[1]?.headers).get('Idempotency-Key')).toMatch(/^diner-payment-/);
    expect(JSON.parse(String(paymentCall?.[1]?.body))).toEqual({
      expected_check_version: 1,
      expected_check_fingerprint: 'fingerprint',
      amount: '150.0000',
      currency: 'MXN',
      method_category: 'CARD',
      payer_type: 'DINER',
      payer_diner_session_id: 11,
      selection_mode: 'EXPLICIT',
      executor_key: 'conekta-card',
      customer_payment_source: 'tok_payment_once',
      payment_customer_identity: {
        display_name: 'Ana', email: 'ana@example.com', phone: '+525500000001',
      },
    });
    expect(sessionStorage.getItem('diner-auth-session-v1')).not.toContain('tok_payment_once');
    releasePayment?.(json({ id: 501, state: 'SUCCEEDED', amount: '150.0000', currency: 'MXN' }, 201));
    expect(await screen.findByRole('heading', { name: 'Pago registrado' })).toBeInTheDocument();
  });
});
