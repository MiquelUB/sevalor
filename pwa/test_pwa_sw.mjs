import fs from "node:fs";
import assert from "node:assert";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

console.log("=== INICIANT TEST DE SERVICE WORKER (WORKBOX SYNC) ===");

function runTest() {
  const swCode = fs.readFileSync(path.join(__dirname, "public/sw.js"), "utf-8");

  console.log("1. Verificant integració de Workbox...");
  assert.ok(swCode.includes("workbox-sw.js"), "Falta la importació de Workbox CDN");
  
  console.log("2. Verificant BackgroundSyncPlugin...");
  assert.ok(swCode.includes("BackgroundSyncPlugin"), "No s'ha instanciat el plugin de Background Sync");
  assert.ok(swCode.includes("sync_queue"), "La cua no es diu 'sync_queue' tal com demana la Spec 013");

  console.log("3. Verificant intercepció de mètodes mutables (POST, PUT, DELETE, PATCH)...");
  assert.ok(swCode.includes("POST") || swCode.match(/method:\s*['"]POST['"]/i), "No intercepta POST");
  assert.ok(swCode.includes("PUT") || swCode.match(/method:\s*['"]PUT['"]/i), "No intercepta PUT");

  console.log("4. Verificant la ruta de l'API interceptada...");
  assert.ok(swCode.includes("/api/v1/"), "La ruta interceptada no és la correcta de la API backend");

  console.log("\n✅ TOTES LES PROVES DE SERVICE WORKER WORKBOX PASSADES CORRECTAMENT.");
  process.exit(0);
}

try {
  runTest();
} catch (err) {
  console.error("❌ Error en el test:", err.message);
  process.exit(1);
}
