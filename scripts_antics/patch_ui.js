const fs = require('fs');
let content = fs.readFileSync("pwa/src/app/gestio/clients/page.tsx", "utf-8");

const newUI = `
            </div>

            {/* SEVALOR DIGITAL TWIN UI (Fitxa 360) */}
            {loadingFitxa ? (
              <div className="flex justify-center p-8">
                <RefreshCw className="w-6 h-6 text-emerald-500 animate-spin" />
              </div>
            ) : fitxa360 ? (
              <div className="space-y-6">
                
                {/* 1. INSTAL·LACIONS / FINQUES */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                    <MapPin className="w-4 h-4 text-emerald-600" />
                    Instal·lacions (Finques)
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                    {fitxa360.finques.length === 0 ? (
                      <p className="text-xs text-slate-400">Cap instal·lació registrada.</p>
                    ) : (
                      fitxa360.finques.map(f => (
                        <div key={f.id} className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                          <p className="text-xs font-bold text-slate-700 dark:text-slate-200">{f.nom}</p>
                          {f.adreca && <p className="text-[11px] text-slate-500 mt-1">{f.adreca}</p>}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* 2. ACTIUS I PECES INSTAL·LADES (Historico Materiales) */}
                <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                  <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                    <Package className="w-4 h-4 text-emerald-600" />
                    Actius & Peces Instal·lades (Últims 365 dies)
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-50 dark:bg-slate-800 text-slate-500">
                        <tr>
                          <th className="px-3 py-2 rounded-l-lg font-medium">Actiu / Material</th>
                          <th className="px-3 py-2 font-medium">Quantitat</th>
                          <th className="px-3 py-2 font-medium">OT Associada</th>
                          <th className="px-3 py-2 rounded-r-lg font-medium">Data Instal·lació</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {fitxa360.peces_instalades.length === 0 ? (
                          <tr><td colSpan={4} className="px-3 py-4 text-center text-slate-400">Sense històric d'actius instal·lats</td></tr>
                        ) : (
                          fitxa360.peces_instalades.map((p, i) => (
                            <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                              <td className="px-3 py-2 font-medium text-slate-700 dark:text-slate-300">{p.nom_article}</td>
                              <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{p.quantitat_instalada} {p.unitat_mesura}</td>
                              <td className="px-3 py-2"><span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded font-mono text-[10px] text-slate-600 dark:text-slate-400">{p.ordre_treball_codi}</span></td>
                              <td className="px-3 py-2 text-slate-500">{new Date(p.data_instalacio).toLocaleDateString()}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* 3. HISTÒRIC D'INTERVENCIONS I INCIDÈNCIES */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Treballs */}
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                      <Factory className="w-4 h-4 text-emerald-600" />
                      Històric Intervencions (OTs)
                    </h3>
                    <div className="space-y-2">
                      {fitxa360.intervencions.length === 0 ? (
                        <p className="text-xs text-slate-400">Sense intervencions recents.</p>
                      ) : (
                        fitxa360.intervencions.slice(0,5).map(ot => (
                          <a key={ot.id} href={'/gestio/feines?c=' + ot.codi} className="block p-3 rounded-xl border border-slate-100 dark:border-slate-800 hover:border-emerald-200 dark:hover:border-emerald-800 hover:bg-emerald-50/50 dark:hover:bg-emerald-900/10 transition-colors">
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-mono text-[10px] font-bold text-slate-500">{ot.codi}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">{ot.estat}</span>
                            </div>
                            <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{ot.titol}</p>
                            {ot.data_planificacio && <p className="text-[10px] text-slate-500 mt-1">Planificat: {new Date(ot.data_planificacio).toLocaleDateString()}</p>}
                          </a>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Incidencies */}
                  <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
                    <h3 className="text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2 mb-4">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      Incidències i Avaries
                    </h3>
                    <div className="space-y-2">
                      {fitxa360.incidencies.length === 0 ? (
                        <p className="text-xs text-slate-400">El client no té incidències.</p>
                      ) : (
                        fitxa360.incidencies.slice(0,5).map(inc => (
                          <div key={inc.id} className="p-3 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-mono text-[10px] font-bold text-amber-600 dark:text-amber-400">{inc.ambit}</span>
                              <span className="text-[10px] px-1.5 py-0.5 bg-white dark:bg-slate-900 rounded border border-slate-200 dark:border-slate-700">{inc.estat}</span>
                            </div>
                            <p className="text-xs text-slate-700 dark:text-slate-300 mt-1 line-clamp-2">{inc.text_observacions || "Sense observacions"}</p>
                            {inc.ordre_treball_codi && <p className="text-[10px] text-slate-500 mt-2">OT: {inc.ordre_treball_codi}</p>}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>

              </div>
            ) : null}
`;

const target = `              {clientSeleccionat.adreca_fiscal && (
                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400">
                  <MapPin className="w-4 h-4 text-slate-400 shrink-0" />
                  <span>{clientSeleccionat.adreca_fiscal}</span>
                </div>
              )}
            </div>`;

content = content.replace(target, target + newUI);

fs.writeFileSync("pwa/src/app/gestio/clients/page.tsx", content);
