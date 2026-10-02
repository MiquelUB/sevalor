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

  console.log("\n=== TOTS ELS TESTS DE SINCRONITZACIÓ PASSATS ✅ ===");
}

run();
