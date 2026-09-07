import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

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

const productDetail = {
  product: {
    id: 101,
    name: 'Desayuno campirano',
    description: 'Huevos, frijoles de la olla y tortillas recién hechas.',
    category_path: [{ id: 1, name: 'Comida' }, { id: 2, name: 'Desayunos' }],
    price: { amount: '125.0000', currency: 'MXN' },
    orderable: true,
    configuration_available: true,
    configuration_required: true,
  },
  fixed_components: [
    { product_id: 201, name: 'Fruta de temporada', quantity: '1.0000' },
    { product_id: 202, name: 'Tortillas', quantity: '2.0000' },
  ],
  choice_groups: [{
    id: 301,
    name: 'Bebida',
    min_selections: 1,
    max_selections: 1,
    required: true,
    options: [{ id: 401, product_id: 501, name: 'Café', description: null, quantity: '1.0000' }],
  }],
  experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['ADD_ITEM', 'BROWSE_MENU'], next_action: 'CONFIGURE_PRODUCT' },
};

const emptyMenu = {
  menus: [],
  experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: [], next_action: null },
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
    accessToken: 'product-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function renderApp(route = '/products/101') {
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

function mockApi(productHandler: () => Promise<Response>) {
  const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(jsonResponse(currentSession));
    if (url.endsWith('/diner/products/101')) return productHandler();
    if (url.endsWith('/diner/menu')) return Promise.resolve(jsonResponse(emptyMenu));
    return Promise.reject(new Error(`Unexpected request: ${url}`));
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

describe('product detail', () => {
  it('renders authoritative identity, price, fixed components and configuration requirement', async () => {
    const fetchMock = mockApi(() => Promise.resolve(jsonResponse(productDetail)));
    renderApp();

    expect(await screen.findByRole('heading', { name: 'Desayuno campirano', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Huevos, frijoles de la olla y tortillas recién hechas.')).toBeInTheDocument();
    expect(screen.getByText('$125.00')).toBeInTheDocument();
    expect(screen.getByText('Disponible')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Incluye' })).toBeInTheDocument();
    expect(screen.getByText('Fruta de temporada')).toBeInTheDocument();
    expect(screen.getByText('Cantidad 2')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Elige algunas opciones' })).toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();

    const productCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/diner/products/101'));
    expect(new Headers(productCall?.[1]?.headers).get('Authorization')).toBe('Bearer product-token');
  });

  it('renders a simple non-orderable product without fabricating structure', async () => {
    mockApi(() => Promise.resolve(jsonResponse({
      ...productDetail,
      product: {
        ...productDetail.product,
        name: 'Pan de temporada',
        description: null,
        orderable: false,
        configuration_available: false,
        configuration_required: false,
      },
      fixed_components: [],
      choice_groups: [],
    })));
    renderApp();
    expect(await screen.findByRole('heading', { name: 'Pan de temporada' })).toBeInTheDocument();
    expect(screen.getAllByText('No disponible').length).toBeGreaterThan(0);
    expect(screen.getByText('No disponible por el momento')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Incluye' })).not.toBeInTheDocument();
    expect(screen.queryByText('Se puede personalizar')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /pedir|agregar/i })).not.toBeInTheDocument();
  });

  it('presents optional configuration without creating interactive selection', async () => {
    mockApi(() => Promise.resolve(jsonResponse({
      ...productDetail,
      product: { ...productDetail.product, configuration_required: false },
    })));
    renderApp();
    expect(await screen.findByRole('heading', { name: 'Se puede personalizar' })).toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  });

  it('shows a structurally appropriate loading state', async () => {
    mockApi(() => new Promise(() => undefined));
    renderApp();
    expect(await screen.findByText('Cargando el producto…')).toBeInTheDocument();
  });

  it('presents the authoritative unavailable/not-found state', async () => {
    mockApi(() => Promise.resolve(jsonResponse({
      error: { state: 'PRODUCT_UNAVAILABLE', code: 'PRODUCT_UNAVAILABLE', message: 'Product unavailable' },
    }, 404)));
    renderApp();
    expect(await screen.findByRole('heading', { name: 'Este producto no está disponible' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reintentar' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver al menú' })).toHaveAttribute('href', '/menu');
  });

  it('recovers from a controlled transient error', async () => {
    let attempts = 0;
    mockApi(() => {
      attempts += 1;
      return Promise.resolve(attempts === 1 ? jsonResponse({ error: { code: 'http_error' } }, 500) : jsonResponse(productDetail));
    });
    renderApp();
    expect(await screen.findByRole('heading', { name: 'No pudimos cargar el producto' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('heading', { name: 'Desayuno campirano' })).toBeInTheDocument();
    expect(attempts).toBe(2);
  });

  it('returns to Menu through the explicit navigation action', async () => {
    mockApi(() => Promise.resolve(jsonResponse(productDetail)));
    renderApp();
    await userEvent.click(await screen.findByRole('link', { name: 'Volver al menú' }));
    expect(await screen.findByRole('heading', { name: 'Menú', level: 1 })).toBeInTheDocument();
  });

  it('rejects a malformed product route locally without calling the product endpoint', async () => {
    const fetchMock = mockApi(() => Promise.resolve(jsonResponse(productDetail)));
    renderApp('/products/not-a-product');
    expect(await screen.findByRole('heading', { name: 'No pudimos abrir este producto' })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/diner/products/'))).toBe(false);
  });
});
