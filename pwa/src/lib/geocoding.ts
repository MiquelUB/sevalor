/**
 * Servei de Geocodificació Sobirà i Territorial de Sevalor
 * Tradueix adreces de text a coordenades reals (EPSG:4326 WGS84)
 * amb suport per a coordenades directes, diccionari territorial de Catalunya i OSM Nominatim.
 */

export interface Coordenades {
  lat: number;
  lng: number;
  ciutat?: string;
  font: "directa" | "diccionari" | "nominatim" | "default";
}

// Diccionari territorial de referència per a Catalunya i ciutats clau
// Permet resolució instantània i offline (sense dependència de xarxa externa)
const DICCIONARI_TERRITORIAL: Array<{
  patrons: string[];
  lat: number;
  lng: number;
  ciutat: string;
}> = [
  // Carrers i zones concretes de Barcelona
  {
    patrons: ["carrer industria", "carrer indistria", "c/ industria", "c. industria", "carrer de la industria", "carrer de la indústria", "indústria"],
    lat: 41.4080,
    lng: 2.1760,
    ciutat: "Barcelona (Carrer Indústria)",
  },
  {
    patrons: ["passeig de gracia", "passeig de gràcia", "pg de gracia", "pg. de gràcia"],
    lat: 41.3920,
    lng: 2.1649,
    ciutat: "Barcelona (Passeig de Gràcia)",
  },
  {
    patrons: ["avinguda diagonal", "av diagonal", "av. diagonal", "diagonal"],
    lat: 41.3970,
    lng: 2.1550,
    ciutat: "Barcelona (Avinguda Diagonal)",
  },
  {
    patrons: ["carrer arago", "carrer aragó", "c/ arago", "c. aragó"],
    lat: 41.3895,
    lng: 2.1648,
    ciutat: "Barcelona (Carrer Aragó)",
  },
  {
    patrons: ["sagrada familia", "sagrada família"],
    lat: 41.4036,
    lng: 2.1743,
    ciutat: "Barcelona (Sagrada Família)",
  },
  // Àrea Metropolitana i Comarques de Barcelona
  {
    patrons: ["barcelona", "bcn", "barcelonès", "barcelones"],
    lat: 41.3879,
    lng: 2.1699,
    ciutat: "Barcelona",
  },
  {
    patrons: ["l'hospitalet", "hospitalet de llobregat", "hospitalet"],
    lat: 41.3597,
    lng: 2.1003,
    ciutat: "L'Hospitalet de Llobregat",
  },
  {
    patrons: ["badalona"],
    lat: 41.4500,
    lng: 2.2474,
    ciutat: "Badalona",
  },
  {
    patrons: ["santa coloma de gramenet", "santa coloma"],
    lat: 41.4517,
    lng: 2.2081,
    ciutat: "Santa Coloma de Gramenet",
  },
  {
    patrons: ["sant cugat del valles", "sant cugat del vallès", "sant cugat"],
    lat: 41.4720,
    lng: 2.0850,
    ciutat: "Sant Cugat del Vallès",
  },
  {
    patrons: ["sabadell"],
    lat: 41.5463,
    lng: 2.1086,
    ciutat: "Sabadell",
  },
  {
    patrons: ["terrassa"],
    lat: 41.5632,
    lng: 2.0089,
    ciutat: "Terrassa",
  },
  {
    patrons: ["mataro", "mataró"],
    lat: 41.5381,
    lng: 2.4447,
    ciutat: "Mataró",
  },
  {
    patrons: ["granollers"],
    lat: 41.6080,
    lng: 2.2880,
    ciutat: "Granollers",
  },
  {
    patrons: ["cornella", "cornellà"],
    lat: 41.3560,
    lng: 2.0720,
    ciutat: "Cornellà de Llobregat",
  },
  {
    patrons: ["sant boi de llobregat", "sant boi"],
    lat: 41.3460,
    lng: 2.0420,
    ciutat: "Sant Boi de Llobregat",
  },
  {
    patrons: ["castelldefels"],
    lat: 41.2800,
    lng: 1.9770,
    ciutat: "Castelldefels",
  },
  {
    patrons: ["el prat de llobregat", "el prat"],
    lat: 41.3280,
    lng: 2.0950,
    ciutat: "El Prat de Llobregat",
  },
  {
    patrons: ["rubi", "rubí"],
    lat: 41.4920,
    lng: 2.0320,
    ciutat: "Rubí",
  },

  // Lleida i Ponent
  {
    patrons: ["balaguer"],
    lat: 41.7912,
    lng: 0.8055,
    ciutat: "Balaguer",
  },
  {
    patrons: ["alcarras", "alcarràs"],
    lat: 41.5644,
    lng: 0.5244,
    ciutat: "Alcarràs",
  },
  {
    patrons: ["mollerussa"],
    lat: 41.6300,
    lng: 0.8950,
    ciutat: "Mollerussa",
  },
  {
    patrons: ["tarrega", "tàrrega"],
    lat: 41.6467,
    lng: 1.1396,
    ciutat: "Tàrrega",
  },
  {
    patrons: ["cervera"],
    lat: 41.6710,
    lng: 1.2720,
    ciutat: "Cervera",
  },
  {
    patrons: ["almacelles"],
    lat: 41.7320,
    lng: 0.4380,
    ciutat: "Almacelles",
  },
  {
    patrons: ["alpicat"],
    lat: 41.6670,
    lng: 0.5560,
    ciutat: "Alpicat",
  },
  {
    patrons: ["les borges blanques", "borges blanques"],
    lat: 41.5220,
    lng: 0.8710,
    ciutat: "Les Borges Blanques",
  },
  {
    patrons: ["tremp"],
    lat: 42.1670,
    lng: 0.8950,
    ciutat: "Tremp",
  },
  {
    patrons: ["la seu d'urgell", "seu d'urgell"],
    lat: 42.3580,
    lng: 1.4600,
    ciutat: "La Seu d'Urgell",
  },
  {
    patrons: ["vielha", "viella"],
    lat: 42.7030,
    lng: 0.7950,
    ciutat: "Vielha",
  },
  {
    patrons: ["lleida", "lérida", "segle xxi", "segrià", "segria"],
    lat: 41.6176,
    lng: 0.6200,
    ciutat: "Lleida (Seu Central)",
  },

  // Girona i Comarques Gironines
  {
    patrons: ["girona", "gerona"],
    lat: 41.9794,
    lng: 2.8214,
    ciutat: "Girona",
  },
  {
    patrons: ["figueres", "figueras"],
    lat: 42.2660,
    lng: 2.9610,
    ciutat: "Figueres",
  },
  {
    patrons: ["olot"],
    lat: 42.1810,
    lng: 2.4890,
    ciutat: "Olot",
  },
  {
    patrons: ["blanes"],
    lat: 41.6750,
    lng: 2.7930,
    ciutat: "Blanes",
  },
  {
    patrons: ["lloret de mar", "lloret"],
    lat: 41.6990,
    lng: 2.8450,
    ciutat: "Lloret de Mar",
  },
  {
    patrons: ["palafrugell"],
    lat: 41.9170,
    lng: 3.1640,
    ciutat: "Palafrugell",
  },
  {
    patrons: ["banyoles"],
    lat: 42.1180,
    lng: 2.7660,
    ciutat: "Banyoles",
  },

  // Tarragona i Terres de l'Ebre
  {
    patrons: ["tarragona"],
    lat: 41.1189,
    lng: 1.2445,
    ciutat: "Tarragona",
  },
  {
    patrons: ["reus"],
    lat: 41.1561,
    lng: 1.1069,
    ciutat: "Reus",
  },
  {
    patrons: ["tortosa"],
    lat: 40.8120,
    lng: 0.5210,
    ciutat: "Tortosa",
  },
  {
    patrons: ["cambrils"],
    lat: 41.0750,
    lng: 1.0590,
    ciutat: "Cambrils",
  },
  {
    patrons: ["salou"],
    lat: 41.0770,
    lng: 1.1290,
    ciutat: "Salou",
  },
  {
    patrons: ["valls"],
    lat: 41.2860,
    lng: 1.2500,
    ciutat: "Valls",
  },
  {
    patrons: ["el vendrell", "vendrell"],
    lat: 41.2210,
    lng: 1.5350,
    ciutat: "El Vendrell",
  },
  {
    patrons: ["amposta"],
    lat: 40.7130,
    lng: 0.5800,
    ciutat: "Amposta",
  },

  // Catalunya Central
  {
    patrons: ["manresa"],
    lat: 41.7285,
    lng: 1.8267,
    ciutat: "Manresa",
  },
  {
    patrons: ["vic"],
    lat: 41.9304,
    lng: 2.2545,
    ciutat: "Vic",
  },
  {
    patrons: ["igualada"],
    lat: 41.5820,
    lng: 1.6170,
    ciutat: "Igualada",
  },
  {
    patrons: ["berga"],
    lat: 42.1040,
    lng: 1.8460,
    ciutat: "Berga",
  },
];

