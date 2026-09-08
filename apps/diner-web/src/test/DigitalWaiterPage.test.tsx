import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11,
    serviceSessionId: 22,
    conversationId: 33,
    displayName: 'Ana',
    customerId: null,
    accessToken: 'waiter-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function conversationResponse(overrides: Record<string, unknown> = {}) {
  return {
    source_message: { id: 101, sequence_number: 1, modality: 'TEXT', content_text: 'Quiero ver el menú' },
    response_message: { id: 102, sequence_number: 2, modality: 'TEXT', content_text: '{}' },
    intent_code: 'MENU_QUERY',
    experience: {
      state: 'OK',
      code: 'OK',
      required_input: [],
      allowed_actions: ['SHOW_PRODUCT'],
      next_action: null,
    },
    authoritative_data: null,
    replayed: false,
    message: 'Listo. El restaurante confirmó la información mostrada.',
    ui_action: null,
    pending_context: {},
    ...overrides,
  };
}

function renderWaiter() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/waiter']}>
          <AuthProvider><AppRoutes /></AuthProvider>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

async function submitMessage(text: string) {
  fireEvent.change(screen.getByLabelText('Escribe lo que necesitas'), { target: { value: text } });
  fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));
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

describe('Digital Waiter UI', () => {
  it('submits natural language through C6A and renders an authoritative menu result', async () => {
    const response = conversationResponse({
      authoritative_data: [{
        id: 7,
        name: 'Carta',
        sections: [{
          id: 8,
          name: 'Bebidas',
          products: [{
            id: 91,
            name: 'Agua mineral',
            description: 'Botella individual',
            price: { amount: '42.00', currency: 'MXN' },
            orderable: true,
            configuration_available: false,
            configuration_required: false,
            category_path: [],
          }],
        }],
      }],
    });
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) return Promise.resolve(json(response));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    expect(await screen.findByRole('heading', { name: 'Mesero digital' })).toBeInTheDocument();
    await submitMessage('Quiero ver el menú');

    expect(await screen.findByText('Agua mineral')).toBeInTheDocument();
    expect(screen.getByText('Tú')).toBeInTheDocument();
    expect(screen.getByText('Listo. El restaurante confirmó la información mostrada.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver Agua mineral' })).toHaveAttribute('href', '/products/91');
    const call = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/diner/conversation/actions'));
    const request = call?.[1];
    expect(request).toBeDefined();
    expect(JSON.parse(String(request?.body))).toEqual({ modality: 'TEXT', content_text: 'Quiero ver el menú' });
    expect(new Headers(request?.headers).get('Authorization')).toBe('Bearer waiter-token');
    expect(new Headers(request?.headers).get('Idempotency-Key')).toMatch(/^diner-conversation-/);
  });

  it('renders backend clarification candidates and returns the selected product reference', async () => {
    let actions = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) {
        actions += 1;
        if (actions === 1) {
          return Promise.resolve(json(conversationResponse({
            intent_code: 'PRODUCT_QUERY',
            experience: {
              state: 'CLARIFICATION_REQUIRED', code: 'AMBIGUOUS_REFERENCE',
              required_input: ['SELECTION'], allowed_actions: ['SELECT_CANDIDATE'],
              next_action: 'SELECT_CANDIDATE',
            },
            authoritative_data: { candidates: [
              { product_id: 91, display_name: 'Coca-Cola', matched_by: 'CANONICAL_NAME' },
              { product_id: 92, display_name: 'Coca-Cola Zero', matched_by: 'CANONICAL_NAME' },
            ] },
            message: 'Necesito una precisión antes de continuar.',
            ui_action: 'SELECT_CANDIDATE',
          })));
        }
        return Promise.resolve(json(conversationResponse({
          intent_code: 'PRODUCT_QUERY',
          authoritative_data: { product: { id: 92, name: 'Coca-Cola Zero' } },
        })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    fireEvent.click(screen.getByRole('button', { name: 'Quiero ver el menú' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Coca-Cola Zero' }));
    await waitFor(() => expect(actions).toBe(2));
    const actionCalls = fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/conversation/actions'));
    expect(JSON.parse(String(actionCalls[1][1]?.body))).toEqual({
      modality: 'TEXT',
      content_text: 'Coca-Cola Zero',
      intent_code: 'PRODUCT_QUERY',
      product_id: 92,
    });
  });

  it('maps secure card entry and payment uncertainty only to existing deterministic routes', async () => {
    let actions = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) {
        actions += 1;
        if (actions === 1) {
          return Promise.resolve(json(conversationResponse({
            intent_code: 'PAYMENT_REQUEST',
            authoritative_data: { check_id: 77, check_status: 'OPEN' },
            experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['OPEN_SECURE_PAYMENT_SOURCE'], next_action: 'OPEN_SECURE_PAYMENT_SOURCE' },
            message: 'Completa los datos de pago en el formulario seguro.',
            ui_action: 'OPEN_SECURE_PAYMENT_SOURCE',
            pending_context: { check_id: 77 },
          })));
        }
        return Promise.resolve(json(conversationResponse({
          response_message: { id: 104, sequence_number: 4, modality: 'TEXT', content_text: '{}' },
          intent_code: 'PAYMENT_STATUS_QUERY',
          experience: { state: 'PAYMENT_UNCERTAIN', code: 'PAYMENT_UNCERTAIN', required_input: [], allowed_actions: ['VIEW_PAYMENT_STATUS'], next_action: 'WAIT_FOR_PAYMENT_RESOLUTION' },
          authoritative_data: { check_id: 77, uncertain_exposure: '100.00' },
          message: 'Estamos confirmando el resultado de tu pago. No realices otro pago por ahora.',
          ui_action: 'WAIT_FOR_PAYMENT_RESOLUTION',
          pending_context: { check_id: 77, payment_id: 501 },
        })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    await submitMessage('Voy a pagar con tarjeta');
    expect(await screen.findByRole('link', { name: 'Completar pago seguro' })).toHaveAttribute('href', '/check/77');
    expect(screen.queryByLabelText(/número de tarjeta|cvv|cvc|vencimiento/i)).not.toBeInTheDocument();

    await submitMessage('¿Qué pasó con mi pago?');
    expect(await screen.findByRole('alert')).toHaveTextContent('No realices otro pago por ahora');
    expect(screen.getByRole('link', { name: 'Consultar pago' })).toHaveAttribute('href', '/check/77/payments/501');
    expect(screen.queryByText(/pagar otra vez/i)).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input, init]) => String(input).endsWith('/payments') && init?.method === 'POST')).toBe(false);
    expect(sessionStorage.getItem('diner-auth-session-v1')).not.toMatch(/payment_source|merchant_credential|tok_/i);
  });

  it('renders continuation decisions and delegates the selected answer to C6A', async () => {
    let actions = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) {
        actions += 1;
        if (actions === 1) {
          return Promise.resolve(json(conversationResponse({
            intent_code: 'SERVICE_CONTINUATION',
            experience: { state: 'CONTINUATION_REQUIRED', code: 'SERVICE_CONTINUATION_DECISION_REQUIRED', required_input: ['YES_OR_NO'], allowed_actions: ['SERVICE_CONTINUATION'], next_action: 'SERVICE_CONTINUATION' },
            authoritative_data: { id: 77, version: 4, continuation_decision: 'PENDING' },
            message: 'Tu cuenta está liquidada. ¿Desean algo más?',
            ui_action: 'SERVICE_CONTINUATION',
            pending_context: { check_id: 77, check_version: 4 },
          })));
        }
        return Promise.resolve(json(conversationResponse({
          intent_code: 'SERVICE_CONTINUATION',
          authoritative_data: { id: 77, version: 5, continuation_decision: 'YES' },
        })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    await submitMessage('¿Ya terminamos?');
    fireEvent.click(await screen.findByRole('button', { name: 'Sí, continuar' }));
    await waitFor(() => expect(actions).toBe(2));
    const actionCalls = fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/conversation/actions'));
    expect(JSON.parse(String(actionCalls[1][1]?.body))).toEqual({
      modality: 'TEXT',
      content_text: 'Sí, queremos algo más',
      intent_code: 'SERVICE_CONTINUATION',
      check_id: 77,
      continuation_decision: 'YES',
      expected_check_version: 4,
    });
  });

  it('maps only authoritative product, configuration, draft, account and check actions', async () => {
    const responses = [
      conversationResponse({
        response_message: { id: 201, sequence_number: 2, modality: 'TEXT', content_text: '{}' },
        intent_code: 'PRODUCT_QUERY',
        authoritative_data: { product: { id: 91, name: 'Desayuno', configuration_required: true } },
        experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['ADD_ITEM', 'SHOW_MENU'], next_action: 'CONFIGURE_ITEM' },
        ui_action: 'CONFIGURE_ITEM',
      }),
      conversationResponse({
        response_message: { id: 202, sequence_number: 4, modality: 'TEXT', content_text: '{}' },
        intent_code: 'ORDER_EXPRESSION',
        authoritative_data: { readiness: 'INCOMPLETE', items: [] },
        experience: { state: 'CONFIGURATION_REQUIRED', code: 'CONFIGURATION_REQUIRED', required_input: ['CHOICE_SELECTIONS'], allowed_actions: ['CONFIGURE_ITEM', 'REVIEW_DRAFT'], next_action: 'CONFIGURE_ITEM' },
        ui_action: 'CONFIGURE_ITEM',
      }),
      conversationResponse({
        response_message: { id: 203, sequence_number: 6, modality: 'TEXT', content_text: '{}' },
        intent_code: 'ORDER_EXPRESSION',
        authoritative_data: { readiness: 'READY', items: [] },
        experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['REVIEW_DRAFT', 'CONFIRM_ORDER'], next_action: 'REVIEW_DRAFT' },
        ui_action: 'REVIEW_DRAFT',
      }),
      conversationResponse({
        response_message: { id: 204, sequence_number: 8, modality: 'TEXT', content_text: '{}' },
        intent_code: 'ORDER_CONFIRMATION',
        authoritative_data: { id: 501, status: 'ACCEPTED', items: [] },
        experience: { state: 'OK', code: 'OK', required_input: [], allowed_actions: ['VIEW_ORDER', 'VIEW_ACCOUNT'], next_action: 'VIEW_ORDER' },
        ui_action: 'VIEW_ORDER',
      }),
      conversationResponse({
        response_message: { id: 205, sequence_number: 10, modality: 'TEXT', content_text: '{}' },
        intent_code: 'CHECK_QUERY',
        experience: { state: 'ACTION_BLOCKED', code: 'ORDERING_BLOCKED', required_input: [], allowed_actions: ['VIEW_CHECK'], next_action: 'VIEW_CHECK' },
        authoritative_data: { id: 77, status: 'FROZEN' },
        ui_action: 'VIEW_CHECK',
        pending_context: { check_id: 77 },
        message: 'El estado actual no permite completar esa acción.',
      }),
    ];
    let actionIndex = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) return Promise.resolve(json(responses[actionIndex++]));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    await submitMessage('Muéstrame el producto');
    expect(await screen.findByRole('link', { name: 'Completar configuración' })).toHaveAttribute('href', '/products/91');
    await submitMessage('Configurar');
    await waitFor(() => expect(screen.getAllByRole('link', { name: 'Completar configuración' })).toHaveLength(2));
    expect(screen.getAllByRole('link', { name: 'Completar configuración' }).at(-1)).toHaveAttribute('href', '/order');
    await submitMessage('Ver borrador');
    expect(await screen.findByRole('link', { name: 'Ver mi pedido' })).toHaveAttribute('href', '/order');
    await submitMessage('Ver cuenta');
    expect(await screen.findByRole('link', { name: 'Ver mi cuenta' })).toHaveAttribute('href', '/account');
    await submitMessage('Ver check');
    expect((await screen.findAllByRole('alert')).at(-1)).toHaveTextContent('no permite completar');
    expect(await screen.findByRole('link', { name: 'Ver cuenta' })).toHaveAttribute('href', '/check/77');
  });

  it('renders unavailable and staff-assistance results without inventing domain outcomes', async () => {
    let actions = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) {
        actions += 1;
        if (actions === 1) return Promise.resolve(json(conversationResponse({
          response_message: { id: 301, sequence_number: 2, modality: 'TEXT', content_text: '{}' },
          experience: { state: 'PRODUCT_UNAVAILABLE', code: 'PRODUCT_UNAVAILABLE', required_input: [], allowed_actions: ['BROWSE_MENU'], next_action: 'BROWSE_MENU' },
          message: 'No encontré ese producto disponible en el menú actual.',
          ui_action: 'BROWSE_MENU',
        })));
        return Promise.resolve(json(conversationResponse({
          response_message: { id: 302, sequence_number: 4, modality: 'TEXT', content_text: '{}' },
          intent_code: 'HUMAN_ASSISTANCE_REQUEST',
          experience: { state: 'STAFF_ASSISTANCE_REQUIRED', code: 'STAFF_ASSISTANCE_REQUIRED', required_input: [], allowed_actions: ['VIEW_OPERATIONAL_REQUEST'], next_action: 'WAIT_FOR_STAFF' },
          authoritative_data: { request_type: 'HUMAN_ASSISTANCE', status: 'PENDING' },
          message: 'Tu solicitud fue registrada para el equipo del restaurante.',
          ui_action: 'WAIT_FOR_STAFF',
        })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    await submitMessage('Quiero un producto agotado');
    expect(await screen.findByRole('link', { name: 'Explorar menú' })).toHaveAttribute('href', '/menu');
    await submitMessage('Necesito ayuda');
    expect(await screen.findByText('Solicitud registrada')).toBeInTheDocument();
    expect(screen.getByText('Estado: PENDING')).toBeInTheDocument();
    expect(screen.getByText('Tu solicitud fue registrada para el equipo del restaurante.')).toBeInTheDocument();
  });

  it('blocks duplicate submission and retries a failed request with the same idempotency key', async () => {
    let actionCalls = 0;
    let releaseFirst: (response: Response) => void = () => undefined;
    const pending = new Promise<Response>((resolve) => { releaseFirst = resolve; });
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) {
        actionCalls += 1;
        if (actionCalls === 1) return pending;
        if (actionCalls === 2) return Promise.reject(new Error('connection lost'));
        return Promise.resolve(json(conversationResponse({ response_message: { id: 402, sequence_number: 4, modality: 'TEXT', content_text: '{}' } })));
      }
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    fireEvent.change(screen.getByLabelText('Escribe lo que necesitas'), { target: { value: 'Una sola vez' } });
    const form = screen.getByRole('button', { name: 'Enviar' }).closest('form');
    expect(form).not.toBeNull();
    fireEvent.submit(form!);
    fireEvent.submit(form!);
    expect(screen.getByRole('button', { name: 'Enviando…' })).toBeDisabled();
    expect(actionCalls).toBe(1);
    releaseFirst(json(conversationResponse({ response_message: { id: 401, sequence_number: 2, modality: 'TEXT', content_text: '{}' } })));
    await screen.findByText('Listo. El restaurante confirmó la información mostrada.');

    await submitMessage('Prueba de reintento');
    const retry = await screen.findByRole('button', { name: 'Reintentar' });
    const failedCall = fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/conversation/actions'))[1];
    const failedKey = new Headers(failedCall[1]?.headers).get('Idempotency-Key');
    fireEvent.click(retry);
    await waitFor(() => expect(actionCalls).toBe(3));
    const retriedCall = fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/diner/conversation/actions'))[2];
    expect(new Headers(retriedCall[1]?.headers).get('Idempotency-Key')).toBe(failedKey);
    expect(screen.getAllByText('Prueba de reintento')).toHaveLength(1);
  });

  it('keeps existing deterministic navigation available beside the assistant', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    const navigation = screen.getByRole('navigation', { name: 'Navegación principal' });
    expect(navigation).toHaveTextContent('Menú');
    expect(navigation).toHaveTextContent('Mi pedido');
    expect(navigation).toHaveTextContent('Mi cuenta');
    expect(screen.getByRole('link', { name: 'Asistente' })).toHaveAttribute('href', '/waiter');
  });

  it('restores a usable empty assistant without browser transcript persistence', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    expect(await screen.findByText(/Puedo ayudarte con el menú/)).toBeInTheDocument();
    expect(screen.getByLabelText('Escribe lo que necesitas')).toBeEnabled();
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index)))
      .not.toEqual(expect.arrayContaining([expect.stringMatching(/waiter|conversation|transcript/i)]));
    expect([...Array(sessionStorage.length)].map((_, index) => sessionStorage.key(index))).toEqual(['diner-auth-session-v1']);
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/conversation/messages'))).toBe(false);
  });

  it('turns an authoritative SESSION_CLOSED response into the existing terminal experience', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/diner-session')) return Promise.resolve(json(currentSession));
      if (url.endsWith('/diner/conversation/actions')) return Promise.resolve(json(conversationResponse({
        experience: { state: 'SESSION_CLOSED', code: 'SESSION_CLOSED', required_input: [], allowed_actions: [], next_action: 'LEAVE_SESSION' },
        message: 'Esta sesión ya terminó.',
        ui_action: 'LEAVE_SESSION',
      })));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    renderWaiter();

    await screen.findByRole('heading', { name: 'Mesero digital' });
    fireEvent.click(screen.getByRole('button', { name: 'Necesito ayuda' }));
    expect(await screen.findByRole('heading', { name: 'Esta sesión ha terminado' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Escribe lo que necesitas')).not.toBeInTheDocument();
    expect(sessionStorage.getItem('diner-auth-session-v1')).toBeNull();
  });
});
