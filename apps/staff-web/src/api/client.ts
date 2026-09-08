import type {
  ApiErrorBody,
  LocationListResponse,
  LoginRequest,
  LoginResponse,
  Organization,
  StaffIdentity,
  Tenant,
} from './contracts';
import { readCredential } from '../session/storage';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
const API_BASE_URL = configuredBaseUrl || '/api';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly kind: 'network' | 'authentication' | 'authorization' | 'backend',
    public readonly correlationId?: string,
    message = code,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

type UnauthorizedListener = () => void;
const unauthorizedListeners = new Set<UnauthorizedListener>();

export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  if (authenticated) {
    const credential = readCredential();
    if (!credential) {
      unauthorizedListeners.forEach((listener) => listener());
      throw new ApiError(401, 'missing_authentication', 'authentication');
    }
    headers.set('Authorization', `Bearer ${credential.accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, 'network_unavailable', 'network', undefined, 'No fue posible conectar con el servicio.');
  }

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try { body = await response.json() as ApiErrorBody; } catch { /* safe status fallback */ }
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message;
    const code = body.error?.code || (typeof body.detail === 'object' ? body.detail.code : undefined) || `http_${response.status}`;
    const kind = response.status === 401 ? 'authentication' : response.status === 403 ? 'authorization' : 'backend';
    if (authenticated && response.status === 401) unauthorizedListeners.forEach((listener) => listener());
    throw new ApiError(response.status, code, kind, body.correlation_id, body.error?.message || detail || 'La operación no pudo completarse.');
  }

  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export const staffApi = {
  login(payload: LoginRequest): Promise<LoginResponse> {
    return request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }, false);
  },
  me(): Promise<StaffIdentity> {
    return request('/auth/me');
  },
  currentTenant(): Promise<Tenant> {
    return request('/tenants/current');
  },
  locations(): Promise<LocationListResponse> {
    return request('/locations?limit=100&offset=0');
  },
  organization(organizationId: number): Promise<Organization> {
    return request(`/organizations/${organizationId}`);
  },
};
