export interface LoginRequest {
  email: string;
  password: string;
  tenant_id?: number;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: { id: number; email: string; display_name: string };
  tenant: { id: number; name: string; slug: string; membership_id: number };
}

export interface StaffIdentity {
  user_id: number;
  email: string;
  display_name: string;
  tenant_id: number;
  membership_id: number;
  roles: string[];
  permissions: string[];
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  status: 'ACTIVE' | string;
}

export interface Organization {
  id: number;
  tenant_id: number;
  code: string;
  name: string;
  status: 'ACTIVE' | 'INACTIVE';
}

export interface Location {
  id: number;
  tenant_id: number;
  organization_id: number;
  code: string;
  name: string;
  timezone: string;
  status: 'ACTIVE' | 'INACTIVE';
}

export interface LocationListResponse {
  items: Location[];
  limit: number;
  offset: number;
}

export interface Resource {
  id: number;
  tenant_id: number;
  location_id: number;
  code: string;
  name: string;
  resource_type: string;
  status: 'ACTIVE' | 'INACTIVE' | string;
  created_at: string;
  updated_at: string;
}

export interface ResourceListResponse {
  items: Resource[];
  limit: number;
  offset: number;
}

export interface CurrentServiceSession {
  id: number;
  resource_id: number;
  party_size: number;
  active_diner_count: number;
  status: string;
  join_context_key: string;
  access_code_version: number;
  opened_at: string;
}

export interface OpenServiceSessionResponse {
  id: number;
  resource_id: number;
  party_size: number;
  status: string;
  join_context_key: string;
  access_code: string;
  access_code_version: number;
  opened_at: string;
}

export interface RegeneratedAccessCodeResponse {
  id: number;
  access_code: string;
  access_code_version: number;
}

export interface ClosedServiceSessionResponse {
  id: number;
  resource_id: number;
  status: string;
  closed_at: string;
}

export interface ApiErrorBody {
  detail?: string | { code?: string; message?: string };
  error?: { code?: string; message?: string; state?: string };
  correlation_id?: string;
}
