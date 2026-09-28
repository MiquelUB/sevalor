path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

# 1. Imports
text = text.replace('import { apiFetch } from "@/lib/api";', 'import { apiFetch, getApiBaseUrl } from "@/lib/api";')

# 2. State
target_state = "const [modalNouVehicleObert, setModalNouVehicleObert] = useState<boolean>(false);"
replace_state = """const [modalNouVehicleObert, setModalNouVehicleObert] = useState<boolean>(false);
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);"""
text = text.replace(target_state, replace_state)

# 3. Handler
target_handler = "  // Carregar vehicles des del backend"
replace_handler = """
  const handleOcrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
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
        
        setModalNouVehicleObert(true);
      } else {
        alert("Error processant OCR");
      }
    } catch (err) {
      alert("Error de xarxa OCR: " + err);
    } finally {
      setOcrLoading(false);
      e.target.value = "";
    }
  };

  // Carregar vehicles des del backend"""
text = text.replace(target_handler, replace_handler)

# 4. Button
import re
target_button_regex = r'<button[^>]*onClick=\{handleObrirModalVehicle\}[^>]*>[\s\S]*?Nou Actiu[\s\S]*?</button>'

replace_button = """<div className="flex items-center gap-2">
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

# Ensure the button replacement is only done once, in the header area
match = re.search(target_button_regex, text)
if match:
    text = text[:match.start()] + replace_button + text[match.end():]
else:
    print("Button target not found. Let's try searching manually.")

with open(path, "w") as f:
    f.write(text)

print("Flota OCR patched successfully")
