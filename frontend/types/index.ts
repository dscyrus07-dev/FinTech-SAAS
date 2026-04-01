export type AccountType = 'salaried' | 'business'

export type BankName =
  | 'HDFC Bank'
  | 'ICICI Bank'
  | 'Axis Bank'
  | 'Kotak Bank'
  | 'HSBC Bank'
  | 'SBI'
  | 'Other'

export type ProcessingMode = 'free' | 'hybrid'

export interface UserDetails {
  fullName: string
  accountType: AccountType | ''
  bankName: BankName | ''
}

export interface CostEstimate {
  total_transactions: number
  ai_transactions: number
  remaining_as_others: number
  estimated_batches: number
  estimated_claude_calls: number
  estimated_cost_usd: number
  estimated_cost_inr: number
  max_ai_calls: number
  max_ai_transactions: number
  batch_size: number
  rule_engine_classified: number
  rule_engine_unclassified: number
}

export interface ProcessingResult {
  status: 'success' | 'error'
  mode: ProcessingMode
  excel_url: string
  pdf_url: string
  account_summary?: SheetPreview    // Sheet 1 — Summary
  monthly_analysis?: SheetPreview   // Sheet 2 — Monthly Analysis
  weekly_analysis?: SheetPreview    // Sheet 3 — Weekly Analysis
  category_analysis?: SheetPreview  // Sheet 4 — Category Analysis
  bounces_penal?: SheetPreview      // Sheet 5 — Bounces & Penal
  funds_received?: SheetPreview     // Sheet 6 — Funds Received
  funds_remittance?: SheetPreview   // Sheet 7 — Funds Remittance
  raw_transactions?: SheetPreview   // Sheet 8 — Raw Transaction
  source_analysis?: SheetPreview    // Sheet 9 — Source Analysis
  category_outcome?: SheetPreview   // Sheet 10 — Category Outcome
  stats?: {
    total_transactions: number
    rule_engine_classified: number
    ai_classified: number
    others: number
    coverage_percent: number
  }
  ai_usage?: {
    ai_calls: number
    ai_transactions_sent: number
    ai_transactions_classified: number
    estimated_cost_usd: number
    estimated_cost_inr: number
  } | null
}

export interface SheetPreview {
  title: string
  headers: string[]
  rows: string[][]
}

export interface SheetData {
  title: string
  headers: string[]
  rows: string[][]
}

export type SelectionRange = {
  start: { row: number; column: number };
  end: { row: number; column: number };
};

export type HistoryEntry = {
  type: 'insert' | 'delete' | 'update';
  data: any;
};

export type SpreadsheetState = {
  sheets: SheetData[];
  activeSheetId: number;
  selection: SelectionRange | null;
  history: HistoryEntry[];
  historyIndex: number; // For undo/redo
  globalDirty: boolean; // For "Save Changes" status
  showFlaggedOnly: boolean;
  filters: Record<number, Record<number, string>>; // sheetId -> columnId -> filter value
  filteredRows: Record<number, number[]>; // sheetId -> array of visible row indices
  editLog: LearningEventRecord[];
};

export interface LearningEventRecord {
  sheet_title?: string
  row_index?: number
  description: string
  category: string
  confidence?: number
  source?: string
  bank_name?: string
  account_type?: string
  recurring_type?: string
  pattern?: string
  metadata?: Record<string, unknown>
}

export type Step = 1 | 2 | 3 | 4 | 5

export interface AppState {
  step: Step
  userDetails: UserDetails
  file: File | null
  mode: ProcessingMode
  apiKey: string
  result: ProcessingResult | null
  error: string | null
}
