import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../routes/AppRoutes';
import { AuthProvider } from '../session/AuthContext';
import { ThemeProvider } from '../theme/ThemeContext';

const session = {
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

function draftItem(overrides: Record<string, unknown> = {}) {
  return {
    item_id: 701,
    product_id: 101,
    product_name: 'Desayuno campirano',
    composition_id: 801,
    quantity: '2.0000',
    position: 0,
    readiness: 'READY',
    issues: [],
    selections: [
      { group_id: 301, group_name: 'Bebida', choice_option_id: 401, selected_product_id: 501, selected_product_name: 'Café' },
      { group_id: 302, group_name: 'Guarnición', choice_option_id: 403, selected_product_id: 503, selected_product_name: 'Frijoles' },
    ],
    missing_choice_groups: [],
    fixed_components: [],
    ...overrides,
  };
}

function draft(version = 7, items: unknown[] = [draftItem()], readiness = items.length ? 'READY' : 'EMPTY') {
  return {
    draft_id: 601,
    tenant_id: 1,
    organization_id: 2,
    location_id: 3,
    conversation_id: 33,
    version,
    readiness,
    items,
  };
}

const productDetail = {
  product: {
    id: 101,
    name: 'Desayuno campirano',
    description: null,
    category_path: [],
    price: { amount: '125.0000', currency: 'MXN' },
    orderable: true,
    configuration_available: true,
    configuration_required: true,
  },
  fixed_components: [],
  choice_groups: [
    {
      id: 301,
      name: 'Bebida',
      min_selections: 1,
      max_selections: 1,
      required: true,
      options: [
        { id: 401, product_id: 501, name: 'Café', description: null, quantity: '1.0000' },
        { id: 402, product_id: 502, name: 'Jugo', description: null, quantity: '1.0000' },
      ],
    },
    {
      id: 302,
      name: 'Guarnición',
      min_selections: 1,
      max_selections: 1,
      required: true,
      options: [{ id: 403, product_id: 503, name: 'Frijoles', description: null, quantity: '1.0000' }],
    },
  ],
  experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['ADD_ITEM'], next_action: null },
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11,
    serviceSessionId: 22,
    conversationId: 33,
    displayName: 'Ana',
    customerId: null,
    accessToken: 'draft-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/order']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function mockFetch(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(response(session));
    return handler(url, init);
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

describe('draft review', () => {
  it('reconstructs simple and configured lines from the authenticated draft read', async () => {
    const simple = draftItem({
      item_id: 702,
      product_id: 102,
      product_name: 'Café americano',
      composition_id: null,
      quantity: '1.0000',
      position: 1,
      selections: [],
    });
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft(7, [draftItem({
        fixed_components: [{ product_id: 601, product_name: 'Fruta de temporada', quantity: '1.0000' }],
      }), simple])));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Mi pedido' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Desayuno campirano' })).toBeInTheDocument();
    expect(screen.getByText('Café')).toBeInTheDocument();
    expect(screen.getByText('Frijoles')).toBeInTheDocument();
    expect(screen.getByText('Fruta de temporada · Cantidad 1')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Café americano' })).toBeInTheDocument();
    expect(screen.getByDisplayValue('2.0000')).toBeInTheDocument();
    expect(screen.queryByText('$125.00')).not.toBeInTheDocument();
    const readCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/diner/order-draft'));
    expect(new Headers(readCall?.[1]?.headers).get('Authorization')).toBe('Bearer draft-token');
  });

  it('identifies authoritative missing configuration groups by name', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft(7, [draftItem({
        readiness: 'INCOMPLETE',
        selections: [],
        missing_choice_groups: [{
          group_id: 301,
          group_name: 'Bebida',
          min_selections: 1,
          max_selections: 1,
          selected_option_ids: [],
        }],
      })], 'INCOMPLETE')));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByText('Bebida')).toBeInTheDocument();
    expect(screen.getAllByText('Configuración pendiente')).toHaveLength(2);
  });

  it('presents a missing or empty authoritative draft as an empty state', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response({ error: { code: 'http_error', message: 'Order Draft not found' } }, 404));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Tu pedido está vacío' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver el menú' })).toHaveAttribute('href', '/menu');
  });

  it('presents an existing authoritative draft with no lines as empty', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft(1, [])));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Tu pedido está vacío' })).toBeInTheDocument();
  });

  it('sends an exact versioned quantity mutation and waits for backend confirmation', async () => {
    let finishUpdate: ((value: Response) => void) | undefined;
    const pendingUpdate = new Promise<Response>((resolve) => { finishUpdate = resolve; });
    const fetchMock = mockFetch((url, init) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      if (url.endsWith('/diner/order-draft/items/701/quantity')) return pendingUpdate;
      return Promise.reject(new Error(`Unexpected request: ${url} ${init?.method}`));
    });
    renderPage();

    const quantity = await screen.findByLabelText('Cantidad', { selector: 'input' });
    await userEvent.clear(quantity);
    await userEvent.type(quantity, '3.5');
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeDisabled();

    const updateCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/quantity'));
    expect(updateCall?.[1]?.method).toBe('PUT');
    expect(JSON.parse(String(updateCall?.[1]?.body))).toEqual({ quantity: '3.5', expected_version: 7 });
    finishUpdate?.(response(draft(8, [draftItem({ quantity: '3.5000' })])));
    expect(await screen.findByText('Cantidad actualizada.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('3.5000')).toBeInTheDocument();
  });

  it('requires explicit confirmation and removes only after the authoritative response', async () => {
    let finishRemove: ((value: Response) => void) | undefined;
    const pendingRemove = new Promise<Response>((resolve) => { finishRemove = resolve; });
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      if (url.endsWith('/diner/order-draft/items/701?expected_version=7')) return pendingRemove;
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Quitar' }));
    expect(screen.getByText('¿Quitar este producto?')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Sí, quitar' }));
    expect(screen.getByRole('heading', { name: 'Desayuno campirano' })).toBeInTheDocument();
    const removeCall = fetchMock.mock.calls.find(([input]) => String(input).includes('?expected_version='));
    expect(removeCall?.[1]?.method).toBe('DELETE');
    finishRemove?.(response(draft(8, [])));
    expect(await screen.findByRole('heading', { name: 'Tu pedido está vacío' })).toBeInTheDocument();
  });

  it('re-reads and presents newer authoritative state after a version conflict', async () => {
    let draftReads = 0;
    mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) {
        draftReads += 1;
        return Promise.resolve(response(draftReads === 1 ? draft() : draft(8, [draftItem({ quantity: '4.0000' })])));
      }
      if (url.endsWith('/diner/order-draft/items/701/quantity')) {
        return Promise.resolve(response({ error: { code: 'http_error', message: 'Draft version conflict' } }, 409));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    const quantity = await screen.findByLabelText('Cantidad', { selector: 'input' });
    await userEvent.clear(quantity);
    await userEvent.type(quantity, '3');
    await userEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    expect(await screen.findByText(/cambió en otro lugar/)).toBeInTheDocument();
    expect(screen.getByDisplayValue('4.0000')).toBeInTheDocument();
    expect(draftReads).toBe(2);
  });

  it('reconciles an ambiguous remove outcome through an authoritative read', async () => {
    let draftReads = 0;
    mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) {
        draftReads += 1;
        return Promise.resolve(response(draftReads === 1 ? draft() : draft(8, [])));
      }
      if (url.includes('/diner/order-draft/items/701?')) return Promise.reject(new TypeError('connection lost'));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Quitar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Sí, quitar' }));
    expect(await screen.findByText('Confirmamos el cambio al volver a consultar tu pedido.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Tu pedido está vacío' })).toBeInTheDocument();
  });

  it('reuses the product configuration interaction and versions each authoritative group replacement', async () => {
    const calls: Array<{ url: string; body: unknown }> = [];
    mockFetch((url, init) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      if (url.endsWith('/diner/products/101')) return Promise.resolve(response(productDetail));
      if (url.includes('/choice-groups/301')) {
        calls.push({ url, body: JSON.parse(String(init?.body)) });
        return Promise.resolve(response(draft(8, [draftItem({
          selections: [
            { group_id: 301, group_name: 'Bebida', choice_option_id: 402, selected_product_id: 502, selected_product_name: 'Jugo' },
            { group_id: 302, group_name: 'Guarnición', choice_option_id: 403, selected_product_id: 503, selected_product_name: 'Frijoles' },
          ],
        })])));
      }
      if (url.includes('/choice-groups/302')) {
        calls.push({ url, body: JSON.parse(String(init?.body)) });
        return Promise.resolve(response(draft(9, [draftItem({
          selections: [
            { group_id: 301, group_name: 'Bebida', choice_option_id: 402, selected_product_id: 502, selected_product_name: 'Jugo' },
            { group_id: 302, group_name: 'Guarnición', choice_option_id: 403, selected_product_id: 503, selected_product_name: 'Frijoles' },
          ],
        })])));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Editar configuración' }));
    expect(await screen.findByRole('radio', { name: /Café/ })).toBeChecked();
    await userEvent.click(screen.getByRole('radio', { name: /Jugo/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Guardar configuración' }));
    expect(await screen.findByText('Configuración actualizada.')).toBeInTheDocument();
    expect(calls).toEqual([
      { url: '/api/diner/order-draft/items/701/choice-groups/301', body: { option_ids: [402], expected_version: 7 } },
      { url: '/api/diner/order-draft/items/701/choice-groups/302', body: { option_ids: [403], expected_version: 8 } },
    ]);
    expect(screen.getByText('Jugo')).toBeInTheDocument();
  });

  it('does not treat an option removed from the current catalog as a valid initial selection', async () => {
    mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft(7, [draftItem({
        selections: [
          { group_id: 301, group_name: 'Bebida', choice_option_id: 499, selected_product_id: 599, selected_product_name: 'Opción retirada' },
          { group_id: 302, group_name: 'Guarnición', choice_option_id: 403, selected_product_id: 503, selected_product_name: 'Frijoles' },
        ],
      })])));
      if (url.endsWith('/diner/products/101')) return Promise.resolve(response(productDetail));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Editar configuración' }));
    expect(await screen.findByRole('radio', { name: /Café/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /Jugo/ })).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Guardar configuración' })).toBeDisabled();
  });

  it('shows a structured loading state and a controlled read failure', async () => {
    const never = new Promise<Response>(() => undefined);
    mockFetch((url) => url.endsWith('/diner/order-draft') ? never : Promise.reject(new Error(`Unexpected request: ${url}`)));
    const view = renderPage();
    expect(await screen.findByText('Cargando tu pedido…')).toBeInTheDocument();
    view.unmount();

    cleanup();
    mockFetch((url) => url.endsWith('/diner/order-draft')
      ? Promise.resolve(response({ error: { code: 'internal_error', message: 'Unavailable' } }, 500))
      : Promise.reject(new Error(`Unexpected request: ${url}`)));
    renderPage();
    expect(await screen.findByRole('heading', { name: 'No pudimos cargar tu pedido' })).toBeInTheDocument();
  });
});
