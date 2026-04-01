'use client'

import React, { createContext, useReducer, useContext, PropsWithChildren } from 'react';
import { SheetData, SpreadsheetState, SelectionRange, CATEGORY_OPTIONS, HistoryEntry, FormatStyle, LearningEventRecord } from './types';

export type Action =
  | { type: 'INIT'; payload: SheetData[] }
  | { type: 'SET_ACTIVE_SHEET'; payload: number }
  | { type: 'SET_SELECTION'; payload: SelectionRange | null }
  | { type: 'SET_CELL_DATA'; payload: { r: number; c: number; val: string; sheetId?: number } }
  | { type: 'SET_CELL_STYLE'; payload: { r: number; c: number; style: Partial<FormatStyle>; sheetId?: number } }
  | { type: 'SET_CELL_NOTE'; payload: { r: number; c: number; note: string; sheetId?: number } }
  | { type: 'TOGGLE_FLAG'; payload: { r: number; sheetId?: number } }
  | { type: 'SET_COL_WIDTH'; payload: { c: number; width: number; sheetId?: number } }
  | { type: 'BULK_UPDATE_CATEGORY'; payload: { category: string; sheetId?: number; colIndex: number } }
  | { type: 'UNDO' }
  | { type: 'REDO' }
  | { type: 'TOGGLE_FLAGGED_ONLY' }
  | { type: 'MARK_CLEAN' }
  | { type: 'REVERT_HISTORY'; payload: HistoryEntry }
  | { type: 'SET_CLIPBOARD'; payload: { data: string[][] } }
  | { type: 'INSERT_ROW'; payload: { index: number; data: string[]; sheetId?: number } }
  | { type: 'DELETE_ROW'; payload: { index: number; sheetId?: number } }
  | { type: 'MOVE_ROW'; payload: { from: number; to: number; sheetId?: number } }
  | { type: 'INSERT_COLUMN'; payload: { index: number; name: string; sheetId?: number } }
  | { type: 'DELETE_COLUMN'; payload: { index: number; sheetId?: number } }
  | { type: 'RENAME_COLUMN'; payload: { index: number; name: string; sheetId?: number } }
  | { type: 'FREEZE_TOP_ROW'; payload: { sheetId?: number } }
  | { type: 'UNFREEZE_ROWS'; payload: { sheetId?: number } }
  | { type: 'SET_FILTER'; payload: { sheetId?: number; columnId: number; value: string } }
  | { type: 'CLEAR_FILTER'; payload: { sheetId?: number; columnId?: number } }
  | { type: 'APPLY_FILTERS'; payload: { sheetId?: number } }
  | { type: 'APPEND_EDIT_LOG'; payload: LearningEventRecord }
  | { type: 'APPLY_TO_SIMILAR'; payload: { sheetId?: number; rowIndex: number; colIndex: number; value: string; descriptionColIndex?: number } };

const initialState: SpreadsheetState = {
  sheets: [],
  activeSheetId: 0,
  selection: null,
  history: [],
  historyIndex: -1,
  globalDirty: false,
  showFlaggedOnly: false,
  filters: {},
  filteredRows: {},
  editLog: [],
};

function cloneSheet(sheet: SheetData): SheetData {
  return {
    ...sheet,
    rows: sheet.rows.map(r => [...r]),
    styles: { ...sheet.styles },
    colWidths: { ...sheet.colWidths },
    flaggedRows: { ...sheet.flaggedRows },
  };
}

function pushHistory(state: SpreadsheetState, newSheets: SheetData[], description: string, sheetId: number): SpreadsheetState {
  // Discard future history if we are in the middle of undoing
  const history = state.history.slice(0, state.historyIndex + 1);
  const prevStateSnapshot = cloneSheet(state.sheets[sheetId]);
  const newEntry: HistoryEntry = {
    id: Date.now().toString() + Math.random(),
    sheetId,
    description,
    previousState: prevStateSnapshot,
    newState: cloneSheet(newSheets[sheetId]),
  };

  history.push(newEntry);
  return {
    ...state,
    sheets: newSheets,
    history,
    historyIndex: history.length - 1,
    globalDirty: true,
  };
}

