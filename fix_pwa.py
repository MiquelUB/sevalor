import re

with open("pwa/src/app/gestio/magatzem/page.tsx", "r") as f:
    content = f.read()

# 1. Add estoc_real to Article interface
content = content.replace("actiu?: boolean;", "actiu?: boolean;\n  estoc_real?: number;")

# 2. Add state for the edit modal
state_injection = """  const [modalOcr, setModalOcr] = useState(false);
  const [modalEditarArticle, setModalEditarArticle] = useState(false);
  const [articleEditant, setArticleEditant] = useState<Article | null>(null);"""
content = content.replace("  const [modalOcr, setModalOcr] = useState(false);", state_injection)

# 3. Add handleEditarArticle
handle_editar_injection = """
  const handleDesarEdicio = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!articleEditant) return;
    setGuardant(true);
    setError(null);
    try {
      await apiFetch(`/gestio/magatzem/articles/${articleEditant.id}`, {
        method: "PUT",
        body: JSON.stringify({
          referencia_inventari: articleEditant.referencia_inventari,
          nom: articleEditant.nom,
          unitat_mesura: articleEditant.unitat_mesura,
          familia: articleEditant.familia,
          estoc_optim: Number(articleEditant.estoc_optim),
          estoc_minim: Number(articleEditant.estoc_minim),
          preu_cost: Number(articleEditant.preu_cost),
          preu_venda: Number(articleEditant.preu_venda),
          es_lot_caducable: articleEditant.es_lot_caducable || false,
        }),
      });
      setModalEditarArticle(false);
      setArticleEditant(null);
      await carregarArticles();
    } catch (err: any) {
      setError(err.message || "Error al modificar l'article");
    } finally {
      setGuardant(false);
    }
  };

  const obrirFitxa = (art: Article) => {
    setArticleEditant({ ...art });
    setModalEditarArticle(true);
  };
"""
content = content.replace("  const handleCrearArticle = async (e: React.FormEvent) => {", handle_editar_injection + "  const handleCrearArticle = async (e: React.FormEvent) => {")

# 4. Add onClick to tr and cursor-pointer
content = content.replace('<tr key={art.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">', '<tr key={art.id} onClick={() => obrirFitxa(art)} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors cursor-pointer">')

# 5. Add Estoc Real column to table header
content = content.replace('<th className="p-3 text-right">Estoc Mínim</th>', '<th className="p-3 text-right">Estoc Real</th>\n                    <th className="p-3 text-right">Estoc Mínim</th>')

# 6. Add Estoc Real column to table body
new_row_data = """                      <td className="p-3 font-mono text-slate-500">
                        {art.unitat_mesura}
                      </td>
                      <td className="p-3 text-right font-mono font-black text-indigo-600 dark:text-indigo-400">
                        {art.estoc_real ?? 0}
                      </td>"""
content = content.replace("""                      <td className="p-3 font-mono text-slate-500">
                        {art.unitat_mesura}
                      </td>""", new_row_data)

# 7. Add Modal to the bottom
modal_edit = """      {/* Modal Editar Article (Fitxa de Producte) */}
      {modalEditarArticle && articleEditant && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-800/50">
              <h3 className="font-bold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-2">
                <Package className="w-4 h-4 text-emerald-600" />
                Fitxa de Producte: {articleEditant.referencia_inventari}
              </h3>
              <button
                onClick={() => setModalEditarArticle(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors bg-white dark:bg-slate-800 shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-5">
              <form id="form-editar-article" onSubmit={handleDesarEdicio} className="space-y-4">
                {/* Dades Principals */}
                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 space-y-4">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Informació General</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Referència Inventari</label>
                      <input
                        type="text"
                        value={articleEditant.referencia_inventari}
                        onChange={(e) => setArticleEditant({ ...articleEditant, referencia_inventari: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Descripció del Producte</label>
                      <input
                        type="text"
                        value={articleEditant.nom}
                        onChange={(e) => setArticleEditant({ ...articleEditant, nom: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Família</label>
                      <select
                        value={articleEditant.familia}
                        onChange={(e) => setArticleEditant({ ...articleEditant, familia: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                        <option value="TUBERIA">Canonades i Tubs</option>
                        <option value="VALVULERIA">Valvuleria</option>
                        <option value="ACCESSORIS">Accessoris</option>
                        <option value="EINES">Eines de Custòdia</option>
                        <option value="GENERAL">General</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Unitat de Mesura</label>
                      <select
                        value={articleEditant.unitat_mesura}
                        onChange={(e) => setArticleEditant({ ...articleEditant, unitat_mesura: e.target.value })}
                        className="w-full p-2 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs"
                      >
                        <option value="UNITAT">Unitats (u)</option>
                        <option value="METRE">Metres (m)</option>
                        <option value="LITRE">Litres (L)</option>
                        <option value="QUILO">Quilograms (kg)</option>
                        <option value="CAIXA">Caixes</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Dades Econòmiques i Estoc */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 bg-emerald-50/50 dark:bg-emerald-900/10 rounded-2xl border border-emerald-100 dark:border-emerald-900/30 space-y-4">
                    <h4 className="text-xs font-bold text-emerald-600 dark:text-emerald-500 uppercase tracking-wider mb-2">Control d'Estoc</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Mínim</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.estoc_minim}
                          onChange={(e) => setArticleEditant({ ...articleEditant, estoc_minim: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Òptim</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.estoc_optim}
                          onChange={(e) => setArticleEditant({ ...articleEditant, estoc_optim: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div className="p-4 bg-indigo-50/50 dark:bg-indigo-900/10 rounded-2xl border border-indigo-100 dark:border-indigo-900/30 space-y-4">
                    <h4 className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider mb-2">Preus i Costos</h4>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Preu Cost (€)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.preu_cost}
                          onChange={(e) => setArticleEditant({ ...articleEditant, preu_cost: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-slate-600 dark:text-slate-400 mb-1">Preu Venda (€)</label>
                        <input
                          type="number"
                          step="0.01"
                          value={articleEditant.preu_venda}
                          onChange={(e) => setArticleEditant({ ...articleEditant, preu_venda: Number(e.target.value) })}
                          className="w-full p-2 rounded-xl border border-indigo-200 dark:border-indigo-800 bg-white dark:bg-slate-900 text-xs"
                          required
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </form>
            </div>
            
            <div className="p-5 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setModalEditarArticle(false)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                disabled={guardant}
              >
                Cancel·lar
              </button>
              <button
                type="submit"
                form="form-editar-article"
                disabled={guardant}
                className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-md shadow-emerald-500/20 disabled:opacity-50 flex items-center gap-2 transition-all"
              >
                {guardant ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Desant...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Desar Canvis</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
"""
content = content.replace("    </div>\n  );\n}", modal_edit + "\n    </div>\n  );\n}")

with open("pwa/src/app/gestio/magatzem/page.tsx", "w") as f:
    f.write(content)

