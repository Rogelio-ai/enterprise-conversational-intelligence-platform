import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { InternalMessageDetail, StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const location = { id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' };
const hostPermissions = ['location.read', 'resource.read', 'restaurant_service.read', 'internal_message.read', 'internal_message.send'];
const waiterPermissions = ['location.read', 'resource.read', 'restaurant_service.read', 'restaurant_service.manage', 'restaurant_order.read', 'restaurant_check.read', 'operational_request.read', 'operational_request.manage', 'table_management.manage', 'internal_message.read', 'internal_message.respond'];
function identity(kind: 'host' | 'waiter'): StaffIdentity {
  const permissions = kind === 'host' ? hostPermissions : waiterPermissions;
  return { user_id: 7, username: kind, email: `${kind}@example.test`, display_name: kind === 'host' ? 'Ana Recepción' : 'Luis Mesero', tenant_id: 11, membership_id: kind === 'host' ? 13 : 201, authorized_location_ids: [21], roles: [kind.toUpperCase()], permissions, location_authorities: [{ location_id: 21, roles: [kind.toUpperCase()], permissions }] };
}
const managedTables = [
  { resource_id: 101, code: 'M01', name: 'Mesa 1', physical_capacity: 4, dining_section_id: 41, dining_section_code: 'TERRAZA', dining_section_name: 'Terraza', administrative_status: 'ACTIVE', individually_movable: true, section_movable: true, effective_movable: true, metadata_version: 2, operational_status: 'AVAILABLE', active_group_id: 5, is_group_representative: true },
  { resource_id: 102, code: 'M02', name: 'Mesa 2', physical_capacity: 2, dining_section_id: 41, dining_section_code: 'TERRAZA', dining_section_name: 'Terraza', administrative_status: 'ACTIVE', individually_movable: true, section_movable: true, effective_movable: true, metadata_version: 2, operational_status: 'AVAILABLE', active_group_id: 5, is_group_representative: false },
  { resource_id: 103, code: 'M03', name: 'Mesa 3', physical_capacity: 4, dining_section_id: 42, dining_section_code: 'SALON', dining_section_name: 'Salón', administrative_status: 'ACTIVE', individually_movable: true, section_movable: true, effective_movable: true, metadata_version: 1, operational_status: 'AVAILABLE', active_group_id: null, is_group_representative: false },
  { resource_id: 104, code: 'M04', name: 'Mesa 4', physical_capacity: 6, dining_section_id: 42, dining_section_code: 'SALON', dining_section_name: 'Salón', administrative_status: 'ACTIVE', individually_movable: true, section_movable: true, effective_movable: true, metadata_version: 1, operational_status: 'AVAILABLE', active_group_id: null, is_group_representative: false },
  { resource_id: 105, code: 'M05', name: 'Mesa 5', physical_capacity: 4, dining_section_id: 42, dining_section_code: 'SALON', dining_section_name: 'Salón', administrative_status: 'ACTIVE', individually_movable: true, section_movable: true, effective_movable: true, metadata_version: 1, operational_status: 'AVAILABLE', active_group_id: null, is_group_representative: false },
];
const group = { id: 5, representative_resource_id: 101, representative_code: 'M01', status: 'ACTIVE', version: 3, member_resource_ids: [101, 102], member_codes: ['M01', 'M02'], responsible_membership_ids: [201], derived_capacity: 6, created_by_membership_id: 13, created_at: '2026-09-28T12:00:00Z', closed_by_membership_id: null, closed_at: null };
const dinerRequest = { id: 900, organization_id: 31, location_id: 21, resource_id: 103, resource_code: 'M03', resource_name: 'Mesa 3', service_session_id: 80, diner_session_id: 81, diner_display_name: 'Invitado', request_type: 'HUMAN_ASSISTANCE', status: 'PENDING', related_restaurant_check_id: null, preparation_work_id: null, restaurant_order_id: null, preparation_area_id: null, preparation_area_code: null, preparation_area_name: null, picked_up_by_membership_id: null, picked_up_at: null, delivered_by_membership_id: null, delivered_at: null, acknowledged_by_membership_id: null, acknowledged_at: null, resolved_by_membership_id: null, resolved_at: null, current_waiter_entered_at: null, current_waiter_hidden_at: null, created_at: '2026-09-28T11:55:00Z', updated_at: '2026-09-28T11:55:00Z' };
function detail(overrides: Partial<InternalMessageDetail> = {}): InternalMessageDetail {
  return { id: 700, organization_id: 31, location_id: 21, creator: { membership_id: 13, display_name: 'Ana Recepción', email: null }, recipient: { membership_id: 201, display_name: 'Luis Mesero', email: null }, type: 'TABLE_PREPARATION_REQUEST', text: 'Se requiere mesa para 6 personas.', party_size: 6, status: 'CREATED', entered_at: null, ready_at: null, created_at: '2026-09-28T12:00:00Z', updated_at: '2026-09-28T12:00:00Z', version: 1, enterado: null, ready: null, responses: [], history: [{ sequence: 1, event_type: 'MESSAGE_CREATED', actor: { membership_id: 13, display_name: 'Ana Recepción', email: null }, response_id: null, occurred_at: '2026-09-28T12:00:00Z' }], prepared_table: null, allowed_actions: ['ENTERADO'], ...overrides };
}
function json(body: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })); }

