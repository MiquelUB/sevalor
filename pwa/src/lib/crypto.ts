/**
 * Mòdul Criptogràfic Web Crypto API per a la PWA de Sevalor Suite (Offline-First)
 * Compleix el Mandat 2 de la Constitució de Sevalor Suite (v3.1) i la Spec 019 (RF-05, RF-06).
 *
 * - PBKDF2 amb 100.000 iteracions i SHA-256
 * - AES-GCM de 256 bits amb IV aleatori de 12 bytes
 * - Validació contra el bloc sentinella SEVALOR_SENTINEL
 * - Tolerància Zero a tokens en text pla a localStorage / IndexedDB
 */

export const SENTINEL_PLAINTEXT = "SEVALOR_SENTINEL";
export const PBKDF2_ITERATIONS = 100000;

/**
 * Converteix un ArrayBuffer o Uint8Array a string hexadecimal.
 */
export function buf2hex(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/**
 * Converteix una cadena hexadecimal a Uint8Array.
 */
export function hex2buf(hexString: string): Uint8Array {
  const bytes = new Uint8Array(hexString.length / 2);
  for (let i = 0; i < hexString.length; i += 2) {
    bytes[i / 2] = parseInt(hexString.substring(i, i + 2), 16);
  }
  return bytes;
}

/**
 * Deriva una clau criptogràfica AES-GCM de 256 bits a partir d'un PIN de 4 dígits utilitzant PBKDF2.
 */
export async function deriveKeyFromPin(
  pin: string,
  salt: Uint8Array
): Promise<CryptoKey> {
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
      salt: salt as any,
      iterations: PBKDF2_ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

/**
 * Xifra una cadena de text pla mitjançant AES-GCM de 256 bits amb la clau derivada del PIN.
 */
export async function encryptWithPin(
  plainText: string,
  pin: string,
  salt: Uint8Array
): Promise<{ cipherTextHex: string; ivHex: string }> {
  const key = await deriveKeyFromPin(pin, salt);
  const iv = crypto.getRandomValues(new Uint8Array(12)); // 96-bit IV recomanat per a AES-GCM
  const enc = new TextEncoder();

  const encryptedBuffer = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv as any },
    key,
    enc.encode(plainText)
  );

  return {
    cipherTextHex: buf2hex(encryptedBuffer),
    ivHex: buf2hex(iv),
  };
}

/**
 * Desxifra una dada xifrada mitjançant AES-GCM de 256 bits amb la clau derivada del PIN.
 */
export async function decryptWithPin(
  cipherTextHex: string,
  ivHex: string,
  pin: string,
  salt: Uint8Array
): Promise<string> {
  const key = await deriveKeyFromPin(pin, salt);
  const iv = hex2buf(ivHex);
  const cipherBuffer = hex2buf(cipherTextHex);

  const decryptedBuffer = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: iv as any },
    key,
    cipherBuffer as any
  );

  const dec = new TextDecoder();
  return dec.decode(decryptedBuffer);
}

/**
 * Crea el bloc sentinella inicial xifrat SEVALOR_SENTINEL per validar futurs desbloquejos offline.
 */
export async function createSentinelBlock(
  pin: string,
  salt: Uint8Array
): Promise<{ cipherTextHex: string; ivHex: string }> {
  return encryptWithPin(SENTINEL_PLAINTEXT, pin, salt);
}

/**
 * Verifica si el PIN introduït desbloqueja amb èxit el bloc sentinella SEVALOR_SENTINEL.
 */
export async function verifySentinelBlock(
  pin: string,
  salt: Uint8Array,
  cipherTextHex: string,
  ivHex: string
): Promise<boolean> {
  try {
    const decrypted = await decryptWithPin(cipherTextHex, ivHex, pin, salt);
    return decrypted === SENTINEL_PLAINTEXT;
  } catch {
    // Si la clau és incorrecta, el desxifratge AES-GCM falla per integritat del tag
    return false;
  }
}
