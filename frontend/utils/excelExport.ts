import ExcelJS from 'exceljs';
import { saveAs } from 'file-saver';
import { SpreadsheetState } from '@/app/components/spreadsheet/types';

// Styling constants matching backend HDFC Excel generator exactly
const HEADER_FONT = { bold: true, size: 11 };
const HEADER_FONT_WHITE = { bold: true, size: 11, color: { argb: 'FFFFFFFF' } };
const HEADER_FILL = {
  type: 'pattern' as const,
  pattern: 'solid' as const,
  fgColor: { argb: 'FF1F4E79' }
}; // Dark blue
const SUMMARY_HEADER_FILL = {
  type: 'pattern' as const,
  pattern: 'solid' as const,
  fgColor: { argb: 'FFD9E1F2' }
}; // Light blue
const BORDER = {
  top: { style: 'thin' as const },
  left: { style: 'thin' as const },
  bottom: { style: 'thin' as const },
  right: { style: 'thin' as const }
};
const CENTER = { horizontal: 'center' as const, vertical: 'middle' as const };
const LEFT = { horizontal: 'left' as const, vertical: 'middle' as const };
const RIGHT = { horizontal: 'right' as const, vertical: 'middle' as const };
const CURRENCY_FORMAT = '₹#,##0.00';