function installApi(kind: 'host' | 'waiter', initial = detail(), options: { createGroupConflict?: boolean; deferAssignments?: boolean; deferPreview?: boolean } = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const pendingAssignments: Array<() => void> = [];
  const pendingPreviews: Array<() => void> = [];
  let message = initial;
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input); calls.push({ url, init });
    if (url.endsWith('/auth/me')) return json(identity(kind));
    if (url.includes('/locations?')) return json({ items: [location], limit: 100, offset: 0 });
    if (url.includes('/resources?')) return json({ items: managedTables.map((table) => ({ id: table.resource_id, tenant_id: 11, location_id: 21, code: table.code, name: table.name, resource_type: 'TABLE', status: 'ACTIVE', created_at: message.created_at, updated_at: message.updated_at })), limit: 100, offset: 0 });
    if (/\/resources\/\d+\/service-sessions\/current$/.test(url)) return json({ detail: 'Not found' }, 404);
    if (url.endsWith('/resources/101/service-sessions') && init?.method === 'POST') return json({ id: 801, resource_id: 101, party_size: 6, status: 'OPEN', join_context_key: 'secure-context', access_code: '4827', access_code_version: 1, opened_at: '2026-09-28T12:12:00Z' }, 201);
    if (url.endsWith('/locations/21/tables/eligible-waiters')) return json({ items: [{ membership_id: 201, display_name: 'Luis Mesero', email: 'luis@example.test' }, { membership_id: 202, display_name: 'María Mesera', email: 'maria@example.test' }] });
    const assignments = url.match(/\/locations\/21\/tables\/(\d+)\/waiter-assignments$/);
    if (assignments) {
      const tableId = Number(assignments[1]);
      const items = tableId === 103 || tableId === 105 ? [{ membership_id: 201, display_name: 'Luis Mesero', email: '', is_responsible: true }] : tableId === 104 ? [{ membership_id: 202, display_name: 'María Mesera', email: '', is_responsible: true }] : [];
      const response = { table_resource_id: tableId, location_id: 21, configured: Boolean(items.length), version: 1, assignments: items };
      if (options.deferAssignments) return new Promise<Response>((resolve) => pendingAssignments.push(() => void json(response).then(resolve)));
      return json(response);
    }
    if (url.endsWith('/locations/21/table-management/tables')) return json({ items: managedTables });
    if (url.endsWith('/locations/21/table-management/sections')) return json({ items: [{ id: 41, organization_id: 31, location_id: 21, code: 'TERRAZA', name: 'Terraza', movable: true, status: 'ACTIVE' }, { id: 42, organization_id: 31, location_id: 21, code: 'SALON', name: 'Salón', movable: true, status: 'ACTIVE' }] });
    if (url.endsWith('/locations/21/table-management/tables/101/active-group')) return json(group);
    if (url.endsWith('/locations/21/table-management/groups:preview') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      const memberIds = [payload.representative_resource_id, ...payload.joined_resource_ids];
      const members = memberIds.map((id: number, index: number) => { const table = managedTables.find((value) => value.resource_id === id)!; return { resource_id: id, code: table.code, name: table.name, physical_capacity: table.physical_capacity, is_representative: index === 0 }; });
      const derivedCapacity = memberIds.length === 3 ? 10 : 8;
      const response = { eligible: true, representative: members[0], members, derived_capacity: derivedCapacity, assigned_membership_ids: [201, 202], automatic_responsible_membership_ids: [], responsibility_selection_required: true };
      if (options.deferPreview) return new Promise<Response>((resolve) => pendingPreviews.push(() => void json(response).then(resolve)));
      return json(response);
    }
    if (url.endsWith('/locations/21/table-management/groups') && init?.method === 'POST') {
      if (options.createGroupConflict) return json({ detail: 'Table Management state changed; refresh and retry' }, 409);
      return json({ ...group, id: 6, representative_resource_id: 103, member_resource_ids: [103, 104, 105], derived_capacity: 10 }, 201);
    }
    if (url.includes('/waiter/operational-requests?')) return json({ items: kind === 'waiter' ? [dinerRequest] : [], limit: 100, offset: 0 });
    if (url.includes('/internal-messages/sent?')) return json({ items: kind === 'host' ? [message] : [], limit: 50, offset: 0 });
    if (url.includes('/internal-messages/inbox?')) return json({ items: kind === 'waiter' ? [message] : [], limit: 50, offset: 0 });
    if (url.endsWith('/locations/21/internal-messages') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      message = detail({ party_size: payload.party_size, text: payload.text, recipient: { membership_id: payload.recipient_membership_id, display_name: 'Luis Mesero', email: null } });
      return json(message, 201);
    }
    if (url.endsWith('/internal-messages/700/enterado') && init?.method === 'POST') {
      message = detail({ status: 'ENTERED', entered_at: '2026-09-28T12:05:00Z', enterado: { membership_id: 201, entered_at: '2026-09-28T12:05:00Z' }, allowed_actions: ['RESPOND', 'READY'] });
      return json(message);
    }
    if (url.endsWith('/internal-messages/700/responses') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      message = { ...message, responses: [{ id: 1, sequence: 1, author: message.recipient, content: payload.content, created_at: '2026-09-28T12:06:00Z' }] };
      return json(message, 201);
    }
    if (url.endsWith('/internal-messages/700/ready') && init?.method === 'POST') {
      const payload = JSON.parse(String(init.body));
      const table = managedTables.find((value) => value.resource_id === payload.prepared_table_resource_id)!;
      message = { ...message, status: 'READY', ready_at: '2026-09-28T12:10:00Z', ready: { membership_id: 201, ready_at: '2026-09-28T12:10:00Z' }, allowed_actions: [], prepared_table: { resource_id: table.resource_id, code: table.code, name: table.name, physical_capacity: table.physical_capacity!, is_group_representative: table.is_group_representative, group_id: table.active_group_id, members: table.is_group_representative ? managedTables.slice(0, 2).map((value) => ({ resource_id: value.resource_id, code: value.code, name: value.name, physical_capacity: value.physical_capacity! })) : [{ resource_id: table.resource_id, code: table.code, name: table.name, physical_capacity: table.physical_capacity! }], derived_group_capacity: table.is_group_representative ? 6 : null } };
      return json(message);
    }
    if (url.endsWith('/internal-messages/700')) return json(message);
    return json({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { calls, resolveAssignments() { pendingAssignments.splice(0).forEach((resolve) => resolve()); }, resolvePreview() { pendingPreviews.splice(0).forEach((resolve) => resolve()); }, get message() { return message; } };
}
function renderRoute(path: '/host' | '/waiter') {
  storeCredential({ accessToken: 'staff-token', expiresAt: new Date(Date.now() + 60_000).toISOString(), tenantId: 11, tenantName: 'Restaurantes Norte' });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><ThemeProvider><MemoryRouter initialEntries={[path]}><AuthProvider><AppRoutes /></AuthProvider></MemoryRouter></ThemeProvider></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('IMP-C Reception and Waiter integration', () => {
  it('shows sections, capacities and the active group without exposing its technical id', async () => {
    installApi('host'); renderRoute('/host');
    const panel = (await screen.findByRole('heading', { name: 'Mesas y grupos preparados' })).closest('section')!;
    const representative = within(panel).getByRole('heading', { name: '*Mesa 1' }).closest('article')!;
    expect(within(representative).getByText('Terraza')).toBeVisible();
    expect(await within(representative).findByText('Capacidad del grupo: 6')).toBeVisible();
    expect(within(representative).getByText('Mesa 2')).toBeVisible();
    expect(within(representative).queryByRole('button', { name: 'Agregar mesa' })).not.toBeInTheDocument();
    expect(within(representative).queryByRole('button', { name: 'Disolver grupo' })).not.toBeInTheDocument();
    const member = within(panel).getByRole('heading', { name: 'Mesa 2' }).closest('article')!;
    expect(within(member).queryByRole('button', { name: 'Retirar mesa' })).not.toBeInTheDocument();
    expect(within(member).queryByRole('button', { name: 'Mover mesa' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Abrir mesa' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Nuevo código' })).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent('Grupo 5');
  });

  it('requires explicit responsibility when joining tables assigned to different waiters', async () => {
    const api = installApi('waiter', detail(), { deferAssignments: true, deferPreview: true }); renderRoute('/waiter'); const user = userEvent.setup();
    const panel = (await screen.findByRole('heading', { name: 'Preparar o unir mesas' })).closest('section')!;
    const mesa3 = within(panel).getByRole('heading', { name: 'Mesa 3' }).closest('article')!;
    await user.click(within(mesa3).getByRole('button', { name: 'Unir mesas' }));
    await user.click(screen.getByRole('checkbox', { name: /Mesa 4/ }));
    await user.click(screen.getByRole('checkbox', { name: /Mesa 5/ }));
    const confirm = screen.getByRole('button', { name: 'Confirmar unión' });
    expect(confirm).toBeDisabled();
    expect(screen.getByText('Calculando capacidad…')).toBeVisible();
    api.resolvePreview();
    expect(await screen.findByText('Capacidad: 10')).toBeVisible();
    expect(api.calls.some((call) => call.url.endsWith('/table-management/groups:preview') && call.init?.method === 'POST')).toBe(true);
    expect(confirm).toBeDisabled();
    api.resolveAssignments();
    expect(await screen.findByRole('checkbox', { name: 'Luis Mesero' })).toBeVisible();
    await user.click(screen.getByRole('checkbox', { name: 'Luis Mesero' }));
    await user.click(confirm);
    expect(await screen.findByText('Grupo confirmado con capacidad 10.')).toBeVisible();
    await waitFor(() => expect(api.calls.some((call) => call.url.endsWith('/table-management/groups') && call.init?.method === 'POST')).toBe(true));
    const call = api.calls.find((value) => value.url.endsWith('/table-management/groups') && value.init?.method === 'POST')!;
    expect(JSON.parse(String(call.init?.body))).toMatchObject({ representative_resource_id: 103, joined_resource_ids: [104, 105], responsible_membership_ids: [201] });
  });

  it('surfaces a CREATE conflict after preview and refetches canonical tables', async () => {
    const api = installApi('waiter', detail(), { createGroupConflict: true }); renderRoute('/waiter'); const user = userEvent.setup();
    const panel = (await screen.findByRole('heading', { name: 'Preparar o unir mesas' })).closest('section')!;
    const mesa3 = within(panel).getByRole('heading', { name: 'Mesa 3' }).closest('article')!;
    await user.click(within(mesa3).getByRole('button', { name: 'Unir mesas' }));
    await user.click(screen.getByRole('checkbox', { name: /Mesa 4/ }));
    await user.click(screen.getByRole('checkbox', { name: /Mesa 5/ }));
    expect(await screen.findByText('Capacidad: 10')).toBeVisible();
    await user.click(screen.getByRole('checkbox', { name: 'Luis Mesero' }));
    await user.click(screen.getByRole('button', { name: 'Confirmar unión' }));
    expect(await screen.findByText('El estado cambió. Actualizamos las mesas; intenta nuevamente.')).toBeVisible();
    await waitFor(() => expect(api.calls.filter((call) => call.url.endsWith('/table-management/tables')).length).toBeGreaterThan(1));
  });

  it('captures party size and waiter, creates the pre-service request, and projects sender progress', async () => {
    const ready = detail({ status: 'READY', entered_at: '2026-09-28T12:05:00Z', ready_at: '2026-09-28T12:10:00Z', allowed_actions: [], responses: [{ id: 1, sequence: 1, author: { membership_id: 201, display_name: 'Luis Mesero', email: null }, content: 'Preparando Terraza.', created_at: '2026-09-28T12:06:00Z' }], prepared_table: { resource_id: 101, code: 'M01', name: 'Mesa 1', physical_capacity: 4, is_group_representative: true, group_id: 5, members: [{ resource_id: 101, code: 'M01', name: 'Mesa 1', physical_capacity: 4 }, { resource_id: 102, code: 'M02', name: 'Mesa 2', physical_capacity: 2 }], derived_group_capacity: 6 } });
    const api = installApi('host', ready); renderRoute('/host'); const user = userEvent.setup();
    expect(await screen.findByText('Listo', { selector: '.message-progress' })).toBeVisible();
    expect(await screen.findByText('La mesa está lista: *Mesa 1')).toBeVisible();
    expect(screen.getByText('Capacidad: 6')).toBeVisible();
    expect(screen.getByText(/Preparando Terraza/)).toBeVisible();
    expect(screen.getByText('Historial')).toBeVisible();
    const size = screen.getByLabelText('¿Cuántas personas son?');
    expect(size).toHaveAttribute('min', '1'); expect(size).toBeRequired();
    await user.type(size, '3'); await user.selectOptions(screen.getByLabelText('Mesero'), '201'); await user.click(screen.getByRole('button', { name: 'Solicitar mesa' }));
    await waitFor(() => expect(api.calls.some((call) => call.url.endsWith('/internal-messages') && call.init?.method === 'POST')).toBe(true));
    const call = api.calls.find((value) => value.url.endsWith('/internal-messages') && value.init?.method === 'POST')!;
    expect(JSON.parse(String(call.init?.body))).toEqual({ recipient_membership_id: 201, type: 'TABLE_PREPARATION_REQUEST', text: 'Se requiere mesa para 3 personas.', party_size: 3 });
    expect(new Headers(call.init?.headers).get('Idempotency-Key')).toBeTruthy();
    expect(api.calls.some((value) => value.url.includes('/service-sessions') && value.init?.method === 'POST')).toBe(false);
  });

  it('projects Solicitado from canonical details', async () => {
    installApi('host', detail()); renderRoute('/host');
    expect(await screen.findByText('Solicitado', { selector: '.message-progress' })).toBeVisible();
  });

  it('projects Enterado from canonical details', async () => {
    installApi('host', detail({ status: 'ENTERED', entered_at: '2026-09-28T12:05:00Z', enterado: { membership_id: 201, entered_at: '2026-09-28T12:05:00Z' } })); renderRoute('/host');
    expect(await screen.findByText('Enterado', { selector: '.message-progress' })).toBeVisible();
  });

  it('projects an individual prepared table from canonical READY details', async () => {
    installApi('host', detail({ status: 'READY', entered_at: '2026-09-28T12:05:00Z', ready_at: '2026-09-28T12:10:00Z', allowed_actions: [], prepared_table: { resource_id: 103, code: 'M03', name: 'Mesa 3', physical_capacity: 4, is_group_representative: false, group_id: null, members: [{ resource_id: 103, code: 'M03', name: 'Mesa 3', physical_capacity: 4 }], derived_group_capacity: null } })); renderRoute('/host');
    expect(await screen.findByText('La mesa está lista: Mesa 3')).toBeVisible();
    expect(screen.getByText('Capacidad: 4')).toBeVisible();
  });

  it('runs Enterado, response and READY only after selecting a prepared table, without opening service', async () => {
    const api = installApi('waiter'); renderRoute('/waiter'); const user = userEvent.setup();
    expect(await screen.findByText('Ayuda al comensal')).toBeVisible();
    expect(screen.getByRole('link', { name: /Inicio/ })).toBeVisible();
    expect(screen.getByText(/Atención compartida de Sucursal Centro/)).toBeVisible();
    const card = (await screen.findByText('Mesa para 6 personas')).closest('article')!;
    expect(within(card).getByRole('button', { name: 'Enterado' })).toBeVisible();
    expect(within(card).queryByRole('button', { name: 'Listo' })).not.toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Enterado' }));
    expect(await within(card).findByRole('button', { name: 'Responder' })).toBeVisible();
    const readyButton = within(card).getByRole('button', { name: 'Listo' });
    expect(readyButton).toBeDisabled();
    expect(within(card).getByText('Historial')).toBeVisible();
    await user.click(within(card).getByRole('button', { name: 'Responder' }));
    await user.type(within(card).getByLabelText('Respuesta a Recepción'), 'Voy a preparar el grupo.');
    await user.click(within(card).getByRole('button', { name: 'Enviar' }));
    expect(await within(card).findByText(/Voy a preparar el grupo/)).toBeVisible();
    await user.selectOptions(within(card).getByLabelText('Mesa preparada para 6 personas'), '101');
    const selectedGroup = within(card).getByLabelText('Grupo de mesas seleccionado');
    expect(within(selectedGroup).getAllByText('*Mesa 1')).toHaveLength(2);
    expect(within(selectedGroup).getByText(/Mesa 2/)).toBeVisible();
    await user.click(within(card).getByRole('button', { name: 'Listo' }));
    const readyProjection = (await within(card).findByText('Capacidad: 6')).closest('.prepared-table-result') as HTMLElement;
    expect(within(readyProjection).getAllByText('*Mesa 1')).toHaveLength(2);
    expect(within(readyProjection).getByText('Mesa 2')).toBeVisible();
    expect(within(card).queryByRole('button', { name: 'Responder' })).not.toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: 'Listo' })).not.toBeInTheDocument();
    expect(api.calls.some((call) => call.url.endsWith('/internal-messages/700/ready') && call.init?.method === 'POST')).toBe(true);
    expect(api.calls.some((call) => call.url.includes('/service-sessions') && call.init?.method === 'POST')).toBe(false);
    const openButton = await within(card).findByRole('button', { name: 'Abrir mesa' });
    await user.click(openButton);
    expect(await within(card).findByText('4827')).toBeVisible();
    const openCall = api.calls.find((call) => call.url.endsWith('/resources/101/service-sessions') && call.init?.method === 'POST');
    expect(JSON.parse(String(openCall?.init?.body))).toEqual({ party_size: 6 });
    expect(api.calls.some((call) => call.url.includes('/access-code/regenerate'))).toBe(false);

    const tablePanel = screen.getByRole('heading', { name: 'Preparar o unir mesas' }).closest('section')!;
    const mesa3 = within(tablePanel).getByRole('heading', { name: 'Mesa 3' }).closest('article')!;
    await user.click(within(mesa3).getByRole('button', { name: 'Unir mesas' }));
    await user.click(screen.getByRole('checkbox', { name: /Mesa 4/ }));
    expect(await screen.findByText('Capacidad: 8')).toBeVisible();
    await user.click(screen.getByRole('checkbox', { name: 'Luis Mesero' }));
    await user.click(screen.getByRole('button', { name: 'Confirmar unión' }));
    await waitFor(() => expect(api.calls.some((call) => call.url.endsWith('/table-management/groups') && call.init?.method === 'POST')).toBe(true));
  });
});
