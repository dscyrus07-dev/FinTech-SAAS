'use client'

import React, { useState, useEffect } from 'react';
import { useSpreadsheet } from './SpreadsheetContext';
import { Bold, Italic, Underline, Type, PaintBucket, Undo, Redo, Search, Filter, Save, Download, Clock, Flag, AlignLeft, AlignCenter, AlignRight, WrapText, Merge, Grid3x3, ArrowUp, ArrowDown, Plus, Minus } from 'lucide-react';

interface SpreadsheetToolbarProps {
  onSave: () => void;
  onDownload: () => void;
  onToggleHistory: () => void;
  isSaving: boolean;
  isDownloading: boolean;
}

export default function SpreadsheetToolbar({ onSave, onDownload, onToggleHistory, isSaving, isDownloading }: SpreadsheetToolbarProps) {
  const { state, dispatch } = useSpreadsheet();
  const [showColorPicker, setShowColorPicker] = useState<'text' | 'bg' | null>(null);
  const [showNumberFormat, setShowNumberFormat] = useState(false);
  const [showBorderOptions, setShowBorderOptions] = useState(false);
  const [showFilterOptions, setShowFilterOptions] = useState(false);

  const activeSheet = state.sheets[state.activeSheetId];

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowColorPicker(null);
      setShowNumberFormat(false);
      setShowBorderOptions(false);
      setShowFilterOptions(false);
    };

    if (showColorPicker || showNumberFormat || showBorderOptions || showFilterOptions) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [showColorPicker, showNumberFormat, showBorderOptions, showFilterOptions]);

  const applyStyle = (style: any) => {
    if (!state.selection) return;
    const { start, end } = state.selection;
    const rMin = Math.min(start.r, end.r);
    const rMax = Math.max(start.r, end.r);
    const cMin = Math.min(start.c, end.c);
    const cMax = Math.max(start.c, end.c);

    for (let r = rMin; r <= rMax; r++) {
      for (let c = cMin; c <= cMax; c++) {
        const realCol = activeSheet?.title.includes('Raw Transaction') ? c - 1 : c;
        if (realCol >= 0) {
          dispatch({ type: 'SET_CELL_STYLE', payload: { r, c: realCol, style } });
        }
      }
    }
  };

  const applyAlignment = (horizontal: 'left' | 'center' | 'right') => {
    applyStyle({ alignment: { horizontal } });
  };

  const applyNumberFormat = (format: string) => {
    applyStyle({ numberFormat: format });
    setShowNumberFormat(false);
  };

  const applyBorder = (borderType: 'all' | 'outside' | 'none') => {
    const borderStyle = { style: 'thin', color: { argb: 'FF000000' } };
    let style: any = {};
    
    switch (borderType) {
      case 'all':
        style = { border: borderStyle };
        break;
      case 'outside':
        style = { border: borderStyle }; // Simplified - would need more complex logic for outside only
        break;
      case 'none':
        style = { border: null };
        break;
    }
    
    applyStyle(style);
    setShowBorderOptions(false);
  };

  const mergeCells = () => {
    // Simplified merge - would need more complex implementation
    applyStyle({ merge: true });
  };

  const insertRow = (position: 'above' | 'below') => {
    if (!state.selection) return;
    const { start } = state.selection;
    const index = position === 'above' ? start.r : start.r + 1;
    const newRow = new Array(activeSheet?.headers.length || 0).fill('');
    dispatch({ type: 'INSERT_ROW', payload: { index, data: newRow } });
  };

  const deleteRow = () => {
    if (!state.selection) return;
    const { start, end } = state.selection;
    for (let r = end.r; r >= start.r; r--) {
      dispatch({ type: 'DELETE_ROW', payload: { index: r } });
    }
  };

  const toggleFreezeTopRow = () => {
    if (!activeSheet) return;
    
    if (activeSheet.frozenRows > 0) {
      dispatch({ type: 'UNFREEZE_ROWS', payload: {} });
    } else {
      dispatch({ type: 'FREEZE_TOP_ROW', payload: {} });
    }
  };

  const isFlagEnabled = activeSheet?.title.includes('Raw Transaction') && state.showFlaggedOnly;

  // Filter functions
  const getActiveFilters = () => {
    const sheetFilters = state.filters[state.activeSheetId] || {};
    return Object.keys(sheetFilters).length;
  };

  const clearAllFilters = () => {
    dispatch({ type: 'CLEAR_FILTER', payload: {} });
    setShowFilterOptions(false);
  };

  const applyFilters = () => {
    dispatch({ type: 'APPLY_FILTERS', payload: {} });
    setShowFilterOptions(false);
  };

  return (
    <div className="flex flex-col border-b bg-neutral-50 shrink-0">
      {/* Upper Toolbar */}
      <div className="flex items-center gap-1 p-2 shrink-0 flex-wrap">
        {/* Font Styles */}
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyStyle({ bold: true })} title="Bold (Ctrl+B)">
          <Bold className="w-4 h-4" />
        </button>
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyStyle({ italic: true })} title="Italic (Ctrl+I)">
          <Italic className="w-4 h-4" />
        </button>
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyStyle({ underline: true })} title="Underline (Ctrl+U)">
          <Underline className="w-4 h-4" />
        </button>

        <div className="w-px h-6 bg-neutral-300 mx-1"></div>

        {/* Colors */}
        <div className="relative">
          <button 
            className={`p-1.5 hover:bg-neutral-200 rounded text-neutral-700 relative ${showColorPicker === 'text' ? 'bg-neutral-200' : ''}`} 
            onClick={() => setShowColorPicker(showColorPicker === 'text' ? null : 'text')} 
            title="Text Color"
          >
            <Type className="w-4 h-4" />
          </button>
          {showColorPicker === 'text' && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-neutral-300 rounded shadow-lg p-2 z-50" onClick={(e) => e.stopPropagation()}>
              <input 
                type="color" 
                className="w-12 h-12 border-0 cursor-pointer" 
                onChange={(e) => {
                  applyStyle({ color: e.target.value });
                  setShowColorPicker(null);
                }} 
              />
              <div className="text-xs text-neutral-600 mt-1">Text Color</div>
            </div>
          )}
        </div>

        <div className="relative">
          <button 
            className={`p-1.5 hover:bg-neutral-200 rounded text-neutral-700 relative ${showColorPicker === 'bg' ? 'bg-neutral-200' : ''}`} 
            onClick={(e) => {
              e.stopPropagation();
              setShowColorPicker(showColorPicker === 'bg' ? null : 'bg');
            }} 
            title="Background Color"
          >
            <PaintBucket className="w-4 h-4" />
          </button>
          {showColorPicker === 'bg' && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-neutral-300 rounded shadow-lg p-2 z-50" onClick={(e) => e.stopPropagation()}>
              <input 
                type="color" 
                className="w-12 h-12 border-0 cursor-pointer" 
                onChange={(e) => {
                  applyStyle({ bg: e.target.value });
                  setShowColorPicker(null);
                }} 
              />
              <div className="text-xs text-neutral-600 mt-1">Background</div>
            </div>
          )}
        </div>

        <div className="w-px h-6 bg-neutral-300 mx-1"></div>

        {/* Alignment */}
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyAlignment('left')} title="Align Left">
          <AlignLeft className="w-4 h-4" />
        </button>
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyAlignment('center')} title="Align Center">
          <AlignCenter className="w-4 h-4" />
        </button>
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyAlignment('right')} title="Align Right">
          <AlignRight className="w-4 h-4" />
        </button>

        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => applyStyle({ wrapText: true })} title="Wrap Text">
          <WrapText className="w-4 h-4" />
        </button>

        <div className="w-px h-6 bg-neutral-300 mx-1"></div>

        {/* Number Format */}
        <div className="relative">
          <button 
            className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700 font-medium text-xs px-3" 
            onClick={() => setShowNumberFormat(!showNumberFormat)}
            title="Number Format"
          >
            123
          </button>
          {showNumberFormat && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-neutral-300 rounded shadow-lg z-10 min-w-32">
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyNumberFormat('General')}>General</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyNumberFormat('₹#,##0.00')}>Currency (₹)</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyNumberFormat('#,##0.00')}>Number</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyNumberFormat('0.00%')}>Percentage</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyNumberFormat('DD/MM/YYYY')}>Date</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyNumberFormat('@')}>Text</button>
            </div>
          )}
        </div>

        {/* Borders */}
        <div className="relative">
          <button 
            className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" 
            onClick={() => setShowBorderOptions(!showBorderOptions)}
            title="Borders"
          >
            <Grid3x3 className="w-4 h-4" />
          </button>
          {showBorderOptions && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-neutral-300 rounded shadow-lg z-10 min-w-32">
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyBorder('all')}>All Borders</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyBorder('outside')}>Outside Borders</button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={() => applyBorder('none')}>No Borders</button>
            </div>
          )}
        </div>

        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={mergeCells} title="Merge & Center">
          <Merge className="w-4 h-4" />
        </button>

        <div className="w-px h-6 bg-neutral-300 mx-1"></div>

        {/* Row Operations */}
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => insertRow('above')} title="Insert Row Above">
          <Plus className="w-4 h-4" />
          <ArrowUp className="w-2 h-2" />
        </button>
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={() => insertRow('below')} title="Insert Row Below">
          <Plus className="w-4 h-4" />
          <ArrowDown className="w-2 h-2" />
        </button>
        <button className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700" onClick={deleteRow} title="Delete Row">
          <Minus className="w-4 h-4" />
        </button>

        <div className="w-px h-6 bg-neutral-300 mx-1"></div>

        {/* Undo/Redo */}
        <button 
          className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700 disabled:opacity-50" 
          onClick={() => dispatch({ type: 'UNDO' })} 
          disabled={state.historyIndex < 0}
          title="Undo (Ctrl+Z)"
        >
          <Undo className="w-4 h-4" />
        </button>
        <button 
          className="p-1.5 hover:bg-neutral-200 rounded text-neutral-700 disabled:opacity-50" 
          onClick={() => dispatch({ type: 'REDO' })} 
          disabled={state.historyIndex >= state.history.length - 1}
          title="Redo (Ctrl+Y)"
        >
          <Redo className="w-4 h-4" />
        </button>

        <div className="w-px h-6 bg-neutral-300 mx-1"></div>

        {/* View Options */}
        <button 
          className={`p-1.5 hover:bg-neutral-200 rounded text-neutral-700 font-medium text-xs px-3 ${activeSheet?.frozenRows > 0 ? 'bg-blue-100 text-blue-700' : ''}`} 
          onClick={toggleFreezeTopRow}
          title={activeSheet?.frozenRows > 0 ? 'Unfreeze Top Row' : 'Freeze Top Row'}
        >
          {activeSheet?.frozenRows > 0 ? '❄️' : '🧊'} Freeze Top Row
        </button>
        {/* Filter */}
        <div className="relative">
          <button 
            className={`flex items-center gap-1.5 p-1.5 hover:bg-neutral-200 rounded text-neutral-700 font-medium text-xs px-3 ${getActiveFilters() > 0 ? 'bg-blue-100 text-blue-700' : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              setShowFilterOptions(!showFilterOptions);
            }}
            title="Filter"
          >
            <Filter className="w-3.5 h-3.5" /> Filter {getActiveFilters() > 0 && `(${getActiveFilters()})`}
          </button>
          {showFilterOptions && (
            <div className="absolute top-full left-0 mt-1 bg-white border border-neutral-300 rounded shadow-lg z-50 min-w-48" onClick={(e) => e.stopPropagation()}>
              <div className="px-3 py-2 border-b">
                <div className="text-xs font-semibold text-neutral-600">Filter Options</div>
                {getActiveFilters() > 0 && (
                  <div className="text-xs text-blue-600 mt-1">{getActiveFilters()} active filter(s)</div>
                )}
              </div>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={applyFilters}>
                Apply Filters
              </button>
              <button className="block w-full text-left px-3 py-2 hover:bg-neutral-100 text-xs" onClick={clearAllFilters}>
                Clear All Filters
              </button>
              <div className="px-3 py-2 border-t">
                <div className="text-xs text-neutral-500">Basic filtering enabled</div>
                <div className="text-xs text-neutral-400">Select cells and use right-click for advanced options</div>
              </div>
            </div>
          )}
        </div>

        {activeSheet?.title.includes('Raw Transaction') && (
          <button 
            className={`flex items-center gap-1.5 p-1.5 rounded font-medium text-xs px-3 ${state.showFlaggedOnly ? 'bg-red-100 text-red-700' : 'hover:bg-neutral-200 text-neutral-700'}`} 
            onClick={() => dispatch({ type: 'TOGGLE_FLAGGED_ONLY' })}
            title="Show Flagged Only"
          >
            <Flag className="w-3.5 h-3.5" /> Flagged Only
          </button>
        )}

        <div className="flex-1"></div>

        <button 
          onClick={onToggleHistory}
          className="flex items-center gap-1.5 p-1.5 hover:bg-neutral-200 rounded text-neutral-700 font-medium text-xs px-3"
        >
          <Clock className="w-3.5 h-3.5" /> Changes
        </button>

        <button 
          onClick={onSave}
          disabled={isSaving || !state.globalDirty}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium text-xs disabled:opacity-50 transition-colors"
        >
          <Save className="w-3.5 h-3.5" /> {isSaving ? 'Saving...' : 'Save Changes'}
        </button>
        
        <button 
          onClick={onDownload}
          disabled={isDownloading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-800 hover:bg-black text-white rounded font-medium text-xs disabled:opacity-50 transition-colors"
        >
          <Download className="w-3.5 h-3.5" /> {isDownloading ? 'Generating...' : 'Download Excel'}
        </button>

      </div>

      {/* Quick Stats Bar */}
      <QuickStatsBar />
    </div>
  );
}

function QuickStatsBar() {
  const { state } = useSpreadsheet();
  const sheet = state.sheets[state.activeSheetId];

  if (!sheet) return null;

  // Enhanced column detection logic
  let creditCol = -1;
  let debitCol = -1;
  let amountCol = -1;
  
  console.log('=== QUICK STATS DEBUG ===');
  console.log('Sheet headers:', sheet.headers);
  console.log('Sheet rows count:', sheet.rows.length);
  
  // Find columns by header name (case-insensitive, more flexible matching)
  sheet.headers.forEach((h, i) => {
    const headerLower = h.toLowerCase().trim();
    console.log(`Header ${i}: "${h}" -> "${headerLower}"`);
    
    // Credit column detection
    if (headerLower.includes('credit') && !headerLower.includes('count')) {
      creditCol = i;
      console.log(`Found credit column at index ${i}: "${h}"`);
    }
    // Debit column detection (exclude account number columns)
    else if (headerLower.includes('debit') && 
             !headerLower.includes('account') && 
             !headerLower.includes('count')) {
      debitCol = i;
      console.log(`Found debit column at index ${i}: "${h}"`);
    }
    // Amount column detection
    else if (headerLower === 'amount' || 
             headerLower.includes('amount') ||
             headerLower.includes('balance')) {
      amountCol = i;
      console.log(`Found amount column at index ${i}: "${h}"`);
    }
  });

  console.log('Detected columns:', { creditCol, debitCol, amountCol });

  // Parse Indian currency values correctly
  const parseIndianCurrency = (value: string | number): number => {
    if (typeof value === 'number') return value;
    if (!value || typeof value !== 'string') return 0;
    
    // Remove ₹ symbol, commas, whitespace, then parse
    const cleanValue = value
      .replace(/[₹\s]/g, '') // Remove ₹ and whitespace
      .replace(/,/g, '')     // Remove commas
      .trim();
    
    const parsed = parseFloat(cleanValue);
    return isNaN(parsed) ? 0 : parsed;
  };

  let totalCredits = 0;
  let totalDebits = 0;
  let processedRows = 0;

  // Calculate totals based on detected columns
  sheet.rows.forEach((r, rowIdx) => {
    let rowCredit = 0;
    let rowDebit = 0;
    
    // Check credit column
    if (creditCol >= 0 && r[creditCol]) {
      const val = parseIndianCurrency(r[creditCol]);
      if (val > 0) {
        rowCredit = val;
        totalCredits += val;
      }
    }
    
    // Check debit column
    if (debitCol >= 0 && r[debitCol]) {
      const val = parseIndianCurrency(r[debitCol]);
      if (val > 0) {
        rowDebit = val;
        totalDebits += val;
      }
    }
    
    // Check amount column (positive = credit, negative = debit)
    if (amountCol >= 0 && r[amountCol]) {
      const val = parseIndianCurrency(r[amountCol]);
      if (val > 0) {
        totalCredits += val;
        rowCredit = val;
      } else if (val < 0) {
        totalDebits += Math.abs(val);
        rowDebit = Math.abs(val);
      }
    }
    
    if (rowCredit > 0 || rowDebit > 0) {
      processedRows++;
      console.log(`Row ${rowIdx}: Credit=${rowCredit}, Debit=${rowDebit}, Raw="${r[amountCol] || r[creditCol] || r[debitCol]}"`);
    }
  });

  console.log(`Processed ${processedRows} rows with data`);
  console.log('Totals:', { totalCredits, totalDebits });

  const flaggedRowsCount = Object.keys(sheet.flaggedRows).length;
  const netBalance = totalCredits - totalDebits;

  console.log('Final stats:', {
    totalCredits,
    totalDebits,
    netBalance,
    flaggedRowsCount
  });
  console.log('=== END QUICK STATS DEBUG ===');

  return (
    <div className="bg-white px-4 py-1.5 text-xs font-semibold flex items-center gap-6 text-neutral-600 border-t border-b border-neutral-200 shadow-sm shrink-0">
      <div className="flex gap-2">
        <span className="text-neutral-400">Total Credits:</span>
        <span className="text-emerald-700">₹{totalCredits.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
      </div>
      <div className="flex gap-2">
        <span className="text-neutral-400">Total Debits:</span>
        <span className="text-rose-700">₹{totalDebits.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</span>
      </div>
      <div className="flex gap-2">
        <span className="text-neutral-400">Net Balance:</span>
        <span className={netBalance >= 0 ? "text-emerald-700" : "text-rose-700"}>
          ₹{netBalance.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
        </span>
      </div>
      {sheet.title.includes('Raw Transaction') && (
        <div className="flex gap-2 border-l border-neutral-300 pl-4 ml-auto">
          <span className="text-neutral-400 font-medium">Flagged Rows:</span>
          <span className="text-red-600">{flaggedRowsCount}</span>
        </div>
      )}
    </div>
  );
}