export const exportToExcel = async (state: SpreadsheetState) => {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Airco Insights';
  workbook.lastModifiedBy = 'Airco Insights User';
  workbook.created = new Date();
  workbook.modified = new Date();

  state.sheets.forEach((sheet) => {
    const isRaw = sheet.title.includes('Raw Transaction');
    
    // Add worksheet with exact backend naming
    let worksheetName = sheet.title;
    if (worksheetName.includes('Summary')) {
      worksheetName = 'Summary';
    } else if (worksheetName.includes('Category Analysis')) {
      worksheetName = 'Category Analysis';
    } else if (worksheetName.includes('Weekly Analysis')) {
      worksheetName = 'Weekly Analysis';
    } else if (worksheetName.includes('Raw Transaction')) {
      worksheetName = 'Raw Transactions';
    } else if (worksheetName.includes('Bounces')) {
      worksheetName = 'Bounces & Penal';
    } else if (worksheetName.includes('Funds Received')) {
      worksheetName = 'Funds Received';
    } else if (worksheetName.includes('Funds Remittance')) {
      worksheetName = 'Funds Remittance';
    } else if (worksheetName.includes('Source Analysis')) {
      worksheetName = 'Source Analysis';
    } else if (worksheetName.includes('Category Outcome')) {
      worksheetName = 'Category Outcome';
    }
    
    const worksheet = workbook.addWorksheet(worksheetName);

    // Special handling for Raw Transactions sheet - match backend structure exactly
    if (isRaw && sheet.rows.length > 0) {
      // Add STATEMENT SUMMARY section
      let currentRow = 1;
      
      // Calculate summary from data (simulate backend calculations)
      let totalDebits = 0;
      let totalCredits = 0;
      let debitCount = 0;
      let creditCount = 0;
      let closingBalance = 0;
      
      sheet.rows.forEach(row => {
        const debit = parseFloat(row[2]?.replace(/[₹,\s]/g, '') || '0');
        const credit = parseFloat(row[3]?.replace(/[₹,\s]/g, '') || '0');
        const balance = parseFloat(row[5]?.replace(/[₹,\s]/g, '') || '0');
        
        if (debit > 0) {
          totalDebits += debit;
          debitCount++;
        }
        if (credit > 0) {
          totalCredits += credit;
          creditCount++;
        }
        if (balance > 0) {
          closingBalance = balance;
        }
      });

      // Summary header
      const summaryHeaderCell = worksheet.getCell(currentRow, 1);
      summaryHeaderCell.value = "STATEMENT SUMMARY";
      summaryHeaderCell.font = { bold: true, size: 12, color: { argb: 'FFFFFFFF' } };
      summaryHeaderCell.fill = HEADER_FILL;
      summaryHeaderCell.alignment = CENTER;
      summaryHeaderCell.border = BORDER;
      worksheet.mergeCells(currentRow, 1, currentRow, 7);
      currentRow++;

      // Summary column headers
      const summaryHeaders = ["Opening Balance", "Dr Count", "Cr Count", "Debits", "Credits", "Closing Bal"];
      summaryHeaders.forEach((header, colIdx) => {
        const cell = worksheet.getCell(currentRow, colIdx + 1);
        cell.value = header;
        cell.font = HEADER_FONT;
        cell.fill = SUMMARY_HEADER_FILL;
        cell.alignment = CENTER;
        cell.border = BORDER;
      });
      currentRow++;

      // Summary values
      const summaryValues = [0, debitCount, creditCount, totalDebits, totalCredits, closingBalance];
      summaryValues.forEach((value, colIdx) => {
        const cell = worksheet.getCell(currentRow, colIdx + 1);
        cell.value = value;
        cell.border = BORDER;
        cell.alignment = CENTER;
        if (colIdx === 0 || colIdx === 3 || colIdx === 4 || colIdx === 5) { // Amount columns
          cell.numFmt = CURRENCY_FORMAT;
        }
      });
      currentRow += 2; // Add spacing

      // Transaction table headers - exact HDFC format
      const headers = ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"];
      headers.forEach((header, colIdx) => {
        const cell = worksheet.getCell(currentRow, colIdx + 1);
        cell.value = header;
        cell.font = HEADER_FONT_WHITE;
        cell.fill = HEADER_FILL;
        cell.alignment = CENTER;
        cell.border = BORDER;
      });
      currentRow++;

      // Transaction data
      sheet.rows.forEach((row, rowIdx) => {
        const isFlagged = sheet.flaggedRows[rowIdx];
        
        // Map data to exact HDFC format
        const rowData = [
          row[0] || '', // Date
          row[1] || '', // Narration
          '', // Chq./Ref.No. (empty for now)
          '', // Value Dt (empty for now)
          row[2] || '', // Withdrawal Amt.
          row[3] || '', // Deposit Amt.
          row[5] || ''  // Closing Balance
        ];

        const excelRow = worksheet.getRow(currentRow);
        excelRow.values = rowData;

        // Apply styling to each cell
        rowData.forEach((value, colIdx) => {
          const cell = excelRow.getCell(colIdx + 1);
          cell.border = BORDER;
          
          // Apply alignment based on column type
          if (colIdx === 0) { // Date
            cell.alignment = CENTER;
          } else if (colIdx === 1) { // Narration
            cell.alignment = LEFT;
          } else if (colIdx === 2 || colIdx === 3) { // Ref No, Value Dt
            cell.alignment = CENTER;
          } else { // Amount columns
            cell.alignment = RIGHT;
            cell.numFmt = CURRENCY_FORMAT;
          }
        });

        // Apply persisted custom styles from the editor state
        headers.forEach((_, colIdx) => {
          const styleKey = `${rowIdx}-${colIdx}`;
          const customStyle = sheet.styles[styleKey];
          const cell = excelRow.getCell(colIdx + 1);

          if (!customStyle) return;

          const font: ExcelJS.Font = {
            ...(cell.font as ExcelJS.Font || {}),
            bold: customStyle.bold ?? false,
            italic: customStyle.italic ?? false,
            underline: customStyle.underline ?? false,
            size: customStyle.fontSize ?? (cell.font as ExcelJS.Font | undefined)?.size ?? 11,
          };
          if (customStyle.color) {
            font.color = { argb: `FF${customStyle.color.replace('#', '').toUpperCase()}` };
          }
          cell.font = font;

          if (customStyle.bg) {
            cell.fill = {
              type: 'pattern',
              pattern: 'solid',
              fgColor: { argb: `FF${customStyle.bg.replace('#', '').toUpperCase()}` },
            };
          }

          if (customStyle.alignment?.horizontal) {
            cell.alignment = {
              ...(cell.alignment || {}),
              horizontal: customStyle.alignment.horizontal,
              vertical: 'middle',
            };
          }

          if (customStyle.numberFormat) {
            cell.numFmt = customStyle.numberFormat;
          }

          if (customStyle.note) {
            cell.note = customStyle.note;
          }
        });

        excelRow.commit();
        currentRow++;
      });

      // Freeze at transaction header row (after summary section)
      const freezeRow = currentRow - sheet.rows.length;
      worksheet.views = [{ state: 'frozen', ySplit: freezeRow - 1 }];

      // Column widths - Match HDFC format exactly
      const columnWidths = [12, 50, 18, 12, 18, 18, 18];
      columnWidths.forEach((width, idx) => {
        worksheet.getColumn(idx + 1).width = width;
      });

    } else {
      // Handle other sheets with standard formatting
      // Setup frozen headers - match backend pattern
      if (sheet.title === 'Summary') {
        worksheet.views = [{ state: 'frozen', ySplit: 4 }]; // Freeze first 4 rows for Summary
      } else {
        worksheet.views = [
          { state: 'frozen', xSplit: isRaw ? 2 : 1, ySplit: 1 } // Freeze 1st row and Col A (and Col B if flag col is present)
        ];
      }

      // Determine actual headers
      const headers = isRaw ? ['Flag', ...sheet.headers] : sheet.headers;
      const headerRow = worksheet.addRow(headers);
      
      // Apply header styling matching backend
      headerRow.eachCell((cell, colNumber) => {
        cell.font = HEADER_FONT_WHITE;
        cell.fill = HEADER_FILL;
        cell.alignment = CENTER;
        cell.border = BORDER;
      });
      headerRow.commit();

      // Map rows with proper styling
      sheet.rows.forEach((r, rowIdx) => {
        const isFlagged = isRaw && sheet.flaggedRows[rowIdx];
        let rowData: string[] = [];
        if (isRaw) {
          rowData = [isFlagged ? 'FLAGGED' : '', ...r];
        } else {
          rowData = [...r];
        }

        const excelRow = worksheet.addRow(rowData);
        
        // Apply base borders to all cells
        excelRow.eachCell((cell, colNumber) => {
          cell.border = BORDER;
          
          // Apply red fill for flagged rows
          if (isFlagged && colNumber === 1) {
            cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFCCCC' } }; // Light red
          }
        });
        
        // Apply cell-specific styling
        headers.forEach((_, colIdx) => {
           const realCol = isRaw ? colIdx - 1 : colIdx;
           const styleKey = `${rowIdx}-${realCol}`;
           const customStyle = sheet.styles[styleKey];
           
           const cell = excelRow.getCell(colIdx + 1); // 1-indexed
           
           if (customStyle) {
              // Apply custom formatting on top of base formatting
              const font: ExcelJS.Font = {
                ...(cell.font as ExcelJS.Font || {}),
                bold: customStyle.bold ?? false,
                italic: customStyle.italic ?? false,
                underline: customStyle.underline ?? false,
                size: customStyle.fontSize ?? (cell.font as ExcelJS.Font | undefined)?.size ?? 11,
              };
              if (customStyle.color) {
                font.color = { argb: 'FF' + customStyle.color.replace('#', '').toUpperCase() };
              }
              cell.font = font;

              if (customStyle.bg) {
                cell.fill = {
                  type: 'pattern',
                  pattern: 'solid',
                  fgColor: { argb: 'FF' + customStyle.bg.replace('#', '').toUpperCase() }
                };
              }
              if (customStyle.alignment?.horizontal) {
                cell.alignment = { horizontal: customStyle.alignment.horizontal, vertical: 'middle' };
              }
              if (customStyle.numberFormat) {
                cell.numFmt = customStyle.numberFormat;
              }
              if (customStyle.note) {
                cell.note = customStyle.note;
              }
           }
           
           // Apply number formatting based on content and header
           const headerName = headers[colIdx]?.toLowerCase() || '';
           const cellValue = cell.value;
           
           if (typeof cellValue === 'string' || typeof cellValue === 'number') {
             const numValue = typeof cellValue === 'string' ? parseFloat(cellValue.replace(/[₹,\s]/g, '')) : cellValue;
             
             if (!isNaN(numValue)) {
               // Currency formatting for amount columns
               if (headerName.includes('amount') || headerName.includes('balance') || 
                   headerName.includes('credit') || headerName.includes('debit')) {
                 cell.numFmt = CURRENCY_FORMAT;
                 cell.alignment = RIGHT;
               }
             }
           }
        });
        excelRow.commit();
      });

      // Apply column widths matching backend patterns
      worksheet.columns.forEach((col, idx) => {
        const headerName = headers[idx] || '';
        
        // Determine width based on content type and header
        let targetWidth = 18; // DEFAULT_COLUMN_WIDTH
        
        // Text columns get wider
        if (headerName.toLowerCase().includes('description') || 
            headerName.toLowerCase().includes('category') ||
            headerName.toLowerCase().includes('name') ||
            headerName.toLowerCase().includes('narration')) {
          targetWidth = 25; // TEXT_COLUMN_WIDTH
        }
        
        // Calculate content-based width
        let maxLen = headerName.length;
        sheet.rows.forEach(r => {
          const val = isRaw ? (idx === 0 ? '' : r[idx - 1]) : r[idx];
          if (val && val.toString().length > maxLen) {
            maxLen = val.toString().length;
          }
        });
        
        // Use the larger of content-based or type-based width
        col.width = Math.min(Math.max(maxLen + 2, targetWidth), 50);
      });
    }
  });

  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  saveAs(blob, 'Airco_Insights_Report.xlsx');
};
