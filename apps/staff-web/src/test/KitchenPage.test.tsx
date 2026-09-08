import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type {
  PreparationDispatch,
  PreparationWork,
  StaffIdentity,
} from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const kitchenIdentity: StaffIdentity = {
  user_id: 7,
  email: 'kitchen@example.test',
  display_name: 'Ana Cocina',
  tenant_id: 11,
  membership_id: 13,
  authorized_location_ids: [21],
  roles: ['KITCHEN'],
  permissions: ['location.read', 'preparation.read', 'preparation.execute', 'preparation.dispatch'],
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

function work(overrides: Partial<PreparationWork> = {}): PreparationWork {
  return {
    id: 501,
    preparation_area_id: 41,
    area_code: 'CALIENTE',
    area_name: 'Línea caliente',
    routed_at: '2026-09-08T12:05:00Z',
    execution_state: 'NEW',
    order: {
      restaurant_order_id: 7001,
      accepted_at: '2026-09-08T12:04:00Z',
      source_channel: 'DINE_IN',
      resource_id: 101,
      service_session_id: 201,
      diner_session_id: 301,
      current_resource_code: 'M08',
      current_resource_name: 'Mesa 8',
    },
    items: [{
      id: 601,
      preparation_work_id: 501,
      source_type: 'COMPONENT',
      source_restaurant_order_item_id: 801,
      source_restaurant_order_item_component_id: 901,
      product_name: 'Papas trufadas',
      parent_product_name: 'Hamburguesa especial',
      required_quantity: '2.000',
      execution_state: 'NEW',
      execution_version: 0,
    }],
    ...overrides,
  };
}

function dispatch(overrides: Partial<PreparationDispatch> = {}): PreparationDispatch {
  return {
    id: 1001,
    location_id: 21,
    preparation_work_id: 501,
    destination_id: 71,
    operation_kind: 'INITIAL',
    generation: 1,
    state: 'DESTINATION_SUBMISSION_ACCEPTED',
    destination_name: 'Impresora caliente',
    destination_channel: 'PRINTER',
    attempt_count: 1,
    last_error_kind: null,
    last_error_message: null,
    created_at: '2026-09-08T12:05:00Z',
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
  works?: PreparationWork[];
  worksResponse?: Promise<Response>;
  transitionResponse?: Promise<Response>;
  transitionConflict?: boolean;
  dispatches?: PreparationDispatch[];
  dispatchResponse?: Promise<Response>;
  reprintResponse?: Promise<Response>;
}

function mockKitchenApi(options: MockOptions = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let values = options.works ?? [work()];
  let printValues = options.dispatches ?? [dispatch()];
  let conflictPending = options.transitionConflict ?? false;
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(options.identity ?? kitchenIdentity);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/preparation-areas?')) return json({ items: [
      { id: 41, location_id: 21, code: 'CALIENTE', name: 'Línea caliente', status: 'ACTIVE' },
      { id: 42, location_id: 21, code: 'FRIA', name: 'Línea fría', status: 'ACTIVE' },
    ] });
    if (url.includes('/preparation-works?')) {
      if (options.worksResponse) return options.worksResponse;
      const query = new URL(url, 'http://staff.test').searchParams;
      const state = query.get('execution_state');
      const areaId = query.get('preparation_area_id');
      return json(values.filter((item) => (
        (!state || item.execution_state === state)
        && (!areaId || item.preparation_area_id === Number(areaId))
      )));
    }
    if (url.includes('/preparation-dispatches?')) {
      if (options.dispatchResponse) return options.dispatchResponse;
      return json(printValues);
    }
    const transition = url.match(/\/preparation-work-items\/(\d+)\/transitions$/);
    if (transition && init?.method === 'POST') {
      const itemId = Number(transition[1]);
      const body = JSON.parse(String(init.body)) as { to_state: 'NEW' | 'IN_PROGRESS' | 'COMPLETED' };
      if (conflictPending) {
        conflictPending = false;
        values = values.map((entry) => ({
          ...entry,
          execution_state: 'IN_PROGRESS',
          items: entry.items.map((item) => item.id === itemId
            ? { ...item, execution_state: 'IN_PROGRESS', execution_version: 1 }
            : item),
        }));
        return json({ detail: 'Preparation Work Item transition precondition failed' }, 409);
      }
      if (options.transitionResponse) return options.transitionResponse;
      values = values.map((entry) => ({
        ...entry,
        execution_state: body.to_state,
        items: entry.items.map((item) => item.id === itemId
          ? { ...item, execution_state: body.to_state, execution_version: item.execution_version + 1 }
          : item),
      }));
      return json({ current_execution_state: body.to_state, current_execution_version: 1, replayed: false }, 201);
    }
    const reprint = url.match(/\/preparation-dispatches\/(\d+)\/reprints$/);
    if (reprint && init?.method === 'POST') {
      if (options.reprintResponse) return options.reprintResponse;
      const source = printValues.find((item) => item.id === Number(reprint[1]))!;
      const created = { ...source, id: 1002, operation_kind: 'REPRINT' as const, generation: source.generation + 1, state: 'PENDING' };
      printValues = [...printValues, created];
      return json(created, 201);
    }
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls };
}