// Memòria cau local en sessió
const cacheGeocoding = new Map<string, Coordenades>();

/**
 * Normalitza el text per facilitar la cerca tolerant a accents i majúscules
 */
function normalitzarText(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

/**
 * Geocodifica una adreça de manera sincrònica i immediata (coordenades directes o diccionari)
 */
export function geocodificarAdreca(
  adreca?: string | null,
  latDefault?: number | null,
  lngDefault?: number | null
): Coordenades {
  // 1. Si ja tenim coordenades numèriques directes
  if (latDefault !== undefined && latDefault !== null && lngDefault !== undefined && lngDefault !== null) {
    if (!isNaN(latDefault) && !isNaN(lngDefault)) {
      return { lat: latDefault, lng: lngDefault, font: "directa" };
    }
  }

  if (!adreca || typeof adreca !== "string" || !adreca.trim()) {
    return { lat: 41.6176, lng: 0.6200, ciutat: "Lleida (Seu Central)", font: "default" };
  }

  const raw = adreca.trim();

  // Comprova memòria cau
  if (cacheGeocoding.has(raw)) {
    return cacheGeocoding.get(raw)!;
  }

  // 2. Extreure parells de coordenades tipus "41.4080, 2.1760" o "41.4080 2.1760"
  if (raw.includes(",") || raw.includes(" ")) {
    const coordsMatch = raw.match(/([-+]?\d{1,2}\.\d+)[,\s]+([-+]?\d{1,3}\.\d+)/);
    if (coordsMatch) {
      const parsedLat = parseFloat(coordsMatch[1]);
      const parsedLng = parseFloat(coordsMatch[2]);
      if (!isNaN(parsedLat) && !isNaN(parsedLng) && parsedLat >= 35 && parsedLat <= 45 && parsedLng >= -10 && parsedLng <= 5) {
        const res: Coordenades = { lat: parsedLat, lng: parsedLng, font: "directa" };
        cacheGeocoding.set(raw, res);
        return res;
      }
    }
  }

  // 3. Cerca al diccionari territorial
  const textNorm = normalitzarText(raw);

  // Primer busquem combinacions específiques de carrer + ciutat
  for (const entrada of DICCIONARI_TERRITORIAL) {
    for (const patro of entrada.patrons) {
      const patroNorm = normalitzarText(patro);
      if (textNorm.includes(patroNorm)) {
        const res: Coordenades = {
          lat: entrada.lat,
          lng: entrada.lng,
          ciutat: entrada.ciutat,
          font: "diccionari",
        };
        cacheGeocoding.set(raw, res);
        return res;
      }
    }
  }

  // 4. Si conté la paraula "barcelona" o derivats de la ciutat comtal
  if (textNorm.includes("barcelona") || textNorm.includes("bcn")) {
    const res: Coordenades = {
      lat: 41.3879,
      lng: 2.1699,
      ciutat: "Barcelona",
      font: "diccionari",
    };
    cacheGeocoding.set(raw, res);
    return res;
  }

  // 5. Per defecte: Seu Central (Lleida)
  const fallback: Coordenades = {
    lat: 41.6176,
    lng: 0.6200,
    ciutat: "Lleida (Seu Central)",
    font: "default",
  };
  return fallback;
}

/**
 * Geocodifica de manera asíncrona amb suport per a OpenStreetMap Nominatim en el navegador
 */
export async function geocodificarAdrecaAsync(adreca: string): Promise<Coordenades> {
  // Intentem primer la resolució local instantània
  const local = geocodificarAdreca(adreca);
  if (local.font === "directa" || (local.font === "diccionari" && local.ciutat?.includes("Carrer Indústria"))) {
    return local;
  }

  // Si som al navegador i tenim connexió a internet, provem Nominatim per afinar el número exacte
  if (typeof window !== "undefined" && navigator.onLine) {
    try {
      const query = `${adreca.trim()}, Catalunya, Espanya`;
      const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
        query
      )}&limit=1`;

      const response = await fetch(url, {
        headers: { "Accept-Language": "ca,es" },
      });

      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0 && data[0].lat && data[0].lon) {
          const lat = parseFloat(data[0].lat);
          const lng = parseFloat(data[0].lon);
          const res: Coordenades = {
            lat,
            lng,
            ciutat: data[0].display_name,
            font: "nominatim",
          };
          cacheGeocoding.set(adreca.trim(), res);
          return res;
        }
      }
    } catch {
      // Si falla Nominatim, fem servir el resultat del diccionari territorial
    }
  }

  return local;
}
