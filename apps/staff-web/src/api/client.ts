import type {
  ApiErrorBody,
  LocationListResponse,
  LoginRequest,
  LoginResponse,
  Organization,
  OpenServiceSessionResponse,
  RegeneratedAccessCodeResponse,
  ResourceListResponse,
  ClosedServiceSessionResponse,
  CurrentServiceSession,
  StaffIdentity,
  StaffOperationalRequest,
  StaffOperationalRequestListResponse,
  OperationalRequestStatus,
  OperationalRequestType,
  PreparationAreaListResponse,
  PreparationDispatch,
  PreparationState,
  PreparationTransitionResult,
  PreparationWork,
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
  tables(locationId: number): Promise<ResourceListResponse> {
    const query = new URLSearchParams({
      location_id: String(locationId),
      resource_type: 'TABLE',
      status: 'ACTIVE',
      limit: '100',
      offset: '0',
    });
    return request(`/resources?${query.toString()}`);
  },
  async currentServiceSession(resourceId: number): Promise<CurrentServiceSession | null> {
    try {
      return await request(`/resources/${resourceId}/service-sessions/current`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  openServiceSession(resourceId: number, partySize: number): Promise<OpenServiceSessionResponse> {
    return request(`/resources/${resourceId}/service-sessions`, {
      method: 'POST',
      body: JSON.stringify({ party_size: partySize }),
    });
  },
  regenerateAccessCode(sessionId: number): Promise<RegeneratedAccessCodeResponse> {
    return request(`/restaurant-service-sessions/${sessionId}/access-code/regenerate`, { method: 'POST' });
  },
  closeServiceSession(sessionId: number): Promise<ClosedServiceSessionResponse> {
    return request(`/restaurant-service-sessions/${sessionId}/close`, { method: 'POST' });
  },
  operationalRequests(
    locationId: number,
    filters: { status?: OperationalRequestStatus; requestType?: OperationalRequestType },
  ): Promise<StaffOperationalRequestListResponse> {
    const query = new URLSearchParams({
      location_id: String(locationId),
      limit: '100',
      offset: '0',
    });
    if (filters.status) query.set('status', filters.status);
    if (filters.requestType) query.set('request_type', filters.requestType);
    return request(`/staff/operational-requests?${query.toString()}`);
  },
  acknowledgeOperationalRequest(
    requestId: number,
    locationId: number,
  ): Promise<StaffOperationalRequest> {
    const query = new URLSearchParams({ location_id: String(locationId) });
    return request(`/staff/operational-requests/${requestId}/acknowledge?${query.toString()}`, {
      method: 'POST',
    });
  },
  completeOperationalRequest(
    requestId: number,
    locationId: number,
  ): Promise<StaffOperationalRequest> {
    const query = new URLSearchParams({ location_id: String(locationId) });
    return request(`/staff/operational-requests/${requestId}/complete?${query.toString()}`, {
      method: 'POST',
    });
  },
  preparationAreas(locationId: number): Promise<PreparationAreaListResponse> {
    const query = new URLSearchParams({ location_id: String(locationId) });
    return request(`/preparation-areas?${query.toString()}`);
  },
  preparationWorks(
    locationId: number,
    filters: { state?: PreparationState; areaId?: number },
  ): Promise<PreparationWork[]> {
    const query = new URLSearchParams({ location_id: String(locationId), limit: '200' });
    if (filters.state) query.set('execution_state', filters.state);
    if (filters.areaId) query.set('preparation_area_id', String(filters.areaId));
    return request(`/preparation-works?${query.toString()}`);
  },
  transitionPreparationItem(
    itemId: number,
    expectedState: PreparationState,
    expectedVersion: number,
    toState: PreparationState,
    idempotencyKey: string,
  ): Promise<PreparationTransitionResult> {
    return request(`/preparation-work-items/${itemId}/transitions`, {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify({
        expected_state: expectedState,
        expected_version: expectedVersion,
        to_state: toState,
      }),
    });
  },
  preparationDispatches(locationId: number): Promise<PreparationDispatch[]> {
    const query = new URLSearchParams({ location_id: String(locationId), limit: '200' });
    return request(`/preparation-dispatches?${query.toString()}`);
  },
  reprintPreparationDispatch(dispatchId: number): Promise<PreparationDispatch> {
    return request(`/preparation-dispatches/${dispatchId}/reprints`, { method: 'POST' });
  },
};
