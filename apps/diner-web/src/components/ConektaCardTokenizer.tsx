import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dinerApi } from '../api/client';
import { loadConektaScript, type ConektaLocale, type ConektaSubmit } from '../payments/conekta';

export interface EphemeralCustomerPaymentSource {
  provider: 'CONEKTA';
  source: string;
}

interface ConektaCardTokenizerProps {
  executorKey: string;
  currency: string;
  onSourceReady: (source: EphemeralCustomerPaymentSource) => void;
}

type TokenizerState = 'loading' | 'initializing' | 'ready' | 'tokenizing' | 'complete' | 'error';
let tokenizerSequence = 0;

function validConfiguration(value: {
  provider: string;
  tokenization_mode: string;
  public_key: string;
  locale: string;
}): value is typeof value & { locale: ConektaLocale } {
  return value.provider === 'CONEKTA'
    && value.tokenization_mode === 'WEB_TOKENIZER'
    && value.public_key.trim().length > 0
    && (value.locale === 'es' || value.locale === 'en');
}

export function ConektaCardTokenizer({ executorKey, currency, onSourceReady }: ConektaCardTokenizerProps) {
  const [containerId] = useState(() => `conekta-card-tokenizer-${++tokenizerSequence}`);
  const submit = useRef<ConektaSubmit | null>(null);
  const onSourceReadyRef = useRef(onSourceReady);
  const [state, setState] = useState<TokenizerState>('loading');
  const [attempt, setAttempt] = useState(0);
  const configuration = useQuery({
    queryKey: ['diner', 'payment-executor-client-configuration', executorKey, currency],
    queryFn: () => dinerApi.getPaymentExecutorClientConfiguration(executorKey, currency),
    retry: false,
  });

  useEffect(() => { onSourceReadyRef.current = onSourceReady; }, [onSourceReady]);

  useEffect(() => {
    const clientConfiguration = configuration.data;
    if (!clientConfiguration) return;
    if (!validConfiguration(clientConfiguration)) {
      setState('error');
      return;
    }

    let active = true;
    const container = document.getElementById(containerId);
    submit.current = null;
    setState('loading');

    loadConektaScript().then((components) => {
      if (!active) return;
      setState('initializing');
      components.Card({
        config: {
          targetIFrame: `#${containerId}`,
          publicKey: clientConfiguration.public_key,
          locale: clientConfiguration.locale,
          useExternalSubmit: true,
        },
        callbacks: {
          onGetInfoSuccess: () => {
            if (active && submit.current) setState('ready');
          },
          onUpdateSubmitTrigger: (nextSubmit) => {
            if (!active || typeof nextSubmit !== 'function') return;
            submit.current = nextSubmit;
            setState('ready');
          },
          onCreateTokenSucceeded: (token) => {
            if (!active) return;
            if (typeof token.id !== 'string' || token.id.length === 0) {
              submit.current = null;
              setState('error');
              return;
            }
            setState('complete');
            onSourceReadyRef.current({ provider: 'CONEKTA', source: token.id });
          },
          onCreateTokenError: () => {
            if (active) setState('error');
          },
        },
        options: {
          backgroundMode: document.documentElement.dataset.theme === 'dark' ? 'darkMode' : 'lightMode',
          inputType: 'minimalMode',
        },
      });
    }).catch(() => {
      if (active) setState('error');
    });

    return () => {
      active = false;
      submit.current = null;
      container?.replaceChildren();
    };
  }, [attempt, configuration.data, containerId]);

  const tokenize = useCallback(() => {
    if (!submit.current || state !== 'ready') return;
    setState('tokenizing');
    try {
      submit.current();
    } catch {
      setState('error');
    }
  }, [state]);

  const retry = useCallback(() => {
    submit.current = null;
    setState('loading');
    if (configuration.isError) void configuration.refetch();
    else setAttempt((current) => current + 1);
  }, [configuration]);

  const failed = configuration.isError || state === 'error';
  const status = configuration.isPending || state === 'loading'
    ? 'Preparando pago con tarjeta…'
    : state === 'initializing'
      ? 'Preparando el formulario seguro…'
      : state === 'tokenizing'
        ? 'Generando información segura de pago…'
        : state === 'complete'
          ? 'Información de tarjeta preparada'
          : state === 'ready'
            ? 'Formulario de tarjeta listo'
            : '';

  return (
    <section className="conekta-tokenizer" aria-labelledby={`${containerId}-title`}>
      <p className="panel-kicker">Tarjeta</p>
      <h2 id={`${containerId}-title`}>Pago seguro con tarjeta</h2>
      <p>Captura los datos directamente en el formulario seguro de Conekta. En este paso sólo prepararemos la información de pago.</p>
      {failed && (
        <div className="conekta-tokenizer-error" role="alert">
          <strong>No fue posible preparar la tarjeta</strong>
          <p>No se realizó ningún pago. Puedes intentarlo nuevamente.</p>
          <button className="secondary-button" type="button" onClick={retry}>Reintentar</button>
        </div>
      )}
      <div
        id={containerId}
        className="conekta-iframe-container"
        aria-hidden={failed ? 'true' : undefined}
      />
      {!failed && <p className="conekta-tokenizer-status" role="status" aria-live="polite">{status}</p>}
      <button
        className="primary-button"
        type="button"
        disabled={state !== 'ready'}
        onClick={tokenize}
      >
        {state === 'tokenizing' ? 'Preparando tarjeta…' : state === 'complete' ? 'Tarjeta preparada' : 'Continuar con tarjeta'}
      </button>
    </section>
  );
}
