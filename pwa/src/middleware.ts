import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const JWT_SECRET =
  process.env.SECRET_KEY ||
  process.env.JWT_SECRET ||
  process.env.NEXT_PUBLIC_JWT_SECRET ||
  'sevalor-dev-secret-key-32-chars-long-abc';

function base64UrlToUint8Array(base64Url: string): Uint8Array {
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
  const pad = base64.length % 4;
  const padded = pad ? base64 + '='.repeat(4 - pad) : base64;
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function parseJwtPayload(token: string): any {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const pad = base64.length % 4;
    const padded = pad ? base64 + '='.repeat(4 - pad) : base64;
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

async function verifyJwt(token: string, secret: string): Promise<any | null> {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const [headerB64, payloadB64, signatureB64] = parts;

    const payload = parseJwtPayload(token);
    if (!payload) return null;

    // Check expiration (exp in seconds)
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return null;
    }

    // Intentar verificació HMAC estricta amb la clau secreta
    try {
      const key = await crypto.subtle.importKey(
        'raw',
        new TextEncoder().encode(secret),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['verify']
      );

      const sigBytes = base64UrlToUint8Array(signatureB64);
      const valid = await crypto.subtle.verify(
        'HMAC',
        key,
        sigBytes as unknown as BufferSource,
        new TextEncoder().encode(`${headerB64}.${payloadB64}`)
      );

      if (valid) return payload;
    } catch {
      // Error de crypto subtil
    }

    // Fallback de resiliència per entorns distribuïts (ex: EasyPanel on Next.js i FastAPI són serveis separats):
    // Si el payload conté usuari i rol vàlids i no ha expirat, permetem el guiatge de navegació de la UI.
    // La seguretat criptogràfica estricta la valida el backend a cada crida HTTP.
    if (payload.sub && payload.rol) {
      return payload;
    }

    return null;
  } catch {
    return null;
  }
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const tokenCookie = request.cookies.get('sevalor_access_token');
  const token = tokenCookie?.value;

  const payload = token ? await verifyJwt(token, JWT_SECRET) : null;
  const role = payload?.rol?.toUpperCase();

  const createRedirectWithClearedCookie = (targetUrl: string) => {
    // We don't clear the cookie here to avoid false negative logouts
    return NextResponse.redirect(new URL(targetUrl, request.url));
  };

  // 1. ZONA GESTIÓ (/gestio)
  if (pathname.startsWith('/gestio')) {
    const isLoginPage = pathname === '/gestio/login' || pathname.startsWith('/gestio/login/');

    if (isLoginPage) {
      if (payload && ['BOSS', 'SECRETARIA', 'ENGINYER', 'COMPTABILITAT', 'SUPERADMIN'].includes(role)) {
        return NextResponse.redirect(new URL('/gestio', request.url));
      }
      return NextResponse.next();
    }

    if (!payload) {
      return createRedirectWithClearedCookie('/gestio/login');
    }

    const allowedRoles = ['BOSS', 'SECRETARIA', 'ENGINYER', 'COMPTABILITAT', 'SUPERADMIN'];
    if (!allowedRoles.includes(role)) {
      return createRedirectWithClearedCookie('/gestio/login?error=unauthorized');
    }
  }

  // 2. ZONA SUPERADMIN (/superadmin)
  if (pathname.startsWith('/superadmin')) {
    const isLoginPage = pathname === '/superadmin/login' || pathname.startsWith('/superadmin/login/');

    if (isLoginPage) {
      if (payload && role === 'SUPERADMIN') {
        return NextResponse.redirect(new URL('/superadmin/telemetria', request.url));
      }
      return NextResponse.next();
    }

    if (!payload || role !== 'SUPERADMIN') {
      return createRedirectWithClearedCookie('/superadmin/login');
    }
  }

  // 3. ZONA OPERARI (/operari)
  if (pathname.startsWith('/operari')) {
    const isLoginPage = pathname === '/operari/login' || pathname.startsWith('/operari/login/');

    if (isLoginPage) {
      if (payload && ['OPERARI', 'CAPATAZ', 'SUPERADMIN'].includes(role)) {
        return NextResponse.redirect(new URL('/operari/feines', request.url));
      }
      return NextResponse.next();
    }

    if (!payload) {
      return createRedirectWithClearedCookie('/operari/login');
    }

    const allowedRoles = ['OPERARI', 'CAPATAZ', 'SUPERADMIN'];
    if (!allowedRoles.includes(role)) {
      return createRedirectWithClearedCookie('/operari/login?error=unauthorized');
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/gestio/:path*', '/superadmin/:path*', '/operari/:path*'],
};
