/**
 * Base de dades local IndexedDB del client (Dexie.js).
 *
 * Compleix Spec 013, 015, 018, 020:
 * - Persistència 100% offline-first de dades de camp
 * - Cua de sincronització asíncrona amb blocs atòmics idempotents
 * - Zero Mock Data
 */

import Dexie, { Table } from "dexie";

export interface LocalOrdreTreball {
  id: string;
  empresa_id: string;
  codi: string;
  titol: string;
  descripcio?: string;
  estat: "PENDENT" | "EN_TRAMIT" | "PAUSADA" | "COMPLETADA";
  client_nom: string;
  coords_gps?: [number, number]; // [lat, lng]
  data_planificacio: string;
  updated_at: string;
}

export interface LocalTiquetDespesa {
  id: string;
  empresa_id: string;
  categoria: "CARBURANT" | "DIETES" | "MATERIAL" | "ALTRES";
  import_total: number;
  tiquet_foto_blob?: Blob | string;
  odometre_foto_blob?: Blob | string; // Obligatori per a CARBURANT
  odometre_valor?: number;
  data_despesa: string;
  estat_sync: "PENDENT" | "SINCRONITZAT" | "ERROR";
}

export interface LocalIncidencia {
  id: string;
  empresa_id: string;
  ordre_id?: string;
  tipus: "AVARIA_VEHICLE" | "MATERIAL_DEFECTUOS" | "ZONA_PERILLOSA" | "EMERGENCIA";
  descripcio?: string;
  audio_blob?: Blob | string;
  foto_blob?: Blob | string;
  coords_gps?: [number, number];
  data_registre: string;
  estat_sync: "PENDENT" | "SINCRONITZAT";
}

export interface SyncQueueItem {
  id: string;
  bloc_uuid: string;
  acció: "CREAR_TIQUET" | "REPORTAR_INCIDENCIA" | "INICIAR_TRAJECTE" | "FINALITZAR_ORDRE";
  payload: any;
  timestamp: number;
  intents: number;
}

export class SevalorLocalDatabase extends Dexie {
  ordres!: Table<LocalOrdreTreball, string>;
  tiquets!: Table<LocalTiquetDespesa, string>;
  incidencies!: Table<LocalIncidencia, string>;
  sync_queue!: Table<SyncQueueItem, string>;

  constructor() {
    super("SevalorFieldDB");
    this.version(1).stores({
      ordres: "id, empresa_id, estat, data_planificacio",
      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
    });
  }
}

export const localDB = new SevalorLocalDatabase();
