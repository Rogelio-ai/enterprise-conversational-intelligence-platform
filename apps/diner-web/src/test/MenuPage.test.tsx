import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

const futureExpiration = new Date(Date.now() + 3_600_000).toISOString();
const currentSession = {
  id: 11,
  service_session_id: 22,
  resource_id: 44,
  conversation_id: 33,
  display_name: 'Ana',
  customer_id: null,
  status: 'ACTIVE',
  joined_at: new Date().toISOString(),
  ended_at: null,
};

const menuResponse = {
  menus: [{
    id: 5,
    name: 'Desayunos de la casa',
    sections: [{
      id: 7,
      name: 'Favoritos',
      products: [
        {
          id: 101,
          name: 'Desayuno campirano',
          description: 'Huevos, frijoles de la olla y tortillas recién hechas.',
          category_path: [{ id: 1, name: 'Comida' }, { id: 2, name: 'Desayunos' }],
          price: { amount: '125.0000', currency: 'MXN' },
          orderable: true,
          configuration_available: true,
          configuration_required: true,
        },
        {
          id: 102,
          name: 'Pan de temporada',
          description: null,
          category_path: [{ id: 3, name: 'Panadería' }],
          price: { amount: '65.0000', currency: 'MXN' },
          orderable: false,
          configuration_available: false,
          configuration_required: false,
        },
      ],
    }],
  }],
  experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['SHOW_PRODUCT', 'ADD_ITEM'], next_action: null },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11,
    serviceSessionId: 22,
    conversationId: 33,
    displayName: 'Ana',
    customerId: null,
    accessToken: 'menu-token',
    expiresAt: futureExpiration,
  }));
}

function renderApp(route = '/menu') {
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

function mockApi(menuHandler: () => Promise<Response>) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(jsonResponse(currentSession));
    if (url.endsWith('/diner/menu')) return menuHandler();
    return Promise.reject(new Error(`Unexpected request: ${url} ${init?.method || 'GET'}`));
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  seedSession();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('menu browsing', () => {
  it('navigates from the authenticated shell and renders the authoritative hierarchy', async () => {
    const fetchMock = mockApi(() => Promise.resolve(jsonResponse(menuResponse)));
    renderApp('/app');

    await userEvent.click(await screen.findByRole('link', { name: /Ver el menú/ }));
    expect(await screen.findByRole('heading', { name: 'Menú', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Desayunos de la casa' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Favoritos' })).toBeInTheDocument();
    expect(screen.getByText('Comida · Desayunos')).toBeInTheDocument();
    expect(screen.getByText('$125.00')).toBeInTheDocument();
    expect(screen.getByText('Requiere elegir opciones')).toBeInTheDocument();
    expect(screen.getByText('No disponible')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Ver Pan de temporada' })).not.toBeInTheDocument();

    const menuCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/diner/menu'));
    expect(menuCall).toBeDefined();
    expect(new Headers(menuCall?.[1]?.headers).get('Authorization')).toBe('Bearer menu-token');
  });

  it('shows a menu-specific structured loading state', async () => {
    mockApi(() => new Promise(() => undefined));
    renderApp();
    expect(await screen.findByText('Cargando el menú…')).toBeInTheDocument();
  });

  it('shows a deliberate empty state when the projection has no products', async () => {
    mockApi(() => Promise.resolve(jsonResponse({ ...menuResponse, menus: [] })));
    renderApp();
    expect(await screen.findByRole('heading', { name: 'Aún no hay productos para mostrar' })).toBeInTheDocument();
  });

  it('offers recovery from a controlled menu error', async () => {
    let attempts = 0;
    mockApi(() => {
      attempts += 1;
      return Promise.resolve(attempts === 1 ? jsonResponse({ error: { code: 'http_error' } }, 500) : jsonResponse(menuResponse));
    });
    renderApp();
    expect(await screen.findByRole('heading', { name: 'No pudimos mostrar el menú' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('Desayuno campirano')).toBeInTheDocument();
    expect(attempts).toBe(2);
  });

  it('navigates an orderable product to the Product Detail route boundary', async () => {
    mockApi(() => Promise.resolve(jsonResponse(menuResponse)));
    renderApp();
    const productLink = await screen.findByRole('link', { name: 'Ver Desayuno campirano' });
    expect(productLink).toHaveAttribute('href', '/products/101');
    await userEvent.click(productLink);
    expect(await screen.findByRole('heading', { name: 'Desayuno campirano' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver al menú' })).toHaveAttribute('href', '/menu');
  });

  it('keeps the C1 access route unauthenticated and unaffected', async () => {
    sessionStorage.clear();
    vi.stubGlobal('fetch', vi.fn());
    renderApp(`/join/${'a'.repeat(43)}`);
    expect(screen.getByRole('heading', { name: 'Únete a tu mesa' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText('Nombre')).toBeEnabled());
  });
});
