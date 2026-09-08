import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { RestaurantPayment, StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const cashierIdentity: StaffIdentity = {
  user_id: 7,
  email: 'cashier@example.test',
  display_name: 'Ana Caja',
  tenant_id: 11,
  membership_id: 13,
  authorized_location_ids: [21],
  roles: ['CASHIER'],
  permissions: [
    'location.read', 'resource.read', 'cash_management.read', 'cash_session.manage',
    'cash_movement.manage', 'restaurant_check.read', 'restaurant_payment.read',
    'restaurant_payment.manage', 'restaurant_payment.recover', 'operational_request.read',
  ],
};

const location = {
  id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO',
  name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE',
};

const register = {
  id: 301, tenant_id: 11, organization_id: 31, location_id: 21,
  code: 'CAJA-1', name: 'Caja principal', resource_type: 'CASH_REGISTER', status: 'ACTIVE',
};

const openSession = {
  id: 401, tenant_id: 11, organization_id: 31, location_id: 21, resource_id: 301,
  cashier_membership_id: 13, currency: 'MXN', status: 'OPEN', movement_version: 0,
  expected_cash: '100.0000', opened_at: '2026-09-08T12:00:00Z',
  selected_cash_count_id: null, final_movement_version: null, frozen_expected_cash: null,
  frozen_variance: null, variance_reason: null, closed_at: null,
};

const baseCheck = {
  id: 501, organization_id: 31, location_id: 21, resource_ids: [101],
  table_scope_session_ids: [201], status: 'OPEN', version: 1, fingerprint: 'check-v1',
  currency: 'MXN', liability_total: '100.0000', confirmed_settlement: '0.0000',
  reserved_financial_exposure: '0.0000', uncertain_exposure: '0.0000',
  outstanding: '100.0000', available_to_initiate: '100.0000',
  created_at: '2026-09-08T11:00:00Z',
};

const detailFields = {
  tenant_id: 11, controller_diner_session_id: null, member_ids: [601], diner_scope_ids: [701],
  consumption_total: '90.0000', gratuity_total: '10.0000', continuation_decision: 'OPEN',
  details: {}, signal: null,
};

function payment(id: number, state: string, overrides: Partial<RestaurantPayment> = {}): RestaurantPayment {
  return {
    id, check_id: 501, check_version: 1, check_fingerprint: 'check-v1', amount: '40.0000',
    currency: 'MXN', method_category: 'CARD', payer_type: 'OTHER', payer_diner_session_id: null,
    payer_reference: 'terminal', state, executor_key: 'mock', external_reference: `ext-${id}`,
    external_status: state, instrument_display: 'VISA •••• 4242', cash_tendered_amount: null,
    cash_change_due: null, terminal_at: state === 'UNCERTAIN' ? null : '2026-09-08T12:10:00Z',
    ...overrides,
  };
}

function json(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  }));
}

interface CashierMockOptions {
  identity?: StaffIdentity;
  active?: boolean;
  uncertain?: boolean;
  paymentConflict?: boolean;
  ambiguousPayment?: boolean;
  deferPayment?: boolean;
}

