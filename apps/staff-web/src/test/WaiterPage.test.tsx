import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StaffIdentity, StaffOperationalRequest } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const waiterIdentity: StaffIdentity = {
  user_id: 7, username: 'waiter', email: 'waiter@example.test', display_name: 'Ana Mesera', tenant_id: 11,
  membership_id: 13, authorized_location_ids: [21], roles: ['WAITER'],
  permissions: ['location.read', 'restaurant_service.read', 'restaurant_order.read', 'restaurant_check.read', 'operational_request.read', 'operational_request.manage'],
  location_authorities: [{
    location_id: 21,
    roles: ['WAITER'],
    permissions: ['location.read', 'restaurant_service.read', 'restaurant_order.read', 'restaurant_check.read', 'operational_request.read', 'operational_request.manage'],
  }],
};
const location = { id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' };

function operationalRequest(id: number, overrides: Partial<StaffOperationalRequest> = {}): StaffOperationalRequest {
  return {
    id, organization_id: 31, location_id: 21, resource_id: 101, resource_code: 'M01', resource_name: 'Mesa 1',
    service_session_id: 501, diner_session_id: 601, diner_display_name: 'Diner seguro', request_type: 'HUMAN_ASSISTANCE',
    status: 'PENDING', related_restaurant_check_id: null, preparation_work_id: null, restaurant_order_id: null,
    preparation_area_id: null, preparation_area_code: null, preparation_area_name: null, picked_up_by_membership_id: null,
    picked_up_at: null, delivered_by_membership_id: null, delivered_at: null, acknowledged_by_membership_id: null,
    acknowledged_at: null, resolved_by_membership_id: null, resolved_at: null, current_waiter_entered_at: null,
    current_waiter_hidden_at: null, created_at: '2026-09-08T12:00:00Z', updated_at: '2026-09-08T12:00:00Z', ...overrides,
  };
}

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

interface MockOptions {
  identity?: StaffIdentity;
  requests?: StaffOperationalRequest[];
  listResponse?: Promise<Response>;
  pendingAction?: { action: string; response: Promise<Response> };
  conflictAction?: string;
  notFoundAction?: string;
  respondFailures?: number;
}

function mockWaiterApi(options: MockOptions = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let values = options.requests ?? [operationalRequest(9001)];
  let conflict = options.conflictAction;
  let notFound = options.notFoundAction;
  let respondFailures = options.respondFailures ?? 0;
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(options.identity ?? waiterIdentity);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/waiter/operational-requests?')) {
      if (options.listResponse) return options.listResponse;
      const view = new URL(url, 'http://staff.test').searchParams.get('view');
      const items = values.filter((request) => view === 'hidden'
        ? Boolean(request.current_waiter_hidden_at) && !['COMPLETED', 'CANCELLED'].includes(request.status)
        : !request.current_waiter_hidden_at);
      return json({ items, limit: 100, offset: 0 });
    }
    const match = url.match(/\/waiter\/operational-requests\/(\d+)\/(entered|hide|show|acknowledge|complete|pick-up|deliver|respond)\?/);
    if (match && init?.method === 'POST') {
      const id = Number(match[1]);
      const action = match[2];
      if (options.pendingAction?.action === action) return options.pendingAction.response;
      if (conflict === action) { conflict = undefined; return json({ detail: { code: 'OPERATIONAL_REQUEST_STATE_CONFLICT', message: 'changed' } }, 409); }
      if (notFound === action) { notFound = undefined; values = values.filter((value) => value.id !== id); return json({ detail: 'Not found' }, 404); }
      if (action === 'respond') {
        if (respondFailures > 0) { respondFailures -= 1; return Promise.reject(new Error('offline')); }
        return json({ message_id: 81, conversation_id: 71, operational_request_id: id, participant_id: 61, author_type: 'STAFF', sequence_number: 2, modality: 'TEXT', content_text: JSON.parse(String(init.body)).content_text, language: null, language_source: null, created_at: '2026-09-08T12:05:00Z' });
      }
      values = values.map((request) => request.id !== id ? request : ({
        ...request,
        ...(action === 'entered' ? { current_waiter_entered_at: '2026-09-08T12:01:00Z' } : {}),
        ...(action === 'hide' ? { current_waiter_hidden_at: '2026-09-08T12:02:00Z' } : {}),
        ...(action === 'show' ? { current_waiter_hidden_at: null } : {}),
        ...(action === 'acknowledge' ? { status: 'ACKNOWLEDGED' as const, acknowledged_by_membership_id: 77, acknowledged_by_display_name: 'Luis Mesero', acknowledged_at: '2026-09-08T12:03:00Z' } : {}),
        ...(action === 'complete' ? { status: 'COMPLETED' as const, resolved_by_membership_id: 78, resolved_at: '2026-09-08T12:04:00Z' } : {}),
        ...(action === 'pick-up' ? { picked_up_by_membership_id: 79, picked_up_at: '2026-09-08T12:03:00Z' } : {}),
        ...(action === 'deliver' ? { status: 'COMPLETED' as const, delivered_by_membership_id: 80, delivered_at: '2026-09-08T12:04:00Z', resolved_by_membership_id: 80, resolved_at: '2026-09-08T12:04:00Z' } : {}),
      }));
      return json(values.find((request) => request.id === id));
    }
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls, setRequests(next: StaffOperationalRequest[]) { values = next; } };
}

