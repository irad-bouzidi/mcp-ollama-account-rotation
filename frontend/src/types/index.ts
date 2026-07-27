export interface Provider {
  id: string;
  name: string;
  display_name: string | null;
  base_url: string | null;
  account_count: number;
  active_accounts: number;
  depleted_accounts: number;
  created_at: string;
}

export interface Account {
  id: string;
  provider_id: string;
  email: string | null;
  is_active: boolean;
  is_depleted: boolean;
  credits_remaining: number | null;
  last_error: string | null;
  requests_count: number;
  rate_limit_reset: string | null;
  created_at: string;
}

export interface ProviderStatus {
  id: string;
  name: string;
  display_name: string | null;
  total_accounts: number;
  active_accounts: number;
  depleted_accounts: number;
  has_available: boolean;
  current_active_account: Account | null;
}

export interface SystemStatus {
  providers: ProviderStatus[];
  any_available: boolean;
  depleted_providers: string[];
}

export interface ProviderCreate {
  name: string;
  display_name?: string | null;
  base_url?: string | null;
}

export interface ProviderUpdate {
  name?: string;
  display_name?: string | null;
  base_url?: string | null;
}

export interface AccountCreate {
  provider_id: string;
  email: string;
  api_token?: string;
}

export interface AccountUpdate {
  email?: string;
  api_token?: string;
  is_active?: boolean;
}
