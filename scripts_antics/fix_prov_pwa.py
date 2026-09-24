import re

with open("pwa/src/app/gestio/proveidors/page.tsx", "r") as f:
    content = f.read()

# 1. Add state for editing
state_injection = """  const [nouAplicaIsp, setNouAplicaIsp] = useState<boolean>(false);
  const [nouIban, setNouIban] = useState<string>("");

  // Estat Modal Fitxa Proveïdor (Edició)
  const [modalFitxaObert, setModalFitxaObert] = useState<boolean>(false);
  const [provEdicio, setProvEdicio] = useState<ProveidorItem | null>(null);

  const desarFitxa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provEdicio) return;
    try {
      await apiFetch(`/gestio/proveidors/${provEdicio.id}`, {
        method: "PUT",
        body: JSON.stringify({
          codi: provEdicio.codi,
          rao_social: provEdicio.rao_social,
          nif: provEdicio.nif,
          telefon: provEdicio.telefon || null,
          email: provEdicio.email || null,
          especialitat: provEdicio.especialitat,
          iban: provEdicio.iban_visible,
        }),
      });
      setModalFitxaObert(false);
      fetchProveidors();
    } catch {
      // Ignorar
    }
  };
"""
content = content.replace('  const [nouIban, setNouIban] = useState<string>("");', state_injection)

# 2. Add onClick to tr
content = content.replace('<tr\n                      key={p.id}\n                      className={`transition-colors',
"""<tr
                      key={p.id}
                      onClick={(e) => {
                        // Evitar que s'obri la fitxa si fem clic a un botó d'acció
                        if ((e.target as HTMLElement).closest("button")) return;
                        setProvEdicio({ ...p });
                        setModalFitxaObert(true);
                      }}
                      className={`transition-colors cursor-pointer""")

# 3. Add Modal to the bottom
modal_fitxa = """      {/* Modal Edició (Fitxa de Proveïdor) */}
      {modalFitxaObert && provEdicio && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-emerald-600" />
                Fitxa de Proveïdor: {provEdicio.rao_social}
              </h3>
              <button
                onClick={() => setModalFitxaObert(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 bg-white dark:bg-slate-800 shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5">
              <form id="form-editar-prov" onSubmit={desarFitxa} className="space-y-4">
                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-4">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Informació General</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Codi Proveïdor</label>
                      <input
                        type="text"
                        value={provEdicio.codi}
                        onChange={(e) => setProvEdicio({ ...provEdicio, codi: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Raó Social</label>
                      <input
                        type="text"
                        value={provEdicio.rao_social}
                        onChange={(e) => setProvEdicio({ ...provEdicio, rao_social: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">NIF/CIF</label>
                      <input
                        type="text"
                        value={provEdicio.nif}
                        onChange={(e) => setProvEdicio({ ...provEdicio, nif: e.target.value.toUpperCase() })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Especialitat</label>
                      <select
                        value={provEdicio.especialitat}
                        onChange={(e) => setProvEdicio({ ...provEdicio, especialitat: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                        <option value="MATERIALS">Distribuïdor Materials</option>
                        <option value="MAQUINARIA">Lloguer Maquinària</option>
                        <option value="SUBCONTRACTA">Subcontracta d'Obra</option>
                        <option value="SERVEIS">Serveis Generals</option>
                      </select>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-blue-50/50 dark:bg-blue-900/10 rounded-2xl border border-blue-100 dark:border-blue-900/30 space-y-4">
                  <h4 className="text-xs font-bold text-blue-600 dark:text-blue-500 uppercase tracking-wider mb-2">Dades de Contacte</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Telèfon</label>
                      <input
                        type="tel"
                        value={provEdicio.telefon || ""}
                        onChange={(e) => setProvEdicio({ ...provEdicio, telefon: e.target.value })}
                        className="w-full p-2 rounded-xl border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-900 text-xs font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Correu Electrònic</label>
                      <input
                        type="email"
                        value={provEdicio.email || ""}
                        onChange={(e) => setProvEdicio({ ...provEdicio, email: e.target.value })}
                        className="w-full p-2 rounded-xl border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-900 text-xs"
                      />
                    </div>
                  </div>
                </div>
              </form>
            </div>
            
            <div className="p-5 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setModalFitxaObert(false)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel·lar
              </button>
              <button
                type="submit"
                form="form-editar-prov"
                className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md shadow-emerald-500/20 flex items-center gap-2 transition-all"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>Desar Canvis</span>
              </button>
            </div>
          </div>
        </div>
      )}
"""
content = content.replace("    </div>\n  );\n}", modal_fitxa + "\n    </div>\n  );\n}")

with open("pwa/src/app/gestio/proveidors/page.tsx", "w") as f:
    f.write(content)

