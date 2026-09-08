import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { StaffIdentity } from '../api/contracts';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { storeCredential } from '../session/storage';
import { ThemeProvider } from '../theme/ThemeContext';

const identity: StaffIdentity = {
  user_id: 7,
  email: 'staff@example.test',
  display_name: 'Ana Operaciones',
  tenant_id: 11,
  membership_id: 13,
  roles: ['HOST'],
  permissions: ['location.read', 'resource.read', 'restaurant_service.read'],
};

const locations = {
  items: [{ id: 21, tenant_id: 11, organization_id: 31, code: 'CENTRO', name: 'Sucursal Centro', timezone: 'America/Mexico_City', status: 'ACTIVE' }],
  limit: 100,
  offset: 0,
};

function response(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

function storedCredential(expiresAt = new Date(Date.now() + 60_000).toISOString()) {
  storeCredential({ accessToken: 'staff-token', expiresAt, tenantId: 11, tenantName: 'Restaurantes Norte' });
}

function mockApi(options: { me?: StaffIdentity; locations?: typeof locations; loginStatus?: number } = {}) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith('/auth/login')) {
      if (options.loginStatus) return response({ detail: 'Invalid authentication credentials' }, options.loginStatus);
      return response({
        access_token: 'staff-token', token_type: 'bearer', expires_in: 3600,
        user: { id: 7, email: identity.email, display_name: identity.display_name },
        tenant: { id: 11, name: 'Restaurantes Norte', slug: 'norte', membership_id: 13 },
      });
    }
    if (url.endsWith('/auth/me')) return response(options.me ?? identity);
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
    expect(screen.getByLabelText('Correo electrónico')).toHaveAttribute('autocomplete', 'username');
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'current-password');
    const user = userEvent.setup();
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'ECIP Staff, inicio de sesión' }));
  });

  it('authenticates, loads authoritative identity, and establishes the sole active location', async () => {
    const { calls } = mockApi();
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Correo electrónico'), identity.email);
    await user.type(screen.getByLabelText('Contraseña'), 'correct-password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(screen.getAllByText('Ana Operaciones').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Sucursal Centro').length).toBeGreaterThan(0);
    expect(calls.some((call) => call.url.endsWith('/auth/me'))).toBe(true);
    const login = calls.find((call) => call.url.endsWith('/auth/login'));
    expect(JSON.parse(String(login?.init?.body))).toEqual({ email: identity.email, password: 'correct-password' });
  });

  it('shows controlled invalid-credential feedback', async () => {
    mockApi({ loginStatus: 401 });
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Correo electrónico'), identity.email);
    await user.type(screen.getByLabelText('Contraseña'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Ingresar a operación' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Acceso rechazado');
    expect(screen.getByRole('alert')).toHaveTextContent('correo o la contraseña');
  });

  it('distinguishes a login network failure from rejected credentials', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    renderApp('/login');
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Correo electrónico'), identity.email);
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

  it('clears auth and location state on logout', async () => {
    storedCredential();
    sessionStorage.setItem('staff-location-context-v1', '21');
    mockApi();
    renderApp('/');
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Salir' }));
    expect(await screen.findByRole('heading', { name: 'Bienvenido de vuelta' })).toBeVisible();
    expect(sessionStorage.getItem('staff-auth-session-v1')).toBeNull();
    expect(sessionStorage.getItem('staff-location-context-v1')).toBeNull();
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

  it('requires explicit choice when several active tenant locations are returned', async () => {
    storedCredential();
    mockApi({ locations: { ...locations, items: [...locations.items, { ...locations.items[0], id: 22, code: 'SUR', name: 'Sucursal Sur' }] } });
    renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Elige dónde operar' })).toBeVisible();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /Sucursal Sur/ }));
    expect(await screen.findByRole('heading', { name: 'Todo en contexto.' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Ubicación operativa' })).toHaveValue('22');
  });

  it('uses authoritative tenant and organization names when read capabilities exist', async () => {
    storedCredential();
    mockApi({ me: { ...identity, permissions: [...identity.permissions, 'tenant.read', 'organization.read'] } });
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
