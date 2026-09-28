import re

path = "pwa/src/app/gestio/flota/page.tsx"
with open(path, "r") as f:
    text = f.read()

target_button = """          <button
            onClick={() => {
              setNovaMatricula("");
              setNovaMarca("");
              setNouModel("");
              setModalNouVehicleObert(true);
            }}
            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Registrar Nou Vehicle</span>
          </button>"""

replace_button = """          <div className="flex items-center gap-2">
            <label className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm cursor-pointer transition-all ${ocrLoading ? 'opacity-50 pointer-events-none' : ''}`}>
              {ocrLoading ? <span className="animate-spin text-lg leading-none">⚙</span> : <span className="text-lg leading-none">✨</span>}
              <span>{ocrLoading ? 'Processant IA...' : 'Alta OCR'}</span>
              <input type="file" className="hidden" accept="image/*,.pdf" onChange={handleOcrUpload} />
            </label>
            <button
              onClick={() => {
                setNovaMatricula("");
                setNovaMarca("");
                setNouModel("");
                setModalNouVehicleObert(true);
              }}
              className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold flex items-center gap-1.5 shadow transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Registrar Nou Vehicle</span>
            </button>
          </div>"""

if target_button in text:
    text = text.replace(target_button, replace_button)
    print("Flota Button OCR Patched")
else:
    print("Button not found. Check again.")

with open(path, "w") as f:
    f.write(text)