function reducer(state: SpreadsheetState, action: Action): SpreadsheetState {
  switch (action.type) {
    case 'INIT':
      return { ...initialState, sheets: action.payload };

    case 'SET_ACTIVE_SHEET':
      return { ...state, activeSheetId: action.payload, selection: null };

    case 'SET_SELECTION':
      return { ...state, selection: action.payload };

    case 'TOGGLE_FLAGGED_ONLY':
      return { ...state, showFlaggedOnly: !state.showFlaggedOnly };

    case 'MARK_CLEAN':
      return { ...state, globalDirty: false, sheets: state.sheets.map(s => ({ ...s, isDirty: false })), editLog: [] };

    case 'SET_CELL_DATA': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      const oldVal = newSheet.rows[action.payload.r]?.[action.payload.c] || '';
      if (oldVal === action.payload.val) return state; // No change

      newSheet.rows[action.payload.r][action.payload.c] = action.payload.val;
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      const colName = newSheet.headers[action.payload.c] || `Col ${action.payload.c + 1}`;
      const normalizedHeader = (newSheet.headers[action.payload.c] || '').toLowerCase();
      const isCategoryChange = normalizedHeader === 'category';
      const description = newSheet.rows[action.payload.r]?.[newSheet.headers.findIndex(h => h.toLowerCase() === 'description')] || oldVal;

      const nextState = pushHistory(state, newSheets, `Row ${action.payload.r + 1}, ${colName}: "${oldVal}" → "${action.payload.val}"`, sId);
      if (!isCategoryChange) return nextState;

      const newEdit: LearningEventRecord = {
        sheet_title: newSheet.title,
        row_index: action.payload.r,
        description: String(description || ''),
        category: String(action.payload.val || ''),
        confidence: 1,
        source: 'user',
        metadata: {
          column: colName,
          previous_value: oldVal,
          new_value: action.payload.val,
        },
      };

      return { ...nextState, editLog: [...nextState.editLog, newEdit] };
    }

    case 'SET_CELL_STYLE': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      const key = `${action.payload.r}-${action.payload.c}`;
      newSheet.styles[key] = { ...(newSheet.styles[key] || {}), ...action.payload.style };
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Format changed at Row ${action.payload.r + 1}`, sId);
    }

    case 'SET_CELL_NOTE': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      const key = `${action.payload.r}-${action.payload.c}`;
      newSheet.styles[key] = { ...(newSheet.styles[key] || {}), note: action.payload.note };
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      const actionDesc = action.payload.note ? `Note added at Row ${action.payload.r + 1}` : `Note removed at Row ${action.payload.r + 1}`;
      return pushHistory(state, newSheets, actionDesc, sId);
    }

    case 'TOGGLE_FLAG': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      const isFlagged = !newSheet.flaggedRows[action.payload.r];
      if (isFlagged) {
        newSheet.flaggedRows[action.payload.r] = true;
      } else {
        delete newSheet.flaggedRows[action.payload.r];
      }
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `${isFlagged ? 'Flagged' : 'Unflagged'} Row ${action.payload.r + 1}`, sId);
    }

    case 'SET_COL_WIDTH': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;
      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      newSheet.colWidths[action.payload.c] = action.payload.width;
      newSheets[sId] = newSheet;
      // Col width drag doesn't need to bloat history, just state update
      return { ...state, sheets: newSheets }; 
    }

    case 'BULK_UPDATE_CATEGORY': {
      if (!state.selection) return state;
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      const rMin = Math.min(state.selection.start.r, state.selection.end.r);
      const rMax = Math.max(state.selection.start.r, state.selection.end.r);
      
      for (let r = rMin; r <= rMax; r++) {
         if (newSheet.rows[r]) {
            newSheet.rows[r][action.payload.colIndex] = action.payload.category;
         }
      }
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      const nextState = pushHistory(state, newSheets, `Bulk edit Category for ${rMax - rMin + 1} rows to "${action.payload.category}"`, sId);
      const descriptionIndex = newSheet.headers.findIndex(h => h.toLowerCase() === 'description');
      const newEvents: LearningEventRecord[] = [];
      for (let r = rMin; r <= rMax; r++) {
        if (!newSheet.rows[r]) continue;
        newEvents.push({
          sheet_title: newSheet.title,
          row_index: r,
          description: String(descriptionIndex >= 0 ? newSheet.rows[r][descriptionIndex] || '' : ''),
          category: String(action.payload.category || ''),
          confidence: 1,
          source: 'user_bulk_update',
          metadata: {
            selected_range: `${rMin}-${rMax}`,
            column_index: action.payload.colIndex,
          },
        });
      }

      return { ...nextState, editLog: [...nextState.editLog, ...newEvents] };
    }

    case 'UNDO': {
      if (state.historyIndex < 0) return state;
      const entry = state.history[state.historyIndex];
      const newSheets = [...state.sheets];
      newSheets[entry.sheetId] = cloneSheet(entry.previousState);
      return {
        ...state,
        sheets: newSheets,
        historyIndex: state.historyIndex - 1,
        globalDirty: true, // Still dirty because it deviates from standard saved point (unless we track exact save pointer, simple true is safer)
      };
    }

    case 'REDO': {
      if (state.historyIndex >= state.history.length - 1) return state;
      const entry = state.history[state.historyIndex + 1];
      const newSheets = [...state.sheets];
      newSheets[entry.sheetId] = cloneSheet(entry.newState);
      return {
        ...state,
        sheets: newSheets,
        historyIndex: state.historyIndex + 1,
        globalDirty: true,
      };
    }

    case 'REVERT_HISTORY': {
      // Find the entry and apply its previous state
      const entryIdx = state.history.findIndex(h => h.id === action.payload.id);
      if (entryIdx === -1) return state;
      
      const entry = state.history[entryIdx];
      const newSheets = [...state.sheets];
      newSheets[entry.sheetId] = cloneSheet(entry.previousState);
      
      // We don't splice history so user can see it's reverted, or we just push a new Revert action
      return pushHistory(state, newSheets, `Reverted: ${entry.description}`, entry.sheetId);
    }

    case 'SET_CLIPBOARD': {
      // Clipboard is handled at component level, no state change needed
      return state;
    }

    case 'INSERT_ROW': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      newSheet.rows.splice(action.payload.index, 0, action.payload.data);
      
      // Update flagged rows indices
      const newFlaggedRows: Record<number, boolean> = {};
      Object.entries(newSheet.flaggedRows).forEach(([idx, flagged]) => {
        const numIdx = parseInt(idx);
        if (numIdx >= action.payload.index) {
          newFlaggedRows[numIdx + 1] = flagged;
        } else {
          newFlaggedRows[numIdx] = flagged;
        }
      });
      newSheet.flaggedRows = newFlaggedRows;
      
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Inserted row at position ${action.payload.index + 1}`, sId);
    }

    case 'DELETE_ROW': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet || action.payload.index >= sheet.rows.length) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      const deletedRow = newSheet.rows[action.payload.index];
      newSheet.rows.splice(action.payload.index, 1);
      
      // Update flagged rows indices
      const newFlaggedRows: Record<number, boolean> = {};
      Object.entries(newSheet.flaggedRows).forEach(([idx, flagged]) => {
        const numIdx = parseInt(idx);
        if (numIdx < action.payload.index) {
          newFlaggedRows[numIdx] = flagged;
        } else if (numIdx > action.payload.index) {
          newFlaggedRows[numIdx - 1] = flagged;
        }
      });
      newSheet.flaggedRows = newFlaggedRows;
      
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Deleted row ${action.payload.index + 1}`, sId);
    }

    case 'MOVE_ROW': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet || 
          action.payload.from >= sheet.rows.length || 
          action.payload.to >= sheet.rows.length ||
          action.payload.from === action.payload.to) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      const [movedRow] = newSheet.rows.splice(action.payload.from, 1);
      newSheet.rows.splice(action.payload.to, 0, movedRow);
      
      // Update flagged rows indices
      const newFlaggedRows: Record<number, boolean> = {};
      Object.entries(newSheet.flaggedRows).forEach(([idx, flagged]) => {
        const numIdx = parseInt(idx);
        if (numIdx === action.payload.from) {
          newFlaggedRows[action.payload.to] = flagged;
        } else if (numIdx === action.payload.to) {
          newFlaggedRows[action.payload.from] = flagged;
        } else if ((numIdx > action.payload.from && numIdx <= action.payload.to) ||
                   (numIdx < action.payload.from && numIdx >= action.payload.to)) {
          // Adjust indices based on move direction
          const offset = action.payload.from < action.payload.to ? -1 : 1;
          newFlaggedRows[numIdx + offset] = flagged;
        } else {
          newFlaggedRows[numIdx] = flagged;
        }
      });
      newSheet.flaggedRows = newFlaggedRows;
      
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Moved row ${action.payload.from + 1} to position ${action.payload.to + 1}`, sId);
    }

    case 'INSERT_COLUMN': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      // Insert header
      newSheet.headers.splice(action.payload.index, 0, action.payload.name);
      
      // Insert column data in each row
      newSheet.rows.forEach(row => {
        row.splice(action.payload.index, 0, '');
      });
      
      // Update styles indices
      const newStyles: Record<string, FormatStyle> = {};
      Object.entries(newSheet.styles).forEach(([key, style]) => {
        const [r, c] = key.split('-').map(Number);
        if (c >= action.payload.index) {
          newStyles[`${r}-${c + 1}`] = style;
        } else {
          newStyles[key] = style;
        }
      });
      newSheet.styles = newStyles;
      
      // Update column widths
      const newColWidths: Record<number, number> = {};
      Object.entries(newSheet.colWidths).forEach(([idx, width]) => {
        const numIdx = parseInt(idx);
        if (numIdx >= action.payload.index) {
          newColWidths[numIdx + 1] = width;
        } else {
          newColWidths[numIdx] = width;
        }
      });
      newColWidths[action.payload.index] = 150; // Default width
      newSheet.colWidths = newColWidths;
      
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Inserted column "${action.payload.name}" at position ${action.payload.index + 1}`, sId);
    }

    case 'DELETE_COLUMN': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet || action.payload.index >= sheet.headers.length) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      const deletedHeader = newSheet.headers[action.payload.index];
      
      // Delete header
      newSheet.headers.splice(action.payload.index, 1);
      
      // Delete column data in each row
      newSheet.rows.forEach(row => {
        row.splice(action.payload.index, 1);
      });
      
      // Update styles indices
      const newStyles: Record<string, FormatStyle> = {};
      Object.entries(newSheet.styles).forEach(([key, style]) => {
        const [r, c] = key.split('-').map(Number);
        if (c < action.payload.index) {
          newStyles[key] = style;
        } else if (c > action.payload.index) {
          newStyles[`${r}-${c - 1}`] = style;
        }
      });
      newSheet.styles = newStyles;
      
      // Update column widths
      const newColWidths: Record<number, number> = {};
      Object.entries(newSheet.colWidths).forEach(([idx, width]) => {
        const numIdx = parseInt(idx);
        if (numIdx < action.payload.index) {
          newColWidths[numIdx] = width;
        } else if (numIdx > action.payload.index) {
          newColWidths[numIdx - 1] = width;
        }
      });
      newSheet.colWidths = newColWidths;
      
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Deleted column "${deletedHeader}"`, sId);
    }

    case 'RENAME_COLUMN': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet || action.payload.index >= sheet.headers.length) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      const oldName = newSheet.headers[action.payload.index];
      newSheet.headers[action.payload.index] = action.payload.name;
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, `Renamed column "${oldName}" to "${action.payload.name}"`, sId);
    }

    case 'FREEZE_TOP_ROW': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      newSheet.frozenRows = 1;
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, 'Froze top row', sId);
    }

    case 'UNFREEZE_ROWS': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      
      newSheet.frozenRows = 0;
      newSheet.isDirty = true;
      newSheets[sId] = newSheet;

      return pushHistory(state, newSheets, 'Unfroze rows', sId);
    }

    case 'SET_FILTER': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const { columnId, value } = action.payload;
      
      const newFilters = { ...state.filters };
      if (!newFilters[sId]) newFilters[sId] = {};
      
      if (value.trim() === '') {
        delete newFilters[sId][columnId];
      } else {
        newFilters[sId][columnId] = value;
      }
      
      return { ...state, filters: newFilters };
    }

    case 'CLEAR_FILTER': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const { columnId } = action.payload;
      
      const newFilters = { ...state.filters };
      const newFilteredRows = { ...state.filteredRows };
      
      if (columnId !== undefined) {
        // Clear specific column filter
        if (newFilters[sId]) {
          delete newFilters[sId][columnId];
        }
      } else {
        // Clear all filters for sheet
        delete newFilters[sId];
        delete newFilteredRows[sId];
      }
      
      return { ...state, filters: newFilters, filteredRows: newFilteredRows };
    }

    case 'APPLY_FILTERS': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;
      
      const sheetFilters = state.filters[sId] || {};
      const hasFilters = Object.keys(sheetFilters).length > 0;
      
      if (!hasFilters) {
        const newFilteredRows = { ...state.filteredRows };
        delete newFilteredRows[sId];
        return { ...state, filteredRows: newFilteredRows };
      }
      
      // Apply filters
      const visibleRows: number[] = [];
      sheet.rows.forEach((row, rowIndex) => {
        let isVisible = true;
        
        Object.entries(sheetFilters).forEach(([colId, filterValue]) => {
          const colIndex = parseInt(colId);
          if (colIndex >= 0 && colIndex < row.length) {
            const cellValue = row[colIndex] || '';
            if (!cellValue.toLowerCase().includes(filterValue.toLowerCase())) {
              isVisible = false;
            }
          }
        });
        
        if (isVisible) {
          visibleRows.push(rowIndex);
        }
      });
      
      const newFilteredRows = { ...state.filteredRows, [sId]: visibleRows };
      return { ...state, filteredRows: newFilteredRows };
    }

    case 'APPEND_EDIT_LOG': {
      return { ...state, editLog: [...state.editLog, action.payload], globalDirty: true };
    }

    case 'APPLY_TO_SIMILAR': {
      const sId = action.payload.sheetId ?? state.activeSheetId;
      const sheet = state.sheets[sId];
      if (!sheet) return state;

      const descriptionIndex = action.payload.descriptionColIndex ?? sheet.headers.findIndex(h => h.toLowerCase() === 'description');
      const newSheets = [...state.sheets];
      const newSheet = cloneSheet(sheet);
      const changedRows: number[] = [];

      const sourceText = String(action.payload.value || '').toUpperCase().trim();
      if (!sourceText) return state;

      newSheet.rows.forEach((row, idx) => {
        const desc = String(row[descriptionIndex] || '').toUpperCase();
        const sameEntity = desc.includes(sourceText) || sourceText.includes(desc);
        if (sameEntity) {
          row[action.payload.colIndex] = action.payload.value;
          changedRows.push(idx);
        }
      });

      if (changedRows.length === 0) return state;

      newSheet.isDirty = true;
      newSheets[sId] = newSheet;
      const next = pushHistory(state, newSheets, `Applied category "${action.payload.value}" to ${changedRows.length} similar rows`, sId);
      return { ...next, editLog: [...next.editLog, ...changedRows.map(r => ({
        sheet_title: newSheet.title,
        row_index: r,
        description: String(newSheet.rows[r]?.[descriptionIndex] || ''),
        category: String(action.payload.value || ''),
        confidence: 1,
        source: 'user_apply_similar',
        metadata: { source_row: action.payload.rowIndex },
      }))] };
    }

    default:
      return state;
  }
}

const SpreadsheetContext = createContext<{
  state: SpreadsheetState;
  dispatch: React.Dispatch<Action>;
} | null>(null);

export const SpreadsheetProvider: React.FC<PropsWithChildren> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <SpreadsheetContext.Provider value={{ state, dispatch }}>
      {children}
    </SpreadsheetContext.Provider>
  );
};

export const useSpreadsheet = () => {
  const context = useContext(SpreadsheetContext);
  if (!context) throw new Error('useSpreadsheet must be used within SpreadsheetProvider');
  return context;
};
