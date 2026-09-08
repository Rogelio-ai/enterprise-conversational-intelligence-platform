import type { LoginResponse } from '../api/contracts';

const AUTH_KEY = 'staff-auth-session-v1';
const LOCATION_KEY = 'staff-location-context-v1';

export interface StoredStaffCredential {
  accessToken: string;
  expiresAt: string;
  tenantId: number;
  tenantName: string;
}

function isCredential(value: unknown): value is StoredStaffCredential {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.accessToken === 'string'
    && typeof candidate.expiresAt === 'string'
    && typeof candidate.tenantId === 'number'
    && typeof candidate.tenantName === 'string';
}

export function credentialFromLogin(value: LoginResponse): StoredStaffCredential {
  return {
    accessToken: value.access_token,
    expiresAt: new Date(Date.now() + value.expires_in * 1000).toISOString(),
    tenantId: value.tenant.id,
    tenantName: value.tenant.name,
  };
}

export function readCredential(): StoredStaffCredential | null {
  try {
    const raw = sessionStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!isCredential(value)) {
      sessionStorage.removeItem(AUTH_KEY);
      return null;
    }
    return value;
  } catch {
    sessionStorage.removeItem(AUTH_KEY);
    return null;
  }
}

export function storeCredential(value: StoredStaffCredential): void {
  sessionStorage.setItem(AUTH_KEY, JSON.stringify(value));
}

export function clearStaffStorage(): void {
  sessionStorage.removeItem(AUTH_KEY);
  sessionStorage.removeItem(LOCATION_KEY);
}

export function credentialExpired(value: StoredStaffCredential): boolean {
  const expiration = Date.parse(value.expiresAt);
  return !Number.isFinite(expiration) || expiration <= Date.now();
}

export function readSelectedLocationId(): number | null {
  const value = Number(sessionStorage.getItem(LOCATION_KEY));
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

export function storeSelectedLocationId(locationId: number): void {
  sessionStorage.setItem(LOCATION_KEY, String(locationId));
}
