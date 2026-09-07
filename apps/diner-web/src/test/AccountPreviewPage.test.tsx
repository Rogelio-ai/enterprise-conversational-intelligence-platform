import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

const session = {
  id: 11,
  service_session_id: 22,
  resource_id: 44,
  conversation_id: 33,
  display_name: 'Ana',
  customer_id: null,
  status: 'ACTIVE',
  joined_at: '2026-09-06T20:00:00Z',
  ended_at: null,
};

function accountPreview(overrides: Record<string, unknown> = {}) {
  return {
    diner_session_id: 11,
    display_name: 'Ana',
    currency: 'MXN',
    eligible_order_ids: [901],
    lines: [{
      order_id: 901,
      order_item_id: 902,
      product_id: 101,
      product_name: 'Tacos de pescado',
      quantity: '2.0000',
      unit_price: '100.0000',
      discount_amount: '10.0000',
      commercial_amount: '190.0000',
    }],
    eligible_total: '190.0000',
    active_check_id: null,
    has_active_nonempty_draft: false,
    experience: {
      state: 'OK',
      code: 'OK',
      required_input: [],
      allowed_actions: ['CREATE_CHECK', 'VIEW_ORDER'],
      next_action: null,
    },
    ...overrides,
  };
}

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11,
    serviceSessionId: 22,
    conversationId: 33,
    displayName: 'Ana',
    customerId: null,
    accessToken: 'account-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/account']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function mockFetch(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(response(session));
    return handler(url, init);
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

describe('account preview', () => {
  it('reads and presents authoritative diner consumption without a mutation', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) return Promise.resolve(response(accountPreview()));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Mi cuenta' })).toBeInTheDocument();
    expect(screen.getByText('Consumo de Ana, actualizado directamente por el restaurante.')).toBeInTheDocument();
    expect(screen.getByText('Tacos de pescado')).toBeInTheDocument();
    expect(screen.getByText('2 × $100.00')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    expect(screen.getAllByText('$190.00')).toHaveLength(2);
    expect(screen.getByRole('link', { name: 'Mi cuenta' })).toHaveAttribute('href', '/account');

    const accountCalls = fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/account-preview'));
    expect(accountCalls).toHaveLength(1);
    expect(accountCalls[0][1]?.method).toBeUndefined();
    expect(new Headers(accountCalls[0][1]?.headers).get('Authorization')).toBe('Bearer account-token');
    expect(fetchMock.mock.calls.some(([input]) => /check|payment|settlement/.test(String(input)))).toBe(false);
  });

  it('presents active-account and unconfirmed-draft facts without adding actions', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) return Promise.resolve(response(accountPreview({
        active_check_id: 77,
        has_active_nonempty_draft: true,
      })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByText('Ya existe una cuenta activa.')).toBeInTheDocument();
    expect(screen.getByText('Tienes un pedido en borrador.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /pagar|crear cuenta/i })).not.toBeInTheDocument();
  });

  it('shows the authoritative zero-consumption state without closing the session', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) return Promise.resolve(response(accountPreview({
        eligible_order_ids: [],
        lines: [],
        eligible_total: '0.0000',
      })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Aún no tienes consumo disponible' })).toBeInTheDocument();
    expect(screen.getByText('Tu consumo elegible actual es $0.00.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver al menú' })).toHaveAttribute('href', '/menu');
    expect(screen.queryByText(/sesión.*termin/i)).not.toBeInTheDocument();
  });

  it('does not invent a currency when the backend cannot unify it', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) return Promise.resolve(response(accountPreview({ currency: null })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findAllByText('190.0000 · moneda no unificada')).toHaveLength(2);
    expect(screen.queryByText('$190.00')).not.toBeInTheDocument();
  });

  it('shows loading and safely retries a failed read', async () => {
    let reads = 0;
    let finishFirst: ((value: Response) => void) | undefined;
    const firstRead = new Promise<Response>((resolve) => { finishFirst = resolve; });
    mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) {
        reads += 1;
        return reads === 1 ? firstRead : Promise.resolve(response(accountPreview()));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByText('Cargando tu cuenta…')).toBeInTheDocument();
    finishFirst?.(response({ error: { code: 'internal_error', message: 'Unavailable' } }, 500));
    expect(await screen.findByRole('heading', { name: 'No pudimos mostrar tu cuenta' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('Tacos de pescado')).toBeInTheDocument();
    expect(reads).toBe(2);
  });

  it('reconstructs refreshed account truth from another backend read', async () => {
    let reads = 0;
    mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) {
        reads += 1;
        return Promise.resolve(response(accountPreview(reads === 1 ? {} : {
          eligible_total: '240.0000',
          lines: [{
            order_id: 903,
            order_item_id: 904,
            product_id: 102,
            product_name: 'Agua mineral',
            quantity: '1.0000',
            unit_price: '50.0000',
            discount_amount: '0.0000',
            commercial_amount: '50.0000',
          }],
        })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    const first = renderPage();
    expect(await screen.findByText('Tacos de pescado')).toBeInTheDocument();
    first.unmount();
    cleanup();
    renderPage();

    expect(await screen.findByText('Agua mineral')).toBeInTheDocument();
    expect(screen.getByText('$240.00')).toBeInTheDocument();
    expect(reads).toBe(2);
  });

  it('preserves the terminal session-closed experience', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/account-preview')) return Promise.resolve(response({
        error: { code: 'session_closed', state: 'SESSION_CLOSED', message: 'Session closed' },
      }, 409));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    await waitFor(() => expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull());
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/account-preview'))).toHaveLength(1);
  });
});