function mockCashierApi(options: CashierMockOptions = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let session: typeof openSession | null = options.active === false ? null : { ...openSession };
  let check = options.uncertain ? {
    ...baseCheck, reserved_financial_exposure: '0.0000', uncertain_exposure: '40.0000',
    outstanding: '100.0000', available_to_initiate: '60.0000',
  } : { ...baseCheck };
  let payments: RestaurantPayment[] = options.uncertain ? [payment(801, 'UNCERTAIN')] : [];
  let movements: Array<Record<string, unknown>> = [];
  let financialReadsFail = false;
  let releasePayment: (() => void) | undefined;

  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(options.identity ?? cashierIdentity);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/resources?')) return json({ items: [register], limit: 100, offset: 0 });
    if (url.includes('/staff/operational-requests?')) return json({
      items: [{
        id: 901, organization_id: 31, location_id: 21, resource_id: 101,
        resource_code: 'M01', resource_name: 'Mesa 1', service_session_id: 201,
        diner_session_id: 701, diner_display_name: 'Cliente', request_type: 'CASH_PAYMENT_ASSISTANCE',
        status: 'PENDING', related_restaurant_check_id: 501, resolved_by_membership_id: null,
        resolved_at: null, created_at: '2026-09-08T12:00:00Z', updated_at: '2026-09-08T12:00:00Z',
      }], limit: 100, offset: 0,
    });
    if (url.includes('/cash-sessions/active?')) {
      return session ? json(session) : json({ detail: { code: 'CASH_SESSION_NOT_FOUND' } }, 404);
    }
    if (url.match(/\/resources\/301\/cash-sessions\?/ ) && init?.method === 'POST') {
      session = { ...openSession };
      return json(session, 201);
    }
    if (url.includes('/cash-sessions/401/movements?') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      const value = {
        id: 1001, cash_session_id: 401, movement_type: payload.movement_type,
        amount: payload.amount, currency: payload.currency, reason: payload.reason ?? null,
        reference: payload.reference ?? null, recorded_at: '2026-09-08T12:20:00Z',
      };
      movements = [...movements, value];
      session = { ...session!, movement_version: 1, expected_cash: '120.0000' };
      return json(value, 201);
    }
    if (url.includes('/cash-sessions/401/movements?')) return json(movements);
    if (url.includes('/cash-sessions/401/counts?') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      return json({
        id: 1101, cash_session_id: 401, counted_amount: payload.counted_amount,
        currency: payload.currency, captured_movement_version: session?.movement_version ?? 0,
        counted_at: '2026-09-08T12:30:00Z',
      }, 201);
    }
    if (url.includes('/cash-sessions/401/close?') && init?.method === 'POST') {
      const closed = {
        ...session!, status: 'CLOSED', selected_cash_count_id: 1101,
        final_movement_version: session?.movement_version ?? 0,
        frozen_expected_cash: session?.expected_cash ?? '0.0000', frozen_variance: '5.0000',
        variance_reason: 'Diferencia revisada', closed_at: '2026-09-08T12:40:00Z',
      };
      session = null;
      return json(closed);
    }
    if (url.includes('/restaurant-payments/801/recover?') && init?.method === 'POST') {
      payments = [payment(801, 'SUCCEEDED')];
      check = {
        ...check, version: 2, fingerprint: 'check-v2', confirmed_settlement: '40.0000',
        uncertain_exposure: '0.0000', outstanding: '60.0000', available_to_initiate: '60.0000',
      };
      return json(payments[0]);
    }
    if (url.includes('/restaurant-checks/501/payments?') && init?.method === 'POST') {
      if (options.paymentConflict) {
        check = { ...check, version: 2, fingerprint: 'check-v2', confirmed_settlement: '20.0000', outstanding: '80.0000', available_to_initiate: '80.0000' };
        return json({ error: { code: 'CHECK_VERSION_CONFLICT', message: 'La cuenta cambió.' } }, 409);
      }
      if (options.ambiguousPayment) {
        financialReadsFail = true;
        throw new TypeError('connection lost');
      }
      if (options.deferPayment) await new Promise<void>((resolve) => { releasePayment = resolve; });
      const payload = JSON.parse(String(init.body));
      const value = payment(802, 'SUCCEEDED', {
        method_category: 'CASH', amount: payload.amount, cash_tendered_amount: payload.cash_tendered_amount,
        cash_change_due: '10.0000', instrument_display: null, executor_key: null,
      });
      payments = [value];
      check = {
        ...check, version: 2, fingerprint: 'check-v2', confirmed_settlement: payload.amount,
        outstanding: '60.0000', available_to_initiate: '60.0000',
      };
      return json(value, 201);
    }
    if (financialReadsFail && url.includes('/restaurant-checks')) throw new TypeError('still offline');
    if (url.includes('/restaurant-checks/501/settlement?')) return json({
      check_id: 501, check_status: check.status, check_version: check.version,
      check_fingerprint: check.fingerprint, liability_total: check.liability_total,
      currency: check.currency, confirmed_settlement: check.confirmed_settlement,
      reserved_financial_exposure: check.reserved_financial_exposure,
      uncertain_exposure: check.uncertain_exposure, available_to_initiate: check.available_to_initiate,
      payments,
    });
    if (url.match(/\/restaurant-checks\/501\?/)) return json({ ...check, ...detailFields });
    if (url.includes('/restaurant-checks?')) return json({ items: [check], limit: 100, offset: 0 });
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return {
    calls,
    releasePayment: () => releasePayment?.(),
    restoreFinancialTruthAsUncertain: () => {
      financialReadsFail = false;
      check = {
        ...baseCheck, uncertain_exposure: '40.0000', outstanding: '100.0000',
        available_to_initiate: '60.0000',
      };
      payments = [payment(801, 'UNCERTAIN')];
    },
  };
}

