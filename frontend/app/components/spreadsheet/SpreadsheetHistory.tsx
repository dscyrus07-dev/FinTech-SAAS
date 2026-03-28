'use client'

import React from 'react';
import { useSpreadsheet } from './SpreadsheetContext';
import { X, Undo2, History } from 'lucide-react';

interface SpreadsheetHistoryProps {
  onClose: () => void;
}

export default function SpreadsheetHistory({ onClose }: SpreadsheetHistoryProps) {
  const { state, dispatch } = useSpreadsheet();
  
  // We want to show only the valid history up to the current historyIndex
  const activeHistory = state.history.slice(0, state.historyIndex + 1);

  return (
    <div className="w-80 bg-white border-l shadow-2xl shrink-0 flex flex-col absolute right-0 top-0 bottom-0 z-40 animate-slide-left">
      <div className="flex items-center justify-between p-4 border-b bg-neutral-50">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-neutral-600" />
          <h3 className="text-sm font-semibold text-neutral-800">Change History</h3>
        </div>
        <button className="text-neutral-500 hover:text-black p-1 hover:bg-neutral-200 rounded" onClick={onClose}>
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 bg-blue-50/50 border-b text-xs text-neutral-600 font-medium text-center">
        {activeHistory.length} changes made
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {activeHistory.length === 0 ? (
          <div className="text-center text-sm text-neutral-400 mt-10">
            No changes have been made yet.
          </div>
        ) : (
          [...activeHistory].reverse().map((entry, idx) => {
            const realIdx = activeHistory.length - 1 - idx;
            const sheetTitle = state.sheets[entry.sheetId]?.title || `Sheet ${entry.sheetId + 1}`;
            return (
              <div key={entry.id} className="text-xs bg-white border rounded shadow-sm p-3 group relative hover:border-blue-300 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex flex-col gap-1">
                    <span className="font-semibold text-neutral-800 tracking-tight">{sheetTitle.replace(/Sheet \d+ — /, '')}</span>
                    <span className="text-neutral-600 leading-relaxed">{entry.description}</span>
                  </div>
                  <button 
                    title="Revert this specific change"
                    className="opacity-0 group-hover:opacity-100 p-1.5 text-red-500 hover:bg-red-50 rounded transition-all"
                    onClick={() => dispatch({ type: 'REVERT_HISTORY', payload: entry })}
                  >
                    <Undo2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
