import re

path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

# 1. Add state variables
target_state = """  const [novaDataAsseguranca, setNovaDataAsseguranca] = useState<string>("");"""
replace_state = """  const [novaDataAsseguranca, setNovaDataAsseguranca] = useState<string>("");
  const [novaPolissaAsseguranca, setNovaPolissaAsseguranca] = useState<string>("");
  const [arxiuAsseguranca, setArxiuAsseguranca] = useState<File | null>(null);
  const [arxiuITV, setArxiuITV] = useState<File | null>(null);
  const [arxiuReparacio, setArxiuReparacio] = useState<File | null>(null);"""
text = text.replace(target_state, replace_state)

# 2. Add polissa to payload
target_payload = """          companyia_asseguradora: novaCompanyiaAsseguranca || null,
          carnet_necessari: nouCarnet
        }),"""
replace_payload = """          companyia_asseguradora: novaCompanyiaAsseguranca || null,
          polissa_asseguranca: novaPolissaAsseguranca || null,
          carnet_necessari: nouCarnet
        }),"""
text = text.replace(target_payload, replace_payload)

# 3. Handle file uploads after creation
target_create = """      if (res.ok) {
        setModalNouVehicleObert(false);
      } else {"""
replace_create = """      if (res.ok) {
        const vehicleData = await res.json();
        const vId = vehicleData.id;
        
        // Pujar documents asíncronament
        const uploadFile = async (file: File, tipus: string) => {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("tipus_document", tipus);
          
          try {
            await fetch(`${getApiBaseUrl()}/gestio/flota/${vId}/documents`, {
              method: "POST",
              headers: {
                "Authorization": `Bearer ${localStorage.getItem("sevalor_auth_token") ? JSON.parse(localStorage.getItem("sevalor_auth_token")!).token : ""}`,
                "X-Empresa-ID": localStorage.getItem("sevalor_tenant_id") || ""
              },
              body: formData
            });
          } catch(e) { console.error("Error pujant", tipus, e) }
        };
        
        if (arxiuAsseguranca) await uploadFile(arxiuAsseguranca, "ASSEGURANCA");
        if (arxiuITV) await uploadFile(arxiuITV, "ITV");
        if (arxiuReparacio) await uploadFile(arxiuReparacio, "REPARACIO");
        
        setModalNouVehicleObert(false);
      } else {"""
text = text.replace(target_create, replace_create)

# 4. Add UI fields to the modal
target_ui = """                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Caducitat Assegurança:
                  </label>"""
replace_ui = """                <div className="space-y-1 col-span-2">
                  <label className="font-bold text-slate-700 dark:text-slate-300 flex justify-between">
                    <span>Pòlissa (Núm) i Document Assegurança:</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Ex: POL-9938221"
                      value={novaPolissaAsseguranca}
                      onChange={(e) => setNovaPolissaAsseguranca(e.target.value)}
                      className="w-1/2 p-2 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] focus:outline-none"
                    />
                    <input
                      type="file"
                      onChange={(e) => setArxiuAsseguranca(e.target.files?.[0] || null)}
                      className="w-1/2 p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Documentació ITV (Opcional):
                  </label>
                  <input
                    type="file"
                    onChange={(e) => setArxiuITV(e.target.files?.[0] || null)}
                    className="w-full p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                  />
                </div>
                
                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Última Reparació / Canvi Oli:
                  </label>
                  <input
                    type="file"
                    onChange={(e) => setArxiuReparacio(e.target.files?.[0] || null)}
                    className="w-full p-1.5 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-mono text-[10px] file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-[10px] file:bg-emerald-600 file:text-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-slate-700 dark:text-slate-300">
                    Caducitat Assegurança:
                  </label>"""
text = text.replace(target_ui, replace_ui)

with open(path, "w") as f:
    f.write(text)

print("Patched UI with file inputs")
