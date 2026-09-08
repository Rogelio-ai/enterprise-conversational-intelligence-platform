import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  StaffIdentity,
  StaffOperationalRequest,
} from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const waiterIdentity: StaffIdentity = {
  user_id: 7,
  email: 'waiter@example.test',
  display_name: 'Ana Mesera',
  tenant_id: 11,
  membership_id: 13,
  authorized_location_ids: [21],
  roles: ['WAITER'],
  permissions: [
    'location.read',
    'restaurant_service.read',
    'restaurant_order.read',
    'restaurant_check.read',
    'operational_request.read',
    'operational_request.manage',
  ],
};

const location = {
  id: 21,
  tenant_id: 11,
  organization_id: 31,
  code: 'CENTRO',
  name: 'Sucursal Centro',
  timezone: 'America/Mexico_City',
  status: 'ACTIVE',
};

function operationalRequest(
  id: number,
  overrides: Partial<StaffOperationalRequest> = {},
): StaffOperationalRequest {
  return {
    id,
    organization_id: 31,
    location_id: 21,
    resource_id: 101,
    resource_code: 'M01',
    resource_name: 'Mesa 1',
    service_session_id: 501,
    diner_session_id: 601,
    diner_display_name: 'Diner seguro',
    request_type: 'HUMAN_ASSISTANCE',
    status: 'PENDING',
    related_restaurant_check_id: null,
    resolved_by_membership_id: null,
    resolved_at: null,
    created_at: '2026-09-08T12:00:00Z',
    updated_at: '2026-09-08T12:00:00Z',
    ...overrides,
  };
}

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  }));
}

interface MockOptions {
  identity?: StaffIdentity;
  requests?: StaffOperationalRequest[];
  listResponse?: Promise<Response>;
  acknowledgeResponse?: Promise<Response>;
  acknowledgeConflict?: boolean;
}

function mockWaiterApi(options: MockOptions = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let values = options.requests ?? [operationalRequest(9001)];
  let conflictPending = options.acknowledgeConflict ?? false;
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(options.identity ?? waiterIdentity);
    if (url.includes('/locations?')) {
      return json({ items: [location], limit: 100, offset: 0 });
    }
    if (url.includes('/staff/operational-requests?')) {
      if (options.listResponse) return options.listResponse;
      const query = new URL(url, 'http://staff.test').searchParams;
      const status = query.get('status');
      const requestType = query.get('request_type');
      const items = values.filter((request) => (
        (!status || request.status === status)
        && (!requestType || request.request_type === requestType)
      ));
      return json({ items, limit: 100, offset: 0 });
    }
    const acknowledge = url.match(/\/staff\/operational-requests\/(\d+)\/acknowledge\?/);
    if (acknowledge && init?.method === 'POST') {
      const id = Number(acknowledge[1]);
      if (conflictPending) {
        conflictPending = false;
        values = values.map((request) => request.id === id
          ? { ...request, status: 'ACKNOWLEDGED' }
          : request);
        return json({ detail: { code: 'OPERATIONAL_REQUEST_STATE_CONFLICT' } }, 409);
      }
      if (options.acknowledgeResponse) return options.acknowledgeResponse;
      values = values.map((request) => request.id === id
        ? { ...request, status: 'ACKNOWLEDGED' }
        : request);
      return json(values.find((request) => request.id === id));
    }
    const complete = url.match(/\/staff\/operational-requests\/(\d+)\/complete\?/);
    if (complete && init?.method === 'POST') {
      const id = Number(complete[1]);
      values = values.map((request) => request.id === id
        ? { ...request, status: 'COMPLETED', resolved_by_membership_id: 13 }
        : request);
      return json(values.find((request) => request.id === id));
    }
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls };
}

