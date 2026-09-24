import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import {
  readStaffResumeHint,
  storeCredential,
  storeStaffResumeHint,
} from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const identity: StaffIdentity = {
  user_id: 7,
  username: 'ana.operaciones',
  email: 'staff@example.test',
  display_name: 'Ana Operaciones',
  tenant_id: 11,
  membership_id: 13,
  authorized_location_ids: [21],
  roles: ['HOST'],
  permissions: ['location.read', 'resource.read', 'restaurant_service.read'],
  location_authorities: [{
    location_id: 21,
    roles: ['HOST'],
    permissions: ['location.read', 'resource.read', 'restaurant_service.read'],
  }],
};

const locations = {
  items: [{ id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' }],
  limit: 100,
  offset: 0,
};
const southLocation = {
  ...locations.items[0], id: 22, code: 'SUR', name: 'Sucursal Sur',
};

function response(body: unknown, status = 200) {
  if (status === 204) return Promise.resolve(new Response(null, { status }));
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

function storedCredential(expiresAt = new Date(Date.now() + 60_000).toISOString()) {
  storeCredential({ accessToken: 'staff-token', expiresAt, tenantId: 11, tenantName: 'Restaurantes Norte' });
}

function mockApi(options: {
  me?: StaffIdentity;
  locations?: typeof locations;
  loginStatus?: number;
  loginBody?: unknown;
} = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/login')) {
      if (options.loginStatus) return response(
        options.loginBody ?? { detail: 'Invalid authentication credentials' },
        options.loginStatus,
      );
      return response({
        access_token: 'staff-token', token_type: 'bearer', expires_in: 3600,
        user: { id: 7, username: identity.username, email: identity.email, display_name: identity.display_name },
        tenant: { id: 11, name: 'Restaurantes Norte', slug: 'norte', membership_id: 13 },
      });
    }
    if (url.endsWith('/auth/me')) return response(options.me ?? identity);
    if (url.endsWith('/auth/logout')) return response(null, 204);
    if (url.includes('/locations?')) return response(options.locations ?? locations);
    if (url.endsWith('/tenants/current')) return response({ id: 11, name: 'Restaurantes Norte', slug: 'norte', status: 'ACTIVE' });
    if (url.includes('/organizations/')) return response({ id: 31, tenant_id: 11, code: 'NORTE', name: 'Grupo Norte', status: 'ACTIVE' });
    return response({ detail: 'Not found' }, 404);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, calls };
}

function renderApp(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[path]}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('staff foundation', () => {
  it('renders a semantic, keyboard-reachable staff login form', async () => {
    renderApp('/login');
    expect(screen.getByRole('heading', { name: 'Bienvenido de vuelta' })).toBeVisible();
    expect(screen.getByLabelText('Usuario')).toHaveAttribute('autocomplete', 'username');
    expect(screen.queryByLabelText('Correo electrónico')).not.toBeInTheDocument();
    expect(screen.queryByText(/Identificador de tenant/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'current-password');
    const user = userEvent.setup();
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'ECIP Staff, inicio de sesión' }));
  });

  it('authenticates, loads authoritative identity, and establishes the sole active location', async () => {
    const { calls } = mockApi();
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Usuario'), identity.username);
    await user.type(screen.getByLabelText('Contraseña'), 'correct-password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(screen.getAllByText('Ana Operaciones').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Sucursal Centro').length).toBeGreaterThan(0);
    expect(calls.some((call) => call.url.endsWith('/auth/me'))).toBe(true);
    const login = calls.find((call) => call.url.endsWith('/auth/login'));
    expect(JSON.parse(String(login?.init?.body))).toEqual({ username: identity.username, password: 'correct-password' });
  });

  it('shows controlled invalid-credential feedback', async () => {
    mockApi({ loginStatus: 401 });
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Usuario'), identity.username);
    await user.type(screen.getByLabelText('Contraseña'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Acceso rechazado');
    expect(screen.getByRole('alert')).toHaveTextContent('usuario o la contraseña');
  });

  it('shows a clear active-session conflict without treating credentials as invalid', async () => {
    mockApi({
      loginStatus: 409,
      loginBody: { error: {
        code: 'staff_already_logged_in',
        message: 'Staff already has an active session',
      }, correlation_id: 'test-correlation-id' },
    });
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Usuario'), identity.username);
    await user.type(screen.getByLabelText('Contraseña'), 'correct-password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya tienes una sesión activa');
    expect(screen.getByRole('alert')).toHaveTextContent('Cierra tu sesión actual');
    expect(screen.getByRole('alert')).not.toHaveTextContent('usuario o la contraseña no son válidos');
  });

  it('distinguishes a login network failure from rejected credentials', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Usuario'), identity.username);
    await user.type(screen.getByLabelText('Contraseña'), 'password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión');
    expect(screen.getByRole('alert')).not.toHaveTextContent('Acceso rechazado');
  });

  it('protects staff routes from unauthenticated access', async () => {
    renderApp('/kitchen');
    expect(await screen.findByRole('heading', { name: 'Bienvenido de vuelta' })).toBeVisible();
  });

  it('restores a valid staff credential through /auth/me without diner semantics', async () => {
    storedCredential();
    const { calls } = mockApi();
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(calls[0].url).toMatch(/\/auth\/me$/);
    expect(calls.every((call) => !call.url.includes('/diner'))).toBe(true);
    const authorization = new Headers(calls[0].init?.headers).get('Authorization');
    expect(authorization).toBe('Bearer staff-token');
  });

  it('keeps a credential on temporary restoration failure and offers retry', async () => {
    storedCredential();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Tu sesión sigue guardada' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    expect(sessionStorage.getItem('staff-auth-session-v1')).not.toBeNull();
  });

  it('clears an expired credential and returns safely to login', async () => {
    storedCredential(new Date(Date.now() - 1_000).toISOString());
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Bienvenido de vuelta' })).toBeVisible();
    expect(screen.getByRole('status')).toHaveTextContent('Tu sesión terminó');
    expect(sessionStorage.getItem('staff-auth-session-v1')).toBeNull();
  });

  it('ends an active session when its known expiration deadline arrives', async () => {
    storedCredential(new Date(Date.now() + 500).toISOString());
    mockApi();
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(await screen.findByRole('heading', { name: 'Bienvenido de vuelta' }, { timeout: 1_500 })).toBeVisible();
    expect(screen.getByRole('status')).toHaveTextContent('Tu sesión terminó');
    expect(sessionStorage.getItem('staff-auth-session-v1')).toBeNull();
  });

  it('closes backend auth, clears local credentials, and preserves only the resume hint on logout', async () => {
    storedCredential();
    sessionStorage.setItem('staff-location-context-v1', '21');
    const { calls } = mockApi();
    renderApp('/');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Salir' }));
    expect(await screen.findByRole('heading', { name: 'Bienvenido de vuelta' })).toBeVisible();
    expect(sessionStorage.getItem('staff-auth-session-v1')).toBeNull();
    expect(sessionStorage.getItem('staff-location-context-v1')).toBeNull();
    expect(readStaffResumeHint()).toEqual({
      identityKey: identity.username, locationId: 21, workspacePath: '/',
    });
    expect(localStorage.getItem('staff-resume-hint-v1')).not.toMatch(/token|password|credential/i);
    const logout = calls.find((call) => call.url.endsWith('/auth/logout'));
    expect(logout?.init?.method).toBe('POST');
    expect(new Headers(logout?.init?.headers).get('Authorization')).toBe('Bearer staff-token');
  });

  it('shows only workspaces supported by the effective permission set', async () => {
    storedCredential();
    mockApi();
    renderApp('/');
    const navigation = await screen.findByRole('navigation', { name: 'Espacios de trabajo' });
    expect(within(navigation).getByRole('link', { name: /Host/ })).toBeVisible();
    expect(within(navigation).queryByRole('link', { name: /Cocina/ })).not.toBeInTheDocument();
    expect(within(navigation).queryByRole('link', { name: /Caja/ })).not.toBeInTheDocument();
    expect(within(navigation).queryByRole('link', { name: /Mesero/ })).not.toBeInTheDocument();
  });

  it('denies a direct workspace route when capabilities are incomplete', async () => {
    storedCredential();
    mockApi();
    renderApp('/kitchen');
    expect(await screen.findByRole('heading', { name: 'Este espacio no está disponible' })).toBeVisible();
    expect(screen.getByText(/autorización permanece en el backend/i)).toBeVisible();
  });

  it.each([
    ['HOST', 'Host', ['location.read', 'resource.read', 'restaurant_service.read']],
    ['WAITER', 'Mesero', ['location.read', 'restaurant_service.read', 'restaurant_order.read', 'restaurant_check.read', 'operational_request.read']],
    ['KITCHEN', 'Cocina', ['location.read', 'preparation.read']],
    ['CASHIER', 'Caja', ['location.read', 'resource.read', 'cash_management.read', 'restaurant_check.read', 'restaurant_payment.read']],
    ['INVENTORY_MANAGER', 'Inventario', ['location.read', 'inventory.read']],
  ])('routes the %s profile only to capability-compatible workspaces', async (role, workspace, permissions) => {
    storedCredential();
    mockApi({ me: {
      ...identity,
      roles: [role],
      permissions,
      location_authorities: [{ location_id: 21, roles: [role], permissions }],
    } });
    renderApp('/');
    const navigation = await screen.findByRole('navigation', { name: 'Espacios de trabajo' });
    expect(within(navigation).getByRole('link', { name: workspace })).toBeVisible();
    expect(within(navigation).queryByRole('link', { name: 'Gerencia' })).not.toBeInTheDocument();
  });

  it('requires explicit choice when several active tenant locations are returned', async () => {
    storedCredential();
    mockApi({
      me: {
        ...identity,
        authorized_location_ids: [21, 22],
        location_authorities: [
          ...identity.location_authorities,
          { ...identity.location_authorities[0], location_id: 22 },
        ],
      },
      locations: { ...locations, items: [...locations.items, southLocation] },
    });
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Elige dónde operar' })).toBeVisible();
    const user = userEvent.setup();
    const selector = screen.getByRole('combobox', { name: 'Sucursal' });
    expect(within(selector).getByRole('option', { name: /Sucursal Centro/ })).toBeVisible();
    expect(within(selector).getByRole('option', { name: /Sucursal Sur/ })).toBeVisible();
    expect(screen.queryByLabelText(/tenant|location|ubicación.*id/i)).not.toBeInTheDocument();
    await user.selectOptions(selector, '22');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Sucursal operativa' })).toHaveValue('22');
  });

  it('shows a controlled no-access state when CURRENT authority has zero Locations', async () => {
    storedCredential();
    const { calls } = mockApi({ me: {
      ...identity,
      authorized_location_ids: [],
      location_authorities: [],
    } });
    renderApp('/host');
    expect(await screen.findByRole('heading', { name: 'No hay una ubicación operable' })).toBeVisible();
    expect(screen.queryByRole('navigation', { name: 'Espacios de trabajo' })).not.toBeInTheDocument();
    expect(calls.some((call) => call.url.includes('/locations?'))).toBe(false);
  });

  it('auto-selects the sole CURRENT Location without an unnecessary selector', async () => {
    storedCredential();
    mockApi();
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(screen.queryByRole('combobox', { name: 'Sucursal' })).not.toBeInTheDocument();
    expect(screen.getAllByText('Sucursal Centro').length).toBeGreaterThan(0);
  });

  it('recomputes visible workspaces from the selected Location authority', async () => {
    const hostPermissions = ['location.read', 'resource.read', 'restaurant_service.read'];
    const kitchenPermissions = ['location.read', 'preparation.read'];
    storedCredential();
    mockApi({
      me: {
        ...identity,
        authorized_location_ids: [21, 22],
        roles: ['HOST', 'KITCHEN'],
        permissions: [...new Set([...hostPermissions, ...kitchenPermissions])],
        location_authorities: [
          { location_id: 21, roles: ['HOST'], permissions: hostPermissions },
          { location_id: 22, roles: ['KITCHEN'], permissions: kitchenPermissions },
        ],
      },
      locations: { ...locations, items: [...locations.items, southLocation] },
    });
    renderApp('/');
    const user = userEvent.setup();
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Sucursal' }), '21');
    let navigation = await screen.findByRole('navigation', { name: 'Espacios de trabajo' });
    expect(within(navigation).getByRole('link', { name: 'Host' })).toBeVisible();
    expect(within(navigation).queryByRole('link', { name: 'Cocina' })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sucursal operativa' }), '22');
    navigation = await screen.findByRole('navigation', { name: 'Espacios de trabajo' });
    expect(within(navigation).getByRole('link', { name: 'Cocina' })).toBeVisible();
    expect(within(navigation).queryByRole('link', { name: 'Host' })).not.toBeInTheDocument();
  });

  it('restores a valid Location and workspace after logout and a later login by the same Staff', async () => {
    storedCredential();
    const api = mockApi();
    const first = renderApp('/host');
    expect(await screen.findByRole('heading', { name: 'Mesas en servicio' })).toBeVisible();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Salir' }));
    expect(await screen.findByRole('heading', { name: 'Bienvenido de vuelta' })).toBeVisible();
    expect(readStaffResumeHint()).toEqual({
      identityKey: identity.username, locationId: 21, workspacePath: '/host',
    });
    first.unmount();

    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Usuario'), identity.username);
    await user.type(screen.getByLabelText('Contraseña'), 'correct-password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('heading', { name: 'Mesas en servicio' })).toBeVisible();
    expect(api.calls.filter((call) => call.url.endsWith('/auth/logout'))).toHaveLength(1);
  });

  it('keeps explicit Inicio navigation at Home and updates the resume intent', async () => {
    const waiterPermissions = [
      'location.read', 'restaurant_service.read', 'restaurant_order.read',
      'restaurant_check.read', 'operational_request.read',
    ];
    storeStaffResumeHint({
      identityKey: identity.username, locationId: 21, workspacePath: '/waiter',
    });
    storedCredential();
    mockApi({ me: {
      ...identity,
      roles: ['WAITER'],
      permissions: waiterPermissions,
      location_authorities: [{
        location_id: 21, roles: ['WAITER'], permissions: waiterPermissions,
      }],
    } });
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Solicitudes' })).toBeVisible();

    await userEvent.setup().click(screen.getByRole('link', { name: /Inicio/ }));

    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    await waitFor(() => expect(readStaffResumeHint()).toEqual({
      identityKey: identity.username, locationId: 21, workspacePath: '/',
    }));
    expect(screen.getAllByText('Sucursal Centro').length).toBeGreaterThan(0);
  });

  it('discards a stale Location hint and resolves the sole CURRENT Location', async () => {
    storeStaffResumeHint({
      identityKey: identity.username, locationId: 22, workspacePath: '/host',
    });
    storedCredential();
    mockApi();
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    await waitFor(() => expect(readStaffResumeHint()).toEqual({
      identityKey: identity.username, locationId: 21, workspacePath: '/',
    }));
  });

  it('does not restore a workspace removed from CURRENT Location permissions', async () => {
    storeStaffResumeHint({
      identityKey: identity.username, locationId: 21, workspacePath: '/host',
    });
    storedCredential();
    const kitchenPermissions = ['location.read', 'preparation.read'];
    mockApi({ me: {
      ...identity,
      roles: ['KITCHEN'],
      permissions: kitchenPermissions,
      location_authorities: [{
        location_id: 21, roles: ['KITCHEN'], permissions: kitchenPermissions,
      }],
    } });
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    const navigation = screen.getByRole('navigation', { name: 'Espacios de trabajo' });
    expect(within(navigation).getByRole('link', { name: 'Cocina' })).toBeVisible();
    expect(within(navigation).queryByRole('link', { name: 'Host' })).not.toBeInTheDocument();
  });

  it('never restores a resume hint belonging to different Staff', async () => {
    storeStaffResumeHint({
      identityKey: 'otra.persona', locationId: 21, workspacePath: '/host',
    });
    storedCredential();
    mockApi();
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    await waitFor(() => expect(readStaffResumeHint()).toEqual({
      identityKey: identity.username, locationId: 21, workspacePath: '/',
    }));
  });

  it('uses authoritative tenant and organization names when read capabilities exist', async () => {
    storedCredential();
    mockApi({ me: {
      ...identity,
      permissions: [...identity.permissions, 'tenant.read', 'organization.read'],
      location_authorities: [{
        ...identity.location_authorities[0],
        permissions: [...identity.location_authorities[0].permissions, 'organization.read'],
      }],
    } });
    renderApp('/');
    expect((await screen.findAllByText('Restaurantes Norte')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('Grupo Norte')).length).toBeGreaterThan(0);
  });

  it('cycles the shared light, dark, and system theme preference', async () => {
    renderApp('/login');
    const user = userEvent.setup();
    const button = screen.getByRole('button', { name: /Tema: Sistema/ });
    await user.click(button);
    expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    expect(localStorage.getItem('staff-theme')).toBe('light');
    await user.click(screen.getByRole('button', { name: /Tema: Claro/ }));
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  });

  it('performs no operational business mutation in the B1 shell', async () => {
    storedCredential();
    const { calls } = mockApi();
    renderApp('/');
    await screen.findByRole('heading', { name: 'Todo en contexto.' });
    await waitFor(() => expect(calls.length).toBeGreaterThanOrEqual(2));
    expect(calls.every((call) => !call.init?.method || call.init.method === 'GET')).toBe(true);
  });
});
