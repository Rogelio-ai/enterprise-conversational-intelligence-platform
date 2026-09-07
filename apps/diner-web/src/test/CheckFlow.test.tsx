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

function mockFetch(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(json(session));
    return handler(url, init);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); seedSession(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('check creation and review', () => {
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
    });
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
    expect(fetchMock.mock.calls.some(([input]) => /payment|settlement|conekta/i.test(String(input)))).toBe(false);
  });
});
