import assert from "node:assert";
import {
  encryptWithPin,
  decryptWithPin,
  verifySentinelBlock,
  SENTINEL_PLAINTEXT,
} from "./src/lib/crypto";

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
