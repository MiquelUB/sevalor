/**
 * Control de Geovalla per a inici d'obres de camp (Spec 013 RF-12, RF-12.1).
 *
 * Fórmula Haversine per a càlcul de distància geodèsica.
 * Màxim radi permès per a inici ordinari: 50 metres.
 */

export const MAX_GEOVALLA_METRES = 50.0;

export function calcularDistanciaMetres(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Radi de la Terra en metres
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

export function validarGeovalla(
  coordsActuals: [number, number],
  coordsParcela: [number, number]
): { dins_geovalla: boolean; distancia_metres: number } {
  const distancia = calcularDistanciaMetres(
    coordsActuals[0],
    coordsActuals[1],
    coordsParcela[0],
    coordsParcela[1]
  );

  return {
    dins_geovalla: distancia <= MAX_GEOVALLA_METRES,
    distancia_metres: Math.round(distancia),
  };
}
