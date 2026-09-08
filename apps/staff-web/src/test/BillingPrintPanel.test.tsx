import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { BillingPrintPanel } from '../components/BillingPrintPanel';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';

const identity = {
  user_id: 7, email: 'cashier@example.test', display_name: 'Ana Caja', tenant_id: 11,
  membership_id: 13, authorized_location_ids: [21], roles: ['CASHIER'],
  permissions: ['restaurant_check.read', 'restaurant_check.manage', 'preparation.read', 'operational_request.read', 'operational_request.manage'],
};
const check = {
  id: 501, organization_id: 31, location_id: 21, resource_ids: [101], table_scope_session_ids: [201],
  status: 'SETTLED', version: 2, fingerprint: 'check-v2', currency: 'MXN', liability_total: '100.0000',
  confirmed_settlement: '100.0000', reserved_financial_exposure: '0.0000', uncertain_exposure: '0.0000',
  outstanding: '0.0000', available_to_initiate: '0.0000', created_at: '2026-09-08T11:00:00Z',
};
const settlement = {
  check_id: 501, check_status: 'SETTLED', check_version: 2, check_fingerprint: 'check-v2',
  liability_total: '100.0000', currency: 'MXN', confirmed_settlement: '100.0000',
  reserved_financial_exposure: '0.0000', uncertain_exposure: '0.0000', available_to_initiate: '0.0000', payments: [],
};
const issuer = { id: 41, organization_id: 31, legal_name: 'Restaurante', tax_identifier: 'AAA010101AAA', tax_regime: '601', fiscal_postal_code: '01000', status: 'ACTIVE', created_at: 'now', updated_at: 'now' };
const recipient = { id: 51, customer_id: 61, legal_name: 'Cliente', tax_identifier: 'XAXX010101000', tax_regime: '616', fiscal_postal_code: '01000', invoice_usage: 'S01', status: 'ACTIVE', created_at: 'now', updated_at: 'now' };
const document = { id: 71, tenant_id: 11, organization_id: 31, location_id: 21, restaurant_check_id: 501, source_check_version: 2, source_check_fingerprint: 'check-v2', document_type: 'INVOICE', status: 'DRAFT', currency: 'MXN', subtotal: '100.0000', discount_total: '0.0000', tax_total: '0.0000', total: '100.0000', issuer_snapshot: {}, recipient_snapshot: {}, issuer_fiscal_postal_code: '01000', readiness_evidence_fingerprint: 'evidence', created_at: 'now', updated_at: 'now' };
const issuance = { id: 81, tenant_id: 11, organization_id: 31, location_id: 21, billing_document_id: 71, provider_key: 'FAKE', state: 'SUCCEEDED', external_reference: 'PAC-1', external_status: 'issued', attempt_count: 1, requested_at: 'now', completed_at: 'now' };
const connector = { id: 91, tenant_id: 11, organization_id: 31, location_id: 21, code: 'LOCAL', name: 'Impresora caja', status: 'ACTIVE' };
const request = (id: number, request_type: string) => ({ id, organization_id: 31, location_id: 21, resource_id: 101, resource_code: 'M01', resource_name: 'Mesa 1', service_session_id: 201, diner_session_id: 301, diner_display_name: 'Cliente', request_type, status: 'PENDING', related_restaurant_check_id: 501, resolved_by_membership_id: null, resolved_at: null, created_at: 'now', updated_at: 'now' });
const dispatch = (state: string) => ({ id: 101, restaurant_check_id: 501, check_version: 2, check_fingerprint: 'check-v2', cashier_resource_id: 301, cashier_resource_code: 'CAJA', cashier_resource_name: 'Caja', connector_id: 91, connector_code: 'LOCAL', connector_name: 'Impresora caja', local_target_key: 'cashier_printer', operation_id: 'op-1', state, attempt_count: state === 'PENDING' ? 0 : 1, available_at: 'now', last_error_kind: null, last_error_message: null, terminal_at: state === 'DESTINATION_SUBMISSION_ACCEPTED' ? 'now' : null, created_at: 'now', updated_at: 'now', attempts: [] });

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

