export interface User {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  email_verified: boolean;
}

export interface Chama {
  id: string;
  name: string;
  description: string;
  category: string;
  currency: string;
  location: string;
  visibility: "public" | "private";
  membership_type: "open" | "invitation";
  requires_approval: boolean;
  maximum_members: number;
}

export interface MyChama {
  id: string;
  chama: Chama;
  role: string;
  permissions: string[];
}

export interface ChamaDetail extends Chama {
  my_role: string;
  my_permissions: string[];
}

export interface Member {
  id: string;
  name: string;
  phone_number: string | null;
  role: string;
  role_id: number;
  status: string;
  joined_at: string | null;
  is_me: boolean;
}

export interface Role {
  id: number;
  role_name: string;
  description: string;
  permissions: string[];
  is_system_role: boolean;
}

export interface RuleVersion {
  id: number;
  category: string;
  version_number: number;
  status: string;
  configuration: Record<string, string | number | boolean>;
  previous_configuration: Record<string, string | number | boolean> | null;
  effective_from: string;
  reason: string;
  proposed_by: string;
  decided_by: string | null;
}

export interface RuleState {
  category: string;
  current: RuleVersion | null;
  upcoming: RuleVersion | null;
  pending: RuleVersion | null;
}

export interface ScheduleRow {
  id: number;
  member: string;
  membership_id: string;
  due_date: string;
  expected: string;
  paid: string;
  outstanding: string;
  status: string;
  rule_version: number;
}

export interface ContributionRow {
  id: string;
  member: string;
  amount: string;
  currency: string;
  method: string;
  reference: string;
  date: string;
}

export interface PaymentRow {
  id: string;
  amount: string;
  status: string;
  receipt: string | null;
  failure_reason: string;
  initiated_at: string;
  member: string;
  simulated?: boolean;
}

export interface Overview {
  chama: string;
  currency: string;
  my_savings: string;
  my_outstanding: string;
  my_overdue_periods: number;
  next_due: { date: string; amount: string } | null;
  group?: {
    members: number;
    members_overdue: number;
    accounts: { code: string; name: string; type: string; balance: string }[];
  };
}

export interface AuditEntry {
  id: string;
  actor: string;
  action: string;
  resource_type: string;
  details: Record<string, string>;
  created_at: string;
}
