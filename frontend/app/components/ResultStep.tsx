'use client'

import { useState, useEffect } from 'react'
import { ProcessingResult, SheetPreview } from '@/types'
import CollapsiblePreview from './CollapsiblePreview'
import DownloadButtons from './DownloadButtons'
import FeedbackSection from './FeedbackSection'
import { CheckCircle2, Eye, FileSpreadsheet } from 'lucide-react'
import SpreadsheetEditor from './spreadsheet/SpreadsheetEditor'
import { SpreadsheetProvider } from './spreadsheet/SpreadsheetContext'

interface ResultStepProps {
  result: ProcessingResult
}

const PLACEHOLDER_SHEETS: SheetPreview[] = [
  {
    title: 'Sheet 1 — Summary',
    headers: ['Metric', 'Value'],
    rows: [],
  },
  {
    title: 'Sheet 2 — Monthly Analysis',
    headers: ['Metric / Category'],
    rows: [],
  },
  {
    title: 'Sheet 3 — Weekly Analysis',
    headers: ['Week', 'Credit Amount', 'Credit Count', 'Debit Amount', 'Debit Count'],
    rows: [],
  },
  {
    title: 'Sheet 4 — Category Analysis',
    headers: ['Category', 'Amount', 'Count'],
    rows: [],
  },
  {
    title: 'Sheet 5 — Bounces & Penal',
    headers: ['Sl. No.', 'Bank Name', 'Account Number', 'Date', 'Cheque No.', 'Description', 'Amount', 'Category', 'Balance'],
    rows: [],
  },
  {
    title: 'Sheet 6 — Funds Received',
    headers: ['Sl. No.', 'Debit Account Number', 'Date', 'Description', 'Amount', 'Category', 'Balance'],
    rows: [],
  },
  {
    title: 'Sheet 7 — Funds Remittance',
    headers: ['Sl. No.', 'Beneficiary Account', 'Date', 'Description', 'Amount', 'Category', 'Balance'],
    rows: [],
  },
  {
    title: 'Sheet 8 — Raw Transaction',
    headers: ['Date', 'Description', 'Debit', 'Credit', 'Balance', 'Category', 'Confidence', 'Recurring'],
    rows: [],
  },
]

export default function ResultStep({ result }: ResultStepProps) {
  const [viewMode, setViewMode] = useState<'preview' | 'review'>('preview')
  const [expandedSheets, setExpandedSheets] = useState<Set<number>>(new Set())
  const [isDesktop, setIsDesktop] = useState(false)

  useEffect(() => {
    setIsDesktop(window.innerWidth >= 1024)
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const sheets: SheetPreview[] = [
    result.account_summary || PLACEHOLDER_SHEETS[0],     // Sheet 1 — Summary
    result.monthly_analysis || PLACEHOLDER_SHEETS[1],    // Sheet 2 — Monthly Analysis
    result.weekly_analysis || PLACEHOLDER_SHEETS[2],     // Sheet 3 — Weekly Analysis
    result.category_analysis || PLACEHOLDER_SHEETS[3],   // Sheet 4 — Category Analysis
    result.bounces_penal || PLACEHOLDER_SHEETS[4],       // Sheet 5 — Bounces & Penal
    result.funds_received || PLACEHOLDER_SHEETS[5],      // Sheet 6 — Funds Received
    result.funds_remittance || PLACEHOLDER_SHEETS[6],    // Sheet 7 — Funds Remittance
    result.raw_transactions || PLACEHOLDER_SHEETS[7],    // Sheet 8 — Raw Transaction
  ]

  const modeLabel = result.mode === 'hybrid' ? 'Hybrid (System + AI)' : 'Free (System Only)'

  const toggleSheetExpansion = (index: number) => {
    const newExpanded = new Set(expandedSheets)
    if (newExpanded.has(index)) {
      newExpanded.delete(index)
    } else {
      newExpanded.add(index)
    }
    setExpandedSheets(newExpanded)
  }

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 className="w-6 h-6 text-black" />
        <h2 className="text-xl font-semibold text-black">
          Categorization Complete
        </h2>
      </div>
      <p className="text-base text-neutral-500 mb-4">
        Your statement has been categorized and structured. Preview or download below.
      </p>

      {/* View Options */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-neutral-600 bg-neutral-100 border border-neutral-200 px-3 py-1.5 rounded-full">
            {modeLabel}
          </span>
          {result.stats && (
            <>
              <span className="text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 px-3 py-1.5 rounded-full">
                {result.stats.total_transactions} transactions
              </span>
              <span className="text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 px-3 py-1.5 rounded-full">
                {result.stats.coverage_percent}% categorized
              </span>
              {result.stats.ai_classified > 0 && (
                <span className="text-xs text-neutral-500 bg-neutral-50 border border-neutral-200 px-3 py-1.5 rounded-full">
                  {result.stats.ai_classified} AI classified
                </span>
              )}
            </>
          )}
          {result.ai_usage && (
            <span className="text-xs text-neutral-500 bg-blue-50 border border-blue-200 px-3 py-1.5 rounded-full">
              AI Cost: ${result.ai_usage.estimated_cost_usd?.toFixed(4)} (~₹{result.ai_usage.estimated_cost_inr?.toFixed(2)})
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode('preview')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${viewMode === 'preview'
              ? 'bg-black text-white'
              : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
              }`}
          >
            <Eye className="w-3.5 h-3.5" />
            Preview
          </button>
          {isDesktop && (
            <button
              onClick={() => setViewMode('review')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${viewMode === 'review'
                ? 'bg-black text-white'
                : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'
                }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5" />
              Review Data
            </button>
          )}
        </div>
      </div>

      {viewMode === 'preview' && (
        <div className="space-y-3">
          {sheets.map((sheet, idx) => (
            <CollapsiblePreview key={idx} sheet={sheet} />
          ))}
        </div>
      )}

      {viewMode === 'review' && (
        <SpreadsheetProvider>
          <SpreadsheetEditor 
            initialResult={result} 
            onExit={() => setViewMode('preview')} 
            apiKey={result.mode === 'hybrid' ? 'requires-auth-key-passthrough-if-needed' : ''} 
          />
        </SpreadsheetProvider>
      )}

      <DownloadButtons
        excelUrl={result.excel_url}
        pdfUrl={result.pdf_url}
      />

      <FeedbackSection />

      {/* Legal Disclaimer */}
      <p className="text-xs text-neutral-300 text-center mt-6 leading-relaxed">
        This report contains categorized transaction data only. No financial advice, predictions, or recommendations are provided.
      </p>
    </div>
  )
}
