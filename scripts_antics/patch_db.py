with open("pwa/src/lib/db.ts", "r") as f:
    content = f.read()

new_interface = """export interface LocalIncidencia {
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

// RF-01 / RF-02 (Spec 013): Draft de Fichaje Laboral
export interface LocalFichajeLaboral {
  id: string;
  empresa_id: string;
  usuari_id: string;
  tipus: "ENTRADA" | "SORTIDA";
  coords_gps?: [number, number];
  timestamp_local: number;
  estat_sync: "PENDENT" | "SINCRONITZAT" | "ERROR";
}"""

content = content.replace("export interface LocalIncidencia {", new_interface)

# Add to the tables definition
old_tables_decl = """  incidencies!: Table<LocalIncidencia, string>;
  sync_queue!: Table<SyncQueueItem, string>;"""
new_tables_decl = """  incidencies!: Table<LocalIncidencia, string>;
  sync_queue!: Table<SyncQueueItem, string>;
  fichajes!: Table<LocalFichajeLaboral, string>;"""

content = content.replace(old_tables_decl, new_tables_decl)

old_stores = """      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
    });"""

new_stores = """      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
      fichajes: "id, empresa_id, usuari_id, estat_sync, timestamp_local",
    });"""

content = content.replace(old_stores, new_stores)

with open("pwa/src/lib/db.ts", "w") as f:
    f.write(content)
