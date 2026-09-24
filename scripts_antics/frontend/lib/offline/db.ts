import Dexie, { Table } from 'dexie';
import { encryptData, decryptData, deriveKey } from './crypto';

// Definim les taules principals per a l'operari (offline-first)
export interface SyncQueueItem {
  id?: number;
  url: string;
  method: string;
  body: any;
  timestamp: number;
}

export interface EncryptedData {
  id: string; // uuid
  iv: number[];
  ciphertext: number[];
}

export class SevalorOfflineDB extends Dexie {
  // Cua de sincronització (No es xifra ja que conté peticions a l'espera)
  syncQueue!: Table<SyncQueueItem, number>;
  
  // Dades del domini xifrades (Feines, Vehicles, Incidències)
  feines!: Table<EncryptedData, string>;
  vehicles!: Table<EncryptedData, string>;
  planols!: Table<EncryptedData, string>;

  constructor() {
    super('SevalorOfflineDB');
    this.version(1).stores({
      syncQueue: '++id, timestamp',
      feines: 'id',
      vehicles: 'id',
      planols: 'id'
    });
  }
}

export const db = new SevalorOfflineDB();

// Utilitats d'accés segur
export async function saveSecureData(table: Table<EncryptedData, string>, id: string, data: any, pin: string) {
  const key = await deriveKey(pin);
  const encrypted = await encryptData(data, key);
  await table.put({
    id,
    iv: encrypted.iv,
    ciphertext: encrypted.ciphertext
  });
}

export async function getSecureData(table: Table<EncryptedData, string>, id: string, pin: string) {
  const record = await table.get(id);
  if (!record) return null;
  const key = await deriveKey(pin);
  try {
    return await decryptData(record.iv, record.ciphertext, key);
  } catch (err) {
    throw new Error("Error de desxifrat (PIN incorrecte?)");
  }
}

export async function getAllSecureData(table: Table<EncryptedData, string>, pin: string) {
  const records = await table.toArray();
  const key = await deriveKey(pin);
  const results = [];
  for (const record of records) {
    try {
      results.push(await decryptData(record.iv, record.ciphertext, key));
    } catch (err) {
      console.error(`No s'ha pogut desxifrar l'element ${record.id}`);
    }
  }
  return results;
}
