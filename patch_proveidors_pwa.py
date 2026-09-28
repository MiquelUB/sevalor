import re

path = "pwa/src/app/gestio/proveidors/page.tsx"
with open(path, "r") as f:
    text = f.read()

# 1. Add state for OCR Loading
target_state = """  const [modalAltaObert, setModalAltaObert] = useState(false);"""
replace_state = """  const [modalAltaObert, setModalAltaObert] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);"""
text = text.replace(target_state, replace_state)

# 2. Add OCR File handler
target_handler = """  const fetchProveidors = async () => {"""
replace_handler = """  const handleOcrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setOcrLoading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = localStorage.getItem("sevalor_auth_token") ? JSON.parse(localStorage.getItem("sevalor_auth_token")!).token : "";
      
      const res = await fetch(`${getApiBaseUrl()}/gestio/proveidors/ocr-draft`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-Empresa-ID": localStorage.getItem("sevalor_tenant_id") || ""
        },
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        setNouNif(data.nif || "");
        setNovaRaoSocial(data.rao_social || "");
        setNouEmail(data.email || "");
        setNouTelefon(data.telefon || "");
        if (data.iban) setNouIban(data.iban);
        
        setModalAltaObert(true);
      } else {
        alert("Error processant OCR del Proveïdor");
      }
    } catch (err) {
      alert("Error de xarxa OCR: " + err);
    } finally {
      setOcrLoading(false);
      e.target.value = "";
    }
  };

  const fetchProveidors = async () => {"""
text = text.replace(target_handler, replace_handler)

# 3. Add OCR Button UI next to "Alta Nou Proveïdor"
target_button = """          <button
            onClick={() => {
              setNovaRaoSocial("");
              setNouNif("");
              setNouTelefon("");
              setNouEmail("");
              setModalAltaObert(true);
            }}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Alta Nou Proveïdor</span>
          </button>"""
replace_button = """          <div className="flex items-center gap-2">
            <label className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm cursor-pointer transition-all ${ocrLoading ? 'opacity-50 pointer-events-none' : ''}`}>
              {ocrLoading ? <span className="animate-spin text-lg leading-none">⚙</span> : <span className="text-lg leading-none">✨</span>}
              <span>{ocrLoading ? 'Processant IA...' : 'Alta OCR'}</span>
              <input type="file" className="hidden" accept="image/*,.pdf" onChange={handleOcrUpload} />
            </label>
            <button
              onClick={() => {
                setNovaRaoSocial("");
                setNouNif("");
                setNouTelefon("");
                setNouEmail("");
                setNouIban("");
                setModalAltaObert(true);
              }}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Alta Nou Proveïdor</span>
            </button>
          </div>"""
text = text.replace(target_button, replace_button)

with open(path, "w") as f:
    f.write(text)

print("OCR UI patched for proveidors")
