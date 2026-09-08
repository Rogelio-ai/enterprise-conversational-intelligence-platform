import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ManagerOperationalOverview, StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const managerPermissions = [
  'location.read', 'resource.read', 'restaurant_service.read', 'restaurant_order.read',
  'operational_request.read', 'preparation.read', 'restaurant_check.read',
  'restaurant_payment.read', 'cash_management.read',
];
const manager: StaffIdentity = {
  user_id: 7, email: 'manager@example.test', display_name: 'Mara Gerencia',
  tenant_id: 11, membership_id: 13, authorized_location_ids: [21],
  roles: ['MANAGER'], permissions: managerPermissions,
};
const location = { id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' };

const overview: ManagerOperationalOverview = {
  location_id: 21, generated_at: '2026-09-08T18:00:00Z',
  active_table_count: 8, available_table_count: 5,
  active_service_session_count: 3, active_diner_count: 7,
  service_sessions: [{ id: 201, resource_id: 101, resource_code: 'M01', resource_name: 'Mesa 1', party_size: 4, active_diner_count: 3, opened_at: '2026-09-08T17:00:00Z' }],
  request_counts_by_status: { PENDING: 4, ACKNOWLEDGED: 2, COMPLETED: 8, CANCELLED: 1 },
  request_counts_by_type: { HUMAN_ASSISTANCE: 2, CASH_PAYMENT_ASSISTANCE: 1, INVOICE_ASSISTANCE: 2, PAID_CHECK_PRINT: 1 },
  preparation_item_counts: { NEW: 5, IN_PROGRESS: 3, COMPLETED: 12 },
  preparation_dispatch_counts: { PENDING: 0, IN_PROGRESS: 0, DESTINATION_SUBMISSION_ACCEPTED: 10, RETRYABLE_FAILURE: 1, UNCERTAIN: 0, ACTION_REQUIRED: 0 },
  preparation_dispatch_exceptions: [{ id: 301, reference_id: 302, state: 'RETRYABLE_FAILURE', destination_name: 'Cocina', attempt_count: 2, last_error_kind: 'OFFLINE', created_at: '2026-09-08T17:30:00Z' }],
  check_counts_by_status: { OPEN: 2, FROZEN: 1, SETTLED: 4, CANCELLED: 0 },
  checks_with_outstanding_count: 2,
  check_exceptions: [{ id: 501, status: 'FROZEN', currency: 'MXN', liability_total: '100.0000', confirmed_settlement: '40.0000', outstanding: '60.0000', reserved_exposure: '0.0000', uncertain_exposure: '40.0000' }],
  uncertain_payments: [{ id: 601, check_id: 501, amount: '40.0000', currency: 'MXN', method_category: 'CARD', state: 'UNCERTAIN', created_at: '2026-09-08T17:40:00Z' }],
  cash_session_counts: { OPEN: 1, CLOSED: 4 },
  cash_session_exceptions: [{ id: 701, resource_id: 102, status: 'CLOSED', currency: 'MXN', expected_cash: '500.0000', frozen_variance: '-20.0000', opened_at: '2026-09-08T10:00:00Z' }],
  fiscal_issuance_counts: { PENDING: 1, IN_PROGRESS: 0, SUCCEEDED: 4, FAILED: 1, REJECTED: 0, UNCERTAIN: 1 },
  fiscal_exceptions: [{ id: 801, billing_document_id: 802, provider_key: 'FINKOK', state: 'UNCERTAIN', attempt_count: 1, requested_at: '2026-09-08T17:45:00Z' }],
  paid_print_counts: { PENDING: 1, IN_PROGRESS: 0, DESTINATION_SUBMISSION_ACCEPTED: 4, RETRYABLE_FAILURE: 0, UNCERTAIN: 0, ACTION_REQUIRED: 1 },
  paid_print_exceptions: [{ id: 901, reference_id: 501, state: 'ACTION_REQUIRED', destination_name: 'Impresora caja', attempt_count: 3, last_error_kind: 'PAPER', created_at: '2026-09-08T17:50:00Z' }],
};

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

function mockApi(options: { identity?: StaffIdentity; overview?: ManagerOperationalOverview; overviewStatus?: number } = {}) {
  const calls: string[] = [];
  const methods: string[] = [];
  let current = options.overview ?? overview;
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input); calls.push(url); methods.push(init?.method ?? 'GET');
    if (url.endsWith('/auth/me')) return json(options.identity ?? manager);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/staff/manager/operational-overview?')) return options.overviewStatus
      ? json({ detail: 'Unavailable' }, options.overviewStatus)
      : json(current);
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls, methods, setOverview: (value: ManagerOperationalOverview) => { current = value; } };
}

