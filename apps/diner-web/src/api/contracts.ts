export interface DinerJoinRequest {
  join_context_key: string;
  display_name: string;
  email?: string;
  access_code: string;
}

export interface DinerJoinResponse {
  diner_session_id: number;
  service_session_id: number;
  conversation_id: number;
  display_name: string;
  customer_id: number | null;
  email?: string | null;
  access_token: string;
  token_type: 'bearer';
  expires_at: string;
  expires_in: number;
}

export interface DinerSessionResponse {
  id: number;
  service_session_id: number;
  resource_id: number;
  conversation_id: number;
  display_name: string;
  customer_id: number | null;
  email?: string | null;
  status: string;
  joined_at: string;
  ended_at: string | null;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    state?: string;
    next_action?: string;
  };
  correlation_id?: string;
}

export interface ExperienceResponse {
  state: string;
  code: string;
  required_input: string[];
  allowed_actions: string[];
  next_action: string | null;
}

export interface PriceResponse {
  amount: string;
  currency: string;
}

export interface CategoryResponse {
  id: number;
  name: string;
}

export interface ProductSummaryResponse {
  id: number;
  name: string;
  description: string | null;
  category_path: CategoryResponse[];
  price: PriceResponse | null;
  orderable: boolean;
  configuration_available: boolean;
  configuration_required: boolean;
}

export interface MenuSectionResponse {
  id: number;
  name: string;
  products: ProductSummaryResponse[];
}

export interface MenuResponse {
  id: number;
  name: string;
  sections: MenuSectionResponse[];
}

export interface DinerMenuResponse {
  menus: MenuResponse[];
  experience: ExperienceResponse;
}

export interface FixedComponentResponse {
  product_id: number;
  name: string;
  quantity: string;
}

export interface ChoiceOptionResponse {
  id: number;
  product_id: number;
  name: string;
  description: string | null;
  quantity: string;
}

export interface ChoiceGroupResponse {
  id: number;
  name: string;
  min_selections: number;
  max_selections: number;
  required: boolean;
  options: ChoiceOptionResponse[];
}

export interface ProductDetailResponse {
  product: ProductSummaryResponse;
  fixed_components: FixedComponentResponse[];
  choice_groups: ChoiceGroupResponse[];
  experience: ExperienceResponse;
}

export interface DraftIssueResponse {
  code: string;
  group_id: number | null;
  option_id: number | null;
  product_id: number | null;
}

export interface DraftSelectionResponse {
  group_id: number;
  group_name: string;
  choice_option_id: number;
  selected_product_id: number;
  selected_product_name: string;
}

export interface MissingChoiceGroupResponse {
  group_id: number;
  group_name: string;
  min_selections: number;
  max_selections: number;
  selected_option_ids: number[];
}

export interface DraftItemResponse {
  item_id: number;
  product_id: number;
  product_name: string;
  composition_id: number | null;
  quantity: string;
  position: number;
  readiness: 'INCOMPLETE' | 'INVALID' | 'READY';
  issues: DraftIssueResponse[];
  selections: DraftSelectionResponse[];
  missing_choice_groups: MissingChoiceGroupResponse[];
  fixed_components: Array<{
    product_id: number;
    product_name: string;
    quantity: string;
  }>;
}

export interface DraftResponse {
  draft_id: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  conversation_id: number;
  version: number;
  readiness: 'EMPTY' | 'INCOMPLETE' | 'INVALID' | 'READY';
  items: DraftItemResponse[];
}

export interface AddDraftItemRequest {
  product_id: number;
  quantity: string;
  expected_version: number;
}

export interface ReplaceDraftGroupSelectionsRequest {
  option_ids: number[];
  expected_version: number;
}

export interface SetDraftItemQuantityRequest {
  quantity: string;
  expected_version: number;
}

export interface AppliedPromotionResponse {
  promotion_id: number;
  name: string;
  promotion_type: string;
  promotion_value: string;
  currency: string | null;
  priority: number;
  is_combinable: boolean;
  calculated_discount: string;
}

export interface CheckoutPreviewLineResponse {
  draft_item_id: number;
  product_id: number;
  product_name: string;
  composition_id: number | null;
  quantity: string;
  price_id: number;
  price_source: string;
  unit_price: string;
  base_amount: string;
  applied_promotions: AppliedPromotionResponse[];
  discount_amount: string;
  commercial_amount: string;
}