function renderCashier() {
  storeCredential({
    accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(),
    tenantId: 11, tenantName: 'Restaurantes Norte',
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/cashier']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('Cashier workspace', () => {
  it('reconstructs the authorized register, active session, check, settlement, and requests', async () => {
    const { calls } = mockCashierApi({ uncertain: true });
    const view = renderCashier();

    expect(await screen.findByRole('heading', { name: 'Caja' })).toBeVisible();
    expect(await screen.findByText('Caja principal · CAJA-1')).toBeVisible();
    expect(screen.getByText('#401')).toBeVisible();
    expect(screen.getByText('Exposición incierta')).toBeVisible();
    expect(screen.getByText('No cobres de nuevo. Recupera o reconcilia el pago existente.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Confirmar pago en efectivo' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Recuperar estado' })).toBeVisible();
    expect(screen.getByText('1')).toBeVisible();
    expect(calls.filter((call) => call.url.includes('location_id=21')).length).toBeGreaterThan(5);
    expect(calls.every((call) => !call.url.includes('location_id=22'))).toBe(true);

    view.unmount();
    renderCashier();
    expect(await screen.findByText('#401')).toBeVisible();
    expect(await screen.findByText('Pago #801 · VISA •••• 4242')).toBeVisible();
  });

  it('opens a register and completes movement, count, variance, and close with server authority', async () => {
    const { calls } = mockCashierApi({ active: false });
    renderCashier();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: 'Abrir caja' }));
    expect(await screen.findByText('#401')).toBeVisible();
    await user.selectOptions(screen.getByLabelText('Tipo'), 'CASH_IN');
    await user.type(screen.getByLabelText('Monto del movimiento'), '20');
    await user.type(screen.getByLabelText('Motivo'), 'Reposición');
    await user.click(screen.getByRole('button', { name: 'Registrar movimiento' }));
    expect(await screen.findByText('Reposición · #1001')).toBeVisible();

    await user.type(screen.getByLabelText('Efectivo contado'), '125');
    await user.click(screen.getByRole('button', { name: 'Capturar conteo' }));
    expect(await screen.findByText('$125.00')).toBeVisible();
    await user.type(screen.getByLabelText('Motivo de diferencia'), 'Diferencia revisada');
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: 'Cerrar caja' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Diferencia confirmada: $5.00');
    expect(await screen.findByRole('button', { name: 'Abrir caja' })).toBeVisible();

    const posts = calls.filter((call) => call.init?.method === 'POST');
    expect(posts.map((call) => call.url)).toEqual(expect.arrayContaining([
      '/api/resources/301/cash-sessions?location_id=21',
      '/api/cash-sessions/401/movements?location_id=21',
      '/api/cash-sessions/401/counts?location_id=21',
      '/api/cash-sessions/401/close?location_id=21',
    ]));
    const closeCall = posts.find((call) => call.url.includes('/close?'))!;
    expect(JSON.parse(String(closeCall.init?.body))).toEqual({
      cash_count_id: 1101, variance_reason: 'Diferencia revisada',
    });
  });

  it('creates one partial cash payment and presents only backend-authorized change and settlement', async () => {
    const api = mockCashierApi({ deferPayment: true });
    renderCashier();
    const user = userEvent.setup();

    await screen.findByRole('heading', { name: 'Recibir efectivo' });
    const amount = screen.getByLabelText('Monto a aplicar');
    await user.clear(amount);
    await user.type(amount, '40');
    await user.type(screen.getByLabelText('Efectivo recibido'), '50');
    const submit = screen.getByRole('button', { name: 'Confirmar pago en efectivo' });
    await user.dblClick(submit);
    expect(api.calls.filter((call) => call.url.includes('/payments?') && call.init?.method === 'POST')).toHaveLength(1);
    api.releasePayment();

    expect(await screen.findByRole('status')).toHaveTextContent('Cambio autorizado: $10.00');
    expect(await screen.findByText('Pago #802 · Efectivo')).toBeVisible();
    expect(screen.getByText('$40.00')).toBeVisible();
    expect(screen.getAllByText('$60.00').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText('Cuenta liquidada')).not.toBeInTheDocument();
    const paymentCall = api.calls.find((call) => call.url.includes('/payments?') && call.init?.method === 'POST')!;
    expect(JSON.parse(String(paymentCall.init?.body))).toMatchObject({
      expected_check_version: 1, expected_check_fingerprint: 'check-v1', amount: '40',
      currency: 'MXN', cash_session_id: 401, cash_tendered_amount: '50', method_category: 'CASH',
    });
  });

  it('blocks blind repayment after ambiguity until authoritative reconciliation and supports recovery', async () => {
    const api = mockCashierApi({ ambiguousPayment: true });
    renderCashier();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText('Efectivo recibido'), '100');
    await user.click(screen.getByRole('button', { name: 'Confirmar pago en efectivo' }));
    expect(await screen.findByText('Confirmación pendiente')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Confirmar pago en efectivo' })).toBeDisabled();
    expect(api.calls.filter((call) => call.url.includes('/payments?') && call.init?.method === 'POST')).toHaveLength(1);

    api.restoreFinancialTruthAsUncertain();
    await user.click(screen.getByRole('button', { name: 'Actualizar verdad' }));
    expect(await screen.findByText('Exposición incierta')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Confirmar pago en efectivo' })).toBeDisabled();
    await user.click(await screen.findByRole('button', { name: 'Recuperar estado' }));
    expect(await screen.findByRole('status')).toHaveTextContent('estado confirmado');
    await waitFor(() => expect(screen.queryByText('Exposición incierta')).not.toBeInTheDocument());
    expect(screen.getByText('$40.00')).toBeVisible();
    expect(screen.getAllByText('$60.00').length).toBeGreaterThanOrEqual(2);
  });

  it('reconciles stale payment conflicts and never creates a client-side financial state', async () => {
    const api = mockCashierApi({ paymentConflict: true });
    renderCashier();
    const user = userEvent.setup();

    await user.type(await screen.findByLabelText('Efectivo recibido'), '100');
    await user.click(screen.getByRole('button', { name: 'Confirmar pago en efectivo' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La cuenta cambió.');
    await waitFor(() => expect(screen.getAllByText('$80.00').length).toBeGreaterThanOrEqual(2));
    expect(api.calls.filter((call) => call.url.includes('/payments?') && call.init?.method === 'POST')).toHaveLength(1);
    expect(document.body.textContent).not.toContain('saldo local');
  });

  it('keeps the route unavailable without the full read authorization set', async () => {
    mockCashierApi({
      identity: { ...cashierIdentity, permissions: cashierIdentity.permissions.filter((value) => value !== 'resource.read') },
    });
    renderCashier();
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Caja' })).not.toBeInTheDocument();
  });
});