function renderWaiter() {
  storeCredential({
    accessToken: 'staff-token',
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    tenantId: 11,
    tenantName: 'Restaurantes Norte',
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/waiter']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('Waiter operational inbox', () => {
  it('loads only the active granted location and renders safe actionable context', async () => {
    const request = operationalRequest(9001);
    const { calls } = mockWaiterApi({ requests: [request] });
    renderWaiter();

    expect(await screen.findByRole('heading', { name: 'Solicitudes' })).toBeVisible();
    const card = (await screen.findByRole('heading', { name: 'Mesa 1' })).closest('article')!;
    expect(within(card).getByText('Ayuda al comensal')).toBeVisible();
    expect(within(card).getByText('Pendiente')).toBeVisible();
    expect(within(card).getByText('M01')).toBeVisible();
    expect(within(card).getByText('Diner seguro')).toBeVisible();
    expect(within(card).getByText('#501')).toBeVisible();
    expect(within(card).getByRole('button', { name: 'Atender' })).toBeVisible();
    const listCall = calls.find((call) => call.url.includes('/staff/operational-requests?'));
    expect(listCall?.url).toContain('location_id=21');
    expect(listCall?.url).toContain('status=PENDING');
    expect(calls.every((call) => !call.url.includes('location_id=22'))).toBe(true);
  });

  it('uses backend status and request-type filters without inventing priority', async () => {
    const requests = [
      operationalRequest(1),
      operationalRequest(2, { status: 'ACKNOWLEDGED', request_type: 'INVOICE_ASSISTANCE' }),
    ];
    const { calls } = mockWaiterApi({ requests });
    renderWaiter();
    const user = userEvent.setup();
    await screen.findByRole('heading', { name: 'Mesa 1' });

    await user.click(screen.getByRole('button', { name: 'En atención' }));
    expect(await screen.findByText('Solicitud de factura')).toBeVisible();
    await user.selectOptions(screen.getByLabelText('Tipo de solicitud'), 'INVOICE_ASSISTANCE');
    await waitFor(() => expect(calls.some((call) => (
      call.url.includes('status=ACKNOWLEDGED')
      && call.url.includes('request_type=INVOICE_ASSISTANCE')
    ))).toBe(true));
  });

  it('consumes the same durable request through acknowledge and complete with refetches', async () => {
    const { calls } = mockWaiterApi({ requests: [operationalRequest(9001)] });
    renderWaiter();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Atender' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Solicitud marcada en atención');
    await user.click(screen.getByRole('button', { name: 'En atención' }));
    await user.click(await screen.findByRole('button', { name: 'Completar' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Atención operativa completada');
    await user.click(screen.getByRole('button', { name: 'Completadas' }));
    expect(await screen.findByText('Completada')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Atender' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Completar' })).not.toBeInTheDocument();

    const mutationCalls = calls.filter((call) => call.init?.method === 'POST');
    expect(mutationCalls.map((call) => call.url)).toEqual([
      '/api/staff/operational-requests/9001/acknowledge?location_id=21',
      '/api/staff/operational-requests/9001/complete?location_id=21',
    ]);
    expect(calls.filter((call) => call.url.includes('/staff/operational-requests?')).length)
      .toBeGreaterThanOrEqual(4);
  });

  it('prevents duplicate submission and refreshes authoritative state after conflict', async () => {
    let resolveAcknowledge!: (response: Response) => void;
    const acknowledgeResponse = new Promise<Response>((resolve) => {
      resolveAcknowledge = resolve;
    });
    const pending = operationalRequest(9001);
    const first = mockWaiterApi({ requests: [pending], acknowledgeResponse });
    renderWaiter();
    const user = userEvent.setup();
    const action = await screen.findByRole('button', { name: 'Atender' });
    await user.click(action);
    expect(screen.getByRole('button', { name: 'Actualizando…' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Actualizando…' }));
    expect(first.calls.filter((call) => call.url.includes('/acknowledge?'))).toHaveLength(1);
    resolveAcknowledge(await json({ ...pending, status: 'ACKNOWLEDGED' }));
    await screen.findByRole('status');

    cleanup();
    vi.unstubAllGlobals();
    const second = mockWaiterApi({ requests: [pending], acknowledgeConflict: true });
    renderWaiter();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Todas' }));
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Atender' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('estado más reciente');
    expect((await screen.findAllByText('En atención')).length).toBeGreaterThanOrEqual(2);
    expect(second.calls.filter((call) => call.url.includes('/staff/operational-requests?')).length)
      .toBeGreaterThanOrEqual(2);
  });

  it('keeps terminal and non-waiter domain requests presentation-only beyond lifecycle actions', async () => {
    const requests = [
      operationalRequest(1, { status: 'COMPLETED' }),
      operationalRequest(2, { status: 'CANCELLED' }),
      operationalRequest(3, { request_type: 'CASH_PAYMENT_ASSISTANCE' }),
      operationalRequest(4, { request_type: 'INVOICE_ASSISTANCE' }),
      operationalRequest(5, { request_type: 'PAID_CHECK_PRINT' }),
    ];
    const { calls } = mockWaiterApi({ requests });
    renderWaiter();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Todas' }));

    expect(await screen.findByText('Completada')).toBeVisible();
    expect(screen.getByText('Cancelada')).toBeVisible();
    expect(screen.getByText('Pago en efectivo')).toBeVisible();
    expect(screen.getByText('Solicitud de factura')).toBeVisible();
    expect(screen.getByText('Cuenta impresa')).toBeVisible();
    expect(screen.getAllByText('Sin acciones pendientes')).toHaveLength(2);
    expect(calls.every((call) => !/payments|settlements|billing|fiscal|paid-print|dispatch/i.test(call.url)))
      .toBe(true);
  });

  it('separates route and action permissions and distinct loading, empty, and error states', async () => {
    const unauthorized = {
      ...waiterIdentity,
      permissions: waiterIdentity.permissions.filter((value) => value !== 'operational_request.read'),
    };
    const denied = mockWaiterApi({ identity: unauthorized });
    renderWaiter();
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    expect(denied.calls.some((call) => call.url.includes('/staff/operational-requests'))).toBe(false);

    cleanup();
    vi.unstubAllGlobals();
    const readOnly = {
      ...waiterIdentity,
      permissions: waiterIdentity.permissions.filter((value) => value !== 'operational_request.manage'),
    };
    mockWaiterApi({ identity: readOnly });
    renderWaiter();
    expect(await screen.findByText('Consulta solamente')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Atender' })).not.toBeInTheDocument();

    cleanup();
    vi.unstubAllGlobals();
    mockWaiterApi({ listResponse: new Promise<Response>(() => undefined) });
    renderWaiter();
    expect(await screen.findByRole('heading', { name: 'Cargando solicitudes' })).toBeVisible();

    cleanup();
    vi.unstubAllGlobals();
    mockWaiterApi({ requests: [] });
    renderWaiter();
    expect(await screen.findByRole('heading', { name: 'No hay solicitudes pendientes.' })).toBeVisible();

    cleanup();
    vi.unstubAllGlobals();
    mockWaiterApi({ listResponse: json({ detail: 'Inbox unavailable' }, 503) });
    renderWaiter();
    expect(await screen.findByRole('heading', { name: 'No pudimos cargar el inbox' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });
});
