export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserMe {
  id: string;
  email: string;
  full_name: string;
  department_id: string | null;
  roles: string[];
  is_active: boolean;
}
