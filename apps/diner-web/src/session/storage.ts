import type { DinerJoinResponse } from '../api/contracts';

const STORAGE_KEY = 'diner-auth-session-v1';

export interface StoredDinerSession {
  dinerSessionId: number;
  serviceSessionId: number;
  conversationId: number;
  displayName: string;
  customerId: number | null;
  accessToken: string;
  expiresAt: string;
}

function isStoredDinerSession(value: unknown): value is StoredDinerSession {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.dinerSessionId === 'number' &&
    typeof candidate.serviceSessionId === 'number' &&
    typeof candidate.conversationId === 'number' &&
    typeof candidate.displayName === 'string' &&
    (typeof candidate.customerId === 'number' || candidate.customerId === null) &&
    typeof candidate.accessToken === 'string' &&
    typeof candidate.expiresAt === 'string'
  );
}

export function fromJoinResponse(response: DinerJoinResponse): StoredDinerSession {
  return {
    dinerSessionId: response.diner_session_id,
    serviceSessionId: response.service_session_id,
    conversationId: response.conversation_id,
    displayName: response.display_name,
    customerId: response.customer_id,
    accessToken: response.access_token,
    expiresAt: response.expires_at,
  };
}

export function readStoredSession(): StoredDinerSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!isStoredDinerSession(value)) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return value;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function storeSession(session: StoredDinerSession): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredSession(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function isSessionExpired(session: StoredDinerSession): boolean {
  const expiration = Date.parse(session.expiresAt);
  return !Number.isFinite(expiration) || expiration <= Date.now();
}