function renderWaiter() {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Restaurantes Norte' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={['/waiter']}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter></ThemeProvider></QueryClientProvider>);
}

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('Waiter Message Center MP8', () => {
  it('defaults to ACTIVOS, switches canonically to OCULTOS, and has distinct empty states', async () => {
    const active = operationalRequest(1);
    const hidden = operationalRequest(2, { resource_name: 'Mesa 2', current_waiter_hidden_at: '2026-09-08T12:02:00Z' });
    const api = mockWaiterApi({ requests: [active, hidden] });
    renderWaiter();
    const user = userEvent.setup();
    expect(await screen.findByRole('heading', { name: 'Mesa 1' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Mesa 2' })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'ACTIVOS' })).toHaveAttribute('aria-selected', 'true');
    expect(api.calls.find((call) => call.url.includes('/waiter/operational-requests?'))?.url).toContain('view=active');
    await user.click(screen.getByRole('tab', { name: 'OCULTOS' }));
    expect(await screen.findByRole('heading', { name: 'Mesa 2' })).toBeVisible();
    expect(api.calls.some((call) => call.url.includes('view=hidden'))).toBe(true);
    api.setRequests([]);
    await user.click(screen.getByRole('button', { name: 'Actualizar' }));
    expect(await screen.findByRole('heading', { name: 'No hay solicitudes ocultas.' })).toBeVisible();
    await user.click(screen.getByRole('tab', { name: 'ACTIVOS' }));
    expect(await screen.findByRole('heading', { name: 'No hay solicitudes activas.' })).toBeVisible();
  });

  it('refreshes the selected view manually and through the 15-second poll without auto-enterado', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = mockWaiterApi({ requests: [operationalRequest(1)] });
    renderWaiter();
    await screen.findByRole('heading', { name: 'Mesa 1' });
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(screen.getByRole('tab', { name: 'OCULTOS' }));
    await screen.findByRole('heading', { name: 'No hay solicitudes ocultas.' });
    const before = api.calls.filter((call) => call.url.includes('view=hidden')).length;
    await act(() => vi.advanceTimersByTimeAsync(15_000));
    await waitFor(() => expect(api.calls.filter((call) => call.url.includes('view=hidden')).length).toBeGreaterThan(before));
    expect(api.calls.some((call) => call.url.includes('/entered?'))).toBe(false);
  });

  it('records Enterado canonically and hide/show refetch their current views without fabricating awareness', async () => {
    const api = mockWaiterApi({ requests: [operationalRequest(1)] });
    renderWaiter();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Enterado' }));
    expect(await screen.findByText('Enterado', { selector: 'dt' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Enterado' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Ocultar' }));
    expect(await screen.findByRole('heading', { name: 'No hay solicitudes activas.' })).toBeVisible();
    await user.click(screen.getByRole('tab', { name: 'OCULTOS' }));
    expect(await screen.findByRole('button', { name: 'Mostrar' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Mostrar' }));
    expect(await screen.findByRole('heading', { name: 'No hay solicitudes ocultas.' })).toBeVisible();
    expect(api.calls.filter((call) => call.url.includes('/waiter/operational-requests?')).length).toBeGreaterThanOrEqual(5);

    cleanup(); vi.unstubAllGlobals();
    mockWaiterApi({ requests: [operationalRequest(3, { current_waiter_hidden_at: '2026-09-08T12:02:00Z' })] });
    renderWaiter();
    await userEvent.setup().click(await screen.findByRole('tab', { name: 'OCULTOS' }));
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Mostrar' }));
    await screen.findByRole('heading', { name: 'No hay solicitudes ocultas.' });
    expect(screen.queryByText('Enterado', { selector: 'dt' })).not.toBeInTheDocument();
  });

  it('uses canonical lifecycle actors and completion evidence', async () => {
    mockWaiterApi({ requests: [operationalRequest(1)] });
    renderWaiter();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Atendido' }));
    expect(await screen.findByText(/Luis Mesero/)).toBeVisible();
    expect(screen.getByText('En atención')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'Completar' }));
    expect(await screen.findByText('Completada')).toBeVisible();
    expect(screen.getByText(/Miembro #78/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Completar' })).not.toBeInTheDocument();
  });

  it('renders PREPARATION_READY without a fake diner and enforces pickup then delivery', async () => {
    const preparation = operationalRequest(10, { request_type: 'PREPARATION_READY', diner_session_id: null, diner_display_name: null, preparation_work_id: 310, restaurant_order_id: 210, preparation_area_id: 41, preparation_area_code: 'PASE', preparation_area_name: 'Pase caliente' });
    mockWaiterApi({ requests: [preparation] });
    renderWaiter();
    const user = userEvent.setup();
    const card = (await screen.findByText('Preparación lista')).closest('article')!;
    expect(within(card).getByText('Pase caliente · PASE')).toBeVisible();
    expect(within(card).queryByText('Comensal')).not.toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: 'Completar' })).not.toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: 'Responder' })).not.toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Recogido' }));
    expect(await within(card).findByText(/Miembro #79/)).toBeVisible();
    await user.click(within(card).getByRole('button', { name: 'Entregado' }));
    expect(await within(card).findByText('Completada')).toBeVisible();
    expect(within(card).getAllByText(/Miembro #80/)).toHaveLength(2);
    expect(within(card).queryByRole('button', { name: 'Entregado' })).not.toBeInTheDocument();
  });

  it('offers Responder for diner PENDING, ACKNOWLEDGED, and COMPLETED but not CANCELLED', async () => {
    mockWaiterApi({ requests: [operationalRequest(1), operationalRequest(2, { status: 'ACKNOWLEDGED', resource_name: 'Mesa 2' }), operationalRequest(3, { status: 'COMPLETED', resource_name: 'Mesa 3' }), operationalRequest(4, { status: 'CANCELLED', resource_name: 'Mesa 4' })] });
    renderWaiter();
    await screen.findByRole('heading', { name: 'Mesa 1' });
    expect(screen.getAllByRole('button', { name: 'Responder' })).toHaveLength(3);
    expect(within(screen.getByRole('heading', { name: 'Mesa 4' }).closest('article')!).queryByRole('button', { name: 'Responder' })).not.toBeInTheDocument();
  });

  it('sends trimmed content with an idempotency key, disables duplicates, and preserves lifecycle', async () => {
    let resolveResponse!: (response: Response) => void;
    const response = new Promise<Response>((resolve) => { resolveResponse = resolve; });
    const api = mockWaiterApi({ pendingAction: { action: 'respond', response } });
    renderWaiter();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Responder' }));
    const input = screen.getByLabelText('Respuesta al comensal');
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled();
    await user.type(input, '  Voy en camino  ');
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    expect(screen.getByRole('button', { name: 'Enviando…' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Enviando…' }));
    expect(api.calls.filter((call) => call.url.includes('/respond?'))).toHaveLength(1);
    const call = api.calls.find((value) => value.url.includes('/respond?'))!;
    expect(JSON.parse(String(call.init?.body))).toEqual({ content_text: 'Voy en camino' });
    expect(new Headers(call.init?.headers).get('Idempotency-Key')).toBeTruthy();
    resolveResponse(await json({ message_id: 81 }));
    expect(await screen.findByRole('status')).toHaveTextContent('Respuesta disponible');
    expect(screen.getByText('Pendiente')).toBeVisible();
    expect(screen.queryByText('Enterado', { selector: 'dt' })).not.toBeInTheDocument();
  });

  it('reuses the key for the same failed response intent and rotates it when content changes', async () => {
    const api = mockWaiterApi({ respondFailures: 2 });
    renderWaiter();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Responder' }));
    const input = screen.getByLabelText('Respuesta al comensal');
    await user.type(input, 'Primera respuesta');
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    await screen.findByRole('alert');
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    await waitFor(() => expect(api.calls.filter((call) => call.url.includes('/respond?'))).toHaveLength(2));
    const firstTwo = api.calls.filter((call) => call.url.includes('/respond?'));
    expect(new Headers(firstTwo[0].init?.headers).get('Idempotency-Key')).toBe(new Headers(firstTwo[1].init?.headers).get('Idempotency-Key'));
    await user.clear(input);
    await user.type(input, 'Respuesta corregida');
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    await screen.findByRole('status');
    const responseCalls = api.calls.filter((call) => call.url.includes('/respond?'));
    expect(new Headers(responseCalls[2].init?.headers).get('Idempotency-Key')).not.toBe(new Headers(responseCalls[1].init?.headers).get('Idempotency-Key'));
  });

  it('refetches after a responder 409 and does not rotate the intent key to bypass it', async () => {
    const api = mockWaiterApi({ conflictAction: 'respond' });
    renderWaiter();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Responder' }));
    await user.type(screen.getByLabelText('Respuesta al comensal'), 'Confirmo tu solicitud');
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('estado canónico');
    expect(api.calls.filter((call) => call.url.includes('/waiter/operational-requests?')).length).toBeGreaterThanOrEqual(2);
    await user.click(screen.getByRole('button', { name: 'Enviar' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Respuesta disponible');
    const responseCalls = api.calls.filter((call) => call.url.includes('/respond?'));
    expect(responseCalls).toHaveLength(2);
    expect(new Headers(responseCalls[0].init?.headers).get('Idempotency-Key')).toBe(new Headers(responseCalls[1].init?.headers).get('Idempotency-Key'));
  });

  it('refetches on 409 and 404, distinguishes 403, and retains canonical state on network failure', async () => {
    const conflict = mockWaiterApi({ conflictAction: 'acknowledge' });
    renderWaiter();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Atendido' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('estado canónico');
    expect(conflict.calls.filter((call) => call.url.includes('/waiter/operational-requests?')).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Pendiente')).toBeVisible();

    cleanup(); vi.unstubAllGlobals();
    mockWaiterApi({ notFoundAction: 'hide' }); renderWaiter();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Ocultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('ya no está en tu ruta');
    expect(await screen.findByRole('heading', { name: 'No hay solicitudes activas.' })).toBeVisible();

    cleanup(); vi.unstubAllGlobals();
    mockWaiterApi({ pendingAction: { action: 'entered', response: json({ detail: 'Forbidden' }, 403) } }); renderWaiter();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Enterado' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya no tienes permiso');
    expect(screen.getByRole('button', { name: 'Enterado' })).toBeVisible();
  });

  it('provides explicit loading/error states and keeps action permission separate', async () => {
    const readOnly = { ...waiterIdentity, permissions: waiterIdentity.permissions.filter((value) => value !== 'operational_request.manage') };
    mockWaiterApi({ identity: readOnly }); renderWaiter();
    expect(await screen.findByText('Consulta solamente')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Atendido' })).not.toBeInTheDocument();

    cleanup(); vi.unstubAllGlobals();
    mockWaiterApi({ listResponse: new Promise<Response>(() => undefined) }); renderWaiter();
    expect(await screen.findByRole('heading', { name: 'Cargando activos' })).toBeVisible();

    cleanup(); vi.unstubAllGlobals();
    mockWaiterApi({ listResponse: json({ detail: 'Unavailable' }, 503) }); renderWaiter();
    expect(await screen.findByRole('heading', { name: 'No pudimos cargar los activos' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });
});
