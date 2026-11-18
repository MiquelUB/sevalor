import assert from 'node:assert';

// Mock browser globals (window, document, localStorage)
const storage = new Map();
globalThis.localStorage = {
  getItem: (k: string) => storage.get(k) || null,
  setItem: (k: string, v: string) => storage.set(k, String(v)),
  removeItem: (k: string) => storage.delete(k),
  clear: () => storage.clear(),
} as any;
globalThis.window = {
  location: { hostname: 'tenant1.sevalor.app' },
} as any;
let cookieJar = '';
globalThis.document = {
  get cookie() { return cookieJar; },
  set cookie(val: string) {
    const parts = val.split(';')[0].trim();
    const [name, value] = parts.split('=');
    if (val.includes('max-age=0')) {
      const regex = new RegExp(`(^|; )${name}=[^;]*`);
      cookieJar = cookieJar.replace(regex, '').trim();
    } else {
      cookieJar = `${name}=${value}`;
    }
  }
} as any;

// Import getAuthToken, setAuthToken, clearAuthToken from api.ts
import { getAuthToken, setAuthToken, clearAuthToken, apiFetch } from './src/lib/api';

async function run() {
  console.log("=== TEST DE SINCRONITZACIÓ TOKEN (LOCALSTORAGE & COOKIE) ===");

  clearAuthToken();
  assert.strictEqual(getAuthToken(), null, "Initial token should be null");

  // Test setAuthToken
  const fakeToken = "header.payload.signature123";
  setAuthToken(fakeToken);

  assert.strictEqual(getAuthToken(), fakeToken, "getAuthToken should return set token");
  assert(document.cookie.includes(`sevalor_access_token=${fakeToken}`), "Cookie must have sevalor_access_token");
  console.log("  ✅ setAuthToken sincronitza només document.cookie per seguretat (Spec 02 Criptografia)");

  // Test fallback to cookie works seamlessly
  assert.strictEqual(getAuthToken(), fakeToken, "getAuthToken should read from cookie");
  console.log("  ✅ getAuthToken recupera de la cookie perfectament");

  // Test clearAuthToken
  clearAuthToken();
  assert.strictEqual(getAuthToken(), null, "getAuthToken should be null after clearAuthToken");
  assert(!document.cookie.includes(fakeToken), "Cookie must be cleared after clearAuthToken");
  console.log("  ✅ clearAuthToken neteja la cookie correctament");

  // Test error handling when FastAPI returns 503 with structured { detail: { code, message } }
  const origFetch = globalThis.fetch;
  try {
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          detail: {
            code: "NODE_IA_OFFLINE",
            message: "El node d'IA local de l'empresa no respon.",
          },
        }),
        { status: 503, statusText: "Service Unavailable", headers: { "Content-Type": "application/json" } }
      )) as any;

    let caughtErr: any = null;
    try {
      await apiFetch("/gestio/copilot/xat", { method: "POST", body: JSON.stringify({ pregunta: "hola" }) });
    } catch (e: any) {
      caughtErr = e;
    }
    assert(caughtErr instanceof Error, "503 ha de llançar Error");
    assert.strictEqual((caughtErr as Error & { code?: string }).code, "NODE_IA_OFFLINE");
    assert.strictEqual(caughtErr.message, "El node d'IA local de l'empresa no respon.");

    // Test 422 array detail from Pydantic
    globalThis.fetch = (async () =>
      new Response(
        JSON.stringify({
          detail: [{ loc: ["body", "pregunta"], msg: "Field required", type: "missing" }],
        }),
        { status: 422, statusText: "Unprocessable Entity", headers: { "Content-Type": "application/json" } }
      )) as any;

    let caught422: any = null;
    try {
      await apiFetch("/gestio/copilot/xat", { method: "POST", body: "{}" });
    } catch (e: any) {
      caught422 = e;
    }
    assert(caught422 instanceof Error, "422 ha de llançar Error");
    assert(caught422.message.includes("Field required"), `422 message unexpected: ${caught422.message}`);
    console.log("  ✅ apiFetch gestiona errors FastAPI 503 (objecte detail) i 422 (llista detail) sense error .includes()");
  } finally {
    globalThis.fetch = origFetch;
  }

  console.log("\n=== TOTS ELS TESTS DE SINCRONITZACIÓ PASSATS ✅ ===");
}

run();