function mockApi(options: { ambiguousIssuance?: boolean; printState?: string } = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  let documents: typeof document[] = [];
  let issuances: typeof issuance[] = [];
  let dispatches: ReturnType<typeof dispatch>[] = [];
  let fiscalReadsFail = false;
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input); calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(identity);
    if (url.includes('/fiscal-context')) return json({ check_id: 501, organization_id: 31, location_id: 21, check_status: 'SETTLED', customer_id: 61, customer_display_name: 'Cliente', customer_email: 'cliente@example.test', issuer_profiles: [issuer], recipient_profile: recipient });
    if (url.includes('/billing-documents?')) return json(documents);
    if (url.match(/\/restaurant-checks\/501\/billing-documents$/) && init?.method === 'POST') { documents = [document]; return json(document, 201); }
    if (url.includes('/billing-documents/71/issuances?') && init?.method === 'POST') {
      if (options.ambiguousIssuance) { fiscalReadsFail = true; throw new TypeError('connection lost'); }
      issuances = [issuance]; return json(issuance, 201);
    }
    if (url.includes('/billing-documents/71/issuances?')) {
      if (fiscalReadsFail) throw new TypeError('still offline');
      return json(issuances);
    }
    if (url.includes('/preparation-delivery-connectors?')) return json([connector]);
    if (url.includes('/paid-print-dispatches?')) return json(dispatches);
    if (url.includes('/restaurant-checks/501/paid-print?') && init?.method === 'POST') { dispatches = [dispatch(options.printState ?? 'PENDING')]; return json(dispatches[0], 201); }
    if (url.includes('/staff/operational-requests?')) return json({ items: [url.includes('INVOICE_ASSISTANCE') ? request(111, 'INVOICE_ASSISTANCE') : request(112, 'PAID_CHECK_PRINT')], limit: 100, offset: 0 });
    if (url.includes('/acknowledge?') && init?.method === 'POST') return json({ ...request(111, 'INVOICE_ASSISTANCE'), status: 'ACKNOWLEDGED' });
    if (url.includes('/complete?') && init?.method === 'POST') return json({ ...request(111, 'INVOICE_ASSISTANCE'), status: 'COMPLETED' });
    throw new Error(`Unhandled request: ${init?.method ?? 'GET'} ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls };
}

function renderPanel(settlementValue = settlement) {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Tenant' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><AuthProvider><BillingPrintPanel locationId={21} check={check as never} settlement={settlementValue as never} registerId={301} /></AuthProvider></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Billing and paid-print operations', () => {
  it('issues explicitly, prevents duplicate clicks, and completes the durable request explicitly', async () => {
    const api = mockApi(); const user = userEvent.setup(); renderPanel();
    await user.click(await screen.findByRole('button', { name: 'Preparar factura' }));
    const issueButton = await screen.findByRole('button', { name: 'Emitir factura' });
    await user.dblClick(issueButton);
    expect(await screen.findByText('Emitida')).toBeVisible();
    expect(api.calls.filter((call) => call.url.includes('/billing-documents/71/issuances?') && call.init?.method === 'POST')).toHaveLength(1);
    await user.click(await screen.findByRole('button', { name: 'Completar solicitud de factura #111' }));
    await waitFor(() => expect(api.calls.some((call) => call.url.includes('/111/acknowledge?'))).toBe(true));
    expect(api.calls.some((call) => call.url.includes('/111/complete?'))).toBe(true);
    expect(api.calls.every((call) => !call.url.includes('location_id=22'))).toBe(true);
  });

  it('locks an ambiguous issuance and does not submit a second fiscal operation', async () => {
    const api = mockApi({ ambiguousIssuance: true }); const user = userEvent.setup(); renderPanel();
    await user.click(await screen.findByRole('button', { name: 'Preparar factura' }));
    await user.click(await screen.findByRole('button', { name: 'Emitir factura' }));
    expect(await screen.findByText('Emisión bloqueada hasta reconciliar el resultado autoritativo.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Emitir factura' })).toBeDisabled();
    expect(api.calls.filter((call) => call.url.includes('/billing-documents/71/issuances?') && call.init?.method === 'POST')).toHaveLength(1);
  });

  it('creates backend print dispatches, reports delivery authority, and never invokes browser printing', async () => {
    const api = mockApi({ printState: 'DESTINATION_SUBMISSION_ACCEPTED' });
    const browserPrint = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    const user = userEvent.setup(); renderPanel();
    const printButton = await screen.findByRole('button', { name: 'Imprimir cuenta pagada' });
    await waitFor(() => expect(printButton).toBeEnabled());
    await user.click(printButton);
    expect(await screen.findByText('Entrega aceptada por destino')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Crear reimpresión autorizada' })).toBeVisible();
    expect(await screen.findByRole('button', { name: 'Completar solicitud de impresión #112' })).toBeVisible();
    expect(browserPrint).not.toHaveBeenCalled();
    expect(api.calls.filter((call) => call.url.includes('/paid-print') && call.init?.method === 'POST')).toHaveLength(1);
  });

  it('blocks fiscal and print commitments when settlement authority is not SETTLED', async () => {
    mockApi(); renderPanel({ ...settlement, check_status: 'OPEN' });
    expect(await screen.findByText('Facturación e impresión permanecen bloqueadas hasta SETTLED.')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Preparar factura' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Imprimir cuenta pagada' })).toBeDisabled();
  });
});
