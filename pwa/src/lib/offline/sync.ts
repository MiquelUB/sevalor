import { db, SyncQueueItem } from './db';

/**
 * Processa la cua de sincronització pendent enviant els payloads al backend.
 * Utilitza `navigator.onLine` per comprovar la connectivitat abans d'iniciar.
 */
export async function processSyncQueue(): Promise<void> {
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
        console.log('[SyncQueue] No hi ha connexió a Internet. Sincronització ajornada.');
        return;
    }

    const pendingItems = await db.sync_queue
        .where('status')
        .equals('pending')
        .or('status')
        .equals('failed')
        .toArray();

    if (pendingItems.length === 0) {
        return;
    }

    console.log(`[SyncQueue] Processant ${pendingItems.length} elements...`);

    const HEAVY_THRESHOLD_BYTES = 100 * 1024; // 100KB
    const lightItems: SyncQueueItem[] = [];
    const heavyItems: SyncQueueItem[] = [];

    for (const item of pendingItems) {
        const payloadSize = new Blob([JSON.stringify(item.payload)]).size;
        if (payloadSize > HEAVY_THRESHOLD_BYTES) {
            heavyItems.push(item);
        } else {
            lightItems.push(item);
        }
    }

    // 1. Processar els items lleugers en batch
    if (lightItems.length > 0) {
        try {
            await Promise.all(lightItems.map(item => db.sync_queue.update(item.id!, { status: 'syncing' })));
            
            const response = await fetch(`/api/v1/operari_pwa/sync/push`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    accions: lightItems.map(item => ({
                        id: String(item.id),
                        accio: item.action,
                        payload: item.payload,
                        timestamp: item.createdAt
                    }))
                })
            });

            if (!response.ok) {
                throw new Error(`Error sincronitzant batch lleuger: ${response.statusText}`);
            }

            await Promise.all(lightItems.map(item => db.sync_queue.delete(item.id!)));
            console.log(`[SyncQueue] Batch de ${lightItems.length} elements lleugers completat.`);
        } catch (error: any) {
            console.error(`[SyncQueue] Error batch lleuger:`, error);
            await Promise.all(lightItems.map(item => db.sync_queue.update(item.id!, { 
                status: 'failed', 
                error: error.message || 'Error desconegut' 
            })));
        }
    }

    // 2. Processar els items pesats (imatges, fotos) seqüencialment per no saturar la xarxa
    for (const item of heavyItems) {
        try {
            await db.sync_queue.update(item.id!, { status: 'syncing' });

            const response = await fetch(`/api/v1/operari_pwa/sync/push`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    accions: [{
                        id: String(item.id),
                        accio: item.action,
                        payload: item.payload,
                        timestamp: item.createdAt
                    }]
                })
            });

            if (!response.ok) {
                if (response.status === 409) {
                    console.warn(`[SyncQueue] Conflicte (409) a l'ítem pesat ${item.id}. S'ignorarà.`);
                    await db.sync_queue.delete(item.id!);
                    continue;
                }
                throw new Error(`Error de xarxa: ${response.statusText}`);
            }

            await db.sync_queue.delete(item.id!);
        } catch (error: any) {
            console.error(`[SyncQueue] Error sincronitzant ítem pesat ${item.id}:`, error);
            await db.sync_queue.update(item.id!, { 
                status: 'failed', 
                error: error.message || 'Error desconegut' 
            });
        }
    }
}

/**
 * Afegeix una nova acció a la cua de sincronització.
 */
export async function addToSyncQueue(action: string, payload: any): Promise<void> {
    await db.sync_queue.add({
        action,
        payload,
        status: 'pending',
        createdAt: Date.now()
    });

    // Intenta processar la cua immediatament si hi ha connexió
    if (typeof navigator !== 'undefined' && navigator.onLine) {
        processSyncQueue().catch(console.error);
    }
}
