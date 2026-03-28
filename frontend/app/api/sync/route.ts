import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  console.log('=== SYNC ROUTE DEBUG ===');
  console.log('BACKEND_URL:', BACKEND_URL);
  console.log('Environment variables:', {
    BACKEND_URL: process.env.BACKEND_URL,
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL
  });
  
  if (!BACKEND_URL || BACKEND_URL === 'undefined') {
    console.error('BACKEND_URL is undefined or invalid');
    return NextResponse.json(
      { message: 'Backend URL not configured' },
      { status: 500 }
    );
  }

  try {
    const body = await request.json();
    console.log('Received request body:', JSON.stringify(body, null, 2));

    // The user's prompt specifically said:
    // "Sends the full updated dataset to the existing backend API via a POST or PUT request — use the same endpoint/auth pattern already in the codebase"
    
    // So we fetch BACKEND_URL/sync (assuming backend expects a JSON payload at /sync or similar endpoint)
    // If we need authorization headers via API key, it passes them exactly like the codebase does.
    const apiKey = body.api_key;
    const backendPayload = {
      sheets: body.sheets
    };
    
    console.log('Sending to backend:', `${BACKEND_URL}/api/sync`);
    console.log('Backend payload:', JSON.stringify(backendPayload, null, 2));
    console.log('Headers:', {
      'Content-Type': 'application/json',
      ...(apiKey && { 'Authorization': `Bearer ${apiKey}` })
    });
    
    // We send to /api/sync on backend
    const response = await fetch(`${BACKEND_URL}/api/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(apiKey && { 'Authorization': `Bearer ${apiKey}` })
      },
      body: JSON.stringify(backendPayload),
    });

    console.log('Backend response status:', response.status);
    console.log('Backend response headers:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      console.error('Backend error response:', errorData);
      return NextResponse.json(
        { message: errorData?.detail || 'Sync failed on backend' },
        { status: response.status }
      );
    }

    const result = await response.json();
    console.log('Backend success response:', result);
    console.log('=== END SYNC ROUTE DEBUG ===');
    return NextResponse.json(result);
  } catch (error) {
    console.error('Sync route error:', error);
    console.error('Error details:', {
      message: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
      name: error instanceof Error ? error.name : 'Unknown'
    });
    console.log('=== END SYNC ROUTE DEBUG ===');
    const msg = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { message: `Cannot reach backend server (${msg}).` },
      { status: 502 }
    );
  }
}
