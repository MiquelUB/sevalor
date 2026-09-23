import Dexie, { type Table } from 'dexie';

// Define data structures
export interface LocalOrdreTreball {
  id: string;
  empresa_id: string;
  client_id: string;
  titol: string;
  descripcio?: string;
  estat: "PENDENT" | "EN_CURS" | "COMPLETADA" | "CANCELADA";
  prioritat: "BAIXA" | "NORMAL" | "ALTA" | "CRITICA";
  assignat_a: string;
  data_inici_prevista?: string;
  data_final_prevista?: string;
}

export interface LocalMaterialDraft {
  id: string;
  empresa_id: string;
  ordre_id: string;
  article_id: string;
  quantitat_utilitzada: number;
  data_registre: string;
  estat_sync: "PENDENT" | "SINCRONITZAT";
}

export interface LocalFichajeLaboral {
  id: string;
  empresa_id: string;
  usuari_id: string;
  tipus: "ENTRADA" | "SORTIDA";
  coords_gps?: [number, number];
  timestamp_local: number;
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

export class SevalorOfflineDatabase extends Dexie {
  ordresTreball!: Table<LocalOrdreTreball, string>;
  materialsDraft!: Table<LocalMaterialDraft, string>;
  fichajes!: Table<LocalFichajeLaboral, string>;
  incidencies!: Table<LocalIncidencia, string>;

  constructor() {
    super('SevalorOfflineDB');
    this.version(1).stores({
      ordresTreball: 'id, empresa_id, assignat_a, estat',
      materialsDraft: 'id, ordre_id, estat_sync',
      fichajes: 'id, usuari_id, estat_sync',
      incidencies: 'id, ordre_id, estat_sync'
    });
  }
}

export const db = new SevalorOfflineDatabase();
