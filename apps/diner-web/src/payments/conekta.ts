export const CONEKTA_SCRIPT_URL = 'https://pay.conekta.com/v1.0/js/conekta-checkout.min.js';

export interface ConektaToken {
  id?: unknown;
}

export type ConektaSubmit = () => void;
export type ConektaLocale = 'es' | 'en';

export interface ConektaCardParameters {
  config: {
    targetIFrame: string;
    publicKey: string;
    locale: ConektaLocale;
    useExternalSubmit: true;
  };
  callbacks: {
    onCreateTokenSucceeded: (token: ConektaToken) => void;
    onCreateTokenError: (error: unknown) => void;
    onGetInfoSuccess: (loadingTime: unknown) => void;
    onUpdateSubmitTrigger: (submit: ConektaSubmit) => void;
  };
  options?: {
    backgroundMode: 'lightMode' | 'darkMode';
    inputType: 'minimalMode';
  };
}

interface ConektaCheckoutComponents {
  Card: (parameters: ConektaCardParameters) => unknown;
}

declare global {
  interface Window {
    ConektaCheckoutComponents?: ConektaCheckoutComponents;
  }
}

let loadingScript: Promise<ConektaCheckoutComponents> | null = null;

function loadedComponents(): ConektaCheckoutComponents | null {
  const components = window.ConektaCheckoutComponents;
  return components && typeof components.Card === 'function' ? components : null;
}

export function loadConektaScript(): Promise<ConektaCheckoutComponents> {
  const loaded = loadedComponents();
  if (loaded) return Promise.resolve(loaded);
  if (loadingScript && document.querySelector(`script[src="${CONEKTA_SCRIPT_URL}"]`)) return loadingScript;
  loadingScript = null;

  loadingScript = new Promise((resolve, reject) => {
    let script = document.querySelector<HTMLScriptElement>(`script[src="${CONEKTA_SCRIPT_URL}"]`);
    const created = !script;
    if (!script) {
      script = document.createElement('script');
      script.src = CONEKTA_SCRIPT_URL;
      script.async = true;
      script.dataset.conektaTokenizer = 'true';
    }

    const fail = (message: string) => {
      loadingScript = null;
      if (created) script?.remove();
      reject(new Error(message));
    };
    const onLoad = () => {
      const components = loadedComponents();
      if (components) {
        loadingScript = null;
        resolve(components);
      }
      else fail('Conekta tokenizer global is unavailable');
    };
    const onError = () => fail('Conekta tokenizer script failed to load');

    script.addEventListener('load', onLoad, { once: true });
    script.addEventListener('error', onError, { once: true });
    if (created) document.head.append(script);
  });

  return loadingScript;
}
