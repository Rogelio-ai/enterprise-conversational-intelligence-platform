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
