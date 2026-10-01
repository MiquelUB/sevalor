export async function deriveMasterKeyFromPin(pin: string, saltHex: string): Promise<CryptoKey> {
    const enc = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey(
        "raw",
        enc.encode(pin),
        { name: "PBKDF2" },
        false,
        ["deriveBits", "deriveKey"]
    );
    
    const match = saltHex.match(/.{1,2}/g);
    if (!match) throw new Error("Invalid salt hex string");
    const saltBuffer = new Uint8Array(match.map(byte => parseInt(byte, 16)));
    
    return crypto.subtle.deriveKey(
        {
            name: "PBKDF2",
            salt: saltBuffer,
            iterations: 100000,
            hash: "SHA-256"
        },
        keyMaterial,
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"]
    );
}

export async function encryptPayload(payload: string, key: CryptoKey): Promise<{ ciphertext: string, iv: string }> {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const enc = new TextEncoder();
    
    const encrypted = await crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: iv
        },
        key,
        enc.encode(payload)
    );
    
    const ciphertextHex = Array.from(new Uint8Array(encrypted)).map(b => b.toString(16).padStart(2, '0')).join('');
    const ivHex = Array.from(iv).map(b => b.toString(16).padStart(2, '0')).join('');
    
    return { ciphertext: ciphertextHex, iv: ivHex };
}

export async function decryptPayload(ciphertextHex: string, ivHex: string, key: CryptoKey): Promise<string> {
    const matchIv = ivHex.match(/.{1,2}/g);
    const matchCipher = ciphertextHex.match(/.{1,2}/g);
    if (!matchIv || !matchCipher) throw new Error("Invalid hex string");

    const iv = new Uint8Array(matchIv.map(byte => parseInt(byte, 16)));
    const encryptedBytes = new Uint8Array(matchCipher.map(byte => parseInt(byte, 16)));
    
    const decrypted = await crypto.subtle.decrypt(
        {
            name: "AES-GCM",
            iv: iv
        },
        key,
        encryptedBytes
    );
    
    const dec = new TextDecoder();
    return dec.decode(decrypted);
}

export const SENTINEL_PLAINTEXT = "SEVALOR_SENTINEL";
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
        
        if (!sentinelData || !saltHex) {
            return false;
        }
        
        const { ciphertext, iv } = JSON.parse(sentinelData);
        const key = await deriveMasterKeyFromPin(pin, saltHex);
        
        const decrypted = await decryptPayload(ciphertext, iv, key);
        return decrypted === SENTINEL_PLAINTEXT;
    } catch (e) {
        return false;
    }
}

export function generateRandomSaltHex(): string {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(salt).map(b => b.toString(16).padStart(2, '0')).join('');
}
