const fs = require('fs');
const path = 'pwa/src/app/gestio/magatzem/page.tsx';
let content = fs.readFileSync(path, 'utf8');

const modalOcrCode = `
      {/* MODAL OCR */}
      {modalOcr && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden border border-slate-200">
            <div className="p-4 border-b border-slate-200 flex justify-between items-center bg-slate-50">
              <h3 className="font-bold text-slate-800 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-500" />
                Entrada Assistida IA (OCR)
              </h3>
              <button onClick={() => setModalOcr(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              <p className="text-sm text-slate-600 mb-4">
                Puja una imatge o PDF d'un albarà o factura i el sistema n'extraurà automàticament les línies,
                quantitats, proveïdor i possibles descomptes.
              </p>
              
              <div className="border-2 border-dashed border-slate-300 rounded-xl p-8 flex flex-col items-center justify-center bg-slate-50">
                <UploadCloud className="w-10 h-10 text-slate-400 mb-2" />
                <span className="text-sm font-medium text-slate-700">Fes clic o arrossega un fitxer</span>
                <span className="text-xs text-slate-500 mt-1">PDF, JPG, PNG (Max 5MB)</span>
                <input 
                  type="file" 
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    alert("Aquesta funcionalitat requereix el servidor OCR en producció. (Fase 1 Connectada)");
                    setModalOcr(false);
                  }}
                />
              </div>
            </div>
            <div className="p-4 border-t border-slate-200 flex justify-end gap-2 bg-slate-50">
              <button onClick={() => setModalOcr(false)} className="px-4 py-2 text-sm font-bold text-slate-600 bg-white border border-slate-300 rounded-xl hover:bg-slate-50 shadow-sm">
                Cancel·lar
              </button>
            </div>
          </div>
        </div>
      )}
`;

content = content.replace('{/* MODAL NOU ARTICLE */}', modalOcrCode + '\n      {/* MODAL NOU ARTICLE */}');

fs.writeFileSync(path, content, 'utf8');
