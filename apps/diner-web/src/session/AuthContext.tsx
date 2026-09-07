import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import type { DinerJoinResponse } from '../api/contracts';
import { ApiError, dinerApi, onAuthFailure } from '../api/client';
import {
  clearStoredSession,
  fromJoinResponse,
  isSessionExpired,
  readStoredSession,
  storeSession,
  type StoredDinerSession,
} from './storage';

export type AuthStatus =
  | 'unauthenticated'
  | 'checking'
  | 'authenticated'
  | 'expired'
  | 'closed'
  | 'restoration-error';

interface AuthContextValue {
  status: AuthStatus;
  session: StoredDinerSession | null;
  authenticate: (response: DinerJoinResponse) => void;
  retryRestoration: () => void;
  leaveSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function initialAuthState(): { status: AuthStatus; session: StoredDinerSession | null } {
  const session = readStoredSession();
  if (!session) return { status: 'unauthenticated', session: null };
  if (isSessionExpired(session)) {
    clearStoredSession();
    return { status: 'expired', session: null };
  }
  return { status: 'checking', session };
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [auth, setAuth] = useState(initialAuthState);
  const restoration = useQuery({
    queryKey: ['diner-session', 'restore'],
    queryFn: dinerApi.getCurrentSession,
    enabled: auth.status === 'checking',
    retry: false,
  });

  const invalidate = useCallback((failure: 'invalid' | 'closed') => {
    clearStoredSession();
    setAuth({ status: failure === 'closed' ? 'closed' : 'expired', session: null });
  }, []);

  useEffect(() => onAuthFailure(invalidate), [invalidate]);

  useEffect(() => {
    if (auth.status !== 'checking') return;
    if (restoration.data) {
      setAuth((current) => {
        if (!current.session) return { status: 'unauthenticated', session: null };
        const session = { ...current.session, displayName: restoration.data.display_name };
        storeSession(session);
        return { status: 'authenticated', session };
      });
    } else if (restoration.error) {
      if (restoration.error instanceof ApiError && restoration.error.state === 'SESSION_CLOSED') {
        invalidate('closed');
      } else if (restoration.error instanceof ApiError && restoration.error.status === 401) {
        invalidate('invalid');
      } else {
        setAuth((current) => ({ status: 'restoration-error', session: current.session }));
      }
    }
  }, [auth.status, invalidate, restoration.data, restoration.error]);

  const authenticate = useCallback((response: DinerJoinResponse) => {
    const session = fromJoinResponse(response);
    storeSession(session);
    setAuth({ status: 'authenticated', session });
  }, []);

  const retryRestoration = useCallback(() => {
    setAuth((current) => ({ ...current, status: current.session ? 'checking' : 'unauthenticated' }));
  }, []);

  const leaveSession = useCallback(() => {
    clearStoredSession();
    setAuth({ status: 'unauthenticated', session: null });
  }, []);

  const value = useMemo(
    () => ({ status: auth.status, session: auth.session, authenticate, retryRestoration, leaveSession }),
    [auth, authenticate, retryRestoration, leaveSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside AuthProvider');
  return value;
}
