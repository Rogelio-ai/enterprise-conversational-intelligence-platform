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

export interface InventoryWarehouse { id: number; code: string; name: string; negative_stock_policy: 'ALLOW' | 'WARN' | 'BLOCK'; is_default: boolean }
export interface PurchaseCostProjection {
  evidence_status: string; last_purchase_cost: string | null; recent_weighted_purchase_cost: string | null;
  currency: string | null; selected_window_days: number | null; accepted_receipt_events: number;
  last_vs_standard_absolute: string | null; last_vs_standard_percentage: string | null;
  weighted_vs_standard_absolute: string | null; weighted_vs_standard_percentage: string | null; source: string;
}
export interface InventoryStockRow {
  inventory_item_id: number; code: string; name: string; warehouse_id: number; warehouse_name: string;
  base_uom: string; quantity: string; negative_stock_policy: string; attention: string[];
  last_material_activity_at: string | null; standard_unit_cost: string | null; cost_currency: string | null;
  inventory_value_at_standard_cost: string | null; purchase_cost: PurchaseCostProjection | null;
  stock_source: string; valuation_source: string | null;
}
export interface InventoryActivity {
  id: number; warehouse_id: number; inventory_item_id?: number | null; label: string; status: string;
  occurred_at: string; quantity?: string | null; value?: string | null; currency?: string | null;
  evidence_status?: string | null; source: string;
}
export interface InventoryReconciliation {
  id: number; warehouse_id: number; inventory_item_id: number; physical_count_id: number; status: 'OPEN' | 'CLOSED'; version: number;
  period_start: string; period_end: string; opening_quantity: string | null; receipts: string | null;
  theoretical_consumption: string | null; registered_losses: string | null; other_adjustments: string | null;
  physical_count: string | null; count_adjustment: string | null; closing_quantity: string | null;
  unexplained_variance: string | null; variance_percentage: string | null; variance_value: string | null;
  currency: string | null; evidence_status: string | null; source: string;
}
export interface InventoryIntelligence {
  location_id: number; generated_at: string; cost_visible: boolean; active_warehouse_count: number;
  active_inventory_item_count: number; stock_position_count: number; negative_stock_count: number;
  counts_requiring_action: number; reconciliations_requiring_action: number; warehouses: InventoryWarehouse[];
  stock: InventoryStockRow[]; recent_receipts: InventoryActivity[]; recent_losses: InventoryActivity[];
  recent_counts: InventoryActivity[]; reconciliations: InventoryReconciliation[]; sources: Record<string, string>;
  limit: number; offset: number;
}
export interface InventorySupplier { id: number; code: string; name: string; status: string; location_ids: number[] }
export interface InventoryOffering { id: number; supplier_id: number; location_id: number; inventory_item_id: number; purchase_uom: string; status: string }
export interface GoodsReceiptLine { id: number; inventory_item_id: number; purchase_order_line_id: number | null; accepted_quantity: string; rejected_quantity: string; received_quantity: string; source_uom: string; unit_cost: string; currency: string; evidence_status: string; stock_movement_id: number | null }
export interface GoodsReceipt { id: number; location_id: number; warehouse_id: number; supplier_id: number; purchase_order_id: number | null; external_reference: string | null; status: 'DRAFT' | 'ACCEPTED' | 'CANCELLED'; version: number; accepted_at: string | null; lines: GoodsReceiptLine[] }
export interface PurchaseOrderReceiptAllocation { goods_receipt_id: number; status: GoodsReceipt['status']; accepted_at: string | null; accepted_quantity: string; rejected_quantity: string; unit_cost?: string; currency?: string }
export interface PurchaseOrderLine { id: number; supplier_offering_id: number; inventory_item_id: number; line_number: number; ordered_quantity: string; source_uom: string; accepted_quantity: string; rejected_quantity: string; remaining_quantity: string; normalized_ordered_quantity: string; base_uom_evidence: string; conversion_factor: string; receipt_allocations: PurchaseOrderReceiptAllocation[]; agreed_unit_price?: string; currency?: string; received_unit_price?: string | null; price_variance?: string | null; price_variance_percentage?: string | null }
export interface PurchaseOrder { id: number; location_id: number; warehouse_id: number; supplier_id: number; status: 'DRAFT'|'SUBMITTED'|'APPROVED'|'PARTIALLY_RECEIVED'|'RECEIVED'|'CLOSED'|'CANCELLED'; currency: string | null; cost_visible: boolean; expected_delivery_at: string | null; external_reference: string | null; notes: string | null; version: number; submitted_at: string | null; approved_at: string | null; terminated_at: string | null; receipts: Array<{ id: number; status: GoodsReceipt['status']; accepted_at: string | null }>; lines: PurchaseOrderLine[] }
export interface InventoryLoss {
  id: number; warehouse_id: number; inventory_item_id: number; category: string; source_quantity: string; source_uom: string;
  normalized_quantity: string | null; evidence_status: string; cost_visible: boolean; extended_loss_cost: string | null;
  cost_currency_evidence: string | null; reason: string | null; occurred_at: string; status: 'DRAFT' | 'PENDING_APPROVAL' | 'POSTED' | 'CANCELLED' | 'REVERSED';
  version: number; approval_required: boolean; approval_reason: string | null; stock_movement_id: number | null; reversal_stock_movement_id: number | null;
}
export interface PhysicalCountLine { id: number; inventory_item_id: number; expected_quantity_at_cursor: string; source_quantity: string; source_uom: string; normalized_counted_quantity: string; variance_quantity: string; variance_value: string | null; evidence_status: string; version: number; adjustment_stock_movement_id: number | null }
export interface PhysicalCount { id: number; warehouse_id: number; count_scope: 'PARTIAL' | 'FULL'; status: 'DRAFT' | 'COUNTING' | 'SUBMITTED' | 'APPROVED' | 'POSTED' | 'CANCELLED'; opened_at: string; cursor_at: string; cursor_movement_id: number; reason: string | null; reference: string | null; version: number; lines: PhysicalCountLine[] }

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

