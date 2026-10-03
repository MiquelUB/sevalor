"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Save, AlertTriangle, FileText, Calendar, DollarSign, XCircle, FilePlus, RefreshCcw } from "lucide-react";
import { getAuthHeader } from "@/lib/auth";
import { getApiBaseUrl } from "@/lib/api";

export default function ContracteDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [contracte, setContracte] = useState<any>(null);
  
  // Actions states
  const [renovating, setRenovating] = useState(false);
  const [percentRenovacio, setPercentRenovacio] = useState(0.0);
  
  const [baixaMotiu, setBaixaMotiu] = useState("");
  const [isDarDeBaixa, setIsDarDeBaixa] = useState(false);
  
  const [prefacturant, setPrefacturant] = useState(false);

  useEffect(() => {
    fetchContracte();
  }, []);

  const fetchContracte = async () => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/gestio/contractes/${params.id}`, {
        headers: getAuthHeader(),
      });
      if (res.ok) {
        setContracte(await res.json());
      } else {
        alert("Contracte no trobat");
        router.push("/gestio/contractes");
      }
    } catch (e) { console.error(e) } finally {
      setLoading(false);
    }
  };

  const handleRenovar = async () => {
    setRenovating(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/gestio/contractes/${params.id}/renovar`, {
        method: "POST",
        headers: { ...getAuthHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ increment_percent: percentRenovacio })
      });
      if (res.ok) {
        alert("Renovat correctament");
        fetchContracte();
      } else {
        const err = await res.json();
        alert(err.detail || "Error renovant");
      }
    } catch(e) { console.error(e) } finally { setRenovating(false); }
  };

  const handleBaixa = async () => {
    if(!baixaMotiu.trim()) { alert("Indica el motiu de la baixa"); return; }
    if(confirm("N'estàs segur de donar de baixa? Les revisions pendents es cancel·laran.")) {
      setIsDarDeBaixa(true);
      try {
        const res = await fetch(`${getApiBaseUrl()}/gestio/contractes/${params.id}/baixa`, {
          method: "POST",
          headers: { ...getAuthHeader(), "Content-Type": "application/json" },
          body: JSON.stringify({ motiu: baixaMotiu })
        });
        if (res.ok) fetchContracte();
      } catch(e) { console.error(e) } finally { setIsDarDeBaixa(false); }
    }
  };

  const handlePrefacturar = async () => {
    setPrefacturant(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/gestio/contractes/${params.id}/prefacturar`, {
        method: "POST",
        headers: getAuthHeader(),
      });
      if (res.ok) {
        const d = await res.json();
        alert(`Pre-factura generada: ID ${d.factura_id}`);
      } else {
        const err = await res.json();
        alert(err.detail);
      }
    } catch(e) { console.error(e) } finally { setPrefacturant(false); }
  };

  if (loading) return <div className="p-8 text-slate-500">Carregant...</div>;
  if (!contracte) return null;

  return (
    <div className="p-4 md:p-8 max-w-5xl mx-auto space-y-6">
      <Link href="/gestio/contractes" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white mb-2 transition-colors">
        <ArrowLeft className="w-4 h-4" />
        Tornar a Contractes
      </Link>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            Contracte {contracte.numero_contracte}
            {contracte.estat === "ACTIU" && <span className="bg-emerald-100 text-emerald-800 text-[10px] px-2 py-0.5 rounded font-bold">ACTIU</span>}
            {contracte.estat === "BAIXA" && <span className="bg-red-100 text-red-800 text-[10px] px-2 py-0.5 rounded font-bold">BAIXA</span>}
          </h1>
          <p className="text-sm font-mono text-slate-500 mt-1">ID: {contracte.id}</p>
        </div>
        
        {contracte.estat === "ACTIU" && (
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrefacturar}
              disabled={prefacturant}
              className="bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-700 px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors disabled:opacity-50"
            >
              <FilePlus className="w-4 h-4 text-blue-500" />
              Generar Pre-factura
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Detalls principals */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-xl shadow-sm md:col-span-2 space-y-4">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Informació del Contracte
          </h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-slate-500">Client ID</p>
              <p className="font-mono text-slate-900 dark:text-white font-medium">{contracte.client_id}</p>
            </div>
            <div>
              <p className="text-slate-500">Import Anual</p>
              <p className="font-mono text-emerald-600 dark:text-emerald-400 font-bold text-lg">{contracte.import_anual.toFixed(2)} €</p>
            </div>
            <div>
              <p className="text-slate-500">Data Inici</p>
              <p className="font-medium text-slate-900 dark:text-white flex items-center gap-1"><Calendar className="w-3.5 h-3.5 text-slate-400"/> {contracte.data_inici}</p>
            </div>
            <div>
              <p className="text-slate-500">Data Fi</p>
              <p className="font-medium text-slate-900 dark:text-white flex items-center gap-1"><Calendar className="w-3.5 h-3.5 text-slate-400"/> {contracte.data_fi || 'Indefinit'}</p>
            </div>
            <div>
              <p className="text-slate-500">Periodicitat</p>
              <p className="font-medium text-slate-900 dark:text-white">{contracte.periodicitat}</p>
            </div>
          </div>
          {contracte.observacions && (
            <div className="pt-4 border-t border-slate-100 dark:border-slate-800">
              <p className="text-slate-500 text-xs uppercase mb-1 font-bold">Observacions</p>
              <p className="text-slate-700 dark:text-slate-300 text-sm whitespace-pre-wrap">{contracte.observacions}</p>
            </div>
          )}
          {contracte.estat === "BAIXA" && contracte.motiu_baixa && (
            <div className="pt-4 border-t border-red-100 dark:border-red-900/50">
              <p className="text-red-500 text-xs uppercase mb-1 font-bold">Motiu de Baixa</p>
              <p className="text-red-700 dark:text-red-400 text-sm">{contracte.motiu_baixa}</p>
            </div>
          )}
        </div>

        {/* Accions Laterals */}
        <div className="space-y-6">
          {contracte.estat === "ACTIU" ? (
            <>
              {/* Renovar */}
              <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 p-5 rounded-xl shadow-sm">
                <h3 className="font-bold text-slate-800 dark:text-slate-200 text-sm flex items-center gap-2 mb-3">
                  <RefreshCcw className="w-4 h-4 text-primary-500" /> Renovar
                </h3>
                <p className="text-xs text-slate-500 mb-3">Allarga el contracte 1 any des de la data de fi amb l'increment de preu desitjat (%).</p>
                <div className="flex gap-2">
                  <input 
                    type="number" 
                    step="0.1" 
                    value={percentRenovacio}
                    onChange={(e) => setPercentRenovacio(parseFloat(e.target.value) || 0)}
                    placeholder="0.0 %"
                    className="w-20 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-600 rounded px-2 text-sm"
                  />
                  <button onClick={handleRenovar} disabled={renovating} className="flex-1 bg-primary-600 text-white rounded text-sm font-bold py-1.5 hover:bg-primary-700 disabled:opacity-50">
                    Aplicar IPC
                  </button>
                </div>
              </div>

              {/* Donar de baixa */}
              <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/30 p-5 rounded-xl shadow-sm">
                <h3 className="font-bold text-red-700 dark:text-red-400 text-sm flex items-center gap-2 mb-3">
                  <XCircle className="w-4 h-4" /> Donar de Baixa
                </h3>
                <input 
                  type="text"
                  value={baixaMotiu}
                  onChange={(e) => setBaixaMotiu(e.target.value)}
                  placeholder="Motiu de la baixa..."
                  className="w-full bg-white dark:bg-slate-900 border border-red-300 dark:border-red-800 rounded px-3 py-2 text-sm mb-2 focus:ring-red-500 focus:border-red-500 dark:text-white"
                />
                <button onClick={handleBaixa} disabled={isDarDeBaixa} className="w-full bg-red-600 text-white rounded text-sm font-bold py-2 hover:bg-red-700 disabled:opacity-50">
                  Cancel·lar Contracte
                </button>
              </div>
            </>
          ) : (
            <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 p-5 rounded-xl shadow-sm text-center">
              <p className="text-sm font-bold text-slate-500">Contracte inactiu</p>
              <p className="text-xs text-slate-400 mt-1">No es permeten accions de renovació o facturació sobre contractes donats de baixa.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
