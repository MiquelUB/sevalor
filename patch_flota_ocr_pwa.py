import re

path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

# 1. Add state for OCR Loading
target_state = """  const [modalNouVehicleObert, setModalNouVehicleObert] = useState(false);"""
replace_state = """  const [modalNouVehicleObert, setModalNouVehicleObert] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);"""
text = text.replace(target_state, replace_state)

# 2. Add OCR File handler
target_handler = """  const handleObrirModalVehicle = () => {"""
replace_handler = """  const handleOcrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setOcrLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = localStorage.getItem("sevalor_auth_token") ? JSON.parse(localStorage.getItem("sevalor_auth_token")!).token : "";
      
      const res = await fetch(`${getApiBaseUrl()}/gestio/flota/ocr-draft`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-Empresa-ID": localStorage.getItem("sevalor_tenant_id") || ""
        },
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        // Omplim el formulari amb les dades de l'OCR
        setNovaMatricula(data.matricula || "");
        setNovaMarca(data.marca || "");
        setNouModel(data.model || "");
        setNouTipus(data.tipus || "THERMIC");
        setNouDistintiu(data.distintiu_ambiental || "C");
        setNovaCompanyiaAsseguranca(data.companyia_asseguradora || "");
        setNovaPolissaAsseguranca(data.polissa_asseguranca || "");
        setNouCarnet(data.carnet_necessari || "B");
        setNouRegim(data.regim_adquisicio || "PROPIETAT");
        if (data.renting_limit_km) setNouLimitKm(data.renting_limit_km);
        
        // Obrim el modal d'alta ja farcit
        setModalNouVehicleObert(true);
      } else {
        alert("Error processant OCR");
      }
    } catch (err) {
      alert("Error de xarxa OCR: " + err);
    } finally {
      setOcrLoading(false);
      // Neteja l'input de fitxer
      e.target.value = "";
    }
  };

  const handleObrirModalVehicle = () => {"""
text = text.replace(target_handler, replace_handler)

# 3. Add OCR Button UI next to "Nou Actiu"
target_button = """          <button
            onClick={handleObrirModalVehicle}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            Nou Actiu
          </button>"""
replace_button = """          <div className="flex items-center gap-2">
            <label className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm cursor-pointer transition-all ${ocrLoading ? 'opacity-50 pointer-events-none' : ''}`}>
              {ocrLoading ? <span className="animate-spin text-lg leading-none">⚙</span> : <span className="text-lg leading-none">✨</span>}
              {ocrLoading ? 'Processant IA...' : 'Alta OCR'}
              <input type="file" className="hidden" accept="image/*,.pdf" onChange={handleOcrUpload} />
            </label>
            <button
              onClick={handleObrirModalVehicle}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              Nou Actiu
            </button>
          </div>"""
text = text.replace(target_button, replace_button)

with open(path, "w") as f:
    f.write(text)

print("OCR UI patched")
