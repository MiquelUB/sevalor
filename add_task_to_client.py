import re

with open("pwa/src/app/gestio/clients/page.tsx", "r") as f:
    content = f.read()

# Add standard icons
content = content.replace('import { Users, Building, Phone, Mail, FileText, Search, Plus, MapPin, Wrench, AlertTriangle, Lock, RefreshCw, X, HardHat } from "lucide-react";',
                          'import { Users, Building, Phone, Mail, FileText, Search, Plus, MapPin, Wrench, AlertTriangle, Lock, RefreshCw, X, HardHat, ClipboardList } from "lucide-react";')

if "ClipboardList" not in content:
    # If the exact import wasn't matched, just add it naively
    content = content.replace('import {', 'import { ClipboardList,', 1)

# Add state variables
state_block = """  const [modalNouClient, setModalNouClient] = useState(false);"""
new_state_block = """  const [modalNouClient, setModalNouClient] = useState(false);
  
  // Gestió de Tasques
  const [modalNovaTasca, setModalNovaTasca] = useState(false);
  const [guardantTasca, setGuardantTasca] = useState(false);
  const [operaris, setOperaris] = useState<any[]>([]);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [novaTasca, setNovaTasca] = useState({
    codi: `OT-${Math.floor(Math.random() * 10000)}`,
    titol: "",
    adreca: "",
    data_planificacio: new Date().toISOString().split('T')[0],
    descripcio: "",
    cap_de_colla_id: "",
    vehicle_id: "",
    finca_id: ""
  });"""

content = content.replace(state_block, new_state_block)

# Add fetch logic for operaris and vehicles when modal opens
modal_open_logic = """
  const handleObrirModalTasca = () => {
    setModalNovaTasca(true);
    setNovaTasca({
      ...novaTasca,
      codi: `OT-${Math.floor(Math.random() * 10000)}`
    });
    // Fetch operaris and vehicles if not loaded
    if (operaris.length === 0) {
      apiFetch("/gestio/operaris").then((data: any) => setOperaris(data)).catch(() => {});
    }
    if (vehicles.length === 0) {
      apiFetch("/gestio/flota").then((data: any) => setVehicles(data)).catch(() => {});
    }
  };

  const handleCrearTasca = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientSeleccionat || !novaTasca.cap_de_colla_id) return;
    setGuardantTasca(true);
    try {
      const payload = {
        ...novaTasca,
        client_id: clientSeleccionat.id,
        vehicle_id: novaTasca.vehicle_id || null,
        finca_id: novaTasca.finca_id || null
      };
      await apiFetch("/gestio/feines", {
        method: "POST",
        body: payload
      });
      setModalNovaTasca(false);
      // Reload Fitxa 360 to see the new tasca
      setLoadingFitxa(true);
      apiFetch<Fitxa360Response>('/gestio/clients/' + clientSeleccionat.id + '/fitxa360')
        .then(data => setFitxa360(data))
        .catch(err => console.error("Error carregant fitxa360:", err))
        .finally(() => setLoadingFitxa(false));
    } catch (err: any) {
      alert("Error al crear la tasca: " + (err.message || ""));
    } finally {
      setGuardantTasca(false);
    }
  };
"""

# Insert modal logic before handleCrearClient
content = content.replace("  const handleCrearClient = async", modal_open_logic + "\n  const handleCrearClient = async")


# Add the button in the UI
button_block = """                  <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs flex items-center gap-2">
                    <Lock className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="font-mono text-slate-700 dark:text-slate-300">
                      {clientSeleccionat.iban}
                    </span>
                  </div>
                )}
              </div>"""

new_button_block = """                  <div className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs flex items-center gap-2">
                    <Lock className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="font-mono text-slate-700 dark:text-slate-300">
                      {clientSeleccionat.iban}
                    </span>
                  </div>
                )}
                
                <button
                  onClick={handleObrirModalTasca}
                  className="mt-2 ml-4 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-sm flex items-center gap-2 transition-all cursor-pointer"
                >
                  <ClipboardList className="w-4 h-4" />
                  Assignar Tasca
                </button>
              </div>"""

content = content.replace(button_block, new_button_block)

# Add the modal HTML at the end of the file, before the last </div>
modal_html = """
      {/* Modal Crear Tasca */}
      {modalNovaTasca && clientSeleccionat && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-blue-600" />
                Assignar Tasca a {clientSeleccionat.rao_social}
              </h3>
              <button
                onClick={() => setModalNovaTasca(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCrearTasca} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Codi Tasca *
                  </label>
                  <input
                    type="text"
                    required
                    value={novaTasca.codi}
                    onChange={(e) => setNovaTasca({ ...novaTasca, codi: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Data Planificació *
                  </label>
                  <input
                    type="date"
                    required
                    value={novaTasca.data_planificacio}
                    onChange={(e) => setNovaTasca({ ...novaTasca, data_planificacio: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Títol de la Feina *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ex: Reparació fuita principal"
                  value={novaTasca.titol}
                  onChange={(e) => setNovaTasca({ ...novaTasca, titol: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-medium"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Adreça de l'Obra *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Carrer de l'Obra, 123"
                  value={novaTasca.adreca}
                  onChange={(e) => setNovaTasca({ ...novaTasca, adreca: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                />
              </div>
              
              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Finca (Opcional)
                </label>
                <select
                  value={novaTasca.finca_id}
                  onChange={(e) => setNovaTasca({ ...novaTasca, finca_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                >
                  <option value="">-- Sense Finca Específica --</option>
                  {fitxa360?.finques.map(f => (
                    <option key={f.id} value={f.id}>{f.nom} ({f.adreca})</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Cap de Colla *
                  </label>
                  <select
                    required
                    value={novaTasca.cap_de_colla_id}
                    onChange={(e) => setNovaTasca({ ...novaTasca, cap_de_colla_id: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  >
                    <option value="">-- Seleccionar --</option>
                    {operaris.map(op => (
                      <option key={op.id} value={op.id}>{op.nom} {op.cognoms}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                    Vehicle (Opcional)
                  </label>
                  <select
                    value={novaTasca.vehicle_id}
                    onChange={(e) => setNovaTasca({ ...novaTasca, vehicle_id: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                  >
                    <option value="">-- Seleccionar --</option>
                    {vehicles.map(v => (
                      <option key={v.id} value={v.id}>{v.matricula} ({v.marca})</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                  Descripció (Opcional)
                </label>
                <textarea
                  placeholder="Instruccions per a l'operari..."
                  value={novaTasca.descripcio}
                  onChange={(e) => setNovaTasca({ ...novaTasca, descripcio: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs min-h-[60px]"
                />
              </div>

              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalNovaTasca(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-xs font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  Cancel·lar
                </button>
                <button
                  type="submit"
                  disabled={guardantTasca}
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow disabled:opacity-50 flex items-center gap-2"
                >
                  <ClipboardList className="w-4 h-4" />
                  {guardantTasca ? "Creant Tasca..." : "Crear i Assignar Tasca"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
"""

content = content.replace("    </div>\n  );\n}\n", modal_html + "\n    </div>\n  );\n}\n")

with open("pwa/src/app/gestio/clients/page.tsx", "w") as f:
    f.write(content)

print("Patch applied to pwa/src/app/gestio/clients/page.tsx")
