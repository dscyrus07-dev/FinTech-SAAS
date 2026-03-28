'use client'

import React, { useState, useRef, useEffect, MouseEvent as ReactMouseEvent } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useSpreadsheet } from './SpreadsheetContext';
import { SheetData, CATEGORY_OPTIONS } from './types';
import { Flag, Trash2, Copy, Clipboard, MoreVertical, Plus, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Columns, Rows } from 'lucide-react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

interface SpreadsheetGridProps {
  sheet: SheetData;
}

export default function SpreadsheetGrid({ sheet }: SpreadsheetGridProps) {
  const { state, dispatch } = useSpreadsheet();
  const parentRef = useRef<HTMLDivElement>(null);
  const [editingCell, setEditingCell] = useState<{ r: number, c: number } | null>(null);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number, y: number, r: number, c: number } | null>(null);
  const [dragStart, setDragStart] = useState<{ r: number, c: number } | null>(null);
  const [notePopup, setNotePopup] = useState<{ r: number, c: number, note: string } | null>(null);

  const isRaw = sheet.title.includes('Raw Transaction');
  const headers = isRaw ? ['Flag', ...sheet.headers] : sheet.headers;
  
  // Apply filtering based on showFlaggedOnly
  const displayedRows = React.useMemo(() => {
    if (isRaw && state.showFlaggedOnly) {
      return sheet.rows.map((r, idx) => ({ r: r, idx })).filter(({ idx }) => sheet.flaggedRows[idx]);
    }
    return sheet.rows.map((r, idx) => ({ r: r, idx }));
  }, [sheet.rows, isRaw, state.showFlaggedOnly, sheet.flaggedRows]);

  const rowVirtualizer = useVirtualizer({
    count: displayedRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 32,
    overscan: 20,
  });

  const colVirtualizer = useVirtualizer({
    horizontal: true,
    count: headers.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => sheet.colWidths[index] || 150,
  });

  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingCell]);

  useEffect(() => {
    const handleGlobalClick = () => { setContextMenu(null); };
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

  const handleCellMouseDown = (e: ReactMouseEvent, rawIndex: number, c: number) => {
    if (e.button !== 0) return; // Only left click
    if (editingCell) finishEdit();
    
    setDragStart({ r: rawIndex, c });
    dispatch({ type: 'SET_SELECTION', payload: { start: { r: rawIndex, c }, end: { r: rawIndex, c } } });
  };

  const handleCellMouseEnter = (e: ReactMouseEvent, rawIndex: number, c: number) => {
    if (e.buttons !== 1 || !dragStart) return;
    dispatch({ type: 'SET_SELECTION', payload: { start: dragStart, end: { r: rawIndex, c } } });
  };

  const handleCellDoubleClick = (rawIndex: number, colIndex: number, val: string) => {
    setEditingCell({ r: rawIndex, c: colIndex });
    setEditValue(val);
  };

  const finishEdit = () => {
    if (editingCell) {
      const realCol = isRaw ? editingCell.c - 1 : editingCell.c;
      if (realCol >= 0) {
        dispatch({
          type: 'SET_CELL_DATA', 
          payload: { r: editingCell.r, c: realCol, val: editValue }
        });
      }
      setEditingCell(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle editing shortcuts
    if (editingCell) {
      if (e.key === 'Enter') {
        finishEdit();
        e.preventDefault();
        // Move down to next cell
        if (editingCell.r < sheet.rows.length - 1) {
          dispatch({ type: 'SET_SELECTION', payload: { start: { r: editingCell.r + 1, c: editingCell.c }, end: { r: editingCell.r + 1, c: editingCell.c } } });
        }
      }
      if (e.key === 'Escape') {
        setEditingCell(null);
        e.preventDefault();
      }
      if (e.key === 'Tab') {
        finishEdit();
        e.preventDefault();
        // Move right or wrap to next row
        if (editingCell.c < headers.length - 1) {
          dispatch({ type: 'SET_SELECTION', payload: { start: { r: editingCell.r, c: editingCell.c + 1 }, end: { r: editingCell.r, c: editingCell.c + 1 } } });
        } else if (editingCell.r < sheet.rows.length - 1) {
          dispatch({ type: 'SET_SELECTION', payload: { start: { r: editingCell.r + 1, c: 0 }, end: { r: editingCell.r + 1, c: 0 } } });
        }
      }
      return;
    }

    // Handle navigation shortcuts
    if (e.ctrlKey || e.metaKey) {
      switch (e.key) {
        case 'c':
          e.preventDefault();
          handleCopy();
          break;
        case 'x':
          e.preventDefault();
          handleCut();
          break;
        case 'v':
          e.preventDefault();
          handlePaste();
          break;
        case 'z':
          e.preventDefault();
          dispatch({ type: 'UNDO' });
          break;
        case 'y':
          e.preventDefault();
          dispatch({ type: 'REDO' });
          break;
        case 'b':
          e.preventDefault();
          applyStyleToSelection({ bold: true });
          break;
        case 'i':
          e.preventDefault();
          applyStyleToSelection({ italic: true });
          break;
        case 'u':
          e.preventDefault();
          applyStyleToSelection({ underline: true });
          break;
        case 'f':
          e.preventDefault();
          // Find & Replace - could open a modal
          break;
        case 'a':
          e.preventDefault();
          // Select all
          if (sheet.rows.length > 0 && headers.length > 0) {
            dispatch({ type: 'SET_SELECTION', payload: { start: { r: 0, c: 0 }, end: { r: sheet.rows.length - 1, c: headers.length - 1 } } });
          }
          break;
        case 'Home':
          e.preventDefault();
          // Jump to A1
          dispatch({ type: 'SET_SELECTION', payload: { start: { r: 0, c: 0 }, end: { r: 0, c: 0 } } });
          break;
        case 'End':
          e.preventDefault();
          // Jump to last data cell
          if (sheet.rows.length > 0 && headers.length > 0) {
            dispatch({ type: 'SET_SELECTION', payload: { start: { r: sheet.rows.length - 1, c: headers.length - 1 }, end: { r: sheet.rows.length - 1, c: headers.length - 1 } } });
          }
          break;
      }
      return;
    }

    // Handle arrow key navigation with data edge detection
    if (e.key.startsWith('Arrow')) {
      e.preventDefault();
      if (!state.selection) return;
      
      const { start, end } = state.selection;
      const currentR = start.r;
      const currentC = start.c;
      let newR = currentR;
      let newC = currentC;

      switch (e.key) {
        case 'ArrowUp':
          newR = Math.max(0, currentR - 1);
          break;
        case 'ArrowDown':
          newR = Math.min(sheet.rows.length - 1, currentR + 1);
          break;
        case 'ArrowLeft':
          newC = Math.max(0, currentC - 1);
          break;
        case 'ArrowRight':
          newC = Math.min(headers.length - 1, currentC + 1);
          break;
      }

      dispatch({ type: 'SET_SELECTION', payload: { start: { r: newR, c: newC }, end: { r: newR, c: newC } } });
      return;
    }

    // Handle delete key
    if (e.key === 'Delete') {
      e.preventDefault();
      clearSelectedCells();
      return;
    }

    // Handle F2 for edit mode
    if (e.key === 'F2') {
      e.preventDefault();
      if (state.selection) {
        const { start } = state.selection;
        const realCol = isRaw ? start.c - 1 : start.c;
        if (realCol >= 0 && start.r < sheet.rows.length) {
          const val = sheet.rows[start.r][realCol] || '';
          setEditingCell({ r: start.r, c: start.c });
          setEditValue(val);
        }
      }
      return;
    }

    // Handle regular typing - start editing
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      if (state.selection) {
        const { start } = state.selection;
        const realCol = isRaw ? start.c - 1 : start.c;
        if (realCol >= 0 && start.r < sheet.rows.length) {
          setEditingCell({ r: start.r, c: start.c });
          setEditValue(e.key);
        }
      }
    }
  };

  const handleCopy = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    const copiedData: string[][] = [];
    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      const row: string[] = [];
      for (let c = bounds.minC; c <= bounds.maxC; c++) {
        const realCol = isRaw ? c - 1 : c;
        if (realCol >= 0 && r < sheet.rows.length) {
          row.push(sheet.rows[r][realCol] || '');
        } else {
          row.push('');
        }
      }
      copiedData.push(row);
    }

    // Store in clipboard (simplified - in real app would use Clipboard API)
    const clipboardData = copiedData.map(row => row.join('\t')).join('\n');
    navigator.clipboard.writeText(clipboardData);
    
    dispatch({ type: 'SET_CLIPBOARD', payload: { data: copiedData } });
  };

  const handleCut = () => {
    handleCopy();
    clearSelectedCells();
  };

  const handlePaste = async () => {
    try {
      const clipboardText = await navigator.clipboard.readText();
      const rows = clipboardText.split('\n').map(row => row.split('\t'));
      
      if (!state.selection || rows.length === 0) return;
      const bounds = getSelectionBounds();
      if (!bounds) return;

      rows.forEach((rowData, rOffset) => {
        const targetRow = bounds.minR + rOffset;
        if (targetRow >= sheet.rows.length) return;

        rowData.forEach((cellData, cOffset) => {
          const targetCol = bounds.minC + cOffset;
          const realCol = isRaw ? targetCol - 1 : targetCol;
          if (realCol >= 0 && targetCol < headers.length) {
            dispatch({
              type: 'SET_CELL_DATA',
              payload: { r: targetRow, c: realCol, val: cellData }
            });
          }
        });
      });
    } catch (error) {
      console.error('Paste failed:', error);
    }
  };

  const clearSelectedCells = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      for (let c = bounds.minC; c <= bounds.maxC; c++) {
        const realCol = isRaw ? c - 1 : c;
        if (realCol >= 0 && r < sheet.rows.length) {
          dispatch({
            type: 'SET_CELL_DATA',
            payload: { r, c: realCol, val: '' }
          });
        }
      }
    }
  };

  const applyStyleToSelection = (style: any) => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      for (let c = bounds.minC; c <= bounds.maxC; c++) {
        const realCol = isRaw ? c - 1 : c;
        if (realCol >= 0 && r < sheet.rows.length) {
          dispatch({
            type: 'SET_CELL_STYLE',
            payload: { r, c: realCol, style }
          });
        }
      }
    }
  };

  // Row operations
  const insertRowAbove = (rowIndex: number) => {
    const newRow = new Array(sheet.headers.length).fill('');
    dispatch({
      type: 'INSERT_ROW',
      payload: { index: rowIndex, data: newRow }
    });
  };

  const insertRowBelow = (rowIndex: number) => {
    const newRow = new Array(sheet.headers.length).fill('');
    dispatch({
      type: 'INSERT_ROW',
      payload: { index: rowIndex + 1, data: newRow }
    });
  };

  const deleteSelectedRows = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    // Delete from bottom to top to maintain indices
    for (let r = bounds.maxR; r >= bounds.minR; r--) {
      dispatch({
        type: 'DELETE_ROW',
        payload: { index: r }
      });
    }
  };

  const duplicateRow = (rowIndex: number) => {
    if (rowIndex >= sheet.rows.length) return;
    const rowData = [...sheet.rows[rowIndex]];
    dispatch({
      type: 'INSERT_ROW',
      payload: { index: rowIndex + 1, data: rowData }
    });
  };

  const moveRowUp = (rowIndex: number) => {
    if (rowIndex <= 0) return;
    dispatch({
      type: 'MOVE_ROW',
      payload: { from: rowIndex, to: rowIndex - 1 }
    });
  };

  const moveRowDown = (rowIndex: number) => {
    if (rowIndex >= sheet.rows.length - 1) return;
    dispatch({
      type: 'MOVE_ROW',
      payload: { from: rowIndex, to: rowIndex + 1 }
    });
  };

  // Column operations
  const insertColumnLeft = (colIndex: number) => {
    const newColName = `Column ${colIndex + 1}`;
    dispatch({
      type: 'INSERT_COLUMN',
      payload: { index: colIndex, name: newColName }
    });
  };

  const insertColumnRight = (colIndex: number) => {
    const newColName = `Column ${colIndex + 2}`;
    dispatch({
      type: 'INSERT_COLUMN',
      payload: { index: colIndex + 1, name: newColName }
    });
  };

  const deleteColumn = (colIndex: number) => {
    dispatch({
      type: 'DELETE_COLUMN',
      payload: { index: colIndex }
    });
  };

  // Shift cell operations
  const shiftCellsUp = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    // Move cells up within the selection
    for (let c = bounds.minC; c <= bounds.maxC; c++) {
      for (let r = bounds.minR; r < bounds.maxR; r++) {
        const realCol = isRaw ? c - 1 : c;
        if (realCol >= 0 && r + 1 < sheet.rows.length) {
          const sourceVal = sheet.rows[r + 1][realCol] || '';
          dispatch({
            type: 'SET_CELL_DATA',
            payload: { r, c: realCol, val: sourceVal }
          });
        }
      }
    }
    
    // Clear the bottom row of selection
    for (let c = bounds.minC; c <= bounds.maxC; c++) {
      const realCol = isRaw ? c - 1 : c;
      if (realCol >= 0) {
        dispatch({
          type: 'SET_CELL_DATA',
          payload: { r: bounds.maxR, c: realCol, val: '' }
        });
      }
    }
  };

  const shiftCellsDown = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    // Move cells down within the selection
    for (let c = bounds.minC; c <= bounds.maxC; c++) {
      for (let r = bounds.maxR; r > bounds.minR; r--) {
        const realCol = isRaw ? c - 1 : c;
        if (realCol >= 0 && r - 1 >= 0) {
          const sourceVal = sheet.rows[r - 1][realCol] || '';
          dispatch({
            type: 'SET_CELL_DATA',
            payload: { r, c: realCol, val: sourceVal }
          });
        }
      }
    }
    
    // Clear the top row of selection
    for (let c = bounds.minC; c <= bounds.maxC; c++) {
      const realCol = isRaw ? c - 1 : c;
      if (realCol >= 0) {
        dispatch({
          type: 'SET_CELL_DATA',
          payload: { r: bounds.minR, c: realCol, val: '' }
        });
      }
    }
  };

  const shiftCellsLeft = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    // Move cells left within the selection
    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      for (let c = bounds.minC; c < bounds.maxC; c++) {
        const realCol = isRaw ? c - 1 : c;
        const targetRealCol = isRaw ? (c + 1) - 1 : c + 1;
        if (realCol >= 0 && targetRealCol < sheet.headers.length) {
          const sourceVal = sheet.rows[r][targetRealCol] || '';
          dispatch({
            type: 'SET_CELL_DATA',
            payload: { r, c: realCol, val: sourceVal }
          });
        }
      }
    }
    
    // Clear the right column of selection
    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      const realCol = isRaw ? bounds.maxC - 1 : bounds.maxC;
      if (realCol >= 0 && realCol < sheet.headers.length) {
        dispatch({
          type: 'SET_CELL_DATA',
          payload: { r, c: realCol, val: '' }
        });
      }
    }
  };

  const shiftCellsRight = () => {
    if (!state.selection) return;
    const bounds = getSelectionBounds();
    if (!bounds) return;

    // Move cells right within the selection
    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      for (let c = bounds.maxC; c > bounds.minC; c--) {
        const realCol = isRaw ? c - 1 : c;
        const sourceRealCol = isRaw ? (c - 1) - 1 : c - 1;
        if (realCol >= 0 && sourceRealCol >= 0) {
          const sourceVal = sheet.rows[r][sourceRealCol] || '';
          dispatch({
            type: 'SET_CELL_DATA',
            payload: { r, c: realCol, val: sourceVal }
          });
        }
      }
    }
    
    // Clear the left column of selection
    for (let r = bounds.minR; r <= bounds.maxR; r++) {
      const realCol = isRaw ? bounds.minC - 1 : bounds.minC;
      if (realCol >= 0 && realCol < sheet.headers.length) {
        dispatch({
          type: 'SET_CELL_DATA',
          payload: { r, c: realCol, val: '' }
        });
      }
    }
  };

  const handleContextMenu = (e: React.MouseEvent, r: number, c: number) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, r, c });
  };

  const isSelected = (r: number, c: number) => {
    if (!state.selection) return false;
    const { start, end } = state.selection;
    const minR = Math.min(start.r, end.r);
    const maxR = Math.max(start.r, end.r);
    const minC = Math.min(start.c, end.c);
    const maxC = Math.max(start.c, end.c);
    return r >= minR && r <= maxR && c >= minC && c <= maxC;
  };

  const getSelectionBounds = () => {
    if (!state.selection) return null;
    const { start, end } = state.selection;
    return {
      minR: Math.min(start.r, end.r), maxR: Math.max(start.r, end.r),
      minC: Math.min(start.c, end.c), maxC: Math.max(start.c, end.c)
    };
  };

  const bounds = getSelectionBounds();
  const showBulkActionBar = bounds && bounds.maxR > bounds.minR && bounds.minC === bounds.maxC;

  return (
    <>
      <div 
        ref={parentRef} 
        className="flex-1 w-full h-full overflow-auto bg-white select-none relative outline-none"
        tabIndex={0}
      >
        <div style={{
          height: `${rowVirtualizer.getTotalSize() + 32}px`,
          width: `${colVirtualizer.getTotalSize()}px`,
          position: 'relative',
        }}>
          {/* Header Row */}
          <div className="absolute top-0 left-0 w-full h-8 flex text-xs font-semibold text-neutral-700 bg-neutral-100 border-b border-neutral-300 z-20">
            {colVirtualizer.getVirtualItems().map((virtualColumn) => (
              <div
                key={virtualColumn.index}
                className="absolute top-0 h-full px-2 py-1.5 flex items-center border-r border-neutral-300 bg-neutral-100"
                style={{
                  left: 0,
                  transform: `translateX(${virtualColumn.start}px)`,
                  width: `${virtualColumn.size}px`,
                }}
              >
                <div className="truncate w-full">{headers[virtualColumn.index]}</div>
              </div>
            ))}
          </div>

          {/* Grid Rows */}
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
             const rowData = displayedRows[virtualRow.index];
             const rawIndex = rowData.idx;
             const cells = rowData.r;

             return (
              <div
                key={virtualRow.index}
                className={cn("absolute left-0 w-full flex text-xs border-b border-neutral-200 hover:bg-neutral-50", 
                  virtualRow.index % 2 === 1 && "bg-neutral-50",
                  isRaw && sheet.flaggedRows[rawIndex] && "bg-rose-50 hover:bg-rose-100"
                )}
                style={{
                  top: 0,
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start + 32}px)`,
                }}
              >
                {colVirtualizer.getVirtualItems().map((virtualColumn) => {
                  const cIndex = virtualColumn.index;
                  const realCol = isRaw ? cIndex - 1 : cIndex;
                  const isFlagCol = isRaw && cIndex === 0;
                  
                  // Value mapping
                  let cellVal = '';
                  if (isFlagCol) {
                    cellVal = '';
                  } else {
                    cellVal = cells[realCol] || '';
                  }

                  const editing = editingCell?.r === rawIndex && editingCell?.c === cIndex;
                  const selected = isSelected(rawIndex, cIndex);
                  
                  const styleKey = `${rawIndex}-${realCol}`;
                  const customStyle = sheet.styles[styleKey] || {};
                  
                  const isCategoryCol = headers[cIndex]?.toLowerCase() === 'category';

                  return (
                    <div
                      key={cIndex}
                      className={cn(
                        "absolute top-0 h-full border-r border-neutral-200 px-2 py-1 flex items-center bg-transparent transition-colors",
                        selected && "bg-blue-100/50 outline outline-1 outline-blue-500 z-10",
                        customStyle.bg && !selected ? "" : "",
                        isFlagCol && "justify-center"
                      )}
                      style={{
                        left: 0,
                        transform: `translateX(${virtualColumn.start}px)`,
                        width: `${virtualColumn.size}px`,
                        backgroundColor: !selected && customStyle.bg ? customStyle.bg : undefined,
                        color: customStyle.color,
                        fontWeight: customStyle.bold ? 'bold' : 'normal',
                        fontStyle: customStyle.italic ? 'italic' : 'normal',
                        textDecoration: customStyle.underline ? 'underline' : 'none'
                      }}
                      onMouseDown={(e) => handleCellMouseDown(e, rawIndex, cIndex)}
                      onMouseEnter={(e) => handleCellMouseEnter(e, rawIndex, cIndex)}
                      onDoubleClick={() => !isFlagCol && handleCellDoubleClick(rawIndex, cIndex, cellVal)}
                      onContextMenu={(e) => handleContextMenu(e, rawIndex, cIndex)}
                    >
                      {/* Note Indicator */}
                      {customStyle.note && (
                         <div className="absolute top-0 right-0 w-0 h-0 border-l-[6px] border-l-transparent border-t-[6px] border-t-red-500" title={customStyle.note}></div>
                      )}

                      {isFlagCol ? (
                        <button 
                          onClick={(e) => { e.stopPropagation(); dispatch({ type: 'TOGGLE_FLAG', payload: { r: rawIndex } }); }}
                          className="hover:bg-neutral-200 p-0.5 rounded cursor-pointer"
                        >
                          <Flag className={cn("w-3.5 h-3.5", sheet.flaggedRows[rawIndex] ? "fill-red-500 text-red-500" : "text-neutral-400")} />
                        </button>
                      ) : editing ? (
                        isCategoryCol ? (
                           <select 
                             ref={inputRef as any}
                             value={editValue} 
                             onChange={e => setEditValue(e.target.value)}
                             onBlur={finishEdit}
                             onKeyDown={handleKeyDown}
                             className="w-full h-full bg-white outline-none ring-2 ring-blue-500 px-1 absolute inset-0 z-50 text-xs"
                           >
                             <option value="">Select...</option>
                             {CATEGORY_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                           </select>
                        ) : (
                          <input
                            ref={inputRef as any}
                            type="text"
                            value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={finishEdit}
                            onKeyDown={handleKeyDown}
                            className="w-full h-full bg-white outline-none ring-2 ring-blue-500 px-1 absolute inset-0 z-50 text-xs"
                          />
                        )
                      ) : (
                        <span className="truncate w-full leading-tight">{cellVal}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div 
          className="fixed z-[100] bg-white border shadow-xl rounded-md w-56 py-1 text-sm font-medium text-neutral-700 font-sans"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Cell Operations */}
          <div className="px-3 py-1 text-xs font-semibold text-neutral-500 uppercase tracking-wide">Cell</div>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center justify-between"
            onClick={() => {
              setNotePopup({ r: contextMenu.r, c: contextMenu.c, note: sheet.styles[`${contextMenu.r}-${isRaw ? contextMenu.c-1 : contextMenu.c}`]?.note || "" });
              setContextMenu(null);
            }}
          >
            Add/Edit Note <Plus className="w-3.5 h-3.5" />
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100"
            onClick={() => {
              const realCol = isRaw ? contextMenu.c - 1 : contextMenu.c;
              if (realCol >= 0) {
                dispatch({
                  type: 'SET_CELL_DATA',
                  payload: { r: contextMenu.r, c: realCol, val: '' }
                });
              }
              setContextMenu(null);
            }}
          >
            Clear Cell Content
          </button>
          
          {/* Row Operations */}
          <div className="border-t my-1"></div>
          <div className="px-3 py-1 text-xs font-semibold text-neutral-500 uppercase tracking-wide">Row</div>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              insertRowAbove(contextMenu.r);
              setContextMenu(null);
            }}
          >
            <ArrowUp className="w-3.5 h-3.5" /> Insert Row Above
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              insertRowBelow(contextMenu.r);
              setContextMenu(null);
            }}
          >
            <ArrowDown className="w-3.5 h-3.5" /> Insert Row Below
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              deleteSelectedRows();
              setContextMenu(null);
            }}
          >
            <Trash2 className="w-3.5 h-3.5" /> Delete Row
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              duplicateRow(contextMenu.r);
              setContextMenu(null);
            }}
          >
            <Copy className="w-3.5 h-3.5" /> Duplicate Row
          </button>
          
          {/* Column Operations */}
          <div className="border-t my-1"></div>
          <div className="px-3 py-1 text-xs font-semibold text-neutral-500 uppercase tracking-wide">Column</div>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              insertColumnLeft(contextMenu.c);
              setContextMenu(null);
            }}
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Insert Column Left
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              insertColumnRight(contextMenu.c);
              setContextMenu(null);
            }}
          >
            <ArrowRight className="w-3.5 h-3.5" /> Insert Column Right
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              deleteColumn(contextMenu.c);
              setContextMenu(null);
            }}
          >
            <Columns className="w-3.5 h-3.5" /> Delete Column
          </button>
          
          {/* Shift Operations */}
          <div className="border-t my-1"></div>
          <div className="px-3 py-1 text-xs font-semibold text-neutral-500 uppercase tracking-wide">Shift Cells</div>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              shiftCellsUp();
              setContextMenu(null);
            }}
          >
            <ArrowUp className="w-3.5 h-3.5" /> Shift Cells Up
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              shiftCellsDown();
              setContextMenu(null);
            }}
          >
            <ArrowDown className="w-3.5 h-3.5" /> Shift Cells Down
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              shiftCellsLeft();
              setContextMenu(null);
            }}
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Shift Cells Left
          </button>
          <button 
            className="w-full text-left px-4 py-2 hover:bg-neutral-100 flex items-center gap-2"
            onClick={() => {
              shiftCellsRight();
              setContextMenu(null);
            }}
          >
            <ArrowRight className="w-3.5 h-3.5" /> Shift Cells Right
          </button>
        </div>
      )}

      {/* Note Popup */}
      {notePopup && (
        <div className="fixed inset-0 z-[101] flex items-center justify-center bg-black/10">
          <div className="bg-white p-4 rounded shadow-xl border w-64 shadow-2xl">
            <h4 className="text-sm font-bold mb-2">Cell Note</h4>
            <textarea 
              className="w-full text-sm border bg-yellow-50 p-2 rounded outline-none ring-1 ring-yellow-200 h-24 resize-none"
              value={notePopup.note}
              onChange={e => setNotePopup({...notePopup, note: e.target.value})}
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-3">
              <button className="px-3 py-1 text-xs hover:bg-neutral-100 rounded" onClick={() => setNotePopup(null)}>Cancel</button>
              <button 
                className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                onClick={() => {
                  dispatch({ 
                    type: 'SET_CELL_NOTE', 
                    payload: { r: notePopup.r, c: isRaw ? notePopup.c - 1 : notePopup.c, note: notePopup.note } 
                  });
                  setNotePopup(null);
                }}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Edit Floating Action Bar */}
      {bounds && bounds.maxR > bounds.minR && headers[bounds.minC]?.toLowerCase() === 'category' && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 bg-neutral-900 shadow-2xl rounded-full px-6 py-3 flex items-center gap-4 text-white z-50 animate-slide-up">
          <span className="text-sm font-medium">{bounds.maxR - bounds.minR + 1} rows selected</span>
          <div className="w-px h-4 bg-neutral-700"></div>
          <div className="flex items-center gap-2">
             <span className="text-xs text-neutral-400">Set Category:</span>
             <select 
                className="bg-neutral-800 border border-neutral-700 text-sm px-2 py-1 rounded text-white outline-none focus:ring-1 focus:ring-blue-500"
                onChange={(e) => {
                  if (e.target.value) {
                     dispatch({ type: 'BULK_UPDATE_CATEGORY', payload: { category: e.target.value, colIndex: isRaw ? bounds.minC - 1 : bounds.minC } });
                  }
                }}
             >
               <option value="">Select...</option>
               {CATEGORY_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
             </select>
          </div>
        </div>
      )}
    </>
  );
}