function renderKitchen() {
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
        <MemoryRouter initialEntries={['/kitchen']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('Kitchen operations', () => {
  it('loads the granted location and renders authoritative station, order, table, quantity, and configuration', async () => {
    const { calls } = mockKitchenApi();
    renderKitchen();

    expect(await screen.findByRole('heading', { name: 'Preparación' })).toBeVisible();
    const card = (await screen.findByRole('heading', { name: 'Mesa 8' })).closest('article')!;
    expect(within(card).getByText(/Línea caliente/)).toBeVisible();
    expect(within(card).getByText(/CALIENTE/)).toBeVisible();
    expect(within(card).getByText(/Orden #7001/)).toBeVisible();
    expect(within(card).getByText('Papas trufadas')).toBeVisible();
    expect(within(card).getByLabelText('Cantidad 2')).toBeVisible();
    expect(within(card).getByText('Configuración de Hamburguesa especial')).toBeVisible();
    expect(within(card).getAllByText('Pendiente').length).toBeGreaterThan(0);
    expect(calls.find((call) => call.url.includes('/preparation-works?'))?.url).toContain('location_id=21');
    expect(calls.every((call) => !call.url.includes('preparation-routing'))).toBe(true);
  });

  it('uses backend state and area filters and exposes no terminal mutation', async () => {
    const completed = work({
      id: 502,
      preparation_area_id: 42,
      area_code: 'FRIA',
      area_name: 'Línea fría',
      execution_state: 'COMPLETED',
      items: [{ ...work().items[0], id: 602, preparation_work_id: 502, product_name: 'Ensalada', parent_product_name: null, execution_state: 'COMPLETED', execution_version: 2 }],
    });
    const { calls } = mockKitchenApi({ works: [work(), completed], dispatches: [] });
    renderKitchen();
    const user = userEvent.setup();
    await screen.findByText('Papas trufadas');

    await user.click(screen.getByRole('button', { name: 'Listos' }));
    expect(await screen.findByText('Ensalada')).toBeVisible();
    await user.selectOptions(screen.getByLabelText('Área / estación'), '42');
    await waitFor(() => expect(calls.some((call) => (
      call.url.includes('execution_state=COMPLETED')
      && call.url.includes('preparation_area_id=42')
    ))).toBe(true));
    expect(screen.getByText('Terminado')).toBeVisible();
    expect(screen.queryByRole('button', { name: /Iniciar|Marcar listo/ })).not.toBeInTheDocument();
  });

  it('calls the exact transition endpoint once and refetches backend truth after success', async () => {
    let resolveTransition!: (response: Response) => void;
    const transitionResponse = new Promise<Response>((resolve) => { resolveTransition = resolve; });
    const { calls } = mockKitchenApi({ transitionResponse, dispatches: [] });
    renderKitchen();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Iniciar' }));
    const busy = screen.getByRole('button', { name: 'Confirmando…' });
    expect(busy).toBeDisabled();
    await user.click(busy);
    expect(calls.filter((call) => call.url.endsWith('/preparation-work-items/601/transitions'))).toHaveLength(1);

    const mutation = calls.find((call) => call.url.endsWith('/preparation-work-items/601/transitions'))!;
    expect(JSON.parse(String(mutation.init?.body))).toEqual({
      expected_state: 'NEW', expected_version: 0, to_state: 'IN_PROGRESS',
    });
    expect(new Headers(mutation.init?.headers).get('Idempotency-Key')).toMatch(/^kitchen-601-0-/);
    resolveTransition(await json({ current_execution_state: 'IN_PROGRESS', current_execution_version: 1, replayed: false }, 201));
    expect(await screen.findByRole('status')).toHaveTextContent('quedó en preparación');
    await waitFor(() => expect(calls.filter((call) => call.url.includes('/preparation-works?')).length).toBeGreaterThanOrEqual(2));
  });

  it('reconciles stale transitions from the backend and keeps read-only staff presentation-only', async () => {
    const conflicted = mockKitchenApi({ transitionConflict: true, dispatches: [] });
    renderKitchen();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Iniciar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('estado más reciente');
    expect(await screen.findByRole('button', { name: 'Marcar listo' })).toBeVisible();
    expect(conflicted.calls.filter((call) => call.url.includes('/preparation-works?')).length).toBeGreaterThanOrEqual(2);

    cleanup();
    vi.unstubAllGlobals();
    mockKitchenApi({ identity: { ...kitchenIdentity, permissions: ['location.read', 'preparation.read'] }, dispatches: [] });
    renderKitchen();
    expect(await screen.findByText('Solo consulta')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Iniciar' })).not.toBeInTheDocument();
  });

  it('keeps loading, empty, backend-error, and location-authorization states distinct', async () => {
    mockKitchenApi({ worksResponse: new Promise<Response>(() => undefined), dispatches: [] });
    renderKitchen();
    expect(await screen.findByRole('heading', { name: 'Cargando Preparación' })).toBeVisible();

    cleanup();
    vi.unstubAllGlobals();
    mockKitchenApi({ works: [], dispatches: [] });
    renderKitchen();
    expect(await screen.findByRole('heading', { name: 'No hay trabajo para estos filtros.' })).toBeVisible();

    cleanup();
    vi.unstubAllGlobals();
    mockKitchenApi({ worksResponse: json({ detail: 'Unavailable' }, 503), dispatches: [] });
    renderKitchen();
    expect(await screen.findByRole('heading', { name: 'No pudimos cargar Preparación' })).toBeVisible();

    cleanup();
    vi.unstubAllGlobals();
    mockKitchenApi({ worksResponse: json({ detail: 'Location not found' }, 404), dispatches: [] });
    renderKitchen();
    expect(await screen.findByRole('alert')).toHaveTextContent('ubicación ya no está autorizada');
  });

  it('blocks an unauthorized route before any Preparation request', async () => {
    const { calls } = mockKitchenApi({ identity: { ...kitchenIdentity, permissions: ['location.read'] } });
    renderKitchen();
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    expect(calls.some((call) => call.url.includes('/preparation-'))).toBe(false);
  });

  it('reprints only through backend authority and never changes Preparation truth on printer failure', async () => {
    const failedDispatch = dispatch({ state: 'RETRYABLE_FAILURE', last_error_kind: 'PRINTER_OFFLINE' });
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const { calls } = mockKitchenApi({
      works: [work({ execution_state: 'COMPLETED', items: [{ ...work().items[0], execution_state: 'COMPLETED', execution_version: 2 }] })],
      dispatches: [failedDispatch],
    });
    renderKitchen();
    expect(await screen.findByText(/Reintento pendiente/)).toBeVisible();
    expect(screen.getByText('PRINTER_OFFLINE')).toBeVisible();
    expect(screen.getAllByText('Listo').length).toBeGreaterThan(0);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Reimprimir' }));
    expect(await screen.findByRole('status')).toHaveTextContent('conserva su estado');
    expect(calls.filter((call) => call.url.endsWith('/preparation-dispatches/1001/reprints'))).toHaveLength(1);
    expect(calls.every((call) => !/printer|local_target|window\.print/i.test(call.url))).toBe(true);
    expect(printSpy).not.toHaveBeenCalled();
    expect(screen.getAllByText('Listo').length).toBeGreaterThan(0);
  });
});
