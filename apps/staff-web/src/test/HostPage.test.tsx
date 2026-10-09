import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const permissions = ['location.read', 'resource.read', 'restaurant_service.read', 'internal_message.read', 'internal_message.send'];
const identity: StaffIdentity = {
  username: 'host', user_id: 7, email: 'host@example.test', display_name: 'Ana Recepción',
  tenant_id: 11, membership_id: 13, authorized_location_ids: [21], roles: ['HOST'], permissions,
  location_authorities: [{ location_id: 21, roles: ['HOST'], permissions }],
};
const location = { id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' };
const resources = [
  { id: 101, tenant_id: 11, location_id: 21, code: 'M01', name: 'Mesa 1', resource_type: 'TABLE', status: 'ACTIVE', created_at: '2026-09-07T12:00:00Z', updated_at: '2026-09-07T12:00:00Z' },
  { id: 102, tenant_id: 11, location_id: 21, code: 'M02', name: 'Mesa 2', resource_type: 'TABLE', status: 'ACTIVE', created_at: '2026-09-07T12:00:00Z', updated_at: '2026-09-07T12:00:00Z' },
];
const managed = resources.map((value, index) => ({ resource_id: value.id, code: value.code, name: value.name, physical_capacity: 4, dining_section_id: 41, dining_section_code: 'SALON', dining_section_name: 'Salón', administrative_status: 'ACTIVE', individually_movable: true, section_movable: true, effective_movable: true, metadata_version: 1, operational_status: index ? 'OCCUPIED' : 'AVAILABLE', active_group_id: null, is_group_representative: false }));

function json(body: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })); }

function installApi(override: StaffIdentity = identity) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal('fetch', vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input); calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(override);
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/resources?')) return json({ items: resources, limit: 100, offset: 0 });
    if (url.endsWith('/resources/101/service-sessions/current')) return json({ detail: 'Not found' }, 404);
    if (url.endsWith('/resources/102/service-sessions/current')) return json({ id: 501, resource_id: 102, party_size: 4, active_diner_count: 2, status: 'OPEN', join_context_key: 'hidden', access_code_version: 1, opened_at: '2026-09-07T12:00:00Z' });
    if (/\/tables\/\d+\/waiter-assignments$/.test(url)) return json({ table_resource_id: url.includes('/101/') ? 101 : 102, location_id: 21, configured: true, version: 1, assignments: [{ membership_id: 201, display_name: 'Luis Mesero', email: '', is_responsible: true }] });
    if (url.endsWith('/locations/21/table-management/tables')) return json({ items: managed });
    if (url.endsWith('/locations/21/table-management/sections')) return json({ items: [] });
    if (url.includes('/internal-messages/sent?')) return json({ items: [], limit: 50, offset: 0 });
    if (url.endsWith('/locations/21/tables/eligible-waiters')) return json({ items: [{ membership_id: 201, display_name: 'Luis Mesero', email: '' }] });
    return json({ detail: 'Not found' }, 404);
  }));
  return calls;
}

function renderHost() {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Restaurantes Norte' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={['/host']}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter></ThemeProvider></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Reception workspace', () => {
  it('presents Reception as a read-only arrival and preparation workspace', async () => {
    const calls = installApi(); renderHost();
    expect(await screen.findByRole('heading', { name: 'Llegada de comensales' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Solicitar preparación de mesa' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Mesas y grupos preparados' })).toBeVisible();
    expect(await screen.findByRole('heading', { name: 'Mesa 1', level: 2 })).toBeVisible();
    expect(await screen.findByRole('heading', { name: 'Mesa 2', level: 2 })).toBeVisible();
    expect(screen.getAllByText('Consulta solamente')).toHaveLength(2);
    for (const name of ['Abrir mesa', 'Nuevo código', 'Unir mesas', 'Agregar mesa', 'Retirar mesa', 'Disolver grupo', 'Mover mesa']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
    expect(calls.some((call) => call.init?.method && call.init.method !== 'GET')).toBe(false);
  });

  it('remains read-only even if a stale identity still carries structural permissions', async () => {
    installApi({ ...identity, permissions: [...permissions, 'restaurant_service.manage', 'table_management.manage'], location_authorities: [{ location_id: 21, roles: ['HOST'], permissions: [...permissions, 'restaurant_service.manage', 'table_management.manage'] }] });
    renderHost();
    const panel = (await screen.findByRole('heading', { name: 'Mesas y grupos preparados' })).closest('section')!;
    expect(within(panel).queryByRole('button', { name: 'Unir mesas' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Abrir mesa' })).not.toBeInTheDocument();
  });
});
