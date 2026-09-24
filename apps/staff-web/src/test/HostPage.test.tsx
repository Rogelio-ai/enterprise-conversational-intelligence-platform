import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CurrentServiceSession, ServiceResponsibility, StaffIdentity, TableWaiterAssignmentSet } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const hostIdentity: StaffIdentity = {
  username: 'host',
  user_id: 7,
  email: 'host@example.test',
  display_name: 'Ana Host',
  tenant_id: 11,
  membership_id: 13,
  authorized_location_ids: [21],
  roles: ['HOST'],
  permissions: ['location.read', 'resource.read', 'resource.manage', 'restaurant_service.read', 'restaurant_service.manage'],
  location_authorities: [{
    location_id: 21,
    roles: ['HOST'],
    permissions: ['location.read', 'resource.read', 'resource.manage', 'restaurant_service.read', 'restaurant_service.manage'],
  }],
};

const location = { id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' };
const tables = [
  { id: 101, tenant_id: 11, location_id: 21, code: 'M01', name: 'Mesa 1', resource_type: 'TABLE', status: 'ACTIVE', created_at: '2026-09-07T12:00:00Z', updated_at: '2026-09-07T12:00:00Z' },
  { id: 102, tenant_id: 11, location_id: 21, code: 'M02', name: 'Mesa 2', resource_type: 'TABLE', status: 'ACTIVE', created_at: '2026-09-07T12:00:00Z', updated_at: '2026-09-07T12:00:00Z' },
];
const activeSession: CurrentServiceSession = {
  id: 501,
  resource_id: 102,
  party_size: 4,
  active_diner_count: 2,
  status: 'OPEN',
  join_context_key: 'authoritative-join-context',
  access_code_version: 1,
  opened_at: '2026-09-07T12:00:00Z',
};

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

async function tableCard(name: string) {
  return (await screen.findByRole('heading', { name })).closest('article') as HTMLElement;
}

interface MockOptions {
  identity?: StaffIdentity;
  tableResponse?: Promise<Response>;
  current?: Record<number, Array<CurrentServiceSession | null>>;
  openResponse?: Promise<Response>;
  closeStatus?: number;
  responsibility?: ServiceResponsibility;
  responsibilityPutStatus?: number;
}

function mockHostApi(options: MockOptions = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const currentCounts = new Map<number, number>();
  const responsibilityCounts = new Map<number, number>();
  const assignmentState: Record<number, TableWaiterAssignmentSet> = {
    101: { table_resource_id: 101, location_id: 21, configured: false, version: 0, assignments: [] },
    102: { table_resource_id: 102, location_id: 21, configured: true, version: 3, assignments: [
      { membership_id: 201, display_name: 'Luis', email: 'luis@example.test', is_responsible: true },
      { membership_id: 202, display_name: 'María', email: 'maria@example.test', is_responsible: false },
      { membership_id: 203, display_name: 'Pedro', email: 'pedro@example.test', is_responsible: false },
    ] },
  };
  let responsibilityState: ServiceResponsibility = options.responsibility ?? {
    service_session_id: 501,
    status: 'OPEN',
    initialized: true,
    version: 1,
    responsible_membership_ids: [202, 203],
    responsible_waiters: [
      { membership_id: 202, display_name: 'María', email: 'maria@example.test' },
      { membership_id: 203, display_name: 'Pedro', email: 'pedro@example.test' },
    ],
    replayed: false,
  };
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(options.identity ?? hostIdentity);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.endsWith('/locations/21/tables/eligible-waiters')) return json({ items: [
      { membership_id: 201, display_name: 'Luis', email: 'luis@example.test' },
      { membership_id: 202, display_name: 'María', email: 'maria@example.test' },
      { membership_id: 203, display_name: 'Pedro', email: 'pedro@example.test' },
    ] });
    const assignmentMatch = url.match(/\/locations\/21\/tables\/(\d+)\/waiter-assignments$/);
    if (assignmentMatch) {
      const tableId = Number(assignmentMatch[1]);
      if (init?.method === 'POST') {
        const payload = JSON.parse(String(init.body));
        assignmentState[tableId] = {
          ...assignmentState[tableId], configured: true,
          version: assignmentState[tableId].version + 1,
          assignments: [...assignmentState[tableId].assignments, {
            membership_id: payload.waiter_membership_id,
            display_name: payload.waiter_membership_id === 201 ? 'Luis' : 'María',
            email: payload.waiter_membership_id === 201 ? 'luis@example.test' : 'maria@example.test',
            is_responsible: assignmentState[tableId].assignments.length === 0,
          }],
        };
      }
      return json(assignmentState[tableId], init?.method === 'POST' ? 201 : 200);
    }
    const responsibleMatch = url.match(/\/locations\/21\/tables\/(\d+)\/responsible-waiters$/);
    if (responsibleMatch && init?.method === 'PUT') {
      const tableId = Number(responsibleMatch[1]);
      const payload = JSON.parse(String(init.body));
      assignmentState[tableId] = { ...assignmentState[tableId], version: assignmentState[tableId].version + 1, assignments: assignmentState[tableId].assignments.map((waiter) => ({ ...waiter, is_responsible: payload.responsible_membership_ids.includes(waiter.membership_id) })) };
      return json(assignmentState[tableId]);
    }
    const unassignMatch = url.match(/\/locations\/21\/tables\/(\d+)\/waiter-assignments\/(\d+):unassign$/);
    if (unassignMatch && init?.method === 'POST') {
      const tableId = Number(unassignMatch[1]);
      const waiterId = Number(unassignMatch[2]);
      const payload = JSON.parse(String(init.body));
      assignmentState[tableId] = { ...assignmentState[tableId], version: assignmentState[tableId].version + 1, assignments: assignmentState[tableId].assignments.filter((waiter) => waiter.membership_id !== waiterId).map((waiter) => ({ ...waiter, is_responsible: payload.replacement_responsible_membership_ids.includes(waiter.membership_id) || waiter.is_responsible })) };
      return json(assignmentState[tableId]);
    }
    const currentMatch = url.match(/\/resources\/(\d+)\/service-sessions\/current$/);
    if (currentMatch) {
      const id = Number(currentMatch[1]);
      const count = currentCounts.get(id) ?? 0;
      currentCounts.set(id, count + 1);
      const sequence = options.current?.[id] ?? [id === 102 ? activeSession : null];
      const value = sequence[Math.min(count, sequence.length - 1)];
      return value ? json(value) : json({ detail: 'Service session not found' }, 404);
    }
    const serviceResponsibilityMatch = url.match(/\/locations\/21\/restaurant-service-sessions\/(\d+)\/responsibility$/);
    if (serviceResponsibilityMatch) {
      const sessionId = Number(serviceResponsibilityMatch[1]);
      if (init?.method === 'PUT') {
        if (options.responsibilityPutStatus) return json({ error: { code: 'SERVICE_RESPONSIBILITY_VERSION_CONFLICT', message: 'Service responsibility changed; refresh and retry' } }, options.responsibilityPutStatus);
        const payload = JSON.parse(String(init.body));
        const tableId = sessionId === 501 ? 102 : 101;
        const assignments = assignmentState[tableId]?.assignments ?? [];
        responsibilityState = {
          ...responsibilityState,
          service_session_id: sessionId,
          version: (responsibilityState.version ?? 0) + 1,
          responsible_membership_ids: payload.responsible_membership_ids,
          responsible_waiters: assignments.filter((waiter) => payload.responsible_membership_ids.includes(waiter.membership_id)).map(({ membership_id, display_name, email }) => ({ membership_id, display_name, email })),
        };
      } else {
        responsibilityCounts.set(sessionId, (responsibilityCounts.get(sessionId) ?? 0) + 1);
      }
      return json({ ...responsibilityState, service_session_id: sessionId });
    }
    if (url.includes('/resources?')) return options.tableResponse ?? json({ items: tables, limit: 100, offset: 0 });
    if (url.endsWith('/resources/101/service-sessions') && init?.method === 'POST') {
      return options.openResponse ?? json({ id: 601, resource_id: 101, party_size: 3, status: 'OPEN', join_context_key: 'new-join-context', access_code: '4827', access_code_version: 1, opened_at: '2026-09-07T13:00:00Z' }, 201);
    }
    if (url.endsWith('/restaurant-service-sessions/501/access-code/regenerate') && init?.method === 'POST') {
      return json({ id: 501, access_code: '7301', access_code_version: 2 });
    }
    if (url.endsWith('/restaurant-service-sessions/501/close') && init?.method === 'POST') {
      if (options.closeStatus) return json({ detail: { code: 'CHECK_NOT_SETTLED', message: 'Restaurant Check must be settled before closing service' } }, options.closeStatus);
      return json({ id: 501, resource_id: 102, status: 'CLOSED', closed_at: '2026-09-07T14:00:00Z' });
    }
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls, currentCounts, responsibilityCounts };
}

