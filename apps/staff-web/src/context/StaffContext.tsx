import {
  useCallback,
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Location, Organization, Tenant } from '../api/contracts';
import { staffApi } from '../api/client';
import { canUseWorkspace, workspaceForPath } from '../navigation/workspaces';
import { useAuth } from '../session/AuthContext';
import {
  clearStaffResumeHint,
  readStaffResumeHint,
  storeStaffResumeHint,
  type StaffResumeHint,
} from '../session/storage';

interface StaffContextValue {
  status: 'loading' | 'ready' | 'selection-required' | 'unavailable' | 'error';
  tenant: Tenant | null;
  organization: Organization | null;
  location: Location | null;
  locations: Location[];
  roles: string[];
  permissions: string[];
  resumePath: string | null;
  hasPermission: (permission: string) => boolean;
  selectHome: () => void;
  selectLocation: (locationId: number) => void;
  retry: () => void;
}

const StaffContext = createContext<StaffContextValue | null>(null);

export function StaffContextProvider({ children }: PropsWithChildren) {
  const { identity, credential, hasPermission: hasTenantPermission } = useAuth();
  const route = useLocation();
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [resumeHint, setResumeHint] = useState<StaffResumeHint | null>(readStaffResumeHint);
  const explicitHomeRef = useRef(false);
  const readableAuthorityIds = useMemo(() => new Set(
    identity?.location_authorities
      .filter((authority) => authority.permissions.includes('location.read'))
      .map((authority) => authority.location_id) ?? [],
  ), [identity]);
  const canReadLocations = readableAuthorityIds.size > 0;
  const locationsQuery = useQuery({
    queryKey: ['staff', 'locations', identity?.tenant_id],
    queryFn: staffApi.locations,
    enabled: Boolean(identity && canReadLocations),
    retry: false,
  });
  const activeLocations = useMemo(
    () => locationsQuery.data?.items.filter(
      (location) => location.status === 'ACTIVE' && readableAuthorityIds.has(location.id),
    ) ?? [],
    [locationsQuery.data, readableAuthorityIds],
  );
  const hintMatchesIdentity = Boolean(identity && resumeHint?.identityKey === identity.username);
  const hintedId = hintMatchesIdentity ? resumeHint?.locationId ?? null : null;
  const validatedId = activeLocations.some((location) => location.id === selectedId)
    ? selectedId
    : activeLocations.some((location) => location.id === hintedId) ? hintedId
    : activeLocations.length === 1 ? activeLocations[0].id : null;
  const location = activeLocations.find((item) => item.id === validatedId) ?? null;
  const authority = identity?.location_authorities.find(
    (value) => value.location_id === location?.id,
  );
  const roles = authority?.roles ?? [];
  const permissions = authority?.permissions ?? [];
  const hasPermission = useCallback(
    (permission: string) => permissions.includes(permission),
    [permissions],
  );
  const hintedWorkspace = resumeHint ? workspaceForPath(resumeHint.workspacePath) : undefined;
  const resumePath = hintMatchesIdentity
    && location?.id === resumeHint?.locationId
    && hintedWorkspace
    && canUseWorkspace(permissions, hintedWorkspace)
    ? resumeHint!.workspacePath
    : null;

  useEffect(() => {
    if (validatedId !== selectedId) {
      setSelectedId(validatedId);
    }
  }, [selectedId, validatedId]);

  useEffect(() => {
    if (!identity || !canReadLocations || locationsQuery.isPending || locationsQuery.isError) return;
    if (resumeHint && (!hintMatchesIdentity || !activeLocations.some(
      (item) => item.id === resumeHint.locationId,
    ))) {
      clearStaffResumeHint();
      setResumeHint(null);
      return;
    }
    if (resumeHint && location?.id === resumeHint.locationId && resumeHint.workspacePath !== '/') {
      const workspace = workspaceForPath(resumeHint.workspacePath);
      if (!workspace || !canUseWorkspace(permissions, workspace)) {
        clearStaffResumeHint();
        setResumeHint(null);
      }
    }
  }, [
    activeLocations, canReadLocations, hintMatchesIdentity, identity, location,
    locationsQuery.isError, locationsQuery.isPending, permissions, resumeHint,
  ]);

  useEffect(() => {
    if (!identity || !location) return;
    if (explicitHomeRef.current && route.pathname !== '/') return;
    explicitHomeRef.current = false;
    const workspace = workspaceForPath(route.pathname);
    if (workspace && !canUseWorkspace(permissions, workspace)) return;
    if (route.pathname === '/' && resumePath && resumePath !== '/') return;
    const next = {
      identityKey: identity.username,
      locationId: location.id,
      workspacePath: workspace ? route.pathname : '/',
    };
    storeStaffResumeHint(next);
    setResumeHint((current) => (
      current?.identityKey === next.identityKey
      && current.locationId === next.locationId
      && current.workspacePath === next.workspacePath ? current : next
    ));
  }, [identity, location, permissions, resumePath, route.pathname]);

  const tenantQuery = useQuery({
    queryKey: ['staff', 'tenant', identity?.tenant_id],
    queryFn: staffApi.currentTenant,
    enabled: Boolean(identity && hasTenantPermission('tenant.read')),
    retry: false,
  });
  const organizationQuery = useQuery({
    queryKey: ['staff', 'organization', location?.organization_id],
    queryFn: () => staffApi.organization(location!.organization_id),
    enabled: Boolean(location && hasPermission('organization.read')),
    retry: false,
  });

  const selectLocation = (locationId: number) => {
    if (!activeLocations.some((item) => item.id === locationId)) return;
    const selectedAuthority = identity?.location_authorities.find(
      (value) => value.location_id === locationId,
    );
    const workspace = workspaceForPath(route.pathname);
    const workspacePath = workspace
      && canUseWorkspace(selectedAuthority?.permissions ?? [], workspace)
      ? route.pathname
      : '/';
    if (identity) {
      const next = { identityKey: identity.username, locationId, workspacePath };
      storeStaffResumeHint(next);
      setResumeHint(next);
    }
    setSelectedId(locationId);
    if (workspace && workspacePath === '/') navigate('/', { replace: true });
  };

  const selectHome = useCallback(() => {
    if (!identity || !location) return;
    explicitHomeRef.current = true;
    const next = {
      identityKey: identity.username,
      locationId: location.id,
      workspacePath: '/',
    };
    storeStaffResumeHint(next);
    setResumeHint(next);
    navigate('/');
  }, [identity, location, navigate]);

  let status: StaffContextValue['status'];
  if (!canReadLocations) status = 'unavailable';
  else if (locationsQuery.isPending) status = 'loading';
  else if (locationsQuery.isError) status = 'error';
  else if (!location && activeLocations.length > 1) status = 'selection-required';
  else if (!location) status = 'unavailable';
  else status = 'ready';

  const tenant = tenantQuery.data ?? (identity && credential ? {
    id: identity.tenant_id,
    name: credential.tenantName,
    slug: '',
    status: 'ACTIVE',
  } : null);

  const value = useMemo<StaffContextValue>(() => ({
    status,
    tenant,
    organization: organizationQuery.data ?? null,
    location,
    locations: activeLocations,
    roles,
    permissions,
    resumePath,
    hasPermission,
    selectHome,
    selectLocation,
    retry: () => { void locationsQuery.refetch(); },
  }), [
    status, tenant, organizationQuery.data, location, activeLocations, roles,
    permissions, resumePath, hasPermission, selectHome, locationsQuery,
  ]);

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>;
}

export function useStaffContext(): StaffContextValue {
  const value = useContext(StaffContext);
  if (!value) throw new Error('useStaffContext must be used inside StaffContextProvider');
  return value;
}
