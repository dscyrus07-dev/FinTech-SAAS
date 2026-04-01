export const CATEGORY_OPTIONS = [
  'Food & Dining', 'Travel & Transport', 'Utilities & Bills',
  'Salary & Income', 'EMI & Loan', 'Bank Transfer',
  'Investment', 'Tax & Government', 'Entertainment',
  'Healthcare', 'Shopping', 'Other'
];

export type LearningEventRecord = {
  sheet_title?: string;
  row_index?: number;
  description: string;
  category: string;
  confidence?: number;
  source?: string;
  bank_name?: string;
  account_type?: string;
  recurring_type?: string;
  pattern?: string;
  metadata?: Record<string, unknown>;
};

export type FormatStyle = {
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  color?: string;
  bg?: string;
  alignment?: { horizontal?: 'left' | 'center' | 'right' };
  fontSize?: number;
  numberFormat?: string;
  note?: string;
};

export type SheetData = {
  id: number;
  title: string;
  headers: string[];
  rows: string[][];
  styles: Record<string, FormatStyle>; // key: `${r}-${c}` (r=row index, c=col index)
  colWidths: Record<number, number>;
  frozenRows: number;
  flaggedRows: Record<number, boolean>;
  isDirty: boolean;
};

export type SelectionRange = {
  start: { r: number; c: number };
  end: { r: number; c: number };
};

export type HistoryEntry = {
  id: string;
  sheetId: number;
  description: string;
  previousState: any; // Simplified diff or previous sheet snapshot
  newState: any;
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
