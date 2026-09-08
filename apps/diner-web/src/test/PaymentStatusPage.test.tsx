import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

const session = {
  id: 11, service_session_id: 22, resource_id: 44, conversation_id: 33,
  display_name: 'Ana', customer_id: null, status: 'ACTIVE',
  joined_at: '2026-09-07T19:00:00Z', ended_at: null,
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function payment(state: string, overrides: Record<string, unknown> = {}) {
  return {
    id: 501, check_id: 77, amount: '40.0000', currency: 'MXN',
    method_category: 'CARD', state, instrument_display: 'VISA •••• 4242',
    terminal_at: null, ...overrides,
  };
}

function settlement(overrides: Record<string, unknown> = {}) {
  return {
    check_id: 77, check_status: 'FROZEN', check_version: 1,
    check_fingerprint: 'fingerprint', liability_total: '100.0000', currency: 'MXN',
    confirmed_settlement: '40.0000', reserved_financial_exposure: '0.0000',
    uncertain_exposure: '0.0000', available_to_initiate: '60.0000', payments: [],
    ...overrides,
  };
}

function check(overrides: Record<string, unknown> = {}) {
  return {
    id: 77, tenant_id: 1, organization_id: 2, location_id: 3, status: 'FROZEN',
    version: 1, fingerprint: 'fingerprint', currency: 'MXN',
    controller_diner_session_id: 11, member_ids: [11], diner_scope_ids: [11],
    table_scope_session_ids: [], consumption_total: '100.0000',
    gratuity_total: '0.0000', liability_total: '100.0000',
    confirmed_settlement: '40.0000', outstanding: '60.0000',
    uncertain_exposure: '0.0000', frozen_at: '2026-09-07T19:30:00Z',
    settled_at: null, continuation_decision: 'NONE', cancelled_at: null,
    details: [], signal: null, ...overrides,
  };
}

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11, serviceSessionId: 22, conversationId: 33,
    displayName: 'Ana', customerId: null, accessToken: 'payment-status-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function renderStatus() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/check/77/payments/501']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function mockStatusFetch(values: {
  payment: Record<string, unknown>;
  settlement: Record<string, unknown>;
  check: Record<string, unknown>;
}) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
    if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(values.payment));
    if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(values.settlement));
    if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(values.check));
    return Promise.reject(new Error(`Unexpected request: ${url} ${init?.method ?? 'GET'}`));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  seedSession();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('diner payment status and settlement experience', () => {
  it('reconstructs full settlement and post-settlement entry from backend reads without another payment', async () => {
    const fetchMock = mockStatusFetch({
      payment: payment('SUCCEEDED', { amount: '100.0000' }),
      settlement: settlement({
        check_status: 'SETTLED', confirmed_settlement: '100.0000',
        available_to_initiate: '0.0000',
      }),
      check: check({
        status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000',
        settled_at: '2026-09-07T20:00:00Z', continuation_decision: 'PENDING',
      }),
    });
    renderStatus();

    expect(await screen.findByRole('heading', { name: 'Pago registrado' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Tu cuenta quedó liquidada' })).toBeInTheDocument();
    expect(screen.getByText('El restaurante confirmó que no queda saldo pendiente ni exposición financiera sin resolver.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Gracias. ¿Necesitas algo más?' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '¿Desean algo más?' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => (
      String(url).endsWith('/payments') && init?.method === 'POST'
    ))).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() => expect(
      fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/payments/501')),
    ).toHaveLength(2));
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/payments') && init?.method === 'POST')).toBe(false);
  });

  it('creates durable invoice, paid-print and human requests without claiming staff completion or choosing continuation', async () => {
    let resolveInvoice: ((value: Response) => void) | undefined;
    const pendingInvoice = new Promise<Response>((resolve) => { resolveInvoice = resolve; });
    let requestId = 700;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ check_status: 'SETTLED', confirmed_settlement: '100.0000', available_to_initiate: '0.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check({ status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000', continuation_decision: 'PENDING', signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED' })));
      if (url.endsWith('/diner/operational-requests') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body));
        const response = json({
          id: requestId++, request_type: body.request_type, status: 'PENDING',
          related_restaurant_check_id: body.related_restaurant_check_id,
          created_at: '2026-09-07T20:01:00Z', resolved_at: null,
          experience: { state: 'STAFF_ASSISTANCE_REQUIRED', code: 'STAFF_ASSISTANCE_REQUIRED', required_input: [], allowed_actions: [], next_action: null },
        }, 201);
        return body.request_type === 'INVOICE_ASSISTANCE' ? pendingInvoice : Promise.resolve(response);
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    const invoice = await screen.findByRole('button', { name: 'Solicitar factura' });
    fireEvent.click(invoice);
    fireEvent.click(invoice);
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/operational-requests'))).toHaveLength(1));
    resolveInvoice?.(json({
      id: 700, request_type: 'INVOICE_ASSISTANCE', status: 'PENDING', related_restaurant_check_id: 77,
      created_at: '2026-09-07T20:01:00Z', resolved_at: null,
      experience: { state: 'STAFF_ASSISTANCE_REQUIRED', code: 'STAFF_ASSISTANCE_REQUIRED', required_input: [], allowed_actions: [], next_action: null },
    }, 201));
    expect(await screen.findByText('Solicitud enviada')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Solicitar cuenta impresa' }));
    await userEvent.click(screen.getByRole('button', { name: 'Necesito ayuda' }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/operational-requests'))).toHaveLength(3));
    const posts = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/operational-requests'));
    expect(posts.map(([, init]) => JSON.parse(String(init?.body)))).toEqual([
      { request_type: 'INVOICE_ASSISTANCE', related_restaurant_check_id: 77 },
      { request_type: 'PAID_CHECK_PRINT', related_restaurant_check_id: 77 },
      { request_type: 'HUMAN_ASSISTANCE', related_restaurant_check_id: null },
    ]);
    expect(posts.every(([, init]) => new Headers(init?.headers).get('Idempotency-Key')?.startsWith('diner-post-settlement-'))).toBe(true);
    expect(sessionStorage.getItem('diner-c5:11:77:request:INVOICE_ASSISTANCE')).toBe(new Headers(posts[0][1]?.headers).get('Idempotency-Key'));
    expect(screen.queryByText(/impreso|facturado|en camino|atendido/i)).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/continuation-decision'))).toBe(false);
  });

  it('submits explicit YES through the continuation contract and returns to the menu', async () => {
    const settledCheck = check({ status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000', continuation_decision: 'PENDING', signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED' });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ check_status: 'SETTLED', confirmed_settlement: '100.0000', available_to_initiate: '0.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(settledCheck));
      if (url.endsWith('/diner/restaurant-checks/77/continuation-decision') && init?.method === 'POST') return Promise.resolve(json({ ...settledCheck, continuation_decision: 'YES', signal: null }));
      if (url.endsWith('/diner/menu')) return Promise.resolve(json({ menus: [], experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: [], next_action: null } }));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'Sí, queremos continuar' }));
    expect(await screen.findByRole('heading', { name: 'Menú' }, { timeout: 5_000 })).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/continuation-decision'));
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ expected_version: 1, decision: 'YES' });
    expect(new Headers(post?.[1]?.headers).get('Idempotency-Key')).toMatch(/^diner-continuation-/);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/diner-session/end'))).toBe(false);
  });

  it('submits explicit NO, uses the authoritative diner closure path and presents SESSION_CLOSED', async () => {
    const settledCheck = check({ status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000', continuation_decision: 'PENDING', signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED' });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session') && init?.method !== 'POST') return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ check_status: 'SETTLED', confirmed_settlement: '100.0000', available_to_initiate: '0.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(settledCheck));
      if (url.endsWith('/diner/restaurant-checks/77/continuation-decision') && init?.method === 'POST') return Promise.resolve(json({ ...settledCheck, continuation_decision: 'NO', signal: null }));
      if (url.endsWith('/diner-session/end') && init?.method === 'POST') return Promise.resolve(json({ ...session, status: 'ENDED', ended_at: '2026-09-07T20:05:00Z' }));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'No, hemos terminado' }));
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/continuation-decision'))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/diner-session/end'))).toHaveLength(1);
    expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull();
  });

  it('keeps the same continuation identity after an ambiguous network result and blocks a conflicting choice', async () => {
    const settledCheck = check({ status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000', continuation_decision: 'PENDING', signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED' });
    let attempts = 0;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ check_status: 'SETTLED', confirmed_settlement: '100.0000', available_to_initiate: '0.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(settledCheck));
      if (url.endsWith('/diner/restaurant-checks/77/continuation-decision') && init?.method === 'POST') {
        attempts += 1;
        return attempts === 1
          ? Promise.reject(new TypeError('connection lost'))
          : Promise.resolve(json({ ...settledCheck, continuation_decision: 'YES', signal: null }));
      }
      if (url.endsWith('/diner/menu')) return Promise.resolve(json({ menus: [], experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: [], next_action: null } }));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'Sí, queremos continuar' }));
    expect(await screen.findByText(/Conservamos la misma solicitud/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'No, hemos terminado' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Sí, queremos continuar' }));
    expect(await screen.findByRole('heading', { name: 'Menú' }, { timeout: 5_000 })).toBeInTheDocument();
    const posts = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/continuation-decision'));
    expect(posts).toHaveLength(2);
    expect(new Headers(posts[0][1]?.headers).get('Idempotency-Key')).toBe(new Headers(posts[1][1]?.headers).get('Idempotency-Key'));
    expect(JSON.parse(String(sessionStorage.getItem('diner-c5:11:77:continuation'))).decision).toBe('YES');
  });

  it('does not bypass staff authority when backend retains terminal closure', async () => {
    const settledCheck = check({ status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000', continuation_decision: 'PENDING', signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED', table_scope_session_ids: [22] });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ check_status: 'SETTLED', confirmed_settlement: '100.0000', available_to_initiate: '0.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json({ ...settledCheck, continuation_decision: init ? 'PENDING' : 'NO' }));
      if (url.endsWith('/diner/restaurant-checks/77/continuation-decision') && init?.method === 'POST') return Promise.resolve(json({ ...settledCheck, continuation_decision: 'NO', signal: null }));
      if (url.endsWith('/diner-session/end') && init?.method === 'POST') return Promise.resolve(json({ detail: { code: 'TABLE_NOT_ELIGIBLE', message: 'Staff closure required' } }, 409));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'No, hemos terminado' }));
    expect(await screen.findByText('Decisión registrada.')).toBeInTheDocument();
    expect(screen.getByText('El equipo completará el cierre correspondiente.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Esta sesión ha terminado' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/diner-session/end'))).toHaveLength(1);
  });

  it('re-reads financial truth after a continuation race and does not force closure', async () => {
    let checkReads = 0;
    const settledCheck = check({ status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000', continuation_decision: 'PENDING', signal: 'SERVICE_CONTINUATION_DECISION_REQUIRED' });
    const changedCheck = check({ status: 'FROZEN', confirmed_settlement: '60.0000', outstanding: '40.0000', continuation_decision: 'NONE' });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement(checkReads > 1 ? { check_status: 'FROZEN', confirmed_settlement: '60.0000', available_to_initiate: '40.0000' } : { check_status: 'SETTLED', confirmed_settlement: '100.0000', available_to_initiate: '0.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) {
        checkReads += 1;
        return Promise.resolve(json(checkReads === 1 ? settledCheck : changedCheck));
      }
      if (url.endsWith('/diner/restaurant-checks/77/continuation-decision') && init?.method === 'POST') return Promise.resolve(json({ error: { code: 'CHECK_NOT_MODIFIABLE', state: 'ACTION_BLOCKED', message: 'Financial state changed' } }, 409));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'No, hemos terminado' }));
    expect(await screen.findByRole('heading', { name: 'Resumen financiero' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Gracias. ¿Necesitas algo más?' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('?view=detailed'))).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/diner-session/end'))).toBe(false);
  });

  it('shows a succeeded partial payment with authoritative outstanding and a safe intentional next step', async () => {
    mockStatusFetch({
      payment: payment('SUCCEEDED'), settlement: settlement(), check: check(),
    });
    renderStatus();

    expect(await screen.findByRole('heading', { name: 'Pago registrado' })).toBeInTheDocument();
    expect(screen.getByText('Este pago fue registrado, pero la cuenta aún conserva saldo pendiente.')).toBeInTheDocument();
    expect(screen.getByText('Saldo pendiente').parentElement).toHaveTextContent('$60.00');
    expect(screen.getByRole('link', { name: 'Volver a opciones de pago' })).toHaveAttribute('href', '/check/77');
    expect(screen.queryByRole('heading', { name: 'Tu cuenta quedó liquidada' })).not.toBeInTheDocument();
  });

  it.each([
    ['RESERVED', 'Pago reservado', '40.0000', '0.0000'],
    ['IN_PROGRESS', 'Estamos procesando tu pago', '40.0000', '0.0000'],
    ['REJECTED', 'El pago no fue aprobado', '0.0000', '0.0000'],
    ['FAILED', 'No se pudo completar el pago', '0.0000', '0.0000'],
    ['CANCELLED', 'Este intento ya no está activo', '0.0000', '0.0000'],
  ])('renders %s truthfully without automatic recovery or payment creation', async (
    state, title, reserved, uncertain,
  ) => {
    const fetchMock = mockStatusFetch({
      payment: payment(state),
      settlement: settlement({
        confirmed_settlement: '0.0000', reserved_financial_exposure: reserved,
        uncertain_exposure: uncertain,
        available_to_initiate: reserved === '0.0000' ? '100.0000' : '60.0000',
      }),
      check: check({ confirmed_settlement: '0.0000', outstanding: '100.0000' }),
    });
    renderStatus();

    expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Consultar estado' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => init?.method === 'POST' && String(url).includes('/payments'))).toBe(false);
  });

  it('keeps zero outstanding unresolved exposure distinct from financial completion', async () => {
    mockStatusFetch({
      payment: payment('UNCERTAIN'),
      settlement: settlement({
        check_status: 'FROZEN', confirmed_settlement: '60.0000',
        uncertain_exposure: '40.0000', available_to_initiate: '0.0000',
      }),
      check: check({ confirmed_settlement: '60.0000', outstanding: '0.0000', uncertain_exposure: '40.0000' }),
    });
    renderStatus();

    expect(await screen.findByRole('heading', { name: 'Estamos confirmando el resultado de tu pago' })).toBeInTheDocument();
    expect(screen.getByText(/Existe un pago pendiente de confirmación/)).toBeInTheDocument();
    expect(screen.getByText('Importe pendiente de confirmación').parentElement).toHaveTextContent('$40.00');
    expect(screen.queryByRole('heading', { name: 'Tu cuenta quedó liquidada' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Volver a opciones de pago' })).not.toBeInTheDocument();
  });

  it('recovers UNCERTAIN through the recovery route and refetches authoritative settlement', async () => {
    let recovered = false;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501/recover') && init?.method === 'POST') {
        recovered = true;
        return Promise.resolve(json(payment('SUCCEEDED', { amount: '100.0000' })));
      }
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) {
        return Promise.resolve(json(payment(recovered ? 'SUCCEEDED' : 'UNCERTAIN', { amount: '100.0000' })));
      }
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) {
        return Promise.resolve(json(settlement(recovered ? {
          check_status: 'SETTLED', confirmed_settlement: '100.0000',
          uncertain_exposure: '0.0000', available_to_initiate: '0.0000',
        } : {
          confirmed_settlement: '0.0000', uncertain_exposure: '100.0000',
          available_to_initiate: '0.0000',
        })));
      }
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) {
        return Promise.resolve(json(check(recovered ? {
          status: 'SETTLED', confirmed_settlement: '100.0000', outstanding: '0.0000',
          uncertain_exposure: '0.0000', settled_at: '2026-09-07T20:00:00Z',
          continuation_decision: 'PENDING',
        } : {
          confirmed_settlement: '0.0000', outstanding: '100.0000', uncertain_exposure: '100.0000',
        })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'Consultar estado' }));
    expect(await screen.findByRole('heading', { name: 'Tu cuenta quedó liquidada' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url, init]) => String(url).endsWith('/recover') && init?.method === 'POST')).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/payments') && init?.method === 'POST')).toBe(false);
  });

  it('keeps STILL_UNCERTAIN persistent and never enables another payment', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501/recover') && init?.method === 'POST') return Promise.resolve(json(payment('UNCERTAIN')));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('UNCERTAIN')));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ confirmed_settlement: '0.0000', uncertain_exposure: '40.0000', available_to_initiate: '60.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check({ confirmed_settlement: '0.0000', outstanding: '100.0000', uncertain_exposure: '40.0000' })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'Consultar estado' }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/recover'))).toHaveLength(1));
    expect(screen.getByRole('heading', { name: 'Estamos confirmando el resultado de tu pago' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Volver a opciones de pago' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/payments') && init?.method === 'POST')).toBe(false);
  });

  it('preserves terminal session closure during explicit recovery', async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
      if (url.endsWith('/diner/restaurant-checks/77/payments/501/recover') && init?.method === 'POST') {
        return Promise.resolve(json({
          error: {
            code: 'SESSION_CLOSED', state: 'SESSION_CLOSED',
            message: 'Session closed',
          },
        }, 409));
      }
      if (url.endsWith('/diner/restaurant-checks/77/payments/501')) return Promise.resolve(json(payment('UNCERTAIN')));
      if (url.endsWith('/diner/restaurant-checks/77/settlement')) return Promise.resolve(json(settlement({ confirmed_settlement: '0.0000', uncertain_exposure: '40.0000' })));
      if (url.includes('/diner/restaurant-checks/77?view=detailed')) return Promise.resolve(json(check({ confirmed_settlement: '0.0000', outstanding: '100.0000', uncertain_exposure: '40.0000' })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderStatus();

    await userEvent.click(await screen.findByRole('button', { name: 'Consultar estado' }));
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull());
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith('/payments') && init?.method === 'POST')).toBe(false);
  });
});
