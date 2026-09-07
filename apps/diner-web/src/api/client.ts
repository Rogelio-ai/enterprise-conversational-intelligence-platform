import type {
  ApiErrorBody,
  DinerJoinRequest,
  DinerJoinResponse,
  DinerMenuResponse,
  DinerSessionResponse,
} from './contracts';
import { readStoredSession } from '../session/storage';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
const API_BASE_URL = configuredBaseUrl || '/api';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly state: string | undefined,
    public readonly correlationId: string | undefined,
  ) {
    super(code);
    this.name = 'ApiError';
  }
}

type AuthFailure = 'invalid' | 'closed';
type AuthFailureListener = (failure: AuthFailure) => void;
const authFailureListeners = new Set<AuthFailureListener>();

export function onAuthFailure(listener: AuthFailureListener): () => void {
  authFailureListeners.add(listener);
  return () => authFailureListeners.delete(listener);
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');

  if (authenticated) {
    const token = readStoredSession()?.accessToken;
    if (!token) {
      authFailureListeners.forEach((listener) => listener('invalid'));
      throw new ApiError(401, 'missing_authentication', undefined, undefined);
    }
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, 'network_error', undefined, undefined);
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // An unreadable response is still represented by its safe HTTP status.
    }
    const code = body.error?.code || 'unexpected_error';
    const state = body.error?.state;
    if (authenticated && state === 'SESSION_CLOSED') {
      authFailureListeners.forEach((listener) => listener('closed'));
    } else if (authenticated && response.status === 401) {
      authFailureListeners.forEach((listener) => listener('invalid'));
    }
    throw new ApiError(response.status, code, state, body.correlation_id);
  }

  return (await response.json()) as T;
}

export const dinerApi = {
  join(payload: DinerJoinRequest): Promise<DinerJoinResponse> {
    return request('/diner-sessions/join', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getCurrentSession(): Promise<DinerSessionResponse> {
    return request('/diner-session', {}, true);
  },

  getMenu(): Promise<DinerMenuResponse> {
    return request('/diner/menu', {}, true);
  },
};
