export interface OrdreTreballLocal {
  id: string;
  empresa_id: string;
  codi: string;
  titol: string;
  descripcio?: string;
  estat_local: "PENDENT" | "EN_TRAMIT" | "PAUSADA" | "COMPLETADA" | "EN_TRANSIT" | "EN_CURS";
  client_nom?: string;
  coords_gps?: [number, number]; // [lat, lng]
  data_programada: string;
  updated_at: string;
}
