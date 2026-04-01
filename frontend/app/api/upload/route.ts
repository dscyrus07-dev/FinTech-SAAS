import { NextRequest, NextResponse } from 'next/server'

// Use server-side env var (not NEXT_PUBLIC_) for Docker internal networking.
// Inside Docker: backend service is at http://backend:8000
// Local dev: fallback to http://localhost:8000
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()

    const file = formData.get('file')
    if (!file || !(file instanceof Blob)) {
      return NextResponse.json(
        { message: 'No PDF file provided.' },
        { status: 400 }
      )
    }

    const backendForm = new FormData()
    backendForm.append('file', file)
    backendForm.append('full_name', formData.get('full_name') as string || '')
    backendForm.append('account_type', formData.get('account_type') as string || '')
    backendForm.append('bank_name', formData.get('bank_name') as string || '')
    backendForm.append('mode', formData.get('mode') as string || 'free')

    const apiKey = formData.get('api_key') as string
    if (apiKey) {
      backendForm.append('api_key', apiKey)
    }

    const pdfPassword = formData.get('pdf_password') as string
    if (pdfPassword) {
      backendForm.append('pdf_password', pdfPassword)
    }

    console.log(`Forwarding to backend: ${BACKEND_URL}/process`)

    const response = await fetch(`${BACKEND_URL}/process`, {
      method: 'POST',
      body: backendForm,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => null)

      // FastAPI may return detail as a plain string OR as a structured object
      // e.g. { detail: { error: "...", stage: "...", code: "..." } }
      const raw = errorData?.detail
      let errorText: string
      if (typeof raw === 'string') {
        errorText = raw
      } else if (raw && typeof raw === 'object') {
        errorText = (raw as { error?: string; message?: string }).error
          || (raw as { error?: string; message?: string }).message
          || 'Processing failed. Please try again.'
      } else if (typeof errorData?.message === 'string') {
        errorText = errorData.message
      } else {
        errorText = 'Processing failed. Please try again.'
      }

      // Friendly messages for known error types
      const lower = errorText.toLowerCase()
      if (response.status === 422 || lower.includes('unsupported')) {
        errorText = 'This bank is not yet supported. Currently available: HDFC, ICICI, Axis, Kotak. More banks coming soon.'
      } else if (lower.includes('scanned') || lower.includes('image') || lower.includes('scanned_pdf')) {
        errorText = 'This PDF appears to be a scanned image and cannot be processed. Please upload a text-based PDF downloaded directly from your bank\'s internet banking portal.'
      } else if (lower.includes('invalid file') || lower.includes('invalid_file')) {
        errorText = 'Invalid file. Please upload a valid bank statement PDF (max 20 MB).'
      } else if (lower.includes('password')) {
        errorText = 'Your PDF appears to be password-protected. Please upload an unprotected version.'
      } else if (lower.includes('no transactions') || lower.includes('no_transactions')) {
        errorText = 'Could not read transactions from this PDF. Please ensure it is a valid, text-based bank statement (not a scanned image) downloaded from your bank\'s portal.'
      } else if (lower.includes('parse') || lower.includes('extract')) {
        errorText = 'Could not read transactions from this PDF. Please ensure it is a valid, text-based bank statement (not a scanned image).'
      } else if (response.status >= 500 && (!errorText || errorText === 'Processing failed. Please try again.')) {
        errorText = 'An unexpected error occurred while processing your statement. Please try again or contact support.'
      }

      console.error('Backend error:', response.status, errorText)
      return NextResponse.json(
        { message: errorText },
        { status: response.status }
      )
    }

    const result = await response.json()

    // Rewrite backend download URLs to frontend proxy URLs
    // Backend returns /download/file.xlsx → Frontend needs /api/download/file.xlsx
    if (result.excel_url && result.excel_url.startsWith('/download/')) {
      result.excel_url = '/api' + result.excel_url
    }
    if (result.pdf_url && result.pdf_url.startsWith('/download/')) {
      result.pdf_url = '/api' + result.pdf_url
    }

    return NextResponse.json(result)
  } catch (error) {
    console.error('Upload route error:', error)
    const msg = error instanceof Error ? error.message : 'Unknown error'
    return NextResponse.json(
      { message: `Cannot reach backend server (${msg}). Is the backend running?` },
      { status: 502 }
    )
  }
}
