"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Settings, Cpu, HardDrive, Server, Smartphone, Wrench, FileText } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { db } from "@/lib/offline/db";

interface Asset {
  id: string;
  nom: string;
  model: string;
  tipus: string;
  num_serie: string;
  estat: string;
}

interface OrdreDetall {
  id: string;
  codi: string;
  titol: string;
  client: string;
  estat: string;
  assets: Asset[];
}

export default function LlistaMaquinesPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  
  const [ordre, setOrdre] = useState<OrdreDetall | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const fetchDades = async () => {
      setLoading(true);
      
      const checkOffline = typeof navigator !== "undefined" && !navigator.onLine;
      setIsOffline(checkOffline);
      
      try {
        if (checkOffline) {
          // Offline: we don't have PIN to decrypt db.ordres, so we simulate reading from cache if it were plaintext.
          // Since it's mandated to load from Dexie, and we only have EncryptedRecord schema, we'll try to find it.
          // But actually we can't decrypt without the key. So we will mock an error or empty state as required by Zero Mock Data.
          throw new Error("Offline, cal PIN per desxifrar. Aquesta versió no manté el PIN en memòria.");
        } else {
          // Fetch from API
          const data = await apiFetch<any>(`/operari/feines/${id}`);
          if (data) {
            setOrdre({
              id: String(data.id),
              codi: data.codi || "OT-00",
              titol: data.titol || "Detall de l'Ordre",
              client: data.client?.rao_social || "Client",
              estat: data.estat || "PENDENT",
              assets: data.assets || [],
            });
          }
        }
      } catch (err) {
        setOrdre(null);
      } finally {
        setLoading(false);
      }
    };

    fetchDades();
  }, [id]);

  const getAssetIcon = (tipus: string) => {
    switch(tipus?.toUpperCase()) {
      case "SERVIDOR": return <Server className="w-5 h-5" />;
      case "XARXA": return <HardDrive className="w-5 h-5" />;
      case "IOT": return <Cpu className="w-5 h-5" />;
      case "MOBILE": return <Smartphone className="w-5 h-5" />;
      default: return <Settings className="w-5 h-5" />;
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors p-4 space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-full hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Fitxa 360 - {ordre ? ordre.codi : id}
        </h1>
      </div>

      {loading ? (
        <div className="text-center py-10 text-slate-400">
          <Wrench className="w-8 h-8 animate-spin mx-auto mb-2" />
          <p className="text-xs">Carregant dades...</p>
        </div>
      ) : !ordre ? (
        <div className="text-center py-10 bg-white dark:bg-slate-900 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800">
          <FileText className="w-8 h-8 mx-auto text-slate-400 mb-2" />
          <p className="text-sm font-bold text-slate-700 dark:text-slate-300">
            {isOffline ? "No s'ha pogut desxifrar la fitxa offline (falta PIN)." : "No s'ha trobat l'ordre de treball."}
          </p>
        </div>
      ) : (
        <>
          <div className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
            <h2 className="text-sm font-bold text-slate-800 dark:text-slate-100">{ordre.titol}</h2>
            <p className="text-xs text-slate-500 mt-1">{ordre.client} • {ordre.estat}</p>
          </div>

          <h3 className="text-sm font-bold mt-4 mb-2 text-slate-700 dark:text-slate-300 px-1">
            Màquines i Actius Assignats
          </h3>
          
          {ordre.assets.length === 0 ? (
            <div className="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 text-center shadow-sm">
              <Settings className="w-8 h-8 mx-auto text-slate-300 dark:text-slate-700 mb-2" />
              <p className="text-sm font-bold text-slate-600 dark:text-slate-400">Cap màquina associada</p>
            </div>
          ) : (
            <div className="space-y-3">
              {ordre.assets.map(asset => (
                <div key={asset.id} className="bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center gap-3">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-slate-500 dark:text-slate-400">
                    {getAssetIcon(asset.tipus)}
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-slate-800 dark:text-slate-100">{asset.nom}</h4>
                    <p className="text-[10px] font-mono text-slate-500">{asset.model} • SN: {asset.num_serie}</p>
                  </div>
                  <span className="text-[9px] font-bold px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {asset.estat}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
