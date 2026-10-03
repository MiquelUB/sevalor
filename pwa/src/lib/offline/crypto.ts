import {
  deriveKeyFromPin,
  encryptWithPin,
  decryptWithPin,
  createSentinelBlock,
  verifySentinelBlock,
  SENTINEL_PLAINTEXT,
  buf2hex,
  hex2buf,
} from "../crypto";

export {
  deriveKeyFromPin,
  encryptWithPin,
  decryptWithPin,
  createSentinelBlock,
  verifySentinelBlock,
  SENTINEL_PLAINTEXT,
  buf2hex,
  hex2buf,
};

export async function deriveMasterKeyFromPin(pin: string, saltHex: string): Promise<CryptoKey> {
  const saltBuffer = hex2buf(saltHex);
  return deriveKeyFromPin(pin, saltBuffer);
}

export async function encryptPayload(payload: string, key: CryptoKey): Promise<{ ciphertext: string; iv: string }> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = new TextEncoder();
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: iv as any },
    key,
    enc.encode(payload)
  );
  return {
    ciphertext: buf2hex(encrypted),
    iv: buf2hex(iv),
  };
}

export async function decryptPayload(ciphertextHex: string, ivHex: string, key: CryptoKey): Promise<string> {
  const iv = hex2buf(ivHex);
  const cipherBuffer = hex2buf(ciphertextHex);
  const decrypted = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: iv as any },
    key,
    cipherBuffer as any
  );
  const dec = new TextDecoder();
  return dec.decode(decrypted);
}

const SENTINEL_KEY = "sevalor_offline_sentinel";
const SALT_KEY = "sevalor_device_salt";

export async function setupOfflineSentinel(pin: string, saltHex: string) {
  const key = await deriveMasterKeyFromPin(pin, saltHex);
  const { ciphertext, iv } = await encryptPayload(SENTINEL_PLAINTEXT, key);
  localStorage.setItem(SENTINEL_KEY, JSON.stringify({ ciphertext, iv }));
  localStorage.setItem(SALT_KEY, saltHex);
}

export async function verifyPinOffline(pin: string): Promise<boolean> {
  try {
    const sentinelData = localStorage.getItem(SENTINEL_KEY);
    const saltHex = localStorage.getItem(SALT_KEY);
    if (!sentinelData || !saltHex) return false;
    const { ciphertext, iv } = JSON.parse(sentinelData);
    const key = await deriveMasterKeyFromPin(pin, saltHex);
    const decrypted = await decryptPayload(ciphertext, iv, key);
    return decrypted === SENTINEL_PLAINTEXT;
  } catch {
    return false;
  }
}

export function generateRandomSaltHex(): string {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  return buf2hex(salt);
}
