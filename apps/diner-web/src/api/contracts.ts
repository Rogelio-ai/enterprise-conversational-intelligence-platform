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
