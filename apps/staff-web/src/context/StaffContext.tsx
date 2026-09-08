import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Location, Organization, Tenant } from '../api/contracts';
import { staffApi } from '../api/client';
import { useAuth } from '../session/AuthContext';
import { readSelectedLocationId, storeSelectedLocationId } from '../session/storage';

interface StaffContextValue {
  status: 'loading' | 'ready' | 'selection-required' | 'unavailable' | 'error';
  tenant: Tenant | null;
  organization: Organization | null;
  location: Location | null;
  locations: Location[];
  selectLocation: (locationId: number) => void;
  retry: () => void;
}

const StaffContext = createContext<StaffContextValue | null>(null);

export function StaffContextProvider({ children }: PropsWithChildren) {
  const { identity, credential, hasPermission } = useAuth();
  const [selectedId, setSelectedId] = useState<number | null>(readSelectedLocationId);
  const canReadLocations = hasPermission('location.read');
  const locationsQuery = useQuery({
    queryKey: ['staff', 'locations', identity?.tenant_id],
    queryFn: staffApi.locations,
    enabled: Boolean(identity && canReadLocations),
    retry: false,
  });
  const activeLocations = useMemo(
    () => locationsQuery.data?.items.filter((location) => location.status === 'ACTIVE') ?? [],
    [locationsQuery.data],
  );
  const validatedId = activeLocations.some((location) => location.id === selectedId)
    ? selectedId
    : activeLocations.length === 1 ? activeLocations[0].id : null;
  const location = activeLocations.find((item) => item.id === validatedId) ?? null;

  useEffect(() => {
    if (validatedId && validatedId !== selectedId) {
      setSelectedId(validatedId);
      storeSelectedLocationId(validatedId);
    }
  }, [selectedId, validatedId]);

  const tenantQuery = useQuery({
    queryKey: ['staff', 'tenant', identity?.tenant_id],
    queryFn: staffApi.currentTenant,
    enabled: Boolean(identity && hasPermission('tenant.read')),
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
    setSelectedId(locationId);
    storeSelectedLocationId(locationId);
  };

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
    selectLocation,
    retry: () => { void locationsQuery.refetch(); },
  }), [status, tenant, organizationQuery.data, location, activeLocations, locationsQuery]);

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>;
}

export function useStaffContext(): StaffContextValue {
  const value = useContext(StaffContext);
  if (!value) throw new Error('useStaffContext must be used inside StaffContextProvider');
  return value;
}
