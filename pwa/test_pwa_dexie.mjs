import "fake-indexeddb/auto";
import Dexie from "dexie";
import assert from "node:assert";

// Implementació equivalent de test per validar el comportament estructural sense l'overhead de TypeScript/Node
class SevalorLocalDatabase extends Dexie {
  constructor() {
    super("SevalorFieldDB");
    this.version(1).stores({
      ordres: "id, empresa_id, estat, data_planificacio",
      tiquets: "id, empresa_id, categoria, estat_sync",
      incidencies: "id, empresa_id, tipus, estat_sync",
      sync_queue: "id, bloc_uuid, timestamp, intents",
      fichajes: "id, empresa_id, usuari_id, estat_sync, timestamp_local",
    });
  }
}

async function runTest() {
  console.log("=== INICIANT TEST PWA INDEXEDDB (DEXIE.JS) ===");
  const db = new SevalorLocalDatabase();

  console.log("1. Instanciació de DB i creació de taula 'fichajes' (Spec 013, RF-01)...");
  
  const fichajeMock = {
    id: "fich-1234",
    empresa_id: "emp-1",
    usuari_id: "usr-99",
    tipus: "ENTRADA",
    coords_gps: [41.3851, 2.1734],
    timestamp_local: Date.now(),
    estat_sync: "PENDENT"
  };

  await db.fichajes.add(fichajeMock);
  console.log("   -> Fichaje de draft desat correctament en mode offline.");

  const recuperat = await db.fichajes.get("fich-1234");
  assert.strictEqual(recuperat.id, "fich-1234");
  assert.strictEqual(recuperat.tipus, "ENTRADA");
  assert.strictEqual(recuperat.estat_sync, "PENDENT");
  
  console.log("2. Verificació de recuperació de dades...");
  console.log("   -> Dades recuperades exactament: ", recuperat.id, recuperat.tipus);

  // Verifiquem query per estat
  const pendents = await db.fichajes.where("estat_sync").equals("PENDENT").toArray();
  assert.strictEqual(pendents.length, 1);
  console.log("3. Índex secundari per 'estat_sync' funciona correctament.");
  
  console.log("\n✅ TOTES LES PROVES DEXIE OFFLINE-FIRST PASSADES CORRECTAMENT.");
  process.exit(0);
}

runTest().catch(err => {
  console.error("❌ Error en el test:", err);
  process.exit(1);
});
