import assert from 'node:assert';
import crypto from 'node:crypto';

const JWT_SECRET = 'sevalor-dev-secret-key-32-chars-long-abc';

function createToken(payload, secret = JWT_SECRET) {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const data = `${header}.${body}`;
  const sig = crypto.createHmac('sha256', secret).update(data).digest('base64url');
  return `${data}.${sig}`;
}

// Emulate NextRequest / NextResponse / Cookies
class MockNextRequest {
  constructor(urlStr, cookies = {}) {
    this.nextUrl = new URL(urlStr, 'http://localhost:3000');
    this.url = this.nextUrl.href;
    this._cookies = new Map(Object.entries(cookies));
    this.cookies = {
      get: (name) => {
        const val = this._cookies.get(name);
        return val !== undefined ? { name, value: val } : undefined;
      },
    };
  }
}

class MockNextResponse {
  constructor(status = 200, headers = {}) {
    this.status = status;
    this.headers = new Map(Object.entries(headers));
    this.cookies = {
      delete: (name) => this.headers.set('set-cookie', `${name}=; Max-Age=0; Path=/`),
    };
  }
  static next() {
    return new MockNextResponse(200);
  }
  static redirect(url) {
    return new MockNextResponse(307, { location: url.toString() });
  }
}

// Implementation under test (same as src/middleware.ts)
function base64UrlToUint8Array(base64Url) {
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

function parseJwtPayload(token) {
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

async function verifyJwt(token, secret) {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const [headerB64, payloadB64, signatureB64] = parts;

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
      sigBytes,
      new TextEncoder().encode(`${headerB64}.${payloadB64}`)
    );

    if (!valid) return null;

    const payload = parseJwtPayload(token);
    if (!payload) return null;

    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return null;
    }

    return payload;
  } catch {
    return null;
  }
}

async function middleware(request) {
  const { pathname } = request.nextUrl;
  const tokenCookie = request.cookies.get('sevalor_access_token');
  const token = tokenCookie?.value;

  const payload = token ? await verifyJwt(token, JWT_SECRET) : null;
  const role = payload?.rol?.toUpperCase();

  const createRedirectWithClearedCookie = (targetUrl) => {
    const response = MockNextResponse.redirect(new URL(targetUrl, request.url));
    if (tokenCookie) {
      response.cookies.delete('sevalor_access_token');
    }
    return response;
  };

  // 1. ZONA GESTIÓ (/gestio)
  if (pathname.startsWith('/gestio')) {
    const isLoginPage = pathname === '/gestio/login' || pathname.startsWith('/gestio/login/');

    if (isLoginPage) {
      if (payload && ['BOSS', 'SECRETARIA', 'ENGINYER', 'COMPTABILITAT', 'SUPERADMIN'].includes(role)) {
        return MockNextResponse.redirect(new URL('/gestio/mapa', request.url));
      }
      return MockNextResponse.next();
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
        return MockNextResponse.redirect(new URL('/superadmin/telemetria', request.url));
      }
      return MockNextResponse.next();
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
        return MockNextResponse.redirect(new URL('/operari/feines', request.url));
      }
      return MockNextResponse.next();
    }

    if (!payload) {
      return createRedirectWithClearedCookie('/operari/login');
    }

    const allowedRoles = ['OPERARI', 'CAPATAZ', 'SUPERADMIN'];
    if (!allowedRoles.includes(role)) {
      return createRedirectWithClearedCookie('/operari/login?error=unauthorized');
    }
  }

  return MockNextResponse.next();
}

