import assert from "node:assert";
import { calcularDistanciaMetres, validarGeovalla, MAX_GEOVALLA_METRES } from "./src/lib/geo.ts";
import { CAMERA_LIVE_INPUT_PROPS } from "./src/lib/media.ts";

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
assert(resProxim.distancia_metres <= MAX_GEOVALLA_METRES, "Hauria d'estar dins de la geovalla");
console.log(`   -> Punt a ${resProxim.distancia_metres}m: dins de geovalla = ${resProxim.dins_geovalla} (OK)`);

// A 120 metres (fora de geovalla)
const puntLlunya = [41.3472, 1.6975];
const resLlunya = validarGeovalla(puntLlunya, puntParcela);
assert.strictEqual(resLlunya.dins_geovalla, false);
assert(resLlunya.distancia_metres > MAX_GEOVALLA_METRES, "Hauria d'estar fora de la geovalla");
console.log(`   -> Punt a ${resLlunya.distancia_metres}m: dins de geovalla = ${resLlunya.dins_geovalla} (OK)`);

console.log("\n✅ TOTS ELS CRITERIS DE LÒGICA PWA DE CAMP S'HAN VALIDAT CORRECTAMENT.");
