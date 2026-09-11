/**
 * Test de Verificació Web Crypto API (Tasca 2.4)
 * Valida PBKDF2 (100.000 iteracions) + AES-GCM-256 + SEVALOR_SENTINEL en Node 20
 */

import assert from "node:assert";

// Implementació equivalent executable directament en Node.js per a test
const SENTINEL_PLAINTEXT = "SEVALOR_SENTINEL";
const PBKDF2_ITERATIONS = 100000;

function buf2hex(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function hex2buf(hexString) {
  const bytes = new Uint8Array(hexString.length / 2);
  for (let i = 0; i < hexString.length; i += 2) {
    bytes[i / 2] = parseInt(hexString.substring(i, i + 2), 16);
  }
  return bytes;
}

async function deriveKeyFromPin(pin, salt) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    enc.encode(pin),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: salt,
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

async function encryptWithPin(plainText, pin, salt) {
  const key = await deriveKeyFromPin(pin, salt);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = new TextEncoder();

  const encryptedBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv },
    key,
    enc.encode(plainText)
  );

  return {
    cipherTextHex: buf2hex(encryptedBuffer),
    ivHex: buf2hex(iv),
  };
}

async function decryptWithPin(cipherTextHex, ivHex, pin, salt) {
  const key = await deriveKeyFromPin(pin, salt);
  const iv = hex2buf(ivHex);
  const cipherBuffer = hex2buf(cipherTextHex);

  const decryptedBuffer = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: iv },
    key,
    cipherBuffer
  );

  const dec = new TextDecoder();
  return dec.decode(decryptedBuffer);
}

async function verifySentinelBlock(pin, salt, cipherTextHex, ivHex) {
  try {
    const decrypted = await decryptWithPin(cipherTextHex, ivHex, pin, salt);
    return decrypted === SENTINEL_PLAINTEXT;
  } catch {
    return false;
  }
}

async function runTests() {
  console.log("=== INICIANT TEST CRIPTOGRÀFIC TASCA 2.4 (SEVALOR_SENTINEL) ===");

  const salt = crypto.getRandomValues(new Uint8Array(16));
  const pinCorrecte = "4826";
  const pinIncorrecte = "1234";

  // 1. Crear bloc sentinella amb PIN correcte
  console.log("1. Generant bloc sentinella xifrat amb PBKDF2 (100.000 iteracions) + AES-GCM-256...");
  const t0 = performance.now();
  const sentinel = await encryptWithPin(SENTINEL_PLAINTEXT, pinCorrecte, salt);
  const t1 = performance.now();
  console.log(`   Bloc generat en ${(t1 - t0).toFixed(2)} ms. IV: ${sentinel.ivHex}`);

  // 2. Validar desxifratge amb PIN correcte
  console.log("2. Verificant desbloqueig offline amb PIN correcte (4826)...");
  const valid = await verifySentinelBlock(pinCorrecte, salt, sentinel.cipherTextHex, sentinel.ivHex);
  assert.strictEqual(valid, true, "El bloc sentinella s'hauria de validar amb el PIN correcte");
  console.log("   -> OK! Desxifratge del sentinella 'SEVALOR_SENTINEL' reeixit.");

  // 3. Validar rebuig amb PIN incorrecte
  console.log("3. Verificant bloqueig amb PIN incorrecte (1234)...");
  const invalid = await verifySentinelBlock(pinIncorrecte, salt, sentinel.cipherTextHex, sentinel.ivHex);
  assert.strictEqual(invalid, false, "El bloc sentinella ha de rebutjar el PIN incorrecte");
  console.log("   -> OK! Accés denegat correctament per fallada d'autenticitat AES-GCM.");

  // 4. Prova de xifratge de token JWT (Zero plaintext tokens)
  console.log("4. Verificant xifratge de token JWT d'operari per a IndexedDB...");
  const jwtToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3OCJ9.signature";
  const encryptedToken = await encryptWithPin(jwtToken, pinCorrecte, salt);
  assert.notStrictEqual(encryptedToken.cipherTextHex, jwtToken);

  const decryptedToken = await decryptWithPin(encryptedToken.cipherTextHex, encryptedToken.ivHex, pinCorrecte, salt);
  assert.strictEqual(decryptedToken, jwtToken);
  console.log("   -> OK! Token JWT xifrat i desxifrat amb integritat absoluta.");

  console.log("\n✅ TOTS ELS CRITERIS DE LA TASCA 2.4 S'HAN VALIDAT AMB ÈXIT.");
}

runTests().catch((err) => {
  console.error("Error en el test criptogràfic:", err);
  process.exit(1);
});