async function runTests() {
  console.log("=== INICIANT TESTS AUTOMATITZATS DE FASE 0 (AUTH & MIDDLEWARE) ===\n");

  let passed = 0;
  let total = 0;

  async function testCase(name, fn) {
    total++;
    try {
      await fn();
      console.log(`  ✅ [PASS] ${name}`);
      passed++;
    } catch (err) {
      console.error(`  ❌ [FAIL] ${name}:`, err.message);
    }
  }

  const now = Math.floor(Date.now() / 1000);
  const bossToken = createToken({ sub: 'b1', rol: 'BOSS', exp: now + 3600 });
  const enginyerToken = createToken({ sub: 'e1', rol: 'ENGINYER', exp: now + 3600 });
  const operariToken = createToken({ sub: 'o1', rol: 'OPERARI', exp: now + 3600 });
  const superadminToken = createToken({ sub: 's1', rol: 'SUPERADMIN', exp: now + 3600 });
  const expiredToken = createToken({ sub: 'b1', rol: 'BOSS', exp: now - 3600 });
  const forgedToken = bossToken.substring(0, bossToken.length - 6) + 'xxxxxx';
  const wrongSecretToken = createToken({ sub: 'b1', rol: 'BOSS', exp: now + 3600 }, 'wrong-secret-key-123456789012345');

  // T0.1: Accés sense cookie a /gestio/clients -> Redirect /gestio/login
  await testCase("T0.1: Accés sense cookie a /gestio/clients redirigeix a /gestio/login", async () => {
    const req = new MockNextRequest('/gestio/clients');
    const res = await middleware(req);
    assert(res.status === 307, `Status era ${res.status}`);
    assert(res.headers.get('location')?.includes('/gestio/login'), `Location: ${res.headers.get('location')}`);
  });

  // T0.2: Cookie falsa / manipulada -> Redirect /gestio/login
  await testCase("T0.2: Token manipulat (forged) és rebutjat i redirigit a /gestio/login", async () => {
    const req = new MockNextRequest('/gestio/clients', { sevalor_access_token: forgedToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/gestio/login'));
  });

  // T0.2b: Token signat amb clau incorrecta -> Rebutjat
  await testCase("T0.2b: Token amb clau secreta incorrecta és rebutjat", async () => {
    const req = new MockNextRequest('/gestio/clients', { sevalor_access_token: wrongSecretToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/gestio/login'));
  });

  // T0.3: Token d'operari intentant accedir a /gestio -> Rebutjat
  await testCase("T0.3: Operari intentant accedir a /gestio és bloquejat (Privilege Escalation Protection)", async () => {
    const req = new MockNextRequest('/gestio/clients', { sevalor_access_token: operariToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/gestio/login?error=unauthorized'));
  });

  // T0.4: Token de BOSS accedint a /gestio -> Permès (status 200 / next)
  await testCase("T0.4: Boss amb token vàlid pot accedir a /gestio/clients", async () => {
    const req = new MockNextRequest('/gestio/clients', { sevalor_access_token: bossToken });
    const res = await middleware(req);
    assert(res.status === 200, `Status era ${res.status}`);
  });

  // T0.5: Token d'Enginyer accedint a /gestio -> Permès
  await testCase("T0.5: Enginyer amb token vàlid pot accedir a /gestio/mapa", async () => {
    const req = new MockNextRequest('/gestio/mapa', { sevalor_access_token: enginyerToken });
    const res = await middleware(req);
    assert(res.status === 200, `Status era ${res.status}`);
  });

  // T0.6: Boss intentant entrar a /superadmin -> Bloquejat
  await testCase("T0.6: Boss intentant entrar a /superadmin és bloquejat", async () => {
    const req = new MockNextRequest('/superadmin/telemetria', { sevalor_access_token: bossToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/superadmin/login'));
  });

  // T0.7: Superadmin entrant a /superadmin -> Permès
  await testCase("T0.7: Superadmin amb token vàlid pot accedir a /superadmin/telemetria", async () => {
    const req = new MockNextRequest('/superadmin/telemetria', { sevalor_access_token: superadminToken });
    const res = await middleware(req);
    assert(res.status === 200, `Status era ${res.status}`);
  });

  // T0.8: Operari accedint a /operari/feines -> Permès
  await testCase("T0.8: Operari amb token vàlid pot accedir a /operari/feines", async () => {
    const req = new MockNextRequest('/operari/feines', { sevalor_access_token: operariToken });
    const res = await middleware(req);
    assert(res.status === 200, `Status era ${res.status}`);
  });

  // T0.9: Boss intentant entrar a /operari/feines -> Bloquejat
  await testCase("T0.9: Boss intentant entrar a /operari/feines és redirigit a login d'operari", async () => {
    const req = new MockNextRequest('/operari/feines', { sevalor_access_token: bossToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/operari/login?error=unauthorized'));
  });

  // T0.10: Token expirat -> Rebutjat
  await testCase("T0.10: Token expirat és rebutjat immediatament", async () => {
    const req = new MockNextRequest('/gestio/clients', { sevalor_access_token: expiredToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/gestio/login'));
  });

  // T0.11: Usuari autenticat que visita la pàgina de login -> Redirigit al dashboard
  await testCase("T0.11: Boss autenticat que entra a /gestio/login és redirigit directament a /gestio/mapa", async () => {
    const req = new MockNextRequest('/gestio/login', { sevalor_access_token: bossToken });
    const res = await middleware(req);
    assert(res.status === 307);
    assert(res.headers.get('location')?.includes('/gestio/mapa'));
  });

  console.log(`\n=== RESULTATS: ${passed}/${total} TESTS PASSATS SATISFACTORIAMENT ===`);
  if (passed !== total) {
    process.exit(1);
  }
}

runTests();