export interface FiscalProfileBase {
  legal_name: string;
  tax_identifier: string;
  tax_regime: string;
  fiscal_postal_code: string;
}

export interface IssuerFiscalProfile extends FiscalProfileBase {
  id: number;
  organization_id: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface RecipientFiscalProfile extends FiscalProfileBase {
  id: number;
  customer_id: number;
  invoice_usage: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BillingFiscalContext {
  check_id: number;
  organization_id: number;
  location_id: number;
  check_status: string;
  customer_id: number;
  customer_display_name: string | null;
  customer_email: string | null;
  issuer_profiles: IssuerFiscalProfile[];
  recipient_profile: RecipientFiscalProfile | null;
}

export interface BillingDocument {
  id: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  restaurant_check_id: number;
  source_check_version: number;
  source_check_fingerprint: string;
  document_type: string;
  status: string;
  currency: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  issuer_snapshot: Record<string, string>;
  recipient_snapshot: Record<string, string>;
  issuer_fiscal_postal_code: string | null;
  readiness_evidence_fingerprint: string | null;
  created_at: string;
  updated_at: string;
}

export interface FiscalIssuance {
  id: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  billing_document_id: number;
  provider_key: string;
  state: 'PENDING' | 'IN_PROGRESS' | 'SUCCEEDED' | 'FAILED' | 'REJECTED' | 'UNCERTAIN';
  external_reference: string | null;
  external_status: string | null;
  attempt_count: number;
  requested_at: string;
  completed_at: string | null;
}

export interface PreparationConnector {
  id: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  code: string;
  name: string;
  status: string;
}

export interface PaidCheckAttempt {
  id: number;
  attempt_sequence: number;
  attempt_type: string;
  connector_id: number;
  started_at: string;
  ended_at: string | null;
  result: string;
  local_job_reference: string | null;
  error_kind: string | null;
  error_message: string | null;
}

export interface PaidCheckDispatch {
  id: number;
  restaurant_check_id: number;
  check_version: number;
  check_fingerprint: string;
  cashier_resource_id: number;
  cashier_resource_code: string;
  cashier_resource_name: string;
  connector_id: number;
  connector_code: string;
  connector_name: string;
  local_target_key: string;
  operation_id: string;
  state: 'PENDING' | 'IN_PROGRESS' | 'DESTINATION_SUBMISSION_ACCEPTED' | 'RETRYABLE_FAILURE' | 'UNCERTAIN' | 'ACTION_REQUIRED';
  attempt_count: number;
  available_at: string;
  last_error_kind: string | null;
  last_error_message: string | null;
  terminal_at: string | null;
  created_at: string;
  updated_at: string;
  attempts: PaidCheckAttempt[];
}

export interface ManagerServiceSession {
  id: number;
  resource_id: number;
  resource_code: string;
  resource_name: string;
  party_size: number;
  active_diner_count: number;
  opened_at: string;
}

export interface ManagerCheckException {
  id: number;
  status: string;
  currency: string;
  liability_total: string;
  confirmed_settlement: string;
  outstanding: string;
  reserved_exposure: string;
  uncertain_exposure: string;
}

export interface ManagerPaymentException {
  id: number;
  check_id: number;
  amount: string;
  currency: string;
  method_category: string;
  state: string;
  created_at: string;
}

export interface ManagerCashSession {
  id: number;
  resource_id: number;
  status: string;
  currency: string;
  expected_cash: string;
  frozen_variance: string | null;
  opened_at: string;
}

export interface ManagerDispatchException {
  id: number;
  reference_id: number;
  state: string;
  destination_name: string;
  attempt_count: number;
  last_error_kind: string | null;
  created_at: string;
}

export interface ManagerFiscalException {
  id: number;
  billing_document_id: number;
  provider_key: string;
  state: string;
  attempt_count: number;
  requested_at: string;
}

export interface ManagerOperationalOverview {
  location_id: number;
  generated_at: string;
  active_table_count: number;
  available_table_count: number;
  active_service_session_count: number;
  active_diner_count: number;
  service_sessions: ManagerServiceSession[];
  request_counts_by_status: Record<string, number>;
  request_counts_by_type: Record<string, number>;
  preparation_item_counts: Record<string, number>;
  preparation_dispatch_counts: Record<string, number>;
  preparation_dispatch_exceptions: ManagerDispatchException[];
  check_counts_by_status: Record<string, number>;
  checks_with_outstanding_count: number;
  check_exceptions: ManagerCheckException[];
  uncertain_payments: ManagerPaymentException[];
  cash_session_counts: Record<string, number>;
  cash_session_exceptions: ManagerCashSession[];
  fiscal_issuance_counts: Record<string, number>;
  fiscal_exceptions: ManagerFiscalException[];
  paid_print_counts: Record<string, number>;
  paid_print_exceptions: ManagerDispatchException[];
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
