import "fake-indexeddb/auto";
import assert from "node:assert";
import { localDB } from "./src/lib/db.ts";

async function runTest() {
  console.log("=== INICIANT TEST PWA INDEXEDDB (DEXIE.JS) ===");

  console.log("1. Instanciació de DB i creació de taula 'tiquets'...");
  
  const tiquetMock = {
    id: "tiq-1234",
    empresa_id: "emp-1",
    categoria: "CARBURANT" as const,
    import_total: 50.0,
    data_despesa: new Date().toISOString(),
    estat_sync: "PENDENT" as const
  };

  await localDB.tiquets.add(tiquetMock);
  console.log("   -> Tiquet desat correctament en mode offline.");

  const recuperat = await localDB.tiquets.get("tiq-1234");
  assert(recuperat);
  assert.strictEqual(recuperat.id, "tiq-1234");
  assert.strictEqual(recuperat.categoria, "CARBURANT");
  assert.strictEqual(recuperat.estat_sync, "PENDENT");
  
  console.log("2. Verificació de recuperació de dades...");
  console.log("   -> Dades recuperades exactament: ", recuperat.id, recuperat.categoria);

  // Verifiquem query per estat
  const pendents = await localDB.tiquets.where("estat_sync").equals("PENDENT").toArray();
  assert.strictEqual(pendents.length, 1);
  console.log("3. Índex secundari per 'estat_sync' funciona correctament.");
  
  console.log("\n✅ TOTES LES PROVES DEXIE OFFLINE-FIRST PASSADES CORRECTAMENT.");
  process.exit(0);
}

runTest().catch(err => {
  console.error("❌ Error en el test:", err);
  process.exit(1);
});
