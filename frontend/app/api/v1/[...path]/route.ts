import { NextRequest, NextResponse } from 'next/server';

async function handleRequest(req: NextRequest, { params }: { params: { path: string[] } }) {
  try {
    const url = new URL(req.url);
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001/api/v1';
    const backendUrl = `${baseUrl}/${params.path.join('/')}${url.search}`;
    
    const headers = new Headers();
    req.headers.forEach((value, key) => {
      if (key.toLowerCase() !== 'host') {
        headers.set(key, value);
      }
    });
    
    const init: RequestInit = {
      method: req.method,
      headers,
    };
    
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      const text = await req.text();
      if (text) init.body = text;
    }
    
    const response = await fetch(backendUrl, init);
    
    const resHeaders = new Headers();
    response.headers.forEach((value, key) => {
      resHeaders.set(key, value);
    });
    
    return new NextResponse(response.body, {
      status: response.status,
      headers: resHeaders
    });
  } catch (error: any) {
    console.error('Proxy Error:', error);
    return NextResponse.json({ error: 'Proxy Error', detail: error.message }, { status: 500 });
  }
}

export const GET = handleRequest;
export const POST = handleRequest;
export const PUT = handleRequest;
export const DELETE = handleRequest;
export const PATCH = handleRequest;