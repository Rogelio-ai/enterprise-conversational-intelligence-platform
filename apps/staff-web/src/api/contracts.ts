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

export type PreparationState = 'NEW' | 'IN_PROGRESS' | 'COMPLETED';

export interface PreparationArea {
  id: number;
  location_id: number;
  code: string;
  name: string;
  status: 'ACTIVE' | 'INACTIVE';
}

export interface PreparationAreaListResponse {
  items: PreparationArea[];
}

export interface PreparationOrderContext {
  restaurant_order_id: number;
  accepted_at: string;
  source_channel: string;
  resource_id: number;
  service_session_id: number;
  diner_session_id: number;
  current_resource_code: string | null;
  current_resource_name: string | null;
}

export interface PreparationWorkItem {
  id: number;
  preparation_work_id: number;
  source_type: string;
  source_restaurant_order_item_id: number | null;
  source_restaurant_order_item_component_id: number | null;
  product_name: string;
  parent_product_name: string | null;
  required_quantity: string;
  execution_state: PreparationState;
  execution_version: number;
}

export interface PreparationWork {
  id: number;
  preparation_area_id: number;
  area_code: string;
  area_name: string;
  routed_at: string;
  execution_state: PreparationState;
  order: PreparationOrderContext;
  items: PreparationWorkItem[];
}

export interface PreparationTransitionResult {
  current_execution_state: PreparationState;
  current_execution_version: number;
  replayed: boolean;
}

export interface PreparationDispatch {
  id: number;
  location_id: number;
  preparation_work_id: number;
  destination_id: number;
  operation_kind: 'INITIAL' | 'REPRINT';
  generation: number;
  state: string;
  destination_name: string;
  destination_channel: string;
  attempt_count: number;
  last_error_kind: string | null;
  last_error_message: string | null;
  created_at: string;
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

export interface CashSession {
  id: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  resource_id: number;
  cashier_membership_id: number;
  currency: string;
  status: 'OPEN' | 'CLOSED';
  movement_version: number;
  expected_cash: string;
  opened_at: string;
  selected_cash_count_id: number | null;
  final_movement_version: number | null;
  frozen_expected_cash: string | null;
  frozen_variance: string | null;
  variance_reason: string | null;
  closed_at: string | null;
}

export interface CashMovement {
  id: number;
  cash_session_id: number;
  movement_type: string;
  amount: string;
  currency: string;
  reason: string | null;
  reference: string | null;
  recorded_at: string;
}

export interface CashCount {
  id: number;
  cash_session_id: number;
  counted_amount: string;
  currency: string;
  captured_movement_version: number;
  counted_at: string;
}

export interface RestaurantCheckSummary {
  id: number;
  organization_id: number;
  location_id: number;
  resource_ids: number[];
  table_scope_session_ids: number[];
  status: string;
  version: number;
  fingerprint: string;
  currency: string;
  liability_total: string;
  confirmed_settlement: string;
  reserved_financial_exposure: string;
  uncertain_exposure: string;
  outstanding: string;
  available_to_initiate: string;
  created_at: string;
}

export interface RestaurantCheckListResponse {
  items: RestaurantCheckSummary[];
  limit: number;
  offset: number;
}

export interface RestaurantCheckDetail extends RestaurantCheckSummary {
  tenant_id: number;
  controller_diner_session_id: number | null;
  member_ids: number[];
  diner_scope_ids: number[];
  consumption_total: string;
  gratuity_total: string;
  continuation_decision: string;
  details: unknown;
  signal: string | null;
}

export interface RestaurantPayment {
  id: number;
  check_id: number;
  check_version: number;
  check_fingerprint: string;
  amount: string;
  currency: string;
  method_category: 'CASH' | 'CARD' | 'TRANSFER';
  payer_type: string;
  payer_diner_session_id: number | null;
  payer_reference: string | null;
  state: string;
  executor_key: string | null;
  external_reference: string | null;
  external_status: string | null;
  instrument_display: string | null;
  cash_tendered_amount: string | null;
  cash_change_due: string | null;
  terminal_at: string | null;
}

export interface CheckSettlement {
  check_id: number;
  check_status: string;
  check_version: number;
  check_fingerprint: string;
  liability_total: string;
  currency: string;
  confirmed_settlement: string;
  reserved_financial_exposure: string;
  uncertain_exposure: string;
  available_to_initiate: string;
  payments: RestaurantPayment[];
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
