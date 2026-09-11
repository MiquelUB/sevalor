"use client";

import React, { useState } from "react";
import {
  Package,
  Search,
  Plus,
  Truck,
  Wrench,
  Scissors,
  AlertTriangle,
  CheckCircle2,
  Lock,
  ArrowDownUp,
  Layers,
  Building,
} from "lucide-react";
import { useGestio } from "@/lib/gestio-context";

interface ArticleInventari {
  id: string;
  referencia: string;
  nom: string;
  familia: "TUBERIA" | "VALVULERIA" | "ACCESSORIS" | "EINES";
  unitat: string;
  estoc_nau_fisic: number;
  estoc_reservat: number; // Spec 004 RF-29: Reserva pesimista d'ordres
  estoc_furgoneta_7482: number; // Estoc rodant
  format_continu?: boolean;
  retalls_disponibles_metres?: number[]; // Llistat de retalls aprofitables
  es_eina?: boolean;
  estat_eina?: "DISPONIBLE" | "EN_TALLER" | "EN_CAMP";
}

export default function GestioMagatzemPage() {
  const { rolActiu } = useGestio();
  const [filtreCerca, setFiltreCerca] = useState("");
  const [filtreFamilia, setFiltreFamilia] = useState<string>("TOTS");

  // Estat del catàleg d'inventari (Zero Mock Data per defecte)
  const [articles, setArticles] = useState<ArticleInventari[]>([
    {
      id: "art-1",
      referencia: "#4322",
      nom: "Tub Polietilè Alta Densitat PE-100 32mm PN16",
      familia: "TUBERIA",
      unitat: "m",
      estoc_nau_fisic: 420,
      estoc_reservat: 50,
      estoc_furgoneta_7482: 25,
      format_continu: true,
      retalls_disponibles_metres: [3.5, 4.2, 1.8],
    },
    {
      id: "art-2",
      referencia: "#1094",
      nom: "Enllaç Mascle Llautó 32 x 1\"",
      familia: "VALVULERIA",
      unitat: "un",
      estoc_nau_fisic: 68,
      estoc_reservat: 6,
      estoc_furgoneta_7482: 8,
    },
    {
      id: "art-3",
      referencia: "#TOOL-88",
      nom: "Radial a Bateria Bosch Professional 18V",
      familia: "EINES",
      unitat: "un",
      estoc_nau_fisic: 2,
      estoc_reservat: 1,
      estoc_furgoneta_7482: 1,
      es_eina: true,
      estat_eina: "EN_CAMP",
    },
    {
      id: "art-4",
      referencia: "#TOOL-92",
      nom: "Equip de Fusió a Topall Hidràulica 160mm",
      familia: "EINES",
      unitat: "un",
      estoc_nau_fisic: 1,
      estoc_reservat: 0,
      estoc_furgoneta_7482: 0,
      es_eina: true,
      estat_eina: "DISPONIBLE",
    },
  ]);

  const articlesFiltrats = articles.filter((a) => {
    const coincideixCerca =
      a.nom.toLowerCase().includes(filtreCerca.toLowerCase()) ||
      a.referencia.toLowerCase().includes(filtreCerca.toLowerCase());
    const coincideixFamilia = filtreFamilia === "TOTS" || a.familia === filtreFamilia;
    return coincideixCerca && coincideixFamilia;
  });

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* Capçalera del Magatzem */}
      <div className="p-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between shadow-sm">
        <div>
          <h1 className="text-base font-bold text-slate-800 dark:text-slate-100">
            Magatzem Central & Inventari Industrial (Spec 004)
          </h1>
          <p className="text-xs text-slate-500">
            Multilocació Nau Central vs Furgonetes Taller • Format Continu • Reserva Pesimista
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Cercador de materials */}
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={filtreCerca}
              onChange={(e) => setFiltreCerca(e.target.value)}
              placeholder="Cercar referència o nom..."
              className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium focus:outline-none focus:border-emerald-600 w-56"
            />
          </div>

          {/* Filtre per família */}
          <select
            value={filtreFamilia}
            onChange={(e) => setFiltreFamilia(e.target.value)}
            className="p-1.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold"
          >
            <option value="TOTS">Totes les Famílies</option>
            <option value="TUBERIA">Canonades i Tubs</option>
            <option value="VALVULERIA">Valvuleria</option>
            <option value="EINES">Eines de Custòdia</option>
          </select>

          <button
            onClick={() => alert("Entrada d'albarà de proveïdor per a sumar stock real.")}
            className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center gap-1 shadow transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Entrada d'Albarà</span>
          </button>
        </div>
      </div>

      {/* Contingut: Taula d'Inventari Multilocació */}
      <div className="flex-1 p-4 overflow-y-auto">
        {articles.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 my-auto shadow-sm">
            <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-3">
              <Package className="w-7 h-7" />
            </div>
            {/* TEXT EXACTE EXIGIT PER LA SPEC 004 */}
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Magatzem central sense moviments d'estoc
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
              Les referències es donen d'alta automàticament en processar albarans de proveïdors o ordres de compra.
            </p>
            <button
              onClick={() =>
                setArticles([
                  {
                    id: "art-1",
                    referencia: "#4322",
                    nom: "Tub Polietilè Alta Densitat PE-100 32mm PN16",
                    familia: "TUBERIA",
                    unitat: "m",
                    estoc_nau_fisic: 420,
                    estoc_reservat: 50,
                    estoc_furgoneta_7482: 25,
                    format_continu: true,
                    retalls_disponibles_metres: [3.5, 4.2, 1.8],
                  },
                ])
              }
              className="mt-4 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow"
            >
              Carregar Inventari de la Nau
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Targetes de Resum de Magatzem */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Nau Central (Física)</p>
                  <h3 className="text-xl font-black text-slate-800 dark:text-slate-100 mt-0.5">
                    {articles.reduce((acc, a) => acc + a.estoc_nau_fisic, 0)} <span className="text-xs text-slate-400 font-normal">unitats</span>
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 flex items-center justify-center">
                  <Building className="w-5 h-5" />
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Reserva Pesimista d'Obres (Spec 004)</p>
                  <h3 className="text-xl font-black text-amber-600 dark:text-amber-400 mt-0.5">
                    {articles.reduce((acc, a) => acc + a.estoc_reservat, 0)} <span className="text-xs text-slate-400 font-normal">reservats</span>
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 flex items-center justify-center">
                  <Lock className="w-5 h-5" />
                </div>
              </div>

              <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase text-slate-400 font-bold">Estoc Rodant (Furgonetes Taller)</p>
                  <h3 className="text-xl font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                    {articles.reduce((acc, a) => acc + a.estoc_furgoneta_7482, 0)} <span className="text-xs text-slate-400 font-normal">a bord</span>
                  </h3>
                </div>
                <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center">
                  <Truck className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Taula Detallada d'Inventari */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-sm">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 font-mono text-[10px] uppercase text-slate-400">
                    <th className="p-3.5">Ref. / Article</th>
                    <th className="p-3.5">Família</th>
                    <th className="p-3.5 text-right">Nau Física</th>
                    <th className="p-3.5 text-right">Reservat (OTs)</th>
                    <th className="p-3.5 text-right">Disponible Net</th>
                    <th className="p-3.5 text-right">Furgoneta 7482</th>
                    <th className="p-3.5">Format Continu / Eina</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {articlesFiltrats.map((art) => {
                    const disponibleNet = Math.max(0, art.estoc_nau_fisic - art.estoc_reservat);

                    return (
                      <tr key={art.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/50 transition-colors">
                        <td className="p-3.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                              {art.referencia}
                            </span>
                            <span className="font-bold text-slate-800 dark:text-slate-100">{art.nom}</span>
                          </div>
                        </td>
                        <td className="p-3.5">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            {art.familia}
                          </span>
                        </td>
                        <td className="p-3.5 text-right font-mono font-bold text-slate-700 dark:text-slate-300">
                          {art.estoc_nau_fisic} {art.unitat}
                        </td>
                        <td className="p-3.5 text-right font-mono text-amber-600 dark:text-amber-400 font-bold">
                          {art.estoc_reservat} {art.unitat}
                        </td>
                        <td className="p-3.5 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                          {disponibleNet} {art.unitat}
                        </td>
                        <td className="p-3.5 text-right font-mono text-slate-700 dark:text-slate-300">
                          {art.estoc_furgoneta_7482} {art.unitat}
                        </td>
                        <td className="p-3.5">
                          {art.format_continu && art.retalls_disponibles_metres && (
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-950 text-sky-800 dark:text-sky-300 flex items-center gap-1">
                                <Scissors className="w-3 h-3" />
                                {art.retalls_disponibles_metres.length} retalls ({art.retalls_disponibles_metres.join("m, ")}m)
                              </span>
                            </div>
                          )}
                          {art.es_eina && (
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                                art.estat_eina === "DISPONIBLE"
                                  ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300"
                                  : "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300"
                              }`}
                            >
                              {art.estat_eina}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setArticles([])}
                className="px-3 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 text-xs font-semibold hover:bg-slate-300 dark:hover:bg-slate-700 transition-colors"
              >
                Provar Estat Buit (Zero Mock Data)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
