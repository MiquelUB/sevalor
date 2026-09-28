import re

path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

# 1. Update interface
target_iface = """  data_proxima_itv: string | null;"""
replace_iface = """  data_proxima_itv: string | null;
  estat_itv: string;
  data_caducitat_asseguranca: string | null;
  companyia_asseguradora: string | null;
  carnet_necessari: string;
  historial_reparacions: string | null;"""

text = text.replace(target_iface, replace_iface)

# 2. Update states for creation
target_state = """  const [nouOdometre, setNouOdometre] = useState(0);
  const [nouLimitKm, setNouLimitKm] = useState(150000);"""
replace_state = """  const [nouOdometre, setNouOdometre] = useState(0);
  const [nouLimitKm, setNouLimitKm] = useState(150000);
  
  const [nouEstatItv, setNouEstatItv] = useState("FAVORABLE");
  const [novaDataItv, setNovaDataItv] = useState("");
  const [novaDataAsseguranca, setNovaDataAsseguranca] = useState("");
  const [novaCompanyiaAsseguranca, setNovaCompanyiaAsseguranca] = useState("");
  const [nouCarnet, setNouCarnet] = useState("B");"""
text = text.replace(target_state, replace_state)

# 3. Update handleCrearVehicle payload
target_payload = """        body: JSON.stringify({
          matricula: novaMatricula.toUpperCase().trim(),
          marca: novaMarca.trim(),
          model: nouModel.trim(),
          tipus: nouTipus,
          distintiu_ambiental: nouDistintiu === "SENSE" ? null : nouDistintiu,
          estat: "OPERATIU",
          data_proxima_itv: null
        })"""
replace_payload = """        body: JSON.stringify({
          matricula: novaMatricula.toUpperCase().trim(),
          marca: novaMarca.trim(),
          model: nouModel.trim(),
          tipus: nouTipus,
          distintiu_ambiental: nouDistintiu === "SENSE" ? null : nouDistintiu,
          estat: "OPERATIU",
          data_proxima_itv: novaDataItv ? novaDataItv : null,
          estat_itv: nouEstatItv,
          data_caducitat_asseguranca: novaDataAsseguranca ? novaDataAsseguranca : null,
          companyia_asseguradora: novaCompanyiaAsseguranca.trim() || null,
          carnet_necessari: nouCarnet
        })"""
text = text.replace(target_payload, replace_payload)

# 4. Update the UI for modal
target_modal = """              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">"""
replace_modal = """
              <div className="grid grid-cols-2 gap-3">
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
              </div>
              
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Estat ITV actual:</label>
                  <select
                    value={nouEstatItv}
                    onChange={(e) => setNouEstatItv(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="FAVORABLE">Favorable Neta</option>
                    <option value="FAVORABLE_LEUS">Favorable amb Def. Lleus</option>
                    <option value="DESFAVORABLE">Desfavorable</option>
                    <option value="NEGATIVA">Negativa</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Data propera ITV:</label>
                  <input
                    type="date"
                    value={novaDataItv}
                    onChange={(e) => setNovaDataItv(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">Carnet Requerit:</label>
                  <select
                    value={nouCarnet}
                    onChange={(e) => setNouCarnet(e.target.value)}
                    className="w-full p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-xs focus:outline-none"
                  >
                    <option value="B">B (Turismes/Furgonetes)</option>
                    <option value="B+E">B+E (Remolc)</option>
                    <option value="C">C (Camions rígids)</option>
                    <option value="C+E">C+E (Tràilers)</option>
                    <option value="AM">AM / A1 (Motos)</option>
                    <option value="N/A">Maquinària exempta</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-800">"""
text = text.replace(target_modal, replace_modal)


# 5. Add columns to the table
target_th = """                    <th className="p-3 text-right">Estat Actiu</th>
                  </tr>"""
replace_th = """                    <th className="p-3">Carnet / Seguro</th>
                    <th className="p-3 text-right">ITV / Estat</th>
                  </tr>"""
text = text.replace(target_th, replace_th)

target_td = """                      <td className="p-3 text-right">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold border ${estatColor.bg} ${estatColor.text} ${estatColor.border}`}>
                          <estatColor.icon className="w-3.5 h-3.5" />
                          {v.estat}
                        </span>
                      </td>"""
replace_td = """                      <td className="p-3">
                        <div className="flex flex-col gap-1">
                          <span className="font-bold text-[10px] bg-slate-200 dark:bg-slate-700 px-1.5 py-0.5 rounded w-max text-slate-800 dark:text-slate-100">
                            Carnet: {v.carnet_necessari || "B"}
                          </span>
                          <span className="text-[10px] text-slate-500">
                            {v.companyia_asseguradora ? v.companyia_asseguradora : "Sense Seguro"}
                            {v.data_caducitat_asseguranca && ` (Fins: ${v.data_caducitat_asseguranca})`}
                          </span>
                        </div>
                      </td>
                      <td className="p-3 text-right flex flex-col items-end gap-1.5">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold border ${estatColor.bg} ${estatColor.text} ${estatColor.border}`}>
                          <estatColor.icon className="w-3.5 h-3.5" />
                          {v.estat}
                        </span>
                        <span className="text-[10px] text-slate-500 font-bold border border-slate-200 px-1.5 py-0.5 rounded bg-slate-50 dark:bg-slate-800">
                          ITV: {v.estat_itv || "FAVORABLE"} 
                          {v.data_proxima_itv && ` - ${v.data_proxima_itv}`}
                        </span>
                      </td>"""
text = text.replace(target_td, replace_td)

with open(path, "w") as f:
    f.write(text)
print("PWA flota patched!")
