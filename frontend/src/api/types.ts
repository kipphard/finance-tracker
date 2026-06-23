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
  expected_return: string;
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
  account_id: string | null;
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
  counterparty: string | null;
  invoice_number: string | null;
  vat_rate: string | null;
  deductible_pct: string | null;
  excluded: boolean;
  is_business: boolean;
  tags: string[];
  is_transfer: boolean;
  series_id: string | null;
}

export interface MonthlyCashflowPoint {
  month: string;
  inflow: string;
  outflow: string;
  net: string;
}

export interface CategoryTotal {
  name: string;
  kind: string | null;
  total: string;
  count: number;
}

export interface IncomeExpenseReport {
  start: string;
  end: string;
  income: string;
  expense: string;
  net: string;
  by_category: CategoryTotal[];
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

export interface ForecastSeriesOut {
  key: string;
  label: string;
  points: ForecastPointOut[];
}

export interface ForecastOut {
  base_currency: string;
  current_total: string;
  monthly_net: string;
  points: ForecastPointOut[];
  series: ForecastSeriesOut[];
}

export interface AttachmentOut {
  id: string;
  transaction_id: string;
  filename: string;
  content_type: string;
  size: number;
  created_at: string;
}

export interface DebtOut {
  id: string;
  name: string;
  amount: string;
  due_date: string | null;
  paid: boolean;
  created_at: string;
}

export interface EmergencyFundOut {
  target_months: number;
  target_amount: string | null;
  current_amount: string;
  monthly_fixed: string;
  target: string;
  gap: string;
  funded_pct: string;
  account_id: string | null;
  account_name: string | null;
  account_priority: number;
  shared_with: string | null;
  earmarked: boolean;
}

export interface TaxReserveOut {
  year: number;
  tariff_year: number;
  income_ytd: string;
  profit_ytd: string;
  owed_ytd: string;
  reserve: string;
  gap: string;
  surplus: string;
  funded_pct: string;
  effective_rate: string;
  projected_annual_owed: string;
  recommended_monthly: string;
  reserve_account_id: string | null;
  reserve_account_name: string | null;
  current_amount: string;
  has_account: boolean;
  account_priority: number;
  shared_with: string | null;
}

export interface TaxReserveUpdate {
  reserve_account_id?: string | null;
  current_amount?: string;
}

export interface AllocationBucketOut {
  id: string;
  name: string;
  percent: string;
  amount: string;
  account_id: string | null;
  earmarked: boolean;
}

export interface AllocationPlanOut {
  currency: string;
  monthly_income: string;
  monthly_fixed: string;
  leftover: string;
  allocated_percent: string;
  unallocated_percent: string;
  unallocated_amount: string;
  buckets: AllocationBucketOut[];
}

export interface PlannedPurchaseOut {
  id: string;
  name: string;
  price: string;
  monthly_save: string;
  created_at: string;
  months: number | null;
  target_month: string | null;
}

export interface PlannedPurchasesOut {
  currency: string;
  monthly_leftover: string;
  planned_fund: string;
  items: PlannedPurchaseOut[];
}

// ===== Freelance (time tracking + invoicing) =============================

export type InvoiceLanguage = "de" | "en";

export interface BusinessProfileOut {
  name: string;
  company_name: string;
  phone: string;
  email: string;
  address: string;
  postal_code: string;
  city: string;
  iban: string;
  bic: string;
  tax_number: string;
  is_kleinunternehmer: boolean;
  vat_note: string;
  intro_text: string;
  payment_terms_days: number;
  payment_info: string;
  default_language: InvoiceLanguage;
  digest_cadence: "off" | "weekly" | "monthly";
  digest_invoices: boolean;
  digest_time: boolean;
  digest_finance: boolean;
  default_hourly_rate: string;
  next_invoice_number: number;
}

export interface ProjectOut {
  id: string;
  client_id: string;
  name: string;
  hourly_rate: string | null;
  budget_hours: string | null;
  notes: string | null;
  archived: boolean;
  created_at: string;
  // computed
  effective_rate: string;
  tracked_hours: string;
  unbilled_hours: string;
  unbilled_amount: string;
}

export interface ClientOut {
  id: string;
  name: string;
  email: string | null;
  address: string;
  hourly_rate: string;
  budget_hours: string | null;
  notes: string | null;
  archived: boolean;
  created_at: string;
  // computed
  tracked_hours: string;
  unbilled_hours: string;
  unbilled_amount: string;
}

export interface TimeEntryOut {
  id: string;
  client_id: string;
  project_id: string | null;
  started_at: string;
  ended_at: string | null;
  minutes: number;
  description: string | null;
  invoice_id: string | null;
  created_at: string;
}

export interface InvoiceItemOut {
  id: string;
  description: string;
  hours: string;
  rate: string;
  amount: string;
  position: number;
}

export interface RecurringInvoiceOut {
  id: string;
  client_id: string;
  client_name: string | null;
  project_id: string | null;
  project_name: string | null;
  cadence: string;
  mode: string; // "flat" | "time"
  amount: string;
  description: string;
  language: InvoiceLanguage;
  next_run: string;
  active: boolean;
  created_at: string;
}

export interface InvoicePaymentOut {
  id: string;
  ts: string;
  amount: string;
  account_name: string | null;
  payee: string | null;
}

export interface InvoiceOut {
  id: string;
  client_id: string;
  client_name: string | null;
  project_id: string | null;
  project_name: string | null;
  number: string;
  issue_date: string;
  due_date: string | null;
  place: string;
  language: InvoiceLanguage;
  intro_text: string;
  status: string;
  overdue: boolean;
  reminder_level: number;
  last_reminder_at: string | null;
  vat_rate: string;
  total: string;
  paid_amount: string;
  created_at: string;
  items: InvoiceItemOut[];
  payments: InvoicePaymentOut[];
}

// ===== Analytics =========================================================

export interface RunwayOut {
  currency: string;
  liquid: string;
  monthly_net: string;
  runway_months: string | null;
  earmarked: string;
}

export interface ClientProfitOut {
  client_id: string;
  name: string;
  tracked_hours: string;
  billed_hours: string;
  unbilled_hours: string;
  invoiced_total: string;
  paid_total: string;
  effective_rate: string;
}

export interface ProjectBurnOut {
  project_id: string;
  name: string;
  client_name: string | null;
  budget_hours: string;
  tracked_hours: string;
  remaining_hours: string;
  pct: string;
  over_budget: boolean;
}

export interface FreelanceInsightsOut {
  clients: ClientProfitOut[];
  projects: ProjectBurnOut[];
}

// --- taxes: EÜR ---

export type BusinessType = "freiberufler" | "gewerbe";
export type HomeOfficeMode = "none" | "flat" | "room";

export interface TaxProfileOut {
  business_type: BusinessType;
  mixed_use_rates: Record<string, number>; // category_id -> percent
  km_rate: string;
  home_office_mode: HomeOfficeMode;
  room_use_pauschale: boolean;
  room_sqm: string | null;
  home_total_sqm: string | null;
  home_annual_cost: string;
}

export interface TaxYearInputOut {
  year: number;
  other_taxable_income: string;
  withheld_lohnsteuer: string;
  income_tax_prepaid: string;
  home_office_days: number;
  business_km: string;
  notes: string;
}

export interface ExpenseLineOut {
  key: "direct" | "mixed" | "home_office" | "travel";
  label: string;
  amount: string;
  gross: string | null;
  percent: string | null;
  count: number;
}

export interface TaxLineItemOut {
  date: string;
  payee: string;
  category: string | null;
  bucket: "income" | "direct" | "mixed";
  amount: string;
  deductible: string;
  percent: string | null;
  tags: string[];
}

export interface EurReportOut {
  year: number;
  business_type: BusinessType;
  is_kleinunternehmer: boolean;
  income: string;
  expense_total: string;
  profit: string;
  expense_lines: ExpenseLineOut[];
  line_items: TaxLineItemOut[];
  other_income: string;
  tariff_year: number;
  tax_with: string;
  tax_without: string;
  tax_estimate: string;
  withheld_lohnsteuer: string;
  income_tax_prepaid: string;
  refund_or_owed: string;
  home_office_mode: HomeOfficeMode;
  home_office_days: number;
  business_km: string;
  km_rate: string;
}

export interface ElsterPromptOut {
  year: number;
  prompt: string;
}
