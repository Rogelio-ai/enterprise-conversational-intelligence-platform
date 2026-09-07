import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

const contextKey = 'a'.repeat(43);
const joinResponse = {
  diner_session_id: 11,
  service_session_id: 22,
  conversation_id: 33,
  display_name: 'Ana',
  customer_id: null,
  access_token: 'secret-token',
  token_type: 'bearer',
  expires_at: new Date(Date.now() + 3_600_000).toISOString(),
  expires_in: 3600,
};

function seedSession(expiresAt = joinResponse.expires_at) {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11,
    serviceSessionId: 22,
    conversationId: 33,
    displayName: 'Ana',
    customerId: null,
    accessToken: 'secret-token',
    expiresAt,
  }));
}

function renderApp(route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('diner access', () => {
  it('shows a recoverable error when entry context is missing', () => {
    renderApp('/');
    expect(screen.getByRole('heading', { name: 'Falta el acceso de la mesa' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Entrar' })).not.toBeInTheDocument();
  });

  it('validates required fields without contacting the API', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    renderApp(`/join/${contextKey}`);
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(screen.getByText('Escribe tu nombre para continuar.')).toBeInTheDocument();
    expect(screen.getByText('Ingresa los cuatro dígitos del código.')).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('uses the authoritative join contract and reaches the authenticated shell', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(joinResponse), { status: 201, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    renderApp(`/join/${contextKey}`);
    await userEvent.type(screen.getByLabelText('Nombre'), '  Ana  ');
    await userEvent.type(screen.getByLabelText(/Email/), 'ana@example.com');
    await userEvent.type(screen.getByLabelText('Código de acceso'), '0427');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('heading', { name: 'Hola, Ana' })).toBeInTheDocument();
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(request.body as string)).toEqual({
      join_context_key: contextKey,
      display_name: 'Ana',
      email: 'ana@example.com',
      access_code: '0427',
    });
  });

  it('presents an invalid join without clearing entered values', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'http_error', message: 'Invalid diner join credentials' } }), { status: 401, headers: { 'Content-Type': 'application/json' } })));
    renderApp(`/join/${contextKey}`);
    await userEvent.type(screen.getByLabelText('Nombre'), 'Luis');
    await userEvent.type(screen.getByLabelText('Código de acceso'), '9999');
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('El código o el acceso de esta mesa no son válidos');
    expect(screen.getByLabelText('Nombre')).toHaveValue('Luis');
  });

  it('restores and validates a session with the bearer token after refresh', async () => {
    seedSession();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 11, service_session_id: 22, resource_id: 44, conversation_id: 33, display_name: 'Ana', customer_id: null, status: 'ACTIVE', joined_at: new Date().toISOString(), ended_at: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    renderApp('/app');
    expect(await screen.findByRole('heading', { name: 'Hola, Ana' })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(new Headers(request.headers).get('Authorization')).toBe('Bearer secret-token');
  });

  it('returns an expired browser session to a safe unauthenticated state', () => {
    seedSession(new Date(Date.now() - 1_000).toISOString());
    renderApp('/app');
    expect(screen.getByRole('heading', { name: 'Tu acceso ya no está activo' })).toBeInTheDocument();
    expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull();
  });

  it('preserves the SESSION_CLOSED distinction during restoration', async () => {
    seedSession();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'SESSION_CLOSED', message: 'Session closed', state: 'SESSION_CLOSED', next_action: 'LEAVE_SESSION' },
    }), { status: 409, headers: { 'Content-Type': 'application/json' } })));
    renderApp('/app');
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull();
  });

  it('clears authentication rejected by the backend', async () => {
    seedSession();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'http_error', message: 'Invalid diner authentication credentials' },
    }), { status: 401, headers: { 'Content-Type': 'application/json' } })));
    renderApp('/app');
    expect(await screen.findByRole('heading', { name: 'Tu acceso ya no está activo' })).toBeInTheDocument();
    expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull();
  });
});
