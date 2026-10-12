export type Role = "super_admin" | "admin" | "operator";
export type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  date_joined: string;
  last_login: string | null;
};
export type ServiceStatus = "scheduled" | "active" | "expiring" | "expired";
export type Customer = {
  id: number;
  name: string;
  manager_name: string;
  phone: string;
  identifier: string;
  start_date: string;
  expiration_date: string;
  status: ServiceStatus;
  days_remaining: number;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};
export type Audit = {
  id: number;
  actor: Pick<User, "id" | "username" | "first_name" | "last_name"> | null;
  action: string;
  entity_type: string;
  entity_id: number | string;
  description: string;
  changes: Record<string, unknown>;
  created_at: string;
};
export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
export type DashboardData = {
  metrics: {
    total_customers: number;
    active_services: number;
    expiring_services: number;
    expired_services: number;
    scheduled_services: number;
    active_administrators: number;
    expiring_7_days: number;
  };
  growth: { month: string; count: number }[];
  distribution: { status: ServiceStatus; count: number }[];
  upcoming_expirations: Customer[];
  recent_customers: Customer[];
  recent_activities: Audit[];
};
