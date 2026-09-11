import assert from "node:assert";

export const MAX_GEOVALLA_METRES = 50.0;

export function calcularDistanciaMetres(lat1, lon1, lat2, lon2) {
  const R = 6371000;
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

export function validarGeovalla(coordsActuals, coordsParcela) {
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

export const CAMERA_LIVE_INPUT_PROPS = {
  type: "file",
  accept: "image/*",
  capture: "environment",
};

console.log("=== INICIANT TEST DE LÒGICA PWA DE CAMP (BLOC 3) ===");

// 1. Validar props d'antifraude de càmera (Tasca 3.2, Spec 020 RF-17)
console.log("1. Verificant atributs de càmera antifraude...");
assert.strictEqual(CAMERA_LIVE_INPUT_PROPS.type, "file");
assert.strictEqual(CAMERA_LIVE_INPUT_PROPS.accept, "image/*");
assert.strictEqual(CAMERA_LIVE_INPUT_PROPS.capture, "environment");
console.log("   -> OK! capture='environment' i accept='image/*' estrictament forçats.");

// 2. Validar càlcul de distància de Geovalla (Tasca 3.6, Spec 013 RF-12)
console.log("2. Verificant càlcul de Geovalla (límit 50m)...");
const puntParcela = [41.3461, 1.6975];

// A 10 metres
const puntProxim = [41.34615, 1.6975];
const resProxim = validarGeovalla(puntProxim, puntParcela);
assert.strictEqual(resProxim.dins_geovalla, true);
assert(resProxim.distancia_metres <= 50, "Hauria d'estar dins de la geovalla");
console.log(`   -> Punt a ${resProxim.distancia_metres}m: dins de geovalla = ${resProxim.dins_geovalla} (OK)`);

// A 120 metres (fora de geovalla)
const puntLlunya = [41.3472, 1.6975];
const resLlunya = validarGeovalla(puntLlunya, puntParcela);
assert.strictEqual(resLlunya.dins_geovalla, false);
assert(resLlunya.distancia_metres > 50, "Hauria d'estar fora de la geovalla");
console.log(`   -> Punt a ${resLlunya.distancia_metres}m: dins de geovalla = ${resLlunya.dins_geovalla} (OK)`);

console.log("\n✅ TOTS ELS CRITERIS DE LÒGICA PWA DE CAMP S'HAN VALIDAT CORRECTAMENT.");