function renderHost() {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Restaurantes Norte' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/host']}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('Host table operations', () => {
  it('loads TABLE resources only from the active location and derives authoritative states', async () => {
    const { calls } = mockHostApi();
    renderHost();
    expect(await screen.findByRole('heading', { name: 'Mesas en servicio' })).toBeVisible();
    expect(await screen.findByRole('heading', { name: 'Mesa 1' })).toBeVisible();
    expect(await within(await tableCard('Mesa 1')).findByText('Disponible')).toBeVisible();
    expect(await within(await tableCard('Mesa 2')).findByText('En servicio')).toBeVisible();
    expect(within(await tableCard('Mesa 2')).getByText('2')).toBeVisible();
    const resourceCall = calls.find((call) => call.url.includes('/resources?'));
    expect(resourceCall?.url).toContain('location_id=21');
    expect(resourceCall?.url).toContain('resource_type=TABLE');
    expect(resourceCall?.url).toContain('status=ACTIVE');
    expect(calls.some((call) => call.url.includes('location_id=22'))).toBe(false);
    expect(calls.every((call) => !call.init?.method || call.init.method === 'GET')).toBe(true);
    expect(calls.every((call) => !/kitchen|cash|payment|billing|manager/i.test(call.url))).toBe(true);
  });

  it('does not fabricate availability while the resource list is loading', async () => {
    mockHostApi({ tableResponse: new Promise<Response>(() => undefined) });
    renderHost();
    expect(await screen.findByText('Cargando mesas')).toBeVisible();
    expect(screen.getByText('Aún no determinamos disponibilidad.')).toBeVisible();
    expect(screen.queryByText('Disponible')).not.toBeInTheDocument();
  });

  it('prevents unauthorized staff from loading or operating the Host workspace', async () => {
    const { calls } = mockHostApi({ identity: { ...hostIdentity, permissions: ['location.read'] } });
    renderHost();
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    expect(calls.some((call) => call.url.includes('/resources?'))).toBe(false);
    expect(screen.queryByRole('button', { name: 'Abrir mesa' })).not.toBeInTheDocument();
  });

  it('opens a selected available table once with the exact party-size contract and displays backend handoff data', async () => {
    let resolveOpen!: (response: Response) => void;
    const openResponse = new Promise<Response>((resolve) => { resolveOpen = resolve; });
    const { calls } = mockHostApi({ openResponse, current: { 101: [null, { ...activeSession, id: 601, resource_id: 101, party_size: 3, active_diner_count: 0, join_context_key: 'new-join-context' }], 102: [activeSession] } });
    renderHost();
    const user = userEvent.setup();
    await user.click(await within(await tableCard('Mesa 1')).findByRole('button', { name: 'Abrir mesa' }));
    await user.clear(screen.getByLabelText('Tamaño del grupo'));
    await user.type(screen.getByLabelText('Tamaño del grupo'), '3');
    await user.click(screen.getByRole('button', { name: 'Confirmar apertura' }));
    expect(screen.getByRole('button', { name: 'Abriendo…' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Abriendo…' }));
    expect(calls.filter((call) => call.url.endsWith('/resources/101/service-sessions') && call.init?.method === 'POST')).toHaveLength(1);
    resolveOpen(new Response(JSON.stringify({ id: 601, resource_id: 101, party_size: 3, status: 'OPEN', join_context_key: 'new-join-context', access_code: '4827', access_code_version: 1, opened_at: '2026-09-07T13:00:00Z' }), { status: 201, headers: { 'Content-Type': 'application/json' } }));
    expect(await screen.findByText('4827')).toBeVisible();
    expect(screen.getByText('new-join-context')).toBeVisible();
    const openCall = calls.find((call) => call.url.endsWith('/resources/101/service-sessions') && call.init?.method === 'POST');
    expect(JSON.parse(String(openCall?.init?.body))).toEqual({ party_size: 3 });
  });

  it('reconstructs an active session after refresh without fabricating the one-time access code', async () => {
    mockHostApi();
    renderHost();
    const card = await tableCard('Mesa 2');
    expect(await within(card).findByText('En servicio')).toBeVisible();
    expect(within(card).getByText('#501')).toBeVisible();
    expect(within(card).getByText('4')).toBeVisible();
    expect(within(card).queryByRole('button', { name: 'Abrir mesa' })).not.toBeInTheDocument();
    expect(screen.queryByText('7301')).not.toBeInTheDocument();
  });

  it('regenerates a lost code through backend authority and presents the returned value', async () => {
    const { calls } = mockHostApi();
    renderHost();
    const user = userEvent.setup();
    await user.click(await within(await tableCard('Mesa 2')).findByRole('button', { name: 'Nuevo código' }));
    expect(await screen.findByText('7301')).toBeVisible();
    expect(calls.some((call) => call.url.endsWith('/restaurant-service-sessions/501/access-code/regenerate') && call.init?.method === 'POST')).toBe(true);
  });

  it('revalidates and shows the latest state when another actor opens the table first', async () => {
    const occupied = { ...activeSession, id: 602, resource_id: 101, active_diner_count: 1 };
    const openConflict = json({ detail: 'Resource already has an open service session' }, 409);
    const { currentCounts } = mockHostApi({ openResponse: openConflict, current: { 101: [null, occupied], 102: [activeSession] } });
    renderHost();
    const user = userEvent.setup();
    await user.click(await within(await tableCard('Mesa 1')).findByRole('button', { name: 'Abrir mesa' }));
    await user.click(screen.getByRole('button', { name: 'Confirmar apertura' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El estado cambió');
    await waitFor(() => expect(currentCounts.get(101)).toBeGreaterThanOrEqual(2));
    expect(await within(await tableCard('Mesa 1')).findByText('En servicio')).toBeVisible();
  });

  it('closes through the authoritative endpoint and reconstructs the released table state', async () => {
    const { calls } = mockHostApi({ current: { 101: [null], 102: [activeSession, null] } });
    renderHost();
    const user = userEvent.setup();
    await user.click(await within(await tableCard('Mesa 2')).findByRole('button', { name: 'Cerrar mesa' }));
    expect(screen.getByRole('alertdialog')).toHaveTextContent('sesiones activas de comensales terminarán');
    await user.click(screen.getByRole('button', { name: 'Cerrar y liberar' }));
    expect(await screen.findByRole('status')).toHaveTextContent('cerrada y liberada');
    expect(await within(await tableCard('Mesa 2')).findByText('Disponible')).toBeVisible();
    expect(calls.some((call) => call.url.endsWith('/restaurant-service-sessions/501/close') && call.init?.method === 'POST')).toBe(true);
  });

  it('never overrides a blocked closure and revalidates authoritative state', async () => {
    const { currentCounts } = mockHostApi({ closeStatus: 409 });
    renderHost();
    const user = userEvent.setup();
    await user.click(await within(await tableCard('Mesa 2')).findByRole('button', { name: 'Cerrar mesa' }));
    await user.click(screen.getByRole('button', { name: 'Cerrar y liberar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Restaurant Check must be settled before closing service');
    expect(await within(await tableCard('Mesa 2')).findByText('En servicio')).toBeVisible();
    expect(currentCounts.get(102)).toBeGreaterThanOrEqual(2);
  });

  it('assigns the first eligible waiter and presents automatic responsibility', async () => {
    const { calls } = mockHostApi();
    renderHost();
    const user = userEvent.setup();
    const card = await tableCard('Mesa 1');
    await user.click(await within(card).findByRole('button', { name: 'Gestionar meseros' }));
    await user.selectOptions(screen.getByLabelText('Mesero elegible'), '201');
    await user.click(screen.getByRole('button', { name: 'Asignar mesero' }));
    expect(await screen.findByRole('status')).toHaveTextContent('asignación de la mesa');
    expect(await within(card).findByText('Luis')).toBeVisible();
    expect(within(card).getByText('Responsable')).toBeVisible();
    const call = calls.find((value) => value.url.endsWith('/locations/21/tables/101/waiter-assignments') && value.init?.method === 'POST');
    expect(JSON.parse(String(call?.init?.body))).toEqual({ waiter_membership_id: 201, expected_version: 0 });
  });

  it('requires manual replacement before removing the sole responsible waiter from a multi-waiter table', async () => {
    const { calls } = mockHostApi();
    renderHost();
    const user = userEvent.setup();
    const card = await tableCard('Mesa 2');
    await user.click(await within(card).findByRole('button', { name: 'Gestionar meseros' }));
    const dialog = screen.getByRole('dialog', { name: 'Mesa 2' });
    const luisRow = within(dialog).getByLabelText(/Luis/).closest('.staffing-list > div') as HTMLElement;
    await user.click(within(luisRow).getByRole('button', { name: 'Desasignar' }));
    const confirm = screen.getByRole('button', { name: 'Confirmar desasignación' });
    expect(confirm).toBeDisabled();
    await user.click(screen.getByLabelText(/^María$/));
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    await waitFor(() => expect(calls.some((value) => value.url.endsWith('/waiter-assignments/201:unassign') && value.init?.method === 'POST')).toBe(true));
    const call = calls.find((value) => value.url.endsWith('/waiter-assignments/201:unassign'));
    expect(JSON.parse(String(call?.init?.body))).toEqual({ replacement_responsible_membership_ids: [202], expected_version: 3 });
  });

  it('updates a shared responsible set without changing assignments', async () => {
    const { calls } = mockHostApi();
    renderHost();
    const user = userEvent.setup();
    const card = await tableCard('Mesa 2');
    await user.click(await within(card).findByRole('button', { name: 'Gestionar meseros' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Mesa 2' })).getByLabelText(/María/));
    await user.click(screen.getByRole('button', { name: 'Guardar responsables' }));
    const call = await waitFor(() => calls.find((value) => value.url.endsWith('/responsible-waiters') && value.init?.method === 'PUT'));
    expect(JSON.parse(String(call?.init?.body))).toEqual({ responsible_membership_ids: [201, 202], expected_version: 3 });
  });

  it('displays multiple SERVICE responsible waiters separately from TABLE staffing', async () => {
    mockHostApi();
    renderHost();
    const card = await tableCard('Mesa 2');
    const service = await within(card).findByRole('region', { name: 'Responsables del servicio de Mesa 2' });
    expect(within(service).getByText('María')).toBeVisible();
    expect(within(service).getByText('Pedro')).toBeVisible();
    expect(within(service).queryByText('Luis')).not.toBeInTheDocument();
    const table = within(card).getByRole('region', { name: 'Meseros asignados a Mesa 2' });
    expect(within(table).getByText('Luis')).toBeVisible();
    expect(within(table).getByText('Responsable')).toBeVisible();
  });

  it('replaces the complete SERVICE set from TABLE-assigned candidates and revalidates it', async () => {
    const { calls, responsibilityCounts } = mockHostApi();
    renderHost();
    const user = userEvent.setup();
    const card = await tableCard('Mesa 2');
    await user.click(await within(card).findByRole('button', { name: 'Cambiar responsables del servicio' }));
    const dialog = screen.getByRole('dialog', { name: /Mesa 2 · Servicio #501/ });
    expect(within(dialog).getByLabelText(/Luis/)).not.toBeChecked();
    expect(within(dialog).getByLabelText(/María/)).toBeChecked();
    expect(within(dialog).getByLabelText(/Pedro/)).toBeChecked();
    await user.click(within(dialog).getByLabelText(/Luis/));
    await user.click(screen.getByRole('button', { name: 'Guardar responsables del servicio' }));
    const transition = await waitFor(() => calls.find((value) => value.url.endsWith('/restaurant-service-sessions/501/responsibility') && value.init?.method === 'PUT'));
    expect(JSON.parse(String(transition?.init?.body))).toEqual({ responsible_membership_ids: [202, 203, 201], expected_version: 1 });
    expect(new Headers(transition?.init?.headers).get('Idempotency-Key')).toMatch(/^service-responsibility-501-/);
    await waitFor(() => expect(responsibilityCounts.get(501)).toBeGreaterThanOrEqual(2));
    expect(await screen.findByRole('status')).toHaveTextContent('responsabilidad del servicio quedó actualizada');
    const refreshed = within(await tableCard('Mesa 2')).getByRole('region', { name: 'Responsables del servicio de Mesa 2' });
    expect(await within(refreshed).findByText('Luis')).toBeVisible();
  });

  it('allows one SERVICE responsible waiter but never submits an empty set', async () => {
    const { calls } = mockHostApi();
    renderHost();
    const user = userEvent.setup();
    const card = await tableCard('Mesa 2');
    await user.click(await within(card).findByRole('button', { name: 'Cambiar responsables del servicio' }));
    const dialog = screen.getByRole('dialog', { name: /Mesa 2 · Servicio #501/ });
    await user.click(within(dialog).getByLabelText(/Pedro/));
    await user.click(screen.getByRole('button', { name: 'Guardar responsables del servicio' }));
    const transition = await waitFor(() => calls.find((value) => value.url.endsWith('/restaurant-service-sessions/501/responsibility') && value.init?.method === 'PUT'));
    expect(JSON.parse(String(transition?.init?.body))).toEqual({ responsible_membership_ids: [202], expected_version: 1 });

    await user.click(await within(await tableCard('Mesa 2')).findByRole('button', { name: 'Cambiar responsables del servicio' }));
    await user.click(screen.getByRole('dialog', { name: /Mesa 2 · Servicio #501/ }).querySelector('input:checked') as HTMLElement);
    expect(screen.getByText('Selecciona al menos un responsable del servicio.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Guardar responsables del servicio' })).toBeDisabled();
    expect(calls.filter((value) => value.url.endsWith('/restaurant-service-sessions/501/responsibility') && value.init?.method === 'PUT')).toHaveLength(1);
  });

  it('shows a controlled conflict and revalidates canonical SERVICE responsibility', async () => {
    const { responsibilityCounts } = mockHostApi({ responsibilityPutStatus: 409 });
    renderHost();
    const user = userEvent.setup();
    const card = await tableCard('Mesa 2');
    await user.click(await within(card).findByRole('button', { name: 'Cambiar responsables del servicio' }));
    await user.click(screen.getByLabelText(/Luis/));
    await user.click(screen.getByRole('button', { name: 'Guardar responsables del servicio' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Service responsibility changed; refresh and retry');
    await waitFor(() => expect(responsibilityCounts.get(501)).toBeGreaterThanOrEqual(2));
    expect(screen.getByRole('dialog', { name: /Mesa 2 · Servicio #501/ })).toBeVisible();
  });

  it('shows legacy uninitialized responsibility without fabricating or offering transition', async () => {
    mockHostApi({ responsibility: {
      service_session_id: 501, status: 'OPEN', initialized: false, version: null,
      responsible_membership_ids: [], responsible_waiters: [], replayed: false,
    } });
    renderHost();
    const service = await within(await tableCard('Mesa 2')).findByRole('region', { name: 'Responsables del servicio de Mesa 2' });
    expect(within(service).getByText('Responsabilidad del servicio no inicializada')).toBeVisible();
    expect(within(service).queryByText('Luis')).not.toBeInTheDocument();
    expect(within(service).queryByRole('button', { name: 'Cambiar responsables del servicio' })).not.toBeInTheDocument();
  });

  it('keeps CLOSED responsibility read-only', async () => {
    mockHostApi({ responsibility: {
      service_session_id: 501, status: 'CLOSED', initialized: true, version: 4,
      responsible_membership_ids: [202], responsible_waiters: [
        { membership_id: 202, display_name: 'María', email: 'maria@example.test' },
      ], replayed: false,
    } });
    renderHost();
    const service = await within(await tableCard('Mesa 2')).findByRole('region', { name: 'Responsables del servicio de Mesa 2' });
    expect(within(service).getByText('María')).toBeVisible();
    expect(within(service).queryByRole('button', { name: 'Cambiar responsables del servicio' })).not.toBeInTheDocument();
  });
});
