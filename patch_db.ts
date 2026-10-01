import Dexie, { Table } from 'dexie';

export interface SyncQueueItem {
    id?: number;
    action: string;
    payload: any;
    status: 'pending' | 'syncing' | 'failed';
    error?: string;
    createdAt: number;
}

export interface EncryptedRecord {
    id: string;
    ciphertext: string;
    iv: string;
}

export interface ItemEstocFurgoneta {
    id: string;
    nom: string;
    referencia: string;
    marca: string;
    quantitat_actual: number;
    quantitat_optima: number;
    unitat: string;
}

export class SevalorLocalDatabase extends Dexie {
    ordres!: Table<EncryptedRecord, string>;
    tiquets!: Table<EncryptedRecord, string>;
    incidencies!: Table<EncryptedRecord, string>;
    fichajes!: Table<EncryptedRecord, string>;
    vehicle_stock!: Table<ItemEstocFurgoneta, string>;
    sync_queue!: Table<SyncQueueItem, number>;

    constructor() {
        super('SevalorLocalDB');
        this.version(3).stores({
            ordres: 'id',
            tiquets: 'id',
            incidencies: 'id',
            fichajes: 'id',
            vehicle_stock: 'id',
            sync_queue: '++id, status'
        });
    }
}

export const db = new SevalorLocalDatabase();