function renderManager() {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Tenant' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={['/manager']}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter></ThemeProvider></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Manager operational overview', () => {
  it('reconstructs every operational area from the active authorized location without sensitive data', async () => {
    const api = mockApi(); renderManager();
    expect(await screen.findByRole('heading', { name: 'Gerencia' })).toBeVisible();
    expect(screen.getByText('PAGO INCIERTO')).toBeVisible();
    expect(screen.getByText('NO COBRAR DE NUEVO HASTA RECONCILIAR EN CAJA.')).toBeVisible();
    expect(screen.getByText('Mesa 1 · M01')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Solicitudes operativas' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Cocina y despachos' })).toBeVisible();
    expect(screen.getByText(/Pendiente \$60\.00/)).toBeVisible();
    expect(screen.getByText(/diferencia confirmada -\$20\.00/)).toBeVisible();
    expect(screen.getByText(/Emisión #801/)).toBeVisible();
    expect(screen.getByText(/Despacho #901/)).toBeVisible();
    expect(api.calls.some((url) => url.includes('location_id=21'))).toBe(true);
    expect(api.calls.every((url) => !url.includes('location_id=22'))).toBe(true);
    expect(document.body).not.toHaveTextContent('credential_binding');
    expect(document.body).not.toHaveTextContent('tax_identifier');
    expect(document.body).not.toHaveTextContent('payer_reference');
  });

  it('refreshes from backend truth and provides drill-down links without manager mutations', async () => {
    const api = mockApi(); const user = userEvent.setup(); renderManager();
    await screen.findByRole('heading', { name: 'Gerencia' });
    api.setOverview({ ...overview, uncertain_payments: [], check_exceptions: [], checks_with_outstanding_count: 0 });
    await user.click(screen.getByRole('button', { name: 'Actualizar panorama' }));
    await waitFor(() => expect(screen.queryByText('PAGO INCIERTO')).not.toBeInTheDocument());
    expect(screen.getByText(/No hay Checks con exposición financiera/)).toBeVisible();
    expect(screen.getByRole('link', { name: 'Ver Host' })).toHaveAttribute('href', '/host');
    expect(screen.getByRole('link', { name: 'Ver solicitudes' })).toHaveAttribute('href', '/waiter');
    expect(screen.getByRole('link', { name: 'Ver Cocina' })).toHaveAttribute('href', '/kitchen');
    expect(screen.getByRole('link', { name: 'Ver Caja' })).toHaveAttribute('href', '/cashier');
    expect(api.calls.filter((url) => url.includes('/operational-overview?')).length).toBeGreaterThanOrEqual(2);
    expect(api.methods.every((method) => method === 'GET')).toBe(true);
  });

  it('distinguishes healthy empty state from loading and backend failure', async () => {
    const empty = {
      ...overview, service_sessions: [], uncertain_payments: [], check_exceptions: [],
      cash_session_exceptions: [], fiscal_exceptions: [], paid_print_exceptions: [],
      preparation_dispatch_exceptions: [], checks_with_outstanding_count: 0,
      request_counts_by_status: { PENDING: 0, ACKNOWLEDGED: 0, COMPLETED: 0, CANCELLED: 0 },
    };
    mockApi({ overview: empty }); renderManager();
    expect(await screen.findByText(/No hay sesiones de servicio activas/)).toBeVisible();
    expect(screen.getByText(/No hay solicitudes accionables/)).toBeVisible();
    cleanup();
    mockApi({ overviewStatus: 503 }); renderManager();
    expect(await screen.findByRole('alert')).toHaveTextContent('No hay una lectura autoritativa actual.');
  });

  it('denies the Manager route when any required capability is absent', async () => {
    mockApi({ identity: { ...manager, permissions: manager.permissions.filter((item) => item !== 'cash_management.read') } });
    renderManager();
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    const navigation = screen.getByRole('navigation', { name: 'Espacios de trabajo' });
    expect(within(navigation).queryByRole('link', { name: 'Gerencia' })).not.toBeInTheDocument();
  });
});