export interface CheckoutPreviewResponse {
  status: string;
  draft_id: number;
  draft_version: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  resolved_at: string;
  currency: string;
  tax_mode: string;
  rounding_policy: string;
  fingerprint_schema_version: number;
  lines: CheckoutPreviewLineResponse[];
  subtotal: string;
  total_discount: string;
  pre_round_total: string;
  rounding_adjustment: string;
  payable_total: string;
  commercial_fingerprint: string;
}

export interface ConfirmOrderRequest {
  expected_draft_version: number;
  expected_commercial_fingerprint: string;
}

export interface OrderComponentResponse {
  kind: string;
  position: number;
  source_component_id: number | null;
  source_choice_group_id: number | null;
  source_choice_option_id: number | null;
  choice_group_name: string | null;
  product_id: number;
  product_name: string;
  quantity: string;
}

export interface OrderPromotionResponse {
  promotion_id: number;
  application_order: number;
  promotion_name: string;
  promotion_type: string;
  promotion_value: string;
  promotion_currency: string | null;
  priority: number;
  is_combinable: boolean;
  calculated_discount: string;
}

export interface RestaurantOrderItemResponse {
  id: number;
  source_order_draft_item_id: number;
  product_id: number;
  product_name: string;
  composition_id: number | null;
  quantity: string;
  position: number;
  source_product_price_id: number;
  price_source: string;
  unit_price: string;
  base_amount: string;
  discount_amount: string;
  commercial_amount: string;
  components: OrderComponentResponse[];
  promotions: OrderPromotionResponse[];
}

export interface RestaurantOrderResponse {
  id: number;
  status: string;
  accepted_at: string;
  source_order_draft_id: number;
  accepted_draft_version: number;
  currency: string;
  tax_mode: string;
  rounding_policy: string;
  subtotal: string;
  total_discount: string;
  pre_round_total: string;
  rounding_adjustment: string;
  payable_total: string;
  items: RestaurantOrderItemResponse[];
}

export interface AccountPreviewLineResponse {
  order_id: number;
  order_item_id: number;
  product_id: number;
  product_name: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  commercial_amount: string;
}

export interface AccountPreviewResponse {
  diner_session_id: number;
  display_name: string;
  currency: string | null;
  eligible_order_ids: number[];
  lines: AccountPreviewLineResponse[];
  eligible_total: string;
  active_check_id: number | null;
  has_active_nonempty_draft: boolean;
  experience: ExperienceResponse;
}

export interface EligibleConsumptionResponse {
  diner_session_id: number;
  service_session_id: number;
  resource_id: number;
  display_name: string;
  eligible_order_ids: number[];
  eligible_total: string;
  currency: string | null;
  active_check_id: number | null;
  has_active_nonempty_draft: boolean;
}

export type CheckCreateMode = 'INDIVIDUAL' | 'GLOBAL_TABLE' | 'SELECTED';

export interface CheckCreateRequest {
  mode: CheckCreateMode;
  diner_session_ids?: number[];
}

export interface CheckItemResponse {
  item_id: number;
  product_id: number;
  product_name: string;
  quantity: string;
  commercial_amount: string;
}

export interface CheckOrderResponse {
  order_id: number;
  diner_session_id: number;
  service_session_id: number;
  resource_id: number;
  accepted_at: string;
  accepted_payable_amount: string;
  accepted_commercial_fingerprint: string;
  items: CheckItemResponse[];
}

export interface CheckDinerResponse {
  diner_session_id: number;
  display_name: string;
  orders: CheckOrderResponse[];
}

export interface CheckResourceResponse {
  resource_id: number;
  service_session_id: number;
  diners: CheckDinerResponse[];
}

export interface RestaurantCheckResponse {
  id: number;
  tenant_id: number;
  organization_id: number;
  location_id: number;
  status: string;
  version: number;
  fingerprint: string;
  currency: string;
  controller_diner_session_id: number | null;
  member_ids: number[];
  diner_scope_ids: number[];
  table_scope_session_ids: number[];
  consumption_total: string;
  gratuity_total: string;
  liability_total: string;
  confirmed_settlement: string;
  outstanding: string;
  uncertain_exposure: string;
  frozen_at: string | null;
  settled_at: string | null;
  continuation_decision: string;
  cancelled_at: string | null;
  details: CheckResourceResponse[] | null;
  signal: string | null;
}

export interface AvailablePaymentExecutorResponse {
  executor_key: string;
  display_name: string;
  topology: string;
  method_category: string;
  currency: string;
}

export interface PaymentExecutorClientConfigurationResponse {
  provider: string;
  tokenization_mode: string;
  public_key: string;
  locale: string;
}
