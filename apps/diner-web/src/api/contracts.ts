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
