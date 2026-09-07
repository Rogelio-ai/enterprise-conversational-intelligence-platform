import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConektaCardTokenizer, type EphemeralCustomerPaymentSource } from '../components/ConektaCardTokenizer';
import { CONEKTA_SCRIPT_URL, loadConektaScript, type ConektaCardParameters } from '../payments/conekta';

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function seedSession() {
  sessionStorage.setItem('diner-auth-session-v1', JSON.stringify({
    dinerSessionId: 11,
    serviceSessionId: 22,
    conversationId: 33,
    displayName: 'Ana',
    customerId: null,
    accessToken: 'tokenizer-test-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
  }));
}

function renderTokenizer(onSourceReady = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <ConektaCardTokenizer executorKey="conekta-card" currency="MXN" onSourceReady={onSourceReady} />
    </QueryClientProvider>,
  );
  return { ...view, onSourceReady };
}

function installProvider(card: (parameters: ConektaCardParameters) => unknown) {
  window.ConektaCheckoutComponents = { Card: card };
  const script = document.querySelector<HTMLScriptElement>(`script[src="${CONEKTA_SCRIPT_URL}"]`);
  if (script) fireEvent.load(script);
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  seedSession();
  window.history.replaceState(null, '', '/check/77');
});

afterEach(() => {
  cleanup();
  delete window.ConektaCheckoutComponents;
  document.querySelectorAll(`script[src="${CONEKTA_SCRIPT_URL}"]`).forEach((script) => script.remove());
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Conekta card tokenizer', () => {
  it('loads authoritative config and returns only the opaque ephemeral source after external submit', async () => {
    const fetchMock = vi.fn((_input: string | URL | Request, _init?: RequestInit) => Promise.resolve(json({
      provider: 'CONEKTA', tokenization_mode: 'WEB_TOKENIZER',
      public_key: 'key_test_public', locale: 'es',
    })));
    const storageSet = vi.spyOn(Storage.prototype, 'setItem');
    const consoleLog = vi.spyOn(console, 'log');
    vi.stubGlobal('fetch', fetchMock);
    let parameters: ConektaCardParameters | undefined;
    const card = vi.fn((value: ConektaCardParameters) => { parameters = value; });
    const sourceReady = vi.fn<(source: EphemeralCustomerPaymentSource) => void>();
    renderTokenizer(sourceReady);

    expect(await screen.findByRole('button', { name: 'Continuar con tarjeta' })).toBeDisabled();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
        '/api/diner/payment-executors/conekta-card/client-configuration?currency=MXN',
        expect.objectContaining({ headers: expect.any(Headers) }),
      ));
    await waitFor(() => expect(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`)).not.toBeNull());
    installProvider(card);
    await waitFor(() => expect(card).toHaveBeenCalledOnce());

    expect(parameters?.config).toEqual({
      targetIFrame: expect.stringMatching(/^#conekta-card-tokenizer-/),
      publicKey: 'key_test_public', locale: 'es', useExternalSubmit: true,
    });
    expect(document.querySelector(parameters?.config.targetIFrame ?? '')).not.toBeNull();
    const submit = vi.fn();
    parameters?.callbacks.onGetInfoSuccess({ initLoadTime: 1 });
    expect(screen.getByRole('button', { name: 'Continuar con tarjeta' })).toBeDisabled();
    parameters?.callbacks.onUpdateSubmitTrigger(submit);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Continuar con tarjeta' })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Continuar con tarjeta' }));
    expect(submit).toHaveBeenCalledOnce();
    expect(screen.getByText('Generando información segura de pago…')).toBeInTheDocument();

    parameters?.callbacks.onCreateTokenSucceeded({ id: 'tok_test_opaque' });
    await waitFor(() => expect(sourceReady).toHaveBeenCalledWith({ provider: 'CONEKTA', source: 'tok_test_opaque' }));
    expect(screen.getByText('Información de tarjeta preparada')).toBeInTheDocument();
    expect(storageSet.mock.calls.some(([, value]) => String(value).includes('tok_test_opaque'))).toBe(false);
    expect(window.location.href).not.toContain('tok_test_opaque');
    expect(consoleLog.mock.calls.flat().some((value) => String(value).includes('tok_test_opaque'))).toBe(false);
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('/payments') && init?.method === 'POST')).toBe(false);
  });

  it('rejects unsupported client configuration without loading a provider script', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json({
      provider: 'OTHER', tokenization_mode: 'RAW_FIELDS', public_key: 'key_test_public', locale: 'es',
    }))));
    renderTokenizer();
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible preparar la tarjeta');
    expect(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`)).toBeNull();
    expect(screen.queryByLabelText(/número|cvv|cvc|vencimiento/i)).not.toBeInTheDocument();
  });

  it('deduplicates concurrent script loads and rejects when the provider global is missing', async () => {
    const first = loadConektaScript();
    const script = document.querySelector<HTMLScriptElement>(`script[src="${CONEKTA_SCRIPT_URL}"]`);
    const second = loadConektaScript();
    expect(document.querySelectorAll(`script[src="${CONEKTA_SCRIPT_URL}"]`)).toHaveLength(1);
    fireEvent.load(script as HTMLScriptElement);
    await expect(first).rejects.toThrow('global is unavailable');
    await expect(second).rejects.toThrow('global is unavailable');
  });

  it('shows a recoverable error after script failure and safely retries loading', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json({
      provider: 'CONEKTA', tokenization_mode: 'WEB_TOKENIZER',
      public_key: 'key_test_public', locale: 'es',
    }))));
    renderTokenizer();
    await waitFor(() => expect(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`)).not.toBeNull());
    fireEvent.error(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`) as HTMLScriptElement);
    expect(await screen.findByRole('alert')).toHaveTextContent('No se realizó ningún pago');
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await waitFor(() => expect(document.querySelectorAll(`script[src="${CONEKTA_SCRIPT_URL}"]`)).toHaveLength(1));
  });

  it('keeps tokenization errors local and ignores provider success after unmount', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json({
      provider: 'CONEKTA', tokenization_mode: 'WEB_TOKENIZER',
      public_key: 'key_test_public', locale: 'es',
    }))));
    let parameters: ConektaCardParameters | undefined;
    const sourceReady = vi.fn();
    const view = renderTokenizer(sourceReady);
    await waitFor(() => expect(document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`)).not.toBeNull());
    installProvider((value) => { parameters = value; });
    await waitFor(() => expect(parameters).toBeDefined());
    parameters?.callbacks.onCreateTokenError({ message: 'declined input' });
    expect(await screen.findByRole('alert')).toHaveTextContent('No fue posible preparar la tarjeta');
    expect(screen.queryByText(/FAILED|REJECTED|UNCERTAIN/)).not.toBeInTheDocument();
    view.unmount();
    parameters?.callbacks.onCreateTokenSucceeded({ id: 'tok_test_opaque' });
    expect(sourceReady).not.toHaveBeenCalled();
  });
});
