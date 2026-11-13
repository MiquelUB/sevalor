/**
 * Base de dades local IndexedDB del client (Dexie.js).
 *
 * Compleix Spec 013, 015, 018, 020:
 * - Persistència 100% offline-first de dades de camp
 * - Cua de sincronització asíncrona amb blocs atòmics idempotents
 * - Zero Mock Data
 */

import Dexie, { Table } from "dexie";

import { OrdreTreballLocal } from "./types/operari";

export interface LocalTiquetDespesa {
  id: string;
  empresa_id: string;
  categoria: "CARBURANT" | "FERRETERIA" | "PEATGES" | "DIETES" | "MATERIAL" | "ALTRES";
  import_total?: number | null;
  nom_fitxer?: string;
  ordre_treball_id?: string | null;
  vehicle_id?: string | null;
  tiquet_foto_blob?: Blob | string;
  odometre_foto_blob?: Blob | string; // Obligatori per a CARBURANT
  odometre_valor?: number;
  data_despesa: string;
  custodia_confirmada?: boolean;
  estat_sync: "PENDENT" | "SINCRONITZAT" | "ERROR";
}

export interface LocalCameraCapture {
  id: string;
  empresa_id: string;
  blob: Blob;
  nom_fitxer: string;
  ordre_treball_id?: string | null;
  fase_foto?: "INICIAL" | "INTERMEDIA" | "FINAL" | null;
  assignada: boolean;
  created_at: string;
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

export interface LocalFitxatgeJornada {
  id: string;
  empresa_id: string;
  usuari_id: string;
  jornada_remota_id?: string;
  estat: "EN_CURS" | "COMPLERT";
  hora_inici: string;
  hora_fi?: string;
  latitud_inici: number;
  longitud_inici: number;
  latitud_fi?: number;
  longitud_fi?: number;
  estat_sync: "PENDENT" | "SINCRONITZAT" | "ERROR";
}

export interface LocalLiniaPicking {
  id: string;
  empresa_id: string;
  picking_id?: string;
  article_id: string;
  nom: string;
  referencia: string;
  quantitat_prevista: number;
  quantitat_carregada_pick_in: number;
  quantitat_retornada_pick_out: number;
  unitat: string;
  estat_sync: "PENDENT" | "SINCRONITZAT";
}

export interface SyncQueueItem {
  id: string;
  bloc_uuid: string;
  acció:
    | "FITXAR_JORNADA"
    | "ACTUALITZAR_PICKING"
    | "CREAR_TIQUET"
    | "REPORTAR_INCIDENCIA"
    | "INICIAR_TRAJECTE"
    | "FINALITZAR_ORDRE";
  payload: any;
  timestamp: number;
  intents: number;
}

export class SevalorLocalDatabase extends Dexie {
  ordres!: Table<OrdreTreballLocal, string>;
  tiquets!: Table<LocalTiquetDespesa, string>;
  incidencies!: Table<LocalIncidencia, string>;
  fichajes!: Table<LocalFitxatgeJornada, string>;
  picking!: Table<LocalLiniaPicking, string>;
  sync_queue!: Table<SyncQueueItem, string>;
  camera_captures!: Table<LocalCameraCapture, string>;

  constructor() {
    super("SevalorFieldDB");
    this.version(2).stores({
      ordres: "id, empresa_id, estat_local, data_programada",
      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
    });
    this.version(3).stores({
      ordres: "id, empresa_id, estat_local, data_programada",
      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      fichajes: "id, empresa_id, usuari_id, estat, estat_sync",
      picking: "id, empresa_id, article_id, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
    });
    this.version(4).stores({
      ordres: "id, empresa_id, estat_local, data_programada",
      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      fichajes: "id, empresa_id, usuari_id, estat, estat_sync",
      picking: "id, empresa_id, article_id, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
      camera_captures: "id, empresa_id, assignada, ordre_treball_id, created_at",
    });
  }
}

export const localDB = new SevalorLocalDatabase();
