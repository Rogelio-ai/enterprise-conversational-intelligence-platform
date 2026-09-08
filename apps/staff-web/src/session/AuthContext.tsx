import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { LoginRequest, StaffIdentity } from '../api/contracts';
import { ApiError, onUnauthorized, staffApi } from '../api/client';
import {
  clearStaffStorage,
  credentialExpired,
  credentialFromLogin,
  readCredential,
  storeCredential,
  type StoredStaffCredential,
} from './storage';

export type AuthStatus =
  | 'unauthenticated'
  | 'checking'
  | 'authenticated'
  | 'expired'
  | 'restoration-error';

interface AuthState {
  status: AuthStatus;
  credential: StoredStaffCredential | null;
  identity: StaffIdentity | null;
}

interface AuthContextValue extends AuthState {
  login: (payload: LoginRequest) => Promise<void>;
  logout: () => void;
  retryRestoration: () => void;
  hasPermission: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function initialState(): AuthState {
  const credential = readCredential();
  if (!credential) return { status: 'unauthenticated', credential: null, identity: null };
  if (credentialExpired(credential)) {
    clearStaffStorage();
    return { status: 'expired', credential: null, identity: null };
  }
  return { status: 'checking', credential, identity: null };
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [auth, setAuth] = useState<AuthState>(initialState);
  const queryClient = useQueryClient();
  const restoration = useQuery({
    queryKey: ['staff', 'identity'],
    queryFn: staffApi.me,
    enabled: auth.status === 'checking' && auth.credential !== null,
    retry: false,
  });

  const invalidate = useCallback(() => {
    clearStaffStorage();
    queryClient.clear();
    setAuth({ status: 'expired', credential: null, identity: null });
  }, [queryClient]);

  useEffect(() => onUnauthorized(invalidate), [invalidate]);

  useEffect(() => {
    if (!auth.credential) return;
    const remaining = Date.parse(auth.credential.expiresAt) - Date.now();
    if (!Number.isFinite(remaining) || remaining <= 0) {
      invalidate();
      return;
    }
    const timer = window.setTimeout(invalidate, Math.min(remaining, 2_147_483_647));
    return () => window.clearTimeout(timer);
  }, [auth.credential, invalidate]);

  useEffect(() => {
    if (auth.status !== 'checking') return;
    if (restoration.data) {
      if (auth.credential && restoration.data.tenant_id !== auth.credential.tenantId) {
        invalidate();
        return;
      }
      setAuth((current) => ({ ...current, status: 'authenticated', identity: restoration.data }));
    } else if (restoration.error) {
      if (restoration.error instanceof ApiError && restoration.error.kind === 'authentication') {
        invalidate();
      } else {
        setAuth((current) => ({ ...current, status: 'restoration-error' }));
      }
    }
  }, [auth.status, auth.credential, invalidate, restoration.data, restoration.error]);

  const login = useCallback(async (payload: LoginRequest) => {
    const response = await staffApi.login(payload);
    const credential = credentialFromLogin(response);
    storeCredential(credential);
    setAuth({ status: 'checking', credential, identity: null });
  }, []);

  const logout = useCallback(() => {
    clearStaffStorage();
    queryClient.clear();
    setAuth({ status: 'unauthenticated', credential: null, identity: null });
  }, [queryClient]);

  const retryRestoration = useCallback(() => {
    setAuth((current) => current.credential
      ? { ...current, status: 'checking' }
      : { status: 'unauthenticated', credential: null, identity: null });
    void restoration.refetch();
  }, [restoration]);

  const permissions = auth.identity?.permissions;
  const hasPermission = useCallback(
    (permission: string) => permissions?.includes(permission) ?? false,
    [permissions],
  );

  const value = useMemo<AuthContextValue>(() => ({
    ...auth,
    login,
    logout,
    retryRestoration,
    hasPermission,
  }), [auth, login, logout, retryRestoration, hasPermission]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
