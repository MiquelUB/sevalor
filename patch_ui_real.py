path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

target_ui = """              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Assegurança (Companyia):</label>
                  <input
                    type="text"
                    placeholder="Ex: Mapfre, Allianz"
                    value={novaCompanyiaAsseguranca}
                    onChange={(e) => setNovaCompanyiaAsseguranca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Caducitat Assegurança:</label>
                  <input
                    type="date"
                    value={novaDataAsseguranca}
                    onChange={(e) => setNovaDataAsseguranca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>"""

replace_ui = """              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Assegurança (Companyia):</label>
                  <input
                    type="text"
                    placeholder="Ex: Mapfre, Allianz"
                    value={novaCompanyiaAsseguranca}
                    onChange={(e) => setNovaCompanyiaAsseguranca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Caducitat Assegurança:</label>
                  <input
                    type="date"
                    value={novaDataAsseguranca}
                    onChange={(e) => setNovaDataAsseguranca(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                
                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-slate-700 dark:text-slate-300 flex justify-between">
                    <span>Pòlissa (Núm) i Document Assegurança:</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Ex: POL-9938221"
                      value={novaPolissaAsseguranca}
                      onChange={(e) => setNovaPolissaAsseguranca(e.target.value)}
                      className="w-1/2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] focus:outline-none"
                    />
                    <input
                      type="file"
                      onChange={(e) => setArxiuAsseguranca(e.target.files?.[0] || null)}
                      className="w-1/2 p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                    />
                  </div>
                </div>
              </div>"""

if target_ui in text:
    text = text.replace(target_ui, replace_ui)
    print("Replaced assegurança block")
else:
    print("Could not find assegurança block")


target_itv = """              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Estat ITV actual:</label>"""

replace_itv = """              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1 col-span-3">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Documentació ITV (Opcional):</label>
                  <input
                    type="file"
                    onChange={(e) => setArxiuITV(e.target.files?.[0] || null)}
                    className="w-full p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Estat ITV actual:</label>"""

if target_itv in text:
    text = text.replace(target_itv, replace_itv)
    print("Replaced ITV block")
else:
    print("Could not find ITV block")


target_reparacio = """                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Carnet Requerit:</label>"""

replace_reparacio = """                <div className="space-y-1 col-span-3">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Última Reparació / Canvi Oli:</label>
                  <input
                    type="file"
                    onChange={(e) => setArxiuReparacio(e.target.files?.[0] || null)}
                    className="w-full p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Carnet Requerit:</label>"""

if target_reparacio in text:
    text = text.replace(target_reparacio, replace_reparacio)
    print("Replaced reparacio block")
else:
    print("Could not find reparacio block")

with open(path, "w") as f:
    f.write(text)

print("Done patching UI")
