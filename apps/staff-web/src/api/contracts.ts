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
  authorized_location_ids: number[];
  roles: string[];
  permissions: string[];
}

export type OperationalRequestStatus = 'PENDING' | 'ACKNOWLEDGED' | 'COMPLETED' | 'CANCELLED';
export type OperationalRequestType =
  | 'HUMAN_ASSISTANCE'
  | 'CASH_PAYMENT_ASSISTANCE'
  | 'INVOICE_ASSISTANCE'
  | 'PAID_CHECK_PRINT';

export interface StaffOperationalRequest {
  id: number;
  organization_id: number;
  location_id: number;
  resource_id: number;
  resource_code: string;
  resource_name: string;
  service_session_id: number;
  diner_session_id: number;
  diner_display_name: string;
  request_type: OperationalRequestType;
  status: OperationalRequestStatus;
  related_restaurant_check_id: number | null;
  resolved_by_membership_id: number | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StaffOperationalRequestListResponse {
  items: StaffOperationalRequest[];
  limit: number;
  offset: number;
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
