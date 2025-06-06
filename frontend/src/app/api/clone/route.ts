import { NextRequest } from 'next/server';

export const runtime = 'nodejs';

async function proxyClone(url: string) {
  const backend = process.env.BACKEND_ORIGIN ?? 'http://localhost:8000';
  const target = `${backend}/clone?url=${encodeURIComponent(url)}`;
  
  console.log(`Proxying to: ${target}`);
  
  try {
    const res = await fetch(target, { 
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}), // Send empty JSON body
    });
    
    console.log(`FastAPI Response: ${res.status} ${res.statusText}`);
    
    if (!res.ok) {
      const errorText = await res.text();
      console.error(`FastAPI Error: ${errorText}`);
      return new Response(`Backend Error: ${res.status} - ${errorText}`, {
        status: res.status,
        headers: { 'Content-Type': 'text/plain' },
      });
    }
    
    return new Response(res.body, {
      status: res.status,
      headers: { 
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache',
      },
    });
  } catch (error) {
    console.error('Proxy Error:', error);
    return new Response(`Proxy Error: ${error}`, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' },
    });
  }
}

// POST /api/clone
export async function POST(req: NextRequest) {
  console.log('API Route called with POST');
  
  let url: string | null = null;

  // Try JSON body first
  try {
    const body = await req.json();
    url = body?.url ?? null;
    console.log(`URL from JSON body: ${url}`);
  } catch (error) {
    console.log('No JSON body, trying query params');
  }

  // Fallback to query string
  if (!url) {
    url = req.nextUrl.searchParams.get('url');
    console.log(`URL from query params: ${url}`);
  }

  if (!url) {
    console.error('No URL provided');
    return new Response('Missing "url" parameter', { status: 400 });
  }

  return proxyClone(url);
}
export async function GET(req: NextRequest) {
  console.log('API Route called with GET');
  
  const url = req.nextUrl.searchParams.get('url');
  console.log(`URL from GET params: ${url}`);
  
  if (!url) {
    return new Response('Missing "url" parameter', { status: 400 });
  }
  
  return proxyClone(url);
}