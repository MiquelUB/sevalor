// Funcions criptogràfiques Web Crypto API (Spec 013 & AGENTS.md)
// Utilitza AES-GCM 256 bits i derivació de clau PBKDF2 a partir del PIN de l'operari.

const SALT = new TextEncoder().encode("SEVALOR_SALT_OFFLINE_APP_V4");
const ITERATIONS = 100000;

export async function deriveKey(pin: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    enc.encode(pin),
    { name: "PBKDF2" },
    false,
    ["deriveBits", "deriveKey"]
  );

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: SALT,
      iterations: ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encryptData(data: any, key: CryptoKey): Promise<{ iv: number[]; ciphertext: number[] }> {
  const enc = new TextEncoder();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: iv,
    },
    key,
    enc.encode(JSON.stringify(data))
  );

  return {
    iv: Array.from(iv),
    ciphertext: Array.from(new Uint8Array(encrypted)),
  };
}

export async function decryptData(iv: number[], ciphertext: number[], key: CryptoKey): Promise<any> {
  const decrypted = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: new Uint8Array(iv),
    },
    key,
    new Uint8Array(ciphertext)
  );

  const dec = new TextDecoder();
  return JSON.parse(dec.decode(decrypted));
}
