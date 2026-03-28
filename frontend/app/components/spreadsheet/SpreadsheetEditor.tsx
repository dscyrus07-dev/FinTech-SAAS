'use client'

import React, { useState, useEffect } from 'react';
import { ProcessingResult } from '@/types';
import { useSpreadsheet } from './SpreadsheetContext';
import SpreadsheetToolbar from './SpreadsheetToolbar';
import SpreadsheetGrid from './SpreadsheetGrid';
import SpreadsheetHistory from './SpreadsheetHistory';
import { exportToExcel } from '@/utils/excelExport';
import { Save, AlertTriangle, ArrowLeft } from 'lucide-react';

interface SpreadsheetEditorProps {
  initialResult: ProcessingResult;
  onExit: () => void;
  apiKey?: string;
}

export default function SpreadsheetEditor({ initialResult, onExit, apiKey }: SpreadsheetEditorProps) {
  const { state, dispatch } = useSpreadsheet();
  const [isSaving, setIsSaving] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showUnsavedModal, setShowUnsavedModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<{ text: string, type: 'success' | 'error' } | null>(null);

  // Initialize data once
  useEffect(() => {
    if (state.sheets.length > 0) return; // Already initialized

    const PLACEHOLDER_SHEETS = [
      { title: 'Sheet 1 — Summary', headers: ['Metric', 'Value'], rows: [] },
      { title: 'Sheet 2 — Monthly Analysis', headers: ['Metric / Category'], rows: [] },
      { title: 'Sheet 3 — Weekly Analysis', headers: ['Week', 'Credit Amount', 'Credit Count', 'Debit Amount', 'Debit Count'], rows: [] },
      { title: 'Sheet 4 — Category Analysis', headers: ['Category', 'Amount', 'Count'], rows: [] },
      { title: 'Sheet 5 — Bounces & Penal', headers: ['Sl. No.', 'Bank Name', 'Account Number', 'Date', 'Cheque No.', 'Description', 'Amount', 'Category', 'Balance'], rows: [] },
      { title: 'Sheet 6 — Funds Received', headers: ['Sl. No.', 'Debit Account Number', 'Date', 'Description', 'Amount', 'Category', 'Balance'], rows: [] },
      { title: 'Sheet 7 — Funds Remittance', headers: ['Sl. No.', 'Beneficiary Account', 'Date', 'Description', 'Amount', 'Category', 'Balance'], rows: [] },
      { title: 'Sheet 8 — Raw Transaction', headers: ['Date', 'Description', 'Debit', 'Credit', 'Balance', 'Category', 'Confidence', 'Recurring'], rows: [] },
    ];

    const mappedSheets = [
      initialResult.account_summary || PLACEHOLDER_SHEETS[0],
      initialResult.monthly_analysis || PLACEHOLDER_SHEETS[1],
      initialResult.weekly_analysis || PLACEHOLDER_SHEETS[2],
      initialResult.category_analysis || PLACEHOLDER_SHEETS[3],
      initialResult.bounces_penal || PLACEHOLDER_SHEETS[4],
      initialResult.funds_received || PLACEHOLDER_SHEETS[5],
      initialResult.funds_remittance || PLACEHOLDER_SHEETS[6],
      initialResult.raw_transactions || PLACEHOLDER_SHEETS[7],
    ].map((s, idx) => ({
      id: idx,
      title: s.title,
      headers: s.headers,
      rows: s.rows || [],
      styles: {},
      colWidths: {},
      frozenRows: 0,
      flaggedRows: {},
      isDirty: false,
    }));

    dispatch({ type: 'INIT', payload: mappedSheets });
  }, [initialResult, dispatch, state.sheets.length]);

  if (state.sheets.length === 0) {
    return <div className="fixed inset-0 bg-white flex items-center justify-center z-50">Loading editor...</div>;
  }

  const handleDownloadExcel = async () => {
    setIsDownloading(true);
    try {
      await exportToExcel(state);
    } catch (e) {
      console.error(e);
      setToastMessage({ text: 'Download Failed', type: 'error' });
    }
    setIsDownloading(false);
  };

  const handleSaveChanges = async () => {
    setIsSaving(true);
    try {
      // Serialize current sheet state
      const payload: Record<string, string[][]> = {};
      state.sheets.forEach(sheet => {
        payload[sheet.title] = [sheet.headers, ...sheet.rows];
      });

      const res = await fetch('/api/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sheets: payload, api_key: apiKey }),
      });

      if (res.ok) {
        setToastMessage({ text: 'Changes saved & synced ✓', type: 'success' });
        dispatch({ type: 'MARK_CLEAN' });
      } else {
        setToastMessage({ text: 'Sync failed — your download will still work', type: 'error' });
      }
    } catch (e) {
      setToastMessage({ text: 'Sync failed — your download will still work', type: 'error' });
    }
    setIsSaving(false);
    
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleExitClick = () => {
    if (state.globalDirty) {
      setShowUnsavedModal(true);
    } else {
      onExit();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col font-sans overflow-hidden">
      {/* Toast Notification */}
      {toastMessage && (
        <div className={`fixed top-4 right-4 z-[9999] px-4 py-2 rounded shadow-lg text-sm font-medium animate-fade-in ${toastMessage.type === 'success' ? 'bg-green-100 text-green-800 border fill-green-500' : 'bg-red-100 text-red-800 border border-red-200'}`}>
          {toastMessage.text}
        </div>
      )}

      {/* Editor Header Bar */}
      <div className="flex bg-neutral-900 text-white items-center px-4 py-2 justify-between">
        <div className="flex items-center gap-4">
          <button onClick={handleExitClick} className="flex items-center gap-2 hover:bg-neutral-800 px-2 py-1 rounded text-sm transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Report
          </button>
          <div className="flex items-center gap-3">
            {/* Airco Insights Logo */}
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-sm">AI</span>
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-lg tracking-tight text-white">Airco Insights</span>
                <span className="text-xs text-blue-200">Spreadsheet Editor</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Toolbar */}
      <SpreadsheetToolbar
        onSave={handleSaveChanges}
        onDownload={handleDownloadExcel}
        onToggleHistory={() => setShowHistory(!showHistory)}
        isSaving={isSaving}
        isDownloading={isDownloading}
      />

      {/* Grid Area */}
      <div className="flex-1 flex overflow-hidden relative">
        <div className="flex-1 flex flex-col bg-neutral-100 relative">
           <SpreadsheetGrid sheet={state.sheets[state.activeSheetId]} />
        </div>

        {/* Change History Slide In */}
        {showHistory && (
          <SpreadsheetHistory onClose={() => setShowHistory(false)} />
        )}
      </div>

      {/* Bottom Tabs */}
      <div className="h-10 bg-neutral-200 border-t flex items-end px-2 gap-1 shrink-0 overflow-x-auto">
        {state.sheets.map(sheet => (
          <button
            key={sheet.id}
            onClick={() => dispatch({ type: 'SET_ACTIVE_SHEET', payload: sheet.id })}
            className={`px-4 py-1.5 min-w-[120px] text-sm truncate rounded-t-md relative transition-colors ${
              state.activeSheetId === sheet.id
                ? 'bg-white font-bold text-black border-t border-x shadow-sm'
                : 'bg-neutral-100 text-neutral-600 hover:bg-white/60 hover:text-black border-transparent'
            }`}
          >
            {sheet.title.replace(/Sheet \d+ — /, '')}
            {sheet.isDirty && (
              <span className="absolute top-1 right-2 w-1.5 h-1.5 bg-orange-500 rounded-full" title="Unsaved changes"></span>
            )}
          </button>
        ))}
      </div>

      {/* Exit Modal */}
      {showUnsavedModal && (
        <div className="fixed inset-0 bg-black/50 z-[999] flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center shrink-0">
                <AlertTriangle className="text-orange-600 w-5 h-5" />
              </div>
              <h3 className="text-lg font-bold text-neutral-900">Unsaved Changes</h3>
            </div>
            <p className="text-sm text-neutral-600 mb-6">You have edits that haven't been downloaded yet.</p>
            <div className="flex flex-col gap-2">
              <button 
                onClick={() => { setShowUnsavedModal(false); }}
                className="w-full py-2 px-4 rounded-md font-medium text-neutral-700 hover:bg-neutral-100 border border-neutral-300"
              >
                Stay
              </button>
              <button 
                onClick={async () => {
                  await handleDownloadExcel();
                  onExit();
                }}
                className="w-full py-2 px-4 rounded-md font-medium text-blue-700 bg-blue-50 border border-blue-200 hover:bg-blue-100"
              >
                Download & Leave
              </button>
              <button 
                onClick={onExit}
                className="w-full py-2 px-4 rounded-md font-medium text-red-600 hover:bg-red-50"
              >
                Leave Without Saving
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
