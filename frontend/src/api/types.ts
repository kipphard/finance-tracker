// Mirrors the backend pydantic schemas. Decimals come over the wire as strings.

export interface UserOut {
  id: string;
  email: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

export interface AccountOut {
  id: string;
  connector: string;
  type: string;
  name: string;
  currency: string;
  institution: string | null;
  created_at: string;
  latest_balance: string | null;
}

export interface BreakdownItem {
  account_id: string;
  name: string;
  connector: string;
  currency: string;
  amount: string;
}

export interface NetWorthOut {
  base_currency: string;
  total: string;
  by_currency: Record<string, string>;
  breakdown: BreakdownItem[];
}

export interface SnapshotOut {
  id: string;
  ts: string;
  total: string;
  breakdown_json: Record<string, unknown>;
}

export interface CashflowSummaryOut {
  currency: string;
  monthly_inflow: string;
  monthly_outflow: string;
  monthly_net: string;
  item_count: number;
}

export type Cadence =
  | "one_off"
  | "weekly"
  | "biweekly"
  | "monthly"
  | "quarterly"
  | "yearly";

export interface CashflowItemOut {
  id: string;
  direction: "inflow" | "outflow";
  name: string;
  amount: string;
  cadence: Cadence;
  currency: string;
  category_id: string | null;
  next_due: string | null;
  active: boolean;
  created_at: string;
  monthly_amount: string | null;
}

export type CategoryKind = "income" | "expense";

export interface CategoryOut {
  id: string;
  name: string;
  kind: CategoryKind;
  is_fixed: boolean;
}

export interface TransactionOut {
  id: string;
  account_id: string;
  ts: string;
  amount: string;
  currency: string;
  raw_payee: string | null;
  description: string | null;
  category_id: string | null;
  is_recurring: boolean;
}

export interface RecurringOut {
  id: string;
  payee: string;
  amount_est: string;
  cadence: string;
  next_due: string | null;
  account_id: string;
}

export interface CategoryBreakdownItem {
  category_id: string | null;
  name: string;
  kind: CategoryKind | null;
  is_fixed: boolean | null;
  total: string;
  count: number;
}

export interface BudgetOut {
  id: string;
  category_id: string;
  monthly_limit: string;
  created_at: string;
}

export interface BudgetStatusOut {
  budget_id: string;
  category_id: string;
  category_name: string;
  monthly_limit: string;
  spent: string;
  remaining: string;
  pct_used: string;
  over: boolean;
  period: string;
}

export interface AlertOut {
  level: "danger" | "warning" | "info";
  kind: string;
  message: string;
}

export interface ForecastPointOut {
  month: string;
  projected: string;
}

export interface ForecastOut {
  base_currency: string;
  current_total: string;
  monthly_net: string;
  points: ForecastPointOut[];
}
