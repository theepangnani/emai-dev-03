export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  roles: string[];
  is_active: boolean;
  google_connected: boolean;
}
