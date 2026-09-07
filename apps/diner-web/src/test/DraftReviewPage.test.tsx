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

function checkoutPreview(version = 7, overrides: Record<string, unknown> = {}) {
  return {
    status: 'READY',
    draft_id: 601,
    draft_version: version,
    tenant_id: 1,
    organization_id: 2,
    location_id: 3,
    resolved_at: '2026-09-06T20:00:00Z',
    currency: 'MXN',
    tax_mode: 'TAX_INCLUDED',
    rounding_policy: 'HALF_UP',
    fingerprint_schema_version: 1,
    lines: [],
    subtotal: '250.0000',
    total_discount: '25.0000',
    pre_round_total: '225.0000',
    rounding_adjustment: '0.0000',
    payable_total: '225.0000',
    commercial_fingerprint: 'a'.repeat(64),
    ...overrides,
  };
}

function acceptedOrder(overrides: Record<string, unknown> = {}) {
  return {
    id: 901,
    status: 'ACCEPTED',
    accepted_at: '2026-09-06T20:01:00Z',
    source_order_draft_id: 601,
    accepted_draft_version: 7,
    currency: 'MXN',
    tax_mode: 'TAX_INCLUDED',
    rounding_policy: 'HALF_UP',
    subtotal: '250.0000',
    total_discount: '25.0000',
    pre_round_total: '225.0000',
    rounding_adjustment: '0.0000',
    payable_total: '225.0000',
    items: [{
      id: 902,
      source_order_draft_item_id: 701,
      product_id: 101,
      product_name: 'Desayuno campirano',
      composition_id: 801,
      quantity: '2.0000',
      position: 0,
      source_product_price_id: 77,
      price_source: 'PLATFORM',
      unit_price: '125.0000',
      base_amount: '250.0000',
      discount_amount: '25.0000',
      commercial_amount: '225.0000',
      components: [],
      promotions: [],
    }],
    ...overrides,
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

function mockFetch(
  handler: (url: string, init?: RequestInit) => Promise<Response>,
  previewHandler: () => Promise<Response> = () => Promise.resolve(response(checkoutPreview())),
) {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/diner-session')) return Promise.resolve(response(session));
    if (url.endsWith('/diner/checkout-preview')) return previewHandler();
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

  it('confirms the exact authoritative preview once and presents the accepted order', async () => {
    let finishConfirmation: ((value: Response) => void) | undefined;
    const pendingConfirmation = new Promise<Response>((resolve) => { finishConfirmation = resolve; });
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      if (url.endsWith('/diner/order/confirm')) return pendingConfirmation;
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByText('$225.00')).toBeInTheDocument();
    const confirm = screen.getByRole('button', { name: 'Confirmar pedido' });
    await userEvent.dblClick(confirm);
    expect(screen.getByRole('button', { name: 'Confirmando con el restaurante…' })).toBeDisabled();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/order/confirm'))).toHaveLength(1);

    const confirmCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/diner/order/confirm'));
    expect(confirmCall?.[1]?.method).toBe('POST');
    expect(JSON.parse(String(confirmCall?.[1]?.body))).toEqual({
      expected_draft_version: 7,
      expected_commercial_fingerprint: 'a'.repeat(64),
    });
    expect(new Headers(confirmCall?.[1]?.headers).get('Idempotency-Key')).toMatch(/^diner-confirm-/);

    finishConfirmation?.(response(acceptedOrder(), 201));
    expect(await screen.findByRole('heading', { name: 'Tu pedido fue confirmado' })).toBeInTheDocument();
    expect(screen.getByText('2 × Desayuno campirano')).toBeInTheDocument();
    expect(screen.getByText('Total aceptado')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Actualizar' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Volver al menú' })).toHaveAttribute('href', '/menu');
  });

  it('does not expose confirmation for an empty or incomplete authoritative draft', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft(7, [], 'EMPTY')));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Tu pedido está vacío' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirmar pedido' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/diner/checkout-preview'))).toBe(false);
  });

  it('keeps an incomplete authoritative draft editable without exposing confirmation', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft(7, [draftItem({ readiness: 'INCOMPLETE' })], 'INCOMPLETE')));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    expect(await screen.findByText('Tu pedido necesita una revisión')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Editar configuración' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Confirmar pedido' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/diner/checkout-preview'))).toBe(false);
  });

  it('refreshes draft and commercial preview after conflict and requires another click', async () => {
    let draftReads = 0;
    let previewReads = 0;
    let confirmations = 0;
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) {
        draftReads += 1;
        return Promise.resolve(response(draftReads === 1 ? draft() : draft(8, [draftItem({ quantity: '3.0000' })])));
      }
      if (url.endsWith('/diner/order/confirm')) {
        confirmations += 1;
        return Promise.resolve(response({ error: { code: 'http_error', message: 'Commercial confirmation expectation is stale' } }, 409));
      }
      if (url.endsWith('/diner/orders')) return Promise.resolve(response([]));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }, () => {
      previewReads += 1;
      return Promise.resolve(response(checkoutPreview(previewReads === 1 ? 7 : 8, {
        subtotal: previewReads === 1 ? '250.0000' : '375.0000',
        payable_total: previewReads === 1 ? '225.0000' : '350.0000',
        commercial_fingerprint: (previewReads === 1 ? 'a' : 'b').repeat(64),
      })));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar pedido' }));
    expect(await screen.findByText(/cambiaron/)).toBeInTheDocument();
    expect(screen.getByDisplayValue('3.0000')).toBeInTheDocument();
    expect(await screen.findByText('$350.00')).toBeInTheDocument();
    expect(confirmations).toBe(1);
    expect(screen.getByRole('button', { name: 'Confirmar pedido' })).toBeEnabled();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/order/confirm'))).toHaveLength(1);
  });

  it('reconciles an ambiguous confirmation to the accepted order without retrying it', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      if (url.endsWith('/diner/order/confirm')) return Promise.reject(new TypeError('connection lost'));
      if (url.endsWith('/diner/orders')) return Promise.resolve(response([acceptedOrder()]));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar pedido' }));
    expect(await screen.findByRole('heading', { name: 'Tu pedido fue confirmado' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/order/confirm'))).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/diner/orders'))).toBe(true);
  });

  it('preserves one idempotency identity when an ambiguous attempt leaves the draft confirmable', async () => {
    let draftReads = 0;
    let confirmations = 0;
    const keys: Array<string | null> = [];
    mockFetch((url, init) => {
      if (url.endsWith('/diner/order-draft')) {
        draftReads += 1;
        return Promise.resolve(response(draft()));
      }
      if (url.endsWith('/diner/order/confirm')) {
        confirmations += 1;
        keys.push(new Headers(init?.headers).get('Idempotency-Key'));
        return confirmations === 1
          ? Promise.reject(new TypeError('connection lost'))
          : Promise.resolve(response(acceptedOrder(), 201));
      }
      if (url.endsWith('/diner/orders')) return Promise.resolve(response([]));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar pedido' }));
    expect(await screen.findByText(/borrador sigue disponible/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar pedido' }));
    expect(await screen.findByRole('heading', { name: 'Tu pedido fue confirmado' })).toBeInTheDocument();
    expect(keys).toHaveLength(2);
    expect(keys[1]).toBe(keys[0]);
    expect(draftReads).toBe(2);
  });

  it('shows a controlled commercial-preview failure without sending confirmation', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }, () => Promise.resolve(response({ error: { code: 'http_error', message: 'Commercial resolution failed' } }, 409)));
    renderPage();

    expect(await screen.findByRole('heading', { name: 'Revisa tu pedido nuevamente' })).toBeInTheDocument();
    expect(screen.getByText(/El pedido no fue confirmado\./)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/diner/order/confirm'))).toBe(false);
  });

  it('preserves the existing controlled session-closed experience during confirmation', async () => {
    const fetchMock = mockFetch((url) => {
      if (url.endsWith('/diner/order-draft')) return Promise.resolve(response(draft()));
      if (url.endsWith('/diner/order/confirm')) return Promise.resolve(response({
        error: { code: 'session_closed', state: 'SESSION_CLOSED', message: 'Session closed' },
      }, 409));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    renderPage();

    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar pedido' }));
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith('/diner/orders'))).toBe(false);
  });
});
